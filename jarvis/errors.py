"""Erreurs structurées : chaque erreur a un code stable, un message lisible
en français et des détails optionnels, et se sérialise en JSON."""
from __future__ import annotations

from typing import Any, Dict, Optional


class JarvisError(Exception):
    code = "erreur"
    http_status = 400

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None, code: Optional[str] = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}
        if code:
            self.code = code

    def to_dict(self) -> Dict[str, Any]:
        return {"code": self.code, "message": self.message, "details": self.details}


class ValidationError(JarvisError):
    code = "parametres_invalides"


class NotFound(JarvisError):
    code = "introuvable"
    http_status = 404


class PermissionDenied(JarvisError):
    code = "permission_refusee"
    http_status = 403


class ConfirmationRequired(JarvisError):
    """L'action est autorisée seulement après une confirmation explicite."""
    code = "confirmation_requise"
    http_status = 409


class ToolUnavailable(JarvisError):
    code = "outil_indisponible"
    http_status = 503


class ProviderError(JarvisError):
    code = "fournisseur_ia_erreur"
    http_status = 502


class LimitReached(JarvisError):
    code = "limite_atteinte"
    http_status = 429


class Cancelled(JarvisError):
    code = "annule"
