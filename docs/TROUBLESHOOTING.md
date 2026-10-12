# Dépannage

| Symptôme | Cause probable | Solution |
|---|---|---|
| macOS refuse d'ouvrir JARVIS | Application signée ad hoc (pas de certificat Apple) | Clic droit > Ouvrir > Ouvrir, ou Réglages Système > Confidentialité et sécurité > Ouvrir quand même |
| « Limite d'usage de l'abonnement Claude atteinte » | Quota de l'abonnement | Attendre l'heure indiquée, ou choisir un autre fournisseur (Modèles IA) ; la tâche se reprend ensuite |
| La fenêtre affiche « Le service JARVIS ne répond pas » | Service arrêté ou planté | Menu JARVIS > Redémarrer le service ; Aide > Ouvrir le journal |
| La fenêtre affiche « Service local injoignable » | JARVIS arrêté ou planté | Relancer `JARVIS.app` ; lire `data/logs/jarvis.log` |
| « Fournisseur IA indisponible : Claude Code non connecté » | Session Claude Code expirée | Ouvrir Terminal, lancer `claude`, se reconnecter, puis Modèles IA > Tester |
| Réponses très lentes | Modèle `sonnet` ou `opus` | Modèles IA : choisir `haiku` (plus rapide) |
| « Limite quotidienne d'appels IA atteinte » | Budget d'appels (300/jour par défaut) | Paramètres > Budget et limites (confirmation demandée) |
| Une tâche reste « Attend votre accord » | Action à risque élevé | Bandeau « À valider » à droite, page Sécurité ou la conversation : Autoriser / Refuser |
| Tâche « interrompue » après redémarrage | JARVIS fermé pendant l'exécution | Tâches > la tâche > Reprendre |
| Le micro ne marche pas | Autorisation macOS | Réglages Système > Confidentialité et sécurité > Microphone et Reconnaissance vocale > JARVIS |
| Pas de notification macOS | « Éditeur de script » non autorisé | Réglages Système > Notifications > Éditeur de script |
| Gmail « indisponible » | Connecteur désactivé dans JARVIS | Applications connectées > Gmail > Activé (confirmation), puis Tester |
| Navigateur piloté « n'a pas démarré » | Chrome absent ou bloqué | `python3 jarvis.py deps` ; fermer via Navigateur > Fermer le navigateur piloté, puis réessayer |
| Besoin d'aide extérieure | — | Diagnostic > **Copier le rapport** (expurgé : pas de chemins personnels, de contenus ni de secrets) |
| Vérifier l'installation | — | `python3 jarvis.py deps` puis `python3 jarvis.py check` |
| Port 8765 occupé | Autre programme | `JARVIS_PORT=8766 python3 jarvis.py start` |
| Erreur après mise à jour | Migration ou code | Diagnostic ; sinon restaurer la dernière sauvegarde (SETUP.md) |

Journal technique : `~/Library/Application Support/JARVIS/data/logs/jarvis.log` (menu Aide > Ouvrir le journal). Journal d'activité : page Historique (exportable).
