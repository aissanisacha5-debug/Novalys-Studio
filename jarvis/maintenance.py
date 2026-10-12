"""Diagnostic, sauvegarde, restauration et vérification (parties 9.3, 29, 31)."""
from __future__ import annotations

import json
import os
import shutil
import sqlite3
import time
import zipfile
from pathlib import Path
from typing import Any, Dict, List

from . import VERSION, paths
from .db import now
from .errors import NotFound, ValidationError
from .services import system_info


def versions() -> Dict[str, str]:
    """Versions des composants dont JARVIS dépend (aucune dépendance Python externe)."""
    import platform
    import subprocess
    out = {"jarvis": VERSION, "python": platform.python_version(), "sqlite": sqlite3.sqlite_version, "macos": platform.mac_ver()[0]}
    try:
        from .providers.claude_code import claude_bin
        b = claude_bin()
        out["claude_code"] = subprocess.run([b, "--version"], capture_output=True, text=True, timeout=10).stdout.strip() if b else "absent"
    except Exception:  # noqa: BLE001
        out["claude_code"] = "inconnu"
    chrome = "/Applications/Google Chrome.app/Contents/Info.plist"
    try:
        import plistlib
        with open(chrome, "rb") as f:
            out["chrome"] = plistlib.load(f).get("CFBundleShortVersionString", "?")
    except OSError:
        out["chrome"] = "absent"
    return out


class Diagnostics:
    def __init__(self, app):
        self.app = app

    def report(self) -> str:
        """Rapport copiable, expurgé : pas de chemins personnels, de contenus ni de secrets."""
        from .logbook import redact
        d = self.run()
        home = os.path.expanduser("~")
        lines = [f"# Diagnostic JARVIS — {d['at']}", "", f"Résultat : {d['summary']}", "", "## Composants"]
        lines += [f"- {'OK' if c['ok'] else c['niveau'].upper()} · {c['composant']} : {c['detail']}" for c in d["checks"]]
        lines += ["", "## Versions"] + [f"- {k} : {v}" for k, v in d["versions"].items()]
        sysi = d["system"]
        lines += ["", "## Système", f"- processeur : {sysi.get('cpu', {}).get('percent', '?')} %",
                  f"- mémoire : {sysi.get('memory', {}).get('used_gb', '?')} / {sysi.get('memory', {}).get('total_gb', '?')} Go",
                  f"- disque libre : {sysi['disk']['free_gb']} Go"]
        errs = self.app.db.all("SELECT ts, kind, tool FROM events WHERE level='erreur' ORDER BY id DESC LIMIT 10")
        lines += ["", "## Dernières erreurs (types seulement)"] + ([f"- {e['ts']} {e['kind']} {e['tool'] or ''}" for e in errs] or ["- aucune"])
        return redact("\n".join(lines).replace(home, "~")) + "\n"

    def run(self, quick: bool = False) -> Dict[str, Any]:
        app = self.app
        checks: List[Dict[str, Any]] = []

        def add(name, ok, detail, level=None):
            checks.append({"composant": name, "ok": bool(ok), "niveau": level or ("ok" if ok else "erreur"), "detail": detail})

        try:
            integ = app.db.one("PRAGMA integrity_check")
            add("Base de données", list(integ.values())[0] == "ok", f"intégrité {list(integ.values())[0]}, schéma {app.db.schema_version()}")
        except Exception as e:  # noqa: BLE001
            add("Base de données", False, str(e))
        add("API locale", True, f"127.0.0.1:{app.port} · version {VERSION}")
        add("Planificateur", app.scheduler.alive(), f"dernier passage {app.scheduler.last_tick or 'jamais'}")
        prov = app.providers.status()
        active = [p for p in prov if p["active"]]
        add("Fournisseur IA actif", bool(active and active[0]["available"]),
            f"{active[0]['label']} : {active[0]['reason']}" if active else "aucun")
        for p in prov:
            if not p["active"]:
                checks.append({"composant": f"IA · {p['label']}", "ok": p["available"], "niveau": "ok" if p["available"] else "info", "detail": p["reason"]})
        tools = app.tools.listing()
        unav = [t["id"] for t in tools if not t["available"]]
        add("Registre d'outils", True, f"{len(tools)} outils, {len(tools) - len(unav)} disponibles" + (f" (indisponibles : {', '.join(unav)})" if unav else ""))
        add("Voix (synthèse)", bool(shutil.which("say")), f"{len(app.voice.voices())} voix")
        add("Notifications macOS", bool(shutil.which("osascript")), "osascript présent")
        ws = paths.workspace_dir()
        add("Espace de travail", os.access(ws, os.W_OK), str(ws))
        backups = sorted(paths.backups_dir().glob("*.zip"))
        add("Sauvegardes", bool(backups), f"{len(backups)} sauvegarde(s), dernière : {backups[-1].name if backups else 'aucune'}",
            None if backups else "attention")
        recent_err = app.db.one("SELECT count(*) AS n FROM events WHERE level='erreur' AND ts >= ?",
                                (time.strftime("%Y-%m-%dT00:00:00"),))["n"]
        add("Erreurs du jour", recent_err == 0, f"{recent_err} erreur(s) journalisée(s) aujourd'hui", None if recent_err == 0 else "attention")
        stuck = app.db.all("SELECT id, title FROM tasks WHERE status IN ('interrompue','attente_autorisation')")
        add("Tâches à reprendre", not stuck, f"{len(stuck)} tâche(s) interrompue(s) ou en attente d'autorisation", None if not stuck else "attention")
        add("Migrations", True, f"schéma {app.db.schema_version()}, appliquées au démarrage : {', '.join(app.migrations) or 'aucune'}")
        br = [p for p in app.db.all("SELECT id FROM processes WHERE kind='navigateur' AND stopped_at IS NULL")]
        add("Navigateur piloté", os.path.exists("/Applications/Google Chrome.app"), ("ouvert" if br else "fermé (démarre à la demande)"))
        add("Voix (dictée)", True, "moteur de Chrome dans la fenêtre JARVIS ; micro autorisé par Sacha dans Chrome", "info")
        info = system_info()
        ok_count = sum(1 for c in checks if c["ok"])
        return {"at": now(), "summary": f"{ok_count}/{len(checks)} contrôles OK", "checks": checks, "system": info, "versions": versions()}


