"""Conversations : historique, recherche, renommage, archivage, export, suppression."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from .db import Database, dumps, loads, now
from .errors import NotFound, ValidationError
from .memory import fts_query


class Conversations:
    def __init__(self, db: Database):
        self.db = db

    def create(self, title: str = "Nouvelle conversation", project_id: Optional[int] = None) -> Dict[str, Any]:
        ts = now()
        cid = self.db.insert("INSERT INTO conversations(title, project_id, created_at, updated_at) VALUES (?,?,?,?)",
                             (title[:120] or "Nouvelle conversation", project_id, ts, ts))
        return self.get(cid)

    def get(self, cid: int) -> Dict[str, Any]:
        r = self.db.one("SELECT c.*, p.name AS project_name FROM conversations c LEFT JOIN projects p ON p.id=c.project_id WHERE c.id=?", (cid,))
        if not r:
            raise NotFound("Conversation introuvable.", {"id": cid})
        return r

    def list(self, archived: bool = False, project_id: Optional[int] = None, q: str = "") -> List[Dict[str, Any]]:
        sql = ("SELECT c.*, p.name AS project_name, (SELECT count(*) FROM messages m WHERE m.conversation_id=c.id) AS n "
               "FROM conversations c LEFT JOIN projects p ON p.id=c.project_id WHERE c.archived=?")
        params: List[Any] = [1 if archived else 0]
        if project_id is not None:
            sql += " AND c.project_id=?"
            params.append(project_id)
        if q:
            sql += " AND c.title LIKE ?"
            params.append(f"%{q}%")
        return self.db.all(sql + " ORDER BY c.updated_at DESC LIMIT 300", params)

    def update(self, cid: int, title: Optional[str] = None, archived: Optional[bool] = None,
               project_id: Any = "inchange") -> Dict[str, Any]:
        self.get(cid)
        if title is not None:
            if not title.strip():
                raise ValidationError("Titre vide.")
            self.db.execute("UPDATE conversations SET title=? WHERE id=?", (title.strip()[:120], cid))
        if archived is not None:
            self.db.execute("UPDATE conversations SET archived=? WHERE id=?", (1 if archived else 0, cid))
        if project_id != "inchange":
            self.db.execute("UPDATE conversations SET project_id=? WHERE id=?", (project_id, cid))
        return self.get(cid)

    def delete(self, cid: int) -> Dict[str, int]:
        """Supprime la conversation et ses informations TEMPORAIRES ; la mémoire personnelle durable est conservée."""
        self.get(cid)
        tmp = self.db.execute("DELETE FROM memories WHERE conversation_id=? AND type='temporaire'", (cid,)).rowcount
        kept = self.db.execute("UPDATE memories SET conversation_id=NULL WHERE conversation_id=?", (cid,)).rowcount
        self.db.execute("DELETE FROM conversations WHERE id=?", (cid,))
        return {"temporary_memories_deleted": tmp, "memories_kept": kept}

    def add_message(self, cid: int, role: str, content: str, meta: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        ts = now()
        mid = self.db.insert("INSERT INTO messages(conversation_id, role, content, meta, created_at) VALUES (?,?,?,?,?)",
                             (cid, role, content, dumps(meta) if meta else None, ts))
        self.db.execute("UPDATE conversations SET updated_at=? WHERE id=?", (ts, cid))
        return {"id": mid, "conversation_id": cid, "role": role, "content": content, "meta": meta, "created_at": ts}

    def messages(self, cid: int, limit: int = 500) -> List[Dict[str, Any]]:
        rows = self.db.all("SELECT * FROM (SELECT * FROM messages WHERE conversation_id=? ORDER BY id DESC LIMIT ?) ORDER BY id",
                           (cid, limit))
        for r in rows:
            r["meta"] = loads(r["meta"], None)
        return rows

    def search(self, q: str, project_id: Optional[int] = None, limit: int = 50) -> List[Dict[str, Any]]:
        fq = fts_query(q)
        if not fq:
            return []
        sql = ("SELECT m.id, m.conversation_id, m.role, snippet(messages_fts, 0, '«', '»', '…', 14) AS snippet, m.created_at, "
               "c.title, c.project_id FROM messages_fts JOIN messages m ON m.id=messages_fts.rowid "
               "JOIN conversations c ON c.id=m.conversation_id WHERE messages_fts MATCH ?")
        params: List[Any] = [fq]
        if project_id is not None:
            sql += " AND c.project_id=?"
            params.append(project_id)
        return self.db.all(sql + " ORDER BY bm25(messages_fts) LIMIT ?", params + [limit])

    def set_summary(self, cid: int, summary: str) -> None:
        self.db.execute("UPDATE conversations SET summary=? WHERE id=?", (summary[:4000], cid))

    def export_markdown(self, cid: int) -> str:
        c = self.get(cid)
        lines = [f"# {c['title']}", "", f"Créée le {c['created_at']}", ""]
        names = {"user": "Sacha", "assistant": "JARVIS", "tool": "Outil", "system": "Système"}
        for m in self.messages(cid, 5000):
            lines += [f"### {names.get(m['role'], m['role'])} · {m['created_at']}", "", m["content"], ""]
        return "\n".join(lines)
