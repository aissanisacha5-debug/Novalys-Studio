"""Outils de test : application isolée (dossiers temporaires, données fictives) et fournisseur IA scripté.

Le fournisseur scripté ne sert QU'AUX TESTS : il rejoue des réponses JSON prévues
pour vérifier le moteur (outils, permissions, confirmations, annulation…) sans
appeler de service réel. L'application livrée n'enregistre jamais ce fournisseur.
"""
from __future__ import annotations

import json
import os
import shutil
import tempfile
import threading
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union

from jarvis.providers.base import Completion, Provider


class ScriptedProvider(Provider):
    id = "test_scripte"
    label = "Fournisseur scripté (tests)"
    remote = False

    def __init__(self, app, script: Union[List[Dict[str, Any]], Callable[[str, str], Dict[str, Any]]]):
        super().__init__(app)
        self.script = script
        self.prompts: List[str] = []
        self.systems: List[str] = []
        self.delay = 0.0

    def available(self):
        return True, "tests"

    def models(self):
        return ["scripte"]

    def complete(self, system, prompt, model=None, json_schema=None, timeout_s=60, cancel_event=None):
        self.prompts.append(prompt)
        self.systems.append(system)
        if self.delay:
            end = time.time() + self.delay
            while time.time() < end:
                if cancel_event is not None and cancel_event.is_set():
                    from jarvis.errors import ProviderError
                    raise ProviderError("annulé", code="annule")
                time.sleep(0.02)
        if callable(self.script):
            data = self.script(system, prompt)
        else:
            idx = min(len(self.prompts) - 1, len(self.script) - 1)
            data = self.script[idx]
        return Completion(json.dumps(data), data, "scripte", self.id, 10, 10, 0.0, "gratuit_local")


class TestEnv:
    def __init__(self):
        self.root = Path(tempfile.mkdtemp(prefix="jarvis-test-"))
        self.data = self.root / "data"
        self.ws = self.root / "workspace"
        self.outside = self.root / "dehors"
        self.outside.mkdir(parents=True)
        os.environ["JARVIS_DATA_DIR"] = str(self.data)
        os.environ["JARVIS_WORKSPACE"] = str(self.ws)
        self.app = None

    def make_app(self, script=None):
        from jarvis.app import JarvisApp
        self.app = JarvisApp(port=0, start_background=False)
        if script is not None:
            self.use_script(script)
        return self.app

    def use_script(self, script):
        p = ScriptedProvider(self.app, script)
        self.app.providers.register(p)
        self.app.settings.update({"ai": {"provider": p.id, "fallback_model": None}}, "tests")
        self.provider = p
        return p

    def wait_task(self, tid: int, states=("terminee", "echouee", "bloquee", "annulee", "attente_autorisation", "attente_reponse", "pause"),
                  timeout: float = 20) -> Dict[str, Any]:
        end = time.time() + timeout
        while time.time() < end:
            t = self.app.tasks.get(tid)
            if t["status"] in states and tid not in self.app.tasks.running():
                return t
            time.sleep(0.05)
        raise AssertionError(f"tâche {tid} toujours « {self.app.tasks.get(tid)['status']} »")

    def close(self):
        if self.app:
            for tid in self.app.tasks.running():
                self.app.tasks._cancel[tid].set()
            time.sleep(0.1)
            self.app.shutdown()
            self.app.db.close()
        shutil.rmtree(self.root, ignore_errors=True)


def say(message: str, actions: Optional[List[Dict[str, Any]]] = None, status: str = None, state: str = "confirme") -> Dict[str, Any]:
    actions = actions or []
    return {"message": message, "actions": actions, "status": status or ("continuer" if actions else "termine"), "result_state": state}


def act(tool: str, **args) -> Dict[str, Any]:
    return {"tool": tool, "args": args}
