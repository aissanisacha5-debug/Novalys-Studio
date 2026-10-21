// Autorisations et autonomie : tout le contrôle au même endroit (voix, niveau d'autonomie, dossiers, autorisations
// préalables, outils, historique des actions, arrêt immédiat). Restreindre s'applique tout de suite ; élargir demande un accord.
import { get, patch, post } from "../api.js";
import { btn, el, errorBox, field, handleError, input, loading, modal, select, toast, toggle, when } from "../ui.js";

const NATIVE_APP = !!(window.webkit && window.webkit.messageHandlers && window.webkit.messageHandlers.jarvisApp);

function pickFolder() {
  return new Promise((resolve) => {
    window.jarvisNativePicked = (path) => resolve(path || null);
    window.webkit.messageHandlers.jarvisApp.postMessage({ cmd: "pickFolder" });
  });
}

export async function render(view, params, app) {
  const page = el("div", { class: "page" }, loading());
  view.append(page);
  async function load() {
    let d, lat;
    try { [d, lat] = await Promise.all([get("/api/permissions"), get("/api/latency?limit=8")]); } catch (e) { return page.replaceChildren(errorBox(e)); }
    const v = d.voice;
    const saveVoice = async (p, msg) => { try { await patch("/api/settings", { voice: p }); if (msg) toast(msg); app.voice.applySettings((await get("/api/voice")).settings); } catch (e) { handleError(e); } };
    const level = select(Object.entries(d.levels).map(([k, txt]) => [k, txt.split(" :")[0]]), d.level);
    level.addEventListener("change", async () => { try { await patch("/api/settings", { autonomy: { level: level.value } }); } catch (e) { handleError(e); } setTimeout(load, 1200); });
    const silence = el("input", { type: "range", min: 500, max: 2000, step: 100, value: v.end_silence_ms || 900, class: "input", "aria-label": "Silence de fin de phrase" });
    const silenceLabel = el("span", { class: "small muted" }, `${v.end_silence_ms || 900} ms`);
    silence.addEventListener("input", () => { silenceLabel.textContent = `${silence.value} ms`; });
    silence.addEventListener("change", () => saveVoice({ end_silence_ms: Number(silence.value) }, "Délai de fin de phrase enregistré."));

    const addDir = async (mode) => {
      let path = null;
      if (NATIVE_APP) path = await pickFolder();
      else {
        const i = input({ placeholder: "/Users/…/Dossier" });
        path = await new Promise((res) => modal("Ajouter un dossier", field("Chemin absolu", i), [(c) => btn("Annuler", () => { c(); res(null); }, { cls: "ghost" }), (c) => btn("Ajouter", () => { c(); res(i.value.trim()); }, { cls: "primary" })]));
      }
      if (!path) return;
      const dirs = (d.dirs || []).filter((x) => x.path !== path);
      try { await patch("/api/settings", { allowed_dirs: [...dirs, { path, mode, label: path.split("/").pop() }] }); } catch (e) { handleError(e); }
      setTimeout(load, 1200);
    };
    const revokeDir = async (path, downgrade) => { await post("/api/permissions/revoke", { type: "dir", path, downgrade }); toast(downgrade ? "Passé en lecture seule." : "Accès au dossier retiré."); load(); };
    const sec = (title, ...children) => el("section", { class: "panel", style: { marginBottom: "16px" } }, el("h3", { style: { marginTop: 0 } }, title), ...children);

    page.replaceChildren(
      el("div", { class: "toolbar" }, el("p", { class: "lead", style: { margin: 0 } }, "Ce que Nova peut faire seul, et ce qui demande votre accord. Retirer un droit s'applique immédiatement ; en ajouter un demande une confirmation."),
        el("span", { class: "grow" }),
        btn("Tout arrêter maintenant", async () => { const r = await post("/api/stop-all", {}); app.voice.stopListening(); toast(`Arrêt : ${r.cancelled.length} tâche(s) annulée(s), voix et navigateur piloté coupés.`); }, { cls: "danger", icon: "stop" })),
      sec("Voix",
        el("div", { class: "form" },
          toggle("Envoi automatique : la phrase est envoyée dès la fin de parole (la transcription reste affichée)", v.auto_send !== false, (x) => saveVoice({ auto_send: x }, x ? "Envoi automatique activé." : "Mode manuel : vous validez la transcription.")),
          toggle("Conversation continue : Nova réécoute après chaque réponse (« stop » pour finir)", !!v.hands_free, (x) => { saveVoice(x ? { hands_free: true, auto_speak: true } : { hands_free: false }, x ? "Conversation continue activée." : "Conversation continue désactivée."); if (x && !app.voice.listening) app.voice.startListening(); }),
          toggle("Interruption vocale : si vous parlez pendant sa réponse, Nova se tait et vous écoute", v.barge_in !== false, (x) => saveVoice({ barge_in: x })),
          field("Silence qui marque la fin d'une phrase (application Nova)", el("div", { style: { display: "flex", gap: "12px", alignItems: "center" } }, silence, silenceLabel)))),
      sec("Niveau d'autonomie",
        el("div", { class: "form-row" }, field("Niveau", level)),
        el("p", { class: "small muted" }, d.levels[d.level]),
        el("p", { class: "small faint" }, "Toujours soumis à votre accord, quel que soit le niveau : suppression de nombreux fichiers, envoi à des tiers, publication, achat, déploiement, réglages de sécurité, actions irréversibles, et toute action à risque élevé après la lecture d'un contenu qui contient des instructions suspectes.")),
      sec("Dossiers autorisés",
        el("table", { class: "table" }, el("tbody", {}, ...(d.dirs || []).map((x) => el("tr", {},
          el("td", { class: "mono" }, x.path), el("td", {}, el("span", { class: "badge " + (x.mode === "rw" ? "wait" : "plain") }, x.mode === "rw" ? "lecture et écriture" : "lecture seule")),
          el("td", {}, el("div", { style: { display: "flex", gap: "4px", justifyContent: "flex-end" } },
            x.mode === "rw" ? btn("Lecture seule", () => revokeDir(x.path, true), { cls: "sm ghost" }) : null,
            btn("Révoquer", () => revokeDir(x.path, false), { cls: "sm ghost", icon: "x" }))))))),
        el("div", { style: { display: "flex", gap: "8px", marginTop: "10px" } },
          btn("Autoriser un dossier en lecture", () => addDir("r"), { cls: "sm", icon: "plus" }),
          btn("Autoriser un dossier en écriture", () => addDir("rw"), { cls: "sm", icon: "plus" })),
        el("p", { class: "small faint" }, "Les autorisations sont conservées après redémarrage. Pour les dossiers protégés par macOS (Documents, Bureau, Téléchargements), macOS demande une seule fois l'accord pour Nova ; il le mémorise ensuite (Réglages Système > Confidentialité et sécurité > Fichiers et dossiers).")),
      sec("Autorisations « ne plus demander »",
        d.policies.length ? el("div", { class: "list" }, ...d.policies.map((p) => el("div", { class: "row" }, el("span", { class: "mono" }, p.tool),
          el("div", { class: "main-col small" }, el("span", { class: "mono" }, p.scope), el("div", { class: "d xs" }, `accordée ${when(p.created_at)}`)),
          btn("Révoquer", async () => { await post("/api/permissions/revoke", { type: "policy", id: p.id }); toast("Autorisation révoquée."); load(); }, { cls: "sm ghost", icon: "x" }))))
          : el("p", { class: "faint small" }, "Aucune. Elles se créent avec le bouton « Autoriser et ne plus demander ici » d'une demande d'accord, pour un dossier ou une commande précise."),
        el("p", { class: "small faint" }, `Possibles seulement pour : ${d.policy_tools.join(", ")} — jamais pour les envois, publications, achats ou réglages.`)),
      sec("Outils",
        el("table", { class: "table" }, el("tbody", {}, ...d.tools.map((t) => el("tr", {},
          el("td", {}, toggle(el("span", { class: "mono" }, t.id), t.enabled, async (x) => { await post("/api/permissions/tools", { tool: t.id, enabled: x }); toast(`${t.id} ${x ? "activé" : "désactivé"}.`); })),
          el("td", { class: "small muted" }, t.description),
          el("td", {}, el("span", { class: "badge " + ({ faible: "plain", modere: "wait", eleve: "err" }[t.risk] || "plain") }, t.risk)),
          el("td", { class: "small faint" }, t.available ? "" : t.unavailable_reason)))))),
      sec("Dernières actions",
        el("div", { class: "events" }, ...d.recent.map((e) => el("div", { class: "event " + e.level }, el("time", {}, (e.ts || "").slice(11, 16)),
          el("div", { class: "m" }, e.message, e.task_id ? el("a", { href: `#/taches/${e.task_id}`, class: "xs", style: { marginLeft: "6px" } }, `tâche #${e.task_id}`) : null)))),
        el("a", { href: "#/historique", class: "small" }, "Tout l'historique")),
      sec("Latence vocale mesurée",
        lat.length ? el("table", { class: "table" }, el("thead", {}, el("tr", {}, ...["Premier fragment", "Premier son", "Réponse complète", "Préchauffé", "Statut"].map((h) => el("th", {}, h)))),
          el("tbody", {}, ...lat.map((l) => el("tr", {}, el("td", {}, l.premier_fragment_ms != null ? `${l.premier_fragment_ms} ms` : "—"),
            el("td", {}, l.premier_son_ms != null ? `${l.premier_son_ms} ms` : "—"), el("td", {}, `${l.total_ms} ms`), el("td", {}, l.prechauffe ? "oui" : "non"), el("td", { class: "small" }, l.statut)))))
          : el("p", { class: "faint small" }, "Aucune mesure : parlez à Nova (ou activez la lecture des réponses) pour en obtenir."),
        el("p", { class: "small faint" }, "Mesuré à partir de la réception de la phrase par Nova (la durée de votre phrase et la reconnaissance vocale ne sont pas comprises).")));
  }
  await load();
}
