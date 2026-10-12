// Historique : journal d'activité filtrable, export, historique des commandes.
import { get } from "../api.js";
import { btn, download, el, errorBox, input, loading, select } from "../ui.js";

export async function render(view, params, app) {
  const q = input({ placeholder: "Rechercher dans le journal…" });
  const level = select([["", "Tous niveaux"], ["succes", "Succès"], ["info", "Info"], ["attention", "Attention"], ["erreur", "Erreur"]], "");
  const kind = select([["", "Tous types"], ...["tache_debut", "tache_fin", "outil_appel", "outil_resultat", "outil_erreur", "autorisation_demandee", "autorisation_accordee",
    "autorisation_refusee", "tache_annulation", "tache_reprise", "memoire", "automatisation", "sauvegarde", "parametres", "demarrage", "arret"].map((k) => [k, k])], "");
  const body = el("div"), shell = el("div");
  [q, level, kind].forEach((x) => x.addEventListener(x === q ? "input" : "change", () => { clearTimeout(body._t); body._t = setTimeout(load, 250); }));
  view.append(el("div", { class: "page" },
    el("div", { class: "toolbar" }, q, el("div", { style: { width: "160px" } }, level), el("div", { style: { width: "210px" } }, kind), el("span", { class: "grow" }),
      btn("Exporter le rapport", async () => { const r = await get("/api/journal/export"); download(`journal-jarvis-${new Date().toISOString().slice(0, 10)}.md`, r.markdown); }, { cls: "ghost", icon: "download" })),
    el("p", { class: "small faint" }, "Le journal permet de reconstruire chaque tâche sans conserver les contenus privés ; les secrets sont expurgés. Rétention configurable (Paramètres)."),
    body, el("h3", {}, "Commandes exécutées"), shell));
  async function load() {
    body.replaceChildren(loading());
    let rows; try { rows = await get(`/api/journal?q=${encodeURIComponent(q.value)}&level=${level.value}&kind=${kind.value}&limit=400`); } catch (e) { return body.replaceChildren(errorBox(e)); }
    body.replaceChildren(el("table", { class: "table" }, el("tbody", {}, ...rows.map((e) => el("tr", {},
      el("td", { class: "faint xs", style: { whiteSpace: "nowrap" } }, e.ts.slice(0, 19).replace("T", " ")),
      el("td", {}, el("span", { class: "badge " + ({ erreur: "err", attention: "wait", succes: "ok" }[e.level] || "plain") }, e.level)),
      el("td", { class: "xs mono" }, e.kind), el("td", { class: "small" }, e.message, e.task_id ? el("a", { href: `#/taches/${e.task_id}`, class: "xs", style: { marginLeft: "6px" } }, `tâche #${e.task_id}`) : null))))));
  }
  async function loadShell() {
    const rows = await get("/api/shell/history");
    shell.replaceChildren(rows.length ? el("table", { class: "table" }, el("tbody", {}, ...rows.map((r) => el("tr", {},
      el("td", { class: "faint xs" }, r.ts.slice(0, 16).replace("T", " ")), el("td", { class: "mono" }, r.command),
      el("td", {}, r.blocked ? el("span", { class: "badge err" }, "bloquée") : el("span", { class: "badge " + (r.exit_code === 0 ? "ok" : "err") }, `code ${r.exit_code}`)),
      el("td", { class: "small muted" }, r.reason || (r.duration_ms != null ? `${r.duration_ms} ms` : "")))))) : el("p", { class: "faint small" }, "Aucune commande exécutée."));
  }
  await Promise.all([load(), loadShell()]);
}
