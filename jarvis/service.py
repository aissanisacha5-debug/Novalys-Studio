"""Service local et démarrage automatique (partie 6 du prompt 4).

États distingués :
- fenêtre fermée : l'application et le service continuent ; un clic sur l'icône rouvre la fenêtre ;
- application quittée : le service s'arrête proprement, SAUF si le démarrage automatique est activé
  (le service tourne alors en arrière-plan, géré par launchd) ;
- service arrêté : plus rien ne tourne (ni rappels, ni automatisations) ;
- Mac en veille : rien ne s'exécute pendant la veille ; les automatisations dues s'exécutent au réveil ;
- Mac éteint : rien ne s'exécute ; au redémarrage, les tâches en cours deviennent « interrompues » (reprise possible).

Le démarrage automatique (LaunchAgent utilisateur, sans droits administrateur) n'est activé que sur
demande explicite de Sacha, avec confirmation.
"""
from __future__ import annotations

import os
import plistlib
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict

from . import VERSION, paths

LABEL = "studio.novalys.jarvis.service"


def agents_dir() -> Path:
    return Path(os.environ.get("JARVIS_LAUNCHAGENTS_DIR", str(Path.home() / "Library" / "LaunchAgents")))


def plist_path() -> Path:
    return agents_dir() / f"{LABEL}.plist"


def build_plist(port: int) -> Dict[str, Any]:
    logs = paths.logs_dir()
    return {
        "Label": LABEL,
        "ProgramArguments": [sys.executable, str(paths.ROOT / "jarvis.py"), "serve"],
        "WorkingDirectory": str(paths.ROOT),
        "EnvironmentVariables": {"JARVIS_DATA_DIR": str(paths.data_dir()), "JARVIS_WORKSPACE": str(paths.workspace_dir()),
                                 "JARVIS_PORT": str(port), "JARVIS_LAUNCHD": "1", "PATH": "/usr/bin:/bin:/usr/sbin:/sbin:"
                                 + os.path.dirname(os.environ.get("JARVIS_CLAUDE_BIN", str(Path.home() / ".local" / "bin" / "claude")))},
        "RunAtLoad": True,
        "KeepAlive": {"SuccessfulExit": False},      # relancé seulement après un plantage, pas après un arrêt propre
        "ThrottleInterval": 30,
        "ProcessType": "Background",
        "StandardOutPath": str(logs / "service.log"),
        "StandardErrorPath": str(logs / "service.log"),
    }


def enable_autostart(port: int, load: bool = True) -> Dict[str, Any]:
    agents_dir().mkdir(parents=True, exist_ok=True)
    with open(plist_path(), "wb") as f:
        plistlib.dump(build_plist(port), f)
    loaded = False
    if load:
        # Le service courant tourne déjà : launchd ne le relancera qu'à la prochaine ouverture de session.
        r = subprocess.run(["launchctl", "bootstrap", f"gui/{os.getuid()}", str(plist_path())], capture_output=True, timeout=15)
        loaded = r.returncode == 0 or b"already" in r.stderr.lower() or b"in progress" in r.stderr.lower()
    return {"enabled": True, "plist": str(plist_path()), "registered_with_launchd": loaded}


def disable_autostart(unload: bool = True) -> Dict[str, Any]:
    if unload and plist_path().exists():
        subprocess.run(["launchctl", "bootout", f"gui/{os.getuid()}/{LABEL}"], capture_output=True, timeout=15)
    existed = plist_path().exists()
    if existed:
        plist_path().unlink()
    return {"enabled": False, "removed": existed}


def info(app) -> Dict[str, Any]:
    started = app.started_at
    return {
        "version": VERSION,
        "pid": os.getpid(),
        "started_at": started,
        "uptime_s": int(time.time() - app.started_ts),
        "launched_by": "launchd (démarrage automatique)" if os.environ.get("JARVIS_LAUNCHD") else
                       ("application JARVIS" if os.environ.get("JARVIS_APP") else "ligne de commande"),
        "autostart": plist_path().exists(),
        "windows_connected": app.bus.subscriber_count(),
        "code_dir": str(paths.ROOT),
        "data_dir": str(paths.data_dir()),
        "workspace_dir": str(paths.workspace_dir()),
        "states": {
            "fenetre_fermee": "Le service continue ; rouvrir la fenêtre par l'icône JARVIS.",
            "application_quittee": "Le service s'arrête proprement" + ("" if not plist_path().exists() else
                                                                      ", sauf ici : le démarrage automatique le garde en arrière-plan") + ".",
            "service_arrete": "Rien ne tourne : ni rappels, ni automatisations, ni tâches.",
            "veille": "Rien ne s'exécute pendant la veille ; les automatisations dues s'exécutent au réveil.",
            "eteint": "Rien ne s'exécute ; au redémarrage, les tâches en cours deviennent « interrompues » et peuvent être reprises.",
        },
    }
