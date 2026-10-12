// E-mails : brouillons locaux (toujours disponibles) et Gmail via le connecteur (lecture + brouillons, jamais d'envoi).
import { get, post } from "../api.js";
import { btn, el, errorBox, field, input, loading, md, modal, status, textarea, toast } from "../ui.js";
import { quickAsk } from "../app.js";

const tool = (id, args) => post(`/api/tools/${id}/invoke`, { args });

export async function render(view, params, app) {
  const tools = await get("/api/tools");
  const gm = tools.find((t) => t.id === "gmail_rechercher");
  const q = input({ value: "in:inbox newer_than:3d", "aria-label": "Requête Gmail" });
  const out = el("div");
  const drafts = el("div");
  view.append(el("div", { class: "page" },
    el("p", { class: "lead" }, "JARVIS prépare, vous envoyez. Aucun envoi, transfert, réponse automatique ni suppression n'est possible depuis JARVIS : l'envoi n'est pas activé."),
    el("div", { class: "grid-2" },
      el("div", {}, el("h3", { style: { marginTop: 0 } }, "Gmail"),
        gm.available ? el("div", {}, el("div", { class: "toolbar" }, q, btn("Rechercher", search, { cls: "primary" })), out)
          : el("div", { class: "unavailable" }, el("b", {}, "Gmail n'est pas activé dans JARVIS. "), gm.unavailable_reason, ". ", el("a", { href: "#/applications" }, "Ouvrir Applications connectées"))),
      el("div", {}, el("h3", { style: { marginTop: 0 } }, "Préparer un brouillon"),
        btn("Nouveau brouillon", () => compose(gm.available), { cls: "primary", icon: "plus" }), " ",
        btn("Trier ma boîte avec JARVIS", () => quickAsk("Recherche mes e-mails des 3 derniers jours, résume-les, identifie les actions à faire et les échéances, et propose des réponses en brouillon (sans rien envoyer)."), { cls: "ghost" }),
        el("h3", {}, "Brouillons locaux"), drafts))));
  async function search() {
    out.replaceChildren(loading("Lecture de Gmail…"));
    try {
      const r = await tool("gmail_rechercher", { query: q.value, max: 15 });
      out.replaceChildren(el("div", { class: "state-line" }, status(r.state), r.verification),
        el("div", { class: "list" }, ...r.result.threads.map((t) => el("div", { class: "row click", onclick: () => read(t) }, el("span", { class: "faint xs" }, (t.date || "").slice(0, 16)),
          el("div", { class: "main-col" }, el("div", { class: "t small" }, t.subject || "(sans objet)"), el("div", { class: "d xs" }, `${t.from || ""} – ${t.snippet || ""}`)), el("span", {})))));
    } catch (e) { out.replaceChildren(errorBox(e)); }
  }
  async function read(t) {
    const body = el("div", {}, loading());
    modal(t.subject || "Message", body, ["close", (c) => btn("Préparer une réponse avec JARVIS", () => { c(); quickAsk(`Lis le fil Gmail ${t.id} (sujet « ${t.subject} ») et prépare un brouillon de réponse dans Gmail, sans l'envoyer.`); }, { cls: "primary" })], true);
    try {
      const r = await tool("gmail_lire", { thread_id: t.id });
      body.replaceChildren(el("div", { class: "state-line" }, status(r.state), r.verification),
        ...(r.result.thread?.messages || []).map((m) => el("div", { class: "panel" }, el("div", { class: "small muted" }, `${m.from} – ${m.date}`), el("pre", { class: "out" }, m.body))));
    } catch (e) { body.replaceChildren(errorBox(e)); }
  }
  function compose(gmailOk) {
    const to = input({ placeholder: "adresse@exemple.fr" }), subject = input(), text = textarea({ style: { minHeight: "200px" } });
    modal("Nouveau brouillon", el("div", { class: "form" }, field("À", to), field("Objet", subject), field("Message", text),
      el("p", { class: "small faint" }, "Vérification automatique : adresse valide et absente de la liste d'opposition CYPHER.")),
      ["close",
        (c) => btn("Brouillon local", async () => { const r = await tool("email_brouillon_preparer", { to: [to.value.trim()], subject: subject.value, body: text.value }); toast("Brouillon local enregistré (non envoyé)."); c(); loadDrafts(); }, {}),
        (c) => gmailOk ? btn("Brouillon dans Gmail", async () => { const r = await tool("gmail_brouillon_creer", { to: [to.value.trim()], subject: subject.value, body: text.value }); toast(r.state === "confirme" ? "Brouillon créé dans Gmail (non envoyé)." : `Résultat ${r.state} : ${r.verification}`, r.state === "confirme" ? "" : "wait"); c(); }, { cls: "primary" }) : el("span")]);
  }
  async function loadDrafts() {
    try {
      const r = await tool("dossier_lister", { path: "brouillons" });
      drafts.replaceChildren(r.result.items.length ? el("div", { class: "list" }, ...r.result.items.map((f) => el("div", { class: "row click", onclick: async () => { const x = await tool("fichier_lire", { path: `${r.result.path}/${f.name}` }); modal(f.name, el("pre", { class: "out" }, x.result.content), ["close"], true); } },
        el("span", { class: "badge plain" }, "non envoyé"), el("div", { class: "main-col small" }, f.name), el("span", { class: "faint xs" }, f.modified)))) : el("p", { class: "faint small" }, "Aucun brouillon."));
    } catch { drafts.replaceChildren(el("p", { class: "faint small" }, "Aucun brouillon.")); }
  }
  await loadDrafts();
}
