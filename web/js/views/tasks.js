// Centre de tâches : liste filtrée, création (manuelle ou exécutée par un agent), détail avec étapes réelles,
// pause / reprise / annulation, confirmations, sources consultées, consommation.
import { get, patch, post } from "../api.js";
import { btn, confirmCard, el, empty, errorBox, field, input, loading, md, modal, select, status, textarea, when } from "../ui.js";

const FILTERS = [["ouvertes", "Ouvertes"], ["en_cours", "En cours"], ["attente_autorisation", "À valider"], ["terminee", "Terminées"], ["echouee", "Échouées"], ["bloquee", "Bloquées"], ["annulee", "Annulées"], ["", "Toutes"]];

export async function render(view, params, app) {
  if (params[0]) return detail(view, Number(params[0]), app);
  let filter = "ouvertes";
  const page = el("div", { class: "page" });
  const body = el("div");
  const tabs = el("div", { class: "tabs", role: "tablist" });
  page.append(el("div", { class: "toolbar" }, tabs, el("span", { class: "grow" }), btn("Nouvelle tâche", () => createModal(app, load), { cls: "primary", icon: "plus" })), body);
  view.append(page);
  const drawTabs = () => tabs.replaceChildren(...FILTERS.map(([v, l]) => el("button", { role: "tab", "aria-selected": String(v === filter), onclick: () => { filter = v; drawTabs(); load(); } }, l)));
  async function load() {
    let rows;
    try { rows = await get(`/api/tasks?status=${filter}`); } catch (e) { return body.replaceChildren(errorBox(e)); }
    if (!rows.length) return body.replaceChildren(empty("Aucune tâche ici.", "Créez une tâche ou demandez quelque chose à Nova."));
    body.replaceChildren(el("table", { class: "table" },
      el("thead", {}, el("tr", {}, el("th", {}, "Tâche"), el("th", {}, "Statut"), el("th", {}, "Résultat"), el("th", {}, "Agent"), el("th", {}, "Projet"), el("th", {}, "Échéance"), el("th", {}, ""))),
      el("tbody", {}, ...rows.map((t) => el("tr", {},
        el("td", {}, el("a", { href: `#/taches/${t.id}` }, t.title), el("div", { class: "faint xs" }, `#${t.id} – ${t.kind === "todo" ? "manuelle" : "exécutée par Nova"} – ${when(t.updated_at)}`)),
        el("td", {}, status(t.status)), el("td", {}, t.result_state ? status(t.result_state) : ""), el("td", { class: "small" }, t.agent),
        el("td", { class: "small" }, t.project_name || ""), el("td", { class: "small" }, t.due_date || ""),
        el("td", {}, actions(t, load)))))));
  }
  drawTabs(); await load();
  const off = app.on((ev) => { if (ev.type === "task") { clearTimeout(page._t); page._t = setTimeout(load, 300); } });
  return off;
}

function actions(t, reload) {
  const a = el("div", { class: "actions", style: { display: "flex", gap: "4px", justifyContent: "flex-end" } });
  const act = (label, path, ic, cls = "sm ghost") => btn(label, async () => { await post(`/api/tasks/${t.id}/${path}`); reload(); }, { cls, icon: ic });
  if (t.kind === "todo" && !["terminee", "annulee"].includes(t.status)) a.append(act("Terminer", "complete", "check"));
  if (!["terminee", "annulee"].includes(t.status)) a.append(btn("Modifier", () => editModal(t, reload), { cls: "sm ghost", icon: "edit" }));
  if (t.status === "en_cours") a.append(act("Pause", "pause", "pause"));
  if (["pause", "interrompue", "bloquee", "echouee", "attente_reponse"].includes(t.status) && t.kind !== "todo") a.append(act("Reprendre", "resume", "play"));
  if (!["terminee", "annulee", "echouee"].includes(t.status)) a.append(act("Annuler", "cancel", "x"));
  return a;
}

function editModal(t, reload) {
  const title = input({ value: t.title }), due = input({ type: "datetime-local", value: (t.due_date || "").slice(0, 16).replace(/^(\d{4}-\d\d-\d\d)$/, "$1T09:00") });
  const prio = select([[3, "Haute"], [2, "Normale"], [1, "Basse"]], t.priority);
  modal("Modifier la tâche", el("div", { class: "form" }, field("Titre", title), el("div", { class: "form-row" }, field("Échéance", due), field("Priorité", prio)),
    el("p", { class: "small faint" }, "Une notification macOS est envoyée à l'échéance si Nova (ou son service) est en marche.")),
    ["close", (close) => btn("Enregistrer", async () => { await patch(`/api/tasks/${t.id}`, { title: title.value, due_date: due.value || null, priority: Number(prio.value) }); close(); reload(); }, { cls: "primary" })]);
}

