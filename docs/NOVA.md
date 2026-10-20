# Nova : audit de départ, plan de transformation, état d'avancement

Mis à jour : 2026-10-20. Ce document dit ce qui existe, ce qui change et ce qui reste à faire. Rien n'y est déclaré terminé sans test.

## 1. Audit (2026-10-20)

Trois dossiers sur le Mac de Sacha ont été inspectés : `~/Documents/CYPHER`, `~/Documents/Jarvis` (un seul fichier d'état) et `~/JARVIS` (un rapport). Le dépôt GitHub `Novalys-Studio` était vide.

### JARVIS (`CYPHER/JARVIS`, seul dépôt Git, base retenue pour Nova)
| Élément | Constat |
|---|---|
| Stack | Python 3.9 **bibliothèque standard seule**, SQLite (WAL, FTS5, migrations versionnées), interface HTML/CSS/modules JS sans compilation, fenêtre native macOS en Swift (WebKit), SSE pour le temps réel |
| Service | API HTTP locale `127.0.0.1:8765`, jeton aléatoire par démarrage, contrôle Host/Origin, CSP stricte |
| Moteur | agent : analyse → plan → permissions → outils → vérification → compte rendu ; état final recoupé ; limites (tours, durée, échecs, boucle, appels IA/jour) |
| IA | fournisseurs interchangeables : Claude Code CLI (actif), API Anthropic, compatible OpenAI, Ollama ; chaîne de repli |
| Outils | 65 outils (fichiers, terminal contrôlé, web, navigateur piloté, documents, sites, mémoire, tâches, agenda, e-mails…) avec risque, délai, vérification |
| Sécurité | modes et niveaux d'autonomie, confirmations à usage unique, autorisations préalables à périmètre exact, contenu suspect → retour aux confirmations, secrets dans le trousseau macOS, journal expurgé |
| Automatisations | `scheduler.py` : déclencheurs et actions, tournent tant que le service tourne (pas pendant la veille du Mac) |
| Voix | dictée native macOS (Speech) ou du navigateur, synthèse `say` **sur le Mac**, réponse lue en flux, interruption avec filtre d'écho, mains libres, mot d'activation sur l'appareil |
| Noyau visuel | `web/js/core.js` (canvas 2D) piloté uniquement par les événements réels du service |
| Gmail / Agenda | **pont via les connecteurs claude.ai et `claude -p`**, désactivé par défaut ; lecture, recherche, brouillons ; aucun envoi. Pas d'OAuth Google propre |
| Tests | 102 tests `unittest` ; rejoués ici sous Linux : 92 réussis, 1 échec propre à macOS (`textutil`), 9 ignorés (tests réels, réseau) |

### CYPHER (`~/Documents/CYPHER`, pas de Git)
Système d'exploitation business de l'agence : Claude Code + skills (`.claude/skills` : briefing, emails, relances, prospection, devis…), mini-CRM en CSV (`memoire/`), moteur Node (`app/generer.js`, `analyst/`, `commerce/`, `agence/`), tableau de bord HTML, applications AppleScript (CYPHER, Voix, STOP), sauvegardes datées. Il contient des **données privées** (prospects, clients, factures, conversations) : il ne doit jamais être poussé dans le dépôt public. JARVIS le lit déjà en lecture seule (outil `agence_consulter`).

### Écarts avec la cible Nova
| Exigence Nova | Existant | Écart |
|---|---|---|
| Accueil plein écran, un noyau, aucun texte | interface complète avec barre latérale | **traité en tranche 1** |
| États repos / écoute / réflexion / recherche / réponse / exécution / erreur | 11 états JARVIS, pas de « recherche » distincte | **traité en tranche 1** |
| Conversation vocale sur téléphone | la voix sort du Mac (`say`) | **traité en tranche 1** (voix jouée par l'appareil) |
| Accès depuis le téléphone | service limité à `127.0.0.1` | à faire : accès distant authentifié et chiffré (tranche 2) |
| Gmail par OAuth 2.0, jetons côté serveur | pont `claude -p` | à faire (tranche 3) |
| Briefing et relances fondés sur les fils | skill CYPHER `relances` (règle J+4 / J+10 sur l'âge) | à refaire sur l'analyse des fils (tranche 4) |
| Automatisations persistantes hors navigateur | scheduler dans le service, s'arrête avec le Mac | file de travaux, reprise, idempotence, coûts (tranche 5) |
| Registre de capacités et politiques | registre d'outils + permissions | à étendre avec les politiques d'envoi (tranche 6) |

## 2. Plan (changements minimaux, dans l'ordre)

1. **Tranche 1 — noyau et voix** (cette branche) : accueil Nova, sept états, voix jouée par l'appareil, interruption, erreurs audio, contexte conservé. La console JARVIS reste intacte sur `/console`.
2. **Tranche 2 — accès téléphone** : écoute configurable au-delà de `127.0.0.1`, authentification forte (appareils appairés, sessions révocables) remplaçant le jeton par démarrage, HTTPS obligatoire (le micro du navigateur l'exige), recommandation : Tailscale ou un petit serveur toujours allumé. Le nom « JARVIS » dans les réponses devient « Nova ».
3. **Tranche 3 — Gmail** : modules séparés `jarvis/google/` (OAuth 2.0 avec PKCE, rafraîchissement et révocation, recherche et récupération, fils, métadonnées, brouillons, envoi autorisé, erreurs et quotas). Portée par défaut `gmail.readonly` ; `gmail.compose` puis `gmail.send` seulement sur activation explicite. Jetons chiffrés côté serveur. Le pont `claude -p` est conservé comme repli jusqu'à validation.
4. **Tranche 4 — briefing et relances** : « Nova, fais-moi un point sur mes mails » ; classement par fil (réponse attendue de Sacha, réponse attendue d'un tiers, relance utile, échéance, demande importante, sans action) avec références vérifiables (identifiant de fil, dates) ; jamais de relance sur le seul âge d'un message ; déduplication et péremption.
5. **Tranche 5 — automatisations persistantes** : table de travaux SQLite, verrous, tentatives limitées, reprise après incident, clés d'idempotence par action, journal, plafonds de fréquence et de coût, interrupteur immédiat par automatisation, notifications.
6. **Tranche 6 — autonomie contrôlée** : registre des capacités (permissions, déclencheurs, limites, niveau de confirmation, vérification, erreurs) ; envoi automatique uniquement dans un périmètre configuré ; un e-mail ne peut jamais modifier une règle.

Chaque tranche ajoute ses tests et met à jour ce document.

## 3. Tranche 1 : ce qui est livré

- `/` sert l'accueil Nova (`web/nova.html`) ; l'interface complète reste sur `/console`. Les menus de l'application macOS (`#/parametres`…) redirigent vers la console.
- Noyau plein écran (`web/js/core.js` réutilisé, deux états ajoutés : recherche, exécution). Aucun texte de réponse ni transcription : seul un libellé d'état invisible est annoncé aux lecteurs d'écran.
- Conversation (`web/js/nova/session.js`) : un toucher (ou Espace / Entrée) ouvre le micro ; la phrase est envoyée au service ; la réponse est lue phrase par phrase pendant sa génération ; le micro se rouvre ensuite. « Stop » ou Échap termine.
- Voix (`web/js/nova/speaker.js`) : synthèse de l'appareil, choix automatique de la voix française la plus naturelle disponible (voix « Natural » d'Edge, voix Premium / Enhanced d'Apple, voix Google…). Dans l'application macOS, la voix du Mac reste utilisée.
- Côté service : `POST /api/chat` accepte `voice_out: "client"` ; la réponse est alors diffusée en événements `speech` (SSE) au lieu d'être lue par le Mac. Les événements d'outil portent `phase: "recherche" | "execution"`.
- Interruption : toucher pendant la réponse, ou parler (ordinateur seulement : micro et haut-parleur du téléphone se gênent). La réponse et la tâche en cours sont arrêtées ; le filtre d'écho ignore la voix de Nova.
- Erreurs audio expliquées à voix haute : micro refusé, absent, reconnaissance indisponible, navigateur non compatible, service injoignable, synthèse muette (garde-fou de 5 s). Silence : le micro se rouvre deux fois puis Nova se met au repos.
- Contexte : la même conversation est reprise pendant 6 h (identifiant conservé sur l'appareil) ; le service résume déjà les longues conversations.
- Contraintes navigateur respectées : micro et son seulement après un geste ; arrêt du micro et de la voix quand l'onglet passe en arrière-plan (la tâche continue sur le serveur) ; écran maintenu allumé pendant une conversation quand le navigateur le permet.
- Action à risque demandée à la voix : Nova le dit et rend la main ; l'accord se donne dans la console (aucune validation implicite).

### Tests de la tranche 1
| Test | Résultat (2026-10-20, conteneur Linux) |
|---|---|
| `tests/js/nova.test.mjs` (21 tests : états, tour complet, contexte, interruption tactile et vocale, écho, anti-doublon, erreurs audio, silence, arrière-plan, voix, synthèse) | 21 réussis |
| `tests/test_nova.py` (11 tests : accueil et console, voix côté appareil, voix du Mac inchangée, contexte, phase recherche, fichiers servis, tests JS) | 11 réussis |
| Suite complète `python3 -m unittest discover -s tests` | 113 tests : 103 réussis, 1 échec propre à macOS (`textutil` absent sous Linux, préexistant), 9 ignorés |
| Essai dans Chromium (bureau 1280×800 et mobile 390×844), service réel, micro et synthèse simulés | tour complet repos → écoute → réflexion → réponse → écoute, réponse réelle du modèle lue en 3 phrases, aucune erreur JavaScript |

**Non testé** : micro et haut-parleurs réels (je ne peux ni parler ni écouter), Safari iOS et Chrome Android sur un vrai téléphone, l'application macOS reconstruite avec cette version (`python3 jarvis.py check`, `build`, `install` à lancer sur le Mac), la vérification JavaScript par JavaScriptCore de `scripts/verifier.py` (macOS seulement ; syntaxe vérifiée ici avec Node).

### Limites connues de la tranche 1
- Le téléphone ne peut pas encore joindre le service (tranche 2).
- La qualité de la voix dépend des voix installées sur l'appareil ; une voix neuronale côté serveur (API temps réel) demanderait une clé et un budget : à décider.
- Le modèle se présente encore comme « JARVIS » (prompt système inchangé dans cette tranche).

## 4. Interface de la vidéo de référence, en vert billet (2026-10-20)

Reproduction de la vidéo envoyée par Sacha, seule la palette violette remplacée par le vert billet
(`#00C878`, `#00E69A`, `#006B45`, `#06271D`, `#080B0A`, `#101713` ; jetons `--nova-*` dans `web/css/tokens.css`).

- **Accueil** : brume verte plein écran, salutation discrète (« Bonjour Sacha » + date), petit noyau lumineux
  (64 px) aux sept états, indication sous le noyau. Aucun texte de conversation.
- **Cartes** : titre de section espacé + filet + méta à droite ; cartes horizontales translucides (avatar,
  nom · contexte, résumé, badge Froid / Tiède / Chaud…). La carte active s'illumine et se développe (détail +
  « Action recommandée »). Entrée en cascade, transitions de 0,5 s.
- **Détail** : deux panneaux côte à côte (proposition lumineuse à gauche, e-mail et pièce jointe à droite),
  question de validation en bas (« Espace ↵ »), puis écran « C'est fait » ; empilés sous 620 px.
- **Données réelles uniquement** : rien n'est affiché par défaut. L'agent montre des éléments obtenus par ses
  outils avec `nova_afficher` (source portée par chaque carte) et `nova_effacer` ; état servi par
  `GET/DELETE /api/nova/view` et l'événement `nova_view`. Tout est rendu en `textContent` (aucun HTML venant
  d'un e-mail).
- **Validation réelle** : la question n'est active que si le moteur attend une confirmation pour la tâche qui a
  affiché la vue. Valider (clic, Espace ou Entrée) approuve cette confirmation ; l'écran de succès n'apparaît
  qu'une fois la tâche réellement terminée.
- **Renommage** : textes visibles de l'interface et de l'app Mac en « Nova » (Nova.app, menus, messages,
  mot d'activation par défaut « Nova », nouvelle icône). Identifiants internes conservés (`studio.novalys.jarvis`,
  `~/Library/Application Support/JARVIS`, trousseau, agent de lancement) pour garder données, autorisations micro
  et secrets existants. `python3 jarvis.py install` met de côté une ancienne `JARVIS.app`.

### Vérification visuelle
Banc reproductible : serveur isolé, provider scripté et données de **démonstration** (`tests/fixtures/nova_demo.json`,
jamais chargées par l'application) ; la validation passe par une vraie confirmation du moteur. Captures
1440×900 et 390×844 (accueil, liste, chaque carte active, détail, succès) comparées aux images de la vidéo.

### Limites
- L'app Mac n'a pas été recompilée ici (Linux) : à construire sur le Mac avec `python3 jarvis.py build`.
- Les cartes n'apparaissent que si l'agent appelle `nova_afficher` ; la connexion Gmail et le briefing
  (tranches 3 et 4) fourniront les vraies données des rendez-vous et e-mails.
