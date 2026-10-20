// Accueil Nova : un noyau lumineux plein écran, une conversation vocale, aucun texte de réponse affiché.
import { api, post, stream } from "../api.js";
import { Core } from "../core.js";
import { NativeListener, WebListener } from "./listener.js";
import { NovaSession } from "./session.js";
import { BrowserSpeaker, MacSpeaker } from "./speaker.js";
import { CORE_STATE, STATE_LABELS } from "./states.js";

// Les menus de l'application macOS envoient vers les pages de la console (#/parametres…).
const toConsole = () => { if (location.hash.startsWith("#/")) location.replace("/console" + location.hash); };
toConsole(); addEventListener("hashchange", toConsole);

const bridge = window.webkit?.messageHandlers?.jarvisVoice;
const listener = bridge ? new NativeListener(bridge) : new WebListener();
const speaker = bridge ? new MacSpeaker(() => post("/api/voice/stop").catch(() => {})) : new BrowserSpeaker();
const voiceOut = speaker.kind === "client" ? "client" : "mac";

const store = {
  get(k) { try { return JSON.parse(localStorage.getItem(k) || "null"); } catch { return null; } },
  set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch { /* stockage indisponible : contexte limité à la session */ } },
};
const clock = { now: () => Date.now(), setTimeout: (f, ms) => setTimeout(f, ms), clearTimeout: (id) => clearTimeout(id) };

const core = new Core(document.getElementById("nova-core"));
const live = document.getElementById("nova-state");
const stage = document.getElementById("nova");
let wakeLock = null;

async function keepAwake(on) {
  try {
    if (on && !wakeLock && navigator.wakeLock) { wakeLock = await navigator.wakeLock.request("screen"); wakeLock.addEventListener("release", () => { wakeLock = null; }); }
    if (!on && wakeLock) { await wakeLock.release(); wakeLock = null; }
  } catch { /* économiseur d'écran non contrôlable ici */ }
}

const session = new NovaSession({
  listener, speaker, store, clock,
  // Interrompre la parole pendant qu'elle parle : sur ordinateur, le micro reste ouvert (filtre d'écho) ;
  // sur téléphone, micro et haut-parleur se gênent : on interrompt d'un toucher.
  bargeIn: !matchMedia("(pointer: coarse)").matches,
  api: {
    chat: (text, conversationId) => post("/api/chat", { text, conversation_id: conversationId, source: "voix", voice_out: voiceOut, client_ts: Date.now() }),
    cancelTask: (id) => post(`/api/tasks/${id}/cancel`, { reason: "interruption" }),
  },
  onState(st) {
    core.set(CORE_STATE[st]);
    stage.dataset.state = st;
    live.textContent = STATE_LABELS[st];
    keepAwake(session.s.active);
  },
});
session.emit();

stream((ev) => session.onServer(ev), (on) => session.setOnline(on));
api("GET", "/api/state").then(() => session.setOnline(true)).catch(() => session.setOnline(false));

stage.addEventListener("click", () => session.tap());
addEventListener("keydown", (e) => {
  if (e.key === " " || e.key === "Enter") { e.preventDefault(); session.tap(); }
  if (e.key === "Escape") session.stop();
});
document.addEventListener("visibilitychange", () => { if (document.hidden) session.suspend(); });
