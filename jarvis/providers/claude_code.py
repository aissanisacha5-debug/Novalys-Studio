"""Fournisseur « Claude Code » : la CLI officielle `claude -p` (mode non interactif).

Elle utilise la connexion déjà faite sur ce Mac (abonnement Claude, sans clé API).
JARVIS l'emploie comme moteur de langage PUR :
- aucun outil intégré (--tools ""), aucun serveur MCP (--strict-mcp-config),
  aucun réglage utilisateur/projet (--setting-sources ""), aucune session conservée ;
- lancée dans un dossier vide ; les actions passent par le registre d'outils de JARVIS,
  donc par ses permissions.
Le coût affiché par la CLI est un équivalent « tarif API » : avec un abonnement,
il n'est pas facturé à l'appel ; il est noté « inclus_abonnement » (limites d'usage
de l'abonnement applicables).
"""
from __future__ import annotations

import json
import os
import re
import shutil
import signal
import subprocess
import time
from typing import Any, Dict, List, Optional, Tuple

from .. import paths
from ..errors import ProviderError
from .base import Completion, Provider

_STATUS_CACHE: Dict[str, Any] = {}


def claude_bin() -> Optional[str]:
    for c in (shutil.which("claude"), os.path.expanduser("~/.local/bin/claude"), "/opt/homebrew/bin/claude",
              "/usr/local/bin/claude", os.path.expanduser("~/.claude/local/claude")):
        if c and os.path.exists(c):
            return c
    return None


def clean_env() -> Dict[str, str]:
    """Environnement minimal et explicite pour la CLI : rien n'est hérité d'une autre session (variables
    Claude, ANTHROPIC_*, PWD…). PWD hérité d'un dossier protégé (Documents) faisait attendre la CLI sur
    une autorisation macOS : le dossier courant est donc toujours le bac à sable de JARVIS."""
    keep = ("HOME", "USER", "LOGNAME", "TMPDIR", "LANG", "LC_ALL", "SSH_AUTH_SOCK", "__CF_USER_TEXT_ENCODING")
    env = {k: os.environ[k] for k in keep if k in os.environ}
    env["PATH"] = "/usr/bin:/bin:/usr/sbin:/sbin:" + os.path.dirname(claude_bin() or "/usr/bin")
    env["PWD"] = str(paths.data_dir() / "ia-sandbox")
    return env


