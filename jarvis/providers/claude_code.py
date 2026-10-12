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
    env = {k: v for k, v in os.environ.items() if not k.startswith("ANTHROPIC_") and not k.startswith("CLAUDE_CODE_")
           and k not in ("CLAUDECODE",)}
    env["PATH"] = env.get("PATH", "/usr/bin:/bin") + ":" + os.path.dirname(claude_bin() or "/usr/bin")
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

    def complete(self, system: str, prompt: str, model: Optional[str] = None, json_schema: Optional[Dict[str, Any]] = None,
                 timeout_s: int = 180, cancel_event=None) -> Completion:
        b = claude_bin()
        if not b:
            raise ProviderError("CLI claude introuvable.")
        sandbox = paths.data_dir() / "ia-sandbox"
        sandbox.mkdir(exist_ok=True)
        cmd = [b, "-p", "--tools", "", "--system-prompt", system, "--output-format", "json",
               "--no-session-persistence", "--strict-mcp-config", "--setting-sources", "",
               "--disable-slash-commands"]
        if model:
            cmd += ["--model", model]
        if json_schema:
            cmd += ["--json-schema", json.dumps(json_schema)]
        proc = subprocess.Popen(cmd, cwd=str(sandbox), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, env=clean_env(), start_new_session=True)
        t0 = time.time()
        payload: Optional[bytes] = prompt.encode("utf-8")
        while True:
            if cancel_event is not None and cancel_event.is_set():
                self._kill(proc)
                raise ProviderError("Appel au modèle annulé.", code="annule")
            if time.time() - t0 > timeout_s:
                self._kill(proc)
                raise ProviderError(f"Le modèle n'a pas répondu en {timeout_s}s.", code="delai_depasse")
            try:
                # communicate() lit en continu (pas de blocage si la réponse dépasse le tampon du tube)
                out_b, err_b = proc.communicate(input=payload, timeout=0.2)
                break
            except subprocess.TimeoutExpired:
                payload = None
        out, err = out_b.decode("utf-8", "replace"), err_b.decode("utf-8", "replace")
        try:
            d = json.loads(out)
        except ValueError:
            raise ProviderError("Réponse illisible de Claude Code.", {"stderr": err[-400:], "stdout": out[-400:]})
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
            raw={"duration_api_ms": d.get("duration_api_ms")},
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
