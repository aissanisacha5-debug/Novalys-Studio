# Installation

## Pour utiliser JARVIS
1. Ouvrir `JARVIS-0.3.0.dmg` (dans `dist/`) et glisser **JARVIS** dans Applications (ou `~/Applications`).
2. Ouvrir JARVIS. L'application est signée « ad hoc » (sans certificat Apple payant) : si macOS refuse, clic droit sur JARVIS > **Ouvrir** > Ouvrir, ou Réglages Système > Confidentialité et sécurité > **Ouvrir quand même**.
3. Choisir un fournisseur IA dans **Modèles IA** (voir AI_PROVIDERS.md). Sur ce Mac, Claude via Claude Code est déjà prêt.
4. Facultatif : autoriser le micro et la reconnaissance vocale au premier clic sur le micro.

Prérequis : macOS 13 ou plus récent ; Python 3 d'Apple (`/usr/bin/python3`, installé avec les outils en ligne de commande : `xcode-select --install` s'il manque). Google Chrome seulement pour le PDF et le navigateur piloté.

## Pour construire depuis le code
```
python3 jarvis.py deps      # prérequis (rien à installer sur ce Mac)
python3 jarvis.py build     # vérification + tests + dist/JARVIS.app + dist/JARVIS-<version>.dmg
python3 jarvis.py install   # installe dans ~/Applications
```
La compilation choisit automatiquement un SDK macOS compatible avec le compilateur Swift installé.

## Mise à jour
`git pull` (ou nouveau code), puis `python3 jarvis.py build && python3 jarvis.py install`. Les données ne sont jamais dans l'application : elles sont conservées. Les migrations de base s'appliquent au démarrage après une sauvegarde automatique.

## Désinstallation
1. Quitter JARVIS (menu JARVIS > Quitter).
2. Paramètres > Service et démarrage : désactiver le démarrage automatique s'il est activé.
3. Supprimer `~/Applications/JARVIS.app`.
4. Facultatif (efface vos données) : `~/Library/Application Support/JARVIS`, `~/JARVIS`, et les secrets « studio.novalys.jarvis » dans Trousseau d'accès. Pensez à exporter la mémoire et à garder une sauvegarde avant.
