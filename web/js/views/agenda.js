// Agenda : planning du jour (tâches et rappels réels), événements Google Agenda si le connecteur est activé.
import { get, post } from "../api.js";
import { btn, el, errorBox, input, loading, status } from "../ui.js";
import { quickAsk } from "../app.js";

const tool = (id, args) => post(`/api/tools/${id}/invoke`, { args });

export async function render(view, params, app) {
  const tomorrow = new Date(Date.now() + 86400000).toISOString().slice(0, 10);
  const day = input({ type: "date", value: tomorrow });
  const plan = el("div"), gcal = el("div");
  view.append(el("div", { class: "page" },
    el("div", { class: "toolbar" }, el("div", { style: { width: "180px" } }, day), btn("Préparer le planning", () => loadPlan(), { cls: "primary" }),
      btn("Résumé de la semaine par Nova", () => quickAsk("Prépare mon résumé hebdomadaire : tâches terminées, en retard, échéances de la semaine prochaine, et propose des blocs de travail."), { cls: "ghost" })),
    el("div", { class: "grid-2" }, el("div", {}, el("h3", { style: { marginTop: 0 } }, "Planning proposé"), plan), el("div", {}, el("h3", { style: { marginTop: 0 } }, "Google Agenda"), gcal))));
  async function loadPlan() {
    plan.replaceChildren(loading());
    try {
      const r = (await tool("planning_preparer", { date: day.value })).result;
      plan.replaceChildren(
        r.en_retard.length ? el("div", { class: "error-box", style: { marginBottom: "12px" } }, `En retard : ${r.en_retard.join(", ")}`) : null,
        r.blocs.length ? el("div", { class: "list" }, ...r.blocs.map((b) => el("div", { class: "row click", onclick: () => app.go(`#/taches/${b.tache_id}`) }, el("span", { class: "mono" }, b.creneau), el("div", { class: "main-col small" }, b.tache), el("span", {}))))
          : el("p", { class: "faint small" }, "Aucune tâche ouverte à planifier."),
        r.rappels.length ? [el("h3", {}, "Rappels"), el("div", { class: "list" }, ...r.rappels.map((x) => el("div", { class: "row" }, el("span", { class: "mono" }, x.heure), el("div", { class: "main-col small" }, x.titre), el("span", {}))))] : null,
        r.conflits.length ? el("div", { class: "panel", style: { marginTop: "12px", borderColor: "rgba(244,184,96,.35)" } }, el("b", { class: "small" }, "Conflits"), ...r.conflits.map((c) => el("div", { class: "small" }, c))) : null,
        el("p", { class: "small faint" }, `${r.non_planifiees} tâche(s) non planifiée(s). Aucun rendez-vous n'est inventé : le planning vient de vos tâches et rappels.`));
    } catch (e) { plan.replaceChildren(errorBox(e)); }
  }
  async function loadCal() {
    const tools = await get("/api/tools");
    const t = tools.find((x) => x.id === "agenda_consulter");
    if (!t.available) return gcal.replaceChildren(el("div", { class: "unavailable" }, el("b", {}, "Non connecté. "), t.unavailable_reason, ". ", el("a", { href: "#/applications" }, "Activer le connecteur")));
    gcal.replaceChildren(btn("Lire les 7 prochains jours", async () => {
      gcal.replaceChildren(loading("Lecture de Google Agenda…"));
      try {
        const r = await tool("agenda_consulter", {});
        gcal.replaceChildren(el("div", { class: "state-line" }, status(r.state), r.verification),
          r.result.events.length ? el("div", { class: "list" }, ...r.result.events.map((e) => el("div", { class: "row" }, el("span", { class: "mono xs" }, (e.start || "").replace("T", " ").slice(0, 16)), el("div", { class: "main-col small" }, e.title, e.location ? el("div", { class: "d xs" }, e.location) : null), el("span", {}))))
            : el("p", { class: "faint small" }, "Aucun événement sur la période."));
      } catch (e) { gcal.replaceChildren(errorBox(e)); }
    }));
  }
  await Promise.all([loadPlan(), loadCal()]);
}
