"""Création de sites web (partie 15) : contrôle qualité local et préparation de déploiement.

La génération du site elle-même est faite par l'agent (outils fichiers), avec un
design adapté au secteur. Ce module fournit les contrôles mesurables (SEO, mobile,
accessibilité, liens internes, formulaires, poids) et prépare un paquet de
déploiement sans jamais publier.
"""
from __future__ import annotations

import re
import time
import zipfile
from pathlib import Path
from typing import Any, Dict, List

from ..errors import NotFound, ValidationError
from .registry import CONFIRME, ECHOUE, Tool
from .web import parse_page

FAKE_REVIEW = re.compile(r"(?i)(★★★★★|5 étoiles|avis client|témoignage)")


def check_site(root: Path) -> Dict[str, Any]:
    if not root.is_dir():
        raise NotFound("Dossier du site introuvable.", {"chemin": str(root)})
    pages = sorted(root.rglob("*.html"))
    if not pages:
        raise ValidationError("Aucune page HTML dans ce dossier.", {"chemin": str(root)})
    issues: List[Dict[str, Any]] = []
    total_bytes = 0

    def issue(page, level, msg):
        issues.append({"page": str(page.relative_to(root)), "level": level, "message": msg})

    for page in pages:
        html = page.read_text(encoding="utf-8", errors="replace")
        total_bytes += len(html.encode())
        low = html.lower()
        p = parse_page(html)
        if not p.title.strip():
            issue(page, "erreur", "Balise <title> manquante")
        elif len(p.title.strip()) > 65:
            issue(page, "avertissement", "Titre long (> 65 caractères)")
        if not p.meta.get("description"):
            issue(page, "erreur", "Meta description manquante")
        if 'name="viewport"' not in low:
            issue(page, "erreur", "Meta viewport manquante (affichage mobile)")
        if not p.lang:
            issue(page, "erreur", "Attribut lang manquant sur <html>")
        if "<h1" not in low:
            issue(page, "avertissement", "Aucun titre <h1>")
        elif low.count("<h1") > 1:
            issue(page, "avertissement", "Plusieurs <h1>")
        if p.images_without_alt:
            issue(page, "erreur", f"{p.images_without_alt} image(s) sans texte alternatif")
        if "<form" in low:
            for m in re.finditer(r"<(input|textarea|select)\b([^>]*)>", html, re.I):
                attrs = m.group(2)
                if re.search(r'type="(hidden|submit|button)"', attrs, re.I):
                    continue
                idm = re.search(r'id="([^"]+)"', attrs)
                if not (idm and re.search(rf'for="{re.escape(idm.group(1))}"', html)) and "aria-label" not in attrs:
                    issue(page, "erreur", f"Champ de formulaire sans libellé ({m.group(1)})")
            if 'action="' not in low and "data-netlify" not in low and "onsubmit" not in low and "addeventlistener('submit'" not in low.replace('"', "'"):
                issue(page, "avertissement", "Formulaire sans destination (action) : il n'enverra rien")
        if not re.search(r"<meta[^>]+property=\"og:", html, re.I):
            issue(page, "info", "Pas de balises Open Graph (partage réseaux sociaux)")
        for href, _ in p.links:
            if not href or href.startswith(("http", "mailto:", "tel:", "#", "javascript:", "//")):
                continue
            target = (page.parent / href.split("#")[0].split("?")[0]).resolve()
            if href.split("#")[0] and not target.exists():
                issue(page, "erreur", f"Lien interne cassé : {href}")
        for m in re.finditer(r'(?:src|href)="([^"]+\.(?:css|js|png|jpe?g|webp|svg|avif|ico|woff2?))"', html, re.I):
            ref = m.group(1)
            if ref.startswith(("http", "//", "data:")):
                continue
            if not (page.parent / ref).resolve().exists():
                issue(page, "erreur", f"Ressource introuvable : {ref}")
        if FAKE_REVIEW.search(html) and "fictif" not in low and "démonstration" not in low and "exemple" not in low:
            issue(page, "avertissement", "Avis/témoignages détectés : vérifier qu'ils sont authentiques, sinon les marquer comme exemples")
    for img in list(root.rglob("*.jpg")) + list(root.rglob("*.png")) + list(root.rglob("*.jpeg")):
        if img.stat().st_size > 400_000:
            issues.append({"page": str(img.relative_to(root)), "level": "avertissement",
                           "message": f"Image lourde ({img.stat().st_size // 1024} Ko) : compresser ou passer en WebP"})
    if not (root / "robots.txt").exists():
        issues.append({"page": "/", "level": "info", "message": "robots.txt absent"})
    if not (root / "sitemap.xml").exists():
        issues.append({"page": "/", "level": "info", "message": "sitemap.xml absent"})
    errors = sum(1 for i in issues if i["level"] == "erreur")
    warnings = sum(1 for i in issues if i["level"] == "avertissement")
    return {"root": str(root), "pages": [str(p.relative_to(root)) for p in pages], "errors": errors, "warnings": warnings,
            "issues": issues, "html_kb": round(total_bytes / 1024, 1)}


