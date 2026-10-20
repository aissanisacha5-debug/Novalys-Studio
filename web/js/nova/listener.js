// Micro de Nova : reconnaissance vocale du navigateur, ou dictée native dans l'application macOS.
// Le micro n'est ouvert qu'après un geste de Sacha, et jamais en arrière-plan (contrainte des navigateurs mobiles).

export class WebListener {
  constructor(SR = globalThis.SpeechRecognition || globalThis.webkitSpeechRecognition) {
    this.SR = SR; this.supported = !!SR; this.rec = null; this.onEvent = () => {};
  }
  start() {
    const rec = new this.SR();
    rec.lang = "fr-FR"; rec.interimResults = true; rec.continuous = false; rec.maxAlternatives = 1;
    rec.onstart = () => this.onEvent({ type: "start" });
    rec.onresult = (e) => {
      let fin = "", interim = "";
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const r = e.results[i];
        if (r.isFinal) fin += r[0].transcript; else interim += r[0].transcript;
      }
      if (fin.trim()) this.onEvent({ type: "final", text: fin.trim() });
      else if (interim) this.onEvent({ type: "interim", text: interim });
    };
    rec.onerror = (e) => this.onEvent({ type: "error", error: e.error || "network" });
    rec.onend = () => { if (this.rec === rec) this.rec = null; this.onEvent({ type: "end" }); };
    this.rec = rec;
    try { rec.start(); } catch (e) { this.rec = null; this.onEvent({ type: "error", error: "audio-capture" }); this.onEvent({ type: "end" }); }
  }
  stop() { const r = this.rec; this.rec = null; try { r?.abort(); } catch { /* ignore */ } }
}

// Pont vers la dictée native (application JARVIS/Nova pour macOS, framework Speech).
export class NativeListener {
  constructor(bridge) {
    this.bridge = bridge; this.supported = true; this.onEvent = () => {};
    window.jarvisNativeVoice = { emit: (ev) => this.native(ev) };
  }
  native(ev) {
    if (ev.type === "start") this.onEvent({ type: "start" });
    else if (ev.type === "result") this.onEvent({ type: ev.final ? "final" : "interim", text: ev.text || "" });
    else if (ev.type === "error") this.onEvent({ type: "error", error: ev.error === "not-authorized" ? "not-allowed" : (ev.error || "network") });
    else if (ev.type === "end") this.onEvent({ type: "end" });
  }
  start() { this.bridge.postMessage({ cmd: "start", silenceMs: 900 }); }
  stop() { this.bridge.postMessage({ cmd: "stop" }); }
}
