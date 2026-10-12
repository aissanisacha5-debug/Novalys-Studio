"""Agents spécialisés (partie 7).

Un seul moteur, plusieurs profils : chaque profil a une mission, des outils
autorisés (sous-ensemble du registre), un périmètre, des limites, un format
de sortie et des critères de réussite. Un profil ne peut jamais élargir les
permissions : il ne fait que restreindre la liste d'outils, et chaque appel
reste contrôlé par le système de permissions.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

READ_TOOLS = ["fichier_lire", "dossier_lister", "fichier_rechercher", "contenu_rechercher", "fichiers_comparer",
              "memoire_rechercher", "projet_consulter", "tache_consulter"]

PROFILES: Dict[str, Dict[str, Any]] = {
    "general": {
        "label": "Orchestrateur",
        "mission": "Comprendre la demande, planifier, agir avec les outils, vérifier et rendre compte.",
        "tools": None,  # tous les outils disponibles
        "max_steps": None,
        "output": "Réponse claire en français, avec l'état de chaque résultat.",
        "success": "Objectif atteint et vérifié, ou blocage expliqué.",
    },
    "developpeur": {
        "label": "Agent développeur",
        "mission": "Créer ou réparer du code dans un dossier de projet autorisé, lancer les tests, corriger.",
        "tools": READ_TOOLS + ["fichier_ecrire", "dossier_creer", "commande_executer", "tests_lancer", "apercu_lancer",
                               "site_controler", "fichier_copier", "fichier_deplacer"],
        "max_steps": 20,
        "output": "Liste des fichiers modifiés, commandes lancées, résultat des tests.",
        "success": "Tests ou contrôles passés.",
    },
    "recherche": {
        "label": "Agent de recherche",
        "mission": "Chercher des informations publiques récentes, ouvrir les sources, comparer, citer.",
        "tools": ["web_rechercher", "web_lire_page", "memoire_rechercher", "rapport_produire"],
        "max_steps": 12,
        "output": "Synthèse avec sources (URL, date de consultation), faits séparés des hypothèses.",
        "success": "Chaque affirmation importante est reliée à une source consultée.",
    },
    "navigateur": {
        "label": "Agent navigateur",
        "mission": "Lire des pages, vérifier des liens, auditer des sites publics.",
        "tools": ["web_lire_page", "web_verifier_liens", "site_auditer", "web_rechercher"],
        "max_steps": 10,
        "output": "Constats mesurés par page.",
        "success": "Pages réellement consultées.",
    },
    "fichiers": {
        "label": "Agent fichiers",
        "mission": "Organiser, classer, comparer et archiver des fichiers dans les dossiers autorisés, sans rien écraser.",
        "tools": READ_TOOLS + ["dossier_creer", "fichier_deplacer", "fichier_copier", "archive_creer", "doublons_detecter",
                               "rapport_produire"],
        "max_steps": 20,
        "output": "Plan de classement puis liste des déplacements vérifiés.",
        "success": "Aucun fichier perdu, chaque déplacement vérifié.",
    },
    "qualite": {
        "label": "Agent contrôle qualité",
        "mission": "Vérifier un résultat : tests, contrôles de site, relecture.",
        "tools": READ_TOOLS + ["tests_lancer", "site_controler", "web_verifier_liens"],
        "max_steps": 10,
        "output": "Verdict (conforme / non conforme) avec preuves.",
        "success": "Verdict appuyé par une vérification exécutée.",
    },
    "securite": {
        "label": "Agent sécurité",
        "mission": "Repérer secrets exposés, permissions excessives et contenus suspects (lecture seule).",
        "tools": READ_TOOLS + ["diagnostic_lancer"],
        "max_steps": 10,
        "output": "Liste de risques classés.",
        "success": "Constats vérifiables.",
    },
    "redaction": {
        "label": "Agent de rédaction",
        "mission": "Rédiger, résumer, reformuler, traduire ; produire des documents.",
        "tools": READ_TOOLS + ["document_creer", "rapport_produire", "email_brouillon_preparer"],
        "max_steps": 8,
        "output": "Document créé et son chemin.",
        "success": "Fichier produit et vérifié.",
    },
    "projet": {
        "label": "Agent gestion de projet",
        "mission": "Décomposer des objectifs, organiser les tâches, détecter les blocages, produire des comptes rendus.",
        "tools": READ_TOOLS + ["projet_creer", "projet_mettre_a_jour", "tache_creer", "tache_terminer", "rappel_creer",
                               "rapport_produire", "planning_preparer"],
        "max_steps": 12,
        "output": "Tâches créées / mises à jour, priorités, prochaines étapes.",
        "success": "Plan cohérent enregistré.",
    },
    "prospection": {
        "label": "Agent de prospection",
        "mission": "Trouver des entreprises, auditer leurs sites publics, qualifier, préparer des brouillons (jamais d'envoi).",
        "tools": ["web_rechercher", "web_lire_page", "site_auditer", "agence_consulter", "document_creer",
                  "email_brouillon_preparer", "rapport_produire", "memoire_rechercher"],
        "max_steps": 20,
        "output": "Prospects qualifiés avec sources, doublons écartés, brouillons préparés.",
        "success": "Données issues de recherches réelles ; aucun envoi.",
    },
    "diagnostic": {
        "label": "Agent de diagnostic",
        "mission": "Vérifier l'état de JARVIS : services, journaux, erreurs, fournisseur IA.",
        "tools": ["diagnostic_lancer", "journal_consulter", "processus_lister", "systeme_etat"],
        "max_steps": 6,
        "output": "État par composant et corrections proposées.",
        "success": "Chaque composant testé.",
    },
    "synthese": {
        "label": "Agent de synthèse",
        "mission": "Consolider des résultats en un compte rendu court.",
        "tools": ["memoire_rechercher", "tache_consulter", "projet_consulter", "rapport_produire"],
        "max_steps": 5,
        "output": "Compte rendu structuré.",
        "success": "Compte rendu fidèle aux résultats.",
    },
}


def profile(name: str) -> Dict[str, Any]:
    return PROFILES.get(name) or PROFILES["general"]


def allowed_tools(name: str, all_ids: List[str]) -> Optional[List[str]]:
    p = profile(name)
    if p["tools"] is None:
        return [t for t in all_ids]
    return [t for t in p["tools"] if t in all_ids]


def listing() -> List[Dict[str, Any]]:
    return [{"id": k, **{kk: vv for kk, vv in v.items()}} for k, v in PROFILES.items()]
