# Connecteurs

Chaque connecteur a une configuration, un état vérifié, des capacités, des permissions, des limites, une procédure de connexion/déconnexion, une gestion d'erreurs et un test (bouton **Tester** dans Applications connectées).

| Connecteur | État au 2026-10-12 | Mécanisme | Capacités | Garde-fous |
|---|---|---|---|---|
| Claude (Claude Code) | **connecté, testé** | CLI officielle `claude -p`, abonnement | conversation, raisonnement, code, extraction JSON | aucun outil Claude Code ; dossier vide ; pas de session conservée |
| Gmail | disponible, **désactivé** par défaut | connecteur claude.ai via `claude -p` | rechercher, lire, créer un brouillon | liste blanche d'outils, liste noire (envoi, transfert, réponse, suppression), appel constaté, liste d'opposition CYPHER |
| Google Agenda | disponible, **désactivé** par défaut | connecteur claude.ai via `claude -p` | lire, créer un événement | création = risque élevé (confirmation) ; suppression interdite |
| Notifications macOS | actif | `osascript display notification` | notifications locales | contenu masqué, heures silencieuses |
| Voix macOS | actif | `say` | 74 voix, volume, vitesse, sortie audio | — |
| Recherche web | actif | page HTML publique DuckDuckGo + lecture HTTP | recherche, lecture, liens, audit | pas d'adresse locale, 15 pages/tâche, pas de contournement |
| CRM CYPHER | actif, lecture seule | fichiers CSV de `CYPHER/memoire` | prospects, clients, oppositions, devis, factures | écriture impossible (zone protégée) |
| Ollama | indisponible | API locale 127.0.0.1:11434 | conversation locale, embeddings | jamais lancé automatiquement |
| API Anthropic | indisponible | API officielle, clé dans le trousseau | conversation, vision | facturé : budget obligatoire |
| GitHub / Netlify / Vercel | non connectés | jetons dans le trousseau | prévu | publication toujours confirmée |

## Serveurs MCP
JARVIS n'installe aucun serveur MCP. Ceux de Claude Code ont été inventoriés (voir ENVIRONMENT_AUDIT.md). Avant d'en ajouter un : provenance, documentation, permissions, maintenance, risques, puis confirmation de Sacha.

## Plugins
`plugins/<nom>/plugin.json` (`id`, `name`, `version`, `tools`, `max_risk`) + `plugin.py` (`register(registry)`). Désactivés par défaut (`plugins_enabled`, réglage sensible). Un outil non déclaré ou plus risqué que déclaré fait échouer le chargement.
