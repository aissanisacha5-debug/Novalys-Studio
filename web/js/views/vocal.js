// Mode vocal : noyau, micro (coupé par défaut), transcription CORRIGEABLE avant envoi, réponse lue à voix haute,
// arrêt immédiat, mains libres et mot d'activation (sur l'appareil), réglages de voix et confidentialité.
import { get, patch, post } from "../api.js";
import { btn, el, field, handleError, md, select, textarea, toast, toggle } from "../ui.js";
import { Core } from "../core.js";

export async function render(view, params, app) {
  const [v, svcState] = await Promise.all([get("/api/voice"), get("/api/state")]);
  const s = v.settings;
  const canvas = el("canvas", { "aria-hidden": "true" });
  const live = el("div", { class: "lead", style: { minHeight: "1.6em", textAlign: "center", margin: "8px auto" }, "aria-live": "polite" });
  const draft = textarea({ placeholder: "La transcription apparaît ici : corrigez-la si besoin, puis envoyez.", style: { minHeight: "70px" }, "aria-label": "Transcription" });
  const answer = el("div", { class: "panel", style: { display: "none", maxWidth: "720px", margin: "0 auto", textAlign: "left" } });
  const mic = el("button", { class: "btn primary mic", type: "button", "data-mic": "", style: { height: "44px", padding: "0 22px" }, "aria-pressed": "false" }, "Parler");
  mic.addEventListener("click", () => app.voice.toggle());
  let convId = app.currentConv;

  const sendDraft = async () => {
    const text = draft.value.trim(); if (!text) return;
    try {
      app.voice.awaitingReply = true;
      const r = await post("/api/chat", { text, conversation_id: convId, source: "voix", client_ts: Date.now() });
      convId = r.conversation_id; app.currentConv = convId; app.voice.lastTaskId = r.task_id; draft.value = "";
      live.textContent = "Demande envoyée : JARVIS réfléchit…";
    } catch (e) { app.voice.awaitingReply = false; handleError(e); }
  };
  draft.addEventListener("keydown", (e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendDraft(); } });

  const save = async (p, msg) => { try { await patch("/api/settings", { voice: p }); if (msg) toast(msg); const nv = (await get("/api/voice")).settings; app.voice.applySettings(nv); } catch (e) { handleError(e); } };
  const vsel = select(v.voices.filter((x) => x.locale.startsWith("fr")).map((x) => [x.name, `${x.name} (${x.locale})`]), s.voice);
  vsel.addEventListener("change", async () => { await save({ voice: vsel.value }); app.voice.speak("Voici ma voix."); });
  const vol = el("input", { type: "range", min: 0, max: 1, step: 0.05, value: s.volume, class: "input", "aria-label": "Volume" });
  vol.addEventListener("change", () => save({ volume: Number(vol.value) }));
  const rate = el("input", { type: "range", min: 120, max: 300, step: 10, value: s.rate, class: "input", "aria-label": "Vitesse" });
  rate.addEventListener("change", () => save({ rate: Number(rate.value) }));

  const p = svcState.provider;
  view.append(el("div", { class: "page narrow", style: { textAlign: "center" } },
    el("div", { class: "core-wrap", style: { margin: "0 auto", width: "min(300px, 66vw)" } }, canvas),
    live,
    el("div", { style: { display: "flex", gap: "10px", justifyContent: "center", flexWrap: "wrap" } }, mic,
      btn("Arrêter la lecture", () => app.voice.stopSpeaking(), { cls: "ghost", icon: "stop" }),
      btn("Tout interrompre", async () => { app.voice.stopListening(); await app.voice.stopSpeaking(); for (const id of app.state?.core?.running || []) await post(`/api/tasks/${id}/cancel`).catch(() => {}); }, { cls: "danger" })),
    !app.voice.supported ? el("p", { class: "error-box", style: { marginTop: "16px" } }, "La dictée n'est pas disponible ici. Ouvrez JARVIS avec son application ; le texte reste toujours disponible.") : null,
    el("div", { style: { marginTop: "18px", textAlign: "left" } }, draft,
      el("div", { style: { display: "flex", gap: "8px", marginTop: "8px", justifyContent: "flex-end" } },
        btn("Effacer", () => { draft.value = ""; }, { cls: "ghost sm" }), btn("Envoyer", sendDraft, { cls: "primary sm", icon: "send" }))),
    el("div", { style: { marginTop: "18px" } }, answer),
    el("div", { class: "panel", style: { textAlign: "left", marginTop: "24px" } },
      el("h3", { style: { marginTop: 0 } }, "Modes d'écoute"),
      el("div", { class: "form" },
        toggle("Envoyer la transcription automatiquement (sinon : vous la relisez avant)", s.auto_send, (x) => save({ auto_send: x }, x ? "Envoi automatique activé." : "La transcription sera à valider.")),
        toggle("Mains libres : après chaque réponse lue, le micro se rouvre (dites « stop » pour arrêter)", s.hands_free, (x, i) => {
          if (x && !app.voice.supported) { i.checked = false; return toast("Dictée indisponible ici.", "err"); }
          save(x ? { hands_free: true, auto_speak: true } : { hands_free: false }, x ? "Mains libres activé : JARVIS lit ses réponses et réécoute ensuite." : "Mains libres désactivé.");
          if (x && !app.voice.listening) app.voice.startListening();
        }),
        toggle("Mot d'activation « Jarvis » (écoute continue, reconnaissance sur ce Mac uniquement)", s.wake_word?.enabled, (x, i) => {
          if (x && !app.voice.wakeSupported) { i.checked = false; return toast("Mot d'activation disponible uniquement dans l'application JARVIS.", "err"); }
          save({ wake_word: { enabled: x } }, x ? "Mot d'activation activé : un bandeau doré l'indique en permanence." : "Mot d'activation désactivé.");
        }),
        toggle("Lire les réponses à voix haute", s.auto_speak, (x) => save({ auto_speak: x }))),
      el("p", { class: "small muted", style: { marginTop: "10px" } },
        "Le mot d'activation n'écoute que si vous l'activez, uniquement avec la reconnaissance vocale de macOS sur l'appareil (aucun son n'est envoyé ; si votre Mac ne le permet pas, JARVIS le dit et le désactive). ",
        "« Couper le micro » dans le bandeau arrête toute écoute. Un bandeau reste visible tant que le micro écoute.")),
    el("div", { class: "panel", style: { textAlign: "left", marginTop: "16px" } },
      el("h3", { style: { marginTop: 0 } }, "Voix de JARVIS"),
      el("div", { class: "form-row" }, field("Voix", vsel), field("Volume", vol), field("Vitesse", rate)),
      el("div", { style: { marginTop: "10px" } }, btn("Tester la voix", () => app.voice.speak("Bonjour Sacha, je suis prêt."), { cls: "sm", icon: "speaker" }))),
    el("div", { class: "panel", style: { textAlign: "left", marginTop: "16px" } },
      el("h3", { style: { marginTop: 0 } }, "Confidentialité"),
      el("p", { class: "small muted" },
        app.voice.engine === "macOS (Speech)" ? "Dictée : reconnaissance vocale de macOS, sur l'appareil quand le Mac le permet (sinon via Apple pour la dictée par bouton ; jamais pour le mot d'activation). "
          : app.voice.engine === "navigateur" ? "Dictée : moteur du navigateur (Chrome envoie l'audio à Google). " : "Dictée indisponible ici. ",
        "Voix : synthèse macOS locale. JARVIS ne conserve aucun audio. ",
        `Le texte de vos demandes est envoyé au fournisseur IA actif : ${p ? `${p.label}${p.models?.length ? "" : ""}` : "aucun"}${p && !p.available ? " (indisponible)" : ""}.`))));

  app.core = new Core(canvas); app.syncCore();
  app.voice.onInterim = (t) => { live.textContent = t ? `« ${t} »` : ""; };
  app.voice.onTranscript = async (text, conf, opts) => {
    live.textContent = conf ? `Compris (confiance ${Math.round(conf * 100)} %)` : "Compris.";
    draft.value = text;
    if (opts?.send) await sendDraft(); else draft.focus();
  };
  const off = app.on(async (ev) => {
    if (ev.type === "mic") mic.textContent = ev.on ? "Arrêter l'écoute" : "Parler";
    if (ev.type === "message" && ev.conversation_id === convId) {
      const c = await get(`/api/conversations/${convId}`);
      const last = [...c.messages].reverse().find((m) => m.role === "assistant");
      if (last) { answer.style.display = "block"; answer.replaceChildren(md(last.content)); live.textContent = ""; }
    }
  });
  return () => { off(); app.voice.onTranscript = null; app.voice.onInterim = null; app.core = null; };
}
