// Paramètres : apparence, animations, détail des réponses, voix, démarrage, raccourcis, confirmations, autonomie,
// rétention, budget ; versions de configuration restaurables. Les réglages sensibles demandent une confirmation.
import { get, patch, post } from "../api.js";
import { btn, el, errorBox, field, handleError, input, loading, modal, select, toast, toggle, when } from "../ui.js";

export async function render(view, params, app) {
  const page = el("div", { class: "page narrow" }, loading());
  view.append(page);
  async function load() {
    let d, v, svc;
    try { [d, v, svc] = await Promise.all([get("/api/settings"), get("/api/voice"), get("/api/service")]); } catch (e) { return page.replaceChildren(errorBox(e)); }
    const s = d.settings;
    const save = async (p, quiet) => { try { await patch("/api/settings", p); if (!quiet) toast("Réglage enregistré."); app.emit({ type: "settings" }); } catch (e) { handleError(e); setTimeout(load, 800); } };
    const saveScripts = async (scripts) => { try { await patch("/api/settings", { scripts_approuves: scripts }); load(); } catch (e) { handleError(e); setTimeout(load, 1200); } };
    const sel = (opts, val, onch) => { const x = select(opts, val); x.addEventListener("change", () => onch(x.value)); return x; };
    const num = (val, onch, attrs = {}) => { const x = input({ type: "number", value: val, ...attrs }); x.addEventListener("change", () => onch(Number(x.value))); return x; };
    const range = (val, min, max, step, onch) => { const x = input({ type: "range", min, max, step, value: val }); x.addEventListener("change", () => onch(Number(x.value))); return x; };
    const sec = (title, ...children) => el("section", { class: "panel" }, el("h3", { style: { marginTop: 0 } }, title), el("div", { class: "form" }, ...children));
    page.replaceChildren(
      sec("Apparence",
        el("div", { class: "form-row" },
          field("Thème", sel([["obsidian-emerald", "Obsidian Emerald"]], s.appearance.theme, (x) => save({ appearance: { theme: x } }))),
          field("Animations", sel([["normales", "Normales"], ["reduites", "Réduites"], ["aucune", "Aucune"]], s.appearance.animations, (x) => { save({ appearance: { animations: x } }); document.documentElement.dataset.motion = x; })))),
      sec("Réponses",
        field("Niveau de détail", sel([["court", "Court"], ["normal", "Normal"], ["detaille", "Détaillé"]], s.assistant.detail_level, (x) => save({ assistant: { detail_level: x } })))),
      sec("Voix",
        el("div", { class: "form-row" },
          field("Voix", sel(v.voices.map((x) => [x.name, `${x.name} (${x.locale})`]), s.voice.voice, (x) => save({ voice: { voice: x } }))),
          field("Sortie audio", sel([["defaut", "Sortie par défaut"], ...v.devices.map((x) => [x, x])], s.voice.output_device || "defaut", (x) => save({ voice: { output_device: x } })))),
        field(`Volume`, range(s.voice.volume, 0, 1, 0.05, (x) => save({ voice: { volume: x } }))),
        field(`Vitesse de parole (mots par minute)`, range(s.voice.rate, 120, 300, 10, (x) => save({ voice: { rate: x } }))),
        toggle("Lire les réponses à voix haute", s.voice.auto_speak, (x) => save({ voice: { auto_speak: x } })),
        btn("Tester la voix", () => post("/api/voice/speak", { text: "Bonjour Sacha, je suis JARVIS. Tout est en ordre." }), { cls: "sm", icon: "speaker" }),
        el("p", { class: "small faint" }, "Mot d'activation : non disponible dans cette version (aucune écoute permanente).")),
      sec("Service et démarrage",
        el("dl", { class: "kv" }, el("dt", {}, "Service"), el("dd", {}, `actif depuis ${Math.round(svc.uptime_s / 60)} min, lancé par ${svc.launched_by} (processus ${svc.pid})`),
          el("dt", {}, "Fenêtres connectées"), el("dd", {}, String(svc.windows_connected)),
          el("dt", {}, "Données"), el("dd", { class: "mono" }, svc.data_dir), el("dt", {}, "Espace de travail"), el("dd", { class: "mono" }, svc.workspace_dir)),
        toggle("Démarrer le service JARVIS automatiquement à l'ouverture de session (garde rappels et automatisations actifs, même application quittée)",
          svc.autostart, async (x, i) => {
            try { await post("/api/service/autostart", { enabled: x }); toast(x ? "Démarrage automatique activé." : "Démarrage automatique désactivé."); load(); }
            catch (e) { i.checked = svc.autostart; handleError(e); setTimeout(load, 1200); }
          }),
        el("dl", { class: "kv" }, ...Object.entries({ "Fenêtre fermée": svc.states.fenetre_fermee, "Application quittée": svc.states.application_quittee,
          "Service arrêté": svc.states.service_arrete, "Mac en veille": svc.states.veille, "Mac éteint": svc.states.eteint })
          .flatMap(([k, v]) => [el("dt", {}, k), el("dd", { class: "small muted" }, v)]))),
      sec("Raccourcis",
        el("dl", { class: "kv" }, ...Object.entries({ "Écrire": "/", "Parler": "Alt + Espace", "Interrompre": "Échap", "Rechercher partout": "⌘ + K" }).flatMap(([k, x]) => [el("dt", {}, k), el("dd", { class: "mono" }, x)])),
        el("p", { class: "small faint" }, "Dans l'application : ⌘, ouvre les paramètres, ⇧⌘D le diagnostic, ⌘R recharge l'interface.")),
      sec("Autonomie et confirmations",
        el("div", { class: "form-row" },
          field("Tours maximum par tâche", num(s.autonomy.max_steps, (x) => save({ autonomy: { max_steps: x } }), { min: 1, max: 50 })),
          field("Durée maximum (s)", num(s.autonomy.max_task_seconds, (x) => save({ autonomy: { max_task_seconds: x } }), { min: 10, max: 7200 })),
          field("Nouvelles tentatives", num(s.autonomy.max_retries, (x) => save({ autonomy: { max_retries: x } }), { min: 0, max: 5 }))),
        toggle("Demander aussi confirmation pour les actions à risque modéré", s.confirmations.moderate_needs_confirmation, (x) => save({ confirmations: { moderate_needs_confirmation: x } })),
        el("p", { class: "small faint" }, "Le mode, les dossiers et les commandes autorisés se règlent dans Sécurité.")),
      sec("Budget et limites",
        el("div", { class: "form-row" },
          field("Appels IA maximum par jour", num(s.budget.max_calls_per_day, (x) => save({ budget: { max_calls_per_day: x } }), { min: 0 })),
          field("Budget quotidien ($)", num(s.budget.daily_usd, (x) => save({ budget: { daily_usd: x } }), { min: 0, step: 0.5 })),
          field("Budget mensuel ($)", num(s.budget.monthly_usd, (x) => save({ budget: { monthly_usd: x } }), { min: 0, step: 1 }))),
        toggle("Arrêt automatique en cas de dépassement", s.budget.stop_on_exceed, (x) => save({ budget: { stop_on_exceed: x } }))),
      sec("Scripts approuvés",
        el("p", { class: "small muted" }, "Scripts que JARVIS peut lancer à votre demande (outil « script_executer »), toujours via les contrôles du terminal (commande autorisée, dossier autorisé, délai). Ajouter ou retirer un script demande votre confirmation."),
        Object.keys(s.scripts_approuves || {}).length ? el("div", { class: "list" }, ...Object.entries(s.scripts_approuves).map(([n, d]) => el("div", { class: "row" },
          el("span", { class: "mono" }, n), el("div", { class: "main-col small" }, el("span", { class: "mono" }, d.command), d.description ? el("div", { class: "d xs" }, d.description) : null),
          btn("Retirer", async () => { const c = { ...s.scripts_approuves }; delete c[n]; await saveScripts(c); }, { cls: "sm ghost" }))))
          : el("p", { class: "faint small" }, "Aucun script approuvé."),
        btn("Ajouter un script", () => {
          const n = input({ placeholder: "nom-court" }), c = input({ placeholder: "python3 /Users/…/JARVIS/scripts/sauvegarde.py" }), w = input({ placeholder: "dossier de travail (facultatif)" }), d = input({ placeholder: "ce que fait le script" });
          modal("Approuver un script", el("div", { class: "form" }, field("Nom", n), field("Commande", c), field("Dossier", w), field("Description", d)),
            ["close", (close) => btn("Demander l'approbation", async () => { close(); await saveScripts({ ...(s.scripts_approuves || {}), [n.value.trim()]: { command: c.value.trim(), cwd: w.value.trim() || undefined, description: d.value.trim() } }); }, { cls: "primary" })]);
        }, { cls: "sm", icon: "plus" })),
      sec("Journal",
        field("Conserver les événements (jours)", num(s.retention.events_days, (x) => save({ retention: { events_days: x } }), { min: 7, max: 3650 }))),
      sec("Versions de la configuration",
        el("div", { class: "list" }, ...d.versions.slice(0, 12).map((x) => el("div", { class: "row" }, el("span", { class: "faint xs" }, when(x.created_at)), el("div", { class: "main-col small" }, x.reason || ""),
          btn("Restaurer", async () => { try { await post(`/api/settings/restore/${x.id}`); } catch (e) { handleError(e); } }, { cls: "sm ghost" })))))
    );
  }
  await load();
}