def _zip_add(z: zipfile.ZipFile, path: Path, arc: str) -> None:
    if path.exists():
        z.write(path, arc)


class Backups:
    """Sauvegarde = archive ZIP : copie cohérente de la base + config non sensible + manifeste.
    Aucun secret (ils sont dans le trousseau, jamais en base)."""

    def __init__(self, app):
        self.app = app

    def create(self, reason: str = "manuelle") -> Dict[str, Any]:
        stamp = time.strftime("%Y%m%d-%H%M%S")
        n = 1
        while (paths.backups_dir() / f"jarvis-sauvegarde-{stamp}.zip").exists():   # jamais d'écrasement
            n += 1
            stamp = time.strftime("%Y%m%d-%H%M%S") + f"-{n}"
        tmpdb = paths.backups_dir() / f".tmp-{stamp}.db"
        self.app.db.backup_file(tmpdb)
        dest = paths.backups_dir() / f"jarvis-sauvegarde-{stamp}.zip"
        manifest = {"format": "jarvis-sauvegarde-v1", "version": VERSION, "created_at": now(), "reason": reason,
                    "schema": self.app.db.schema_version()}
        with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as z:
            z.write(tmpdb, "jarvis.db")
            z.writestr("config.json", json.dumps(self.app.settings.all(), ensure_ascii=False, indent=2))
            z.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        tmpdb.unlink()
        v = self.verify(dest)
        if not v["ok"]:
            raise ValidationError("La sauvegarde créée ne passe pas la vérification.", v)
        self.app.logbook.log("sauvegarde", f"Sauvegarde créée et vérifiée : {dest.name}", "succes")
        self._rotate(keep=20)
        return {"path": str(dest), "size": dest.stat().st_size, "verification": v}

    def verify(self, path: Path) -> Dict[str, Any]:
        try:
            with zipfile.ZipFile(path) as z:
                if z.testzip() is not None:
                    return {"ok": False, "detail": "archive corrompue"}
                man = json.loads(z.read("manifest.json"))
                tmp = paths.backups_dir() / ".verif.db"
                tmp.write_bytes(z.read("jarvis.db"))
            c = sqlite3.connect(str(tmp))
            integ = c.execute("PRAGMA integrity_check").fetchone()[0]
            counts = {t: c.execute(f"SELECT count(*) FROM {t}").fetchone()[0] for t in ("memories", "tasks", "conversations", "projects")}
            c.close()
            tmp.unlink()
            return {"ok": integ == "ok", "detail": f"intégrité {integ}", "manifest": man, "counts": counts}
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "detail": str(e)}

    def list(self) -> List[Dict[str, Any]]:
        return [{"name": p.name, "size": p.stat().st_size, "created": time.strftime("%Y-%m-%d %H:%M", time.localtime(p.stat().st_mtime))}
                for p in sorted(paths.backups_dir().glob("jarvis-sauvegarde-*.zip"), reverse=True)]

    def _rotate(self, keep: int) -> None:
        files = sorted(paths.backups_dir().glob("jarvis-sauvegarde-*.zip"))
        # on ne supprime une ancienne sauvegarde que si la plus récente est vérifiée
        if files and self.verify(files[-1])["ok"]:
            for f in files[:-keep]:
                f.unlink()

    def restore(self, name: str) -> Dict[str, Any]:
        """Restaure une sauvegarde : l'état actuel est d'abord sauvegardé. Prend effet au redémarrage."""
        src = paths.backups_dir() / name
        if not src.exists() or "/" in name:
            raise NotFound("Sauvegarde introuvable.")
        v = self.verify(src)
        if not v["ok"]:
            raise ValidationError("Sauvegarde invalide : restauration refusée.", v)
        before = self.create("avant restauration")
        with zipfile.ZipFile(src) as z:
            (paths.data_dir() / "restauration-en-attente.db").write_bytes(z.read("jarvis.db"))
        self.app.logbook.log("sauvegarde", f"Restauration de {name} programmée (au prochain démarrage)", "attention")
        return {"restored_from": name, "safety_backup": before["path"], "effective": "au prochain démarrage de JARVIS"}


def apply_pending_restore() -> bool:
    pending = paths.data_dir() / "restauration-en-attente.db"
    if not pending.exists():
        return False
    db = paths.db_path()
    for ext in ("", "-wal", "-shm"):
        p = Path(str(db) + ext)
        if p.exists():
            p.unlink()
    shutil.move(str(pending), str(db))
    return True
