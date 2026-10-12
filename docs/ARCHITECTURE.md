# Architecture de JARVIS v0.2

## Choix et raisons

| Besoin | Choix | Pourquoi (et ce qui a été écarté) |
|---|---|---|
| Backend | Python 3.9, **bibliothèque standard seule** | Déjà installé ; aucune dépendance à installer ou à maintenir. Node/Tauri écartés : absents, et Homebrew aussi. |
| Base | **Un seul fichier SQLite** (WAL, FTS5), migrations versionnées | Suffisant pour un utilisateur ; recherche plein texte intégrée. Pas de serveur de base. |
| Interface | HTML + CSS + modules JavaScript natifs, servis par le backend | Pas d'étape de compilation ; rapide ; un seul processus. React/Vite écartés (Node absent). |
| Fenêtre | Chrome en mode application (`--app`, profil séparé) | Fenêtre dédiée sans barre d'adresse + reconnaissance vocale du navigateur. Repli : navigateur par défaut. |
| Navigateur piloté | Chrome sans interface + protocole DevTools (client WebSocket maison) | Pages rendues en JavaScript, formulaires ; Playwright écarté (Node absent). |
| Qualité | `scripts/verifier.py` (ast, JavaScriptCore, CSS, secrets) + `unittest` | Aucun outil à installer ; ruff/mypy/eslint écartés (pip/Node non nécessaires pour ce volume). |
| Temps réel | Server-Sent Events (`/api/stream`) | Le noyau visuel et le rail reflètent les événements réels du backend. |
| IA | Couche fournisseurs : **Claude Code CLI** (actif), Ollama, API Anthropic | Seul accès réellement disponible sans frais : `claude -p` utilisé comme moteur de texte pur (aucun outil Claude Code). |
| Secrets | Trousseau macOS (`security`) | Jamais en base, journal, conversation, sauvegarde ni code. |

## Modules (une responsabilité chacun)

```
jarvis.py                 lanceur : start / serve / stop / status / open / backup / test
jarvis/
  app.py                  assemblage des modules, envoi de message, état du noyau, plugins, arrêt propre
  server.py           13  API locale HTTP + SSE, contrôle hôte/origine/jeton, interface statique
  agent/engine.py      3  moteur d'agent : analyse → plan → permissions → outils → vérification → compte rendu
  agent/profiles.py    3  agents spécialisés (mission, outils autorisés, limites, format, critères)
  tasks.py             3  orchestrateur : tâches, dépendances, pause, reprise, annulation, verrous de fichiers
  tools/registry.py    4  registre d'outils : schéma, validation, risque, délai, vérification, disponibilité
  tools/files.py          fichiers et dossiers (9.1)
  tools/shell.py          exécuteur de commandes contrôlé, tests, serveurs d'aperçu (10)
  tools/web.py            recherche, lecture de pages, liens, audit de site (11)
  tools/browser.py        navigateur piloté : ouvrir, remplir, suivre un lien, envoyer (accord), capture
  tools/sites.py          contrôle qualité de site, paquet de déploiement (15)
  tools/documents.py      md, txt, html, json, csv, xlsx, docx, pdf (22)
  tools/data_tools.py     tâches, mémoire, projets, rappels, rapports, e-mails, agenda, Mac, agence, délégation
  permissions.py       5  modes, dossiers autorisés, zones interdites, confirmations à usage unique
  memory.py            6  mémoire durable + FTS5 (13)
  conversations.py        historique, recherche, export
  projects.py             projets, décisions, rappels (14, 18)
  connectors.py        7  connecteurs, pont Gmail/Agenda via Claude Code avec vérification d'appel (20)
  scheduler.py         8  automatisations et planificateur (19)
  logbook.py           9  journal d'activité expurgé + bus d'événements (27)
  providers/          10  fournisseurs IA, budget, modèle de remplacement, usage (21, 25)
  db.py, migrations/  11  stockage, migrations versionnées
  services.py         12  voix (say), notifications macOS, trousseau, infos système, applications
  maintenance.py      14  diagnostic, sauvegardes vérifiées, restauration
  config.py               préférences versionnées, réglages sensibles
web/                    interface Obsidian Emerald (tokens.css = système de design)
tests/                  64 tests (2 « réels », opt-in)
```
Les numéros renvoient aux 14 couches de la partie 4.

## Cycle d'une demande

1. `POST /api/chat` enregistre le message et crée une tâche (type `conversation`).
2. Le moteur construit un contexte **compact** : préférences et souvenirs pertinents (FTS), 14 derniers messages, résumé des anciens (au-delà de 30 messages), étapes déjà exécutées. Jamais tout l'historique.
3. Le modèle répond en JSON validé par schéma (`message`, `plan`, `actions`, `status`, `result_state`).
4. Chaque action passe par le registre : outil existant → disponible → arguments valides → risque autorisé par le mode → confirmation si risque élevé → exécution avec délai → **vérification** (relecture, sha256, code de sortie, HTTP, intégrité ZIP/PDF/OpenXML…) → journal.
5. Les résultats (données non fiables, balisées) sont renvoyés au modèle au tour suivant ; il conclut avec un état honnête.
6. Limites : tours max, durée max, échecs successifs, détection de boucle, action identique non répétée, limite d'appels IA par jour.
7. **État final recoupé** : l'affirmation du modèle est confrontée aux étapes réelles (succès sans vérification → « non vérifié » ; succès malgré un échec → « partiel » ; tout en échec → « échoué »). Une **prochaine action** est conservée avec la tâche.
8. Lectures indépendantes d'un même tour exécutées **en parallèle** (4 au plus) ; les écritures restent séquentielles avec verrous de fichiers.
9. IA : chaîne de repli explicite (modèle par agent → modèle principal → modèle de remplacement → fournisseur de remplacement), seuls les fournisseurs disponibles sont essayés.

## Sécurité (résumé, détail dans SECURITY.md)

- API sur 127.0.0.1, jeton aléatoire par démarrage, Host et Origin vérifiés, CSP stricte.
- Permissions contrôlées dans le backend ; l'interface et les agents ne peuvent pas s'en accorder.
- Changement de mode, dossiers, commandes, connecteurs, budget : confirmation explicite.
- Commandes sans shell, liste blanche, opérateurs refusés, commandes dangereuses bloquées.

## Versions

- Schéma : `schema_migrations` (actuel `0002_complements`) ; sauvegarde automatique avant migration (vérifiée sur la base réelle le 2026-10-12).
- Configuration : `config_versions` (chaque modification, restaurable) ; `CONFIG_SCHEMA_VERSION = 1`.
- Outils : champ `version` par outil. Plugins : manifeste `plugin.json` (outils déclarés, risque maximal).
