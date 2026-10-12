# Fournisseurs d'IA

JARVIS a son propre moteur. Le fournisseur ne sert qu'à produire le texte de chaque tour de réflexion ; les actions passent toujours par les outils et les permissions de JARVIS. Réglages : **Modèles IA**.

| Fournisseur | Prérequis | Coût | Internet | État sur ce Mac |
|---|---|---|---|---|
| Claude (via Claude Code) | Claude Code installé et connecté à l'abonnement | inclus dans l'abonnement, avec **limites d'usage** | oui | **actif, testé** depuis l'application |
| Compatible OpenAI | adresse + modèle ; clé dans le trousseau si distant | selon le service (payant pour OpenAI/Mistral ; gratuit en local) | oui, sauf modèle local | non configuré |
| API Anthropic | clé API (console.anthropic.com) dans le trousseau | **facturé à l'usage** | oui | non configuré |
| Ollama | Ollama installé + un modèle téléchargé | gratuit (local) | non | non installé |

## Exemples « compatible OpenAI »
- Mistral : `https://api.mistral.ai/v1` + clé.
- OpenAI : `https://api.openai.com/v1` + clé (payant).
- LM Studio (local, hors ligne) : `http://127.0.0.1:1234/v1`, sans clé.
- Ollama via son API compatible : `http://127.0.0.1:11434/v1`, sans clé. Sur 16 Go de mémoire, choisir un modèle de 8 milliards de paramètres au plus.

Une adresse distante reçoit le contenu des conversations : son enregistrement demande une confirmation.

## Clés et secrets
Sécurité > Secrets : la clé va dans le trousseau macOS. Elle n'est jamais affichée, journalisée, sauvegardée ni envoyée à l'interface.

## Repli
Ordre essayé : modèle de l'agent → modèle principal → modèle de remplacement → **fournisseur de remplacement** (s'il est configuré et disponible). Aucun repli n'existe s'il n'est pas configuré.

## Erreurs gérées
- Fournisseur indisponible ou non configuré : la tâche passe « Bloquée » avec une prochaine action ; rien n'est inventé.
- **Limite d'usage de l'abonnement** (constatée le 2026-10-12, réinitialisation à 20 h 10) : message clair avec l'heure de réinitialisation.
- Clé refusée (401/403), limite de débit (429, délai indiqué), service indisponible (5xx), délai dépassé.
- Budget : nombre d'appels par jour, budget quotidien et mensuel (Paramètres > Budget et limites).

## Hors ligne
Seul un modèle local (LM Studio, Ollama) permet de travailler sans Internet. Claude, Anthropic, OpenAI et Mistral nécessitent une connexion.
