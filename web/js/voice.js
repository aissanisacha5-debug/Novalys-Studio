// Voix : dictée (moteur natif macOS dans l'application, sinon moteur du navigateur), synthèse par la voix macOS (service).
// Le micro est COUPÉ par défaut ; un bandeau permanent indique toute écoute ; aucun audio n'est enregistré par JARVIS.
// Modes : 1) bouton micro (une phrase, texte corrigeable avant envoi) ; 2) mains libres (le micro se rouvre après chaque
// réponse lue) ; 3) mot d'activation « Jarvis » (application seulement, reconnaissance SUR L'APPAREIL uniquement).
import { patch, post } from "./api.js";
import { $, handleError, toast } from "./ui.js";

const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
const NATIVE = !!(window.webkit && window.webkit.messageHandlers && window.webkit.messageHandlers.jarvisVoice);
const STOP_WORDS = /^(stop|arr[eê]te|termin[eé]|fin|c'est tout|merci jarvis)[.!]?$/i;

export class Voice {
  constructor(app) {
    this.app = app; this.listening = false; this.rec = null; this.interim = ""; this.onTranscript = null; this.onInterim = null;
    this.supported = NATIVE || !!SR;
    this.engine = NATIVE ? "macOS (Speech)" : SR ? "navigateur" : "aucun";
    this.wakeSupported = NATIVE;
    this.wakeActive = false; this.handsFree = false; this.autoSend = false; this.awaitingReply = false; this.speaking = false;
    if (NATIVE) window.jarvisNativeVoice = { emit: (ev) => this.onNative(ev) };
    app.on((ev) => this.onAppEvent(ev));
  }

  native(cmd, extra = {}) { window.webkit.messageHandlers.jarvisVoice.postMessage({ cmd, ...extra }); }

  // Réglages lus depuis le service (Paramètres > Voix)
  applySettings(v) {
    if (!v) return;
    this.autoSend = !!v.auto_send;
    this.handsFree = !!v.hands_free && this.supported;
    const wantWake = !!(v.wake_word && v.wake_word.enabled) && this.wakeSupported;
    if (wantWake && !this.wakeActive) this.native("wake_start", { phrase: v.wake_word.phrase || "Jarvis" });
    if (!wantWake && this.wakeActive) this.native("wake_stop");
    this.render();
  }

  onNative(ev) {
    if (ev.type === "start") this.setListening(true);
    if (ev.type === "wake_listening") { this.wakeActive = true; this.render(); }
    if (ev.type === "wake_stopped") { this.wakeActive = false; this.render(); }
    if (ev.type === "wake_detected") { this.setListening(true); toast("Je vous écoute."); }
    if (ev.type === "result") {
      if (ev.final) { if (ev.text.trim()) this.deliver(ev.text.trim(), ev.confidence, this.wakeActive); }
      else { this.interim = ev.text; this.onInterim?.(ev.text); this.render(); this.app.setCore("transcription"); }
    }
    if (ev.type === "error") {
      toast(ev.message, ev.error === "no-speech" ? "wait" : "err");
      if (ev.error === "wake-unavailable") { this.wakeActive = false; patch("/api/settings", { voice: { wake_word: { enabled: false } } }).catch(() => {}); }
      this.setListening(false);
    }
    if (ev.type === "end") this.setListening(false);
  }

  onAppEvent(ev) {
    if (ev.type === "voice") {
      this.speaking = !!ev.speaking;
      if (NATIVE && this.wakeActive) this.native(ev.speaking ? "wake_pause" : "wake_resume");   // JARVIS ne s'écoute pas parler
      if (!ev.speaking && this.awaitingReply) this.afterReply();
    }
    if (ev.type === "activity" && (ev.state === "termine" || ev.state === "erreur") && this.awaitingReply) {
      // réponse sans lecture vocale (ou lecture désactivée) : on attend un court instant qu'une lecture démarre
      setTimeout(() => { if (!this.speaking && this.awaitingReply) this.afterReply(); }, 1500);
    }
  }

  afterReply() {
    this.awaitingReply = false;
    if (this.handsFree && !this.listening) setTimeout(() => this.startListening(), 400);
    else if (NATIVE && this.wakeActive) this.native("wake_resume");
  }

  toggle() { this.listening ? this.stopListening() : this.startListening(); }

  startListening() {
    if (!this.supported) { toast("La dictée n'est pas disponible ici : ouvrez JARVIS avec son application.", "err"); return; }
    if (this.listening) return;
    post("/api/voice/stop").catch(() => {});          // JARVIS se tait quand on lui parle
    if (NATIVE) { this.native("start"); return; }    // l'indicateur s'allume quand l'application confirme le micro
    const rec = new SR();
    rec.lang = "fr-FR"; rec.interimResults = true; rec.continuous = false; rec.maxAlternatives = 1;
    rec.onresult = (e) => {
      let finalText = "", interim = "";
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const r = e.results[i];
        if (r.isFinal) finalText += r[0].transcript; else interim += r[0].transcript;
      }
      this.interim = interim; this.onInterim?.(interim); this.render();
      if (interim) this.app.setCore("transcription");
      if (finalText.trim()) this.deliver(finalText.trim(), e.results[e.results.length - 1][0].confidence);
    };
    rec.onerror = (e) => {
      const msg = { "not-allowed": "Accès au micro refusé : autorisez le micro pour JARVIS (Réglages Système > Confidentialité et sécurité > Microphone).",
        "no-speech": "Je n'ai rien entendu.", "network": "Reconnaissance vocale indisponible (réseau).", "audio-capture": "Aucun micro détecté." }[e.error] || `Erreur vocale : ${e.error}`;
      if (e.error !== "aborted") toast(msg, e.error === "no-speech" ? "wait" : "err");
    };
    rec.onend = () => { this.setListening(false); };
    try { rec.start(); } catch (e) { handleError(e); return; }
    this.rec = rec; this.setListening(true);
  }

  stopListening() {
    if (NATIVE) this.native("stop");
    try { this.rec?.abort(); } catch { /* ignore */ }
    this.setListening(false);
  }

  setListening(on) {
    this.listening = on;
    if (!on) this.interim = "";
    for (const b of document.querySelectorAll("[data-mic]")) { b.classList.toggle("on", on); b.setAttribute("aria-pressed", String(on)); }
    this.render();
    this.app.syncCore();
    this.app.emit({ type: "mic", on });
  }

  // Bandeau permanent : écoute d'une demande, ou écoute du mot d'activation (sur l'appareil).
  render() {
    const banner = $("#mic-banner"); if (!banner) return;
    const label = banner.querySelector("[data-mic-label]");
    banner.classList.toggle("on", this.listening || this.wakeActive);
    banner.classList.toggle("wake", this.wakeActive && !this.listening);
    if (label) {
      label.textContent = this.listening
        ? (this.interim ? `« ${this.interim} »` : "Microphone actif — JARVIS vous écoute.")
        : this.wakeActive ? "Mot d'activation actif : dites « Jarvis… » (reconnaissance sur ce Mac, rien n'est envoyé)." : "";
    }
  }

  async disableHandsFree() {
    this.handsFree = false;
    try { await patch("/api/settings", { voice: { hands_free: false } }); } catch { /* ignore */ }
    toast("Mode mains libres désactivé.");
  }

  async deliver(text, confidence, fromWake = false) {
    this.stopListening();
    if (STOP_WORDS.test(text.trim())) {
      if (this.handsFree) await this.disableHandsFree();
      this.awaitingReply = false;
      if (NATIVE && this.wakeActive) this.native("wake_resume");
      return;
    }
    // Sans envoi automatique, la transcription est placée dans la zone de saisie pour être corrigée puis envoyée.
    if (this.onTranscript) return this.onTranscript(text, confidence, { send: this.autoSend || this.handsFree || fromWake });
    const input = document.querySelector("#composer-input");
    if (input && !(this.autoSend || this.handsFree || fromWake)) {
      input.value = text; input.dispatchEvent(new Event("input")); input.focus();
      toast("Transcription prête : corrigez-la si besoin, puis Entrée pour l'envoyer.");
      this.app.syncCore();
      return;
    }
    try {
      this.awaitingReply = true;
      const r = await post("/api/chat", { text, conversation_id: this.app.currentConv, source: "voix" });
      this.app.currentConv = r.conversation_id;
      if (!location.hash.startsWith("#/conversation") && !location.hash.startsWith("#/vocal")) this.app.go(`#/conversation/${r.conversation_id}`);
      this.app.emit({ type: "message", conversation_id: r.conversation_id });
    } catch (e) { this.awaitingReply = false; handleError(e); }
  }

  async speak(text) { try { await post("/api/voice/speak", { text }); } catch (e) { handleError(e); } }
  async stopSpeaking() { try { await post("/api/voice/stop"); } catch { /* ignore */ } }
}
