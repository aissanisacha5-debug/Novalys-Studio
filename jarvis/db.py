"""Accès SQLite et migrations versionnées.

Une seule base (data/jarvis.db). Les migrations sont les fichiers
jarvis/migrations/NNNN_nom.sql, appliqués dans l'ordre et notés dans
la table schema_migrations. Une sauvegarde est faite avant toute
migration sur une base existante.
"""
from __future__ import annotations

import json
import shutil
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from . import paths


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


class Database:
    def __init__(self, path: Optional[Path] = None):
        self.path = Path(path or paths.db_path())
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(str(self.path), check_same_thread=False, isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.execute("PRAGMA busy_timeout=5000")

    # -- requêtes -------------------------------------------------------
    def execute(self, sql: str, params: Iterable[Any] = ()) -> sqlite3.Cursor:
        with self._lock:
            return self._conn.execute(sql, tuple(params))

    def insert(self, sql: str, params: Iterable[Any] = ()) -> int:
        with self._lock:
            cur = self._conn.execute(sql, tuple(params))
            return int(cur.lastrowid)

    def one(self, sql: str, params: Iterable[Any] = ()) -> Optional[Dict[str, Any]]:
        with self._lock:
            row = self._conn.execute(sql, tuple(params)).fetchone()
        return dict(row) if row else None

    def all(self, sql: str, params: Iterable[Any] = ()) -> List[Dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(sql, tuple(params)).fetchall()
        return [dict(r) for r in rows]

    def transaction(self):
        return _Tx(self)

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    # -- migrations -----------------------------------------------------
    def migrate(self) -> List[str]:
        self.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations (version TEXT PRIMARY KEY, applied_at TEXT NOT NULL)"
        )
        done = {r["version"] for r in self.all("SELECT version FROM schema_migrations")}
        files = sorted(p for p in paths.MIGRATIONS_DIR.glob("*.sql"))
        pending = [f for f in files if f.stem not in done]
        if pending and done:
            self.backup_file(suffix="avant-migration")
        applied = []
        for f in pending:
            sql = f.read_text(encoding="utf-8")
            with self._lock:
                self._conn.executescript("BEGIN;" + sql + "\nCOMMIT;")
                self._conn.execute(
                    "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)", (f.stem, now())
                )
            applied.append(f.stem)
        return applied

    def schema_version(self) -> str:
        r = self.one("SELECT max(version) AS v FROM schema_migrations")
        return (r or {}).get("v") or "aucune"

    def backup_file(self, dest: Optional[Path] = None, suffix: str = "") -> Path:
        """Copie cohérente de la base (API backup de SQLite)."""
        stamp = time.strftime("%Y%m%d-%H%M%S")
        dest = dest or paths.backups_dir() / f"jarvis-{stamp}{('-' + suffix) if suffix else ''}.db"
        with self._lock:
            target = sqlite3.connect(str(dest))
            self._conn.backup(target)
            target.close()
        return dest


class _Tx:
    def __init__(self, db: Database):
        self.db = db

    def __enter__(self):
        self.db._lock.acquire()
        self.db._conn.execute("BEGIN")
        return self.db

    def __exit__(self, exc_type, exc, tb):
        try:
            if exc_type is None:
                self.db._conn.execute("COMMIT")
            else:
                self.db._conn.execute("ROLLBACK")
        finally:
            self.db._lock.release()
        return False


def dumps(v: Any) -> str:
    return json.dumps(v, ensure_ascii=False)


def loads(s: Optional[str], default: Any = None) -> Any:
    if not s:
        return default
    try:
        return json.loads(s)
    except ValueError:
        return default


def copy_file(src: Path, dst: Path) -> None:
    shutil.copy2(str(src), str(dst))
