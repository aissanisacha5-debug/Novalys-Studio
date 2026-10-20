"""Affichage de Nova : l'agent présente des éléments réels (rendez-vous, e-mails, prospects, tâches) sous forme de
cartes, puis une vue détaillée à deux panneaux (proposition / e-mail à valider).

L'outil ne fait qu'afficher : il ne lit ni n'envoie rien. Les données viennent des autres outils (agenda, CRM,
Gmail…) et chaque carte peut porter sa source. La validation d'un envoi passe toujours par le système de
confirmation du moteur : la vue ne fait que montrer la question au bon endroit.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..errors import ValidationError
from .registry import Tool

TONES = ("froid", "tiede", "chaud", "info", "ok", "alerte")
ICONS = ("rappel", "email", "document", "appel", "tache", "agenda")
VIEWS = ("liste", "detail", "succes")


def _s(v: Any, name: str, limit: int, required: bool = False) -> Optional[str]:
    if v is None or v == "":
        if required:
            raise ValidationError(f"Affichage Nova : « {name} » est obligatoire.")
        return None
    if not isinstance(v, str):
        raise ValidationError(f"Affichage Nova : « {name} » doit être un texte.")
    v = v.strip()
    if len(v) > limit:
        raise ValidationError(f"Affichage Nova : « {name} » dépasse {limit} caractères.")
    return v


def _obj(v: Any, name: str) -> Dict[str, Any]:
    if v is None:
        return {}
    if not isinstance(v, dict):
        raise ValidationError(f"Affichage Nova : « {name} » doit être un objet.")
    return v


def normalize_item(raw: Any, i: int) -> Dict[str, Any]:
    it = _obj(raw, f"elements[{i}]")
    badge = _obj(it.get("badge"), "badge")
    action = _obj(it.get("action"), "action")
    source = _obj(it.get("source"), "source")
    tone = badge.get("ton", "info")
    if badge and tone not in TONES:
        raise ValidationError(f"Affichage Nova : ton de badge inconnu « {tone} » ({', '.join(TONES)}).")
    icon = action.get("icone", "tache")
    if action and icon not in ICONS:
        raise ValidationError(f"Affichage Nova : icône inconnue « {icon} » ({', '.join(ICONS)}).")
    return {
        "id": _s(it.get("id"), "id", 80) or f"e{i + 1}",
        "nom": _s(it.get("nom"), "nom", 80, True),
        "contexte": _s(it.get("contexte"), "contexte", 140),
        "resume": _s(it.get("resume"), "resume", 200),
        "details": _s(it.get("details"), "details", 400),
        "badge": {"texte": _s(badge.get("texte"), "badge.texte", 20, True), "ton": tone} if badge else None,
        "action": {"label": _s(action.get("label"), "action.label", 40) or "Action recommandée",
                   "texte": _s(action.get("texte"), "action.texte", 160, True), "icone": icon} if action else None,
        "source": {"type": _s(source.get("type"), "source.type", 40), "ref": _s(source.get("ref"), "source.ref", 200),
                   "date": _s(source.get("date"), "source.date", 40)} if source else None,
    }


def normalize_detail(raw: Any) -> Optional[Dict[str, Any]]:
    if raw is None:
        return None
    d = _obj(raw, "detail")
    left = _obj(d.get("gauche"), "detail.gauche")
    right = _obj(d.get("droite"), "detail.droite")
    sections: List[Dict[str, Any]] = []
    for j, sec in enumerate(left.get("sections") or []):
        sec = _obj(sec, f"sections[{j}]")
        puces = sec.get("puces") or []
        if not isinstance(puces, list) or len(puces) > 8:
            raise ValidationError("Affichage Nova : « puces » doit être une liste de 8 éléments au plus.")
        sections.append({"titre": _s(sec.get("titre"), "section.titre", 40, True), "texte": _s(sec.get("texte"), "section.texte", 300),
                         "puces": [_s(p, "puce", 200, True) for p in puces]})
    if len(sections) > 6:
        raise ValidationError("Affichage Nova : 6 sections au plus.")
    total = _obj(left.get("total"), "total")
    piece = _obj(right.get("piece"), "piece")
    validation = _obj(d.get("validation"), "validation")
    return {
        "element": _s(d.get("element"), "detail.element", 80),
        "gauche": {"surtitre": _s(left.get("surtitre"), "surtitre", 80), "sections": sections,
                   "total": {"label": _s(total.get("label"), "total.label", 40, True), "valeur": _s(total.get("valeur"), "total.valeur", 40, True)}
                   if total else None},
        "droite": {"a": _s(right.get("a"), "droite.a", 200), "sujet": _s(right.get("sujet"), "droite.sujet", 200),
                   "corps": _s(right.get("corps"), "droite.corps", 4000),
                   "piece": {"nom": _s(piece.get("nom"), "piece.nom", 120, True), "info": _s(piece.get("info"), "piece.info", 40)} if piece else None},
        "validation": {"question": _s(validation.get("question"), "validation.question", 120, True),
                       "succes": _s(validation.get("succes"), "validation.succes", 80) or "C'est fait",
                       "succes_detail": _s(validation.get("succes_detail"), "validation.succes_detail", 120)} if validation else None,
    }


def normalize_view(a: Dict[str, Any]) -> Dict[str, Any]:
    vue = a.get("vue") or ("detail" if a.get("detail") else "liste")
    if vue not in VIEWS:
        raise ValidationError(f"Affichage Nova : vue inconnue « {vue} » ({', '.join(VIEWS)}).")
    raw_items = a.get("elements") or []
    if not isinstance(raw_items, list) or len(raw_items) > 8:
        raise ValidationError("Affichage Nova : « elements » doit être une liste de 8 cartes au plus.")
    items = [normalize_item(x, i) for i, x in enumerate(raw_items)]
    ids = [x["id"] for x in items]
    if len(set(ids)) != len(ids):
        raise ValidationError("Affichage Nova : identifiants de cartes en double.")
    selection = _s(a.get("selection"), "selection", 80)
    if selection and selection not in ids:
        raise ValidationError(f"Affichage Nova : « {selection} » ne correspond à aucune carte.")
    detail = normalize_detail(a.get("detail"))
    if vue == "detail" and not detail:
        raise ValidationError("Affichage Nova : la vue « detail » demande un « detail ».")
    succes = _obj(a.get("succes"), "succes")
    return {
        "vue": vue,
        "titre": _s(a.get("titre"), "titre", 60, True),
        "meta": _s(a.get("meta"), "meta", 60),
        "elements": items,
        "selection": selection,
        "detail": detail,
        "succes": {"titre": _s(succes.get("titre"), "succes.titre", 80, True), "detail": _s(succes.get("detail"), "succes.detail", 120)}
        if succes else None,
    }


def h_show(ctx, a):
    view = normalize_view(a)
    app = ctx.app
    view["task_id"] = ctx.task_id
    app.nova_view = view
    app.bus.publish({"type": "nova_view", "task_id": ctx.task_id, "view": view})
    return {"affiche": True, "vue": view["vue"], "cartes": len(view["elements"])}


def h_clear(ctx, a):
    ctx.app.nova_view = None
    ctx.app.bus.publish({"type": "nova_view", "task_id": ctx.task_id, "view": None})
    return {"efface": True}


def register(reg) -> None:
    P = lambda **kw: kw  # noqa: E731
    reg.register(Tool(
        "nova_afficher",
        "Afficher à Sacha, sur l'écran de Nova, des cartes (rendez-vous, e-mails, prospects, tâches…) avec un titre de section, "
        "et éventuellement une vue détaillée à deux panneaux (proposition à gauche, e-mail à droite) avec la question de validation. "
        "UNIQUEMENT des données obtenues par d'autres outils (jamais inventées) ; renseigner la source de chaque carte. "
        "N'envoie rien : un envoi reste soumis à la confirmation du moteur. "
        "elements[] : {id, nom, contexte, resume, details, badge:{texte, ton: froid|tiede|chaud|info|ok|alerte}, "
        "action:{label, texte, icone: rappel|email|document|appel|tache|agenda}, source:{type, ref, date}}. "
        "detail : {element, gauche:{surtitre, sections:[{titre, texte|puces[]}], total:{label, valeur}}, "
        "droite:{a, sujet, corps, piece:{nom, info}}, validation:{question, succes, succes_detail}}.",
        {"titre": P(type="string", required=True, description="Titre de section, ex. « Debrief des rendez-vous »"),
         "meta": P(type="string", description="Texte discret à droite, ex. « Hier · 3 rendez-vous »"),
         "vue": P(type="string", enum=list(VIEWS), description="liste (défaut), detail ou succes"),
         "elements": P(type="array", maxItems=8),
         "selection": P(type="string", description="id de la carte à mettre en avant et développer"),
         "detail": P(type="object"),
         "succes": P(type="object", description="{titre, detail} pour la vue succes")},
        h_show, "faible", "nova", 10))
    reg.register(Tool("nova_effacer", "Revenir à l'accueil de Nova (effacer les cartes affichées).", {}, h_clear, "faible", "nova", 5))
