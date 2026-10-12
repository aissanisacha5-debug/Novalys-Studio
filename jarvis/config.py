"""Préférences de JARVIS, persistées dans SQLite et versionnées.

Chaque modification crée un instantané dans config_versions (restaurable).
Les réglages qui élargissent des droits (dossiers, autonomie, commandes,
envoi d'e-mails) sont dits « sensibles » : l'API exige une confirmation
explicite avant de les appliquer (voir server.py) et l'agent n'a aucun
outil pour les modifier.
"""
from __future__ import annotations

import copy
import threading
from typing import Any, Dict, List

from . import CONFIG_SCHEMA_VERSION, paths
from .db import Database, dumps, loads, now
from .errors import ValidationError

MODES = {
    "conversation": "Répond sans aucune action (aucun outil).",
    "assistance": "Lit, recherche, analyse et prépare (outils à risque faible seulement).",
    "execution_supervisee": "Exécute les tâches autorisées ; confirmation pour toute action sensible.",
    "autonomie_limitee": "Exécute les automatisations configurées dans leur périmètre ; confirmation pour les actions à risque élevé.",
    "developpement": "Travaille dans les dossiers de projet, lance tests et serveurs locaux.",
    "maintenance": "Diagnostic, journaux, propositions de correction (lecture seule).",
    "vocal": "Comme l'exécution supervisée, avec commandes vocales.",
}


def default_settings() -> Dict[str, Any]:
    return {
        "appearance": {"theme": "obsidian-emerald", "animations": "normales", "density": "confortable"},
        "assistant": {"name": "JARVIS", "detail_level": "normal", "language": "fr"},
        "ai": {
            "provider": "claude_code",
            "model": "sonnet",
            "fallback_model": "haiku",
            "fallback_provider": None,
            "fallback_provider_model": None,
            "models_by_agent": {"synthese": "haiku", "diagnostic": "haiku"},
            "openai_compatible": {"base_url": "", "model": "", "label": ""},
            "timeout_s": 180,
            "send_private_files_remote": False,
        },
        "voice": {
            "tts_engine": "macos_say",
            "voice": "Thomas",
            "volume": 0.8,
            "rate": 190,
            "auto_speak": False,
            "max_spoken_chars": 600,
            "stt_engine": "navigateur",
            "wake_word": {"enabled": False, "phrase": "Hey Jarvis", "sensitivity": 0.5},
        },
        "notifications": {
            "enabled": True,
            "macos": True,
            "kinds": ["tache_terminee", "erreur", "confirmation", "projet_bloque", "automatisation_echec", "integration", "limite", "rappel"],
            "quiet_hours": {"enabled": True, "start": "22:00", "end": "08:00"},
            "hide_content": True,
        },
        "startup": {"open_window": True, "browser": "chrome", "port": 8765},
        "shortcuts": {"focus_input": "/", "voice": "Alt+Space", "stop": "Escape", "palette": "Meta+K"},
        "confirmations": {"moderate_needs_confirmation": False},
        "autonomy": {"mode": "execution_supervisee", "max_steps": 12, "max_task_seconds": 900, "max_retries": 2},
        "allowed_dirs": [
            {"path": str(paths.workspace_dir()), "mode": "rw", "label": "Espace de travail JARVIS"},
            {"path": str(paths.CYPHER_DIR), "mode": "r", "label": "Dossier CYPHER (lecture seule)"},
        ],
        "shell": {
            "allowed_commands": [
                "ls", "pwd", "cat", "head", "tail", "wc", "grep", "find", "diff", "echo", "date", "du", "df",
                "python3", "git", "swift", "open", "zip", "unzip", "tar", "file", "stat", "sort", "uniq", "which",
                "sw_vers", "uname", "say", "mdfind", "sqlite3", "npm", "node", "npx",
            ],
            "max_output_chars": 20000,
            "default_timeout_s": 60,
        },
        "email": {"mode": "brouillons", "send_enabled": False},
        "budget": {"daily_usd": 0.0, "monthly_usd": 0.0, "max_calls_per_day": 300, "stop_on_exceed": True},
        "retention": {"events_days": 180, "keep_audio": False},
        "web": {"search_engine": "duckduckgo_html", "max_pages_per_task": 15, "user_agent": "JARVIS/0.1 (assistant personnel; usage raisonnable)"},
    }


SENSITIVE_KEYS = {
    "allowed_dirs",
    "autonomy.mode",
    "shell.allowed_commands",
    "email.send_enabled",
    "email.mode",
    "ai.send_private_files_remote",
    "ai.openai_compatible",
    "budget",
    "confirmations.moderate_needs_confirmation",
    "connectors",
    "plugins_enabled",
    "web",
}


