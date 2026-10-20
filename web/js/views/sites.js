// Création de sites : brief → Nova (agent développeur) construit, contrôle, prévisualise ; contrôle qualité et paquet de déploiement.
import { get, post } from "../api.js";
import { btn, el, empty, errorBox, field, input, loading, modal, select, status, textarea, toast } from "../ui.js";
import { quickAsk } from "../app.js";

const tool = (id, args) => post(`/api/tools/${id}/invoke`, { args });

export async function render(view, params, app) {
  const biz = input({ placeholder: "Ex. Trattoria Da Marco, restaurant italien" });
  const city = input({ placeholder: "Ville" });
  const style = select([["auto", "Adapté au secteur (Nova choisit)"], ["premium", "Premium et sobre"], ["chaleureux", "Chaleureux et authentique"], ["moderne", "Moderne et dynamique"], ["minimal", "Minimaliste"]], "auto");
  const pages = input({ value: "Accueil, Menu ou Services, À propos, Contact, Mentions légales" });
  const notes = textarea({ placeholder: "Informations réelles fournies par le client (horaires, adresse, services, couleurs…). Ce qui manque sera marqué comme donnée fictive de démonstration." });
  const list = el("div", {}, loading());
  view.append(el("div", { class: "page" },
    el("div", { class: "panel" }, el("h3", { style: { marginTop: 0 } }, "Nouveau site"),
      el("div", { class: "form" }, el("div", { class: "form-row" }, field("Entreprise et activité", biz), field("Ville", city), field("Direction artistique", style)), field("Pages", pages), field("Informations du client", notes),
        el("div", {}, btn("Faire construire par Nova", () => {
          const slug = (biz.value || "site").toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "").slice(0, 40);
          quickAsk(`Crée un site vitrine complet pour « ${biz.value} »${city.value ? " à " + city.value : ""}, dans workspace/sites/${slug}. Pages : ${pages.value}. Direction artistique : ${style.value === "auto" ? "adaptée au secteur et au positionnement (pas un modèle générique)" : style.value}. Informations réelles : ${notes.value || "aucune"}. ` +
            "Utilise du HTML/CSS/JS statique, responsive, accessible, avec métadonnées SEO, Open Graph, robots.txt et sitemap.xml. N'invente ni avis, ni certification, ni prix : marque clairement les contenus fictifs de démonstration. " +
            "Ensuite lance site_controler et corrige jusqu'à 0 erreur, puis apercu_lancer et donne-moi l'adresse d'aperçu et un compte rendu.");
        }, { cls: "primary" })))),
    el("h3", {}, "Sites de l'espace de travail"), list));
  async function load() {
    let d; try { d = await get("/api/sites"); } catch (e) { return list.replaceChildren(errorBox(e)); }
    if (!d.sites.length) return list.replaceChildren(empty("Aucun site pour l'instant.", "Décrivez un client ci-dessus : Nova construit le site, le contrôle et lance l'aperçu."));
    list.replaceChildren(el("table", { class: "table" }, el("thead", {}, el("tr", {}, ...["Site", "Pages", "Contrôle", ""].map((h) => el("th", {}, h)))),
      el("tbody", {}, ...d.sites.map((s) => el("tr", {}, el("td", {}, s.name, el("div", { class: "faint xs mono" }, s.dir)), el("td", { class: "small" }, (s.pages || []).length),
        el("td", {}, s.error ? el("span", { class: "badge err" }, s.error) : [status(s.errors ? "echoue" : "confirme"), ` ${s.errors} erreur(s), ${s.warnings} avertissement(s)`]),
        el("td", {}, el("div", { style: { display: "flex", gap: "4px", justifyContent: "flex-end", flexWrap: "wrap" } },
          btn("Contrôler", async () => { const r = (await tool("site_controler", { dir: s.dir })).result;
            modal(`Contrôle — ${s.name}`, el("table", { class: "table" }, el("tbody", {}, ...r.issues.map((i) => el("tr", {}, el("td", {}, el("span", { class: "badge " + (i.level === "erreur" ? "err" : i.level === "avertissement" ? "wait" : "plain") }, i.level)), el("td", { class: "small mono" }, i.page), el("td", { class: "small" }, i.message))))), ["close"], true); }, { cls: "sm ghost" }),
          btn("Aperçu", async () => { const r = await tool("apercu_lancer", { dir: s.dir }); toast(`Aperçu : ${r.result.url} (${r.verification})`); await tool("url_ouvrir", { url: r.result.url }); }, { cls: "sm" }),
          btn("Corriger avec Nova", () => quickAsk(`Lance site_controler sur ${s.dir}, corrige toutes les erreurs et les avertissements importants, puis relance le contrôle et fais un compte rendu.`), { cls: "sm ghost" }),
          btn("Préparer le déploiement", async () => { const r = await tool("site_preparer_deploiement", { dir: s.dir }); toast(`Paquet prêt (non publié) : ${r.result.package}`); }, { cls: "sm ghost" }))))))));
  }
  await load();
}
