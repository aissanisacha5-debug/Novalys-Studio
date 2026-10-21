// États du noyau de Nova. L'accueil n'affiche jamais de texte de réponse ni de transcription :
// tout passe par le noyau (couleur, mouvement) et par la voix.
export const NOVA_STATES = ["repos", "ecoute", "reflexion", "recherche", "reponse", "execution", "erreur"];

// Correspondance avec les états du noyau visuel partagé (web/js/core.js).
export const CORE_STATE = {
  repos: "attente", ecoute: "ecoute", reflexion: "reflexion", recherche: "recherche",
  reponse: "parle", execution: "execution", erreur: "erreur",
};

// Étiquettes lues par les lecteurs d'écran uniquement (aucune n'est affichée).
export const STATE_LABELS = {
  repos: "Nova est au repos. Touchez l'écran pour parler.", ecoute: "Nova vous écoute.", reflexion: "Nova réfléchit.",
  recherche: "Nova recherche.", reponse: "Nova vous répond.", execution: "Nova exécute une action.", erreur: "Nova a rencontré un problème.",
};

// Priorité : erreur > réponse vocale > écoute > recherche / exécution / réflexion > repos.
export function deriveState(s, now) {
  if (s.offline || (s.errorUntil && now < s.errorUntil)) return "erreur";
  if (s.speaking) return "reponse";
  if (s.listening && !s.barge) return "ecoute";
  if (s.sending || s.pendingTask != null) return s.phase || "reflexion";
  return "repos";
}