def h_check(ctx, a):
    root = ctx.app.permissions.resolve_path(a["dir"])
    return check_site(root)


def v_check(ctx, a, r):
    return (CONFIRME, "0 erreur bloquante") if r["errors"] == 0 else (ECHOUE, f"{r['errors']} erreur(s) à corriger")


def h_prepare_deploy(ctx, a):
    root = ctx.app.permissions.resolve_path(a["dir"])
    report = check_site(root)
    if report["errors"]:
        raise ValidationError("Le site a encore des erreurs : corrige-les avant de préparer le déploiement.",
                              {"erreurs": report["errors"]})
    out_dir = ctx.app.permissions.resolve_path(str(root.parent / "deploiements"), write=True)
    out_dir.mkdir(parents=True, exist_ok=True)
    dest = out_dir / f"{root.name}-{time.strftime('%Y%m%d-%H%M%S')}.zip"
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as z:
        for f in root.rglob("*"):
            if f.is_file() and not any(part.startswith(".") for part in f.relative_to(root).parts):
                z.write(f, str(f.relative_to(root)))
    checklist = out_dir / f"{root.name}-CHECKLIST-DEPLOIEMENT.md"
    checklist.write_text(
        f"# Déploiement de {root.name} — préparé, NON publié\n\n"
        f"Paquet : `{dest.name}` ({dest.stat().st_size // 1024} Ko), contrôle qualité : 0 erreur, {report['warnings']} avertissement(s).\n\n"
        "## À valider par Sacha avant publication\n"
        "- [ ] Contenus et coordonnées vérifiés avec le client (aucune donnée fictive restante)\n"
        "- [ ] Mentions légales et politique de confidentialité complètes\n"
        "- [ ] Nom de domaine choisi\n"
        "- [ ] Hébergeur choisi (Netlify / Vercel / GitHub Pages : offres gratuites possibles, conditions à vérifier)\n"
        "- [ ] Formulaire relié à un service réel et testé\n\n"
        "## Publication (manuelle, ou par JARVIS après confirmation explicite et connecteur configuré)\n"
        "Netlify : glisser-déposer le ZIP sur app.netlify.com/drop.\n", encoding="utf-8")
    return {"package": str(dest), "checklist": str(checklist), "warnings": report["warnings"], "published": False}


def v_deploy(ctx, a, r):
    try:
        with zipfile.ZipFile(r["package"]) as z:
            ok = z.testzip() is None and any(n.endswith("index.html") for n in z.namelist())
        return (CONFIRME, "paquet ZIP valide avec index.html") if ok else (ECHOUE, "paquet incomplet")
    except Exception as e:  # noqa: BLE001
        return ECHOUE, str(e)


def register(reg) -> None:
    P = lambda **kw: kw  # noqa: E731
    reg.register(Tool("site_controler", "Contrôle qualité d'un site statique local : SEO, mobile, accessibilité, liens, ressources, formulaires.",
                      {"dir": P(type="string", required=True)}, h_check, "faible", "sites", 60,
                      expected="rapport d'erreurs et avertissements", verification="0 erreur bloquante", verify=v_check))
    reg.register(Tool("site_preparer_deploiement", "Préparer un paquet de déploiement (ZIP + checklist). Ne publie jamais.",
                      {"dir": P(type="string", required=True)}, h_prepare_deploy, "modere", "sites", 120,
                      expected="paquet prêt, non publié", verification="intégrité du ZIP", verify=v_deploy))
