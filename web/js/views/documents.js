// Documents : créer un document (md, txt, html, docx, pdf, csv, xlsx, json), rapports existants, rédaction par Nova.
import { post } from "../api.js";
import { btn, el, field, input, loading, select, textarea, toast } from "../ui.js";
import { quickAsk } from "../app.js";

const tool = (id, args) => post(`/api/tools/${id}/invoke`, { args });

export async function render(view, params, app) {
  const name = input({ placeholder: "rapports/mon-document" });
  const fmt = select(["md", "docx", "pdf", "html", "txt", "csv", "xlsx", "json"], "md");
  const title = input({ placeholder: "Titre" });
  const content = textarea({ placeholder: "Contenu en Markdown (titres #, listes -, **gras**, tableaux |a|b|). Pour csv/xlsx : lignes séparées par des virgules.", style: { minHeight: "220px" } });
  const result = el("div");
  const list = el("div", {}, loading());
  view.append(el("div", { class: "page" },
    el("div", { class: "grid-2" },
      el("div", { class: "panel" }, el("h3", { style: { marginTop: 0 } }, "Créer un document"),
        el("div", { class: "form" }, el("div", { class: "form-row" }, field("Fichier (dans l'espace de travail)", name), field("Format", fmt)), field("Titre", title), field("Contenu", content),
          el("div", {}, btn("Créer et vérifier", async () => {
            const path = `${name.value || "documents/sans-titre"}.${fmt.value}`;
            const r = await tool("document_creer", { path, format: fmt.value, title: title.value, content: content.value });
            result.replaceChildren(el("p", { class: "small" }, `${r.state === "confirme" ? "Créé et vérifié" : "Créé"} : `, el("span", { class: "mono" }, r.result.path), ` (${r.verification})`,
              " ", btn("Ouvrir", () => tool("fichier_ouvrir", { path: r.result.path }), { cls: "sm" })));
            toast("Document créé."); loadList();
          }, { cls: "primary" })), result)),
      el("div", { class: "panel" }, el("h3", { style: { marginTop: 0 } }, "Faire rédiger par Nova"),
        el("p", { class: "small muted" }, "Décrivez le document : Nova le rédige, le crée au bon format et vérifie le fichier."),
        ...[["Proposition commerciale", "Rédige une proposition commerciale pour un site vitrine (structure type, sans prix inventés : laisse les prix à compléter), au format docx dans workspace/documents."],
          ["Compte rendu de réunion", "Prépare un modèle de compte rendu de réunion client en Markdown dans workspace/documents."],
          ["Documentation technique", "Rédige la documentation technique du dernier site créé dans workspace/sites (structure, pages, déploiement)."]]
          .map(([l, p]) => el("div", { style: { marginBottom: "8px" } }, btn(l, () => quickAsk(p), { cls: "sm" }))))),
    el("h3", {}, "Documents et rapports récents"), list));

  async function loadList() {
    const out = [];
    for (const d of ["documents", "rapports", "brouillons"]) {
      try { const r = await tool("dossier_lister", { path: d }); out.push(...r.result.items.filter((i) => !i.dir).map((i) => ({ ...i, path: `${r.result.path}/${i.name}`, dir: d }))); } catch { /* dossier pas encore créé */ }
    }
    out.sort((a, b) => b.modified.localeCompare(a.modified));
    list.replaceChildren(out.length ? el("div", { class: "list" }, ...out.slice(0, 40).map((f) => el("div", { class: "row" }, el("span", { class: "badge plain" }, f.dir),
      el("div", { class: "main-col" }, el("div", { class: "t small" }, f.name), el("div", { class: "d xs" }, f.modified)),
      btn("Ouvrir", () => tool("fichier_ouvrir", { path: f.path }), { cls: "sm ghost", icon: "external" }))))
      : el("p", { class: "faint small" }, "Aucun document pour l'instant."));
  }
  await loadList();
}
