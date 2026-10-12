# Installation, démarrage, mise à jour, désinstallation

JARVIS n'a **aucune dépendance à installer** : Python 3 (fourni par les outils en ligne de commande d'Apple), SQLite, Google Chrome (déjà présent) et Claude Code (déjà connecté).

## Démarrer
- **Double-clic sur `~/Applications/JARVIS.app`** (ou via Spotlight : « JARVIS »). Le service local démarre s'il ne tourne pas, puis la fenêtre s'ouvre.
- En ligne de commande : `python3 jarvis.py start` (dans `Documents/CYPHER/JARVIS`).
- Recréer le lanceur : `./scripts/creer-lanceur.sh`.

## Arrêter
- Dans JARVIS : **Diagnostic > Arrêter JARVIS** (arrêt propre : tâches annulées, voix coupée, serveurs d'aperçu arrêtés).
- Ou `python3 jarvis.py stop`.

## Contrôle de santé
`python3 jarvis.py status` affiche chaque composant (base, API, planificateur, fournisseur IA, outils, voix, sauvegardes…). Même chose dans **Diagnostic**.

## Tests
`python3 jarvis.py test` (62 tests sans IA réelle). Tests avec Claude réel : `JARVIS_TEST_REEL=1 python3 -m unittest tests.test_reel`.

## Mise à jour
1. `python3 jarvis.py backup` (sauvegarde vérifiée).
2. Remplacer les fichiers de `jarvis/` et `web/` (ou `git pull` si un dépôt distant est ajouté).
3. `python3 jarvis.py test`, puis redémarrer. Les migrations de base s'appliquent seules au démarrage, après une sauvegarde automatique.

## Restauration
Diagnostic > Sauvegardes > **Restaurer** (confirmation demandée) : l'état actuel est d'abord sauvegardé, la restauration s'applique au redémarrage suivant. En ligne de commande, en dernier recours : arrêter JARVIS, copier `jarvis.db` d'une archive `data/backups/*.zip` vers `data/restauration-en-attente.db`, redémarrer.

## Données
`data/` (non versionné) : `jarvis.db`, `token`, `backups/`, `versions/` (versions précédentes des fichiers modifiés), `corbeille/`, `logs/`. `workspace/` : fichiers produits (sites, rapports, documents, brouillons).

## Désinstaller
1. Arrêter JARVIS.
2. Supprimer `~/Applications/JARVIS.app`.
3. Facultatif : supprimer les secrets du trousseau (Trousseau d'accès, service `studio.novalys.jarvis`) et le dossier `Documents/CYPHER/JARVIS` (après avoir gardé ce qui vous intéresse dans `workspace/` et `data/backups/`).
Rien n'est installé ailleurs (aucun service système, aucun lancement automatique).
