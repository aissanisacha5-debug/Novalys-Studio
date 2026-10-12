# Limites connues (v0.1, 2026-10-12)

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
- Lecture HTTP simple : les sites qui exigent JavaScript pour afficher leur contenu sont mal lus. Playwright n'est pas installé (Node absent).
- Pas de remplissage de formulaires ni de téléchargement automatisés en v0.1.
- Recherche : page publique DuckDuckGo ; si elle demande une vérification humaine, JARVIS s'arrête et le dit.

## Connecteurs
- Gmail / Google Agenda : désactivés par défaut dans JARVIS (un clic + confirmation pour activer). Lecture, recherche, brouillons, création d'événement avec confirmation. **Aucun envoi.**
- GitHub, Netlify, Vercel : non connectés (jeton absent). Le déploiement se limite à un paquet ZIP + checklist.
- Les connecteurs claude.ai passent par la CLI : les contenus d'e-mails transitent par Claude (comme pour CYPHER).

## Agence
- Le CRM vient de CYPHER en **lecture seule** ; la modification des prospects, offres et prix reste dans CYPHER (règle de validation par Sacha).
- Revenus « confirmés » = factures marquées payées dans CYPHER ; tout le reste est une prévision.

## Divers
- Une seule personne, un seul Mac ; pas d'accès distant ni mobile (prévu dans la feuille de route, avec authentification forte).
- Fenêtre : Chrome en mode application (pas d'application native Swift en v0.1).
- Python 3.9 système (LibreSSL 2.8.3) : suffisant aujourd'hui ; une version plus récente serait préférable à terme.
