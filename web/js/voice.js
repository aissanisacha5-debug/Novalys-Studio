// Voix : reconnaissance par le moteur de dictée du navigateur (Web Speech API), synthèse par la voix macOS (backend).
// Le micro est COUPÉ par défaut ; un bandeau permanent s'affiche tant qu'il est actif ; aucun audio n'est enregistré par JARVIS.
import { post } from "./api.js";
import { $, handleError, toast } from "./ui.js";

const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
// Dans l'application JARVIS (WebKit), la dictée passe par le moteur natif de macOS (Speech, sur l'appareil si possible).
const NATIVE = !!(window.webkit && window.webkit.messageHandlers && window.webkit.messageHandlers.jarvisVoice);

export class Voice {
  constructor(app) {
    this.app = app; this.listening = false; this.rec = null; this.interim = ""; this.onTranscript = null; this.onInterim = null;
    this.supported = NATIVE || !!SR;
    this.engine = NATIVE ? "macOS (Speech)" : SR ? "navigateur" : "aucun";
    if (NATIVE) {
      window.jarvisNativeVoice = {
        emit: (ev) => {
          if (ev.type === "start") this.setListening(true);
          if (ev.type === "result") {
            if (ev.final) { if (ev.text.trim()) this.deliver(ev.text.trim(), ev.confidence); }
            else { this.interim = ev.text; this.onInterim?.(ev.text); }
          }
          if (ev.type === "error") { toast(ev.message, ev.error === "no-speech" ? "wait" : "err"); this.setListening(false); }
          if (ev.type === "end") this.setListening(false);
        },
      };
    }
  }
  toggle() { this.listening ? this.stopListening() : this.startListening(); }
  startListening() {
    if (!this.supported) { toast("La reconnaissance vocale n'est pas disponible ici : ouvrez JARVIS avec son application.", "err"); return; }
    if (this.listening) return;
    if (NATIVE) {
      // l'indicateur ne s'allume qu'à la confirmation du micro par l'application (événement « start »)
      window.webkit.messageHandlers.jarvisVoice.postMessage({ cmd: "start" });
      post("/api/voice/stop").catch(() => {});
      return;
    }
    const rec = new SR();
    rec.lang = "fr-FR"; rec.interimResults = true; rec.continuous = false; rec.maxAlternatives = 1;
    rec.onresult = (e) => {
      let finalText = "", interim = "";
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const r = e.results[i];
        if (r.isFinal) finalText += r[0].transcript; else interim += r[0].transcript;
      }
      this.interim = interim; this.onInterim?.(interim);
      if (finalText.trim()) this.deliver(finalText.trim(), e.results[e.results.length - 1][0].confidence);
    };
    rec.onerror = (e) => {
      const msg = { "not-allowed": "Accès au micro refusé : autorisez le micro pour cette fenêtre (icône dans la barre d'adresse ou Réglages Système > Confidentialité > Micro).",
        "no-speech": "Je n'ai rien entendu.", "network": "Reconnaissance vocale indisponible (réseau).", "audio-capture": "Aucun micro détecté." }[e.error] || `Erreur vocale : ${e.error}`;
      if (e.error !== "aborted") toast(msg, e.error === "no-speech" ? "wait" : "err");
    };
    rec.onend = () => { this.setListening(false); };
    try { rec.start(); } catch (e) { handleError(e); return; }
    this.rec = rec; this.setListening(true);
    post("/api/voice/stop").catch(() => {});          // JARVIS se tait quand on lui parle
  }
  stopListening() {
    if (NATIVE) { window.webkit.messageHandlers.jarvisVoice.postMessage({ cmd: "stop" }); }
    try { this.rec?.abort(); } catch { /* ignore */ }
    this.setListening(false);
  }
  setListening(on) {
    this.listening = on;
    $("#mic-banner").classList.toggle("on", on);
    for (const b of document.querySelectorAll("[data-mic]")) { b.classList.toggle("on", on); b.setAttribute("aria-pressed", String(on)); }
    this.app.syncCore();
    this.app.emit({ type: "mic", on });
  }
  async deliver(text, confidence) {
    this.stopListening();
    if (this.onTranscript) return this.onTranscript(text, confidence);
    try {
      const r = await post("/api/chat", { text, conversation_id: this.app.currentConv, source: "voix" });
      this.app.currentConv = r.conversation_id;
      if (!location.hash.startsWith("#/conversation") && !location.hash.startsWith("#/vocal")) this.app.go(`#/conversation/${r.conversation_id}`);
      this.app.emit({ type: "message", conversation_id: r.conversation_id });
    } catch (e) { handleError(e); }
  }
  async speak(text) { try { await post("/api/voice/speak", { text }); } catch (e) { handleError(e); } }
  async stopSpeaking() { try { await post("/api/voice/stop"); } catch { /* ignore */ } }
}
