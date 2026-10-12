// Applications connectées : état réel, capacités, permissions, limites, connexion/déconnexion, test, applications du Mac.
import { get, post } from "../api.js";
import { btn, el, errorBox, handleError, loading, modal, toast, toggle } from "../ui.js";

export async function render(view, params, app) {
  const page = el("div", { class: "page" }, loading());
  view.append(page);
  async function load() {
    let cs, apps, plugins;
    try { [cs, apps, plugins] = await Promise.all([get("/api/connectors"), get("/api/apps"), get("/api/plugins")]); } catch (e) { return page.replaceChildren(errorBox(e)); }
    page.replaceChildren(
      el("p", { class: "lead" }, "Chaque connecteur est testé réellement : « connecté » n'est affiché qu'après vérification. Aucun service inconnu n'est connecté automatiquement."),
      el("table", { class: "table" }, el("thead", {}, el("tr", {}, ...["Service", "État", "Capacités", "Permissions et limites", ""].map((h) => el("th", {}, h)))),
        el("tbody", {}, ...cs.map((c) => el("tr", {},
          el("td", {}, el("b", { style: { fontWeight: 500 } }, c.label), el("div", { class: "faint xs" }, c.kind)),
          el("td", {}, el("span", { class: "badge " + (c.connected ? "ok" : "plain") }, c.connected ? "connecté" : "non connecté"), el("div", { class: "faint xs" }, c.state)),
          el("td", { class: "small" }, c.capabilities.join(", ")),
          el("td", { class: "small muted" }, c.permissions, el("div", { class: "xs faint" }, c.limits)),
          el("td", {}, el("div", { style: { display: "flex", gap: "4px", justifyContent: "flex-end", flexWrap: "wrap" } },
            "enabled" in c ? toggle("Activé", c.enabled, async (on, i) => {
              try { await post(`/api/connectors/${c.id}/enable`, { enabled: on }); toast("Connecteur désactivé."); load(); }
              catch (e) { i.checked = !on; handleError(e); setTimeout(load, 800); }
            }) : null,
            btn("Tester", async () => { const r = await post(`/api/connectors/${c.id}/test`); toast(`${c.label} : ${r.ok ? "OK" : "échec"} — ${r.detail}${r.ms ? ` (${r.ms} ms)` : ""}`, r.ok ? "" : "err"); }, { cls: "sm ghost" }),
            btn("Procédure", () => modal(c.label, el("dl", { class: "kv" }, el("dt", {}, "Connexion"), el("dd", {}, c.connect), el("dt", {}, "Déconnexion"), el("dd", {}, c.disconnect)), ["close"]), { cls: "sm ghost" }))))))),
      el("h3", {}, "Plugins"),
      plugins.length ? el("div", { class: "list" }, ...plugins.map((p) => el("div", { class: "row" }, el("span", { class: "badge " + (p.loaded ? "ok" : "plain") }, p.enabled ? (p.loaded ? "chargé" : "erreur") : "désactivé"), el("div", { class: "main-col small" }, `${p.name} ${p.version} — outils : ${p.tools.join(", ")}`, p.error ? el("div", { class: "xs", style: { color: "var(--err)" } }, p.error) : null), el("span", {}))))
        : el("p", { class: "small faint" }, "Aucun plugin installé. Un plugin (dossier plugins/<nom>) déclare ses outils et son risque maximal ; il est désactivé par défaut et n'obtient aucun droit implicite."),
      el("h3", {}, `Applications du Mac (${apps.length})`),
      el("p", { class: "small muted" }, "JARVIS peut ouvrir une application installée (outil application_ouvrir, vérification par détection du processus). Le contrôle de l'interface d'autres applications (accessibilité, AppleScript) n'est pas activé : aucune autorisation d'accessibilité n'a été accordée."),
      el("div", { class: "shortcuts", style: { justifyContent: "flex-start" } }, ...apps.slice(0, 60).map((a) => el("button", { type: "button", onclick: async () => {
        try { const r = await post("/api/tools/application_ouvrir/invoke", { args: { name: a } }); toast(`${a} : ${r.verification}`); } catch (e) { handleError(e); }
      } }, a))));
  }
  await load();
}
