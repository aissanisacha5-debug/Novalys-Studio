"""Autres fournisseurs : Ollama (local, gratuit) et API Anthropic (clé requise, payante).

Ils sont réellement implémentés mais déclarés indisponibles tant que leurs
conditions ne sont pas remplies (Ollama non installé / aucune clé dans le trousseau).
Aucun modèle local n'est lancé automatiquement.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any, Dict, List, Tuple

from ..errors import ProviderError
from .base import Completion, Provider

OLLAMA = "http://127.0.0.1:11434"


class OllamaProvider(Provider):
    id = "ollama"
    label = "Ollama (modèles locaux)"
    remote = False
    capabilities = ("conversation", "resume", "embeddings")

    def _get(self, path: str, timeout: float = 1.5) -> Dict[str, Any]:
        with urllib.request.urlopen(OLLAMA + path, timeout=timeout) as r:
            return json.loads(r.read().decode())

    def available(self) -> Tuple[bool, str]:
        try:
            tags = self._get("/api/tags")
        except Exception:  # noqa: BLE001
            return False, "Ollama n'est pas installé ou pas démarré (http://127.0.0.1:11434)"
        if not tags.get("models"):
            return False, "Ollama démarré mais aucun modèle téléchargé"
        return True, f"{len(tags['models'])} modèle(s) local(aux)"

    def models(self) -> List[str]:
        try:
            return [m["name"] for m in self._get("/api/tags").get("models", [])]
        except Exception:  # noqa: BLE001
            return []

    def complete(self, system, prompt, model=None, json_schema=None, timeout_s=180, cancel_event=None) -> Completion:
        body: Dict[str, Any] = {"model": model if model in self.models() else (self.models() or [""])[0],
                                "system": system, "prompt": prompt, "stream": False}
        if json_schema:
            body["format"] = json_schema
        req = urllib.request.Request(OLLAMA + "/api/generate", data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=timeout_s) as r:
                d = json.loads(r.read().decode())
        except Exception as e:  # noqa: BLE001
            raise ProviderError(f"Ollama : {e}")
        text = d.get("response", "")
        data = None
        if json_schema:
            try:
                data = json.loads(text)
            except ValueError:
                raise ProviderError("Ollama n'a pas renvoyé de JSON valide.")
        return Completion(text, data, body["model"], self.id, d.get("prompt_eval_count"), d.get("eval_count"), 0.0, "gratuit_local")


class AnthropicAPIProvider(Provider):
    """API Anthropic officielle. Clé lue dans le trousseau macOS (jamais en clair)."""
    id = "anthropic_api"
    label = "API Anthropic (clé personnelle, facturée)"
    remote = True
    capabilities = ("conversation", "raisonnement", "code", "resume", "vision", "extraction_structuree")
    # Tarifs non codés en dur : à renseigner dans Paramètres (ai.prices = {modèle: [entrée, sortie] $/million}).
    MODELS = ["claude-sonnet-5-5", "claude-haiku-5-5", "claude-opus-5-5"]

    def available(self) -> Tuple[bool, str]:
        if not self.app.secrets.has("anthropic_api_key"):
            return False, "aucune clé API enregistrée dans le trousseau (Paramètres > Modèles IA)"
        return True, "clé présente dans le trousseau"

    def models(self) -> List[str]:
        return list(self.MODELS)

    def complete(self, system, prompt, model=None, json_schema=None, timeout_s=180, cancel_event=None) -> Completion:
        key = self.app.secrets.get("anthropic_api_key")
        if not key:
            raise ProviderError("Clé API absente.")
        model = model if model in self.MODELS else "claude-sonnet-5-5"
        sys_prompt = system
        if json_schema:
            sys_prompt += "\n\nRéponds UNIQUEMENT avec un objet JSON valide respectant ce schéma :\n" + json.dumps(json_schema)
        body = {"model": model, "max_tokens": 4096, "system": sys_prompt, "messages": [{"role": "user", "content": prompt}]}
        req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=json.dumps(body).encode(),
                                     headers={"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=timeout_s) as r:
                d = json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            raise provider_http_error("API Anthropic", e)
        except Exception as e:  # noqa: BLE001
            raise ProviderError(f"API Anthropic injoignable : {e}")
        text = "".join(b.get("text", "") for b in d.get("content", []) if b.get("type") == "text")
        u = d.get("usage", {})
        prices = (self.app.settings.get("ai.prices") or {}).get(model)
        cost = (u.get("input_tokens", 0) * prices[0] + u.get("output_tokens", 0) * prices[1]) / 1e6 if prices else None
        data = None
        if json_schema:
            try:
                start, end = text.find("{"), text.rfind("}")
                data = json.loads(text[start:end + 1])
            except ValueError:
                raise ProviderError("Réponse JSON invalide.")
        return Completion(text, data, model, self.id, u.get("input_tokens"), u.get("output_tokens"),
                          round(cost, 6) if cost is not None else None, "estimation" if cost is not None else "inconnu")


class OpenAICompatibleProvider(Provider):
    """Tout service exposant l'API « chat completions » (OpenAI, Mistral, Groq, LM Studio, Ollama /v1…).
    Configuration : ai.openai_compatible = {base_url, model, label} ; clé facultative dans le trousseau
    (« openai_compatible_key »). Indisponible tant que l'adresse n'est pas configurée."""
    id = "openai_compatible"
    label = "Compatible OpenAI (configurable)"
    remote = True
    capabilities = ("conversation", "resume", "extraction_structuree")

    def cfg(self) -> Dict[str, Any]:
        return self.app.settings.get("ai.openai_compatible") or {}

    def available(self) -> Tuple[bool, str]:
        c = self.cfg()
        if not c.get("base_url") or not c.get("model"):
            return False, "non configuré (adresse et modèle à renseigner dans Modèles IA)"
        local = c["base_url"].startswith(("http://127.0.0.1", "http://localhost"))
        if not local and not self.app.secrets.has("openai_compatible_key"):
            return False, "clé absente dans le trousseau (Sécurité > Secrets)"
        return True, f"{c.get('label') or c['base_url']} · {c['model']}"

    def models(self) -> List[str]:
        m = self.cfg().get("model")
        return [m] if m else []

    def complete(self, system, prompt, model=None, json_schema=None, timeout_s=180, cancel_event=None) -> Completion:
        c = self.cfg()
        model = model if model and model in self.models() else c.get("model")
        sys_prompt = system + ("\n\nRéponds UNIQUEMENT avec un objet JSON valide respectant ce schéma :\n" + json.dumps(json_schema) if json_schema else "")
        body: Dict[str, Any] = {"model": model, "messages": [{"role": "system", "content": sys_prompt}, {"role": "user", "content": prompt}],
                                "temperature": 0.2}
        if json_schema:
            body["response_format"] = {"type": "json_object"}
        headers = {"Content-Type": "application/json"}
        key = self.app.secrets.get("openai_compatible_key") if self.app.secrets.has("openai_compatible_key") else None
        if key:
            headers["Authorization"] = "Bearer " + key
        url = c["base_url"].rstrip("/") + "/chat/completions"
        req = urllib.request.Request(url, data=json.dumps(body).encode(), headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=timeout_s) as r:
                d = json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            raise provider_http_error("Fournisseur compatible OpenAI", e)
        except Exception as e:  # noqa: BLE001
            raise ProviderError(f"Fournisseur compatible OpenAI injoignable : {e}")
        text = ((d.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
        data = None
        if json_schema:
            try:
                start, end = text.find("{"), text.rfind("}")
                data = json.loads(text[start:end + 1])
            except ValueError:
                raise ProviderError("Réponse JSON invalide du fournisseur.")
        u = d.get("usage") or {}
        local = c["base_url"].startswith(("http://127.0.0.1", "http://localhost"))
        return Completion(text, data, model, self.id, u.get("prompt_tokens"), u.get("completion_tokens"),
                          0.0 if local else None, "gratuit_local" if local else "inconnu")


def provider_http_error(label: str, e) -> ProviderError:
    """Erreurs HTTP normalisées : authentification, limite de débit, indisponibilité."""
    if e.code in (401, 403):
        return ProviderError(f"{label} : authentification refusée (clé invalide ou expirée).", {"status": e.code},
                             code="echec_authentification")
    if e.code == 429:
        retry = e.headers.get("Retry-After") if getattr(e, "headers", None) else None
        return ProviderError(f"{label} : limite de débit atteinte" + (f", réessayer dans {retry} s." if retry else "."),
                             {"status": 429, "retry_after": retry}, code="limite_debit")
    if e.code >= 500:
        return ProviderError(f"{label} : service momentanément indisponible (HTTP {e.code}).", {"status": e.code},
                             code="fournisseur_indisponible")
    return ProviderError(f"{label} : HTTP {e.code}", {"status": e.code})