function createModal(app, reload) {
  const title = input({ placeholder: "Ex. Préparer le devis du restaurant" });
  const obj = textarea({ placeholder: "Objectif détaillé (facultatif pour une tâche manuelle)" });
  const exec = el("input", { type: "checkbox" });
  const prio = select([[3, "Haute"], [2, "Normale"], [1, "Basse"]], 2);
  const due = input({ type: "datetime-local" });
  const agent = select([["general", "Orchestrateur"], ["developpeur", "Développeur"], ["recherche", "Recherche"], ["fichiers", "Fichiers"], ["redaction", "Rédaction"], ["projet", "Gestion de projet"], ["prospection", "Prospection"], ["qualite", "Contrôle qualité"]], "general");
  const projSel = select([["", "Aucun projet"]], "");
  get("/api/projects").then((ps) => ps.forEach((p) => projSel.append(el("option", { value: p.id }, p.name))));
  modal("Nouvelle tâche", el("div", { class: "form" }, field("Titre", title), field("Objectif", obj),
    el("div", { class: "form-row" }, field("Priorité", prio), field("Échéance", due), field("Projet", projSel)),
    el("label", { class: "switch" }, exec, "Faire exécuter par Nova maintenant"), field("Agent", agent)),
    ["close", (close) => btn("Créer la tâche", async () => {
      await post("/api/tasks", { title: title.value, objective: obj.value || title.value, execute: exec.checked, priority: Number(prio.value),
        due_date: due.value || null, project_id: projSel.value || null, agent: agent.value });
      close(); reload();
    }, { cls: "primary" })]);
}

async function detail(view, id, app) {
  const page = el("div", { class: "page narrow" }, loading());
  view.append(page);
  async function load() {
    let t;
    try { t = await get(`/api/tasks/${id}`); } catch (e) { return page.replaceChildren(errorBox(e)); }
    document.querySelector("#page-sub").textContent = `Tâche #${t.id}`;
    const pending = t.confirmations.filter((c) => c.status === "en_attente");
    page.replaceChildren(
      el("div", { class: "crumbs" }, el("a", { href: "#/taches" }, "Tâches"), "/", `#${t.id}`),
      el("h2", { class: "title" }, t.title),
      el("div", { class: "state-line", style: { marginBottom: "14px" } }, status(t.status), t.result_state ? status(t.result_state) : null, el("span", {}, `agent ${t.agent}`),
        el("span", {}, `${t.steps_done} action(s)`), t.usage?.calls ? el("span", {}, `${t.usage.calls} appel(s) IA`) : null, actions(t, load)),
      el("dl", { class: "kv" }, el("dt", {}, "Objectif"), el("dd", {}, t.objective), el("dt", {}, "Priorité"), el("dd", {}, String(t.priority)),
        el("dt", {}, "Limites"), el("dd", {}, `${t.max_steps} tours, ${t.max_seconds} s, ${t.max_retries} nouvelles tentatives`),
        t.depends_on.length ? [el("dt", {}, "Dépend de"), el("dd", {}, t.depends_on.map((d) => `#${d}`).join(", "))] : null,
        t.next_action ? [el("dt", {}, "Prochaine action"), el("dd", { class: "rare" }, t.next_action)] : null,
        el("dt", {}, "Créée"), el("dd", {}, when(t.created_at)), t.finished_at ? [el("dt", {}, "Terminée"), el("dd", {}, when(t.finished_at))] : null),
      ...pending.map((c) => el("div", { style: { marginTop: "16px" } }, confirmCard(c, load))),
      t.result ? [el("h3", {}, "Compte rendu"), el("div", { class: "panel" }, md(t.result))] : null,
      t.error ? el("div", { class: "error-box", style: { marginTop: "12px" } }, t.error) : null,
      el("h3", {}, "Étapes"),
      t.steps.length ? el("table", { class: "table" }, el("tbody", {}, ...t.steps.map((s) => el("tr", {},
        el("td", { class: "faint" }, s.idx), el("td", {}, s.kind === "modele" ? "Réflexion du modèle" : el("span", { class: "mono" }, s.tool)),
        el("td", {}, status(s.status === "termine" ? (s.result?.state || "terminee") : s.status === "echec" ? "echoue" : s.status)),
        el("td", { class: "small" }, s.kind === "modele" ? (s.result?.message || s.error || "").slice(0, 260) : (s.error || s.result?.verification || ""),
          s.result?.result ? el("details", { class: "tool-out" }, el("summary", {}, "données"), el("pre", {}, JSON.stringify(s.result.result, null, 2).slice(0, 5000))) : null),
        el("td", { class: "faint xs" }, s.duration_ms != null ? `${s.duration_ms} ms` : ""))))) : el("p", { class: "faint" }, "Aucune étape."),
      t.sources.length ? [el("h3", {}, "Sources consultées"), el("div", { class: "list" }, ...t.sources.map((s) => el("div", { class: "row" }, el("span", { class: "badge plain" }, s.confidence || ""),
        el("div", { class: "main-col" }, el("a", { href: s.url, target: "_blank", rel: "noopener noreferrer", class: "t small" }, s.title || s.url), el("div", { class: "d xs" }, `consulté ${when(s.fetched_at)}${s.published_at ? ", publié " + s.published_at : ""}`)), el("span", {}))))] : null,
      el("h3", {}, "Journal"), el("div", { class: "events" }, ...t.events.map((e) => el("div", { class: "event " + e.level }, el("time", {}, (e.ts || "").slice(11, 19)), el("div", { class: "m" }, e.message)))));
  }
  await load();
  const off = app.on((ev) => { if ((ev.type === "task" && ev.task_id === id) || (ev.type === "event" && ev.event.task_id === id)) { clearTimeout(page._t); page._t = setTimeout(load, 300); } });
  return off;
}
