"""Exécuteur de commandes contrôlé (partie 10).

- Jamais de shell : la commande est découpée (shlex) et lancée sans /bin/sh.
- Le programme doit figurer dans la liste autorisée (Paramètres > Sécurité).
- Les opérateurs de shell (|, ;, &&, >, $(…), `…`) sont refusés.
- Les arguments qui ressemblent à des chemins passent par le contrôle des dossiers.
- Commandes dangereuses : bloquées ; commandes sensibles : confirmation.
- Délai maximum, sortie limitée, arrêt du groupe de processus à l'annulation.
"""
from __future__ import annotations

import os
import re
import shlex
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .. import paths
from ..db import now
from ..errors import JarvisError, NotFound, PermissionDenied, ValidationError
from .registry import CONFIRME, ECHOUE, Tool, ToolContext

SHELL_META = re.compile(r"(\|\||&&|[|;<>`]|\$\(|\$\{|\n)")

ALWAYS_BLOCKED = {
    "rm", "rmdir", "sudo", "su", "dd", "mkfs", "diskutil", "csrutil", "spctl", "launchctl", "killall", "kill",
    "pkill", "shutdown", "reboot", "halt", "chmod", "chown", "chflags", "security", "defaults", "tccutil",
    "networksetup", "systemsetup", "pmset", "nvram", "bless", "fdesetup", "curl", "wget", "nc", "ssh", "scp",
    "osascript", "bash", "sh", "zsh", "fish", "eval", "exec", "crontab", "at", "softwareupdate", "installer",
}

# (motif sur la ligne complète, risque, raison)
SENSITIVE_RULES: List[Tuple[re.Pattern, str, str]] = [
    (re.compile(r"^git\s+(push|reset\s+--hard|clean\s+-[a-z]*f|checkout\s+--\s|branch\s+-D|rebase|filter-branch)"), "eleve",
     "opération Git difficile à annuler ou publiée à l'extérieur"),
    (re.compile(r"^find\b.*\s-(delete|exec|execdir|ok)\b"), "eleve", "find avec suppression ou exécution"),
    (re.compile(r"^python3\s+(-c|-m\s+pip)\b"), "eleve", "exécution de code arbitraire ou installation pip"),
    (re.compile(r"^(npm|npx)\s+(publish|login|adduser|token)"), "eleve", "publication ou identification npm"),
    (re.compile(r"^(npm\s+(install|i|ci|add)|npx)\b"), "modere", "installation de dépendances"),
    (re.compile(r"^open\s+(-a\s+)?\S*https?://"), "modere", "ouverture d'une adresse web"),
    (re.compile(r"^(unzip|tar)\b"), "modere", "extraction d'archive"),
    (re.compile(r"^git\s+(commit|add|init|mv|stash|tag|merge|pull|fetch|clone)"), "modere", "modification du dépôt"),
]


def _program(argv: List[str]) -> str:
    return os.path.basename(argv[0]) if argv else ""


def parse(command: str) -> List[str]:
    if not command or not command.strip():
        raise ValidationError("Commande vide.")
    if SHELL_META.search(command):
        raise PermissionDenied("Opérateurs de shell refusés (|, ;, &&, >, <, $(), `). Lance une commande simple.",
                               {"commande": command})
    try:
        argv = shlex.split(command)
    except ValueError as e:
        raise ValidationError(f"Commande mal formée : {e}")
    return argv


def classify(command: str, allowed: List[str]) -> Tuple[str, str]:
    """Retourne (risque, raison) ; lève PermissionDenied si la commande est interdite."""
    argv = parse(command)
    prog = _program(argv)
    if prog in ALWAYS_BLOCKED:
        raise PermissionDenied(f"Commande dangereuse bloquée : {prog}.", {"commande": command})
    if prog not in allowed:
        raise PermissionDenied(f"« {prog} » n'est pas dans la liste des commandes autorisées.",
                               {"commande": command, "autorisees": allowed})
    line = " ".join(argv)
    for pat, risk, why in SENSITIVE_RULES:
        if pat.search(line):
            return risk, why
    return "modere" if prog in ("python3", "swift", "node", "git", "zip", "open", "say") else "faible", "commande autorisée"


def _check_path_args(ctx: ToolContext, argv: List[str]) -> None:
    for a in argv[1:]:
        cand = a.split("=", 1)[1] if a.startswith("-") and "=" in a else a
        if cand.startswith(("/", "~")) or cand.startswith("..") or "/../" in cand:
            if cand.startswith(("http://", "https://")):
                continue
            ctx.app.permissions.resolve_path(cand)


