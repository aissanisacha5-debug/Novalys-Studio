# Prochaines étapes

## Pour Sacha (regroupé, 5 minutes)
1. Double-cliquer **JARVIS** dans `~/Applications` ; si macOS demande l'accès au dossier **Documents**, cliquer **Autoriser**. Vérification : la fenêtre s'ouvre et Diagnostic affiche « Fournisseur IA actif : connecté ».
2. Facultatif, voix : cliquer le micro, autoriser Chrome. Vérification : bandeau vert « Microphone actif » et votre phrase transcrite.
3. Facultatif, e-mails/agenda : Applications connectées > Gmail et Google Agenda > Activé, puis **Tester**. Vérification : « OK — appel constaté ».

## Développement suivant (v0.3)
1. Corriger ce qui gêne après une semaine d'usage réel.
2. Fenêtre native Swift + dictée `SFSpeechRecognizer` sur l'appareil (plus privée), puis mot d'activation local.
3. Téléchargement de documents par le navigateur piloté (avec accord).
4. Écriture dans le CRM CYPHER via les commandes de CYPHER (avec validation).
5. Recherche sémantique si Ollama est installé.

## Reprendre le travail
1. Lire PROJECT_STATUS.md. 2. `python3 jarvis.py deps` puis `python3 jarvis.py check`. 3. `JARVIS_TEST_REEL=1 python3 -m unittest tests.test_reel`. 4. Choisir l'étape suivante. Un ancien rapport ne prouve pas que le code fonctionne encore : relancer les tests.
