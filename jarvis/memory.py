"""Mémoire à long terme (partie 13) : SQLite + recherche plein texte FTS5.

Chaque souvenir a un type, une nature (fait / préférence / hypothèse),
une source, une raison, des dates, une confiance, un statut et un projet.
Les secrets sont refusés à l'enregistrement.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Any, Dict, List, Optional

from .db import Database, now
from .errors import NotFound, ValidationError
from .logbook import redact

TYPES = {
    "preference": "Préférence",
    "info_personnelle": "Information personnelle utile",
    "objectif": "Objectif",
    "projet": "Projet",
    "decision": "Décision",
    "tache": "Tâche",
    "resultat": "Résultat",
    "instruction": "Instruction personnalisée",
    "connaissance": "Connaissance professionnelle",
    "operation": "Historique d'opération",
    "resume_conversation": "Résumé de conversation",
    "reference_document": "Référence de document",
    "temporaire": "Information temporaire",
}
NATURES = ("fait", "preference", "hypothese")
STATUSES = ("valide", "obsolete", "a_verifier")

_SECRET_HINT = re.compile(r"(?i)\b(mot de passe|password|passwd|code pin|iban|cvv|clé api|api key|token|secret)\b")


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s.lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def _words(s: str) -> set:
    return {w for w in _norm(s).split() if len(w) > 2}


def similarity(a: str, b: str) -> float:
    wa, wb = _words(a), _words(b)
    return len(wa & wb) / len(wa | wb) if wa and wb else 0.0


def fts_query(q: str) -> str:
    words = [w for w in re.findall(r"\w+", q, re.UNICODE) if len(w) > 1]
    return " OR ".join(f'"{w}"*' for w in words[:12])


class Memory:
    def __init__(self, db: Database, logbook=None):
        self.db = db
        self.logbook = logbook

    def add(self, content: str, type: str = "connaissance", source: str = "utilisateur", nature: str = "fait",
            reason: str = "", confidence: Optional[float] = None, project_id: Optional[int] = None,
            status: str = "valide", expires_at: Optional[str] = None, conversation_id: Optional[int] = None) -> Dict[str, Any]:
        content = (content or "").strip()
        if not content:
            raise ValidationError("Contenu vide.")
        if type not in TYPES:
            raise ValidationError("Type de mémoire inconnu.", {"types": list(TYPES)})
        if nature not in NATURES:
            raise ValidationError("Nature : fait, preference ou hypothese.")
        if status not in STATUSES:
            raise ValidationError("Statut : valide, obsolete ou a_verifier.")
        if redact(content) != content or _SECRET_HINT.search(content):
            raise ValidationError("Information sensible (mot de passe, clé, numéro bancaire…) : JARVIS ne la mémorise pas.")
        dup = self.find_duplicate(content, project_id)
        if dup:
            self.db.execute("UPDATE memories SET updated_at=?, status='valide' WHERE id=?", (now(), dup["id"]))
            return {**self.get(dup["id"]), "duplicate_of_existing": True}
        if type == "temporaire" and not expires_at:
            import datetime as _dt
            expires_at = (_dt.datetime.now() + _dt.timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%S")
        # Informations proches mais différentes (même type, même projet) : contradiction possible.
        conflicts = [r for r in self.search(content, type=type, project_id=project_id, limit=10, strict_project=True)
                     if 0.5 <= similarity(r["content"], content) < 1.0]
        if conflicts and status == "valide":
            status = "a_verifier"
        ts = now()
        mid = self.db.insert(
            "INSERT INTO memories(type, nature, content, source, reason, confidence, status, project_id, expires_at, conversation_id, "
            "created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (type, nature, content, source, reason, confidence, status, project_id, expires_at, conversation_id, ts, ts))
        if self.logbook:
            self.logbook.log("memoire", f"Mémorisé ({TYPES[type]}) : {content[:120]}" + (" — contradiction possible, à vérifier" if conflicts else ""),
                             "attention" if conflicts else "succes", data={"id": mid, "source": source, "conflits": [c["id"] for c in conflicts]})
        out = self.get(mid)
        out["possible_conflicts"] = [{"id": c["id"], "content": c["content"]} for c in conflicts]
        return out

    def get(self, mid: int) -> Dict[str, Any]:
        r = self.db.one("SELECT m.*, p.name AS project_name FROM memories m LEFT JOIN projects p ON p.id=m.project_id WHERE m.id=?", (mid,))
        if not r:
            raise NotFound("Souvenir introuvable.", {"id": mid})
        return r

    def find_duplicate(self, content: str, project_id: Optional[int]) -> Optional[Dict[str, Any]]:
        n = _norm(content)
        for r in self.search(content, project_id=project_id, limit=10, include_obsolete=True, strict_project=True):
            if _norm(r["content"]) == n:
                return r
        return None

    def search(self, q: str = "", type: str = "", project_id: Optional[int] = None, limit: int = 50,
               include_obsolete: bool = False, strict_project: bool = False) -> List[Dict[str, Any]]:
        params: List[Any] = []
        if q.strip() and fts_query(q):
            sql = ("SELECT m.*, p.name AS project_name, bm25(memories_fts) AS score FROM memories_fts "
                   "JOIN memories m ON m.id = memories_fts.rowid LEFT JOIN projects p ON p.id=m.project_id "
                   "WHERE memories_fts MATCH ?")
            params.append(fts_query(q))
        else:
            sql = "SELECT m.*, p.name AS project_name, 0 AS score FROM memories m LEFT JOIN projects p ON p.id=m.project_id WHERE 1=1"
        if type:
            sql += " AND m.type=?"
            params.append(type)
        if project_id is not None:
            sql += " AND m.project_id=?" if strict_project else " AND (m.project_id=? OR m.project_id IS NULL)"
            params.append(project_id)
        elif strict_project:
            sql += " AND m.project_id IS NULL"
        if not include_obsolete:
            sql += " AND m.status != 'obsolete' AND (m.expires_at IS NULL OR m.expires_at > ?)"
            params.append(now()[:19])
        sql += " ORDER BY score, m.updated_at DESC LIMIT ?"
        params.append(limit)
        return self.db.all(sql, params)

    def update(self, mid: int, **fields) -> Dict[str, Any]:
        self.get(mid)
        allowed = {"content", "type", "nature", "status", "reason", "confidence", "project_id", "source"}
        sets, params = [], []
        for k, v in fields.items():
            if k not in allowed or v is None:
                continue
            if k == "content" and (redact(v) != v or _SECRET_HINT.search(v)):
                raise ValidationError("Information sensible refusée.")
            if k == "type" and v not in TYPES or k == "nature" and v not in NATURES or k == "status" and v not in STATUSES:
                raise ValidationError(f"Valeur invalide pour {k}.")
            sets.append(f"{k}=?")
            params.append(v)
        if not sets:
            return self.get(mid)
        sets.append("updated_at=?")
        params += [now(), mid]
        self.db.execute(f"UPDATE memories SET {', '.join(sets)} WHERE id=?", params)
        if self.logbook:
            self.logbook.log("memoire", f"Souvenir {mid} corrigé", "info", data={"champs": list(fields)})
        return self.get(mid)

    def forget(self, mid: int) -> None:
        self.get(mid)
        self.db.execute("DELETE FROM memories WHERE id=?", (mid,))
        if self.logbook:
            self.logbook.log("memoire", f"Souvenir {mid} oublié à la demande", "info")

    def forget_project(self, project_id: int) -> int:
        cur = self.db.execute("DELETE FROM memories WHERE project_id=?", (project_id,))
        if self.logbook:
            self.logbook.log("memoire", f"Mémoire du projet {project_id} supprimée ({cur.rowcount} éléments)", "attention")
        return cur.rowcount

    def export(self, project_id: Optional[int] = None) -> Dict[str, Any]:
        rows = self.db.all("SELECT * FROM memories" + (" WHERE project_id=?" if project_id else "") + " ORDER BY id",
                           (project_id,) if project_id else ())
        return {"format": "jarvis-memoire-v1", "exported_at": now(), "count": len(rows), "items": rows}

    def import_(self, data: Dict[str, Any]) -> Dict[str, int]:
        if not isinstance(data, dict) or data.get("format") != "jarvis-memoire-v1":
            raise ValidationError("Format d'import inconnu (attendu : jarvis-memoire-v1).")
        added = skipped = 0
        for it in data.get("items", []):
            try:
                r = self.add(it["content"], it.get("type", "connaissance"), it.get("source", "import"),
                             it.get("nature", "fait"), it.get("reason", "import"), it.get("confidence"), None,
                             it.get("status", "valide"))
                skipped += 1 if r.get("duplicate_of_existing") else 0
                added += 0 if r.get("duplicate_of_existing") else 1
            except ValidationError:
                skipped += 1
        return {"added": added, "skipped": skipped}

    def duplicates(self) -> List[List[Dict[str, Any]]]:
        groups: Dict[str, List[Dict[str, Any]]] = {}
        for r in self.db.all("SELECT * FROM memories ORDER BY id"):
            groups.setdefault(_norm(r["content"]) + f"|{r['project_id']}", []).append(r)
        return [g for g in groups.values() if len(g) > 1]

    def cleanup(self) -> Dict[str, int]:
        """Fusionne les doublons exacts (garde le plus ancien)."""
        removed = 0
        for g in self.duplicates():
            for r in g[1:]:
                self.db.execute("DELETE FROM memories WHERE id=?", (r["id"],))
                removed += 1
        return {"doublons_supprimes": removed}

    def purge_expired(self) -> int:
        cur = self.db.execute("DELETE FROM memories WHERE expires_at IS NOT NULL AND expires_at <= ?", (now()[:19],))
        if cur.rowcount and self.logbook:
            self.logbook.log("memoire", f"{cur.rowcount} information(s) temporaire(s) expirée(s) supprimée(s)", "info")
        return cur.rowcount

    def stats(self) -> Dict[str, Any]:
        rows = self.db.all("SELECT type, count(*) AS n FROM memories WHERE status!='obsolete' GROUP BY type")
        return {"total": sum(r["n"] for r in rows), "par_type": {r["type"]: r["n"] for r in rows}}