def run_command(ctx: ToolContext, command: str, cwd: Optional[str], timeout_s: int,
                record: bool = True) -> Dict[str, Any]:
    app = ctx.app
    allowed = app.settings.get("shell.allowed_commands", [])
    argv = parse(command)
    try:
        classify(command, allowed)
    except PermissionDenied as e:
        if record:
            app.db.insert("INSERT INTO shell_history(ts, command, cwd, blocked, reason, task_id) VALUES (?,?,?,?,?,?)",
                          (now(), command, cwd, 1, e.message, ctx.task_id))
        raise
    workdir = app.permissions.resolve_path(cwd or str(paths.workspace_dir()), write=True)
    if not workdir.is_dir():
        raise NotFound("Dossier de travail inexistant.", {"cwd": str(workdir)})
    _check_path_args(ctx, argv)
    max_out = app.settings.get("shell.max_output_chars", 20000)
    env = {k: v for k, v in os.environ.items() if not re.search(r"(?i)(key|token|secret|password|anthropic)", k)}
    env["PATH"] = os.environ.get("PATH", "/usr/bin:/bin:/usr/sbin:/sbin") + ":/opt/homebrew/bin:/usr/local/bin"
    env["PWD"] = str(workdir)
    env.pop("OLDPWD", None)
    t0 = time.time()
    proc = subprocess.Popen(argv, cwd=str(workdir), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            stdin=subprocess.DEVNULL, env=env, start_new_session=True)
    out_chunks: List[bytes] = []
    total = 0
    killed = None
    try:
        while True:
            if ctx.cancel_event is not None and ctx.cancel_event.is_set():
                killed = "annulation"
                break
            if time.time() - t0 > timeout_s:
                killed = "délai dépassé"
                break
            try:
                out, _ = proc.communicate(timeout=0.25)
                if out:
                    out_chunks.append(out)
                break
            except subprocess.TimeoutExpired:
                continue
    finally:
        if killed and proc.poll() is None:
            try:
                os.killpg(proc.pid, signal.SIGTERM)
                proc.wait(timeout=3)
            except Exception:  # noqa: BLE001
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except Exception:  # noqa: BLE001
                    pass
            try:
                out, _ = proc.communicate(timeout=2)
                if out:
                    out_chunks.append(out)
            except Exception:  # noqa: BLE001
                pass
    output = b"".join(out_chunks).decode("utf-8", "replace")
    total = len(output)
    truncated = total > max_out
    if truncated:
        output = output[: max_out // 2] + f"\n… [{total - max_out} caractères coupés] …\n" + output[-max_out // 2:]
    ms = int((time.time() - t0) * 1000)
    code = proc.returncode
    if record:
        app.db.insert("INSERT INTO shell_history(ts, command, cwd, exit_code, duration_ms, output_tail, blocked, reason, task_id) "
                      "VALUES (?,?,?,?,?,?,?,?,?)",
                      (now(), command, str(workdir), code, ms, output[-2000:], 0, killed, ctx.task_id))
    res = {"command": command, "cwd": str(workdir), "exit_code": code, "duration_ms": ms, "output": output,
           "truncated": truncated, "stopped": killed}
    if killed == "annulation":
        from ..errors import Cancelled
        raise Cancelled("Commande interrompue (annulation).", res)
    if killed:
        raise JarvisError(f"Commande arrêtée : {killed} ({timeout_s}s).", res, code="delai_depasse")
    return res


def h_exec(ctx, a):
    return run_command(ctx, a["command"], a.get("cwd"), a.get("timeout_s") or ctx.app.settings.get("shell.default_timeout_s", 60))


def v_exec(ctx, a, r):
    if r["exit_code"] == 0:
        return CONFIRME, "code de sortie 0"
    return ECHOUE, f"code de sortie {r['exit_code']}"


def risk_exec(a):
    from ..app import current_app
    try:
        return classify(a["command"], current_app().settings.get("shell.allowed_commands", []))[0]
    except (PermissionDenied, ValidationError):
        return "faible"  # l'exécution lèvera l'erreur avec le motif exact


def detect_test_command(d: Path) -> Optional[str]:
    if (d / "package.json").exists():
        return "npm test --silent"
    if (d / "tests").is_dir() and any((d / "tests").glob("test_*.py")):
        return f"python3 -m unittest discover -s tests -t ."
    if any(d.glob("test_*.py")):
        return "python3 -m unittest discover"
    if (d / "Package.swift").exists():
        return "swift test"
    return None


def h_test(ctx, a):
    d = ctx.app.permissions.resolve_path(a["project_dir"], write=True)
    cmd = a.get("command") or detect_test_command(d)
    if not cmd:
        # Projet statique : contrôle qualité HTML intégré
        from .sites import check_site
        report = check_site(d)
        return {"kind": "controle_site", "passed": report["errors"] == 0, "report": report}
    r = run_command(ctx, cmd, str(d), a.get("timeout_s", 300))
    return {"kind": "commande", "command": cmd, "passed": r["exit_code"] == 0, "exit_code": r["exit_code"],
            "output": r["output"][-6000:]}


def v_test(ctx, a, r):
    return (CONFIRME, "tests passés") if r.get("passed") else (ECHOUE, "tests en échec")


def _free_port(start: int = 8800) -> int:
    for port in range(start, start + 200):
        with socket.socket() as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    raise JarvisError("Aucun port libre.", code="port")


def h_serve(ctx, a):
    d = ctx.app.permissions.resolve_path(a["dir"])
    if not d.is_dir():
        raise NotFound("Dossier inexistant.", {"chemin": str(d)})
    port = a.get("port") or _free_port()
    log = paths.logs_dir() / f"apercu-{port}.log"
    with open(log, "ab") as lf:
        proc = subprocess.Popen([sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1"], cwd=str(d),
                                stdout=lf, stderr=subprocess.STDOUT, start_new_session=True)
    pid_row = ctx.app.db.insert("INSERT INTO processes(pid, kind, command, cwd, port, started_at) VALUES (?,?,?,?,?,?)",
                                (proc.pid, "apercu", f"http.server {port}", str(d), port, now()))
    url = f"http://127.0.0.1:{port}/"
    for _ in range(30):
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                break
        except OSError:
            time.sleep(0.1)
    return {"url": url, "pid": proc.pid, "process_id": pid_row, "dir": str(d), "port": port}


def v_serve(ctx, a, r):
    import urllib.request
    try:
        with urllib.request.urlopen(r["url"], timeout=3) as resp:
            return CONFIRME, f"HTTP {resp.status} sur {r['url']}"
    except Exception as e:  # noqa: BLE001
        return ECHOUE, f"serveur injoignable : {e}"


def h_stop_process(ctx, a):
    row = ctx.app.db.one("SELECT * FROM processes WHERE id=?", (a["process_id"],))
    if not row:
        raise NotFound("Processus JARVIS inconnu.")
    if row["stopped_at"]:
        return {"already_stopped": True, "pid": row["pid"]}
    try:
        os.killpg(row["pid"], signal.SIGTERM)
    except ProcessLookupError:
        pass
    ctx.app.db.execute("UPDATE processes SET stopped_at=? WHERE id=?", (now(), row["id"]))
    return {"stopped": True, "pid": row["pid"]}


def h_processes(ctx, a):
    rows = ctx.app.db.all("SELECT * FROM processes ORDER BY id DESC LIMIT 50")
    for r in rows:
        alive = False
        if not r["stopped_at"]:
            try:
                os.kill(r["pid"], 0)
                alive = True
            except OSError:
                alive = False
        r["alive"] = alive
    return {"processes": rows}


def register(reg) -> None:
    P = lambda **kw: kw  # noqa: E731
    reg.register(Tool("commande_executer",
                      "Exécuter une commande autorisée (sans shell, sans | ; > &&) dans un dossier de travail autorisé.",
                      {"command": P(type="string", required=True, maxLength=2000), "cwd": P(type="string"),
                       "timeout_s": P(type="integer", min=1, max=1800)},
                      h_exec, risk_exec, "terminal", 1900, "liste blanche, délai, sortie limitée",
                      "sortie et code de sortie", "code de sortie", v_exec, reversible=False,
                      describe=lambda a: {"action": f"Exécuter : {a['command']}", "target": a.get("cwd") or "espace de travail",
                                          "consequences": "Commande sensible (voir la règle déclenchée).", "reversible": False}))
    reg.register(Tool("tests_lancer", "Lancer les tests d'un projet (détection automatique, ou contrôle qualité pour un site statique).",
                      {"project_dir": P(type="string", required=True), "command": P(type="string"),
                       "timeout_s": P(type="integer", default=300, min=10, max=1800)},
                      h_test, "modere", "developpement", 1900, verification="résultat des tests", verify=v_test))
    reg.register(Tool("apercu_lancer", "Démarrer un serveur local d'aperçu (127.0.0.1 uniquement) pour un dossier.",
                      {"dir": P(type="string", required=True), "port": P(type="integer", min=1024, max=65000)},
                      h_serve, "modere", "developpement", 20, "écoute locale uniquement", "URL d'aperçu",
                      "requête HTTP sur l'URL", v_serve))
    reg.register(Tool("processus_arreter", "Arrêter un processus démarré par JARVIS (jamais un processus système).",
                      {"process_id": P(type="integer", required=True)}, h_stop_process, "modere", "systeme", 10))
    reg.register(Tool("processus_lister", "Lister les processus démarrés par JARVIS.", {}, h_processes, "faible", "systeme", 10))
