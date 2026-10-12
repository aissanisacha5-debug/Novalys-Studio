# Journal des versions

## 0.5.0 — 2026-10-12 (prompt 6)
- Vocal : envoi automatique par défaut (mode manuel en option), fin de phrase réglable, réponse lue phrase par phrase pendant la génération (flux réel du fournisseur), préchauffage du fournisseur, interruption vocale avec filtre d'écho, anti-doublon, réponse interrompue proprement.
- Latence mesurée et affichée (premier fragment, premier son, total).
- Autonomie : niveaux assisté / prudent / locale (défaut) / avancée ; suppressions récupérables automatiques en autonomie locale ; contenu suspect → retour aux confirmations.
- Autorisations : page « Autorisations et autonomie » (voix, niveau, dossiers, autorisations préalables, outils, historique, latence, tout arrêter) ; révocation immédiate ; « ne plus demander ici » limité à un périmètre ; sélecteur de dossiers macOS ; outils désactivables.

## 0.4.0 — 2026-10-12 (prompt 5)
- Voix : transcription affichée en direct et corrigeable avant envoi (ou envoi automatique), mains libres (micro rouvert après chaque réponse lue, « stop » pour sortir), mot d'activation « Jarvis » natif avec reconnaissance SUR L'APPAREIL uniquement, écoute suspendue pendant que JARVIS parle, « Couper le micro » arrête toute écoute.
- États du noyau : prêt, écoute, transcription, réflexion, outil, tâche, JARVIS parle, accord, terminé, erreur, service indisponible.
- Mémoire : désactivable ; informations temporaires liées à une conversation et effacées avec elle ; règles de mémorisation (hypothèses, données sensibles).
- Tâches : modification (titre, échéance avec heure, priorité), notification d'échéance.
- Outils : date et heure, notes, scripts approuvés, consultation et modification des réglages non sensibles.
- Fournisseur actif affiché dans la conversation ; migration 0003.

## 0.3.0 — 2026-10-12 (prompt 4)
- Application macOS native `JARVIS.app` (Swift, WebKit) : fenêtre, icône, menus, téléchargements, liens externes vers le navigateur, page d'état si le service ne répond pas, arrêt propre (y compris SIGTERM).
- Image disque `JARVIS-<version>.dmg` vérifiée ; construction reproductible (`build`), installation (`install`) avec conservation de l'ancienne version.
- Code, données (`~/Library/Application Support/JARVIS`) et espace de travail (`~/JARVIS`) séparés ; migration par copie, sans suppression.
- Service local : états documentés, démarrage automatique optionnel (LaunchAgent, confirmation), informations de service dans Paramètres.
- Dictée native macOS (Speech, sur l'appareil quand possible).
- Fournisseur « compatible OpenAI », erreurs d'API normalisées (401, 429, 5xx), limite d'abonnement détectée → tâche bloquée avec prochaine action, test du fournisseur actif.
- Correctif : la CLI Claude attendait une autorisation macOS à cause d'un dossier courant hérité ; environnement minimal et explicite.
- 85 tests, 0 échec ; conversation réelle validée depuis l'application installée.

## 0.2.0 — 2026-10-12 (prompt 3)
- Navigateur piloté (Chrome sans interface, protocole DevTools) : pages JavaScript, champs, remplissage vérifié, liens, captures ; envoi de formulaire avec accord ; champs sensibles refusés.
- Moteur : état final recoupé avec les étapes réelles (partiel / non vérifié / échoué), prochaine action, lectures en parallèle.
- Mémoire : informations temporaires avec expiration, détection de contradictions (« à vérifier »).
- IA : fournisseur de remplacement, modèle par agent, chaîne de repli journalisée.
- Diagnostic : versions, migrations, navigateur ; rapport copiable expurgé.
- Outillage : `verifier` (syntaxe 3.9, imports, JS, CSS, secrets), `check`, `deps`, `dev`, `demo` (données fictives séparées), `build`.
- Migration 0002 (testée sur une base v0.1 et appliquée à la base réelle avec sauvegarde).
- Design : couleurs du noyau lues dans les jetons ; plus aucune couleur codée en dur hors de tokens.css.
- 76 tests (73 hors ligne dont 2 de navigateur réseau, 3 avec Claude réel).

## 0.1.0 — 2026-10-12
Première version fonctionnelle.
- Socle : API locale (127.0.0.1, jeton, contrôle hôte/origine), SQLite + migrations versionnées, configuration versionnée, journal expurgé, flux temps réel.
- Moteur d'agent JSON vérifié, 12 profils d'agents spécialisés, délégation, limites (tours, durée, échecs, boucles, idempotence).
- 53 outils (fichiers, terminal, web, sites, documents, tâches, mémoire, projets, rappels, rapports, e-mails, agenda, Mac, agence).
- Permissions par mode, dossier, risque ; confirmations à usage unique.
- Fournisseurs : Claude Code (actif), Ollama, API Anthropic ; budget et usage.
- Automatisations (6 déclencheurs, 7 actions), rappels, notifications macOS.
- Sauvegardes vérifiées, restauration, diagnostic.
- Interface « Obsidian Emerald » : 23 espaces, noyau visuel relié aux états réels, voix.
- 64 tests (62 hors ligne + 2 avec Claude réel).
