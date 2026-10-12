# État du projet JARVIS

Mis à jour : 2026-10-12 · Version 0.1.0 · **Phase actuelle : 15 (livraison) terminée pour la v0.1**

## Résumé
JARVIS fonctionne sur le Mac de Sacha : service local démarré (`http://127.0.0.1:8765`), fenêtre Chrome dédiée, lanceur `~/Applications/JARVIS.app`. Fournisseur IA réel : Claude via Claude Code (abonnement, sans clé API). 64 tests passent (62 hors ligne + 2 avec Claude réel).

## Phases
| Phase | État |
|---|---|
| 1 Audit | fait — docs/ENVIRONMENT_AUDIT.md |
| 2 Architecture | fait — docs/ARCHITECTURE.md |
| 3 Socle (API, base, config, journal) | fait |
| 4 Interface Obsidian Emerald (23 espaces) | fait, vérifiée dans un navigateur (bureau 1440×900 et mobile 375×812) |
| 5 Conversation (modèle réel) | fait — Claude Code |
| 6 Moteur d'outils, permissions, confirmations | fait |
| 7 Fichiers et terminal | fait |
| 8 Mémoire, projets, tâches | fait |
| 9 Navigateur et intégrations | fait (lecture HTTP + DuckDuckGo ; Gmail/Agenda via Claude Code, désactivés par défaut) |
| 10 Voix | fait partiellement — synthèse testée ; dictée Chrome implémentée, non testée au micro ; mot d'activation non implémenté |
| 11 Automatisations | fait |
| 12 Création web et prospection | fait |
| 13 Sécurité | fait — tests négatifs |
| 14 Tests | fait — 64 tests |
| 15 Livraison | fait |

## Critères de livraison (partie 36)

| # | Critère | Test exécuté | Résultat et preuve | Limite |
|---|---|---|---|---|
| 1 | L'application démarre | `python3 jarvis.py start` puis `status` | « démarré — 11/13 contrôles OK » (les 2 restants = Ollama et API Anthropic non configurés, attendu) | Le lanceur .app attend l'autorisation macOS d'accès à Documents (1er lancement) |
| 2 | L'interface fonctionne | 23 pages chargées une à une dans le navigateur intégré, erreurs JS vérifiées | 23/23 affichées, 0 erreur de syntaxe (contrôle JavaScriptCore) | — |
| 3 | Le backend fonctionne | `tests/test_api_and_tools.py::ApiTests` | 8 tests OK (jeton, hôte, origine, CSP, réglages, tâches, erreurs) | — |
| 4 | Un fournisseur IA réel répond | `JARVIS_TEST_REEL=1 … tests.test_reel` + conversation dans l'interface | 2/2 OK ; usage enregistré `claude_code / inclus_abonnement` | consomme l'usage de l'abonnement |
| 5 | Les erreurs sont gérées | tests outil inconnu, paramètres invalides, fichier inexistant, fournisseur indisponible | erreurs structurées (`code`, `message`, `details`), tâche conservée | — |
| 6 | Une tâche peut être créée | `test_tache_creee_puis_annulee_via_api`, `test_dependances` | OK | — |
| 7 | Une tâche peut être annulée | `test_annulation_arrete_reellement_la_commande` | processus tué : le fichier « fin » n'est jamais écrit | — |
| 8 | La mémoire persiste après redémarrage | `test_memoire_persiste_apres_redemarrage` | OK | — |
| 9 | Un fichier de test peut être créé | interface : « Crée test/bonjour.md… » + `test_action_reelle_puis_compte_rendu` | fichier écrit, relu, sha256 identique, état « Confirmé » | — |
| 10 | Un fichier de test peut être lu | `test_ecriture_lecture_version_precedente` | OK | — |
| 11 | Une commande autorisée fonctionne | `test_commande_autorisee` (`echo bonjour`) | code 0, sortie lue | — |
| 12 | Une commande interdite est bloquée | `test_commandes_dangereuses_bloquees`, `test_operateurs_de_shell_refuses` | `rm`, `sudo`, `curl`, `chmod`, `osascript`, `bash`, `|`, `;`, `>`, `$()` refusés et journalisés | — |
| 13 | Une confirmation sensible fonctionne | interface : suppression de test/bonjour.md → carte d'accord → Autoriser ; tests `test_confirmation_*` | fichier déplacé en corbeille seulement après accord ; accord à usage unique et lié aux arguments | — |
| 14 | Le journal d'activité fonctionne | page Historique, `test_journal_expurge_les_secrets` | événements enregistrés, filtrables, exportables | — |
| 15 | Les secrets sont protégés | tests expurgation, mémoire refusant les secrets, sauvegarde sans secret, `.env` illisible, `data/` illisible | OK ; secrets au trousseau ; crochet Git anti-secret | — |
| 16 | Les tests principaux passent | `python3 jarvis.py test` | 64 tests, 0 échec (2 ignorés sans `JARVIS_TEST_REEL`) | — |
| 17 | Les limites sont documentées | docs/KNOWN_LIMITATIONS.md | fait | — |
| 18 | Le démarrage est documenté | README.md, docs/INSTALLATION.md | fait | — |
| 19 | Arrêt propre | `python3 jarvis.py stop` (exécuté plusieurs fois) | « JARVIS arrêté proprement » ; tâches annulées, aperçus arrêtés | — |
| 20 | Procédure de récupération | `test_sauvegarde_verifiee_et_restauration` + docs/INSTALLATION.md | restauration appliquée au redémarrage ; un bug de collision de noms de sauvegardes a été trouvé et corrigé | — |

## Fichiers principaux
`jarvis.py` (lanceur) · `jarvis/app.py` · `jarvis/server.py` · `jarvis/agent/engine.py` · `jarvis/tasks.py` · `jarvis/tools/*` · `jarvis/permissions.py` · `web/js/app.js` · `web/css/tokens.css` · `tests/`.

## Décisions d'architecture
Python standard + SQLite + JavaScript natif (aucune dépendance, Node absent) ; Claude Code comme moteur de texte pur (actions via le registre de JARVIS) ; Chrome en mode application ; CRM CYPHER en lecture seule. Détails : docs/ARCHITECTURE.md.

## Dépendances
Aucune à installer. Utilise : Python 3.9 (Apple), SQLite, Google Chrome, Claude Code CLI, outils macOS (`say`, `osascript`, `textutil`, `security`).

## Permissions manquantes (action de Sacha)
1. Autoriser JARVIS.app à accéder au dossier Documents (fenêtre macOS au premier lancement).
2. Autoriser le micro dans la fenêtre JARVIS au premier usage de la dictée.
3. Facultatif : activer Gmail et Google Agenda dans Applications connectées (un clic + confirmation).
4. Facultatif : autoriser les notifications d'« Éditeur de script ».

## Problèmes connus
Voir docs/KNOWN_LIMITATIONS.md. Aucun test en échec.

## Prochaines étapes exactes
Voir NEXT_STEPS.md.
