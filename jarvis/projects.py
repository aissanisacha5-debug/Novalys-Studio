"""Gestion des projets (partie 14), rappels et notifications persistées."""
from __future__ import annotations

import datetime as dt
from typing import Any, Dict, List, Optional

from .db import Database, now
from .errors import NotFound, ValidationError

PROJECT_STATUSES = ("idee", "actif", "en_pause", "bloque", "termine", "archive")


class Projects:
    FIELDS = ("name", "description", "objectives", "folder", "status", "priority", "due_date", "notes", "results",
              "next_steps", "success_criteria")

    def __init__(self, db: Database):
        self.db = db

    def create(self, name: str, **f) -> Dict[str, Any]:
        if not name or not name.strip():
            raise ValidationError("Nom de projet obligatoire.")
        if self.db.one("SELECT id FROM projects WHERE lower(name)=lower(?) AND status!='archive'", (name.strip(),)):
            raise ValidationError("Un projet porte déjà ce nom.", {"nom": name})
        ts = now()
        pid = self.db.insert(
            "INSERT INTO projects(name, description, objectives, folder, status, priority, due_date, success_criteria, created_at, updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            (name.strip()[:120], f.get("description", ""), f.get("objectives", ""), f.get("folder"),
             f.get("status", "actif"), int(f.get("priority", 2)), f.get("due_date"), f.get("success_criteria", ""), ts, ts))
        return self.get(pid)

    def get(self, pid: int) -> Dict[str, Any]:
        r = self.db.one("SELECT * FROM projects WHERE id=?", (pid,))
        if not r:
            raise NotFound("Projet introuvable.", {"id": pid})
        return r

    def find(self, name_or_id: Any) -> Dict[str, Any]:
        if isinstance(name_or_id, int) or str(name_or_id).isdigit():
            return self.get(int(name_or_id))
        r = self.db.one("SELECT * FROM projects WHERE lower(name)=lower(?)", (str(name_or_id),)) or \
            self.db.one("SELECT * FROM projects WHERE name LIKE ? ORDER BY updated_at DESC", (f"%{name_or_id}%",))
        if not r:
            raise NotFound("Projet introuvable.", {"nom": name_or_id})
        return r

    def list(self, include_archived: bool = False) -> List[Dict[str, Any]]:
        sql = ("SELECT p.*, (SELECT count(*) FROM tasks t WHERE t.project_id=p.id) AS tasks_total, "
               "(SELECT count(*) FROM tasks t WHERE t.project_id=p.id AND t.status='terminee') AS tasks_done, "
               "(SELECT count(*) FROM tasks t WHERE t.project_id=p.id AND t.status IN ('bloquee','echouee','attente_autorisation')) AS tasks_blocked "
               "FROM projects p")
        if not include_archived:
            sql += " WHERE p.status!='archive'"
        return self.db.all(sql + " ORDER BY p.priority DESC, p.updated_at DESC")

    def update(self, pid: int, **f) -> Dict[str, Any]:
        cur = self.get(pid)
        if f.get("status") and f["status"] not in PROJECT_STATUSES:
            raise ValidationError("Statut inconnu.", {"statuts": PROJECT_STATUSES})
        if f.get("status") == "termine" and cur.get("success_criteria"):
            open_tasks = self.db.one("SELECT count(*) AS n FROM tasks WHERE project_id=? AND status NOT IN ('terminee','annulee')", (pid,))["n"]
            if open_tasks and not f.get("force"):
                raise ValidationError(f"Impossible de terminer : {open_tasks} tâche(s) encore ouverte(s) et des critères de réussite définis.",
                                      {"taches_ouvertes": open_tasks})
        sets, params = [], []
        for k in self.FIELDS:
            if k in f and f[k] is not None:
                sets.append(f"{k}=?")
                params.append(f[k])
        if sets:
            sets.append("updated_at=?")
            self.db.execute(f"UPDATE projects SET {', '.join(sets)} WHERE id=?", params + [now(), pid])
        return self.get(pid)

    def add_decision(self, pid: int, decision: str, reason: str = "") -> Dict[str, Any]:
        self.get(pid)
        did = self.db.insert("INSERT INTO project_decisions(project_id, decision, reason, created_at) VALUES (?,?,?,?)",
                             (pid, decision, reason, now()))
        return self.db.one("SELECT * FROM project_decisions WHERE id=?", (did,))

    def detail(self, pid: int) -> Dict[str, Any]:
        p = self.get(pid)
        p["tasks"] = self.db.all("SELECT id, title, status, priority, due_date, depends_on, result_state FROM tasks WHERE project_id=? ORDER BY id DESC", (pid,))
        p["decisions"] = self.db.all("SELECT * FROM project_decisions WHERE project_id=? ORDER BY id DESC", (pid,))
        p["memories"] = self.db.all("SELECT id, type, nature, content, updated_at FROM memories WHERE project_id=? AND status!='obsolete' ORDER BY id DESC LIMIT 50", (pid,))
        p["conversations"] = self.db.all("SELECT id, title, updated_at FROM conversations WHERE project_id=? ORDER BY updated_at DESC", (pid,))
        p["history"] = self.db.all("SELECT e.ts, e.message, e.level FROM events e JOIN tasks t ON t.id=e.task_id WHERE t.project_id=? ORDER BY e.id DESC LIMIT 40", (pid,))
        return p

    def report(self, pid: int) -> str:
        p = self.detail(pid)
        done = [t for t in p["tasks"] if t["status"] == "terminee"]
        blocked = [t for t in p["tasks"] if t["status"] in ("bloquee", "echouee", "attente_autorisation")]
        openx = [t for t in p["tasks"] if t["status"] not in ("terminee", "annulee")]
        lines = [f"# Compte rendu — {p['name']}", "", f"Statut : {p['status']} · priorité {p['priority']} · échéance {p['due_date'] or 'aucune'}",
                 "", "## Objectifs", p["objectives"] or "_non renseignés_", "",
                 f"## Avancement : {len(done)}/{len(p['tasks'])} tâches terminées", ""]
        for t in done[:20]:
            lines.append(f"- [x] {t['title']}")
        lines += ["", "## Ouvert"] + [f"- [ ] {t['title']} ({t['status']})" for t in openx[:30]]
        if blocked:
            lines += ["", "## Bloqué"] + [f"- {t['title']} : {t['status']}" for t in blocked]
        lines += ["", "## Décisions"] + [f"- {d['created_at'][:10]} {d['decision']}" for d in p["decisions"][:20]]
        lines += ["", "## Prochaines étapes", p["next_steps"] or "_à définir_", ""]
        return "\n".join(lines)


