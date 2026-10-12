// Diagnostic : contrôles de santé réels, système (processeur, mémoire, disque), processus JARVIS, durées, sauvegardes, coûts.
import { get, post } from "../api.js";
import { btn, el, errorBox, loading, status, toast, when } from "../ui.js";

export async function render(view, params, app) {
  const page = el("div", { class: "page" }, loading("Diagnostic en cours…"));
  view.append(page);
  async function load() {
    let d, sys, backups, costs;
    try { [d, sys, backups, costs] = await Promise.all([get("/api/diagnostics"), get("/api/system"), get("/api/backups"), get("/api/costs")]); } catch (e) { return page.replaceChildren(errorBox(e)); }
    const meter = (pct) => el("div", { class: "meter " + (pct > 90 ? "err" : pct > 75 ? "warn" : "") }, el("i", { style: { width: pct + "%" } }));
    const m = (v, l, pct) => el("div", { class: "metric" }, el("div", { class: "v" }, v), el("div", { class: "l" }, l), pct != null ? meter(pct) : null);
    const kinds = Object.fromEntries((costs.month_by_kind || []).map((k) => [k.cost_kind, k]));
    page.replaceChildren(
      el("div", { class: "toolbar" }, el("h2", { class: "title", style: { margin: 0 } }, d.summary), el("span", { class: "grow" }), btn("Relancer", load, { icon: "refresh" }),
        btn("Arrêter JARVIS", async () => { await post("/api/shutdown"); document.body.replaceChildren(el("div", { class: "empty-state", style: { marginTop: "30vh" } }, el("b", {}, "JARVIS est arrêté proprement."), "Relancez-le avec l'application JARVIS.")); }, { cls: "danger" })),
      el("div", { class: "metrics" },
        sys.cpu ? m(`${sys.cpu.percent} %`, `charge processeur (${sys.cpu.cores} cœurs)`, sys.cpu.percent) : null,
        sys.memory ? m(`${sys.memory.used_gb} / ${sys.memory.total_gb} Go`, "mémoire utilisée", sys.memory.percent) : null,
        m(`${sys.disk.free_gb} Go`, `libres sur ${sys.disk.total_gb} Go`, sys.disk.percent),
        m(sys.tasks_running.length, "tâches JARVIS en cours")),
      el("table", { class: "table" }, el("tbody", {}, ...d.checks.map((c) => el("tr", {}, el("td", {}, el("span", { class: "badge " + (c.ok ? "ok" : c.niveau === "info" ? "plain" : c.niveau === "attention" ? "wait" : "err") }, c.ok ? "OK" : c.niveau === "info" ? "info" : c.niveau === "attention" ? "à voir" : "erreur")),
        el("td", {}, c.composant), el("td", { class: "small muted" }, c.detail))))),
      el("div", { class: "grid-2" },
        el("div", {}, el("h3", {}, "Consommation IA (mois)"),
          el("dl", { class: "kv" }, el("dt", {}, "Appels aujourd'hui"), el("dd", {}, costs.today.calls), el("dt", {}, "Appels ce mois"), el("dd", {}, costs.month.calls),
            el("dt", {}, "Jetons (entrée / sortie)"), el("dd", {}, `${costs.month.input_tokens} / ${costs.month.output_tokens}`),
            el("dt", {}, "Coût réel facturé"), el("dd", {}, kinds.reel ? `${kinds.reel.cost_usd} $` : "0 $ (aucun service payant connecté)"),
            el("dt", {}, "Inclus dans l'abonnement"), el("dd", {}, kinds.inclus_abonnement ? `${kinds.inclus_abonnement.calls} appels (équivalent API ≈ ${(kinds.inclus_abonnement.cost_usd || 0).toFixed(3)} $, non facturé)` : "0"),
            el("dt", {}, "Limite d'appels / jour"), el("dd", {}, costs.budget.max_calls_per_day), el("dt", {}, "Budget"), el("dd", {}, `${costs.budget.daily_usd} $/jour, ${costs.budget.monthly_usd} $/mois (0 = aucune dépense autorisée)`)),
          el("p", { class: "small faint" }, costs.note)),
        el("div", {}, el("h3", {}, "Sauvegardes"),
          el("div", { class: "toolbar" }, btn("Sauvegarder maintenant", async () => { const r = await post("/api/backups"); toast(`Sauvegarde vérifiée : ${r.verification.detail}`); load(); }, { cls: "primary" })),
          backups.length ? el("div", { class: "list" }, ...backups.slice(0, 8).map((b) => el("div", { class: "row" }, el("span", { class: "faint xs" }, b.created), el("div", { class: "main-col small mono" }, b.name),
            el("div", { class: "actions" }, btn("Vérifier", async () => { const r = await post("/api/backups/verify", { name: b.name }); toast(r.ok ? `Valide : ${r.detail}, ${JSON.stringify(r.counts)}` : `Invalide : ${r.detail}`, r.ok ? "" : "err"); }, { cls: "sm ghost" }),
              btn("Restaurer", async () => { await post("/api/backups/restore", { name: b.name }); }, { cls: "sm ghost" })))))
            : el("p", { class: "faint small" }, "Aucune sauvegarde."))),
      el("h3", {}, "Processus démarrés par JARVIS"),
      sys.processes.length ? el("table", { class: "table" }, el("tbody", {}, ...sys.processes.map((p) => el("tr", {}, el("td", { class: "mono" }, p.pid), el("td", {}, p.kind), el("td", { class: "small" }, p.command),
        el("td", { class: "small faint" }, p.port ? `http://127.0.0.1:${p.port}/` : ""), el("td", {}, p.stopped_at ? el("span", { class: "badge plain" }, "arrêté") : el("span", { class: "badge ok" }, "actif")),
        el("td", {}, p.stopped_at ? null : btn("Arrêter", async () => { await post("/api/tools/processus_arreter/invoke", { args: { process_id: p.id } }); load(); }, { cls: "sm ghost" }))))))
        : el("p", { class: "faint small" }, "Aucun processus."),
      el("h3", {}, "Durées des dernières tâches"),
      el("table", { class: "table" }, el("tbody", {}, ...sys.durations.map((t) => el("tr", {}, el("td", {}, el("a", { href: `#/taches/${t.id}` }, t.title)), el("td", {}, status(t.status)),
        el("td", { class: "small faint" }, t.started_at && t.finished_at ? `${Math.max(0, Math.round((new Date(t.finished_at.replace(/([+-]\d\d)(\d\d)$/, "$1:$2")) - new Date(t.started_at.replace(/([+-]\d\d)(\d\d)$/, "$1:$2"))) / 1000))} s` : ""))))));
  }
  await load();
}
