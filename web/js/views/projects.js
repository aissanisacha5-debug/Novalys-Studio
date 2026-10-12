// Projets : liste, création, détail (objectifs, tâches, décisions, mémoire, conversations, historique, compte rendu).
import { get, patch, post } from "../api.js";
import { btn, download, el, empty, errorBox, field, input, loading, md, modal, select, status, textarea, toast, when } from "../ui.js";
import { quickAsk } from "../app.js";

export async function render(view, params, app) {
  if (params[0]) return detail(view, Number(params[0]), app);
  const page = el("div", { class: "page" }, loading());
  view.append(page);
  let ps;
  try { ps = await get("/api/projects"); } catch (e) { return page.replaceChildren(errorBox(e)); }
  page.replaceChildren(
    el("div", { class: "toolbar" }, el("p", { class: "muted", style: { margin: 0 } }, `${ps.length} projet(s)`), el("span", { class: "grow" }), btn("Nouveau projet", () => createModal(), { cls: "primary", icon: "plus" })),
    ps.length ? el("table", { class: "table" }, el("thead", {}, el("tr", {}, ...["Projet", "Statut", "Avancement", "Bloqué", "Échéance", "Priorité"].map((h) => el("th", {}, h)))),
      el("tbody", {}, ...ps.map((p) => el("tr", {}, el("td", {}, el("a", { href: `#/projets/${p.id}` }, p.name), el("div", { class: "faint xs" }, (p.description || "").slice(0, 90))),
        el("td", {}, status(p.status)),
        el("td", { style: { minWidth: "140px" } }, `${p.tasks_done}/${p.tasks_total}`, el("div", { class: "meter" }, el("i", { style: { width: (p.tasks_total ? Math.round(100 * p.tasks_done / p.tasks_total) : 0) + "%" } }))),
        el("td", {}, p.tasks_blocked ? el("span", { class: "badge err" }, `${p.tasks_blocked} tâche(s)`) : el("span", { class: "faint" }, "non")),
        el("td", { class: "small" }, p.due_date || ""), el("td", { class: "small" }, ["", "basse", "normale", "haute"][p.priority] || p.priority)))))
      : empty("Aucun projet.", "Créez un projet pour regrouper tâches, fichiers, décisions et conversations.", btn("Créer un projet", () => createModal(), { cls: "primary" })));

  function createModal() {
    const name = input(), desc = textarea(), obj = textarea({ placeholder: "Objectifs mesurables" }), crit = textarea({ placeholder: "Critères de réussite" });
    const due = input({ type: "date" }), folder = input({ placeholder: "Dossier (ex. projets/mon-projet, dans l'espace de travail)" });
    modal("Nouveau projet", el("div", { class: "form" }, field("Nom", name), field("Description", desc), field("Objectifs", obj), field("Critères de réussite", crit),
      el("div", { class: "form-row" }, field("Échéance", due), field("Dossier associé", folder))),
      ["close", (close) => btn("Créer", async () => {
        const p = await post("/api/projects", { name: name.value, description: desc.value, objectives: obj.value, success_criteria: crit.value, due_date: due.value || null, folder: folder.value || null });
        close(); app.go(`#/projets/${p.id}`);
      }, { cls: "primary" })]);
  }
}

