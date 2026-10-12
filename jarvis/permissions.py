"""Système de permissions (contrôlé côté backend).

Trois couches, toutes vérifiées avant chaque appel d'outil :
1. Le mode de fonctionnement fixe le niveau de risque maximal permis.
2. Les chemins doivent être dans un dossier autorisé (lecture ou
   lecture/écriture) et hors des zones protégées.
3. Les actions à risque élevé exigent une confirmation à usage unique,
   liée à l'outil ET aux arguments exacts (hash).

Les agents n'ont aucun outil pour modifier ces règles.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from . import paths
from .db import Database, dumps, loads, now
from .errors import ConfirmationRequired, JarvisError, PermissionDenied, ValidationError

RISKS = ("faible", "modere", "eleve")
ACTION_MODES = ("execution_supervisee", "vocal", "autonomie_limitee", "developpement")
LEVELS = {
    "assiste": "Assisté : JARVIS lit et cherche seul ; il propose et attend votre accord pour toute modification.",
    "prudent": "Prudent : modifications locales réversibles automatiques ; accord pour toute action à risque élevé.",
    "locale": "Autonomie locale : en plus, les suppressions récupérables (corbeille JARVIS) dans vos dossiers autorisés sont automatiques.",
    "avancee": "Autonomie avancée : comme l'autonomie locale, avec des enchaînements plus longs (30 tours, 3 nouvelles tentatives).",
}
# Outils pour lesquels une autorisation préalable (« ne plus demander ») est possible, limitée à un périmètre.
POLICY_TOOLS = {"fichier_supprimer", "commande_executer"}
INTERPRETERS = {"python3", "python", "node", "npx", "npm", "swift", "sh", "bash", "zsh", "env", "xargs", "osascript", "perl", "ruby"}

# Niveau de risque autorisé par mode : (autorisé sans confirmation, autorisé avec confirmation)
MODE_POLICY: Dict[str, Tuple[Tuple[str, ...], Tuple[str, ...]]] = {
    "conversation": ((), ()),
    "assistance": (("faible",), ()),
    "maintenance": (("faible",), ()),
    "execution_supervisee": (("faible", "modere"), ("eleve",)),
    "vocal": (("faible", "modere"), ("eleve",)),
    "autonomie_limitee": (("faible", "modere"), ("eleve",)),
    "developpement": (("faible", "modere"), ("eleve",)),
}

HOME = Path.home()

# Zones jamais accessibles (lecture comprise), quel que soit le réglage.
FORBIDDEN_PREFIXES = [
    HOME / "Library" / "Keychains",
    HOME / ".ssh",
    HOME / ".gnupg",
    HOME / ".aws",
    HOME / ".config" / "gcloud",
    HOME / "Library" / "Cookies",
    HOME / "Library" / "Application Support" / "Google" / "Chrome",
    HOME / "Library" / "Safari",
    HOME / "Library" / "Mail",
    HOME / "Library" / "Messages",
    HOME / ".claude",
    Path("/System"),
    Path("/private/etc"),
    Path("/etc"),
    Path("/usr"),
    Path("/bin"),
    Path("/sbin"),
    Path("/Library/Keychains"),
]

FORBIDDEN_NAMES = {".env", "id_rsa", "id_ed25519", "credentials", "credentials.json", "token", ".netrc", ".npmrc", ".pypirc"}
FORBIDDEN_SUFFIXES = (".pem", ".key", ".p12", ".keychain", ".keychain-db", ".kdbx")


def _write_protected() -> List[Path]:
    """Zones lisibles mais jamais modifiables par l'agent."""
    return [
        paths.ROOT / "jarvis",          # le code de JARVIS (dont ce fichier)
        paths.ROOT / "web",
        paths.ROOT / "tests",
        paths.data_dir(),               # base, jeton, sauvegardes
        paths.CYPHER_DIR / "memoire",   # mémoire CYPHER : modifiée seulement par Sacha
        paths.CYPHER_DIR / ".claude",
        paths.CYPHER_DIR / "app" / "evaluateur",
        paths.CYPHER_DIR / "CLAUDE.md",
        paths.CYPHER_DIR / "ETAT.md",
    ]


def _is_within(p: Path, base: Path) -> bool:
    try:
        p.relative_to(base)
        return True
    except ValueError:
        return False


