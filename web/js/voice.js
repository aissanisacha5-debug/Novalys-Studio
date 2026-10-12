// Voix : reconnaissance par le moteur de dictée du navigateur (Web Speech API), synthèse par la voix macOS (backend).
// Le micro est COUPÉ par défaut ; un bandeau permanent s'affiche tant qu'il est actif ; aucun audio n'est enregistré par JARVIS.
import { post } from "./api.js";
import { $, handleError, toast } from "./ui.js";

const SR = window.SpeechRecognition || window.webkitSpeechRecognition;

export class Voice {
  constructor(app) {
    this.app = app; this.listening = false; this.rec = null; this.interim = ""; this.onTranscript = null; this.onInterim = null;
    this.supported = !!SR;
  }
  toggle() { this.listening ? this.stopListening() : this.startListening(); }
  startListening() {
    if (!this.supported) { toast("La reconnaissance vocale n'est pas disponible dans ce navigateur (utilisez la fenêtre JARVIS ouverte avec Chrome).", "err"); return; }
    if (this.listening) return;
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
  stopListening() { try { this.rec?.abort(); } catch { /* ignore */ } this.setListening(false); }
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
