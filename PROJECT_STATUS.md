# État du projet JARVIS

Mis à jour : 2026-10-12 · **Version 0.3.0** (prompt 4 : application indépendante)

## Application
- **Application compilée** : `~/Applications/JARVIS.app` (installée) et `Documents/CYPHER/JARVIS/dist/JARVIS.app`
- **Image d'installation** : `Documents/CYPHER/JARVIS/dist/JARVIS-0.3.0.dmg` (vérifiée par `hdiutil verify`)
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
