// Nova : accueil minimaliste (petit noyau central), puis cartes et vue détaillée quand Nova présente des éléments réels.
// La conversation est vocale ; aucun texte de réponse ni transcription n'est affiché.
import { api, get, post, stream } from "../api.js";
import { Board } from "./board.js";
import { NativeListener, WebListener } from "./listener.js";
import { NovaSession } from "./session.js";
import { BrowserSpeaker, MacSpeaker } from "./speaker.js";
import { STATE_LABELS } from "./states.js";

// Les menus de l'application macOS envoient vers les pages de la console (#/parametres…).
const toConsole = () => { if (location.hash.startsWith("#/")) location.replace("/console" + location.hash); };
toConsole(); addEventListener("hashchange", toConsole);

const $ = (id) => document.getElementById(id);
const body = document.body;
const HINTS = { repos: "Touchez pour parler", ecoute: "Je vous écoute", reflexion: "Je réfléchis", recherche: "Je cherche",
  reponse: "", execution: "J'agis", erreur: "Un problème est survenu" };

const bridge = window.webkit?.messageHandlers?.jarvisVoice;
const listener = bridge ? new NativeListener(bridge) : new WebListener();
const speaker = bridge ? new MacSpeaker(() => post("/api/voice/stop").catch(() => {})) : new BrowserSpeaker();
const voiceOut = speaker.kind === "client" ? "client" : "mac";

const store = {
  get(k) { try { return JSON.parse(localStorage.getItem(k) || "null"); } catch { return null; } },
  set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch { /* stockage indisponible : contexte limité à la session */ } },
};
const clock = { now: () => Date.now(), setTimeout: (f, ms) => setTimeout(f, ms), clearTimeout: (id) => clearTimeout(id) };
let wakeLock = null;
async function keepAwake(on) {
  try {
    if (on && !wakeLock && navigator.wakeLock) { wakeLock = await navigator.wakeLock.request("screen"); wakeLock.addEventListener("release", () => { wakeLock = null; }); }
    if (!on && wakeLock) { await wakeLock.release(); wakeLock = null; }
  } catch { /* économiseur d'écran non contrôlable ici */ }
}

const session = new NovaSession({
  listener, speaker, store, clock,
  bargeIn: !matchMedia("(pointer: coarse)").matches,
  api: {
    chat: (text, conversationId) => post("/api/chat", { text, conversation_id: conversationId, source: "voix", voice_out: voiceOut, client_ts: Date.now() }),
    cancelTask: (id) => post(`/api/tasks/${id}/cancel`, { reason: "interruption" }),
  },
  onState(st) {
    body.dataset.state = st;
    $("nova-hint").textContent = HINTS[st];
    $("nova-orb").setAttribute("aria-label", STATE_LABELS[st]);
    keepAwake(session.s.active);
  },
});

const board = new Board($("nova-board"), {
  onChange: (kind) => { body.dataset.view = kind; },
  onApprove: (id) => post(`/api/confirmations/${id}`, { approve: true }).catch(() => board.approveFailed()),
});

const refreshConfirmations = () => get("/api/confirmations").then((l) => board.setConfirmations(l)).catch(() => {});

function greet() {
  const now = new Date();
  get("/api/state").then((s) => {
    const name = s?.settings?.assistant?.user_name || "";
    $("nova-hello").textContent = `${now.getHours() >= 18 ? "Bonsoir" : "Bonjour"}${name ? " " + name : ""}`;
    session.setOnline(true);
  }).catch(() => session.setOnline(false));
  $("nova-date").textContent = now.toLocaleDateString("fr-FR", { weekday: "long", day: "numeric", month: "long" });
}

stream((ev) => {
  session.onServer(ev);
  if (ev.type === "nova_view") { ev.view ? board.show(ev.view) : board.clear(); refreshConfirmations(); }
  if (ev.type === "confirmation") refreshConfirmations();
  if (ev.type === "activity" && (ev.state === "termine" || ev.state === "erreur")) board.taskFinished(ev.task_id, ev.state === "termine");
}, (on) => session.setOnline(on));

greet(); session.emit();
api("GET", "/api/nova/view").then((r) => { if (r?.view) { board.show(r.view); refreshConfirmations(); } }).catch(() => {});

$("nova-orb").addEventListener("click", (e) => { e.stopPropagation(); session.tap(); });
$("nova").addEventListener("click", () => session.tap());
addEventListener("keydown", (e) => {
  if (e.target.closest?.(".nova-card") && e.key === "Enter") return;
  if (e.key === " " || e.key === "Enter") { e.preventDefault(); if (!board.approve()) session.tap(); }
  if (e.key === "Escape") { if (!board.back()) session.stop(); }
});
document.addEventListener("visibilitychange", () => { if (document.hidden) session.suspend(); });
