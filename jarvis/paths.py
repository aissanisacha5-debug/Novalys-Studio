"""Emplacements des fichiers de JARVIS.

Tout est relatif au dossier JARVIS/ ; la variable d'environnement
JARVIS_DATA_DIR permet aux tests d'utiliser un dossier jetable.
"""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WEB_DIR = ROOT / "web"
MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"


def data_dir() -> Path:
    d = Path(os.environ.get("JARVIS_DATA_DIR", str(ROOT / "data")))
    d.mkdir(parents=True, exist_ok=True)
    return d


def workspace_dir() -> Path:
    d = Path(os.environ.get("JARVIS_WORKSPACE", str(ROOT / "workspace")))
    d.mkdir(parents=True, exist_ok=True)
    return d


def db_path() -> Path:
    return data_dir() / "jarvis.db"


def backups_dir() -> Path:
    d = data_dir() / "backups"
    d.mkdir(parents=True, exist_ok=True)
    return d


def logs_dir() -> Path:
    d = data_dir() / "logs"
    d.mkdir(parents=True, exist_ok=True)
    return d


# Dossier CYPHER (parent de JARVIS) : lu en lecture seule par le module agence.
CYPHER_DIR = ROOT.parent
