# Limites connues (v0.5, 2026-10-12)

## Vocal instantané (v0.5)
- Interruption vocale, conversation continue et reconnaissance : non testées au micro (je ne peux pas parler). La chaîne « phrase reçue → réponse lue » est testée en réel dans l'application installée (3 échanges enchaînés).
- Le filtre d'écho compare les mots entendus au texte lu : efficace mais pas infaillible avec des haut-parleurs forts ; un casque est plus sûr.
- Dans un navigateur (hors application), la fin de phrase est décidée par le navigateur (délai non réglable).

## Voix (v0.4)
- Dictée, mains libres et mot d'activation : **implémentés et compilés, non testés au micro** (je ne peux ni parler ni accorder l'autorisation micro à la place de Sacha). Le mot d'activation exige la reconnaissance du français sur l'appareil ; si le Mac ne la propose pas, l'option se désactive avec un message.
- Pas de détection de mot d'activation sans application ouverte (l'écoute vit dans la fenêtre JARVIS).
- Synthèse vocale testée (lecture puis arrêt immédiat, volume réglable).

## Application
- Signature **ad hoc** : pas de certificat Apple Developer ni de notarisation (payant) ; premier lancement depuis le .dmg à autoriser (clic droit > Ouvrir).
- Python 3 d'Apple requis (non embarqué) ; architecture Apple Silicon (arm64) uniquement.
- Je n'ai pas pu regarder la fenêtre native moi-même (pas d'accès à l'écran) : son fonctionnement est prouvé par la connexion de l'interface au service (« fenêtres connectées : 1 ») et par une vraie conversation faite à travers le service lancé par l'application. L'interface elle-même a été vérifiée page par page dans un navigateur.
- La dictée native n'a pas été essayée au micro (je ne peux pas parler).

Rien n'est caché : chaque limite est visible aussi dans l'interface (« indisponible », « non vérifié »).

## IA
- **Fournisseur actif : Claude via Claude Code** (abonnement, en arrière-plan). Limite d'usage atteinte le 2026-10-12 pendant les tests : JARVIS l'affiche clairement et met la tâche en attente. Autres fournisseurs (compatible OpenAI, Anthropic, Ollama) prêts mais non configurés.
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
- Rappels et automatisations : tournent tant que le service tourne ; avec le démarrage automatique (optionnel), même application quittée. Jamais pendant la veille ni Mac éteint.

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
- Fenêtre : application native (WebKit) depuis la v0.3 ; Chrome reste utilisé pour le PDF et le navigateur piloté.
- Python 3.9 système (LibreSSL 2.8.3) : suffisant aujourd'hui ; une version plus récente serait préférable à terme.