class ClaudeCodeProvider(Provider):
    id = "claude_code"
    label = "Claude (via Claude Code, abonnement)"
    remote = True
    capabilities = ("conversation", "raisonnement", "code", "resume", "extraction_structuree")

    def available(self) -> Tuple[bool, str]:
        b = claude_bin()
        if not b:
            return False, "CLI « claude » introuvable"
        c = _STATUS_CACHE.get("auth")
        if c and time.time() - c[0] < 300:
            return c[1]
        try:
            out = subprocess.run([b, "auth", "status"], capture_output=True, timeout=20, env=clean_env())
            info = json.loads(out.stdout.decode() or "{}")
            res = (True, f"connecté ({info.get('authMethod', '?')})") if info.get("loggedIn") else (False, "Claude Code non connecté")
        except Exception as e:  # noqa: BLE001
            res = (False, f"vérification impossible : {e}")
        _STATUS_CACHE["auth"] = (time.time(), res)
        return res

    def models(self) -> List[str]:
        return ["sonnet", "haiku", "opus"]

    # -- préchauffage : un processus prêt à recevoir la prochaine demande -------------------
    # La CLI met ~0,5 s à s'initialiser ; en mode « stream-json » elle attend la demande sur son entrée
    # sans limite de temps. Un processus de réserve par configuration (consigne, modèle, schéma) est donc
    # lancé à l'avance : aucune requête n'est envoyée au modèle tant qu'il n'a pas reçu de demande.
    _pool: Dict[str, Tuple[float, Any]] = {}
    _pool_lock = __import__("threading").Lock()
    POOL_TTL = 240

    def _cmd(self, system: str, model: Optional[str], json_schema: Optional[Dict[str, Any]]) -> List[str]:
        cmd = [claude_bin(), "-p", "--tools", "", "--system-prompt", system, "--input-format", "stream-json",
               "--output-format", "stream-json", "--verbose", "--include-partial-messages",
               "--no-session-persistence", "--strict-mcp-config", "--setting-sources", "", "--disable-slash-commands"]
        if model:
            cmd += ["--model", model]
        if json_schema:
            cmd += ["--json-schema", json.dumps(json_schema)]
        return cmd

    def _spawn(self, cmd: List[str]):
        sandbox = paths.data_dir() / "ia-sandbox"
        sandbox.mkdir(exist_ok=True)
        return subprocess.Popen(cmd, cwd=str(sandbox), stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                env=clean_env(), start_new_session=True)

    def _take(self, key: str, cmd: List[str]):
        with self._pool_lock:
            item = self._pool.pop(key, None)
        if item:
            ts, proc = item
            if proc.poll() is None and time.time() - ts < self.POOL_TTL:
                return proc, True
            self._kill(proc)
        return self._spawn(cmd), False

    def _prewarm(self, key: str, cmd: List[str]) -> None:
        if not self.app.settings.get("ai.prewarm", True):
            return
        with self._pool_lock:
            for k, (ts, proc) in list(self._pool.items()):       # une seule réserve à la fois
                self._pool.pop(k)
                self._kill(proc)
            self._pool[key] = (time.time(), self._spawn(cmd))

    @classmethod
    def shutdown_pool(cls) -> None:
        with cls._pool_lock:
            for k, (ts, proc) in list(cls._pool.items()):
                cls._pool.pop(k)
                cls._kill(proc)

    def complete(self, system: str, prompt: str, model: Optional[str] = None, json_schema: Optional[Dict[str, Any]] = None,
                 timeout_s: int = 180, cancel_event=None, on_partial=None) -> Completion:
        """Appel en flux (stream-json) : `on_partial(texte_partiel)` reçoit la réponse au fur et à mesure
        (réel : fragments envoyés par le fournisseur, jamais simulés)."""
        import hashlib
        import queue as _queue
        import threading as _th
        if not claude_bin():
            raise ProviderError("CLI claude introuvable.")
        cmd = self._cmd(system, model, json_schema)
        key = hashlib.sha1("\x00".join(cmd).encode()).hexdigest()
        proc, warm = self._take(key, cmd)
        t0 = time.time()
        lines: "_queue.Queue" = _queue.Queue()

        def reader():
            for line in proc.stdout:
                lines.put(line)
            lines.put(None)

        _th.Thread(target=reader, daemon=True).start()
        try:
            proc.stdin.write((json.dumps({"type": "user", "message": {"role": "user", "content": prompt}}) + "\n").encode("utf-8"))
            proc.stdin.flush()
        except BrokenPipeError:
            pass
        partial, first_ms, result = "", None, None
        while True:
            if cancel_event is not None and cancel_event.is_set():
                self._kill(proc)
                raise ProviderError("Appel au modèle annulé.", code="annule")
            if time.time() - t0 > timeout_s:
                self._kill(proc)
                raise ProviderError(f"Le modèle n'a pas répondu en {timeout_s}s.", code="delai_depasse")
            try:
                line = lines.get(timeout=0.1)
            except _queue.Empty:
                continue
            if line is None:
                break
            try:
                d = json.loads(line)
            except ValueError:
                continue
            if d.get("type") == "stream_event":
                delta = (d.get("event") or {}).get("delta") or {}
                piece = delta.get("partial_json") if delta.get("type") == "input_json_delta" else (
                    delta.get("text") if delta.get("type") == "text_delta" else None)
                if piece:
                    if first_ms is None:
                        first_ms = int((time.time() - t0) * 1000)
                    partial += piece
                    if on_partial:
                        try:
                            on_partial(partial)
                        except Exception:  # noqa: BLE001 - un consommateur fautif n'interrompt pas l'appel
                            pass
            elif d.get("type") == "result":
                result = d
                break
        try:
            proc.stdin.close()
        except Exception:  # noqa: BLE001
            pass
        __import__("threading").Thread(target=lambda: (proc.wait(timeout=15) if proc.poll() is None else None), daemon=True).start()
        __import__("threading").Thread(target=self._prewarm, args=(key, cmd), daemon=True).start()
        if not result:
            err = proc.stderr.read().decode("utf-8", "replace") if proc.poll() is not None else ""
            raise ProviderError("Réponse illisible de Claude Code.", {"stderr": err[-400:]})
        d = result
        msg = str(d.get("result") or "")
        if d.get("is_error") and re.search(r"(?i)(session|usage|weekly|rate) limit|limite", msg):
            reset = re.search(r"(?i)resets?\s+([^·\n]+)", msg)
            raise ProviderError("Limite d'usage de l'abonnement Claude atteinte" + (f" (réinitialisation : {reset.group(1).strip()})" if reset else "")
                                + ". Attendez la réinitialisation ou choisissez un autre fournisseur dans Modèles IA.",
                                {"reset": reset.group(1).strip() if reset else None}, code="limite_usage")
        if d.get("is_error") or d.get("subtype") not in (None, "success"):
            raise ProviderError(f"Claude Code a renvoyé une erreur : {str(d.get('result') or d.get('subtype'))[:300]}",
                                {"subtype": d.get("subtype")})
        usage = d.get("usage") or {}
        used_model = next(iter((d.get("modelUsage") or {}).keys()), model or "")
        return Completion(
            text=d.get("result") or "",
            data=d.get("structured_output"),
            model=used_model,
            provider=self.id,
            input_tokens=(usage.get("input_tokens") or 0) + (usage.get("cache_read_input_tokens") or 0)
            + (usage.get("cache_creation_input_tokens") or 0),
            output_tokens=usage.get("output_tokens"),
            cost_usd=d.get("total_cost_usd"),
            cost_kind="inclus_abonnement",
            raw={"duration_api_ms": d.get("duration_api_ms"), "first_fragment_ms": first_ms, "prewarmed": warm, "streamed": True},
        )

    @staticmethod
    def _kill(proc) -> None:
        try:
            os.killpg(proc.pid, signal.SIGTERM)
            proc.wait(timeout=3)
        except Exception:  # noqa: BLE001
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except Exception:  # noqa: BLE001
                pass
