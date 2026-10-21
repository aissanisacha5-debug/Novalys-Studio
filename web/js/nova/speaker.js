// Voix de Nova.
// - BrowserSpeaker : synthèse de l'appareil (téléphone, navigateur de bureau), phrase par phrase, interruptible.
// - MacSpeaker : dans l'application macOS, la voix du Mac lit la réponse (service Nova, commande say).

// Voix de référence de Nova (vidéo) : masculine, grave. À qualité égale, une voix masculine est préférée.
const MALE = /thomas|henri|paul|r[ée]my|daniel|nicolas|jacques|eddy|reed|claude|antoine|alain|gu?illaume|fabrice|jean/i;

// Choisit la voix française la plus naturelle disponible sur l'appareil.
export function pickVoice(voices, lang = "fr-FR") {
  let best = null, bestScore = -Infinity;
  for (const v of voices || []) {
    const vl = String(v.lang || "").replace("_", "-");
    if (!vl.toLowerCase().startsWith("fr")) continue;
    const name = `${v.name || ""} ${v.voiceURI || ""}`;
    let score = vl.toLowerCase() === lang.toLowerCase() ? 40 : 20;
    if (/natural|neural|online/i.test(name)) score += 30;          // voix neuronales (Edge, Windows, Android)
    if (/premium|enhanced|am[ée]lior|siri/i.test(name)) score += 25;  // voix Apple de qualité supérieure
    if (/google/i.test(name)) score += 15;
    if (/am[ée]lie|audrey|aur[ée]lie|thomas|denise|henri|vivienne|eloise|r[ée]my|marie|paul/i.test(name)) score += 10;
    if (MALE.test(v.name || "")) score += 12;
    if (/compact|espeak/i.test(name)) score -= 20;
    if (v.default) score += 2;
    if (score > bestScore) { best = v; bestScore = score; }
  }
  return best;
}

export class BrowserSpeaker {
  constructor(synth = globalThis.speechSynthesis, Utterance = globalThis.SpeechSynthesisUtterance, { rate = 1.05, pitch = 0.85 } = {}) {
    this.kind = "client"; this.synth = synth; this.Utterance = Utterance; this.rate = rate; this.pitch = pitch;
    this.supported = !!(synth && Utterance); this.canSpeakLocally = this.supported;
    this.pending = 0; this.speaking = false; this.voice = null; this.gen = 0; this.onEvent = () => {};
    if (this.supported) {
      const load = () => { this.voice = pickVoice(this.synth.getVoices()); };
      load();
      this.synth.addEventListener?.("voiceschanged", load);
    }
  }

  // iOS et certains navigateurs n'autorisent le son qu'après un geste : on « réveille » la synthèse au premier toucher.
  unlock() {
    if (!this.supported || this.unlocked) return;
    this.unlocked = true;
    try { const u = new this.Utterance(" "); u.volume = 0; this.synth.speak(u); } catch { /* ignore */ }
  }

  say(text) {
    if (!this.supported || !String(text || "").trim()) return;
    const u = new this.Utterance(text);
    u.lang = "fr-FR"; u.rate = this.rate; u.pitch = this.pitch; if (this.voice) u.voice = this.voice;
    const gen = this.gen;
    u.onstart = () => { if (gen === this.gen && !this.speaking) { this.speaking = true; this.onEvent({ type: "start" }); } };
    const done = (err) => {
      if (gen !== this.gen) return;
      this.pending = Math.max(0, this.pending - 1);
      if (err) { this.pending = 0; this.speaking = false; this.synth.cancel(); this.onEvent({ type: "error", error: err }); return; }
      if (this.pending === 0 && this.speaking) { this.speaking = false; this.onEvent({ type: "idle" }); }
    };
    u.onend = () => done(null);
    u.onerror = (e) => done(e && e.error && !["interrupted", "canceled"].includes(e.error) ? e.error : null);
    this.pending += 1;
    try { this.synth.speak(u); } catch (e) { done("synthesis-failed"); }
  }

  cancel() {
    this.gen += 1; this.pending = 0;
    try { this.synth?.cancel(); } catch { /* ignore */ }
    if (this.speaking) { this.speaking = false; this.onEvent({ type: "idle" }); }
  }
}

export class MacSpeaker {
  constructor(stopFn) { this.kind = "mac"; this.supported = true; this.canSpeakLocally = false; this.stopFn = stopFn; this.speaking = false; this.onEvent = () => {}; }
  unlock() {}
  say() {}
  serverVoice(ev) {
    if (ev.speaking && !this.speaking) { this.speaking = true; this.onEvent({ type: "start" }); }
    if (!ev.speaking && this.speaking) { this.speaking = false; this.onEvent({ type: "idle" }); }
  }
  cancel() { this.stopFn(); if (this.speaking) { this.speaking = false; this.onEvent({ type: "idle" }); } }
}