def _deep_merge(base: Dict[str, Any], over: Dict[str, Any]) -> Dict[str, Any]:
    out = copy.deepcopy(base)
    for k, v in (over or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


def _flatten_keys(d: Dict[str, Any], prefix: str = "") -> List[str]:
    keys = []
    for k, v in d.items():
        full = f"{prefix}.{k}" if prefix else k
        keys.append(full)
        if isinstance(v, dict):
            keys.extend(_flatten_keys(v, full))
    return keys


def touches_sensitive(patch: Dict[str, Any]) -> List[str]:
    hit = []
    for k in _flatten_keys(patch):
        if k in SENSITIVE_KEYS:
            hit.append(k)
    return sorted(set(hit))


class Settings:
    def __init__(self, db: Database):
        self.db = db
        self._lock = threading.RLock()
        self._cache: Dict[str, Any] = {}
        self.reload()

    def reload(self) -> None:
        row = self.db.one("SELECT value FROM settings WHERE key='prefs'")
        stored = loads(row["value"], {}) if row else {}
        with self._lock:
            self._cache = _deep_merge(default_settings(), stored)
        if not row:
            self._save(self._cache, "valeurs par défaut")

    def all(self) -> Dict[str, Any]:
        with self._lock:
            return copy.deepcopy(self._cache)

    def get(self, dotted: str, default: Any = None) -> Any:
        cur: Any = self.all()
        for part in dotted.split("."):
            if not isinstance(cur, dict) or part not in cur:
                return default
            cur = cur[part]
        return cur

    def update(self, patch: Dict[str, Any], reason: str = "modification") -> Dict[str, Any]:
        if not isinstance(patch, dict):
            raise ValidationError("Le correctif de configuration doit être un objet.")
        self._validate(patch)
        with self._lock:
            new = _deep_merge(self._cache, patch)
            self._save(new, reason)
            self._cache = new
            return copy.deepcopy(new)

    def _save(self, value: Dict[str, Any], reason: str) -> None:
        self.db.execute(
            "INSERT INTO settings(key, value, updated_at) VALUES('prefs', ?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
            (dumps(value), now()),
        )
        self.db.execute(
            "INSERT INTO config_versions(schema_version, snapshot, reason, created_at) VALUES (?,?,?,?)",
            (CONFIG_SCHEMA_VERSION, dumps(value), reason, now()),
        )

    def versions(self, limit: int = 30) -> List[Dict[str, Any]]:
        return self.db.all(
            "SELECT id, schema_version, reason, created_at FROM config_versions ORDER BY id DESC LIMIT ?", (limit,)
        )

    def restore_version(self, version_id: int) -> Dict[str, Any]:
        row = self.db.one("SELECT snapshot FROM config_versions WHERE id=?", (version_id,))
        if not row:
            raise ValidationError("Version de configuration introuvable.")
        snap = loads(row["snapshot"], {})
        with self._lock:
            self._save(snap, f"restauration de la version {version_id}")
            self._cache = _deep_merge(default_settings(), snap)
            return copy.deepcopy(self._cache)

    # -- validation -------------------------------------------------------
    def _validate(self, patch: Dict[str, Any]) -> None:
        ap = patch.get("appearance", {})
        if "animations" in ap and ap["animations"] not in ("normales", "reduites", "aucune"):
            raise ValidationError("animations : normales, reduites ou aucune.")
        au = patch.get("autonomy", {})
        if "mode" in au and au["mode"] not in MODES:
            raise ValidationError("Mode inconnu.", {"modes": list(MODES)})
        for k, lo, hi in (("max_steps", 1, 50), ("max_task_seconds", 10, 7200), ("max_retries", 0, 5)):
            if k in au and not (isinstance(au[k], int) and lo <= au[k] <= hi):
                raise ValidationError(f"autonomy.{k} doit être un entier entre {lo} et {hi}.")
        vo = patch.get("voice", {})
        if "volume" in vo and not (isinstance(vo["volume"], (int, float)) and 0 <= vo["volume"] <= 1):
            raise ValidationError("voice.volume doit être entre 0 et 1.")
        if "rate" in vo and not (isinstance(vo["rate"], int) and 80 <= vo["rate"] <= 400):
            raise ValidationError("voice.rate doit être entre 80 et 400 mots/minute.")
        if "allowed_dirs" in patch:
            dirs = patch["allowed_dirs"]
            if not isinstance(dirs, list):
                raise ValidationError("allowed_dirs doit être une liste.")
            for d in dirs:
                if not isinstance(d, dict) or d.get("mode") not in ("r", "rw") or not str(d.get("path", "")).startswith("/"):
                    raise ValidationError("Chaque dossier autorisé : {path absolu, mode r|rw}.")
        det = patch.get("assistant", {}).get("detail_level")
        if det is not None and det not in ("court", "normal", "detaille"):
            raise ValidationError("detail_level : court, normal ou detaille.")
