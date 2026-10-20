// Fichiers : navigation dans les dossiers autorisés (via les outils, donc via les permissions), lecture,
// création de dossier, renommage, copie, suppression (corbeille Nova, confirmation), doublons, archive.
import { get, post } from "../api.js";
import { btn, el, empty, errorBox, field, handleError, input, loading, modal, toast } from "../ui.js";

const tool = (id, args) => post(`/api/tools/${id}/invoke`, { args }).then((r) => r.result);

export async function render(view, params, app) {
  const s = await get("/api/settings");
  const dirs = s.settings.allowed_dirs;
  let cwd = decodeURIComponent(params.join("/") || "") || dirs[0].path;
  const page = el("div", { class: "page" });
  const body = el("div");
  view.append(page);
  page.append(el("div", { class: "toolbar" }, ...dirs.map((d) => btn(d.label || d.path, () => { cwd = d.path; load(); }, { cls: "sm" + (cwd.startsWith(d.path) ? "" : " ghost"), title: d.path })),
    el("span", { class: "grow" }),
    btn("Nouveau dossier", () => { const n = input({ placeholder: "nom-du-dossier" }); modal("Nouveau dossier", field(`Dans ${cwd}`, n), ["close", (c) => btn("Créer", async () => { await tool("dossier_creer", { path: `${cwd}/${n.value}` }); c(); load(); }, { cls: "primary" })]); }, { cls: "sm", icon: "plus" }),
    btn("Doublons", async () => { const r = await tool("doublons_detecter", { root: cwd }); modal("Fichiers en double", r.groups.length ? el("div", { class: "list" }, ...r.groups.map((g) => el("div", { class: "row" }, el("span", { class: "faint xs" }, `${Math.round(g.size / 1024)} Ko`), el("div", { class: "main-col mono" }, g.files.join("\n")), el("span", {})))) : el("p", {}, "Aucun doublon."), ["close"], true); }, { cls: "sm ghost" })),
    el("p", { class: "small muted" }, "Seuls les dossiers autorisés sont accessibles (Paramètres > Sécurité). Le dossier CYPHER est en lecture seule ; les suppressions vont dans la corbeille Nova et demandent votre accord."),
    body);

  async function load() {
    body.replaceChildren(loading());
    let r;
    try { r = await tool("dossier_lister", { path: cwd }); } catch (e) { return body.replaceChildren(errorBox(e)); }
    const parts = r.path.split("/").filter(Boolean);
    const crumbs = el("div", { class: "crumbs" }, ...parts.map((p, i) => [el("button", { type: "button", onclick: () => { cwd = "/" + parts.slice(0, i + 1).join("/"); load(); } }, p), "/"]));
    if (!r.items.length) return body.replaceChildren(crumbs, empty("Dossier vide.", "Demandez à Nova d'y créer des fichiers."));
    body.replaceChildren(crumbs, el("table", { class: "table" }, el("thead", {}, el("tr", {}, el("th", {}, "Nom"), el("th", {}, "Taille"), el("th", {}, "Modifié"), el("th", {}, ""))),
      el("tbody", {}, ...r.items.map((it) => {
        const full = `${r.path}/${it.name}`;
        return el("tr", {},
          el("td", {}, el("a", { href: "#", onclick: (e) => { e.preventDefault(); it.dir ? (cwd = full, load()) : open(full); } }, (it.dir ? "▸ " : "") + it.name)),
          el("td", { class: "small faint" }, it.dir ? "—" : fmt(it.size)), el("td", { class: "small faint" }, it.modified),
          el("td", {}, el("div", { style: { display: "flex", gap: "4px", justifyContent: "flex-end" } },
            btn("Renommer", () => { const n = input({ value: it.name }); modal("Renommer", n, ["close", (c) => btn("Renommer", async () => { await tool("fichier_deplacer", { src: full, dst: `${r.path}/${n.value}` }); c(); load(); }, { cls: "primary" })]); }, { cls: "sm ghost" }),
            btn("Copier", async () => { await tool("fichier_copier", { src: full, dst: `${full}-copie` }); toast("Copie créée."); load(); }, { cls: "sm ghost" }),
            btn("Ouvrir", async () => { await tool("fichier_ouvrir", { path: full }); }, { cls: "sm ghost", icon: "external" }),
            btn("Supprimer", async () => { await tool("fichier_supprimer", { path: full }); load(); }, { cls: "sm ghost", icon: "trash" }))));
      }))));
  }
  async function open(path) {
    try {
      const r = await tool("fichier_lire", { path, max_chars: 60000 });
      modal(path.split("/").pop(), el("pre", { class: "out" }, r.content + (r.truncated ? "\n…(tronqué)" : "")), ["close"], true);
    } catch (e) { handleError(e); }
  }
  await load();
}
const fmt = (n) => n < 1024 ? `${n} o` : n < 1048576 ? `${(n / 1024).toFixed(1)} Ko` : `${(n / 1048576).toFixed(1)} Mo`;
