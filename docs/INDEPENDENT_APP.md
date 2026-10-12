# JARVIS, application indépendante (v0.3)

## Ce qui a changé
| Avant (v0.2) | Maintenant (v0.3) |
|---|---|
| Fenêtre Chrome en mode application, lancée par un script | **Application macOS native** `JARVIS.app` (Swift + WebKit) : fenêtre, icône, menus, raccourcis propres |
| Code et données dans `Documents/CYPHER/JARVIS` | Code **dans l'application** ; données dans `~/Library/Application Support/JARVIS` ; fichiers produits dans `~/JARVIS` |
| Dictée par Chrome (audio envoyé à Google) | **Dictée native macOS** (Speech, sur l'appareil quand c'est possible) |
| Un seul fournisseur IA | Fournisseurs interchangeables : Claude (via Claude Code), API Anthropic, **tout service compatible OpenAI** (Mistral, OpenAI, LM Studio, Ollama), Ollama ; fournisseur de remplacement |
| Service lancé à la main | Service démarré par l'application ; **démarrage automatique optionnel** (LaunchAgent) |

## Audit des dépendances à Claude
- **Interface** : aucun lien, bouton ni redirection vers claude.ai ou une autre interface de chatbot (vérifié par le test `test_aucun_renvoi_vers_une_interface_de_chatbot`). La fenêtre n'affiche que les pages locales de JARVIS ; tout autre lien s'ouvre dans le navigateur par défaut.
- **Moteur** : la conversation, l'orchestrateur, la mémoire, les outils et les permissions sont ceux de JARVIS. Le fournisseur IA ne fait que générer du texte, en arrière-plan.
- **Claude conservé comme fournisseur optionnel** : « Claude (via Claude Code) » réutilise la connexion de ce Mac à l'abonnement Claude. C'est une dépendance **en arrière-plan** (la CLI doit être installée et connectée), jamais une interface à ouvrir. Il peut être remplacé dans Modèles IA.
- **Gmail / Google Agenda** passent par les connecteurs claude.ai de Claude Code : optionnels, désactivés par défaut.

## Architecture
```
JARVIS.app (Swift)  ── démarre / arrête ──>  service Python (127.0.0.1:8765)
  WKWebView  <── interface Obsidian Emerald, API + flux temps réel ──>  moteur, orchestrateur, mémoire, outils
  Speech (dictée native) ── pont JavaScript ──>  conversation
                                                fournisseurs IA (au choix) en arrière-plan
```
Séparation stricte : interface (`web/`), service et API (`jarvis/server.py`), moteur (`jarvis/agent`), orchestrateur (`jarvis/tasks.py`), mémoire, outils et connecteurs, fournisseurs (`jarvis/providers`), configuration, journaux et diagnostic.

## Construire et livrer
`python3 jarvis.py build` → vérifications, 85 tests, compilation Swift, `dist/JARVIS.app` signée ad hoc et `dist/JARVIS-0.3.0.dmg` vérifiée. `python3 jarvis.py install` → copie dans `~/Applications` (ancienne version conservée dans `~/Library/Application Support/JARVIS/anciennes-versions`).

## Ce qui n'est pas fait
- Pas de signature Apple Developer ni de notarisation (compte payant) : au premier lancement depuis le .dmg, macOS peut demander « Ouvrir quand même ».
- Python 3 d'Apple (`/usr/bin/python3`) reste nécessaire : il n'est pas embarqué dans l'application.
- Sans fournisseur IA disponible, JARVIS s'ouvre et tout fonctionne sauf la réflexion du modèle (la tâche est mise en attente avec une prochaine action).
