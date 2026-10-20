// Centre de notifications : liste, lecture, réglages (types, heures silencieuses, contenu masqué).
import { get, patch, post } from "../api.js";
import { btn, el, empty, errorBox, field, handleError, input, toast, toggle, when } from "../ui.js";

const KINDS = { tache_terminee: "Tâche terminée", erreur: "Erreur importante", confirmation: "Confirmation nécessaire", projet_bloque: "Projet bloqué",
  automatisation_echec: "Automatisation en échec", integration: "Intégration déconnectée", limite: "Limite atteinte", rappel: "Rappel" };

export async function render(view, params, app) {
  const list = el("div"), prefs = el("div");
  view.append(el("div", { class: "page" }, el("div", { class: "grid-2" },
    el("div", {}, el("div", { class: "toolbar" }, el("h3", { style: { margin: 0 } }, "Notifications"), el("span", { class: "grow" }),
      btn("Tout marquer comme lu", async () => { await post("/api/notifications/read", {}); load(); }, { cls: "sm ghost", icon: "check" })), list),
    el("div", {}, el("h3", { style: { marginTop: 0 } }, "Réglages"), prefs))));
  async function load() {
    let ns; try { ns = await get("/api/notifications"); } catch (e) { return list.replaceChildren(errorBox(e)); }
    list.replaceChildren(ns.length ? el("div", { class: "list" }, ...ns.map((n) => el("div", { class: "row", style: { opacity: n.read ? 0.6 : 1 } },
      el("span", { class: "badge " + (n.priority === "haute" ? "wait" : "plain") }, KINDS[n.kind] || n.kind),
      el("div", { class: "main-col" }, el("div", { class: "t small" }, n.title), n.body ? el("div", { class: "d xs" }, n.body) : null),
      el("span", { class: "faint xs" }, when(n.ts), n.delivered_macos ? " – macOS" : "")))) : empty("Aucune notification.", "Les fins de tâches, erreurs et demandes d'accord apparaîtront ici."));
  }
  async function loadPrefs() {
    const s = (await get("/api/settings")).settings.notifications;
    const save = async (p) => { try { await patch("/api/settings", { notifications: p }); toast("Réglage enregistré."); } catch (e) { handleError(e); } };
    const start = input({ value: s.quiet_hours.start }), end = input({ value: s.quiet_hours.end });
    prefs.replaceChildren(el("div", { class: "form" },
      toggle("Notifications activées", s.enabled, (v) => save({ enabled: v })),
      toggle("Notifications macOS (en plus du centre Nova)", s.macos, (v) => save({ macos: v })),
      toggle("Masquer le contenu (écran verrouillé)", s.hide_content, (v) => save({ hide_content: v })),
      toggle("Heures silencieuses", s.quiet_hours.enabled, (v) => save({ quiet_hours: { enabled: v } })),
      el("div", { class: "form-row" }, field("Début", start), field("Fin", end)),
      btn("Enregistrer les horaires", () => save({ quiet_hours: { start: start.value, end: end.value } }), { cls: "sm" }),
      el("h3", {}, "Types d'événements"),
      ...Object.entries(KINDS).map(([k, l]) => toggle(l, s.kinds.includes(k), async (v) => {
        const cur = (await get("/api/settings")).settings.notifications.kinds;
        save({ kinds: v ? [...new Set([...cur, k])] : cur.filter((x) => x !== k) });
      })),
      el("p", { class: "small faint" }, "Si aucune notification macOS n'apparaît : Réglages Système > Notifications > Éditeur de script, autoriser.")));
  }
  await Promise.all([load(), loadPrefs()]);
  await post("/api/notifications/read", {}).catch(() => {});
}
