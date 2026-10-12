# Voix, mains libres et mémoire (v0.4)

## Utiliser la voix dans l'application
| Action | Comment |
|---|---|
| Parler une fois | bouton micro (ou Alt+Espace). Un bandeau vert « Microphone actif » s'affiche ; la transcription apparaît en direct |
| Corriger avant d'envoyer | par défaut, la transcription est placée dans la zone de saisie (ou dans le cadre « Transcription » du Mode vocal) : corrigez, puis Entrée |
| Envoyer sans relire | Mode vocal > « Envoyer la transcription automatiquement » |
| Entendre les réponses | Mode vocal > « Lire les réponses à voix haute » ; voix, volume et vitesse dans le même écran ou Paramètres > Voix |
| Arrêter la lecture | « Arrêter la lecture », Échap, ou le bouton rouge Interrompre (coupe aussi le micro et les tâches) |
| Mains libres | Mode vocal > « Mains libres » : JARVIS lit sa réponse puis rouvre le micro. Dites « stop » (ou « terminé ») pour sortir |
| Mot d'activation | Mode vocal > « Mot d'activation Jarvis » : bandeau doré permanent ; dites « Jarvis, … » |
| Tout couper | « Couper le micro » dans le bandeau : arrête l'écoute, les mains libres et le mot d'activation |

États affichés par le noyau et le badge : Prêt, Écoute active, Transcription en cours, Réflexion, Utilise un outil, Tâche en cours, JARVIS parle, Attend votre accord, Terminé, Erreur, Service indisponible.

## Moteurs et confidentialité
- **Dictée (application)** : reconnaissance vocale de macOS (framework Speech). Sur l'appareil quand le Mac le permet ; sinon, pour le bouton micro seulement, via Apple.
- **Mot d'activation** : uniquement si la reconnaissance **sur l'appareil** est disponible pour le français. Sinon JARVIS le dit et désactive l'option : aucune écoute continue n'est envoyée sur Internet. Les sessions de reconnaissance sont relancées toutes les 50 s ; l'écoute est suspendue pendant que JARVIS parle (il ne s'entend pas lui-même).
- **Synthèse** : voix macOS locales (`say`).
- **Dans un navigateur** (hors application) : dictée par le moteur du navigateur ; mains libres possible ; pas de mot d'activation.
- Premier usage : macOS demande l'autorisation **Microphone** et **Reconnaissance vocale** pour JARVIS.

## Mémoire
- Types : préférence, information personnelle, objectif, projet, décision, tâche, résultat, instruction, connaissance, opération, résumé, référence, **temporaire**. Nature : fait, préférence ou **hypothèse** (ce que JARVIS déduit n'est jamais un fait). Statut : valide, à vérifier (contradiction détectée), obsolète.
- **Temporaire** : expire (7 jours par défaut) ; si elle naît dans une conversation, elle est **effacée avec cette conversation**. Effacer une conversation ne touche pas au reste de la mémoire.
- **Désactiver la mémorisation** : Mémoire > interrupteur. JARVIS consulte encore la mémoire mais n'ajoute plus rien ; vous pouvez toujours ajouter vous-même.
- Consulter, ajouter, corriger, oublier, exporter, importer : page Mémoire. « Qu'as-tu retenu ? » dans la conversation : JARVIS cite chaque information avec sa source et sa raison.
- Jamais de secret ; jamais de donnée sensible sans demande explicite.

## Tâches et rappels
- Créer, modifier (titre, échéance date et heure, priorité), terminer, annuler, reprendre : page Tâches ou en le demandant.
- Notification macOS à l'échéance d'une tâche ou d'un rappel **si le service JARVIS tourne** (application ouverte, ou démarrage automatique activé). Rien pendant la veille ou Mac éteint : l'échéance manquée est notifiée au réveil / au prochain démarrage.
- Historique d'exécution : page de la tâche (étapes, outils, vérifications, journal).

## Outils ajoutés en v0.4
`date_heure`, `note_creer` (~/JARVIS/notes), `tache_modifier`, `script_executer` (scripts approuvés dans Paramètres, avec confirmation à l'ajout), `parametres_consulter`, `parametre_modifier` (réglages non sensibles seulement : voix, volume, vitesse, lecture auto, détail, animations, notifications).
