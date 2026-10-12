# Utiliser JARVIS

## L'essentiel
- **Écrire** : touche `/` puis Entrée. **Parler** : Alt+Espace (ou le micro). **Interrompre** : Échap ou le bouton rouge (arrête la tâche en cours, la voix et le micro). **Chercher partout** : ⌘K.
- Le **noyau** reflète l'état réel : en attente, écoute, réflexion, utilise un outil, tâche en cours, attend votre accord (doré), erreur (rouge).
- Chaque réponse indique un **état** : Confirmé (vérifié par le moteur), Partiel (une partie a échoué), Probable, Non vérifié, Bloqué, Échoué, Réponse directe ; et souvent une **prochaine action**.
- « Voir les étapes » montre chaque outil appelé, son résultat et sa vérification.

## Exemples de demandes
| Vous dites | JARVIS fait |
|---|---|
| « Crée un site premium pour un restaurant à Saint-Étienne » | crée `workspace/sites/…`, écrit les pages, lance le contrôle qualité jusqu'à 0 erreur, ouvre l'aperçu local, rend compte |
| « Organise les documents du dossier X » | liste, propose un classement, déplace sans rien écraser, vérifie chaque déplacement |
| « Trouve des entreprises… et prépare une proposition » | recherche réelle avec sources, audit des sites, doublons et oppositions vérifiés dans le CRM CYPHER, brouillons non envoyés |
| « Répare ce projet et vérifie qu'il fonctionne » | inspecte, lance les tests, corrige, relance, rapport |
| « Prépare mon planning de demain » | planning à partir de vos tâches et rappels réels, conflits signalés, aucun rendez-vous inventé |
| « Compare les solutions… et recommande » | recherche datée, sources, critères, incertitudes |
| « Prépare un rapport et ouvre-le » | rapport (md, pdf, docx) dans `workspace/rapports`, vérifié, ouvert |
| « Remplis le formulaire de contact de ce site avec… » | ouvre la page dans le navigateur piloté, remplit et relit les champs ; **l'envoi attend votre accord** |
| « Retiens que… » / « Oublie… » / « Qu'est-ce que tu sais sur ce projet ? » | mémoire durable avec source et raison ; contradictions signalées « à vérifier » |

## Accords
Une carte dorée « Confirmation requise » apparaît (conversation, rail de droite, page Sécurité) avec l'action, la cible, les conséquences et la réversibilité. **Autoriser** vaut pour cette action précise, une seule fois.

## Espaces
Accueil, Conversation, Mode vocal, Tâches, Projets, Fichiers, Documents, Navigateur, Recherche, Automatisations, Mémoire, Agenda, Rappels, E-mails, Prospection, Création de sites, Applications connectées, Notifications, Historique, Diagnostic, Sécurité, Paramètres, Modèles IA.

## Modes
Sécurité > Mode actif : conversation (aucune action), assistance (lecture seule), exécution supervisée (par défaut), autonomie limitée, développement, maintenance, vocal. Changer de mode demande un accord et n'ajoute aucun droit.

## Démonstration
`python3 jarvis.py demo` ouvre une instance séparée avec des données **fictives** (préfixe [DÉMO]) sur le port 8767, sans toucher à vos données.
