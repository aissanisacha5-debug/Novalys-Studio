# Sécurité de JARVIS

## Principes

1. Les contenus externes (pages web, fichiers, documents, e-mails, résultats d'outils) sont des **données non fiables**. Ils sont balisés comme tels pour le modèle et ne peuvent jamais modifier les règles.
2. Les permissions sont **vérifiées dans le backend**, à chaque appel d'outil. L'interface ne fait qu'afficher et demander.
3. Les agents (et les plugins) ne disposent d'aucun outil pour modifier leurs permissions, le mode, les dossiers ou les règles.
4. Un « fais tout » n'autorise rien de plus : chaque action à risque élevé demande une confirmation propre.

## Niveaux de risque

| Risque | Exemples | Contrôle |
|---|---|---|
| Faible | lire, rechercher, résumer, brouillon local, mémoriser | libre dans les modes qui l'autorisent |
| Modéré | écrire/déplacer un fichier, lancer un test, installer une dépendance, ouvrir une app | libre en exécution supervisée / développement ; confirmation possible (réglage) |
| Élevé | supprimer, `git push`, `python3 -c`, créer un événement d'agenda, réglages sensibles, restauration | **confirmation à usage unique**, liée à l'outil et aux arguments exacts (hash) |

Une confirmation présente : action, cible, conséquences, données concernées, réversibilité, résultat attendu. Elle ne sert qu'une fois et jamais pour une autre action.

## Modes

`conversation` (aucun outil) · `assistance` et `maintenance` (risque faible seulement) · `execution_supervisee`, `vocal`, `autonomie_limitee`, `developpement` (faible + modéré ; élevé avec confirmation). Changer de mode demande une confirmation et **n'accorde aucun autre droit**.

## Fichiers

- Accès limité aux **dossiers autorisés** (par défaut : `JARVIS/workspace` en écriture, `CYPHER` en lecture seule).
- Chemins résolus (`realpath`) : `..` et liens symboliques ne permettent pas de sortir.
- Toujours interdits : trousseaux, `~/.ssh`, `~/.gnupg`, `~/.aws`, cookies et profils de navigateurs, Mail, Messages, `~/.claude`, `/System`, `/etc`, `/usr`, `.env`, `*.pem`, `*.key`, `JARVIS/data`.
- Jamais modifiables par l'agent : le code de JARVIS, `CYPHER/memoire`, `.claude`, `CLAUDE.md`, `ETAT.md`, l'évaluateur de CYPHER.
- Pas d'écrasement silencieux : version précédente conservée (`data/versions`), suppression = corbeille JARVIS (`data/corbeille`).

## Commandes

Sans shell (`shlex` + exécution directe), liste blanche configurable, opérateurs `| ; && > < $() \`` refusés, commandes dangereuses toujours bloquées (`rm`, `sudo`, `curl`, `wget`, `chmod`, `osascript`, `bash`, `launchctl`, `defaults`, `security`, `kill`…), arguments de type chemin contrôlés, dossier de travail autorisé, variables d'environnement sensibles retirées, délai maximum, sortie limitée, arrêt du groupe de processus à l'annulation, historique.

## Réseau

- API sur `127.0.0.1` uniquement ; jeton aléatoire par démarrage (`data/token`, droits 600) exigé sur toute l'API.
- En-tête `Host` vérifié (anti DNS rebinding), `Origin` vérifiée, CSP stricte (`script-src 'self'`), `X-Frame-Options: DENY`.
- Lecture web : http(s) seulement, adresses locales et privées refusées (pas de rebond vers l'API ou le réseau local), 15 pages par tâche, pas de contournement de CAPTCHA ni de connexion.

## Secrets

Trousseau macOS (service `studio.novalys.jarvis`) ; jamais dans le code, l'interface, la base, les journaux (expurgation automatique : clés `sk-…`, jetons, mots de passe, numéros de carte), les conversations, les sauvegardes ou Git. La mémoire refuse toute information qui ressemble à un secret. Un crochet Git `pre-commit` (`scripts/verifier-secrets.py`) bloque un commit contenant un secret probable ; `python3 jarvis.py verifier` contrôle aussi les fichiers suivis par Git.

## Navigateur piloté

Chrome sans interface, **profil séparé** (`data/navigateur-pilote` : aucune session ni cookie de Sacha), port de contrôle sur 127.0.0.1, fermé après 10 min d'inactivité. Adresses locales/privées refusées, y compris après une redirection. Champs mot de passe, carte, IBAN, CVC : **jamais remplis** (Sacha les saisit lui-même). Remplir = risque modéré (valeurs relues) ; **envoyer un formulaire = risque élevé, confirmation obligatoire**. Chaque action est notée (table `browser_actions`). Aucun contournement de CAPTCHA ni de connexion.

## Niveaux A / B / C du prompt 3

| Prompt 3 | JARVIS | Exemples |
|---|---|---|
| A — local, faible risque | `faible` | lire, rechercher, ouvrir une page, brouillon local |
| B — modifie l'environnement | `modere` | écrire un fichier, installer une dépendance (`npm install`), lancer un aperçu, remplir un formulaire |
| C — sensible ou externe | `eleve` | supprimer, envoyer un formulaire, `git push`, événement d'agenda, réglages de sécurité, restauration |

Une autorisation n'est jamais permanente : chaque confirmation vaut pour une action et des arguments précis.

## E-mails et agenda

Gmail et Google Agenda passent par les connecteurs claude.ai via Claude Code, avec une **liste blanche** d'outils (`--allowedTools` + `--permission-mode dontAsk`) et une **liste noire** explicite : envoi, transfert, réponse, suppression, spam, suppression d'événement. Résultat « confirmé » seulement si l'appel d'outil est constaté. Liste d'opposition de CYPHER vérifiée avant tout brouillon. **Aucun envoi possible en v0.1.**

## Signaler un problème

Le journal (Historique) et le Diagnostic montrent chaque action, autorisation et erreur. En cas de doute : bouton **Interrompre** (ou Échap), puis **Diagnostic > Arrêter JARVIS**.
