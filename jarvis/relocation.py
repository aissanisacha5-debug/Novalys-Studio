"""Migration des données de l'ancien emplacement (dossier du dépôt, v0.1/v0.2) vers les emplacements
de l'application indépendante. Copie seulement : l'ancien emplacement n'est jamais supprimé."""
from __future__ import annotations

import json
import os
import shutil
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, Optional

from . import paths

MARKER = "migration-v03.json"


def migrate_legacy() -> Optional[Dict[str, Any]]:
    """Copie la base et l'espace de travail historiques si le nouvel emplacement est vide."""
    env = os.environ.get("JARVIS_DATA_DIR")
    if (env and Path(env).resolve() != paths.DEFAULT_DATA.resolve()) or os.environ.get("JARVIS_NO_MIGRATION"):
        return None          # emplacement explicite (tests, développement, démonstration) : pas de migration
    data = paths.data_dir()
    if (data / "jarvis.db").exists() or (data / MARKER).exists():
        return None          # déjà migré ou installation existante : aucun accès à l'ancien dossier
    for root in paths.LEGACY_ROOTS:
        old_db = root / "data" / "jarvis.db"
        if not old_db.exists():
            continue
        src = sqlite3.connect(str(old_db))
        dst = sqlite3.connect(str(data / "jarvis.db"))
        src.backup(dst)
        dst.close()
        src.close()
        for sub in ("backups", "versions", "corbeille"):
            if (root / "data" / sub).is_dir():
                shutil.copytree(str(root / "data" / sub), str(data / sub), dirs_exist_ok=True)
        ws_old, ws_new = root / "workspace", paths.workspace_dir()
        copied_ws = False
        if ws_old.is_dir() and not any(ws_new.iterdir()):
            shutil.copytree(str(ws_old), str(ws_new), dirs_exist_ok=True)
            copied_ws = True
        info = {"from": str(root), "at": time.strftime("%Y-%m-%dT%H:%M:%S"), "workspace_copied": copied_ws,
                "old_workspace": str(ws_old), "note": "copie ; l'ancien emplacement est conservé"}
        (data / MARKER).write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
        return info
    (data / MARKER).write_text(json.dumps({"from": None, "at": time.strftime("%Y-%m-%dT%H:%M:%S")}), encoding="utf-8")
    return None


def fix_allowed_dirs(settings) -> bool:
    """Remplace l'ancien espace de travail par le nouveau dans les dossiers autorisés (après migration)."""
    marker = paths.data_dir() / MARKER
    if not marker.exists():
        return False
    old = {str(Path(r) / "workspace") for r in paths.LEGACY_ROOTS}
    new = str(paths.workspace_dir())
    dirs = settings.get("allowed_dirs", []) or []
    changed = False
    out = []
    for d in dirs:
        if d.get("path") in old:
            d = {**d, "path": new, "label": "Espace de travail JARVIS"}
            changed = True
        if d.get("path") == str(paths.ROOT.parent) and paths.ROOT.parent != paths.CYPHER_DIR and (paths.CYPHER_DIR).exists():
            d = {**d, "path": str(paths.CYPHER_DIR)}
            changed = True
        if d not in out:
            out.append(d)
    if changed:
        settings.update({"allowed_dirs": out}, "relocalisation : espace de travail de l'application indépendante")
    return changed
