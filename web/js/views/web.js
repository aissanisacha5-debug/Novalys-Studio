// Navigateur : recherche web publique, lecture de pages, audit de site, vérification de liens, sources consultées.
import { get, post } from "../api.js";
import { btn, el, errorBox, input, loading, status, toast, when } from "../ui.js";
import { quickAsk } from "../app.js";

const tool = (id, args) => post(`/api/tools/${id}/invoke`, { args });

export async function render(view, params, app) {
  const q = input({ placeholder: "Rechercher sur le web ou coller une adresse https://…", "aria-label": "Recherche ou adresse" });
  const out = el("div");
  const go = async () => {
    const v = q.value.trim(); if (!v) return;
    out.replaceChildren(loading(/^https?:\/\//.test(v) ? "Lecture de la page…" : "Recherche…"));
    try {
      if (/^https?:\/\//.test(v) && rendered.checked) {
        const r = await tool("navigateur_ouvrir", { url: v, max_chars: 20000 });
        const p = r.result;
        out.replaceChildren(el("div", { class: "panel" },
          el("div", { class: "state-line" }, status(r.state), "navigateur piloté (rendu JavaScript, profil séparé)", `consulté ${when(p.consulted_at)}`),
          el("h3", {}, p.title || p.url),
          el("div", { style: { display: "flex", gap: "8px", margin: "8px 0", flexWrap: "wrap" } },
            btn("Capture d'écran", async () => { const c = await tool("navigateur_capture", {}); toast(`Capture enregistrée : ${c.result.path}`); }, { cls: "sm" }),
            btn("Fermer le navigateur piloté", async () => { await tool("navigateur_fermer", {}); toast("Navigateur piloté fermé."); }, { cls: "sm ghost" })),
          p.fields.length ? [el("h3", {}, `Champs de formulaire (${p.fields.length})`),
            el("table", { class: "table" }, el("tbody", {}, ...p.fields.map((f) => el("tr", {}, el("td", { class: "mono" }, f.selector || "—"), el("td", { class: "small" }, f.label), el("td", { class: "small faint" }, f.type),
              el("td", {}, f.sensible ? el("span", { class: "badge err" }, "sensible : jamais rempli par JARVIS") : null))))),
            el("p", { class: "small faint" }, "Demandez à JARVIS de remplir ces champs : il les remplit et vérifie les valeurs ; l'envoi du formulaire demande toujours votre accord.")] : null,
          el("pre", { class: "out" }, p.content.replace(/<<<.*?>>>/g, "").trim())));
      } else if (/^https?:\/\//.test(v)) {
        const r = await tool("web_lire_page", { url: v, max_chars: 20000 });
        const p = r.result;
        out.replaceChildren(el("div", { class: "panel" },
          el("div", { class: "state-line" }, status(r.state), `HTTP ${p.status}`, `consulté ${when(p.consulted_at)}`, p.published_at ? `publié ${p.published_at}` : "date de publication inconnue"),
          el("h3", {}, p.title || p.url), el("p", { class: "small muted" }, p.description),
          el("div", { style: { display: "flex", gap: "8px", margin: "8px 0" } },
            btn("Auditer ce site", () => audit(v), { cls: "sm" }), btn("Vérifier les liens", () => links(v), { cls: "sm" }),
            btn("Résumer avec JARVIS", () => quickAsk(`Lis ${v} et résume l'essentiel, en séparant les faits vérifiés des hypothèses, avec la source.`), { cls: "sm primary" }),
            el("a", { class: "btn sm ghost", href: p.url, target: "_blank", rel: "noopener noreferrer" }, "Ouvrir dans le navigateur")),
          el("pre", { class: "out" }, p.content.replace(/<<<.*?>>>/g, "").trim())));
      } else {
        const r = await tool("web_rechercher", { query: v, max: 10 });
        out.replaceChildren(el("p", { class: "small muted" }, `${r.result.results.length} résultat(s) — ${r.result.engine}, ${when(r.result.consulted_at)}. Extraits non vérifiés : ouvrez une page pour la lire.`),
          el("div", { class: "list" }, ...r.result.results.map((x) => el("div", { class: "row" }, el("span", {}),
            el("div", { class: "main-col" }, el("a", { href: "#", class: "t", onclick: (e) => { e.preventDefault(); q.value = x.url; go(); } }, x.title), el("div", { class: "d xs mono" }, x.url), el("div", { class: "d small" }, x.snippet)),
            el("a", { class: "btn sm ghost", href: x.url, target: "_blank", rel: "noopener noreferrer" }, "Ouvrir")))));
      }
    } catch (e) { out.replaceChildren(errorBox(e)); }
  };
  const audit = async (url) => {
    out.replaceChildren(loading("Audit en cours…"));
    try {
      const r = (await tool("site_auditer", { url })).result;
      out.replaceChildren(el("div", { class: "panel" }, el("div", { class: "metrics" }, el("div", { class: "metric" }, el("div", { class: "v" }, `${r.score}/100`), el("div", { class: "l" }, "score des contrôles"))),
        el("table", { class: "table" }, el("tbody", {}, ...r.findings.map((f) => el("tr", {}, el("td", {}, status(f.ok ? "confirme" : "echoue")), el("td", {}, f.label), el("td", { class: "small muted" }, f.detail))))),
        el("p", { class: "small faint" }, r.note)));
    } catch (e) { out.replaceChildren(errorBox(e)); }
  };
  const links = async (url) => {
    out.replaceChildren(loading("Vérification des liens…"));
    try {
      const r = (await tool("web_verifier_liens", { url, max: 60 })).result;
      out.replaceChildren(el("p", {}, `${r.checked} lien(s) vérifié(s), ${r.broken.length} en erreur.`),
        el("table", { class: "table" }, el("tbody", {}, ...r.results.map((x) => el("tr", {}, el("td", {}, status(x.ok ? "confirme" : "echoue")), el("td", { class: "mono" }, x.url), el("td", {}, x.status ?? x.error))))));
    } catch (e) { out.replaceChildren(errorBox(e)); }
  };
  q.addEventListener("keydown", (e) => { if (e.key === "Enter") go(); });
  const rendered = el("input", { type: "checkbox" });
  const sources = el("div");
  view.append(el("div", { class: "page" }, el("div", { class: "toolbar" }, q, btn("Aller", go, { cls: "primary" }), el("label", { class: "switch small" }, rendered, "Rendu JavaScript (navigateur piloté)")),
    el("p", { class: "small faint" }, "Pages publiques uniquement. Les adresses locales sont refusées ; aucun CAPTCHA ni connexion n'est contourné. Le contenu des pages est traité comme une donnée non fiable."),
    out, el("h3", {}, "Sources récemment consultées"), sources));
  try {
    const s = await get("/api/sources");
    sources.replaceChildren(s.length ? el("div", { class: "list" }, ...s.slice(0, 25).map((x) => el("div", { class: "row" }, el("span", { class: "badge plain" }, x.origin || ""),
      el("div", { class: "main-col" }, el("a", { class: "t small", href: x.url, target: "_blank", rel: "noopener noreferrer" }, x.title || x.url), el("div", { class: "d xs" }, `${x.confidence} – ${when(x.fetched_at)}`)), el("span", {}))))
      : el("p", { class: "faint small" }, "Aucune source consultée."));
  } catch (e) { sources.replaceChildren(errorBox(e)); }
  q.focus();
}
