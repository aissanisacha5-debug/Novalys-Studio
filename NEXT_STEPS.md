# Prochaines étapes

## Pour Sacha (5 minutes, regroupées)
1. Ouvrir **JARVIS** (`~/Applications`) et cliquer **Autoriser** si macOS demande l'accès au dossier Documents.
2. Dans la fenêtre, cliquer le micro une fois et autoriser Chrome à l'utiliser (seulement si vous voulez la voix).
3. Facultatif : **Applications connectées > Gmail > Activé**, puis **Tester** (même chose pour Google Agenda).
Vérification : la page **Diagnostic** affiche le fournisseur IA « connecté » et 0 erreur.

## Pour le prochain développement (dans l'ordre)
1. Corriger les gênes remontées après une semaine d'usage réel.
2. Fenêtre native Swift + dictée `SFSpeechRecognizer` sur l'appareil (plus privé que la dictée Chrome).
3. Outils « remplir un formulaire » et « télécharger » avec confirmation.
4. Relier l'écriture du CRM aux commandes de CYPHER (avec validation), au lieu de la lecture seule.
5. Recherche sémantique si Ollama est installé.

## Reprendre le travail (règle de continuité)
1. Lire PROJECT_STATUS.md. 2. `python3 jarvis.py status`. 3. `python3 jarvis.py test`. 4. Choisir l'étape suivante ci-dessus. Ne pas considérer ce fichier comme preuve que le code fonctionne encore : relancer les tests.
