"""Assemblage de JARVIS : chaque module a une responsabilité claire et est relié ici."""
from __future__ import annotations

import importlib.util
import json
import threading
from typing import Any, Dict, List, Optional

from . import VERSION, paths
from .config import Settings
from .connectors import Connectors
from .conversations import Conversations
from .db import Database, now
from .errors import ValidationError
from .logbook import EventBus, Logbook
from .maintenance import Backups, Diagnostics, apply_pending_restore
from .memory import Memory
from .permissions import Permissions
from .projects import Projects, Reminders
from .providers.base import ProviderManager
from .providers.claude_code import ClaudeCodeProvider
from .providers.others import AnthropicAPIProvider, OllamaProvider, OpenAICompatibleProvider
from .scheduler import Scheduler
from .services import Notifier, Secrets, Voice
from .tasks import TaskManager
from .tools import browser, data_tools, documents, files, shell, sites, web
from .tools.registry import ToolRegistry

_CURRENT: Optional["JarvisApp"] = None


def current_app() -> "JarvisApp":
    if _CURRENT is None:
        raise RuntimeError("JARVIS n'est pas initialisé")
    return _CURRENT


class JarvisApp:
    def __init__(self, port: int = 8765, start_background: bool = True):
        global _CURRENT
        _CURRENT = self
        self.port = port
        from .relocation import fix_allowed_dirs, migrate_legacy
        self.relocated = migrate_legacy()
        self.restored = apply_pending_restore()
        self.db = Database()
        self.migrations = self.db.migrate()
        self.bus = EventBus()
        self.logbook = Logbook(self.db, self.bus)
        self.settings = Settings(self.db)
        fix_allowed_dirs(self.settings)
        self.permissions = Permissions(self.db, self.settings)
        self.secrets = Secrets()
        self.notifier = Notifier(self.db, self.settings, self.bus)
        self.voice = Voice(self.settings, self.bus)
        self.memory = Memory(self.db, self.logbook)
        self.conversations = Conversations(self.db)
        self.projects = Projects(self.db)
        self.reminders = Reminders(self.db)
        self.providers = ProviderManager(self)
        for p in (ClaudeCodeProvider(self), OllamaProvider(self), AnthropicAPIProvider(self), OpenAICompatibleProvider(self)):
            self.providers.register(p)
        self.tools = ToolRegistry(self)
        for mod in (files, shell, web, browser, sites, documents, data_tools):
            mod.register(self.tools)
        self.plugins = self._load_plugins()
        self.tasks = TaskManager(self)
        self.scheduler = Scheduler(self)
        self.connectors = Connectors(self)
        self.diagnostics = Diagnostics(self)
        self.backups = Backups(self)
        self.started_at = now()
        import time as _time
        self.started_ts = _time.time()
        interrupted = self.tasks.recover()
        self.scheduler.defaults()
        self.logbook.log("demarrage", f"JARVIS {VERSION} démarré" + (f" · {interrupted} tâche(s) interrompue(s)" if interrupted else "")
                         + (" · restauration appliquée" if self.restored else "") + (f" · migrations {self.migrations}" if self.migrations else ""),
                         "succes")
        if start_background:
            self.scheduler.start()
            threading.Thread(target=self._daily_backup, daemon=True).start()

    def notify(self, kind: str, title: str, body: str = ""):
        return self.notifier.notify(kind, title, body)

    def _daily_backup(self) -> None:
        try:
            today = now()[:10].replace("-", "")
            if not any(today in b["name"] for b in self.backups.list()):
                self.backups.create("quotidienne automatique")
        except Exception as e:  # noqa: BLE001
            self.logbook.log("sauvegarde", f"Sauvegarde quotidienne impossible : {e}", "erreur")

    # -- plugins ---------------------------------------------------------------------------
    def _load_plugins(self) -> List[Dict[str, Any]]:
        """Plugins : plugins/<nom>/plugin.json + plugin.py. Désactivés par défaut ; chaque plugin
        déclare ses outils et le risque maximal demandé ; il n'obtient aucun droit implicite."""
        out = []
        root = paths.ROOT / "plugins"
        enabled = self.settings.get("plugins_enabled", []) or []
        if not root.is_dir():
            return out
        for d in sorted(root.iterdir()):
            mf = d / "plugin.json"
            if not mf.exists():
                continue
            try:
                man = json.loads(mf.read_text(encoding="utf-8"))
            except ValueError:
                out.append({"id": d.name, "error": "manifeste illisible", "enabled": False})
                continue
            info = {"id": man.get("id", d.name), "name": man.get("name", d.name), "version": man.get("version", "?"),
                    "tools": man.get("tools", []), "max_risk": man.get("max_risk", "faible"), "enabled": d.name in enabled}
            if info["enabled"]:
                try:
                    spec = importlib.util.spec_from_file_location(f"jarvis_plugin_{d.name}", d / "plugin.py")
                    mod = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(mod)
                    before = set(self.tools.ids())
                    mod.register(self.tools)
                    added = set(self.tools.ids()) - before
                    undeclared = added - set(info["tools"])
                    for tid in added:
                        t = self.tools.get(tid)
                        order = ["faible", "modere", "eleve"]
                        if isinstance(t.risk, str) and order.index(t.risk) > order.index(info["max_risk"]):
                            raise ValidationError(f"L'outil {tid} dépasse le risque déclaré par le plugin.")
                    if undeclared:
                        raise ValidationError(f"Outils non déclarés : {sorted(undeclared)}")
                    info["loaded"] = True
                except Exception as e:  # noqa: BLE001
                    for tid in set(self.tools.ids()) - before:
                        self.tools._tools.pop(tid, None)
                    info["loaded"] = False
                    info["error"] = str(e)
            out.append(info)
        return out

    # -- conversation -------------------------------------------------------------------------
    def send_message(self, conversation_id: Optional[int], text: str, project_id: Optional[int] = None,
                     agent: str = "general", source: str = "texte", client_ts: Optional[float] = None,
                     voice_out: str = "mac") -> Dict[str, Any]:
        text = (text or "").strip()
        if not text:
            raise ValidationError("Message vide.")
        if conversation_id is None:
            conv = self.conversations.create(text[:60], project_id)
            conversation_id = conv["id"]
        else:
            conv = self.conversations.get(conversation_id)
        msg = self.conversations.add_message(conversation_id, "user", text, {"source": source})
        self.bus.publish({"type": "message", "conversation_id": conversation_id})
        live: Any = source == "voix" or bool(self.settings.get("voice.auto_speak"))
        if live:
            # « client » : la réponse est envoyée en phrases (événements « speech ») à l'appareil qui parle avec Sacha (Nova)
            live = "client" if voice_out == "client" else "mac"
        task = self.tasks.create(text, text[:100], "conversation", agent, conversation_id, conv.get("project_id") or project_id,
                                 live_voice=live, client_ts=client_ts)
        self._maybe_summarize(conversation_id)
        return {"conversation_id": conversation_id, "message": msg, "task_id": task["id"]}

    def _maybe_summarize(self, cid: int) -> None:
        """Conversations longues : les anciens messages sont résumés pour ne pas renvoyer tout l'historique."""
        n = self.db.one("SELECT count(*) AS n FROM messages WHERE conversation_id=?", (cid,))["n"]
        if n < 30 or n % 15:
            return

        def work():
            try:
                old = self.conversations.messages(cid, 400)[:-14]
                text = "\n".join(f"{m['role']}: {m['content'][:600]}" for m in old)[-30000:]
                c = self.providers.complete("Tu résumes des conversations en français, de façon factuelle, en 12 lignes max : "
                                            "décisions, faits, demandes en cours, préférences exprimées.", text,
                                            model=self.settings.get("ai.fallback_model"))
                self.conversations.set_summary(cid, c.text.strip())
            except Exception as e:  # noqa: BLE001
                self.logbook.log("ia", f"Résumé de conversation impossible : {e}", "attention", conversation_id=cid)

        threading.Thread(target=work, daemon=True).start()

    # -- état du noyau (dérivé de l'état réel) ----------------------------------------------
    def core_state(self) -> Dict[str, Any]:
        running = self.tasks.running()
        pending = self.db.one("SELECT count(*) AS n FROM confirmations WHERE status='en_attente'")["n"]
        last_err = self.db.one("SELECT ts, message FROM events WHERE level='erreur' ORDER BY id DESC LIMIT 1")
        last_tool = None
        if running:
            last_tool = self.db.one("SELECT tool, status, kind FROM task_steps WHERE task_id IN (%s) ORDER BY id DESC LIMIT 1"
                                    % ",".join("?" * len(running)), running)
        if pending:
            state = "autorisation"
        elif running and last_tool and last_tool["kind"] == "outil" and last_tool["status"] == "en_cours":
            state = "outil"
        elif running and last_tool and last_tool["kind"] == "modele" and last_tool["status"] == "en_cours":
            state = "reflexion"
        elif running:
            state = "tache"
        else:
            state = "attente"
        return {"state": state, "running": running, "pending_confirmations": pending, "speaking": self.voice.speaking(),
                "last_error": last_err}

    def shutdown(self) -> None:
        self.logbook.log("arret", "Arrêt propre de JARVIS demandé", "info")
        self.scheduler.stop()
        running = self.tasks.running()
        for tid in running:
            ev = self.tasks._cancel.get(tid)
            if ev:
                ev.set()
        # laisse aux tâches le temps de s'arrêter (et de tuer leurs sous-processus) avant de quitter
        import time as _time
        end = _time.time() + 6
        while self.tasks.running() and _time.time() < end:
            _time.sleep(0.1)
        self.voice.stop()
        browser.shutdown(self)
        for p in self.db.all("SELECT id, pid FROM processes WHERE stopped_at IS NULL"):
            try:
                import os
                import signal
                os.killpg(p["pid"], signal.SIGTERM)
            except Exception:  # noqa: BLE001
                pass
            self.db.execute("UPDATE processes SET stopped_at=? WHERE id=?", (now(), p["id"]))
