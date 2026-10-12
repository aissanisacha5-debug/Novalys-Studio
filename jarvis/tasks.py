"""Centre de tâches : création, exécution, dépendances, pause, reprise, annulation, confirmations.

Statuts : en_attente · en_cours · pause · attente_autorisation · attente_reponse ·
terminee · echouee · bloquee · annulee · interrompue (redémarrage pendant l'exécution).
Une tâche annulée s'arrête réellement : l'événement d'annulation coupe l'appel au
modèle et les commandes en cours (groupe de processus tué).
"""
from __future__ import annotations

import os
import threading
import traceback
from typing import Any, Dict, List, Optional

from .db import dumps, loads, now
from .errors import Cancelled, ConfirmationRequired, JarvisError, NotFound, ValidationError

ACTIVE = ("en_cours",)
OPEN = ("en_attente", "en_cours", "pause", "attente_autorisation", "attente_reponse", "interrompue")
WRITE_TOOLS = {"fichier_ecrire": ("path",), "dossier_creer": ("path",), "fichier_deplacer": ("src", "dst"),
               "fichier_copier": ("dst",), "fichier_supprimer": ("path",), "archive_creer": ("dest",),
               "document_creer": ("path",), "site_creer": ("dir",)}


class TaskManager:
    def __init__(self, app):
        self.app = app
        self._threads: Dict[int, threading.Thread] = {}
        self._cancel: Dict[int, threading.Event] = {}
        self._pause: Dict[int, threading.Event] = {}
        self._locks: Dict[str, int] = {}
        self._mu = threading.RLock()

    # -- création / consultation ---------------------------------------------------
    def create(self, objective: str, title: Optional[str] = None, kind: str = "agent", agent: str = "general",
               conversation_id: Optional[int] = None, project_id: Optional[int] = None, priority: int = 2,
               depends_on: Optional[List[int]] = None, due_date: Optional[str] = None, start: bool = True,
               parent_id: Optional[int] = None) -> Dict[str, Any]:
        if not objective or not objective.strip():
            raise ValidationError("Objectif vide.")
        if kind not in ("agent", "conversation", "todo", "automatisation"):
            raise ValidationError("Type de tâche inconnu.")
        for d in depends_on or []:
            if not self.app.db.one("SELECT id FROM tasks WHERE id=?", (d,)):
                raise ValidationError(f"Dépendance inconnue : tâche {d}.")
        s = self.app.settings
        ts = now()
        tid = self.app.db.insert(
            "INSERT INTO tasks(title, objective, kind, agent, conversation_id, project_id, parent_id, depends_on, priority, status, "
            "due_date, max_steps, max_seconds, max_retries, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            ((title or objective)[:140], objective, kind, agent, conversation_id, project_id, parent_id, dumps(depends_on or []),
             int(priority), "en_attente", due_date, s.get("autonomy.max_steps", 12), s.get("autonomy.max_task_seconds", 900),
             s.get("autonomy.max_retries", 2), ts, ts))
        self.app.logbook.log("tache_creee", f"Tâche #{tid} créée : {(title or objective)[:100]}", "info", tid, conversation_id)
        self._publish(tid)
        if start and kind != "todo":
            self.start(tid)
        return self.get(tid)

    def get(self, tid: int) -> Dict[str, Any]:
        r = self.app.db.one("SELECT t.*, p.name AS project_name FROM tasks t LEFT JOIN projects p ON p.id=t.project_id WHERE t.id=?", (tid,))
        if not r:
            raise NotFound("Tâche introuvable.", {"id": tid})
        r["depends_on"] = loads(r["depends_on"], [])
        return r

    def list(self, status: str = "", project_id: Optional[int] = None, include_chat: bool = False, limit: int = 200) -> List[Dict[str, Any]]:
        sql = "SELECT t.*, p.name AS project_name FROM tasks t LEFT JOIN projects p ON p.id=t.project_id WHERE 1=1"
        params: List[Any] = []
        if not include_chat:
            sql += " AND t.kind != 'conversation'"
        if status == "ouvertes":
            sql += f" AND t.status IN ({','.join('?' * len(OPEN))})"
            params += list(OPEN)
        elif status:
            sql += " AND t.status=?"
            params.append(status)
        if project_id is not None:
            sql += " AND t.project_id=?"
            params.append(project_id)
        rows = self.app.db.all(sql + " ORDER BY CASE WHEN t.status='en_cours' THEN 0 ELSE 1 END, t.priority DESC, t.id DESC LIMIT ?", params + [limit])
        for r in rows:
            r["depends_on"] = loads(r["depends_on"], [])
        return rows

    def detail(self, tid: int) -> Dict[str, Any]:
        t = self.get(tid)
        steps = self.app.db.all("SELECT * FROM task_steps WHERE task_id=? ORDER BY idx", (tid,))
        for s in steps:
            s["args"] = loads(s["args"], None)
            s["result"] = loads(s["result"], None)
        t["steps"] = steps
        t["events"] = self.app.logbook.search(task_id=tid, limit=200)
        t["confirmations"] = self.app.db.all("SELECT id, tool, action, target, consequences, data_concerned, reversible, expected, status, risk, created_at "
                                              "FROM confirmations WHERE task_id=? ORDER BY id", (tid,))
        t["sources"] = self.app.db.all("SELECT * FROM web_sources WHERE task_id=? ORDER BY id", (tid,))
        t["usage"] = self.app.db.one("SELECT count(*) AS calls, sum(input_tokens) AS input_tokens, sum(output_tokens) AS output_tokens, "
                                     "sum(cost_usd) AS cost_usd FROM ai_usage WHERE task_id=?", (tid,))
        return t

    # -- exécution -------------------------------------------------------------------
    def _deps_ok(self, t: Dict[str, Any]) -> Optional[str]:
        for d in t["depends_on"]:
            dt = self.app.db.one("SELECT status FROM tasks WHERE id=?", (d,))
            if not dt:
                continue
            if dt["status"] in ("echouee", "annulee", "bloquee"):
                return "bloquee"
            if dt["status"] != "terminee":
                return "attente"
        return None

    def start(self, tid: int, resume_action: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        t = self.get(tid)
        if t["kind"] == "todo":
            raise ValidationError("Une tâche manuelle ne s'exécute pas : marque-la terminée quand c'est fait.")
        with self._mu:
            if tid in self._threads and self._threads[tid].is_alive():
                return t
            dep = self._deps_ok(t)
            if dep == "bloquee":
                return self.finish(tid, "bloquee", "Une tâche dont celle-ci dépend a échoué ou a été annulée.", "bloque",
                                   error="dépendance en échec")
            if dep == "attente":
                self.set_status(tid, "en_attente")
                return self.get(tid)
            ce, pe = threading.Event(), threading.Event()
            self._cancel[tid], self._pause[tid] = ce, pe
            if resume_action:
                t["_resume_confirmation"] = resume_action
            th = threading.Thread(target=self._run, args=(t, ce, pe), daemon=True, name=f"tache-{tid}")
            self._threads[tid] = th
            self.app.db.execute("UPDATE tasks SET started_at=coalesce(started_at, ?) WHERE id=?", (now(), tid))
            th.start()
        return self.get(tid)

    def _run(self, t: Dict[str, Any], ce: threading.Event, pe: threading.Event) -> None:
        from .agent.engine import AgentRunner
        tid = t["id"]
        self.app.logbook.log("tache_debut", f"Tâche #{tid} démarrée", "info", tid, t.get("conversation_id"))
        try:
            AgentRunner(self.app, t, ce, pe).run()
        except Cancelled:
            self.finish(tid, "annulee", "Tâche annulée. Les résultats déjà obtenus sont conservés.", "bloque")
        except ConfirmationRequired:
            pass  # statut déjà « attente_autorisation »
        except Exception as e:  # noqa: BLE001
            self.app.logbook.log("tache_erreur", f"Erreur interne : {e}", "erreur", tid, data={"trace": traceback.format_exc()[-1500:]})
            self.finish(tid, "echouee", f"Erreur interne de JARVIS : {e}", "echoue", error=str(e))
        finally:
            with self._mu:
                self._threads.pop(tid, None)
            self.app.bus.publish({"type": "activity", "state": "calme", "task_id": tid})

    def running(self) -> List[int]:
        with self._mu:
            return [tid for tid, th in self._threads.items() if th.is_alive()]

    def set_status(self, tid: int, status: str) -> None:
        self.app.db.execute("UPDATE tasks SET status=?, updated_at=? WHERE id=?", (status, now(), tid))
        self._publish(tid)

    def finish(self, tid: int, status: str, message: str, result_state: str, error: Optional[str] = None,
               next_action: Optional[str] = None) -> Dict[str, Any]:
        app = self.app
        if next_action is None and status in ("bloquee", "echouee", "interrompue", "annulee"):
            next_action = {"bloquee": "Lire le blocage, puis reprendre la tâche ou la reformuler.",
                           "echouee": "Consulter l'erreur (Diagnostic) puis relancer.",
                           "annulee": None}.get(status)
        app.db.execute("UPDATE tasks SET status=?, result=?, result_state=?, error=?, next_action=?, finished_at=?, updated_at=? WHERE id=?",
                       (status, message, result_state, error, next_action, now(), now(), tid))
        self.release_locks(tid)
        t = self.get(tid)
        level = {"terminee": "succes", "echouee": "erreur", "bloquee": "attention", "annulee": "info"}.get(status, "info")
        app.logbook.log("tache_fin", f"Tâche #{tid} : {status} ({result_state})", level, tid, t.get("conversation_id"),
                        data={"error": error} if error else None)
        if t.get("conversation_id") and t["kind"] in ("conversation", "agent"):
            tools_used = app.db.one("SELECT count(*) AS n FROM task_steps WHERE task_id=? AND kind='outil' AND status='termine'", (tid,))["n"]
            app.conversations.add_message(t["conversation_id"], "assistant", message,
                                          {"task_id": tid, "status": status, "result_state": result_state, "tools_used": tools_used,
                                           "next_action": next_action})
            app.bus.publish({"type": "message", "conversation_id": t["conversation_id"], "task_id": tid})
            if app.settings.get("voice.auto_speak") and status in ("terminee", "attente_reponse", "bloquee", "echouee"):
                try:
                    app.voice.speak(message)
                except JarvisError:
                    pass
        if t["kind"] != "conversation":
            if status == "terminee":
                app.notify("tache_terminee", "Tâche terminée", t["title"])
            elif status in ("echouee", "bloquee"):
                app.notify("erreur" if status == "echouee" else "projet_bloque", f"Tâche {status}", t["title"])
        self._publish(tid)
        app.bus.publish({"type": "activity", "state": "erreur" if status == "echouee" else "termine", "task_id": tid})
        self.start_ready_dependents()
        return t

    def start_ready_dependents(self) -> None:
        for t in self.app.db.all("SELECT id FROM tasks WHERE status='en_attente' AND kind!='todo' AND depends_on != '[]'"):
            if t["id"] not in self.running():
                try:
                    self.start(t["id"])
                except JarvisError:
                    pass

    # -- contrôle ------------------------------------------------------------------------
    def cancel(self, tid: int) -> Dict[str, Any]:
        t = self.get(tid)
        if t["status"] in ("terminee", "annulee", "echouee"):
            raise ValidationError(f"Tâche déjà {t['status']}.")
        ev = self._cancel.get(tid)
        self.app.db.execute("UPDATE confirmations SET status='expiree' WHERE task_id=? AND status='en_attente'", (tid,))
        if ev and tid in self.running():
            ev.set()
            self.app.logbook.log("tache_annulation", f"Annulation demandée pour #{tid}", "attention", tid)
            return self.get(tid)
        return self.finish(tid, "annulee", "Tâche annulée.", "bloque")

    def pause(self, tid: int) -> Dict[str, Any]:
        if tid not in self.running():
            raise ValidationError("La tâche n'est pas en cours d'exécution.")
        self._pause[tid].set()
        return self.get(tid)

    def resume(self, tid: int) -> Dict[str, Any]:
        t = self.get(tid)
        if t["status"] not in ("pause", "interrompue", "bloquee", "echouee", "attente_reponse"):
            raise ValidationError(f"Impossible de reprendre une tâche « {t['status']} ».")
        self.app.db.execute("UPDATE tasks SET max_seconds=max_seconds+?, max_steps=max_steps+? WHERE id=?",
                            (self.app.settings.get("autonomy.max_task_seconds", 900), 6, tid))
        self.app.logbook.log("tache_reprise", f"Reprise de la tâche #{tid}", "info", tid)
        return self.start(tid)

    def complete_todo(self, tid: int) -> Dict[str, Any]:
        t = self.get(tid)
        if t["kind"] != "todo":
            raise ValidationError("Seules les tâches manuelles se marquent terminées à la main.")
        return self.finish(tid, "terminee", "Marquée terminée par Sacha.", "confirme")

    # -- confirmations --------------------------------------------------------------------
    def wait_confirmation(self, tid: int, cid: Optional[int], action: Dict[str, Any]) -> None:
        self.set_status(tid, "attente_autorisation")
        self.app.bus.publish({"type": "activity", "state": "autorisation", "task_id": tid, "confirmation_id": cid})

    def on_confirmation(self, conf: Dict[str, Any]) -> None:
        tid = conf.get("task_id")
        if not tid:
            return
        t = self.get(tid)
        if t["status"] != "attente_autorisation":
            return
        if conf["status"] == "acceptee":
            self.app.logbook.log("autorisation_accordee", f"Confirmation #{conf['id']} accordée", "succes", tid, tool=conf["tool"])
            self.start(tid, resume_action={"tool": conf["tool"], "args": loads(conf["args"], {})})
        else:
            self.app.logbook.log("autorisation_refusee", f"Confirmation #{conf['id']} refusée", "attention", tid, tool=conf["tool"])
            self.app.db.insert("INSERT INTO task_steps(task_id, idx, kind, tool, args, status, error, started_at, finished_at) "
                               "VALUES (?, (SELECT coalesce(max(idx),0)+1 FROM task_steps WHERE task_id=?), 'outil', ?, ?, 'refuse', ?, ?, ?)",
                               (tid, tid, conf["tool"], conf["args"], "Action refusée par Sacha : ne pas la refaire.", now(), now()))
            self.start(tid)

    # -- verrous de fichiers (conflits entre tâches) ---------------------------------------
    def lock_paths(self, tid: int, tool: str, args: Dict[str, Any]) -> None:
        keys = WRITE_TOOLS.get(tool)
        if not keys:
            return
        with self._mu:
            for k in keys:
                raw = args.get(k)
                if not isinstance(raw, str):
                    continue
                p = os.path.realpath(os.path.expanduser(raw))
                owner = self._locks.get(p)
                if owner and owner != tid and owner in self.running():
                    raise JarvisError(f"Conflit : la tâche #{owner} modifie déjà {p}.", {"chemin": p, "tache": owner}, code="conflit")
                self._locks[p] = tid

    def release_locks(self, tid: int) -> None:
        with self._mu:
            for p in [p for p, o in self._locks.items() if o == tid]:
                del self._locks[p]

    # -- reprise après redémarrage -----------------------------------------------------
    def recover(self) -> int:
        rows = self.app.db.all("SELECT id FROM tasks WHERE status='en_cours'")
        for r in rows:
            self.app.db.execute("UPDATE tasks SET status='interrompue', updated_at=? WHERE id=?", (now(), r["id"]))
            self.app.db.execute("UPDATE tasks SET next_action='Reprendre la tâche (les étapes déjà faites ne sont pas refaites).' WHERE id=?", (r["id"],))
            self.app.logbook.log("tache_interrompue", f"Tâche #{r['id']} interrompue par un redémarrage : reprise possible.",
                                 "attention", r["id"])
        return len(rows)

    def _publish(self, tid: int) -> None:
        self.app.bus.publish({"type": "task", "task_id": tid})
