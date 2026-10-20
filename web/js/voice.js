// Voix : dictée (moteur natif macOS dans l'application, sinon moteur du navigateur), synthèse par la voix macOS (service).
// Le micro est COUPÉ par défaut ; un bandeau permanent indique toute écoute ; aucun audio n'est enregistré par Nova.
// Modes : 1) bouton micro (une phrase, texte corrigeable avant envoi) ; 2) mains libres (le micro se rouvre après chaque
// réponse lue) ; 3) mot d'activation « Nova » (application seulement, reconnaissance SUR L'APPAREIL uniquement).
import { patch, post } from "./api.js";
import { $, handleError, toast } from "./ui.js";
import { isEcho } from "./echo.js";

const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
const NATIVE = !!(window.webkit && window.webkit.messageHandlers && window.webkit.messageHandlers.jarvisVoice);
const STOP_WORDS = /^(stop|arr[eê]te|termin[eé]|fin|c'est tout|merci jarvis)[.!]?$/i;

export class Voice {
  constructor(app) {
    this.app = app; this.listening = false; this.rec = null; this.interim = ""; this.onTranscript = null; this.onInterim = null;
    this.supported = NATIVE || !!SR;
    this.engine = NATIVE ? "macOS (Speech)" : SR ? "navigateur" : "aucun";
    this.wakeSupported = NATIVE;
    this.wakeActive = false; this.handsFree = false; this.autoSend = true; this.awaitingReply = false; this.speaking = false;
    this.bargeIn = true; this.endSilenceMs = 900; this.bargeMode = false; this.spokenText = ""; this.lastSent = null; this.sending = false;
    if (NATIVE) window.jarvisNativeVoice = { emit: (ev) => this.onNative(ev) };
    app.on((ev) => this.onAppEvent(ev));
  }

  native(cmd, extra = {}) { window.webkit.messageHandlers.jarvisVoice.postMessage({ cmd, ...extra }); }

  // Réglages lus depuis le service (Paramètres > Voix)
  applySettings(v) {
    if (!v) return;
    this.autoSend = v.auto_send !== false;
    this.bargeIn = v.barge_in !== false;
    this.endSilenceMs = Number(v.end_silence_ms) || 900;
    this.handsFree = !!v.hands_free && this.supported;
    const wantWake = !!(v.wake_word && v.wake_word.enabled) && this.wakeSupported;
    if (wantWake && !this.wakeActive) this.native("wake_start", { phrase: v.wake_word.phrase || "Nova" });
    if (!wantWake && this.wakeActive) this.native("wake_stop");
    this.render();
  }

  onNative(ev) {
    if (ev.type === "start") this.setListening(true);
    if (ev.type === "wake_listening") { this.wakeActive = true; this.render(); }
    if (ev.type === "wake_stopped") { this.wakeActive = false; this.render(); }
    if (ev.type === "wake_detected") { this.setListening(true); toast("Je vous écoute."); }
    if (ev.type === "result") this.onResult(ev.text || "", !!ev.final, ev.confidence);
    if (ev.type === "error") {
      toast(ev.message, ev.error === "no-speech" ? "wait" : "err");
      if (ev.error === "wake-unavailable") { this.wakeActive = false; patch("/api/settings", { voice: { wake_word: { enabled: false } } }).catch(() => {}); }
      this.setListening(false);
    }
    if (ev.type === "end") this.setListening(false);
  }

  // Écho : la phrase captée ressemble à ce que Nova est en train de dire (haut-parleurs) → ignorée.
  isEcho(text) { return isEcho(text, this.spokenText); }

  onResult(text, final, confidence) {
    if (this.bargeMode && this.speaking) {
      if (this.isEcho(text)) { if (final) this.restartBarge(); return; }
      if (text.trim().split(/\s+/).length >= 2 || final) this.bargeInNow();
    }
    if (final) { if (text.trim()) this.deliver(text.trim(), confidence, this.wakeActive || this.bargeMode); return; }
    this.interim = text; this.onInterim?.(text); this.render(); this.app.setCore("transcription");
  }

  // Interruption : Sacha reprend la parole pendant que Nova parle.
  async bargeInNow() {
    if (!this.speaking) return;
    this.speaking = false;
    post("/api/voice/stop").catch(() => {});
    // n'annule que la réponse en cours de cette conversation vocale (jamais une autre tâche)
    if (this.lastTaskId) post(`/api/tasks/${this.lastTaskId}/cancel`, { reason: "interruption" }).catch(() => {});
    this.app.emit({ type: "barge" });
  }

  restartBarge() {
    if (!this.handsFree || !this.bargeIn) return;
    this.stopListening(true);
    setTimeout(() => { if (this.speaking) this.startListening({ barge: true }); }, 150);
  }

  onAppEvent(ev) {
    if (ev.type === "voice") {
      if (ev.speaking && ev.text) this.spokenText += " " + ev.text;
      if (!ev.speaking) this.spokenText = "";
      // Conversation continue + interruption : le micro écoute aussi pendant que Nova parle.
      if (ev.speaking && !this.speaking && this.handsFree && this.bargeIn && !this.listening) setTimeout(() => this.startListening({ barge: true }), 250);
      this.speaking = !!ev.speaking;
      if (NATIVE && this.wakeActive) this.native(ev.speaking ? "wake_pause" : "wake_resume");   // Nova ne s'écoute pas parler
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

  startListening(opts = {}) {
    if (!this.supported) { toast("La dictée n'est pas disponible ici : ouvrez Nova avec son application.", "err"); return; }
    if (this.listening) return;
    this.bargeMode = !!opts.barge;
    if (!this.bargeMode) post("/api/voice/stop").catch(() => {});   // Nova se tait quand on lui parle
    if (NATIVE) { this.native("start", { silenceMs: this.endSilenceMs }); return; }   // l'indicateur s'allume quand l'application confirme le micro
    const rec = new SR();
    rec.lang = "fr-FR"; rec.interimResults = true; rec.continuous = false; rec.maxAlternatives = 1;
    rec.onresult = (e) => {
      let finalText = "", interim = "";
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const r = e.results[i];
        if (r.isFinal) finalText += r[0].transcript; else interim += r[0].transcript;
      }
      if (finalText.trim()) this.onResult(finalText.trim(), true, e.results[e.results.length - 1][0].confidence);
      else if (interim) this.onResult(interim, false);
    };
    rec.onerror = (e) => {
      const msg = { "not-allowed": "Accès au micro refusé : autorisez le micro pour Nova (Réglages Système > Confidentialité et sécurité > Microphone).",
        "no-speech": "Je n'ai rien entendu.", "network": "Reconnaissance vocale indisponible (réseau).", "audio-capture": "Aucun micro détecté." }[e.error] || `Erreur vocale : ${e.error}`;
      if (e.error !== "aborted") toast(msg, e.error === "no-speech" ? "wait" : "err");
    };
    rec.onend = () => { this.setListening(false); };
    try { rec.start(); } catch (e) { handleError(e); return; }
    this.rec = rec; this.setListening(true);
  }

  stopListening(keepBarge = false) {
    if (!keepBarge) this.bargeMode = false;
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
        ? (this.interim ? `« ${this.interim} »` : "Microphone actif — Nova vous écoute.")
        : this.wakeActive ? "Mot d'activation actif : dites « Nova… » (reconnaissance sur ce Mac, rien n'est envoyé)." : "";
    }
  }

  async disableHandsFree() {
    this.handsFree = false;
    try { await patch("/api/settings", { voice: { hands_free: false } }); } catch { /* ignore */ }
    toast("Mode mains libres désactivé.");
  }

  async deliver(text, confidence, fromWake = false) {
    this.stopListening();
    // Anti-doublon : une même phrase n'est envoyée qu'une fois (8 s), et jamais pendant un envoi en cours.
    const key = text.toLowerCase().replace(/\s+/g, " ").trim();
    if (this.sending || (this.lastSent && this.lastSent.key === key && Date.now() - this.lastSent.t < 8000)) return;
    this.lastSent = { key, t: Date.now() };
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
      this.awaitingReply = true; this.sending = true;
      const r = await post("/api/chat", { text, conversation_id: this.app.currentConv, source: "voix", client_ts: Date.now() });
      this.app.currentConv = r.conversation_id; this.lastTaskId = r.task_id;
      if (!location.hash.startsWith("#/conversation") && !location.hash.startsWith("#/vocal")) this.app.go(`#/conversation/${r.conversation_id}`);
      this.app.emit({ type: "message", conversation_id: r.conversation_id });
    } catch (e) { this.awaitingReply = false; handleError(e); }
    finally { this.sending = false; }
  }

  async speak(text) { try { await post("/api/voice/speak", { text }); } catch (e) { handleError(e); } }
  async stopSpeaking() { try { await post("/api/voice/stop"); } catch { /* ignore */ } }
}
