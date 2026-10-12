// Prospection et agence : CRM CYPHER (lecture seule), revenus confirmés vs prévisions, oppositions, prospection assistée.
import { get } from "../api.js";
import { btn, el, errorBox, input, loading } from "../ui.js";
import { quickAsk } from "../app.js";

export async function render(view, params, app) {
  const page = el("div", { class: "page" }, loading());
  view.append(page);
  let d; try { d = await get("/api/agency"); } catch (e) { return page.replaceChildren(errorBox(e)); }
  const eur = (n) => (n || 0).toLocaleString("fr-FR", { style: "currency", currency: "EUR" });
  let tab = "prospects";
  const tabs = el("div", { class: "tabs", role: "tablist" });
  const body = el("div");
  const filter = input({ placeholder: "Filtrer…" });
  filter.addEventListener("input", draw);
  const sector = input({ placeholder: "Secteur et ville, ex. restaurants à Saint-Étienne" });
  page.replaceChildren(
    el("div", { class: "metrics" },
      el("div", { class: "metric" }, el("div", { class: "v" }, d.prospects.length), el("div", { class: "l" }, "prospects (CRM CYPHER)")),
      el("div", { class: "metric" }, el("div", { class: "v" }, d.clients.length), el("div", { class: "l" }, "clients")),
      el("div", { class: "metric" }, el("div", { class: "v rare" }, eur(d.revenus.confirmes)), el("div", { class: "l" }, "revenus confirmés (factures payées)")),
      el("div", { class: "metric" }, el("div", { class: "v" }, eur(d.revenus.en_attente_de_paiement)), el("div", { class: "l" }, "factures en attente (prévision)")),
      el("div", { class: "metric" }, el("div", { class: "v" }, eur(d.revenus.devis_ouverts)), el("div", { class: "l" }, "devis ouverts (prévision)")),
      el("div", { class: "metric" }, el("div", { class: "v" }, d.oppositions.length), el("div", { class: "l" }, "oppositions (jamais contactées)"))),
    el("div", { class: "panel" }, el("h3", { style: { marginTop: 0 } }, "Prospection assistée"),
      el("p", { class: "small muted" }, "JARVIS cherche des entreprises, audite leurs sites publics, écarte les doublons et les oppositions, puis prépare des brouillons. Il n'envoie rien."),
      el("div", { class: "toolbar", style: { marginBottom: 0 } }, sector,
        btn("Lancer la recherche", () => quickAsk(`Trouve 5 entreprises pertinentes (${sector.value || "commerces locaux"}) qui auraient besoin d'un site ou d'un meilleur site. Pour chacune : source, audit public du site, vérifie qu'elle n'est pas déjà dans le CRM ni dans les oppositions, qualifie-la et prépare un brouillon d'e-mail local personnalisé (sans prix inventés). N'envoie rien.`), { cls: "primary" }))),
    el("div", { class: "toolbar", style: { marginTop: "20px" } }, tabs, el("span", { class: "grow" }), filter),
    body,
    el("p", { class: "small faint" }, `Source : ${d.source} (lecture seule). Les modifications du CRM, des offres et des prix se font dans CYPHER, avec votre validation. ${d.revenus.note}`));
  const TABS = [["prospects", "Prospects"], ["clients", "Clients"], ["devis", "Devis"], ["factures", "Factures"], ["oppositions", "Oppositions"]];
  function drawTabs() { tabs.replaceChildren(...TABS.map(([k, l]) => el("button", { role: "tab", "aria-selected": String(k === tab), onclick: () => { tab = k; drawTabs(); draw(); } }, `${l} (${d[k].length})`))); }
  function draw() {
    const rows = d[tab].filter((r) => !filter.value || Object.values(r).join(" ").toLowerCase().includes(filter.value.toLowerCase()));
    if (!rows.length) return body.replaceChildren(el("p", { class: "faint small" }, "Aucune ligne."));
    const cols = Object.keys(rows[0]).slice(0, 8);
    body.replaceChildren(el("div", { style: { overflowX: "auto" } }, el("table", { class: "table" }, el("thead", {}, el("tr", {}, ...cols.map((c) => el("th", {}, c)))),
      el("tbody", {}, ...rows.slice(0, 300).map((r) => el("tr", {}, ...cols.map((c) => el("td", { class: "small" }, String(r[c] ?? "").slice(0, 90)))))))));
  }
  drawTabs(); draw();
}
