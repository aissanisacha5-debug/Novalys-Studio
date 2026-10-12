// Recherche interne : mémoire, conversations, tâches, projets, fichiers, sources web — avec provenance.
import { get } from "../api.js";
import { el, empty, errorBox, input, loading, status, when } from "../ui.js";

export async function render(view, params, app) {
  const q = input({ placeholder: "Rechercher partout (mémoire, conversations, tâches, projets, fichiers)…", "aria-label": "Recherche" });
  const out = el("div");
  const sec = (title, items, row) => items.length ? [el("h3", {}, `${title} (${items.length})`), el("div", { class: "list" }, ...items.map(row))] : [];
  const go = async () => {
    if (!q.value.trim()) return out.replaceChildren();
    out.replaceChildren(loading("Recherche…"));
    let r; try { r = await get(`/api/search?q=${encodeURIComponent(q.value)}`); } catch (e) { return out.replaceChildren(errorBox(e)); }
    const total = Object.values(r).reduce((n, a) => n + a.length, 0);
    if (!total) return out.replaceChildren(empty("Aucun résultat.", "Essayez un autre mot, ou demandez à JARVIS de chercher sur le web."));
    out.replaceChildren(
      ...sec("Mémoire", r.memory, (m) => el("div", { class: "row click", onclick: () => app.go("#/memoire") }, el("span", { class: "badge plain" }, m.type), el("div", { class: "main-col" }, el("div", { class: "small" }, m.content), el("div", { class: "d xs" }, `source : ${m.source}${m.project_name ? " – projet " + m.project_name : ""}`)), status(m.status))),
      ...sec("Conversations", r.messages, (m) => el("div", { class: "row click", onclick: () => app.go(`#/conversation/${m.conversation_id}`) }, el("span", { class: "faint xs" }, m.role === "user" ? "Sacha" : "JARVIS"), el("div", { class: "main-col" }, el("div", { class: "t small" }, m.title), el("div", { class: "d small" }, m.snippet)), el("span", { class: "faint xs" }, when(m.created_at)))),
      ...sec("Tâches", r.tasks, (t) => el("div", { class: "row click", onclick: () => app.go(`#/taches/${t.id}`) }, status(t.status), el("div", { class: "main-col small" }, t.title), el("span", {}))),
      ...sec("Projets", r.projects, (p) => el("div", { class: "row click", onclick: () => app.go(`#/projets/${p.id}`) }, status(p.status), el("div", { class: "main-col small" }, p.name), el("span", {}))),
      ...sec("Fichiers de l'espace de travail", r.files, (f) => el("div", { class: "row" }, el("span", { class: "faint xs" }, `l. ${f.line}`), el("div", { class: "main-col" }, el("div", { class: "d xs mono" }, f.file), el("div", { class: "small" }, f.text)), el("span", {}))),
      ...sec("Sources web", r.sources, (s) => el("div", { class: "row" }, el("span", {}), el("div", { class: "main-col" }, el("a", { href: s.url, target: "_blank", rel: "noopener noreferrer", class: "small" }, s.title || s.url)), el("span", { class: "faint xs" }, when(s.fetched_at)))));
  };
  let t; q.addEventListener("input", () => { clearTimeout(t); t = setTimeout(go, 350); });
  view.append(el("div", { class: "page narrow" }, q, el("p", { class: "small faint" }, "Recherche textuelle rapide (index plein texte). Chaque résultat indique sa provenance ; les projets restent séparés."), out));
  q.focus();
}
