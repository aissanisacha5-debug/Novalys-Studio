# Dépannage

| Symptôme | Cause probable | Solution |
|---|---|---|
| La fenêtre affiche « Service local injoignable » | JARVIS arrêté ou planté | Relancer `JARVIS.app` ; lire `data/logs/jarvis.log` |
| « Fournisseur IA indisponible : Claude Code non connecté » | Session Claude Code expirée | Ouvrir Terminal, lancer `claude`, se reconnecter, puis Modèles IA > Tester |
| Réponses très lentes | Modèle `sonnet` ou `opus` | Modèles IA : choisir `haiku` (plus rapide) |
| « Limite quotidienne d'appels IA atteinte » | Budget d'appels (300/jour par défaut) | Paramètres > Budget et limites (confirmation demandée) |
| Une tâche reste « Attend votre accord » | Action à risque élevé | Bandeau « À valider » à droite, page Sécurité ou la conversation : Autoriser / Refuser |
| Tâche « interrompue » après redémarrage | JARVIS fermé pendant l'exécution | Tâches > la tâche > Reprendre |
| Le micro ne marche pas | Autorisation Chrome ou macOS | Cliquer l'icône micro dans la fenêtre / Réglages Système > Confidentialité > Micro > Google Chrome |
| Pas de notification macOS | « Éditeur de script » non autorisé | Réglages Système > Notifications > Éditeur de script |
| Gmail « indisponible » | Connecteur désactivé dans JARVIS | Applications connectées > Gmail > Activé (confirmation), puis Tester |
| Navigateur piloté « n'a pas démarré » | Chrome absent ou bloqué | `python3 jarvis.py deps` ; fermer via Navigateur > Fermer le navigateur piloté, puis réessayer |
| Besoin d'aide extérieure | — | Diagnostic > **Copier le rapport** (expurgé : pas de chemins personnels, de contenus ni de secrets) |
| Vérifier l'installation | — | `python3 jarvis.py deps` puis `python3 jarvis.py check` |
| Port 8765 occupé | Autre programme | `JARVIS_PORT=8766 python3 jarvis.py start` |
| Erreur après mise à jour | Migration ou code | Diagnostic ; sinon restaurer la dernière sauvegarde (SETUP.md) |

Journal technique : `data/logs/jarvis.log`. Journal d'activité : page Historique (exportable).
