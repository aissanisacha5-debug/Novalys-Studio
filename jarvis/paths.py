"""Emplacements des fichiers de JARVIS.

Code, données et fichiers produits sont séparés :
- code : le dossier de l'application (dans JARVIS.app/Contents/Resources/app, ou le dépôt en développement) ;
- données : ~/Library/Application Support/JARVIS/data (base, jeton, sauvegardes, journaux) ;
- espace de travail : ~/JARVIS (sites, rapports, documents produits, visibles dans le Finder).
Les variables JARVIS_DATA_DIR / JARVIS_WORKSPACE / JARVIS_CYPHER_DIR permettent de les déplacer
(tests, mode développement, démonstration).
"""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WEB_DIR = ROOT / "web"
MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"


SUPPORT_DIR = Path.home() / "Library" / "Application Support" / "JARVIS"
DEFAULT_DATA = SUPPORT_DIR / "data"
DEFAULT_WORKSPACE = Path.home() / "JARVIS"
# Emplacements de la v0.1/v0.2 (données dans le dépôt) : migrés une fois, jamais supprimés.
LEGACY_ROOTS = [ROOT, Path.home() / "Documents" / "CYPHER" / "JARVIS"]


def data_dir() -> Path:
    d = Path(os.environ.get("JARVIS_DATA_DIR", str(DEFAULT_DATA)))
    d.mkdir(parents=True, exist_ok=True)
    return d


def workspace_dir() -> Path:
    d = Path(os.environ.get("JARVIS_WORKSPACE", str(DEFAULT_WORKSPACE)))
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


# Dossier CYPHER (assistant business de Sacha) : lu en lecture seule par le module agence.
CYPHER_DIR = Path(os.environ.get("JARVIS_CYPHER_DIR", str(Path.home() / "Documents" / "CYPHER")))
