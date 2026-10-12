# Feuille de route

## v0.1 — livrée (2026-10-12)
Socle (API locale, SQLite, migrations, journal, sauvegardes), moteur d'agent avec 53 outils et vérification, permissions et confirmations, mémoire FTS, projets, tâches, automatisations, documents (md→pdf/docx/xlsx), recherche web et audit de site, création et contrôle de sites, voix (dictée Chrome + voix macOS), connecteurs Gmail/Agenda via Claude Code, interface Obsidian Emerald (23 espaces), 64 tests.

## v0.2 — livrée (2026-10-12, prompt 3)
Navigateur piloté (Chrome DevTools), état final recoupé avec les étapes, résultats partiels, prochaine action, lectures parallèles, mémoire temporaire et détection de contradictions, repli IA multi-fournisseurs et modèle par agent, diagnostic copiable et expurgé avec versions, scripts `verifier`/`check`/`deps`/`dev`/`demo`/`build`, migration 0002 testée, 76 tests.

## v0.3 — à faire ensuite (sans coût)
1. Utiliser JARVIS une semaine, corriger ce qui gêne (priorité absolue).
2. Fenêtre native Swift (WKWebView) + reconnaissance vocale native `SFSpeechRecognizer` sur l'appareil (confidentialité) — demande l'autorisation micro/dictée.
3. Mot d'activation local (après 2), désactivé par défaut.
4. Outil « télécharger un document autorisé » avec confirmation.
5. Écriture dans le CRM CYPHER via les commandes de CYPHER (après validation de Sacha), plutôt que de dupliquer le CRM.
6. Recherche sémantique si Ollama est installé (modèle d'embeddings léger).

## v0.4 — avec accord explicite
- Lancement automatique au démarrage du Mac (LaunchAgent).
- Envoi d'e-mails avec règles explicites (liste de destinataires validés, quotas, journal), après une période d'essai en brouillons.
- Déploiement Netlify/Vercel avec jeton (confirmation à chaque mise en ligne).
- Accès mobile sécurisé (tunnel authentifié), multi-appareils.

## Plus tard (si utile)
Agents spécialisés supplémentaires, vision, présentations, domotique (si réellement disponible), tableau de bord financier relié à la comptabilité réelle.
