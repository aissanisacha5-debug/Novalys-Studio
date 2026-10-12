"""Journal d'activité + bus d'événements temps réel.

Chaque événement important est enregistré (table events) après
expurgation des secrets, puis diffusé aux interfaces connectées (SSE).
L'état du noyau visuel est calculé à partir de ces événements réels.
"""
from __future__ import annotations

import json
import queue
import re
import threading
import time
from typing import Any, Dict, List, Optional

from .db import Database, dumps, loads, now

_SECRET_PATTERNS = [
    (re.compile(r"sk-ant-[A-Za-z0-9_\-]{10,}"), "sk-ant-***"),
    (re.compile(r"\bsk-[A-Za-z0-9_\-]{16,}"), "sk-***"),
    (re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}"), "gh_***"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "AKIA***"),
    (re.compile(r"\bxox[abprs]-[A-Za-z0-9\-]{10,}"), "xox-***"),
    (re.compile(r"(?i)(bearer\s+)[A-Za-z0-9\._\-]{12,}"), r"\1***"),
    (re.compile(r"(?i)\b(password|passwd|mot[ _]de[ _]passe|secret|api[_-]?key|token|apikey)\b(\s*[:=]\s*)(\S+)"), r"\1\2***"),
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----"), "[clé privée expurgée]"),
    (re.compile(r"\b(?:\d{4}[ \-]){3}\d{1,7}\b"), "[numéro expurgé]"),
    (re.compile(r"\b\d{13,19}\b"), "[numéro expurgé]"),
]


def redact(text: Any) -> Any:
    """Expurge les secrets reconnaissables d'une chaîne (ou d'une structure)."""
    if isinstance(text, str):
        out = text
        for pat, rep in _SECRET_PATTERNS:
            out = pat.sub(rep, out)
        return out
    if isinstance(text, dict):
        return {k: ("***" if re.search(r"(?i)(password|secret|token|api_?key|cookie)", str(k)) else redact(v)) for k, v in text.items()}
    if isinstance(text, list):
        return [redact(v) for v in text]
    return text


class EventBus:
    def __init__(self) -> None:
        self._subs: List[queue.Queue] = []
        self._lock = threading.Lock()

    def subscribe(self) -> queue.Queue:
        q: queue.Queue = queue.Queue(maxsize=500)
        with self._lock:
            self._subs.append(q)
        return q

    def unsubscribe(self, q: queue.Queue) -> None:
        with self._lock:
            if q in self._subs:
                self._subs.remove(q)

    def publish(self, event: Dict[str, Any]) -> None:
        with self._lock:
            subs = list(self._subs)
        for q in subs:
            try:
                q.put_nowait(event)
            except queue.Full:
                pass

    def subscriber_count(self) -> int:
        with self._lock:
            return len(self._subs)


class Logbook:
    LEVELS = ("debug", "info", "succes", "attention", "erreur")

    def __init__(self, db: Database, bus: EventBus):
        self.db = db
        self.bus = bus

    def log(
        self,
        kind: str,
        message: str,
        level: str = "info",
        task_id: Optional[int] = None,
        conversation_id: Optional[int] = None,
        tool: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        message = redact(message)[:2000]
        data = redact(data) if data else None
        ts = now()
        eid = self.db.insert(
            "INSERT INTO events(ts, kind, level, task_id, conversation_id, tool, message, data) VALUES (?,?,?,?,?,?,?,?)",
            (ts, kind, level, task_id, conversation_id, tool, message, dumps(data) if data else None),
        )
        ev = {"id": eid, "ts": ts, "kind": kind, "level": level, "task_id": task_id,
              "conversation_id": conversation_id, "tool": tool, "message": message, "data": data}
        self.bus.publish({"type": "event", "event": ev})
        return ev

    def search(self, q: str = "", kind: str = "", level: str = "", task_id: Optional[int] = None,
               limit: int = 200, offset: int = 0) -> List[Dict[str, Any]]:
        sql = "SELECT * FROM events WHERE 1=1"
        params: List[Any] = []
        if q:
            sql += " AND (message LIKE ? OR tool LIKE ?)"
            params += [f"%{q}%", f"%{q}%"]
        if kind:
            sql += " AND kind = ?"
            params.append(kind)
        if level:
            sql += " AND level = ?"
            params.append(level)
        if task_id is not None:
            sql += " AND task_id = ?"
            params.append(task_id)
        sql += " ORDER BY id DESC LIMIT ? OFFSET ?"
        params += [min(limit, 1000), offset]
        rows = self.db.all(sql, params)
        for r in rows:
            r["data"] = loads(r.get("data"), None)
        return rows

    def purge_older_than(self, days: int) -> int:
        cutoff = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(time.time() - days * 86400))
        cur = self.db.execute("DELETE FROM events WHERE ts < ?", (cutoff,))
        return cur.rowcount

    def export_markdown(self, task_id: Optional[int] = None, limit: int = 2000) -> str:
        rows = list(reversed(self.search(task_id=task_id, limit=limit)))
        lines = ["# Journal d'activité JARVIS", "", f"Exporté le {now()}", ""]
        for r in rows:
            extra = f" · outil {r['tool']}" if r.get("tool") else ""
            lines.append(f"- `{r['ts']}` **{r['level']}** [{r['kind']}{extra}] {r['message']}")
        return "\n".join(lines) + "\n"


def to_json_line(ev: Dict[str, Any]) -> str:
    return json.dumps(ev, ensure_ascii=False)
