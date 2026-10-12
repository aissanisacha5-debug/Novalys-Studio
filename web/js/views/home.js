// Accueil : noyau JARVIS (état réel), saisie, raccourcis, tâches en cours, derniers résultats, alertes.
import { get, post } from "../api.js";
import { el, empty, handleError, status, when } from "../ui.js";
import { Core } from "../core.js";
import { composer } from "./chat.js";

const SHORTCUTS = [
  ["Planning de demain", "Prépare mon planning de demain à partir de mes tâches."],
  ["Créer un site", "Crée un site vitrine premium pour un restaurant italien à Saint-Étienne (données fictives clairement indiquées), contrôle-le et lance l'aperçu."],
  ["Organiser mes fichiers", "Analyse le dossier workspace et propose un classement, sans rien déplacer avant mon accord."],
  ["Rechercher", "Compare les solutions d'hébergement gratuites pour un site vitrine et recommande la plus adaptée, avec sources."],
  ["Que sais-tu de moi ?", "Qu'est-ce que tu sais sur moi et mes projets ? Indique d'où vient chaque information."],
];

export async function render(view, params, app) {
  const canvas = el("canvas", { "aria-hidden": "true" });
  const stateLine = el("div", { class: "core-state" });
  const h = new Date().getHours();
  const hello = h < 6 ? "Bonne nuit, Sacha." : h < 18 ? "Bonjour, Sacha." : "Bonsoir, Sacha.";
  const sub = el("p", {});
  const { box } = composer(app, async (text) => {
    const r = await post("/api/chat", { text, conversation_id: null });
    app.currentConv = r.conversation_id; app.go(`#/conversation/${r.conversation_id}`);
  });
  const cols = el("div", { class: "home-cols" });
  view.append(el("div", { class: "home" },
    el("div", { class: "core-wrap" }, canvas, stateLine),
    el("div", { class: "greet" }, el("h2", {}, hello), sub),
    el("div", { class: "home-compose" }, box,
      el("div", { class: "shortcuts" }, ...SHORTCUTS.map(([l, p]) => el("button", { type: "button", onclick: async () => {
        try { const r = await post("/api/chat", { text: p, conversation_id: null }); app.currentConv = r.conversation_id; app.go(`#/conversation/${r.conversation_id}`); } catch (e) { handleError(e); }
      } }, l)))),
    cols));
  app.core = new Core(canvas);
  app.syncCore();
  const offCore = app.on((ev) => { if (ev.type === "core") stateLine.replaceChildren(el("b", {}, ev.label)); });
  stateLine.replaceChildren(el("b", {}, app.core.label()));

  async function load() {
    const s = app.state;
    sub.textContent = s?.provider?.available
      ? `${s.tasks_open} tâche(s) ouverte(s), ${s.core.pending_confirmations} action(s) à valider, ${s.ai_calls_today} appel(s) IA aujourd'hui.`
      : "Le fournisseur IA n'est pas disponible : la conversation ne peut pas répondre. Voir Modèles IA.";
    let tasks = [], notifs = [], done = [];
    try { [tasks, notifs, done] = await Promise.all([get("/api/tasks?status=ouvertes"), get("/api/notifications?unread=1"), get("/api/tasks?status=terminee")]); } catch (e) { return; }
    const col = (title, items, fallback) => el("div", {}, el("h3", {}, title), items.length ? el("div", { class: "list" }, ...items) : el("div", { class: "faint small" }, fallback));
    cols.replaceChildren(
      col("Tâches en cours", tasks.slice(0, 5).map((t) => el("div", { class: "row click", onclick: () => app.go(`#/taches/${t.id}`) }, status(t.status), el("div", { class: "main-col" }, el("div", { class: "t small" }, t.title)), el("span", {}))), "Aucune tâche ouverte."),
      col("Derniers résultats", done.slice(0, 5).map((t) => el("div", { class: "row click", onclick: () => app.go(`#/taches/${t.id}`) }, status(t.result_state || "terminee"), el("div", { class: "main-col" }, el("div", { class: "t small" }, t.title), el("div", { class: "d xs" }, when(t.finished_at))), el("span", {}))), "Rien de terminé pour l'instant."),
      col("Alertes", notifs.slice(0, 5).map((n) => el("div", { class: "row click", onclick: () => app.go("#/notifications") }, el("span", { class: "dot " + (n.priority === "haute" ? "wait" : "") }), el("div", { class: "main-col" }, el("div", { class: "t small" }, n.title), el("div", { class: "d xs" }, n.body || "")), el("span", {}))), "Aucune alerte."));
  }
  const offState = app.on((ev) => { if (ev.type === "state") load(); });
  await load();
  return () => { offCore(); offState(); app.core = null; };
}
