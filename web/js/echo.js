// Filtre d'écho partagé (console Nova et Nova) : une phrase captée par le micro qui reprend surtout
// les mots que l'assistant est en train de dire vient des haut-parleurs, pas de Sacha.
const words = (x) => String(x || "").toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "")
  .replace(/[^a-z0-9 ]/g, " ").split(/\s+/).filter((w) => w.length > 2);

export function isEcho(heard, spoken) {
  const h = words(heard); if (!h.length) return true;
  const said = new Set(words(spoken));
  return h.filter((w) => said.has(w)).length / h.length >= 0.6;
}
