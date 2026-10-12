#!/usr/bin/env python3
"""Lanceur de JARVIS.

  python3 jarvis.py start      démarre JARVIS en arrière-plan et ouvre la fenêtre
  python3 jarvis.py serve      démarre au premier plan (journal dans le terminal)
  python3 jarvis.py stop       arrêt propre
  python3 jarvis.py status     état des services (contrôle de santé)
  python3 jarvis.py open       ouvre la fenêtre
  python3 jarvis.py backup     sauvegarde vérifiée
  python3 jarvis.py test       lance la suite de tests
  python3 jarvis.py verifier   vérification statique (syntaxe 3.9, imports, JS, CSS, secrets)
  python3 jarvis.py check      verifier + test (à lancer avant chaque livraison)
  python3 jarvis.py deps       contrôle des prérequis système (aucune dépendance à installer)
  python3 jarvis.py dev        mode développement : données séparées (data-dev), port 8766, rechargement auto
  python3 jarvis.py demo       démonstration : données FICTIVES séparées (data-demo), port 8767
  python3 jarvis.py build      check + compilation de dist/JARVIS.app et dist/JARVIS-<version>.dmg
  python3 jarvis.py install    installe dist/JARVIS.app dans ~/Applications (l'ancienne version est conservée à part)
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
INSTALLED_APP = Path.home() / "Applications" / "JARVIS.app"


def installed_native_app() -> bool:
    return (INSTALLED_APP / "Contents" / "Resources" / "app" / "jarvis.py").exists()


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
    if os.environ.get("JARVIS_NO_WINDOW"):
        return
    if installed_native_app() and port() == 8765:
        subprocess.Popen(["open", str(INSTALLED_APP)])        # fenêtre native JARVIS
        return
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


def verifier() -> None:
    env = dict(os.environ)
    env.setdefault("JARVIS_DATA_DIR", str(ROOT / "data-verif"))
    code = subprocess.call([sys.executable, str(ROOT / "scripts" / "verifier.py")], cwd=str(ROOT), env=env)
    import shutil
    shutil.rmtree(ROOT / "data-verif", ignore_errors=True)
    if code:
        sys.exit(code)


def check() -> None:
    verifier()
    code = subprocess.call([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-t", "."], cwd=str(ROOT))
    if code:
        sys.exit(code)
    print("check : vérification statique et tests OK.")


def deps() -> None:
    import shutil
    import sqlite3
    ok = True

    def line(name, good, detail):
        nonlocal ok
        ok = ok and good
        print(f"  {'✓' if good else '✗'} {name} — {detail}")

    print("Prérequis JARVIS (rien à installer) :")
    line("Python ≥ 3.9", sys.version_info >= (3, 9), sys.version.split()[0])
    try:
        sqlite3.connect(":memory:").execute("CREATE VIRTUAL TABLE t USING fts5(x)")
        line("SQLite + FTS5", True, sqlite3.sqlite_version)
    except sqlite3.Error as e:
        line("SQLite + FTS5", False, str(e))
    from jarvis.providers.claude_code import claude_bin
    line("Claude Code (fournisseur IA)", bool(claude_bin()), claude_bin() or "absent : installer Claude Code puis se connecter")
    line("Google Chrome (fenêtre, PDF, navigateur piloté)", os.path.isdir(CHROME), CHROME)
    for tool in ("say", "osascript", "textutil", "security", "sips", "iconutil"):
        line(tool, bool(shutil.which(tool)), shutil.which(tool) or "absent")
    if not ok:
        sys.exit(1)


def _child(env_extra, port):
    env = {**os.environ, **env_extra, "JARVIS_PORT": str(port)}
    return subprocess.Popen([sys.executable, str(ROOT / "jarvis.py"), "serve"], cwd=str(ROOT), env=env)


def dev() -> None:
    """Serveur de développement : données séparées, redémarrage dès qu'un fichier Python change."""
    extra = {"JARVIS_DATA_DIR": str(ROOT / "data-dev"), "JARVIS_WORKSPACE": str(ROOT / "workspace-dev")}
    files = lambda: {p: p.stat().st_mtime for p in (ROOT / "jarvis").rglob("*.py")}  # noqa: E731
    seen = files()
    proc = _child(extra, 8766)
    print("Mode développement : http://127.0.0.1:8766/ (Ctrl+C pour arrêter). Le web se recharge avec ⌘R.")
    try:
        while True:
            time.sleep(1)
            cur = files()
            if cur != seen:
                seen = cur
                print("Changement détecté : redémarrage du backend…")
                proc.terminate()
                proc.wait(10)
                proc = _child(extra, 8766)
    except KeyboardInterrupt:
        proc.terminate()


