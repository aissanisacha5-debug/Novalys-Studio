# JARVIS

Assistant personnel et professionnel de Sacha (Novalys Studio), local, sur Mac.
Il comprend une demande, planifie, agit avec de vrais outils, **vérifie** le résultat et rend compte, sous un système de permissions strict.

## Nova (transformation en cours)
JARVIS devient **Nova**, assistant vocal accessible sur ordinateur et téléphone. L'accueil (`/`) est désormais un noyau lumineux plein écran : touchez-le et parlez. L'interface complète reste sur `/console`. Audit, plan et état : [docs/NOVA.md](docs/NOVA.md).

## Installer et lancer
- **Installer** : ouvrir `dist/JARVIS-0.3.0.dmg`, glisser JARVIS dans Applications (ou `python3 jarvis.py install`). Détails : [docs/INSTALLATION.md](docs/INSTALLATION.md).
- **Lancer** : double-clic sur **JARVIS** (Dock, Applications ou Spotlight). Aucun terminal, aucun navigateur, aucune autre application de conversation n'est nécessaire.
- **Configurer** : Modèles IA (fournisseur), Paramètres (voix, démarrage automatique, budget), Sécurité (dossiers, clés).
- **Mettre à jour** : `python3 jarvis.py build && python3 jarvis.py install` (les données sont conservées).
- **Arrêter** : menu JARVIS > Quitter.

## Ce que JARVIS sait faire aujourd'hui
- **Converser** en français dans sa propre fenêtre, avec le fournisseur IA de votre choix (Claude via l'abonnement, API compatible OpenAI, Anthropic, modèle local), historique, recherche, export.
- **Agir** : créer, lire, organiser, comparer, archiver des fichiers dans les dossiers autorisés ; lancer des commandes autorisées, des tests, des aperçus de sites.
- **Créer des sites** : construction par l'agent, contrôle qualité (SEO, mobile, accessibilité, liens), aperçu local, paquet de déploiement (jamais publié seul).
- **Rechercher** sur le web avec sources datées, lire des pages, auditer un site public.
- **Naviguer** : navigateur piloté (pages JavaScript, champs de formulaires, captures) ; envoi d'un formulaire seulement avec votre accord.
- **Documents** : Markdown, HTML, DOCX, PDF, CSV, XLSX, JSON — vérifiés après création.
- **Organiser** : tâches (avec dépendances, pause, reprise, annulation), projets, rappels, planning, automatisations.
- **Mémoire** durable, consultable, corrigeable, exportable ; jamais de secret.
- **Agence** : CRM de CYPHER en lecture seule, revenus confirmés vs prévisions, prospection assistée (brouillons uniquement).
- **E-mails / agenda** via les connecteurs Gmail et Google Agenda (à activer) : lecture et brouillons, aucun envoi.
- **Voix** : dictée native macOS (corrigeable avant envoi), réponses lues, mains libres et mot d'activation « Jarvis » sur l'appareil (optionnels), micro coupé par défaut. Voir [docs/VOICE_AND_MEMORY.md](docs/VOICE_AND_MEMORY.md).

## Documentation
- [PROJECT_STATUS.md](PROJECT_STATUS.md) — état, critères de livraison et preuves
- [docs/INDEPENDENT_APP.md](docs/INDEPENDENT_APP.md) · [docs/INSTALLATION.md](docs/INSTALLATION.md) · [docs/STARTUP.md](docs/STARTUP.md) · [docs/AI_PROVIDERS.md](docs/AI_PROVIDERS.md) · [docs/DATA_AND_PRIVACY.md](docs/DATA_AND_PRIVACY.md)
- [docs/SETUP.md](docs/SETUP.md) — installation et commandes · [docs/USAGE.md](docs/USAGE.md) — utilisation
- [NEXT_STEPS.md](NEXT_STEPS.md) — prochaines actions
- [docs/SECURITY.md](docs/SECURITY.md) · [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- [docs/ENVIRONMENT_AUDIT.md](docs/ENVIRONMENT_AUDIT.md) · [docs/CONNECTORS.md](docs/CONNECTORS.md) · [docs/KNOWN_LIMITATIONS.md](docs/KNOWN_LIMITATIONS.md)
- [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) · [docs/ROADMAP.md](docs/ROADMAP.md) · [CHANGELOG.md](CHANGELOG.md)

## Commandes
```
python3 jarvis.py start | stop | status | open | backup | test | verifier | check | deps | dev | demo | build | install
```
