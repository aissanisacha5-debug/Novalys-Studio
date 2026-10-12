// Mode vocal : grand noyau, micro (coupé par défaut), transcription, réponse lue à voix haute, arrêt immédiat.
import { get, patch, post } from "../api.js";
import { btn, el, field, handleError, md, select, toast } from "../ui.js";
import { Core } from "../core.js";

export async function render(view, params, app) {
  const v = await get("/api/voice");
  const canvas = el("canvas", { "aria-hidden": "true" });
  const transcript = el("div", { class: "lead", style: { minHeight: "1.6em", textAlign: "center", margin: "8px auto" } });
  const answer = el("div", { class: "panel", style: { display: "none", maxWidth: "720px", margin: "0 auto" } });
  const mic = el("button", { class: "btn primary mic", type: "button", "data-mic": "", style: { height: "44px", padding: "0 22px" }, "aria-pressed": "false" }, "Activer le micro");
  mic.addEventListener("click", () => app.voice.toggle());
  const stopBtn = btn("Arrêter immédiatement", async () => { app.voice.stopListening(); await app.voice.stopSpeaking(); }, { cls: "danger" });
  const autoSpeak = el("input", { type: "checkbox" }); autoSpeak.checked = !!v.settings.auto_speak;
  autoSpeak.addEventListener("change", async () => { try { await patch("/api/settings", { voice: { auto_speak: autoSpeak.checked } }); toast("Réglage enregistré."); } catch (e) { handleError(e); } });
  const voiceSel = select(v.voices.filter((x) => x.locale.startsWith("fr")).map((x) => [x.name, `${x.name} (${x.locale})`]), v.settings.voice);
  voiceSel.addEventListener("change", () => patch("/api/settings", { voice: { voice: voiceSel.value } }).then(() => app.voice.speak("Voici ma nouvelle voix.")).catch(handleError));

  const unsupported = !app.voice.supported;
  view.append(el("div", { class: "page narrow", style: { textAlign: "center" } },
    el("div", { class: "core-wrap", style: { margin: "0 auto", width: "min(320px, 70vw)" } }, canvas),
    transcript,
    el("div", { style: { display: "flex", gap: "10px", justifyContent: "center", flexWrap: "wrap" } }, mic, stopBtn),
    unsupported ? el("p", { class: "error-box", style: { marginTop: "16px" } }, "La reconnaissance vocale n'est pas disponible ici. Ouvrez JARVIS avec son application.") : null,
    el("div", { style: { marginTop: "24px" } }, answer),
    el("div", { class: "panel", style: { textAlign: "left", marginTop: "28px" } },
      el("div", { class: "form-row" },
        field("Voix de JARVIS", voiceSel),
        el("label", { class: "switch", style: { alignSelf: "end" } }, autoSpeak, "Lire les réponses à voix haute")),
      el("p", { class: "small muted", style: { marginTop: "14px" } },
        "Confidentialité : le micro reste coupé tant que vous ne l'activez pas, et un bandeau vert reste visible pendant l'écoute. ",
        app.voice.engine === "macOS (Speech)"
          ? "La transcription utilise la reconnaissance vocale de macOS, sur l'appareil quand le Mac le permet (sinon via les serveurs d'Apple) ; JARVIS n'enregistre aucun audio. "
          : "Dans un navigateur, la transcription utilise le moteur du navigateur (Chrome envoie l'audio à Google) ; JARVIS n'enregistre aucun audio. ",
        "La voix de réponse est la synthèse vocale locale de macOS. Le mot d'activation « Hey Jarvis » n'est pas encore disponible (écoute permanente non implémentée)."))));
  app.core = new Core(canvas); app.syncCore();

  let convId = app.currentConv;
  app.voice.onInterim = (t) => { transcript.textContent = t ? `« ${t} »` : ""; };
  app.voice.onTranscript = async (text, conf) => {
    transcript.textContent = `« ${text} »` + (conf ? `  (confiance ${Math.round(conf * 100)} %)` : "");
    try {
      const r = await post("/api/chat", { text, conversation_id: convId, source: "voix" });
      convId = r.conversation_id; app.currentConv = convId;
    } catch (e) { handleError(e); }
  };
  const off = app.on(async (ev) => {
    if (ev.type === "mic") mic.textContent = ev.on ? "Couper le micro" : "Activer le micro";
    if (ev.type === "message" && ev.conversation_id === convId) {
      const c = await get(`/api/conversations/${convId}`);
      const last = [...c.messages].reverse().find((m) => m.role === "assistant");
      if (last) { answer.style.display = "block"; answer.replaceChildren(md(last.content)); }
    }
  });
  return () => { off(); app.voice.onTranscript = null; app.voice.onInterim = null; app.core = null; };
}
