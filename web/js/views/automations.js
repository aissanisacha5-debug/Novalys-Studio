// Automatisations : déclencheur, conditions, action, délai, tentatives, historique ; observables et désactivables.
import { del, get, post } from "../api.js";
import { btn, el, errorBox, field, input, loading, modal, select, status, textarea, toast, toggle, when } from "../ui.js";

export async function render(view, params, app) {
  const page = el("div", { class: "page" }, loading());
  view.append(page);
  async function load() {
    let d; try { d = await get("/api/automations"); } catch (e) { return page.replaceChildren(errorBox(e)); }
    const trig = (t) => ({ intervalle: `toutes les ${t.minutes} min`, quotidien: `chaque jour à ${t.heure}${t.jours && t.jours.length < 7 ? " (jours " + t.jours.join(",") + ")" : ""}`,
      date: `le ${t.quand}`, dossier: `fichier ajouté dans ${t.path}`, evenement: `événement ${t.kind}`, manuel: "manuel" }[t.type] || t.type);
    page.replaceChildren(
      el("div", { class: "toolbar" }, el("p", { class: "muted", style: { margin: 0 } }, "Les automatisations tournent tant que JARVIS est ouvert. Elles respectent les permissions et ne contournent aucune confirmation."),
        el("span", { class: "grow" }), btn("Nouvelle automatisation", () => create(d, load), { cls: "primary", icon: "plus" })),
      el("table", { class: "table" }, el("thead", {}, el("tr", {}, ...["Active", "Nom", "Déclencheur", "Action", "Dernière exécution", "Prochaine", ""].map((h) => el("th", {}, h)))),
        el("tbody", {}, ...d.items.map((a) => el("tr", {},
          el("td", {}, toggle(el("span", { class: "sr-only" }, "active"), a.enabled, async (on) => { await post(`/api/automations/${a.id}/${on ? "enable" : "disable"}`); toast(on ? "Automatisation activée." : "Automatisation désactivée."); load(); })),
          el("td", {}, a.name, a.fail_streak ? el("div", { class: "xs", style: { color: "var(--err)" } }, `${a.fail_streak} échec(s) consécutif(s)`) : null),
          el("td", { class: "small" }, trig(a.trigger)), el("td", { class: "small" }, d.actions[a.action.type] || a.action.type, a.action.objectif ? el("div", { class: "faint xs" }, a.action.objectif.slice(0, 80)) : null),
          el("td", { class: "small" }, a.runs[0] ? [status(a.runs[0].status), " ", when(a.runs[0].started_at)] : el("span", { class: "faint" }, "jamais")),
          el("td", { class: "small faint" }, a.enabled ? (a.next_run || "").replace("T", " ").slice(0, 16) : "—"),
          el("td", {}, el("div", { style: { display: "flex", gap: "4px" } }, btn("Lancer", async () => { await post(`/api/automations/${a.id}/run`); toast("Exécution lancée."); setTimeout(load, 1500); }, { cls: "sm ghost", icon: "play" }),
            btn("Historique", () => modal(`Historique — ${a.name}`, a.runs.length ? el("table", { class: "table" }, el("tbody", {}, ...a.runs.map((r) => el("tr", {}, el("td", {}, status(r.status)), el("td", { class: "small" }, when(r.started_at)), el("td", { class: "small mono" }, (r.error || r.output || "").slice(0, 300)))))) : el("p", {}, "Aucune exécution."), ["close"], true), { cls: "sm ghost" }),
            btn("Supprimer", async () => { await del(`/api/automations/${a.id}`); load(); }, { cls: "sm ghost", icon: "trash" }))))))));
  }
  await load();
}

function create(d, reload) {
  const name = input({ placeholder: "Ex. Relances du lundi" });
  const ttype = select(Object.entries(d.triggers), "quotidien");
  const heure = input({ value: "09:00" }), minutes = input({ type: "number", value: "60", min: 5 }), quand = input({ type: "datetime-local" });
  const path = input({ placeholder: "Dossier autorisé" }), kind = select(["tache_fin", "outil_erreur", "autorisation_demandee"], "tache_fin");
  const atype = select(Object.entries(d.actions), "bilan_quotidien");
  const obj = textarea({ placeholder: "Objectif confié à l'agent" }), dir = input({ placeholder: "Dossier du projet" }), url = input({ placeholder: "https://…" });
  const weekdays = el("input", { type: "checkbox" });
  const tfields = el("div"), afields = el("div");
  const drawT = () => tfields.replaceChildren(...({ quotidien: [field("Heure (HH:MM)", heure), el("label", { class: "switch" }, weekdays, "Jours ouvrés seulement")], intervalle: [field("Minutes (5 minimum)", minutes)],
    date: [field("Date et heure", quand)], dossier: [field("Dossier", path)], evenement: [field("Événement", kind)], manuel: [] }[ttype.value] || []));
  const drawA = () => afields.replaceChildren(...({ agent: [field("Objectif", obj)], tests_projet: [field("Dossier du projet", dir)], liens_site: [field("Adresse du site", url)] }[atype.value] || []));
  ttype.addEventListener("change", drawT); atype.addEventListener("change", drawA); drawT(); drawA();
  modal("Nouvelle automatisation", el("div", { class: "form" }, field("Nom", name), el("div", { class: "form-row" }, field("Déclencheur", ttype), field("Action", atype)), tfields, afields,
    el("p", { class: "small faint" }, "Créée désactivée : activez-la après l'avoir lancée une fois à la main.")),
    ["close", (close) => btn("Créer", async () => {
      const trigger = { type: ttype.value };
      if (ttype.value === "quotidien") { trigger.heure = heure.value; if (weekdays.checked) trigger.jours = [1, 2, 3, 4, 5]; }
      if (ttype.value === "intervalle") trigger.minutes = Number(minutes.value);
      if (ttype.value === "date") trigger.quand = quand.value;
      if (ttype.value === "dossier") trigger.path = path.value;
      if (ttype.value === "evenement") trigger.kind = kind.value;
      const action = { type: atype.value, objectif: obj.value || undefined, dir: dir.value || undefined, url: url.value || undefined };
      await post("/api/automations", { name: name.value || "Automatisation", trigger, action });
      close(); reload();
    }, { cls: "primary" })]);
}
