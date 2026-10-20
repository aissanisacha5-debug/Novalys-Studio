// Conversation vocale de Nova : écoute → envoi au service → réponse lue phrase par phrase → nouvelle écoute.
// Aucune dépendance au DOM : le micro, la voix, l'API et l'horloge sont injectés (testable hors navigateur).
import { isEcho } from "../echo.js";
import { deriveState } from "./states.js";

export const STOP_WORDS = /^(stop|arr[eê]te|termin[eé]|fin|c'est tout|merci nova|au revoir)[.!]?$/i;
const CONV_KEY = "nova.conversation";
const CONV_TTL_MS = 6 * 3600 * 1000;       // au-delà, une nouvelle conversation commence (le contexte ancien reste en mémoire durable)
const DUP_MS = 8000;

export const MESSAGES = {
  "not-allowed": "Je n'ai pas accès au micro. Autorisez-le dans les réglages du navigateur, puis touchez l'écran.",
  "service-not-allowed": "La reconnaissance vocale est bloquée sur cet appareil.",
  "audio-capture": "Je ne trouve aucun micro.",
  network: "La reconnaissance vocale ne répond pas. Vérifiez la connexion.",
  unsupported: "Ce navigateur ne permet pas la reconnaissance vocale. Essayez Chrome, Edge ou Safari.",
  api: "Je n'arrive pas à joindre mon service.",
  confirmation: "J'ai besoin de votre accord pour continuer. Vous pouvez le donner dans la console.",
};

export class NovaSession {
  constructor({ api, listener, speaker, store, clock, onState = () => {}, bargeIn = true, errorMs = 3000 }) {
    Object.assign(this, { api, listener, speaker, store, clock, onState, bargeIn, errorMs });
    this.s = { active: false, listening: false, barge: false, speaking: false, sending: false, pendingTask: null,
      phase: null, errorUntil: 0, offline: false };
    this.spoken = ""; this.lastSent = null; this.noSpeech = 0; this.buffer = []; this.timers = new Set();
    this.lastState = null; this.confirmAsked = null;
    listener.onEvent = (ev) => this.onListener(ev);
    speaker.onEvent = (ev) => this.onSpeaker(ev);
  }

  // -- état ---------------------------------------------------------------------------------
  get state() { return deriveState(this.s, this.clock.now()); }
  emit() { const st = this.state; if (st !== this.lastState) { this.lastState = st; this.onState(st); } }
  later(fn, ms) {
    const id = this.clock.setTimeout(() => { this.timers.delete(id); fn(); }, ms);
    this.timers.add(id); return id;
  }
  clearTimers() { for (const id of this.timers) this.clock.clearTimeout(id); this.timers.clear(); }

  conversationId() {
    const c = this.store.get(CONV_KEY);
    return c && this.clock.now() - c.t < CONV_TTL_MS ? c.id : null;
  }

  // -- gestes de Sacha ------------------------------------------------------------------------
  // Un toucher : démarre la conversation, interrompt Nova pendant qu'elle parle ou réfléchit, ou termine l'écoute.
  tap() {
    if (!this.s.active) { this.s.active = true; this.speaker.unlock?.(); this.listen(); return; }
    if (this.s.speaking || this.s.sending || this.s.pendingTask != null) { this.interrupt(); return; }
    if (this.s.listening) { this.stop(); return; }
    this.listen();
  }

  stop() {
    this.s.active = false; this.clearTimers();
    if (this.s.listening) this.listener.stop();
    this.s.listening = false; this.s.barge = false;
    if (this.s.speaking) this.speaker.cancel();
    this.s.speaking = false; this.spoken = "";
    this.emit();
  }

  // Onglet masqué ou application en arrière-plan : les navigateurs coupent le micro et le son. La tâche continue côté serveur.
  suspend() { this.stop(); }

  setOnline(on) { this.s.offline = !on; this.emit(); }

  interrupt() {
    this.speaker.cancel(); this.s.speaking = false; this.spoken = "";
    if (this.s.pendingTask != null) this.api.cancelTask(this.s.pendingTask).catch(() => {});
    this.s.pendingTask = null; this.s.phase = null; this.s.sending = false; this.buffer = [];
    if (this.s.listening) { this.listener.stop(); this.s.listening = false; }
    this.s.barge = false;
    this.listen();
  }

  listen(barge = false) {
    if (!this.listener.supported) { this.fail("unsupported", true); return; }
    if (this.s.listening) return;
    this.s.listening = true; this.s.barge = barge;
    this.listener.start({ barge });
    this.emit();
  }

  fail(code, stopSession) {
    this.s.errorUntil = this.clock.now() + this.errorMs;
    if (stopSession) { this.s.active = false; if (this.s.listening) this.listener.stop(); this.s.listening = false; }
    const msg = MESSAGES[code];
    if (msg && this.speaker.canSpeakLocally) this.sayNow(msg);
    this.emit();
    this.later(() => this.emit(), this.errorMs + 10);
  }

  // -- micro --------------------------------------------------------------------------------
  onListener(ev) {
    if (ev.type === "interim") {
      if (this.s.barge && this.s.speaking && !isEcho(ev.text, this.spoken) && ev.text.trim().split(/\s+/).length >= 2) this.interrupt();
      return;
    }
    if (ev.type === "final") {
      const text = (ev.text || "").trim();
      if (this.s.barge && this.s.speaking) {
        if (!text || isEcho(text, this.spoken)) return;      // Nova s'entend elle-même
        this.interrupt();
      }
      if (text) { this.noSpeech = 0; this.utter(text); }
      return;
    }
    if (ev.type === "error") {
      if (ev.error === "aborted") return;
      if (ev.error === "no-speech") { this.noSpeech += 1; if (this.noSpeech >= 3) { this.noSpeech = 0; this.s.active = false; } return; }
      this.fail(ev.error in MESSAGES ? ev.error : "network", true);
      return;
    }
    if (ev.type === "end") {
      const wasBarge = this.s.barge;
      this.s.listening = false; this.s.barge = false;
      // fin d'écoute sans phrase : on rouvre le micro tant que la conversation est active et que Nova ne travaille pas
      if (this.s.active && !this.s.sending && this.s.pendingTask == null && !this.s.speaking && !wasBarge) this.later(() => this.s.active && !this.s.listening && this.listen(), 250);
      else if (this.s.active && wasBarge && this.s.speaking && this.bargeIn) this.later(() => this.s.speaking && !this.s.listening && this.listen(true), 150);
      this.emit();
    }
  }

  async utter(text) {
    if (this.s.listening) { this.listener.stop(); this.s.listening = false; this.s.barge = false; }
    const key = text.toLowerCase().replace(/\s+/g, " ").trim();
    if (STOP_WORDS.test(key)) { this.stop(); return; }
    const now = this.clock.now();
    if (this.s.sending || (this.lastSent && this.lastSent.key === key && now - this.lastSent.t < DUP_MS)) return;
    this.lastSent = { key, t: now };
    this.s.sending = true; this.s.phase = "reflexion"; this.buffer = []; this.emit();
    try {
      const r = await this.api.chat(text, this.conversationId());
      if (!this.s.sending) return;                         // interrompu pendant l'envoi
      this.store.set(CONV_KEY, { id: r.conversation_id, t: this.clock.now() });
      this.s.pendingTask = r.task_id; this.s.sending = false;
      const early = this.buffer.filter((e) => e.task_id === r.task_id); this.buffer = [];
      for (const e of early) this.onServer(e);              // événements arrivés avant la réponse HTTP
      this.emit();
    } catch (e) {
      this.s.sending = false; this.s.phase = null;
      this.fail("api", true);
    }
  }

  // -- événements du service (SSE) ------------------------------------------------------------
  onServer(ev) {
    if (ev.type === "voice" && this.speaker.kind === "mac") { this.speaker.serverVoice?.(ev); return; }
    if (ev.task_id == null) return;
    if (this.s.sending && this.s.pendingTask == null) { this.buffer.push(ev); return; }
    if (ev.task_id !== this.s.pendingTask && !(ev.type === "speech" && ev.task_id === this.lastTask)) return;
    if (ev.type === "speech") {
      if (this.speaker.kind === "client" && this.s.active) { this.spoken += " " + ev.text; this.sayNow(ev.text); }
      return;
    }
    if (ev.type !== "activity") return;
    if (ev.state === "reflexion") this.s.phase = "reflexion";
    else if (ev.state === "outil") this.s.phase = ev.phase === "recherche" ? "recherche" : "execution";
    else if (ev.state === "autorisation") {
      // Action à risque : Nova ne valide jamais seule. Elle le dit, et la tâche attend l'accord donné dans la console.
      this.lastTask = this.s.pendingTask; this.s.pendingTask = null; this.s.phase = null;
      if (this.confirmAsked !== ev.task_id && this.speaker.canSpeakLocally) { this.confirmAsked = ev.task_id; this.sayNow(MESSAGES.confirmation); }
      if (!this.s.speaking) this.afterTurn();
    } else if (ev.state === "termine" || ev.state === "erreur" || ev.state === "calme") {
      this.lastTask = this.s.pendingTask; this.s.pendingTask = null; this.s.phase = null;
      if (ev.state === "erreur") { this.s.errorUntil = this.clock.now() + this.errorMs; this.later(() => this.emit(), this.errorMs + 10); }
      if (!this.s.speaking) this.afterTurn();
    }
    this.emit();
  }

  // -- voix ---------------------------------------------------------------------------------
  // La phrase est « en cours » dès sa mise en file : pas de retour au repos entre l'arrivée et le premier son.
  // Garde-fou : si la synthèse ne démarre jamais (navigateur muet), Nova ne reste pas bloquée en « réponse ».
  sayNow(text) {
    this.s.speaking = true; this.awaitStart = true;
    this.speaker.say(text);
    this.later(() => { if (this.awaitStart) { this.awaitStart = false; this.onSpeaker({ type: "error", error: "no-start" }); } }, 5000);
  }

  onSpeaker(ev) {
    if (ev.type === "start") {
      this.awaitStart = false;
      this.s.speaking = true;
      if (this.bargeIn && this.s.active && !this.s.listening && this.listener.supported) this.later(() => this.s.speaking && !this.s.listening && this.listen(true), 250);
    } else if (ev.type === "idle" || ev.type === "error") {
      this.awaitStart = false; this.s.speaking = false; this.spoken = "";
      if (this.s.listening && this.s.barge) { this.listener.stop(); this.s.listening = false; this.s.barge = false; }
      if (ev.type === "error") { this.s.errorUntil = this.clock.now() + this.errorMs; this.later(() => this.emit(), this.errorMs + 10); }
      if (this.s.pendingTask == null && !this.s.sending) this.afterTurn();
    }
    this.emit();
  }

  afterTurn() { if (this.s.active) this.later(() => this.s.active && !this.s.listening && !this.s.speaking && this.listen(), 350); }
}
