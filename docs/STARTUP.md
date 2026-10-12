# Démarrage, arrière-plan et arrêt

## Lancer JARVIS sans Claude Code ni terminal
Double-clic sur **JARVIS** (Applications, Dock ou Spotlight). L'application démarre son service local si besoin, puis affiche l'interface. Aucun terminal, aucun navigateur, aucune autre application n'est nécessaire.

En ligne de commande (développeurs) : `python3 jarvis.py start` ouvre l'application installée ; `python3 jarvis.py dev` lance une instance de développement séparée (port 8766).

## États
| Situation | Ce qui se passe |
|---|---|
| Fenêtre fermée (⌘W) | L'application et le service continuent ; un clic sur l'icône rouvre la fenêtre |
| Application quittée (⌘Q) | Le service s'arrête proprement (tâches annulées, voix coupée, aperçus arrêtés) — **sauf** si le démarrage automatique est activé |
| Service arrêté | Rien ne tourne : ni rappels, ni automatisations, ni tâches |
| Mac en veille | Rien ne s'exécute pendant la veille ; les automatisations dues s'exécutent au réveil |
| Mac éteint | Rien ne s'exécute ; au redémarrage, les tâches en cours deviennent « interrompues » et se reprennent sans refaire les étapes faites |

L'état réel du service (processus, lancé par qui, fenêtres connectées, emplacements) est visible dans **Paramètres > Service et démarrage** et dans **Diagnostic**.

## Démarrage automatique (optionnel)
Paramètres > Service et démarrage > activer l'option, puis **confirmer**. JARVIS installe un agent de lancement utilisateur (`~/Library/LaunchAgents/studio.novalys.jarvis.service.plist`, sans droits administrateur) : le service démarre à l'ouverture de session et redémarre après un plantage (pas après un arrêt volontaire). Désactivation au même endroit (l'agent est retiré). Désactivé par défaut.

## Arrêt
- Menu JARVIS > Quitter, ou Diagnostic > **Arrêter JARVIS**, ou `python3 jarvis.py stop`.
- Menu JARVIS > **Redémarrer le service** en cas de problème.

## Journaux et plantages
`~/Library/Application Support/JARVIS/data/logs/jarvis.log` (menu Aide > Ouvrir le journal) ; `service.log` pour le service lancé au démarrage. Si le service ne répond pas, la fenêtre l'affiche avec la marche à suivre au lieu d'une page blanche.
