# Limites connues (v0.2, 2026-10-12)

Rien n'est caché : chaque limite est visible aussi dans l'interface (« indisponible », « non vérifié »).

## IA
- **Seul fournisseur actif : Claude via Claude Code** (abonnement). Pas de clé API. Chaque échange consomme l'usage de l'abonnement ; si la limite de l'abonnement est atteinte, JARVIS l'affiche comme une erreur du fournisseur.
- Latence : 4 à 15 s par tour de réflexion ; une tâche à plusieurs étapes prend donc de quelques secondes à quelques minutes.
- Ollama et l'API Anthropic sont implémentés mais **indisponibles** (non installé / pas de clé).
- Recherche sémantique (embeddings) : **non implémentée** ; la recherche plein texte (FTS5) est utilisée.
- Vision / analyse d'images : non implémentée.

## Voix
- Dictée : moteur de reconnaissance de Chrome (l'audio part chez Google pour la transcription). Fonctionne dans la fenêtre JARVIS (Chrome) après autorisation du micro par Sacha. **Non testée de bout en bout par moi** : je ne peux pas parler au micro.
- Synthèse : voix macOS locales (`say`), testée.
- Mot d'activation « Hey Jarvis » : **non implémenté** (aucune écoute permanente). Prévu dans l'architecture (réglage `voice.wake_word`, désactivé).

## Mac
- Pas de contrôle de l'interface des autres applications (accessibilité non accordée, volontairement). JARVIS sait ouvrir une application, un fichier, une adresse, notifier, parler.
- Notifications macOS envoyées via `osascript` : elles apparaissent sous « Éditeur de script » ; si rien ne s'affiche, autoriser dans Réglages Système > Notifications.
- Rappels et automatisations : ne tournent que lorsque JARVIS est ouvert (pas de lancement au démarrage du Mac sans votre accord).

## Navigateur
- Navigateur piloté (Chrome sans interface) : pages JavaScript, formulaires, liens, captures — **opérationnel** (testé sur httpbin.org). Profil vierge : pas d'accès aux sites où Sacha est connecté (volontaire).
- Téléchargement de fichiers par le navigateur : **non implémenté**.
- Sélecteurs CSS fournis par le modèle : peuvent échouer sur des sites complexes (erreur claire, rien n'est envoyé sans accord).
- Recherche : page publique DuckDuckGo ; si elle demande une vérification humaine, JARVIS s'arrête et le dit.

## Connecteurs
- Gmail / Google Agenda : désactivés par défaut dans JARVIS (un clic + confirmation pour activer). Lecture, recherche, brouillons, création d'événement avec confirmation. **Aucun envoi.**
- GitHub, Netlify, Vercel : non connectés (jeton absent). Le déploiement se limite à un paquet ZIP + checklist.
- Les connecteurs claude.ai passent par la CLI : les contenus d'e-mails transitent par Claude (comme pour CYPHER).

## Agence
- Le CRM vient de CYPHER en **lecture seule** ; la modification des prospects, offres et prix reste dans CYPHER (règle de validation par Sacha).
- Revenus « confirmés » = factures marquées payées dans CYPHER ; tout le reste est une prévision.

## Tests
- Tests réels : un défaut a été trouvé grâce à eux (avec le modèle haiku, environ 1 demande sur 3 échouait : le modèle tentait d'appeler les outils lui-même au lieu de les écrire dans sa réponse). Correction du prompt système, puis 6 essais sur 6 réussis. Le comportement d'un modèle reste variable ; le moteur signale honnêtement un échec (le test vérifie le fichier, pas la parole du modèle).
- Pas de test end-to-end automatisé de l'interface (Playwright absent) : l'interface a été vérifiée dans un navigateur réel, page par page, à la main et par script.

## Divers
- Une seule personne, un seul Mac ; pas d'accès distant ni mobile (prévu dans la feuille de route, avec authentification forte).
- Fenêtre : Chrome en mode application (pas d'application native Swift en v0.1).
- Python 3.9 système (LibreSSL 2.8.3) : suffisant aujourd'hui ; une version plus récente serait préférable à terme.