class Reminders:
    def __init__(self, db: Database):
        self.db = db

    def add(self, title: str, due_at: str, project_id: Optional[int] = None) -> Dict[str, Any]:
        try:
            dt.datetime.fromisoformat(due_at.replace("Z", ""))
        except ValueError:
            raise ValidationError("Date invalide (format AAAA-MM-JJTHH:MM).")
        rid = self.db.insert("INSERT INTO reminders(title, due_at, project_id, created_at) VALUES (?,?,?,?)",
                             (title, due_at, project_id, now()))
        return self.db.one("SELECT * FROM reminders WHERE id=?", (rid,))

    def list(self, include_done: bool = False) -> List[Dict[str, Any]]:
        return self.db.all("SELECT * FROM reminders" + ("" if include_done else " WHERE done=0") + " ORDER BY due_at")

    def complete(self, rid: int) -> None:
        if not self.db.one("SELECT id FROM reminders WHERE id=?", (rid,)):
            raise NotFound("Rappel introuvable.")
        self.db.execute("UPDATE reminders SET done=1 WHERE id=?", (rid,))

    def due(self) -> List[Dict[str, Any]]:
        n = dt.datetime.now().strftime("%Y-%m-%dT%H:%M")
        return self.db.all("SELECT * FROM reminders WHERE done=0 AND notified=0 AND due_at<=?", (n,))
