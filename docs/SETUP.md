# Installation et configuration

JARVIS est une **application web locale** (service Python + interface dans une fenêtre Chrome dédiée) avec un lanceur macOS. Ce n'est pas un installateur natif.

## Commandes exactes (dans `Documents/CYPHER/JARVIS`)

| Étape | Commande |
|---|---|
| 1. Installer les dépendances | **aucune** : `python3 jarvis.py deps` vérifie les prérequis déjà présents (Python ≥ 3.9, SQLite FTS5, Claude Code, Chrome, outils macOS) |
| 2. Configurer les variables | aucune obligatoire ; options dans `.env.example` (`JARVIS_PORT`…). Les clés éventuelles vont dans le trousseau via l'interface (Sécurité > Secrets) |
| 3. Initialiser la base | automatique au premier démarrage (migrations `jarvis/migrations/*.sql`, sauvegarde avant chaque migration) |
| 4. Mode développement | `python3 jarvis.py dev` → http://127.0.0.1:8766 (données séparées `data-dev/`, rechargement du backend à chaque modification) |
| 5. Tests | `python3 jarvis.py check` (vérification statique + tests) ; tests avec Claude réel : `JARVIS_TEST_REEL=1 python3 -m unittest tests.test_reel` |
| 6. Construire | `python3 jarvis.py build` (check, puis création/mise à jour de `~/Applications/JARVIS.app`) |
| 7. Lancer | double-clic sur **JARVIS** (`~/Applications`) ou `python3 jarvis.py start` → http://127.0.0.1:8765 |

Autres commandes : `status` (santé), `stop` (arrêt propre), `open` (fenêtre), `backup` (sauvegarde vérifiée), `demo` (données **fictives** séparées, port 8767), `verifier` (vérification statique seule).

## Configuration recommandée (une fois)
1. Premier lancement par l'icône : si macOS demande l'accès au dossier **Documents**, cliquer **Autoriser**.
2. Voix : autoriser le micro dans la fenêtre JARVIS au premier clic sur le micro.
3. E-mails/agenda (facultatif) : Applications connectées > Gmail / Google Agenda > Activé (confirmation), puis **Tester**.
4. Notifications (facultatif) : Réglages Système > Notifications > Éditeur de script > autoriser.

## Reconstruction reproductible
Le dépôt Git local contient tout le code ; `data/` et `workspace/` ne sont jamais suivis. Sur un autre Mac : copier le dossier (ou cloner), `python3 jarvis.py deps`, `python3 jarvis.py build`, puis restaurer éventuellement une sauvegarde (`data/backups/*.zip`, voir ci-dessous).

## Mise à jour
1. `python3 jarvis.py backup` ; 2. remplacer le code (`git pull` si un dépôt distant est ajouté) ; 3. `python3 jarvis.py check` ; 4. `python3 jarvis.py stop && python3 jarvis.py start`. Les migrations s'appliquent seules après une sauvegarde automatique (`data/backups/*-avant-migration.db`).

## Restauration
Diagnostic > Sauvegardes > **Restaurer** (confirmation) : l'état actuel est d'abord sauvegardé ; la restauration s'applique au redémarrage. En dernier recours : arrêter JARVIS, extraire `jarvis.db` d'une archive `data/backups/*.zip` vers `data/restauration-en-attente.db`, redémarrer.

## Données
`data/` : `jarvis.db`, `token` (600), `backups/`, `versions/` (versions précédentes de fichiers), `corbeille/`, `logs/`, `navigateur-pilote/` (profil séparé). `workspace/` : sites, rapports, documents, brouillons, captures.

## Désinstallation
Arrêter JARVIS, supprimer `~/Applications/JARVIS.app`, puis (facultatif) les secrets du trousseau (service `studio.novalys.jarvis`) et le dossier `JARVIS`. Rien d'autre n'est installé (aucun service système, aucun lancement automatique).