def args_hash(tool: str, args: Dict[str, Any]) -> str:
    raw = tool + "|" + json.dumps(args, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class Permissions:
    def __init__(self, db: Database, settings):
        self.db = db
        self.settings = settings

    # -- mode ---------------------------------------------------------------
    def mode(self) -> str:
        return self.settings.get("autonomy.mode", "execution_supervisee")

    def level(self) -> str:
        return self.settings.get("autonomy.level", "locale")

    def check_risk(self, risk: str, mode: Optional[str] = None, tool: Any = None, args: Optional[Dict[str, Any]] = None) -> str:
        """Retourne 'ok' ou 'confirmation' ; lève PermissionDenied si le mode l'interdit.
        Le niveau d'autonomie ajuste les modes d'action : assisté (confirmation dès le risque modéré), prudent
        (confirmation au risque élevé), autonomie locale et avancée (les suppressions locales récupérables
        dans un dossier autorisé en écriture sont automatiques ; tout le reste du risque élevé reste confirmé)."""
        mode = mode or self.mode()
        free, confirm = MODE_POLICY.get(mode, ((), ()))
        if mode in ACTION_MODES:
            lvl = self.level()
            if lvl == "assiste":
                free, confirm = ("faible",), ("modere", "eleve")
            elif risk == "eleve" and lvl in ("locale", "avancee") and tool is not None and getattr(tool, "local_reversible", None):
                lr = tool.local_reversible
                try:
                    if (lr(self, args or {}) if callable(lr) else bool(lr)):
                        return "ok"
                except JarvisError:
                    pass
        if risk == "modere" and self.settings.get("confirmations.moderate_needs_confirmation") and risk in free:
            return "confirmation"
        if risk in free:
            return "ok"
        if risk in confirm:
            return "confirmation"
        raise PermissionDenied(
            f"Le mode « {mode} » n'autorise pas les actions à risque {risk}.",
            {"mode": mode, "risque": risk},
        )

    # -- chemins -------------------------------------------------------------
    def allowed_dirs(self) -> List[Dict[str, Any]]:
        return self.settings.get("allowed_dirs", []) or []

    def resolve_path(self, raw: str, write: bool = False) -> Path:
        if not isinstance(raw, str) or not raw.strip():
            raise ValidationError("Chemin vide.")
        raw = os.path.expanduser(raw.strip())
        p = Path(raw)
        if not p.is_absolute():
            p = paths.workspace_dir() / p
        # realpath : neutralise « .. » et les liens symboliques qui sortiraient du périmètre
        real = Path(os.path.realpath(str(p)))
        self._check_forbidden(real)
        mode_needed = "rw" if write else "r"
        for d in self.allowed_dirs():
            base = Path(os.path.realpath(d["path"]))
            if _is_within(real, base):
                if mode_needed == "rw" and d.get("mode") != "rw":
                    continue
                if write:
                    for wp in _write_protected():
                        wpr = Path(os.path.realpath(str(wp)))
                        if real == wpr or _is_within(real, wpr):
                            raise PermissionDenied(
                                "Zone protégée en écriture.", {"chemin": str(real), "zone": str(wpr)}
                            )
                return real
        raise PermissionDenied(
            "Chemin hors des dossiers autorisés" + (" en écriture." if write else "."),
            {"chemin": str(real), "dossiers": [d["path"] for d in self.allowed_dirs()]},
        )

    def _check_forbidden(self, real: Path) -> None:
        # data/ contient la base, le jeton d'accès et les sauvegardes : jamais lisible par un outil.
        for fp in FORBIDDEN_PREFIXES + [Path(os.path.realpath(str(paths.data_dir())))]:
            if real == fp or _is_within(real, fp):
                raise PermissionDenied("Zone système ou secrète interdite.", {"chemin": str(real)})
        name = real.name.lower()
        if name in FORBIDDEN_NAMES or name.endswith(FORBIDDEN_SUFFIXES) or name.startswith(".env"):
            raise PermissionDenied("Fichier de secrets interdit.", {"chemin": str(real)})

    # -- confirmations ---------------------------------------------------------
    def request_confirmation(self, tool: str, args: Dict[str, Any], risk: str, describe: Dict[str, Any],
                             task_id: Optional[int] = None) -> int:
        h = args_hash(tool, args)
        existing = self.db.one(
            "SELECT id FROM confirmations WHERE tool=? AND args_hash=? AND status='en_attente' AND "
            "(task_id IS ? OR task_id=?)", (tool, h, task_id, task_id))
        if existing:
            return existing["id"]
        return self.db.insert(
            "INSERT INTO confirmations(task_id, tool, args, args_hash, action, target, consequences, data_concerned, "
            "reversible, expected, risk, status, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?, 'en_attente', ?)",
            (task_id, tool, dumps(args), h, describe.get("action", tool), describe.get("target"),
             describe.get("consequences"), describe.get("data"), 1 if describe.get("reversible") else 0,
             describe.get("expected"), risk, now()),
        )

    # -- autorisations préalables (périmètre précis, révocables) -----------------------------
    def policies(self) -> List[Dict[str, Any]]:
        return list(self.settings.get("policies") or [])

    def _scope_for(self, tool: str, args: Dict[str, Any]) -> Optional[str]:
        if tool == "fichier_supprimer" and args.get("path"):
            return str(self.resolve_path(args["path"], write=True).parent)
        if tool == "commande_executer" and args.get("command"):
            import shlex
            parts = shlex.split(args["command"])
            # Jamais d'autorisation durable pour un interpréteur (exécuterait n'importe quel code) ; sinon : commande EXACTE.
            if not parts or os.path.basename(parts[0]) in INTERPRETERS:
                return None
            return " ".join(parts)
        return None

    def matching_policy(self, tool: str, args: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if tool not in POLICY_TOOLS:
            return None
        for p in self.policies():
            if p.get("tool") != tool or (p.get("expires_at") and p["expires_at"] < now()[:19]):
                continue
            try:
                if tool == "fichier_supprimer":
                    target = self.resolve_path(args.get("path", ""), write=True)      # le périmètre ne dispense jamais du contrôle des dossiers
                    if _is_within(target, Path(p["scope"])):
                        return p
                elif tool == "commande_executer":
                    cmd = " ".join(__import__("shlex").split(args.get("command", "")))
                    if cmd == p["scope"]:                       # commande identique, arguments compris
                        return p
            except (JarvisError, ValueError):
                continue
        return None

    def add_policy(self, tool: str, args: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if tool not in POLICY_TOOLS:
            return None
        scope = self._scope_for(tool, args)
        if not scope:
            return None
        import uuid
        pol = {"id": uuid.uuid4().hex[:8], "tool": tool, "scope": scope, "created_at": now()[:19], "expires_at": None}
        cur = [p for p in self.policies() if not (p["tool"] == tool and p["scope"] == scope)]
        self.settings.update({"policies": cur + [pol]}, f"autorisation préalable : {tool} sur {scope}")
        return pol

    def revoke_policy(self, pid: str) -> bool:
        cur = self.policies()
        new = [p for p in cur if p["id"] != pid]
        if len(new) == len(cur):
            return False
        self.settings.update({"policies": new}, f"autorisation préalable {pid} révoquée")
        return True

    def decide(self, confirmation_id: int, approve: bool) -> Dict[str, Any]:
        row = self.db.one("SELECT * FROM confirmations WHERE id=?", (confirmation_id,))
        if not row:
            raise ValidationError("Confirmation introuvable.")
        if row["status"] != "en_attente":
            raise ValidationError(f"Cette confirmation est déjà « {row['status']} ».")
        status = "acceptee" if approve else "refusee"
        self.db.execute("UPDATE confirmations SET status=?, decided_at=? WHERE id=?", (status, now(), confirmation_id))
        row["status"] = status
        return row

    def consume_confirmation(self, tool: str, args: Dict[str, Any], task_id: Optional[int]) -> bool:
        """Vrai si une confirmation acceptée correspond exactement (outil + arguments), puis la consomme."""
        h = args_hash(tool, args)
        row = self.db.one(
            "SELECT id FROM confirmations WHERE tool=? AND args_hash=? AND status='acceptee' AND (task_id IS ? OR task_id=?) "
            "ORDER BY id DESC LIMIT 1", (tool, h, task_id, task_id))
        if not row:
            return False
        self.db.execute("UPDATE confirmations SET status='utilisee' WHERE id=?", (row["id"],))
        return True

    def pending(self) -> List[Dict[str, Any]]:
        rows = self.db.all("SELECT * FROM confirmations WHERE status='en_attente' ORDER BY id DESC")
        for r in rows:
            r["args"] = loads(r["args"], {})
        return rows

    def summary(self) -> Dict[str, Any]:
        mode = self.mode()
        free, confirm = MODE_POLICY.get(mode, ((), ()))
        return {
            "mode": mode,
            "sans_confirmation": list(free),
            "avec_confirmation": list(confirm),
            "interdits": [r for r in RISKS if r not in free and r not in confirm],
            "dossiers": self.allowed_dirs(),
            "zones_interdites": [str(p) for p in FORBIDDEN_PREFIXES],
            "zones_protegees_ecriture": [str(p) for p in _write_protected()],
        }


def raise_confirmation(conf_id: int, describe: Dict[str, Any]) -> None:
    raise ConfirmationRequired("Confirmation nécessaire avant cette action.", {"confirmation_id": conf_id, **describe})
