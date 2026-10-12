# État du projet JARVIS

Mis à jour : 2026-10-12 · **Version 0.5.0** (prompt 6 : vocal instantané, autonomie, autorisations)

## Prompt 6 — résultats vérifiés
| Fonctionnalité | État | Preuve |
|---|---|---|
| Envoi automatique de la phrase (sans bouton) | opérationnel | 3 échanges « voix » enchaînés dans l'application installée, contexte conservé |
| Réponse lue pendant la génération (flux réel) | opérationnelle | premier son 1,1–1,8 s, réponse complète 1,8–2,4 s (3,9 s avec un outil) |
| Préchauffage du fournisseur | opérationnel | ~0,5 s gagnée (1,6 → 1,1 s au premier fragment) |
| Conversation continue, interruption vocale, anti-doublon | implémentés ; non testés au micro | logique testée (filtre d'écho, segments) |
| Niveaux d'autonomie, suppression récupérable automatique, confirmations conservées pour le risque élevé | opérationnels | test_autonomie |
| Autorisations persistantes, révocation, « ne plus demander ici », outils désactivables | opérationnelles | test_autonomie (redémarrage compris) |
| Contenu suspect → retour aux confirmations | opérationnel | test_contenu_contamine |
| Chaîne d'actions locales sans confirmation | opérationnelle | test (4 outils, 0 confirmation) |
| Tout arrêter | opérationnel | test (tâche annulée « réponse interrompue ») |
| `python3 jarvis.py check` | **103 tests, 0 échec** | 2026-10-12 |

Version 0.4.0 (prompt 5 : assistant vocal, mémoire, tâches) — base : v0.3 application indépendante

## Prompt 5 — résultats vérifiés
| Fonctionnalité | État | Preuve |
|---|---|---|
| Conversation dans l'application (moteur IA réel) | opérationnelle | application installée v0.4 : « Quel jour sommes-nous ? » → outil date_heure → « lundi 12 octobre 2026 » (confirmé) |
| Transcription corrigeable avant envoi (cadre du Mode vocal / zone de saisie) | opérationnelle (saisie) ; dictée non testée au micro | envoi depuis le cadre testé : « Il est 20 h 32 » |
| Synthèse vocale + arrêt immédiat | opérationnelle | test automatique (lecture, arrêt, état « parle ») |
| Mains libres | implémenté, non testé au micro | — |
| Mot d'activation « Jarvis » (sur l'appareil uniquement) | implémenté et compilé, non testé au micro | — |
| Mémoire : consulter, ajouter, modifier, supprimer, désactiver ; temporaire effacée avec la conversation | opérationnelle | tests test_assistant, test_core |
| Tâches : créer, modifier (échéance, priorité), terminer, annuler, notifier l'échéance | opérationnelle | test_assistant (notification unique), migration 0003 sur la base réelle |
| Outils date/heure, notes, scripts approuvés, réglages (non sensibles seulement) | opérationnelle | test_assistant |
| États visuels (prêt, écoute, transcription, réflexion, outil, parle, terminé, erreur, service indisponible) | opérationnelle | interface vérifiée dans le navigateur |
| `python3 jarvis.py check` | **93 tests, 0 échec**, 3 ignorés | 2026-10-12 |


## Application
- **Application compilée** : `~/Applications/JARVIS.app` (installée, v0.5.0) et `Documents/CYPHER/JARVIS/dist/JARVIS.app`
- **Image d'installation** : `Documents/CYPHER/JARVIS/dist/JARVIS-0.5.0.dmg` (vérifiée par `hdiutil verify`)
- **Lancer sans Claude Code** : double-clic sur JARVIS (Dock, Applications, Spotlight). L'application démarre son service local (127.0.0.1:8765) et affiche l'interface dans sa propre fenêtre.
- **Compiler** : `python3 jarvis.py build` · **Installer** : `python3 jarvis.py install` · **Tests** : `python3 jarvis.py check` · **Développement** : `python3 jarvis.py dev`

## Dépendances encore nécessaires
- Python 3 d'Apple (`/usr/bin/python3`) — présent.
- Un fournisseur IA : Claude Code connecté (présent, utilisé en arrière-plan) **ou** une API compatible OpenAI / Anthropic **ou** un modèle local.
- Google Chrome pour le PDF et le navigateur piloté — présent.
- Aucune clé obligatoire. Facultatif : clés API (Sécurité > Secrets), Gmail/Agenda à activer.

## Tests exécutés (2026-10-12)
| Test | Résultat |
|---|---|
| `python3 jarvis.py check` (vérification statique + 85 tests) | **OK**, 0 échec, 3 ignorés (tests réels sans `JARVIS_TEST_REEL`, réseau httpbin indisponible) — 2 passages |
| Compilation Swift + assemblage + signature ad hoc (`codesign --verify --deep --strict`) | OK |
| Image disque (`hdiutil verify`) | OK |
| Installation dans ~/Applications puis lancement par `open` avec environnement vierge | OK : service lancé par l'application, interface connectée (1 fenêtre) |
| Conversation réelle depuis l'application installée | OK : fichier créé, relu, état « confirmé » (Claude sonnet, 2,3 s pour le test fournisseur) |
| Fournisseur en limite d'usage | OK : message clair, tâche « bloquée » avec prochaine action (constaté en réel) |
| Fermeture (SIGTERM = Quitter) | OK : service arrêté proprement |
| Migration des données v0.2 → Application Support | OK : copie, ancien dossier conservé, dossiers autorisés mis à jour |
| Absence de lien vers une interface de chatbot | OK (test automatique) |
| Secrets non suivis par Git | OK (`verifier`) |

**Non exécutés** : dictée au micro (je ne peux pas parler) ; observation visuelle de la fenêtre native (pas d'accès à l'écran : preuve indirecte par la connexion de l'interface) ; démarrage automatique réel au login (option non activée, plist testé sans chargement) ; lancement depuis le .dmg sur un autre Mac.

## État par fonctionnalité
| Fonctionnalité | État |
|---|---|
| Application native, fenêtre, icône, menus, arrêt propre | opérationnelle |
| Conversation dans l'application (moteur JARVIS) | opérationnelle |
| Tâches, orchestrateur, reprise, annulation | opérationnelle |
| Mémoire, projets, rappels, automatisations | opérationnelle |
| Outils fichiers, terminal, documents, sites, web, navigateur piloté | opérationnelle |
| Permissions, confirmations, journal, diagnostic, sauvegardes | opérationnelle |
| Données séparées + migration | opérationnelle |
| Service en arrière-plan + démarrage automatique | partielle (option prête et testée sans chargement ; non activée) |
| Fournisseur Claude (via Claude Code) | opérationnelle (soumise aux limites de l'abonnement) |
| Fournisseurs compatible OpenAI / Anthropic / Ollama | non configurées (code testé avec un serveur local de test) |
| Dictée native | non testée au micro |
| Gmail / Google Agenda | non configurées |
| Signature Apple / notarisation | indisponible (compte Apple Developer payant) |

## Étapes manuelles restantes (Sacha)
1. Facultatif : si macOS demande à JARVIS l'accès au dossier Documents, l'autoriser (lecture du CRM CYPHER).
2. Facultatif : essayer le micro (autoriser micro et reconnaissance vocale).
3. Facultatif : Paramètres > Service et démarrage > démarrage automatique ; Modèles IA > fournisseur de remplacement.

Historique des versions : CHANGELOG.md. Limites : docs/KNOWN_LIMITATIONS.md.