def demo() -> None:
    """Démonstration avec des données FICTIVES, totalement séparées des données réelles."""
    os.environ["JARVIS_DATA_DIR"] = str(ROOT / "data-demo")
    os.environ["JARVIS_WORKSPACE"] = str(ROOT / "workspace-demo")
    os.environ["JARVIS_PORT"] = "8767"
    from jarvis.app import JarvisApp
    app = JarvisApp(8767, start_background=False)
    if not app.db.one("SELECT id FROM projects WHERE name LIKE '[DÉMO]%'"):
        p = app.projects.create("[DÉMO] Site Trattoria Fictiva", description="Projet fictif de démonstration.",
                                objectives="Site vitrine 5 pages, réservation par téléphone.", success_criteria="Contrôle qualité sans erreur.")
        app.tasks.create("[DÉMO] Rédiger les textes de la page d'accueil", kind="todo", project_id=p["id"], start=False, priority=3)
        app.tasks.create("[DÉMO] Choisir les photos (libres de droits)", kind="todo", project_id=p["id"], start=False)
        app.memory.add("[DÉMO] Le client fictif préfère des tons chauds.", "preference", "démonstration", "preference", "donnée fictive", project_id=p["id"])
        app.reminders.add("[DÉMO] Appeler le client fictif", time.strftime("%Y-%m-%dT18:00"))
        print("Données fictives de démonstration créées (préfixe [DÉMO]).")
    app.shutdown()
    app.db.close()
    with open(paths.logs_dir() / "demo.log", "ab") as out:
        subprocess.Popen([sys.executable, str(ROOT / "jarvis.py"), "serve"], cwd=str(ROOT), stdout=out, stderr=subprocess.STDOUT,
                         env=dict(os.environ), start_new_session=True)
    for _ in range(60):
        if health():
            break
        time.sleep(0.25)
    print("Démonstration : http://127.0.0.1:8767/  (arrêt : JARVIS_PORT=8767 JARVIS_DATA_DIR=data-demo python3 jarvis.py stop)")
    open_window()


def build() -> None:
    """Vérifie, teste, puis compile l'application native et l'image disque (dist/)."""
    check()
    code = subprocess.call([sys.executable, str(ROOT / "scripts" / "build_app.py")], cwd=str(ROOT))
    if code:
        sys.exit(code)


def install() -> None:
    """Installe dist/JARVIS.app dans ~/Applications sans toucher aux données (elles sont dans Application Support)."""
    import shutil
    src = ROOT / "dist" / "JARVIS.app"
    if not src.exists():
        print("Aucune application construite : lancer d'abord « python3 jarvis.py build ».")
        sys.exit(1)
    INSTALLED_APP.parent.mkdir(parents=True, exist_ok=True)
    if INSTALLED_APP.exists():
        keep = paths.SUPPORT_DIR / "anciennes-versions" / f"JARVIS-{time.strftime('%Y%m%d-%H%M%S')}.app"
        keep.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(INSTALLED_APP), str(keep))
        print(f"Ancienne version conservée : {keep}")
    shutil.copytree(str(src), str(INSTALLED_APP), symlinks=True)
    r = subprocess.run(["codesign", "--verify", "--deep", "--strict", str(INSTALLED_APP)], capture_output=True)
    print(f"Installé : {INSTALLED_APP} (signature {'valide' if r.returncode == 0 else 'INVALIDE'})")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "start"
    {"start": start, "serve": serve, "stop": stop, "status": status, "open": open_window, "backup": backup, "test": test,
     "verifier": verifier, "check": check, "deps": deps, "dev": dev, "demo": demo, "build": build, "install": install}.get(
        cmd, lambda: print(__doc__))()
