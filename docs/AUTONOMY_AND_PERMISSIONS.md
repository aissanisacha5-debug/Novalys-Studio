# Vocal instantané, autonomie et autorisations (v0.5)

## Conversation vocale
- **Envoi automatique** (par défaut) : la phrase part dès la fin de parole ; la transcription reste affichée. Mode manuel : Autorisations et autonomie > Voix.
- **Fin de phrase** : silence réglable (500 à 2000 ms, 900 ms par défaut) dans l'application.
- **Réponse en flux** : le fournisseur Claude envoie la réponse au fil de l'eau ; chaque phrase complète est lue dès qu'elle arrive. Avec un fournisseur sans flux, la réponse est lue d'un bloc (rien n'est simulé).
- **Préchauffage** : un processus du fournisseur est lancé à l'avance (aucune requête n'est envoyée tant qu'il n'a pas reçu de demande) : ~0,5 s gagnée.
- **Conversation continue** : JARVIS réécoute après chaque réponse ; « stop » pour finir ; « Couper le micro » arrête tout.
- **Interruption vocale** : pendant sa réponse, le micro reste ouvert ; si vous parlez, JARVIS se tait, annule la réponse en cours (« Réponse interrompue ») et traite votre nouvelle phrase. Ce que le micro capte de sa propre voix est reconnu et ignoré (comparaison avec le texte lu). Avec des haut-parleurs forts, un casque reste plus fiable.
- **Anti-doublon** : une même phrase n'est envoyée qu'une fois (8 s), jamais pendant un envoi en cours.

## Latence mesurée (application installée, 2026-10-12, Claude via Claude Code)
| Mesure | Résultats réels |
|---|---|
| Réception de la phrase → premier fragment du modèle | 1,1 à 1,8 s |
| Réception → début de la voix | 1,1 à 1,8 s |
| Réception → réponse complète | 1,8 à 2,4 s (réponse directe) ; 3,9 s avec un outil (heure) |
| Gain du préchauffage | ~0,5 s sur le premier fragment |
Non compris : la durée de votre phrase et le silence de fin (0,9 s par défaut), la reconnaissance vocale (non mesurée, faute de micro de test). Mesures consultables dans Autorisations et autonomie > Latence.

## Niveaux d'autonomie (Autorisations et autonomie)
| Niveau | Sans demander | Avec votre accord |
|---|---|---|
| Assisté | lecture, recherche | toute modification |
| Prudent | lecture, recherche, création et modification de fichiers, notes, documents, rangement | suppressions et actions à risque élevé |
| **Autonomie locale** (par défaut) | idem + suppression récupérable (corbeille JARVIS) d'un fichier ou d'un petit dossier (≤ 20 éléments) dans un dossier autorisé en écriture | suppressions massives, commandes sensibles, envois, publications, achats, réglages de sécurité |
| Autonomie avancée | idem, enchaînements plus longs (30 tours, 3 nouvelles tentatives) | idem |

Toujours soumis à accord : effacer beaucoup de fichiers, actions irréversibles, envois à des tiers, publication, achat, déploiement, transmission de données privées, réglages de sécurité, installation privilégiée. Si la tâche a lu un contenu qui contient des instructions suspectes (« ignore tes règles », « supprime tout »…), plus aucune action à risque élevé n'est automatique.

## Autorisations persistantes
- **Dossiers** lecture / écriture : conservés après redémarrage ; révocation ou passage en lecture seule immédiats ; ajout par le sélecteur de dossiers macOS (application) avec une confirmation. Une lecture ne devient jamais une écriture.
- **« Autoriser et ne plus demander ici »** sur une demande d'accord : crée une autorisation préalable limitée à un dossier (suppression) ou à une commande EXACTE (arguments compris ; jamais pour un interpréteur comme python3 ou node). Ignorée si la tâche a lu un contenu suspect. Jamais pour un envoi, une publication, un achat ou un réglage. Révocable à tout moment.
- **Outils** : chacun peut être désactivé ; un outil désactivé n'est plus proposé au modèle.
- **macOS** : Documents, Bureau, Téléchargements demandent une fois l'accord pour JARVIS ; macOS le conserve (Réglages Système > Confidentialité et sécurité > Fichiers et dossiers). Micro et Reconnaissance vocale : une fois, au premier usage.
- **Tout arrêter** : bouton rouge de la page (annule les tâches, coupe la voix, ferme le navigateur piloté), en plus d'« Interrompre » en haut de l'écran.
