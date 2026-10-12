"""API locale de JARVIS (HTTP + flux d'événements SSE) et service de l'interface.

Sécurité réseau :
- écoute sur 127.0.0.1 uniquement ;
- en-tête Host vérifié (anti « DNS rebinding ») et Origin vérifiée si présente ;
- jeton aléatoire par démarrage, exigé sur toute l'API (en-tête X-Jarvis-Token,
  ou ?token= pour le flux SSE) ; une page web tierce ne peut ni le lire ni l'envoyer ;
- les droits sont contrôlés ici et dans les modules : l'interface ne peut pas s'en accorder.
"""
from __future__ import annotations

import json
import mimetypes
import os
import queue
import re
import secrets
import threading
import time
import traceback
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable, Dict, List, Optional, Tuple

from . import VERSION, paths
from .agent import profiles
from .config import MODES, touches_sensitive
from .db import loads
from .errors import ConfirmationRequired, JarvisError, NotFound, ValidationError
from .scheduler import ACTIONS, TRIGGERS
from .services import list_apps, system_info
from .tools.registry import ToolContext

Route = Tuple[str, re.Pattern, Callable]


class Api:
    def __init__(self, app, token: str):
        self.app = app
        self.token = token
        self.routes: List[Route] = []
        r = self.add
        r("GET", r"/api/state", self.state)
        r("POST", r"/api/chat", self.chat)
        r("GET", r"/api/conversations", lambda q, b: self.app.conversations.list(q.get("archived") == "1",
                                                                                   _int(q.get("project")), q.get("q", "")))
        r("POST", r"/api/conversations", lambda q, b: self.app.conversations.create(b.get("title", "Nouvelle conversation"), b.get("project_id")))
        r("GET", r"/api/conversations/(\d+)", self.conv_get)
        r("PATCH", r"/api/conversations/(\d+)", self.conv_patch)
        r("DELETE", r"/api/conversations/(\d+)", lambda q, b, i: (self.app.conversations.delete(int(i)), {"deleted": True})[1])
        r("GET", r"/api/conversations/(\d+)/export", lambda q, b, i: {"markdown": self.app.conversations.export_markdown(int(i))})
        r("GET", r"/api/search", self.search)
        r("GET", r"/api/tasks", lambda q, b: self.app.tasks.list(q.get("status", ""), _int(q.get("project")), q.get("chat") == "1"))
        r("POST", r"/api/tasks", self.task_create)
        r("GET", r"/api/tasks/(\d+)", lambda q, b, i: self.app.tasks.detail(int(i)))
        r("POST", r"/api/tasks/(\d+)/(cancel|pause|resume|complete|start)", self.task_action)
        r("GET", r"/api/confirmations", lambda q, b: self.app.permissions.pending())
        r("POST", r"/api/confirmations/(\d+)", self.confirm)
        r("GET", r"/api/memory", lambda q, b: {"items": self.app.memory.search(q.get("q", ""), q.get("type", ""), _int(q.get("project")), 300,
                                                                                q.get("obsolete") == "1"), "stats": self.app.memory.stats(),
                                               "duplicates": len(self.app.memory.duplicates())})
        r("POST", r"/api/memory", lambda q, b: self.app.memory.add(b.get("content", ""), b.get("type", "connaissance"), "saisie de Sacha",
                                                                   b.get("nature", "fait"), b.get("reason", "ajout manuel"), b.get("confidence"),
                                                                   b.get("project_id")))
        r("PATCH", r"/api/memory/(\d+)", lambda q, b, i: self.app.memory.update(int(i), **{k: b.get(k) for k in
                                                                                           ("content", "type", "nature", "status", "reason", "project_id")}))
        r("DELETE", r"/api/memory/(\d+)", lambda q, b, i: (self.app.memory.forget(int(i)), {"forgotten": True})[1])
        r("GET", r"/api/memory/export", lambda q, b: self.app.memory.export(_int(q.get("project"))))
        r("POST", r"/api/memory/import", lambda q, b: self.app.memory.import_(b))
        r("POST", r"/api/memory/cleanup", lambda q, b: self.app.memory.cleanup())
        r("DELETE", r"/api/memory/project/(\d+)", lambda q, b, i: {"deleted": self.app.memory.forget_project(int(i))})
        r("GET", r"/api/projects", lambda q, b: self.app.projects.list(q.get("all") == "1"))
        r("POST", r"/api/projects", lambda q, b: self.app.projects.create(b.get("name", ""), **{k: v for k, v in b.items() if k != "name"}))
        r("GET", r"/api/projects/(\d+)", lambda q, b, i: self.app.projects.detail(int(i)))
        r("PATCH", r"/api/projects/(\d+)", lambda q, b, i: self.app.projects.update(int(i), **b))
        r("POST", r"/api/projects/(\d+)/decisions", lambda q, b, i: self.app.projects.add_decision(int(i), b.get("decision", ""), b.get("reason", "")))
        r("GET", r"/api/projects/(\d+)/report", lambda q, b, i: {"markdown": self.app.projects.report(int(i))})
        r("GET", r"/api/reminders", lambda q, b: self.app.reminders.list(q.get("all") == "1"))
        r("POST", r"/api/reminders", lambda q, b: self.app.reminders.add(b.get("title", ""), b.get("due_at", ""), b.get("project_id")))
        r("POST", r"/api/reminders/(\d+)/done", lambda q, b, i: (self.app.reminders.complete(int(i)), {"done": True})[1])
        r("GET", r"/api/automations", lambda q, b: {"items": self.app.scheduler.list(), "triggers": TRIGGERS, "actions": ACTIONS})
        r("POST", r"/api/automations", self.auto_create)
        r("POST", r"/api/automations/(\d+)/(enable|disable|run)", self.auto_action)
        r("DELETE", r"/api/automations/(\d+)", lambda q, b, i: (self.app.scheduler.delete(int(i)), {"deleted": True})[1])
        r("GET", r"/api/notifications", lambda q, b: self.app.notifier.list(q.get("unread") == "1"))
        r("POST", r"/api/notifications/read", lambda q, b: (self.app.notifier.mark_read(b.get("id")), {"ok": True})[1])
        r("GET", r"/api/journal", lambda q, b: self.app.logbook.search(q.get("q", ""), q.get("kind", ""), q.get("level", ""),
                                                                        _int(q.get("task_id")), int(q.get("limit", 200))))
        r("GET", r"/api/journal/export", lambda q, b: {"markdown": self.app.logbook.export_markdown(_int(q.get("task_id")))})
        r("GET", r"/api/tools", lambda q, b: self.app.tools.listing())
        r("POST", r"/api/tools/([a-z_]+)/invoke", self.tool_invoke)
        r("GET", r"/api/agents", lambda q, b: profiles.listing())
        r("GET", r"/api/settings", lambda q, b: {"settings": self.app.settings.all(), "modes": MODES, "versions": self.app.settings.versions(),
                                                 "permissions": self.app.permissions.summary()})
        r("PATCH", r"/api/settings", self.settings_patch)
        r("POST", r"/api/settings/restore/(\d+)", lambda q, b, i: self.sensitive_change({"__restore_version__": int(i)}, "restauration de configuration"))
        r("GET", r"/api/providers", lambda q, b: self.app.providers.status())
        r("GET", r"/api/secrets", lambda q, b: self.app.secrets.status())
        r("POST", r"/api/secrets", self.secret_set)
        r("DELETE", r"/api/secrets/([a-z_]+)", lambda q, b, n: (self.app.secrets.delete(n), {"deleted": True})[1])
        r("GET", r"/api/connectors", lambda q, b: self.app.connectors.list())
        r("POST", r"/api/connectors/([a-z_]+)/test", lambda q, b, c: self.app.connectors.test(c))
        r("POST", r"/api/connectors/([a-z_]+)/enable", self.connector_enable)
        r("GET", r"/api/voice", lambda q, b: {"voices": self.app.voice.voices(), "devices": self.app.voice.devices(),
                                              "settings": self.app.settings.get("voice"), "speaking": self.app.voice.speaking()})
        r("POST", r"/api/voice/speak", lambda q, b: self.app.voice.speak(b.get("text", "")))
        r("POST", r"/api/voice/stop", lambda q, b: {"stopped": self.app.voice.stop()})
        r("GET", r"/api/diagnostics", lambda q, b: self.app.diagnostics.run())
        r("GET", r"/api/diagnostics/report", lambda q, b: {"markdown": self.app.diagnostics.report()})
        r("GET", r"/api/system", lambda q, b: {**system_info(), "processes": self.app.db.all("SELECT * FROM processes ORDER BY id DESC LIMIT 30"),
                                               "tasks_running": self.app.tasks.running(), "durations": self.app.db.all(
                                                   "SELECT id, title, status, started_at, finished_at FROM tasks WHERE finished_at IS NOT NULL "
                                                   "AND kind!='conversation' ORDER BY id DESC LIMIT 15")})
        r("GET", r"/api/backups", lambda q, b: self.app.backups.list())
        r("POST", r"/api/backups", lambda q, b: self.app.backups.create("manuelle"))
        r("POST", r"/api/backups/verify", lambda q, b: self.app.backups.verify(paths.backups_dir() / os.path.basename(b.get("name", ""))))
        r("POST", r"/api/backups/restore", lambda q, b: self.sensitive_change({"__restore_backup__": os.path.basename(b.get("name", ""))},
                                                                              "restauration d'une sauvegarde"))
        r("GET", r"/api/costs", self.costs)
        r("GET", r"/api/agency", self.agency)
        r("GET", r"/api/sites", self.sites)
        r("GET", r"/api/apps", lambda q, b: list_apps())
        r("GET", r"/api/shell/history", lambda q, b: self.app.db.all("SELECT * FROM shell_history ORDER BY id DESC LIMIT 100"))
        r("GET", r"/api/sources", lambda q, b: self.app.db.all("SELECT * FROM web_sources ORDER BY id DESC LIMIT 200"))
        r("GET", r"/api/plugins", lambda q, b: self.app.plugins)
        r("POST", r"/api/shutdown", self.shutdown)

    def add(self, method: str, pattern: str, fn: Callable) -> None:
        self.routes.append((method, re.compile("^" + pattern + "$"), fn))

    def dispatch(self, method: str, path: str, query: Dict[str, str], body: Dict[str, Any]) -> Any:
        for m, pat, fn in self.routes:
            if m != method:
                continue
            mt = pat.match(path)
            if mt:
                return fn(query, body, *mt.groups())
        raise NotFound("Route inconnue.", {"route": f"{method} {path}"})

    # -- gestionnaires ------------------------------------------------------------------------
    def state(self, q, b):
        app = self.app
        prov = [p for p in app.providers.status() if p["active"]]
        today = time.strftime("%Y-%m-%d")
        return {
            "version": VERSION, "started_at": app.started_at, "core": app.core_state(), "mode": app.permissions.mode(),
            "mode_description": MODES.get(app.permissions.mode()), "provider": prov[0] if prov else None,
            "tasks_open": app.db.one("SELECT count(*) AS n FROM tasks WHERE kind!='conversation' AND status IN "
                                     "('en_attente','en_cours','pause','attente_autorisation','attente_reponse','interrompue')")["n"],
            "notifications_unread": app.db.one("SELECT count(*) AS n FROM notifications WHERE read=0")["n"],
            "ai_calls_today": app.db.one("SELECT count(*) AS n FROM ai_usage WHERE ts LIKE ?", (today + "%",))["n"],
            "connectors": [{"id": c["id"], "label": c["label"], "connected": c["connected"]} for c in app.connectors.list()],
            "settings": {"appearance": app.settings.get("appearance"), "voice": app.settings.get("voice"),
                         "assistant": app.settings.get("assistant"), "shortcuts": app.settings.get("shortcuts")},
        }

    def chat(self, q, b):
        return self.app.send_message(_int(b.get("conversation_id")), b.get("text", ""), _int(b.get("project_id")),
                                     b.get("agent", "general") if b.get("agent") in profiles.PROFILES else "general", b.get("source", "texte"))

    def conv_get(self, q, b, i):
        c = self.app.conversations.get(int(i))
        c["messages"] = self.app.conversations.messages(int(i))
        c["running_task"] = self.app.db.one("SELECT id, status FROM tasks WHERE conversation_id=? AND status IN "
                                            "('en_attente','en_cours','attente_autorisation','pause') ORDER BY id DESC LIMIT 1", (int(i),))
        return c

    def conv_patch(self, q, b, i):
        return self.app.conversations.update(int(i), b.get("title"), b.get("archived"),
                                             b["project_id"] if "project_id" in b else "inchange")

    def search(self, q, b):
        term = q.get("q", "").strip()
        if not term:
            return {"memory": [], "messages": [], "tasks": [], "projects": [], "files": [], "sources": []}
        pid = _int(q.get("project"))
        app = self.app
        like = f"%{term}%"
        files = []
        try:
            ctx = ToolContext(app, mode="assistance")
            files = app.tools.invoke("contenu_rechercher", {"query": term, "max": 30}, ctx)["result"]["hits"]
        except JarvisError:
            pass
        return {
            "memory": app.memory.search(term, project_id=pid, limit=30),
            "messages": app.conversations.search(term, pid, 30),
            "tasks": app.db.all("SELECT id, title, status, project_id FROM tasks WHERE (title LIKE ? OR objective LIKE ? OR result LIKE ?)"
                                + (" AND project_id=?" if pid else "") + " ORDER BY id DESC LIMIT 30",
                                [like, like, like] + ([pid] if pid else [])),
            "projects": app.db.all("SELECT id, name, status FROM projects WHERE name LIKE ? OR description LIKE ? OR notes LIKE ?", (like, like, like)),
            "files": files,
            "sources": app.db.all("SELECT url, title, fetched_at FROM web_sources WHERE title LIKE ? OR excerpt LIKE ? ORDER BY id DESC LIMIT 20", (like, like)),
        }

    def task_create(self, q, b):
        kind = "agent" if b.get("execute") else "todo"
        return self.app.tasks.create(b.get("objective") or b.get("title", ""), b.get("title"), kind, b.get("agent", "general"), None,
                                     _int(b.get("project_id")), int(b.get("priority", 2)), b.get("depends_on") or None, b.get("due_date") or None,
                                     start=kind == "agent")

    def task_action(self, q, b, i, action):
        tm, tid = self.app.tasks, int(i)
        return {"cancel": tm.cancel, "pause": tm.pause, "resume": tm.resume, "complete": tm.complete_todo, "start": tm.start}[action](tid)

    def confirm(self, q, b, i):
        app = self.app
        approve = bool(b.get("approve"))
        conf = app.permissions.decide(int(i), approve)
        app.logbook.log("autorisation_accordee" if approve else "autorisation_refusee",
                        f"Confirmation #{i} {'accordée' if approve else 'refusée'} : {conf['action']}", "succes" if approve else "attention",
                        conf.get("task_id"), tool=conf["tool"])
        if conf["tool"].startswith("__"):
            if approve:
                return {"applied": self._apply_sensitive(conf), "confirmation": conf["id"]}
            return {"applied": False}
        if conf.get("task_id"):
            app.tasks.on_confirmation(conf)
        app.bus.publish({"type": "confirmation", "id": int(i), "status": conf["status"]})
        return {"status": conf["status"], "task_id": conf.get("task_id")}

    def _apply_sensitive(self, conf) -> Any:
        app = self.app
        args = loads(conf["args"], {})
        app.permissions.consume_confirmation(conf["tool"], args, None)
        if "__restore_version__" in args:
            return app.settings.restore_version(args["__restore_version__"])
        if "__restore_backup__" in args:
            return app.backups.restore(args["__restore_backup__"])
        if "__secret__" in args:
            return {"ok": True}
        res = app.settings.update(args, "modification confirmée par Sacha")
        app.logbook.log("parametres", f"Paramètres sensibles modifiés : {', '.join(touches_sensitive(args))}", "attention")
        return {"settings": res}

    def sensitive_change(self, patch: Dict[str, Any], label: str, describe: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        d = {"action": label, "target": "configuration de JARVIS", "consequences": describe or "Élargit ou modifie des droits de JARVIS.",
             "reversible": True, "expected": "nouvelle configuration active"}
        cid = self.app.permissions.request_confirmation("__parametres__", patch, "eleve", d, None)
        self.app.bus.publish({"type": "confirmation", "id": cid})
        raise ConfirmationRequired("Ce changement touche aux droits de JARVIS : confirmation nécessaire.",
                                   {"confirmation_id": cid, **d, "patch": patch})

    def settings_patch(self, q, b):
        sens = touches_sensitive(b)
        if sens:
            # mode : affiche la portée réelle du nouveau mode dans la demande de confirmation
            detail = f"Réglages sensibles : {', '.join(sens)}."
            if b.get("autonomy", {}).get("mode"):
                detail += f" Nouveau mode « {b['autonomy']['mode']} » : {MODES.get(b['autonomy']['mode'], '')}"
            return self.sensitive_change(b, "Modifier des réglages sensibles", detail)
        return {"settings": self.app.settings.update(b, "préférences")}

    def secret_set(self, q, b):
        name, value = b.get("name", ""), b.get("value", "")
        self.app.secrets.set(name, value)
        self.app.logbook.log("secret", f"Secret « {name} » enregistré dans le trousseau (valeur jamais journalisée)", "info")
        return {"saved": True, "name": name}

    def connector_enable(self, q, b, cid):
        if cid not in ("gmail", "google_agenda"):
            raise ValidationError("Ce connecteur ne se (dés)active pas ici.")
        cur = dict(self.app.settings.get("connectors") or {})
        cur[cid] = bool(b.get("enabled"))
        if not b.get("enabled"):
            return {"settings": self.app.settings.update({"connectors": cur}, f"connecteur {cid} désactivé")}
        return self.sensitive_change({"connectors": cur}, f"Activer le connecteur {cid}",
                                     "JARVIS pourra lire ce service et y créer des brouillons/événements (jamais d'envoi ni de suppression).")

    def tool_invoke(self, q, b, tool_id):
        ctx = ToolContext(self.app, None, None, threading.Event(), None, "general")
        return self.app.tools.invoke(tool_id, b.get("args") or {}, ctx)

    def auto_create(self, q, b):
        return self.app.scheduler.create(b.get("name", "Automatisation"), b.get("trigger") or {}, b.get("action") or {},
                                         b.get("conditions"), False, b.get("timezone", "Europe/Paris"),
                                         int(b.get("max_seconds", 300)), int(b.get("max_retries", 1)))

    def auto_action(self, q, b, i, action):
        s = self.app.scheduler
        if action == "run":
            s.run_async(int(i), "manuel")
            return {"started": True}
        return s.set_enabled(int(i), action == "enable")

    def costs(self, q, b):
        db = self.app.db
        today, month = time.strftime("%Y-%m-%d"), time.strftime("%Y-%m")
        agg = "count(*) AS calls, sum(ok) AS ok, coalesce(sum(input_tokens),0) AS input_tokens, coalesce(sum(output_tokens),0) AS output_tokens, sum(cost_usd) AS cost_usd"
        return {
            "by_model": db.all(f"SELECT provider, model, cost_kind, {agg} FROM ai_usage GROUP BY provider, model, cost_kind ORDER BY calls DESC"),
            "today": db.one(f"SELECT {agg} FROM ai_usage WHERE ts LIKE ?", (today + "%",)),
            "month": db.one(f"SELECT {agg} FROM ai_usage WHERE ts LIKE ?", (month + "%",)),
            "month_by_kind": db.all("SELECT cost_kind, count(*) AS calls, sum(cost_usd) AS cost_usd FROM ai_usage WHERE ts LIKE ? GROUP BY cost_kind", (month + "%",)),
            "budget": self.app.settings.get("budget"),
            "automations": db.one("SELECT count(*) AS runs FROM automation_runs WHERE started_at LIKE ?", (month + "%",)),
            "note": "Claude via Claude Code : coût « inclus_abonnement » (le montant indiqué est l'équivalent tarif API calculé par la CLI, "
                    "non facturé à l'appel ; les limites d'usage de l'abonnement s'appliquent). Aucun service payant n'est connecté.",
        }

    def agency(self, q, b):
        from .connectors import cypher_crm
        crm = cypher_crm()
        factures = crm["factures"]
        paid = [f for f in factures if str(f.get("statut", "")).lower() in ("payee", "payée", "paye", "payé")]
        def amount(r):
            for k in ("montant_ttc", "total_ttc", "montant", "total", "montant_ht", "total_ht"):
                try:
                    return float(str(r.get(k, "")).replace(",", ".").replace(" ", ""))
                except ValueError:
                    continue
            return 0.0
        return {**crm, "revenus": {"confirmes": round(sum(amount(f) for f in paid), 2),
                                   "en_attente_de_paiement": round(sum(amount(f) for f in factures if f not in paid), 2),
                                   "devis_ouverts": round(sum(amount(d) for d in crm["devis"] if str(d.get("statut", "")).lower()
                                                              not in ("refuse", "refusé", "accepte", "accepté", "archive", "archivé")), 2),
                                   "note": "Confirmé = facture déclarée payée dans CYPHER. Le reste est une prévision."}}

    def sites(self, q, b):
        root = paths.workspace_dir() / "sites"
        root.mkdir(exist_ok=True)
        out = []
        from .tools.sites import check_site
        for d in sorted(root.iterdir()):
            if d.is_dir() and any(d.glob("*.html")):
                try:
                    rep = check_site(d)
                    out.append({"name": d.name, "dir": str(d), "pages": rep["pages"], "errors": rep["errors"], "warnings": rep["warnings"]})
                except JarvisError as e:
                    out.append({"name": d.name, "dir": str(d), "error": e.message})
        return {"root": str(root), "sites": out}

    def shutdown(self, q, b):
        threading.Thread(target=_shutdown_later, args=(self.app,), daemon=True).start()
        return {"stopping": True}


_SERVER: Optional[ThreadingHTTPServer] = None


def _shutdown_later(app) -> None:
    time.sleep(0.3)
    app.shutdown()
    if _SERVER:
        _SERVER.shutdown()


def _int(v) -> Optional[int]:
    try:
        return int(v) if v not in (None, "", "null") else None
    except (TypeError, ValueError):
        return None


def make_handler(api: Api, port: int):
    allowed_hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}

    class Handler(BaseHTTPRequestHandler):
        server_version = f"JARVIS/{VERSION}"
        protocol_version = "HTTP/1.1"

        def log_message(self, fmt, *args):  # journal HTTP silencieux (le journal d'activité suffit)
            return

        def _send(self, code: int, payload: Any, ctype: str = "application/json; charset=utf-8") -> None:
            body = payload if isinstance(payload, bytes) else json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header("Referrer-Policy", "no-referrer")
            if ctype.startswith("text/html"):
                self.send_header("Content-Security-Policy", "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; "
                                 "connect-src 'self'; script-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'")
            self.end_headers()
            self.wfile.write(body)

        def _guard(self, need_token: bool, query: Dict[str, str]) -> bool:
            if self.headers.get("Host", "") not in allowed_hosts:
                self._send(403, {"error": {"code": "hote_refuse", "message": "Hôte non autorisé."}})
                return False
            origin = self.headers.get("Origin")
            if origin and urllib.parse.urlparse(origin).netloc not in allowed_hosts:
                self._send(403, {"error": {"code": "origine_refusee", "message": "Origine non autorisée."}})
                return False
            if need_token:
                tok = self.headers.get("X-Jarvis-Token") or query.get("token", "")
                if not secrets.compare_digest(tok, api.token):
                    self._send(401, {"error": {"code": "non_authentifie", "message": "Jeton manquant ou invalide."}})
                    return False
            return True

        def _parse(self):
            u = urllib.parse.urlparse(self.path)
            q = {k: v[0] for k, v in urllib.parse.parse_qs(u.query).items()}
            return u.path, q

        def do_GET(self):
            path, q = self._parse()
            if path == "/api/health":
                if self._guard(False, q):
                    self._send(200, {"ok": True, "version": VERSION})
                return
            if path == "/api/stream":
                if self._guard(True, q):
                    self._stream()
                return
            if path.startswith("/api/"):
                return self._api("GET", path, q)
            if not self._guard(False, q):
                return
            self._static(path)

        def do_POST(self):
            self._api("POST", *self._parse())

        def do_PATCH(self):
            self._api("PATCH", *self._parse())

        def do_DELETE(self):
            self._api("DELETE", *self._parse())

        def _api(self, method, path, q):
            if not self._guard(True, q):
                return
            body: Dict[str, Any] = {}
            n = int(self.headers.get("Content-Length") or 0)
            if n > 5_000_000:
                return self._send(413, {"error": {"code": "trop_gros", "message": "Requête trop volumineuse."}})
            if n:
                try:
                    body = json.loads(self.rfile.read(n).decode("utf-8") or "{}")
                except ValueError:
                    return self._send(400, {"error": {"code": "json_invalide", "message": "Corps JSON invalide."}})
            try:
                res = api.dispatch(method, path, q, body if isinstance(body, dict) else {"_": body})
                self._send(200, {"ok": True, "data": res})
            except JarvisError as e:
                self._send(e.http_status, {"ok": False, "error": e.to_dict()})
            except Exception as e:  # noqa: BLE001
                api.app.logbook.log("api_erreur", f"{method} {path} : {e}", "erreur", data={"trace": traceback.format_exc()[-1200:]})
                self._send(500, {"ok": False, "error": {"code": "erreur_interne", "message": str(e)}})

        def _static(self, path):
            if path in ("", "/"):
                path = "/index.html"
            target = (paths.WEB_DIR / path.lstrip("/")).resolve()
            if not str(target).startswith(str(paths.WEB_DIR.resolve())) or not target.is_file():
                return self._send(404, {"error": {"code": "introuvable", "message": "Fichier introuvable."}})
            data = target.read_bytes()
            if target.name == "index.html":
                data = data.replace(b"__JARVIS_TOKEN__", api.token.encode())
            ctype = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
            if ctype.startswith("text/") or ctype in ("application/javascript",):
                ctype += "; charset=utf-8"
            self._send(200, data, ctype)

        def _stream(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Connection", "keep-alive")
            self.end_headers()
            q = api.app.bus.subscribe()
            try:
                self.wfile.write(b"retry: 2000\n\n")
                self.wfile.flush()
                while True:
                    try:
                        ev = q.get(timeout=15)
                        data = json.dumps(ev, ensure_ascii=False, default=str)
                        self.wfile.write(f"data: {data}\n\n".encode("utf-8"))
                    except queue.Empty:
                        self.wfile.write(b": ping\n\n")
                    self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError, OSError):
                pass
            finally:
                api.app.bus.unsubscribe(q)

    return Handler


class _Server(ThreadingHTTPServer):
    daemon_threads = True

    def handle_error(self, request, client_address):
        import sys
        exc = sys.exc_info()[1]
        if isinstance(exc, (ConnectionResetError, BrokenPipeError, TimeoutError)):
            return  # fenêtre fermée ou rechargée : rien d'anormal
        super().handle_error(request, client_address)


def serve(app, port: int, token: str) -> ThreadingHTTPServer:
    global _SERVER
    api = Api(app, token)
    srv = _Server(("127.0.0.1", port), make_handler(api, port))
    srv.daemon_threads = True
    _SERVER = srv
    return srv
