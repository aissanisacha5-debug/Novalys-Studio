"""Registre central des outils.

Chaque outil déclare : identifiant, description, paramètres (schéma
validé), niveau de risque, limites, délai maximum, résultat attendu,
méthode de vérification, annulabilité et disponibilité. L'agent ne
peut appeler qu'un outil enregistré, disponible, avec des arguments
valides, et seulement si les permissions l'autorisent.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

from ..errors import (Cancelled, JarvisError, NotFound, PermissionDenied, ToolUnavailable,
                      ValidationError)
from ..permissions import raise_confirmation

TYPES = {
    "string": str,
    "integer": int,
    "number": (int, float),
    "boolean": bool,
    "array": list,
    "object": dict,
}

# États de résultat (partie 2.3)
CONFIRME, PROBABLE, NON_VERIFIE, BLOQUE, ECHOUE = "confirme", "probable", "non_verifie", "bloque", "echoue"


@dataclass
class ToolContext:
    app: Any
    task_id: Optional[int] = None
    conversation_id: Optional[int] = None
    cancel_event: Optional[threading.Event] = None
    mode: Optional[str] = None
    agent: str = "general"

    def check_cancel(self) -> None:
        if self.cancel_event is not None and self.cancel_event.is_set():
            raise Cancelled("Tâche annulée.")


@dataclass
class Tool:
    id: str
    description: str
    params: Dict[str, Dict[str, Any]]
    handler: Callable[[ToolContext, Dict[str, Any]], Dict[str, Any]]
    risk: Any = "faible"                       # str ou fonction(args) -> str
    category: str = "general"
    timeout_s: int = 60
    limits: str = ""
    expected: str = ""
    verification: str = "aucune"
    verify: Optional[Callable[[ToolContext, Dict[str, Any], Dict[str, Any]], Tuple[str, str]]] = None
    reversible: bool = True
    cancellable: bool = True
    available: Callable[[Any], Tuple[bool, str]] = field(default=lambda app: (True, ""))
    describe: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None
    version: str = "1"

    def risk_for(self, args: Dict[str, Any]) -> str:
        return self.risk(args) if callable(self.risk) else self.risk

    def schema(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "description": self.description,
            "params": self.params,
            "risk": self.risk if isinstance(self.risk, str) else "variable",
            "category": self.category,
            "timeout_s": self.timeout_s,
            "limits": self.limits,
            "expected": self.expected,
            "verification": self.verification,
            "reversible": self.reversible,
            "cancellable": self.cancellable,
            "version": self.version,
        }


def validate_args(tool: Tool, args: Any) -> Dict[str, Any]:
    if args is None:
        args = {}
    if not isinstance(args, dict):
        raise ValidationError("Les arguments doivent être un objet.", {"outil": tool.id})
    unknown = set(args) - set(tool.params)
    if unknown:
        raise ValidationError("Paramètres inconnus.", {"outil": tool.id, "inconnus": sorted(unknown)})
    clean: Dict[str, Any] = {}
    for name, spec in tool.params.items():
        if name not in args or args[name] is None:
            if spec.get("required"):
                raise ValidationError(f"Paramètre obligatoire manquant : {name}.", {"outil": tool.id})
            if "default" in spec:
                clean[name] = spec["default"]
            continue
        v = args[name]
        t = spec.get("type", "string")
        py = TYPES[t]
        if t == "integer" and isinstance(v, bool) or (t in ("integer", "number") and isinstance(v, bool)):
            raise ValidationError(f"{name} doit être un {t}.", {"outil": tool.id})
        if not isinstance(v, py):
            raise ValidationError(f"{name} doit être de type {t}.", {"outil": tool.id, "recu": type(v).__name__})
        if "enum" in spec and v not in spec["enum"]:
            raise ValidationError(f"{name} doit valoir : {', '.join(map(str, spec['enum']))}.", {"outil": tool.id})
        if t == "string" and len(v) > spec.get("maxLength", 200000):
            raise ValidationError(f"{name} est trop long.", {"outil": tool.id})
        if t in ("integer", "number"):
            if "min" in spec and v < spec["min"] or "max" in spec and v > spec["max"]:
                raise ValidationError(f"{name} hors limites [{spec.get('min')}, {spec.get('max')}].", {"outil": tool.id})
        if t == "array" and len(v) > spec.get("maxItems", 1000):
            raise ValidationError(f"{name} contient trop d'éléments.", {"outil": tool.id})
        clean[name] = v
    return clean


class ToolRegistry:
    def __init__(self, app: Any):
        self.app = app
        self._tools: Dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        if tool.id in self._tools:
            raise ValueError(f"Outil déjà enregistré : {tool.id}")
        self._tools[tool.id] = tool

    def get(self, tool_id: str) -> Tool:
        t = self._tools.get(tool_id)
        if not t:
            raise ToolUnavailable(f"L'outil « {tool_id} » n'existe pas.", {"outils": sorted(self._tools)})
        return t

    def ids(self) -> List[str]:
        return sorted(self._tools)

    def listing(self) -> List[Dict[str, Any]]:
        out = []
        for t in sorted(self._tools.values(), key=lambda x: (x.category, x.id)):
            ok, why = t.available(self.app)
            d = t.schema()
            d["available"] = ok
            d["unavailable_reason"] = why
            out.append(d)
        return out

    def for_model(self, allowed: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """Description compacte des outils disponibles, pour le prompt du modèle."""
        out = []
        for t in sorted(self._tools.values(), key=lambda x: x.id):
            if allowed is not None and t.id not in allowed:
                continue
            ok, _ = t.available(self.app)
            if not ok:
                continue
            params = {k: {kk: vv for kk, vv in v.items() if kk in ("type", "required", "description", "enum")}
                      for k, v in t.params.items()}
            out.append({"id": t.id, "description": t.description, "risque": t.risk if isinstance(t.risk, str) else "variable",
                        "params": params})
        return out

    def invoke(self, tool_id: str, args: Any, ctx: ToolContext) -> Dict[str, Any]:
        app = self.app
        tool = self.get(tool_id)
        ok, why = tool.available(app)
        if not ok:
            raise ToolUnavailable(f"Outil « {tool_id} » indisponible : {why}", {"outil": tool_id})
        clean = validate_args(tool, args)
        risk = tool.risk_for(clean)
        decision = app.permissions.check_risk(risk, ctx.mode)
        if decision == "confirmation":
            if not app.permissions.consume_confirmation(tool_id, clean, ctx.task_id):
                describe = {"action": tool.description, "target": None, "consequences": None,
                            "data": None, "reversible": tool.reversible, "expected": tool.expected}
                if tool.describe:
                    describe.update(tool.describe(clean))
                cid = app.permissions.request_confirmation(tool_id, clean, risk, describe, ctx.task_id)
                app.logbook.log("autorisation_demandee", f"Confirmation demandée : {describe['action']}",
                                "attention", ctx.task_id, ctx.conversation_id, tool_id, {"confirmation_id": cid})
                app.notify("confirmation", "Confirmation requise", describe["action"])
                app.bus.publish({"type": "confirmation", "id": cid})
                raise_confirmation(cid, describe)
            app.logbook.log("autorisation_utilisee", "Confirmation acceptée utilisée.", "info",
                            ctx.task_id, ctx.conversation_id, tool_id)
        ctx.check_cancel()
        app.logbook.log("outil_appel", f"Outil {tool_id}", "info", ctx.task_id, ctx.conversation_id, tool_id,
                        {"args": _short(clean)})
        app.bus.publish({"type": "activity", "state": "outil", "tool": tool_id, "task_id": ctx.task_id})
        t0 = time.time()
        result_box: Dict[str, Any] = {}

        def run():
            try:
                result_box["value"] = tool.handler(ctx, clean)
            except BaseException as e:  # noqa: BLE001 - relayée plus bas
                result_box["error"] = e

        th = threading.Thread(target=run, daemon=True, name=f"outil-{tool_id}")
        th.start()
        th.join(tool.timeout_s)
        ms = int((time.time() - t0) * 1000)
        if th.is_alive():
            app.logbook.log("outil_erreur", f"Délai dépassé ({tool.timeout_s}s)", "erreur", ctx.task_id,
                            ctx.conversation_id, tool_id)
            raise JarvisError(f"L'outil {tool_id} a dépassé son délai maximum ({tool.timeout_s}s).",
                              {"outil": tool_id}, code="delai_depasse")
        if ctx.task_id is None:
            app.bus.publish({"type": "activity", "state": "calme"})
        if "error" in result_box:
            e = result_box["error"]
            level = "attention" if isinstance(e, (PermissionDenied, ValidationError, NotFound)) else "erreur"
            app.logbook.log("outil_erreur", f"{tool_id} : {e}", level, ctx.task_id, ctx.conversation_id, tool_id)
            raise e
        result = result_box.get("value") or {}
        state, proof = NON_VERIFIE, ""
        if tool.verify:
            try:
                state, proof = tool.verify(ctx, clean, result)
            except Exception as e:  # noqa: BLE001
                state, proof = NON_VERIFIE, f"vérification impossible : {e}"
        elif result.get("_state"):
            state = result.pop("_state")
            proof = result.get("verification", "")
        out = {"tool": tool_id, "ok": True, "state": state, "verification": proof, "duration_ms": ms, "result": result}
        app.logbook.log("outil_resultat", f"{tool_id} terminé ({state}, {ms} ms)", "succes", ctx.task_id,
                        ctx.conversation_id, tool_id)
        return out


def _short(v: Any, n: int = 300) -> Any:
    if isinstance(v, str):
        return v if len(v) <= n else v[:n] + f"… (+{len(v) - n} car.)"
    if isinstance(v, dict):
        return {k: _short(x, n) for k, x in v.items()}
    if isinstance(v, list):
        return [_short(x, n) for x in v[:20]]
    return v
