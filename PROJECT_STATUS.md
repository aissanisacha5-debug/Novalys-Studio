# État du projet JARVIS

Mis à jour : 2026-10-12 · **Version 0.2.0** (prompt 3 exécuté) · Service réel démarré sur http://127.0.0.1:8765 · Lanceur `~/Applications/JARVIS.app`

## A. Réalisé
- **Modules** : API locale + flux temps réel, base SQLite (migrations 0001, 0002), configuration versionnée, journal expurgé, permissions (modes, dossiers, risques A/B/C, confirmations à usage unique), registre de **59 outils**, moteur d'agent (plan, actions JSON, vérification, état final recoupé, prochaine action, lectures parallèles, boucles, idempotence), 12 agents spécialisés, orchestrateur de tâches persistant (dépendances, priorité, pause, reprise, annulation réelle, verrous de fichiers, reprise après redémarrage), mémoire (FTS5, contradictions, temporaire), projets, rappels, automatisations, documents, sites, web, **navigateur piloté**, voix, notifications, connecteurs, fournisseurs IA avec repli, diagnostic copiable, sauvegardes/restauration, plugins.
- **Interface** Obsidian Emerald : 23 espaces reliés au backend, noyau visuel piloté par les événements réels, responsive (bureau et mobile vérifiés), clavier, réduction des animations.
- **Outillage** : `python3 jarvis.py start|stop|status|open|backup|test|verifier|check|deps|dev|demo|build`, crochet Git anti-secret, dépôt Git local (point de restauration `eb730a6` avant le prompt 3).
- **Documents** : README, PROJECT_STATUS, NEXT_STEPS, CHANGELOG, `.env.example`, docs/ SETUP, USAGE, SECURITY, ARCHITECTURE, ENVIRONMENT_AUDIT, CONNECTORS, KNOWN_LIMITATIONS, TROUBLESHOOTING, ROADMAP.

## B. Tests (exécutés le 2026-10-12)
| Commande | Résultat |
|---|---|
| `python3 jarvis.py verifier` | OK — 44 fichiers Python (syntaxe 3.9, imports), 28 JS (syntaxe, imports), CSS (jetons), secrets suivis par Git |
| `python3 jarvis.py check` | **77 tests, 0 échec**, 3 ignorés (2 tests navigateur quand httpbin.org ne répond pas, 1 hors réseau) |
| `JARVIS_TEST_REEL=1 python3 -m unittest tests.test_reel` | 3/3 OK (réponse réelle, création de fichier réelle, **parcours complet API → tâche → outil → compte rendu → redémarrage → persistance**) — passé 4 fois de suite après correction |
| Navigateur piloté (réseau) | OK lors de 5 passages : formulaire rempli et relu, envoi seulement après accord, réponse du site lue, capture PNG ; mot de passe refusé ; adresse locale refusée |
| Migration réelle | base de Sacha migrée 0001 → 0002 avec sauvegarde `data/backups/*-avant-migration.db` |
| Lancement à froid | `stop` puis `start` : 14/16 contrôles OK (les 2 restants : Ollama et API Anthropic non configurés) |
| Interface | 23/23 pages affichées sans erreur sur l'instance réelle (script dans le navigateur intégré) |

**Défauts trouvés et corrigés pendant la validation** : modèle haiku qui tentait d'appeler les outils lui-même (1 demande sur 3 échouait → 6/6 après correction) ; collision de noms de sauvegardes ; Chrome PDF qui ne rend pas la main ; navigation lue avant le chargement de la nouvelle page ; 25 imports inutiles ; 9 couleurs codées en dur.

**Non exécutés** : test au micro (je ne peux pas parler ; la dictée Chrome est implémentée, non testée de bout en bout) ; tests Gmail/Agenda (connecteurs désactivés par défaut, à activer par Sacha) ; test e2e automatisé de l'interface (Playwright absent : vérification manuelle et scriptée à la place).

## C. Lancement
- Démarrer : double-clic **JARVIS** (`~/Applications`) ou `python3 jarvis.py start` → http://127.0.0.1:8765
- Construire : `python3 jarvis.py build` (application web locale + lanceur ; **pas d'installateur natif**)
- Tests : `python3 jarvis.py check`

## D. Configuration restante
- **Clés API** : aucune nécessaire (Claude via l'abonnement). Facultatif et payant : clé API Anthropic (Sécurité > Secrets).
- **Comptes** : activer Gmail et Google Agenda dans Applications connectées (déjà connectés à claude.ai).
- **Permissions macOS** : accès au dossier Documents pour JARVIS.app (premier lancement) ; micro pour Chrome (voix) ; notifications d'« Éditeur de script ».
- **Services externes** : GitHub/Netlify/Vercel non connectés (jetons absents, déploiement = paquet ZIP).

## E. Limites connues
Voir docs/KNOWN_LIMITATIONS.md. Principales : dictée via Google (Chrome), pas de mot d'activation, pas de téléchargement par le navigateur piloté, CRM CYPHER en lecture seule, rappels/automatisations seulement quand JARVIS est ouvert, variabilité du modèle IA.

## F. État par fonctionnalité
| Fonctionnalité | État | Preuve |
|---|---|---|
| Démarrage, arrêt propre, lancement à froid | opérationnelle | `start`/`stop`/`status` exécutés |
| Interface (23 espaces) | opérationnelle | 23/23 pages, captures d'écran |
| Conversation (Claude réel) | opérationnelle | tests réels 3/3 |
| Orchestrateur de tâches (dépendances, pause, reprise, annulation, redémarrage) | opérationnelle | test_agent, test_reel |
| Outils fichiers / terminal / documents (pdf, docx, xlsx…) | opérationnelle | test_security, test_api_and_tools |
| Permissions et confirmations | opérationnelle | tests + suppression réelle avec accord dans l'interface |
| Mémoire durable (contradictions, temporaire, export) | opérationnelle | test_core |
| Projets, rappels, planning, automatisations | opérationnelle | test_core, test_api_and_tools |
| Recherche web, lecture, audit de site | opérationnelle | utilisée en réel (DuckDuckGo) |
| Navigateur piloté (JS, formulaires avec accord, captures) | opérationnelle | BrowserTests (réseau) |
| Création et contrôle de sites, aperçu, paquet | opérationnelle | test_controle_de_site, test_apercu |
| Journal, historique, diagnostic copiable | opérationnelle | test_v02, page Diagnostic |
| Sauvegarde / restauration / migrations | opérationnelle | test_core (base v0.1 migrée) + base réelle |
| Repli IA (modèle, fournisseur) | opérationnelle (testée avec fournisseurs de test) | test_repli |
| Synthèse vocale | opérationnelle | voix testée (`say`) |
| Dictée vocale | **non testée** | implémentée (Chrome) ; nécessite le micro de Sacha |
| Mot d'activation | **non implémentée** | — |
| Gmail / Google Agenda | **non configurée** | connecteurs prêts, désactivés ; test via bouton Tester |
| Ollama / API Anthropic | **non configurée** | indisponibles, état affiché |
| GitHub / Netlify / Vercel | **non configurée** | jetons absents |
| Lanceur JARVIS.app | **partielle** | créé ; premier lancement en attente de l'autorisation macOS « Documents » |