async function detail(view, id, app) {
  const page = el("div", { class: "page" }, loading());
  view.append(page);
  async function load() {
    let p;
    try { p = await get(`/api/projects/${id}`); } catch (e) { return page.replaceChildren(errorBox(e)); }
    const edit = (key, label, multiline = true) => {
      const i = multiline ? textarea({ value: p[key] || "" }) : input({ value: p[key] || "" });
      modal(label, i, ["close", (close) => btn("Enregistrer", async () => { await patch(`/api/projects/${id}`, { [key]: i.value }); close(); load(); }, { cls: "primary" })]);
    };
    const statusSel = select([["idee", "Idée"], ["actif", "Actif"], ["en_pause", "En pause"], ["bloque", "Bloqué"], ["termine", "Terminé"], ["archive", "Archivé"]], p.status);
    statusSel.addEventListener("change", async () => { try { await patch(`/api/projects/${id}`, { status: statusSel.value }); toast("Statut mis à jour."); } catch (e) { statusSel.value = p.status; (await import("../ui.js")).handleError(e); } });
    const sec = (title, key) => el("div", {}, el("h3", { style: { display: "flex", gap: "8px", alignItems: "center" } }, title, btn("Modifier", () => edit(key, title), { cls: "sm ghost", icon: "edit" })),
      p[key] ? md(p[key]) : el("p", { class: "faint small" }, "Non renseigné."));
    page.replaceChildren(
      el("div", { class: "crumbs" }, el("a", { href: "#/projets" }, "Projets"), "/", p.name),
      el("div", { class: "toolbar" }, el("h2", { class: "title", style: { margin: 0 } }, p.name), el("span", { class: "grow" }), el("div", { style: { width: "150px" } }, statusSel),
        btn("Compte rendu", async () => { const r = await get(`/api/projects/${id}/report`); modal("Compte rendu", md(r.markdown), ["close", (c) => btn("Télécharger", () => download(`compte-rendu-${id}.md`, r.markdown), { icon: "download" })], true); }, { icon: "doc" }),
        btn("Demander à JARVIS", () => quickAsk(`Pour le projet « ${p.name} » : fais le point, détecte les tâches bloquées et propose les 3 prochaines priorités.`), { cls: "primary", icon: "chat" })),
      el("p", { class: "lead" }, p.description || ""),
      el("div", { class: "grid-2" }, sec("Objectifs", "objectives"), sec("Critères de réussite", "success_criteria"), sec("Prochaines étapes", "next_steps"), sec("Notes", "notes")),
      el("h3", {}, `Tâches (${p.tasks.length})`),
      p.tasks.length ? el("div", { class: "list" }, ...p.tasks.map((t) => el("div", { class: "row click", onclick: () => app.go(`#/taches/${t.id}`) }, status(t.status), el("div", { class: "main-col" }, el("div", { class: "t small" }, t.title)), el("span", { class: "faint xs" }, t.due_date || ""))))
        : el("p", { class: "faint small" }, "Aucune tâche."),
      el("h3", { style: { display: "flex", gap: "8px", alignItems: "center" } }, "Décisions", btn("Ajouter", () => {
        const d = input(), r = textarea({ placeholder: "Pourquoi" });
        modal("Nouvelle décision", el("div", { class: "form" }, field("Décision", d), field("Raison", r)), ["close", (close) => btn("Enregistrer", async () => { await post(`/api/projects/${id}/decisions`, { decision: d.value, reason: r.value }); close(); load(); }, { cls: "primary" })]);
      }, { cls: "sm ghost", icon: "plus" })),
      p.decisions.length ? el("div", { class: "list" }, ...p.decisions.map((d) => el("div", { class: "row" }, el("span", { class: "faint xs" }, d.created_at.slice(0, 10)), el("div", { class: "main-col" }, el("div", { class: "small" }, d.decision), d.reason ? el("div", { class: "d xs" }, d.reason) : null), el("span", {}))))
        : el("p", { class: "faint small" }, "Aucune décision enregistrée."),
      el("div", { class: "grid-2" },
        el("div", {}, el("h3", {}, "Mémoire du projet"), p.memories.length ? el("div", { class: "list" }, ...p.memories.map((m) => el("div", { class: "row" }, el("span", { class: "badge plain" }, m.nature), el("div", { class: "main-col small" }, m.content), el("span", {})))) : el("p", { class: "faint small" }, "Rien de mémorisé.")),
        el("div", {}, el("h3", {}, "Conversations"), p.conversations.length ? el("div", { class: "list" }, ...p.conversations.map((c) => el("div", { class: "row click", onclick: () => app.go(`#/conversation/${c.id}`) }, el("span", {}), el("div", { class: "main-col small" }, c.title), el("span", { class: "faint xs" }, when(c.updated_at))))) : el("p", { class: "faint small" }, "Aucune."))),
      el("h3", {}, "Historique"), p.history.length ? el("div", { class: "events" }, ...p.history.map((e) => el("div", { class: "event " + e.level }, el("time", {}, e.ts.slice(5, 10)), el("div", { class: "m" }, e.message)))) : el("p", { class: "faint small" }, "Aucun événement."),
      p.folder ? el("p", { class: "small muted" }, "Dossier : ", el("span", { class: "mono" }, p.folder)) : null);
  }
  await load();
}
