# Données et confidentialité

## Où sont les données
| Quoi | Où |
|---|---|
| Application (code) | `~/Applications/JARVIS.app` — ne contient aucune donnée personnelle |
| Base (conversations, tâches, mémoire, projets, journal, réglages) | `~/Library/Application Support/JARVIS/data/jarvis.db` (SQLite) |
| Sauvegardes, versions précédentes de fichiers, corbeille, journaux | même dossier : `backups/`, `versions/`, `corbeille/`, `logs/` |
| Fichiers produits (sites, rapports, documents, brouillons) | `~/JARVIS` |
| Secrets (clés, jetons) | Trousseau macOS (service `studio.novalys.jarvis`) |
| CRM de CYPHER | `~/Documents/CYPHER/memoire` — **lecture seule**, jamais modifié par JARVIS |

Les données de la v0.2 (`Documents/CYPHER/JARVIS/data` et `workspace`) ont été **copiées** vers ces emplacements le 2026-10-12 ; l'ancien dossier n'a pas été supprimé.

## Ce qui sort du Mac
- Le texte envoyé au fournisseur IA choisi (contexte compact de la conversation, souvenirs pertinents, résultats d'outils). Avec un modèle local, rien ne sort.
- Les pages web consultées (requêtes vers les sites concernés).
- Dictée native : sur l'appareil quand macOS le permet ; sinon via les serveurs d'Apple. JARVIS n'enregistre aucun audio.
- Gmail/Agenda (si activés) : via les connecteurs claude.ai.

## Protection
- API locale sur 127.0.0.1 uniquement, jeton par démarrage, jamais exposée à Internet.
- Journaux expurgés (clés, jetons, mots de passe, numéros de carte). Le rapport de diagnostic copiable retire aussi les chemins personnels.
- La mémoire refuse les secrets ; les informations temporaires expirent seules.

## Vos droits sur vos données
- **Exporter** : Mémoire > Exporter (JSON) ; Conversation > Exporter (Markdown) ; Historique > Exporter le rapport.
- **Sauvegarder / restaurer** : Diagnostic > Sauvegardes (sauvegarde vérifiée ; restauration avec confirmation, l'état courant est d'abord sauvegardé).
- **Supprimer** : un souvenir (Oublier), la mémoire d'un projet, une conversation — chaque fois avec confirmation. Tout effacer : voir INSTALLATION.md > Désinstallation.
- **Rétention** du journal : Paramètres > Journal (180 jours par défaut).
