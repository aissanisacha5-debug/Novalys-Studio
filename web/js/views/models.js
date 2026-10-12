// Modèles IA : fournisseurs réellement disponibles, modèle et modèle de remplacement, test, consommation.
import { get, patch, post } from "../api.js";
import { btn, el, errorBox, field, handleError, loading, select, toast } from "../ui.js";

export async function render(view, params, app) {
  const page = el("div", { class: "page" }, loading());
  view.append(page);
  async function load() {
    let ps, s, costs;
    try { [ps, s, costs] = await Promise.all([get("/api/providers"), get("/api/settings"), get("/api/costs")]); } catch (e) { return page.replaceChildren(errorBox(e)); }
    const ai = s.settings.ai;
    const active = ps.find((p) => p.id === ai.provider);
    const save = async (p) => { try { await patch("/api/settings", { ai: p }); toast("Réglage enregistré."); load(); } catch (e) { handleError(e); } };
    const provSel = select(ps.map((p) => [p.id, `${p.label}${p.available ? "" : " — indisponible"}`]), ai.provider);
    provSel.addEventListener("change", () => save({ provider: provSel.value }));
    const models = active?.models?.length ? active.models : [ai.model];
    const modelSel = select(models, ai.model); modelSel.addEventListener("change", () => save({ model: modelSel.value }));
    const fbSel = select([["", "Aucun"], ...models.map((m) => [m, m])], ai.fallback_model || ""); fbSel.addEventListener("change", () => save({ fallback_model: fbSel.value || null }));
    page.replaceChildren(
      el("div", { class: "panel" }, el("h3", { style: { marginTop: 0 } }, "Fournisseur actif"),
        el("div", { class: "form-row" }, field("Fournisseur", provSel), field("Modèle", modelSel), field("Modèle de remplacement", fbSel)),
        el("div", { class: "toolbar", style: { marginTop: "12px", marginBottom: 0 } },
          btn("Tester le fournisseur", async () => { const r = await post("/api/connectors/claude_code/test"); toast(r.ok ? `Réponse reçue : ${r.detail} (${r.ms} ms)` : `Échec : ${r.detail}`, r.ok ? "" : "err"); }, { cls: "primary" })),
        el("p", { class: "small muted" }, "Claude via Claude Code utilise la connexion de ce Mac à votre abonnement Claude : pas de clé API ni de facturation à l'appel, mais les limites d'usage de l'abonnement s'appliquent. ",
          "JARVIS l'utilise comme moteur de texte sans aucun outil Claude Code : toutes les actions passent par les outils et les permissions de JARVIS.")),
      el("h3", {}, "Fournisseurs"),
      el("table", { class: "table" }, el("thead", {}, el("tr", {}, ...["Fournisseur", "État", "Local / distant", "Capacités", "Modèles"].map((h) => el("th", {}, h)))),
        el("tbody", {}, ...ps.map((p) => el("tr", {}, el("td", {}, p.label, p.active ? el("span", { class: "badge ok", style: { marginLeft: "6px" } }, "actif") : null),
          el("td", {}, el("span", { class: "badge " + (p.available ? "ok" : "plain") }, p.available ? "disponible" : "indisponible"), el("div", { class: "faint xs" }, p.reason)),
          el("td", { class: "small" }, p.remote ? "distant" : "100 % local"), el("td", { class: "small" }, p.capabilities.join(", ")), el("td", { class: "small mono" }, p.models.join(", ")))))),
      el("h3", {}, "Consommation"),
      el("table", { class: "table" }, el("thead", {}, el("tr", {}, ...["Fournisseur", "Modèle", "Nature du coût", "Appels", "Jetons entrée", "Jetons sortie", "Montant"].map((h) => el("th", {}, h)))),
        el("tbody", {}, ...costs.by_model.map((r) => el("tr", {}, el("td", {}, r.provider), el("td", { class: "mono small" }, r.model || ""),
          el("td", {}, el("span", { class: "badge " + ({ reel: "err", estimation: "wait", inclus_abonnement: "rare", gratuit_local: "ok" }[r.cost_kind] || "plain") }, { reel: "coût réel", estimation: "estimation", inclus_abonnement: "inclus dans l'abonnement", gratuit_local: "gratuit (local)", inconnu: "inconnu" }[r.cost_kind] || r.cost_kind)),
          el("td", {}, r.calls), el("td", {}, r.input_tokens), el("td", {}, r.output_tokens),
          el("td", { class: "small" }, r.cost_usd == null ? "inconnu" : r.cost_kind === "inclus_abonnement" ? `≈ ${r.cost_usd.toFixed(3)} $ équivalent, non facturé` : `${r.cost_usd.toFixed(3)} $`))))),
      el("p", { class: "small faint" }, "Recherche sémantique (embeddings) : non activée. La recherche plein texte suffit pour l'instant ; Ollama (local) pourra l'apporter s'il est installé."));
  }
  await load();
}
