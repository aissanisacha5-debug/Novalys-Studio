# JARVIS

Assistant personnel et professionnel de Sacha (Novalys Studio), local, sur Mac.
Il comprend une demande, planifie, agit avec de vrais outils, **vérifie** le résultat et rend compte, sous un système de permissions strict.

## Démarrer
Double-clic sur **JARVIS** dans `~/Applications` (ou Spotlight). Pour arrêter : **Diagnostic > Arrêter JARVIS**.

## Ce que JARVIS sait faire aujourd'hui
- **Converser** en français (Claude via votre abonnement, sans clé API), historique, recherche, export.
- **Agir** : créer, lire, organiser, comparer, archiver des fichiers dans les dossiers autorisés ; lancer des commandes autorisées, des tests, des aperçus de sites.
- **Créer des sites** : construction par l'agent, contrôle qualité (SEO, mobile, accessibilité, liens), aperçu local, paquet de déploiement (jamais publié seul).
- **Rechercher** sur le web avec sources datées, lire des pages, auditer un site public.
- **Naviguer** : navigateur piloté (pages JavaScript, champs de formulaires, captures) ; envoi d'un formulaire seulement avec votre accord.
- **Documents** : Markdown, HTML, DOCX, PDF, CSV, XLSX, JSON — vérifiés après création.
- **Organiser** : tâches (avec dépendances, pause, reprise, annulation), projets, rappels, planning, automatisations.
- **Mémoire** durable, consultable, corrigeable, exportable ; jamais de secret.
- **Agence** : CRM de CYPHER en lecture seule, revenus confirmés vs prévisions, prospection assistée (brouillons uniquement).
- **E-mails / agenda** via les connecteurs Gmail et Google Agenda (à activer) : lecture et brouillons, aucun envoi.
- **Voix** : dictée (Chrome) et réponses lues par une voix macOS, micro coupé par défaut.

## Documentation
- [PROJECT_STATUS.md](PROJECT_STATUS.md) — état, critères de livraison et preuves
- [docs/SETUP.md](docs/SETUP.md) — installation et commandes · [docs/USAGE.md](docs/USAGE.md) — utilisation
- [NEXT_STEPS.md](NEXT_STEPS.md) — prochaines actions
- [docs/SECURITY.md](docs/SECURITY.md) · [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- [docs/ENVIRONMENT_AUDIT.md](docs/ENVIRONMENT_AUDIT.md) · [docs/CONNECTORS.md](docs/CONNECTORS.md) · [docs/KNOWN_LIMITATIONS.md](docs/KNOWN_LIMITATIONS.md)
- [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) · [docs/ROADMAP.md](docs/ROADMAP.md) · [CHANGELOG.md](CHANGELOG.md)

## Commandes
```
python3 jarvis.py start | stop | status | open | backup | test | verifier | check | deps | dev | demo | build
```
