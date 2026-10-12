#!/usr/bin/env python3
"""Lanceur de JARVIS.

  python3 jarvis.py start      démarre JARVIS en arrière-plan et ouvre la fenêtre
  python3 jarvis.py serve      démarre au premier plan (journal dans le terminal)
  python3 jarvis.py stop       arrêt propre
  python3 jarvis.py status     état des services (contrôle de santé)
  python3 jarvis.py open       ouvre la fenêtre
  python3 jarvis.py backup     sauvegarde vérifiée
  python3 jarvis.py test       lance la suite de tests
"""
from __future__ import annotations

import json
import os
import secrets
import signal
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from jarvis import VERSION, paths  # noqa: E402

CHROME = "/Applications/Google Chrome.app"


def port() -> int:
    return int(os.environ.get("JARVIS_PORT", "8765"))


def token_file() -> Path:
    return paths.data_dir() / "token"


def pid_file() -> Path:
    return paths.data_dir() / "jarvis.pid"


def health(timeout: float = 1.5) -> bool:
    try:
        req = urllib.request.Request(f"http://127.0.0.1:{port()}/api/health", headers={"Host": f"127.0.0.1:{port()}"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read()).get("ok", False)
    except Exception:  # noqa: BLE001
        return False


def api(method: str, path: str, body=None):
    tok = token_file().read_text().strip()
    req = urllib.request.Request(f"http://127.0.0.1:{port()}{path}", method=method,
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers={"X-Jarvis-Token": tok, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read())


def serve() -> None:
    from jarvis.app import JarvisApp
    from jarvis.server import serve as make_server
    tok = secrets.token_urlsafe(32)
    tf = token_file()
    tf.write_text(tok)
    os.chmod(tf, 0o600)
    pid_file().write_text(str(os.getpid()))
    app = JarvisApp(port())
    srv = make_server(app, port(), tok)

    def stop(*_):
        import threading
        threading.Thread(target=lambda: (app.shutdown(), srv.shutdown()), daemon=True).start()

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    print(f"JARVIS {VERSION} — http://127.0.0.1:{port()}/  (Ctrl+C pour arrêter)", flush=True)
    try:
        srv.serve_forever(poll_interval=0.3)
    finally:
        srv.server_close()
        app.db.close()
        for f in (pid_file(),):
            if f.exists():
                f.unlink()
        print("JARVIS arrêté proprement.", flush=True)


def open_window() -> None:
    url = f"http://127.0.0.1:{port()}/"
    if os.path.isdir(CHROME):
        # Fenêtre d'application dédiée (sans barre d'adresse), profil séparé.
        profile = paths.data_dir() / "fenetre-chrome"
        subprocess.Popen(["open", "-na", CHROME, "--args", f"--app={url}", f"--user-data-dir={profile}",
                          "--window-size=1440,900", "--no-first-run", "--no-default-browser-check"])
    else:
        subprocess.Popen(["open", url])


def start() -> None:
    if health():
        print("JARVIS est déjà démarré.")
    else:
        log = paths.logs_dir() / "jarvis.log"
        with open(log, "ab") as out:
            subprocess.Popen([sys.executable, str(ROOT / "jarvis.py"), "serve"], cwd=str(ROOT), stdout=out, stderr=subprocess.STDOUT,
                             stdin=subprocess.DEVNULL, start_new_session=True)
        for _ in range(60):
            if health():
                break
            time.sleep(0.25)
        else:
            print(f"Échec du démarrage. Voir {log}")
            sys.exit(1)
        print(f"JARVIS démarré sur http://127.0.0.1:{port()}/")
    open_window()


def stop() -> None:
    if not health():
        print("JARVIS n'est pas démarré.")
        return
    try:
        api("POST", "/api/shutdown")
    except Exception:  # noqa: BLE001
        if pid_file().exists():
            os.kill(int(pid_file().read_text()), signal.SIGTERM)
    for _ in range(40):
        if not health(0.5):
            print("JARVIS arrêté proprement.")
            return
        time.sleep(0.25)
    print("Arrêt non confirmé.")


def status() -> None:
    if not health():
        print("JARVIS : arrêté")
        sys.exit(1)
    d = api("GET", "/api/diagnostics")["data"]
    print(f"JARVIS {VERSION} : démarré — {d['summary']}")
    for c in d["checks"]:
        print(f"  {'✓' if c['ok'] else ('·' if c['niveau'] == 'info' else '✗')} {c['composant']} — {c['detail']}")


def backup() -> None:
    if health():
        r = api("POST", "/api/backups")["data"]
    else:
        from jarvis.app import JarvisApp
        r = JarvisApp(port(), start_background=False).backups.create("ligne de commande")
    print(f"Sauvegarde : {r['path']} ({r['verification']['detail']})")


def test() -> None:
    sys.exit(subprocess.call([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-t", ".", "-v"], cwd=str(ROOT)))


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "start"
    {"start": start, "serve": serve, "stop": stop, "status": status, "open": open_window, "backup": backup, "test": test}.get(
        cmd, lambda: print(__doc__))()
