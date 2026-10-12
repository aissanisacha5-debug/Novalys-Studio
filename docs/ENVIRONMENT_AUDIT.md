# Audit de l'environnement — 2026-10-12

Audit réalisé avant toute installation, en lecture seule. Aucun mot de passe, cookie, clé ni secret n'a été collecté.

## Matériel et système (vérifié)

| Élément | Résultat | Commande |
|---|---|---|
| macOS | 26.7.1 (25G241) | `sw_vers` |
| Processeur | Apple M5, arm64, 10 cœurs | `uname -m`, `sysctl` |
| Mémoire | 16 Go unifiés | `sysctl hw.memsize` |
| Disque | 926 Go, 845 Go libres | `df -h ~` |

## Outils présents

| Outil | État | Conséquence pour JARVIS |
|---|---|---|
| Python | 3.9.6 (Command Line Tools), LibreSSL 2.8.3 | **Backend écrit en Python, bibliothèque standard uniquement** |
| SQLite | 3.51.0 avec FTS5 | Base unique + recherche plein texte |
| Git | 2.50.1 | Versionnement local |
| Swift | 6.3.3 (sans Xcode complet) | Non utilisé en v0.1 (réserve : fenêtre native, reconnaissance vocale native) |
| Node.js / npm / npx | **absents** | Pas de React/Vite/Tauri : interface en JavaScript natif (modules ES), aucune étape de compilation |
| Homebrew | **absent** | Aucune installation par Homebrew |
| Ollama / modèle local | **absent** | Fournisseur local implémenté mais indisponible |
| ffmpeg, whisper | absents | Pas de transcription locale |
| Claude Code CLI | 2.1.296, connecté par **claude.ai** (abonnement) | **Fournisseur IA réel** via `claude -p` (mode non interactif officiel) |
| `say` | 74 voix dont 20 françaises (Thomas, Audrey Premium…) | Synthèse vocale locale |
| `osascript`, `shortcuts`, `automator`, `textutil`, `sips`, `mdfind` | présents | Notifications, ouverture d'apps, conversion DOCX, lecture PDF (PDFKit) |
| Navigateurs | Safari, Google Chrome | Fenêtre JARVIS en mode application Chrome ; PDF par Chrome sans interface ; dictée par Chrome |

## Connecteurs et MCP (vérifié avec `claude mcp list` et un appel réel)

| Serveur | État |
|---|---|
| claude.ai Gmail | connecté — appel réel `search_threads` constaté dans le flux |
| claude.ai Google Calendar | connecté |
| claude.ai Claude Docs | connecté (non utilisé) |
| context7 | connecté (non utilisé) |
| plugin GitHub | **échec** (en-tête d'autorisation invalide) |
| plugin Playwright | **échec** (`npx` introuvable) |
| Claude Desktop `mcpServers` | aucun |

Constat important : sans `--setting-sources` utilisateur, la CLI ne charge pas les connecteurs claude.ai ; un premier essai a même renvoyé « 0 résultat » **sans avoir appelé l'outil**. D'où la règle de JARVIS : un résultat de connecteur n'est « confirmé » que si l'appel d'outil est constaté dans le flux `stream-json`.

## Accès IA

- L'abonnement Claude Pro **n'est pas une clé API**. JARVIS utilise la CLI officielle `claude -p`, déjà connectée par Sacha ; chaque appel compte dans les limites d'usage de l'abonnement. Le « coût » affiché par la CLI est un équivalent tarif API, non facturé : JARVIS le classe « inclus dans l'abonnement ».
- Latence mesurée : 4 à 10 s par appel (haiku/sonnet).
- API Anthropic : non configurée (aucune clé). Ollama : non installé.

## Permissions macOS

| Permission | État |
|---|---|
| Accessibilité / enregistrement d'écran | **non accordées, non demandées** (règle du cahier des charges) |
| Notifications | via `osascript` (attribuées à « Éditeur de script ») ; affichage selon Réglages Système |
| Micro | demandé par Chrome lors de la première dictée (action de Sacha) |
| Trousseau | `security` (secrets de JARVIS, service `studio.novalys.jarvis`) |
| Lancement au démarrage | **non configuré** (accord explicite requis) |

## Projet existant

Le dossier `Documents/CYPHER` contient déjà **CYPHER**, l'assistant business de Sacha (mémoire, CRM, missions, application). Il n'a pas été modifié : JARVIS est construit dans `CYPHER/JARVIS/`, lit le CRM de CYPHER en **lecture seule** et ne peut jamais écrire dans `CYPHER/memoire`, `.claude`, `CLAUDE.md`, `ETAT.md` ni l'évaluateur. Seule écriture hors de `JARVIS/` : une ligne dans `CYPHER/journal.md` (règle 5 de CYPHER).
