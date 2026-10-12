"""Couche fournisseurs IA indépendante (partie 21).

Un fournisseur expose : disponibilité vérifiée, appel avec délai maximum,
sortie JSON structurée optionnelle, usage (jetons, coût et nature du coût).
Les coûts sont classés : reel / estimation / inclus_abonnement / gratuit_local / inconnu.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from ..db import now
from ..errors import LimitReached, ProviderError


@dataclass
class Completion:
    text: str
    data: Optional[Dict[str, Any]] = None
    model: str = ""
    provider: str = ""
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    cost_usd: Optional[float] = None
    cost_kind: str = "inconnu"
    duration_ms: int = 0
    raw: Dict[str, Any] = field(default_factory=dict)


class Provider:
    id = "base"
    label = "Fournisseur"
    remote = True
    capabilities: Tuple[str, ...] = ()

    def __init__(self, app):
        self.app = app

    def available(self) -> Tuple[bool, str]:
        return False, "non implémenté"

    def models(self) -> List[str]:
        return []

    def complete(self, system: str, prompt: str, model: Optional[str] = None, json_schema: Optional[Dict[str, Any]] = None,
                 timeout_s: int = 120, cancel_event=None) -> Completion:
        raise NotImplementedError


class ProviderManager:
    def __init__(self, app):
        self.app = app
        self.providers: Dict[str, Provider] = {}

    def register(self, p: Provider) -> None:
        self.providers[p.id] = p

    def status(self) -> List[Dict[str, Any]]:
        out = []
        for p in self.providers.values():
            ok, why = p.available()
            out.append({"id": p.id, "label": p.label, "available": ok, "reason": why, "remote": p.remote,
                        "models": p.models() if ok else [], "capabilities": list(p.capabilities),
                        "active": self.app.settings.get("ai.provider") == p.id})
        return out

    def _check_budget(self) -> None:
        s = self.app.settings
        day = time.strftime("%Y-%m-%d")
        calls = self.app.db.one("SELECT count(*) AS n FROM ai_usage WHERE ts LIKE ?", (day + "%",))["n"]
        max_calls = s.get("budget.max_calls_per_day", 300)
        if max_calls and calls >= max_calls and s.get("budget.stop_on_exceed", True):
            raise LimitReached(f"Limite quotidienne d'appels IA atteinte ({max_calls}).", {"appels": calls})
        daily = s.get("budget.daily_usd", 0) or 0
        if daily > 0:
            spent = self.app.db.one("SELECT coalesce(sum(cost_usd),0) AS c FROM ai_usage WHERE ts LIKE ? AND cost_kind IN ('reel','estimation')",
                                    (day + "%",))["c"]
            if spent >= daily and s.get("budget.stop_on_exceed", True):
                raise LimitReached(f"Budget quotidien atteint ({spent:.2f} / {daily:.2f} $).")
        monthly = s.get("budget.monthly_usd", 0) or 0
        if monthly > 0:
            spent = self.app.db.one("SELECT coalesce(sum(cost_usd),0) AS c FROM ai_usage WHERE ts LIKE ? AND cost_kind IN ('reel','estimation')",
                                    (day[:7] + "%",))["c"]
            if spent >= monthly and s.get("budget.stop_on_exceed", True):
                raise LimitReached(f"Budget mensuel atteint ({spent:.2f} / {monthly:.2f} $).")

    def complete(self, system: str, prompt: str, json_schema: Optional[Dict[str, Any]] = None, task_id: Optional[int] = None,
                 cancel_event=None, model: Optional[str] = None) -> Completion:
        s = self.app.settings
        pid = s.get("ai.provider", "claude_code")
        p = self.providers.get(pid)
        if not p:
            raise ProviderError(f"Fournisseur IA inconnu : {pid}.")
        ok, why = p.available()
        if not ok:
            raise ProviderError(f"Fournisseur IA « {p.label} » indisponible : {why}", {"provider": pid}, code="fournisseur_indisponible")
        self._check_budget()
        models = [model or s.get("ai.model")]
        fb = s.get("ai.fallback_model")
        if fb and fb not in models:
            models.append(fb)
        last_err: Optional[Exception] = None
        for m in models:
            t0 = time.time()
            try:
                c = p.complete(system, prompt, m, json_schema, s.get("ai.timeout_s", 180), cancel_event)
                c.duration_ms = int((time.time() - t0) * 1000)
                self._record(c, task_id, True)
                return c
            except ProviderError as e:
                last_err = e
                self._record(Completion("", provider=p.id, model=m or "", duration_ms=int((time.time() - t0) * 1000)), task_id, False)
                if e.code in ("annule", "delai_depasse"):
                    break
                self.app.logbook.log("ia", f"Échec du modèle {m} : {e.message} — essai du modèle de remplacement", "attention", task_id)
        raise last_err or ProviderError("Aucune réponse du fournisseur.")

    def _record(self, c: Completion, task_id: Optional[int], ok: bool) -> None:
        self.app.db.insert(
            "INSERT INTO ai_usage(ts, provider, model, task_id, input_tokens, output_tokens, cost_usd, cost_kind, duration_ms, ok) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            (now(), c.provider, c.model, task_id, c.input_tokens, c.output_tokens, c.cost_usd, c.cost_kind, c.duration_ms, 1 if ok else 0))
