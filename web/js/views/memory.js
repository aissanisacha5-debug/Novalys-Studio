// Mémoire : consultation, recherche, ajout, correction, oubli, export/import, doublons, mémoire par projet.
import { del, get, patch, post } from "../api.js";
import { btn, download, el, empty, errorBox, field, handleError, input, loading, modal, select, status, textarea, toast, toggle, when } from "../ui.js";

const TYPES = { preference: "Préférence", info_personnelle: "Info personnelle", objectif: "Objectif", projet: "Projet", decision: "Décision", tache: "Tâche",
  resultat: "Résultat", instruction: "Instruction", connaissance: "Connaissance", operation: "Opération", resume_conversation: "Résumé", reference_document: "Document", temporaire: "Temporaire" };
const NATURES = [["fait", "Fait"], ["preference", "Préférence"], ["hypothese", "Hypothèse"]];

export async function render(view, params, app) {
  let q = "", type = "", obsolete = false;
  const body = el("div");
  const search = input({ placeholder: "Rechercher dans la mémoire…" });
  search.addEventListener("input", () => { q = search.value; clearTimeout(body._t); body._t = setTimeout(load, 300); });
  const typeSel = select([["", "Tous les types"], ...Object.entries(TYPES)], "");
  typeSel.addEventListener("change", () => { type = typeSel.value; load(); });
  const stats = el("div");
  const st = await get("/api/settings");
  const memToggle = toggle("JARVIS peut mémoriser de nouvelles informations (désactivé : il consulte seulement la mémoire existante ; vous pouvez toujours ajouter vous-même)",
    st.settings.memory?.enabled !== false, async (x, i) => {
      try { await patch("/api/settings", { memory: { enabled: x } }); toast(x ? "Mémorisation activée." : "Mémorisation désactivée."); }
      catch (e) { i.checked = !x; handleError(e); }
    });
  view.append(el("div", { class: "page" }, stats,
    el("div", { class: "toolbar" }, search, el("div", { style: { width: "180px" } }, typeSel),
      el("label", { class: "switch small" }, (() => { const c = el("input", { type: "checkbox" }); c.addEventListener("change", () => { obsolete = c.checked; load(); }); return c; })(), "Inclure l'obsolète"),
      el("span", { class: "grow" }),
      btn("Ajouter", () => edit(null, load), { cls: "primary", icon: "plus" }),
      btn("Exporter", async () => download(`memoire-jarvis-${new Date().toISOString().slice(0, 10)}.json`, JSON.stringify(await get("/api/memory/export"), null, 2), "application/json"), { cls: "ghost", icon: "download" }),
      btn("Importer", () => importModal(load), { cls: "ghost" }),
      btn("Fusionner les doublons", async () => { const r = await post("/api/memory/cleanup"); toast(`${r.doublons_supprimes} doublon(s) fusionné(s).`); load(); }, { cls: "ghost" })),
    memToggle,
    el("p", { class: "small faint" }, "JARVIS ne mémorise jamais de mot de passe, clé, donnée bancaire ni secret. Chaque souvenir indique sa source et sa raison ; vous pouvez le corriger ou l'oublier. Les informations « temporaires » liées à une conversation sont effacées avec elle ; supprimer une conversation ne touche pas au reste de la mémoire."),
    body));
  async function load() {
    body.replaceChildren(loading());
    let d; try { d = await get(`/api/memory?q=${encodeURIComponent(q)}&type=${type}&obsolete=${obsolete ? 1 : 0}`); } catch (e) { return body.replaceChildren(errorBox(e)); }
    stats.replaceChildren(el("div", { class: "metrics" }, el("div", { class: "metric" }, el("div", { class: "v" }, d.stats.total), el("div", { class: "l" }, "souvenirs valides")),
      ...Object.entries(d.stats.par_type).slice(0, 4).map(([k, v]) => el("div", { class: "metric" }, el("div", { class: "v" }, v), el("div", { class: "l" }, TYPES[k] || k))),
      el("div", { class: "metric" }, el("div", { class: "v" }, d.duplicates), el("div", { class: "l" }, "groupes de doublons"))));
    if (!d.items.length) return body.replaceChildren(empty("Mémoire vide.", "Dites à JARVIS « retiens que… » ou ajoutez une information."));
    body.replaceChildren(el("table", { class: "table" }, el("thead", {}, el("tr", {}, ...["Information", "Type", "Nature", "Statut", "Source et raison", "Mise à jour", ""].map((h) => el("th", {}, h)))),
      el("tbody", {}, ...d.items.map((m) => el("tr", {},
        el("td", {}, m.content, m.project_name ? el("div", { class: "faint xs" }, `projet ${m.project_name}`) : null),
        el("td", { class: "small" }, TYPES[m.type] || m.type), el("td", {}, el("span", { class: "badge " + (m.nature === "hypothese" ? "wait" : m.nature === "preference" ? "rare" : "plain") }, m.nature)),
        el("td", {}, status(m.status)), el("td", { class: "small muted" }, m.source, m.reason ? el("div", { class: "xs" }, m.reason) : null),
        el("td", { class: "small faint" }, when(m.updated_at)),
        el("td", {}, el("div", { style: { display: "flex", gap: "4px" } }, btn("Corriger", () => edit(m, load), { cls: "sm ghost", icon: "edit" }),
          btn("Oublier", async () => { modal("Oublier cette information ?", el("p", {}, m.content), ["close", (c) => btn("Oublier", async () => { await del(`/api/memory/${m.id}`); c(); toast("Information oubliée."); load(); }, { cls: "danger" })]); }, { cls: "sm ghost", icon: "trash" }))))))));
  }
  await load();
}

function edit(m, reload) {
  const content = textarea({ value: m?.content || "" });
  const type = select(Object.entries(TYPES), m?.type || "connaissance"), nature = select(NATURES, m?.nature || "fait");
  const st = select([["valide", "Valide"], ["a_verifier", "À vérifier"], ["obsolete", "Obsolète"]], m?.status || "valide");
  const reason = input({ value: m?.reason || "", placeholder: "Pourquoi mémoriser ?" });
  const proj = select([["", "Aucun projet"]], m?.project_id || "");
  get("/api/projects").then((ps) => ps.forEach((p) => proj.append(el("option", { value: p.id, selected: p.id === m?.project_id }, p.name))));
  modal(m ? "Corriger l'information" : "Ajouter à la mémoire", el("div", { class: "form" }, field("Information", content),
    el("div", { class: "form-row" }, field("Type", type), field("Nature", nature), field("Statut", st)), field("Raison", reason), field("Projet", proj)),
    ["close", (close) => btn("Enregistrer", async () => {
      const body = { content: content.value, type: type.value, nature: nature.value, status: st.value, reason: reason.value, project_id: proj.value ? Number(proj.value) : null };
      if (m) await patch(`/api/memory/${m.id}`, body); else await post("/api/memory", body);
      close(); reload();
    }, { cls: "primary" })]);
}

function importModal(reload) {
  const file = el("input", { type: "file", accept: "application/json" });
  modal("Importer une mémoire (format JARVIS)", file, ["close", (close) => btn("Importer", async () => {
    const f = file.files[0]; if (!f) return;
    try { const r = await post("/api/memory/import", JSON.parse(await f.text())); toast(`${r.added} ajouté(s), ${r.skipped} ignoré(s).`); close(); reload(); } catch (e) { handleError(e); }
  }, { cls: "primary" })]);
}
