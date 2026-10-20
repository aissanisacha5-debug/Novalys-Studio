// Tests de l'accueil Nova (noyau, conversation vocale, voix). Exécution : node --test tests/js
// Le micro, la synthèse, l'API et l'horloge sont simulés : ces tests vérifient la logique, pas le matériel.
import { test } from "node:test";
import assert from "node:assert/strict";
import { NovaSession, MESSAGES } from "../../web/js/nova/session.js";
import { deriveState, NOVA_STATES, CORE_STATE } from "../../web/js/nova/states.js";
import { BrowserSpeaker, pickVoice } from "../../web/js/nova/speaker.js";
import { isEcho } from "../../web/js/echo.js";
import { avatarIndex, resolveKind, pendingFor } from "../../web/js/nova/board.js";

function fakeClock() {
  let t = 1_000_000, id = 0; const timers = new Map();
  return {
    now: () => t,
    setTimeout: (f, ms) => { timers.set(++id, { f, at: t + ms }); return id; },
    clearTimeout: (i) => timers.delete(i),
    advance(ms) {
      t += ms;
      for (;;) {
        const due = [...timers.entries()].filter(([, v]) => v.at <= t).sort((a, b) => a[1].at - b[1].at)[0];
        if (!due) break; timers.delete(due[0]); due[1].f();
      }
    },
  };
}

function setup(opts = {}) {
  const calls = { chat: [], cancel: [], said: [], listen: 0, stopListen: 0, cancelSpeech: 0 };
  const listener = { supported: opts.micSupported !== false, start: (o) => { calls.listen++; calls.lastBarge = o.barge; }, stop: () => { calls.stopListen++; } };
  const speaker = { kind: "client", canSpeakLocally: true, unlock: () => { calls.unlocked = true; }, say: (t) => calls.said.push(t), cancel: () => { calls.cancelSpeech++; } };
  let next = opts.chat || ((text, conv) => Promise.resolve({ conversation_id: conv || 7, task_id: 42 }));
  const api = { chat: (text, conv) => { calls.chat.push({ text, conv }); return next(text, conv); }, cancelTask: (id) => { calls.cancel.push(id); return Promise.resolve(); } };
  const mem = new Map(opts.store || []);
  const store = { get: (k) => mem.get(k) ?? null, set: (k, v) => mem.set(k, v) };
  const clock = fakeClock();
  const states = [];
  const s = new NovaSession({ api, listener, speaker, store, clock, bargeIn: opts.bargeIn ?? true, onState: (st) => states.push(st) });
  return { s, calls, listener, speaker, clock, states, mem, setChat: (f) => { next = f; } };
}
const flush = () => new Promise((r) => setImmediate(r));

test("les sept états du noyau existent et ont un rendu", () => {
  assert.deepEqual(NOVA_STATES, ["repos", "ecoute", "reflexion", "recherche", "reponse", "execution", "erreur"]);
  for (const st of NOVA_STATES) assert.ok(CORE_STATE[st], st);
});

test("priorité des états : erreur > réponse > écoute > travail > repos", () => {
  const base = { offline: false, errorUntil: 0, speaking: false, listening: false, barge: false, sending: false, pendingTask: null, phase: null };
  assert.equal(deriveState(base, 0), "repos");
  assert.equal(deriveState({ ...base, listening: true }, 0), "ecoute");
  assert.equal(deriveState({ ...base, pendingTask: 1 }, 0), "reflexion");
  assert.equal(deriveState({ ...base, pendingTask: 1, phase: "recherche" }, 0), "recherche");
  assert.equal(deriveState({ ...base, pendingTask: 1, phase: "execution" }, 0), "execution");
  assert.equal(deriveState({ ...base, pendingTask: 1, speaking: true, listening: true, barge: true }, 0), "reponse");
  assert.equal(deriveState({ ...base, speaking: true, errorUntil: 10 }, 5), "erreur");
  assert.equal(deriveState({ ...base, offline: true }, 0), "erreur");
});

test("un toucher ouvre le micro et réveille la voix (geste requis par les navigateurs)", () => {
  const { s, calls, states } = setup();
  s.tap();
  assert.equal(calls.listen, 1); assert.ok(calls.unlocked); assert.equal(states.at(-1), "ecoute");
});

test("tour complet : phrase → réflexion → recherche → réponse vocale → nouvelle écoute", async () => {
  const { s, calls, clock, states } = setup();
  s.tap();
  s.onListener({ type: "final", text: "Quel temps fait-il à Lyon ?" });
  assert.equal(states.at(-1), "reflexion");
  await flush();
  assert.equal(calls.chat[0].text, "Quel temps fait-il à Lyon ?");
  s.onListener({ type: "end" });
  s.onServer({ type: "activity", state: "outil", phase: "recherche", task_id: 42 });
  assert.equal(states.at(-1), "recherche");
  s.onServer({ type: "activity", state: "outil", phase: "execution", task_id: 42 });
  assert.equal(states.at(-1), "execution");
  s.onServer({ type: "speech", text: "Il fait doux.", task_id: 42 });
  assert.deepEqual(calls.said, ["Il fait doux."]);
  s.onSpeaker({ type: "start" });
  assert.equal(states.at(-1), "reponse");
  s.onServer({ type: "activity", state: "termine", task_id: 42 });
  assert.equal(states.at(-1), "reponse");
  const before = calls.listen;
  s.onSpeaker({ type: "idle" });
  clock.advance(400);
  assert.ok(calls.listen > before, "le micro se rouvre après la réponse");
  assert.equal(states.at(-1), "ecoute");
});

test("les événements arrivés avant la réponse HTTP sont rejoués (aucune phrase perdue)", async () => {
  let resolve; const { s, calls, setChat } = setup();
  setChat(() => new Promise((r) => { resolve = r; }));
  s.tap(); s.onListener({ type: "final", text: "Bonjour Nova" });
  s.onServer({ type: "speech", text: "Bonjour Sacha.", task_id: 42 });
  s.onServer({ type: "speech", text: "Autre tâche.", task_id: 99 });
  assert.deepEqual(calls.said, []);
  resolve({ conversation_id: 3, task_id: 42 }); await flush();
  assert.deepEqual(calls.said, ["Bonjour Sacha."]);
});

test("le contexte est conservé : même conversation d'un tour à l'autre, nouvelle après 6 h", async () => {
  const { s, calls, clock } = setup();
  s.tap(); s.onListener({ type: "final", text: "Première question" }); await flush();
  assert.equal(calls.chat[0].conv, null);
  s.onServer({ type: "activity", state: "termine", task_id: 42 });
  clock.advance(10_000);
  s.onListener({ type: "final", text: "Deuxième question" }); await flush();
  assert.equal(calls.chat[1].conv, 7);
  s.onServer({ type: "activity", state: "termine", task_id: 42 });
  clock.advance(7 * 3600 * 1000);
  s.onListener({ type: "final", text: "Troisième question" }); await flush();
  assert.equal(calls.chat[2].conv, null);
});

test("interruption : toucher pendant la réponse coupe la voix, annule la tâche et rouvre le micro", async () => {
  const { s, calls, states } = setup();
  s.tap(); s.onListener({ type: "final", text: "Raconte une histoire" }); await flush();
  s.onSpeaker({ type: "start" });
  s.tap();
  assert.equal(calls.cancelSpeech, 1); assert.deepEqual(calls.cancel, [42]); assert.equal(states.at(-1), "ecoute");
});

test("interruption à la voix : une vraie phrase coupe Nova, son propre écho est ignoré", async () => {
  const { s, calls, clock } = setup();
  s.tap(); s.onListener({ type: "final", text: "Lis-moi le briefing" }); await flush(); s.onListener({ type: "end" });
  s.onServer({ type: "speech", text: "Vous avez trois rendez-vous aujourd'hui.", task_id: 42 });
  s.onSpeaker({ type: "start" }); clock.advance(300);
  assert.equal(calls.lastBarge, true, "micro ouvert pendant la réponse");
  s.onListener({ type: "interim", text: "trois rendez-vous aujourd'hui" });
  assert.equal(calls.cancelSpeech, 0, "écho ignoré");
  s.onListener({ type: "interim", text: "attends une seconde" });
  assert.equal(calls.cancelSpeech, 1); assert.deepEqual(calls.cancel, [42]);
});

test("pas d'interruption vocale sur téléphone (toucher seulement)", async () => {
  const { s, calls, clock } = setup({ bargeIn: false });
  s.tap(); s.onListener({ type: "final", text: "Bonjour" }); await flush(); s.onListener({ type: "end" });
  const n = calls.listen; s.onSpeaker({ type: "start" }); clock.advance(500);
  assert.equal(calls.listen, n);
});

test("anti-doublon : la même phrase répétée dans les 8 s n'est envoyée qu'une fois", async () => {
  const { s, calls } = setup();
  s.tap(); s.onListener({ type: "final", text: "Ouvre mes notes" }); await flush();
  s.onServer({ type: "activity", state: "termine", task_id: 42 });
  s.onListener({ type: "final", text: "ouvre   mes notes" }); await flush();
  assert.equal(calls.chat.length, 1);
});

test("« stop » termine la conversation sans rien envoyer", async () => {
  const { s, calls, states } = setup();
  s.tap(); s.onListener({ type: "final", text: "Stop" }); await flush();
  assert.equal(calls.chat.length, 0); assert.equal(s.s.active, false); assert.equal(states.at(-1), "repos");
});

test("erreurs audio : micro refusé → état erreur expliqué à voix haute, session arrêtée", () => {
  const { s, calls, clock, states } = setup();
  s.tap(); s.onListener({ type: "error", error: "not-allowed" });
  assert.equal(states.at(-1), "erreur"); assert.deepEqual(calls.said, [MESSAGES["not-allowed"]]); assert.equal(s.s.active, false);
  s.onSpeaker({ type: "start" }); assert.equal(s.state, "erreur", "l'erreur reste visible pendant l'explication");
  s.onSpeaker({ type: "idle" });
  clock.advance(3100);
  assert.equal(states.at(-1), "repos");
});

test("silence : le micro se rouvre deux fois puis Nova se met au repos", () => {
  const { s, calls, clock } = setup();
  s.tap();
  for (let i = 0; i < 3; i++) { s.onListener({ type: "error", error: "no-speech" }); s.onListener({ type: "end" }); clock.advance(300); }
  assert.equal(calls.listen, 3); assert.equal(s.s.active, false); assert.equal(s.state, "repos");
});

test("navigateur sans reconnaissance vocale : erreur claire", () => {
  const { s, calls, states } = setup({ micSupported: false });
  s.tap();
  assert.equal(states.at(-1), "erreur"); assert.deepEqual(calls.said, [MESSAGES.unsupported]);
});

test("service injoignable : erreur réseau à l'envoi, puis déconnexion du flux", async () => {
  const { s, calls, states, setChat } = setup();
  setChat(() => Promise.reject(new Error("hors ligne")));
  s.tap(); s.onListener({ type: "final", text: "Bonjour" }); await flush();
  assert.equal(states.at(-1), "erreur"); assert.deepEqual(calls.said, [MESSAGES.api]);
  s.setOnline(false); assert.equal(s.state, "erreur");
});

test("action à risque : Nova le dit et rend la main (aucune validation implicite)", async () => {
  const { s, calls, clock } = setup();
  s.tap(); s.onListener({ type: "final", text: "Supprime ce dossier" }); await flush(); s.onListener({ type: "end" });
  s.onServer({ type: "activity", state: "autorisation", task_id: 42 });
  assert.deepEqual(calls.said, [MESSAGES.confirmation]);
  assert.equal(s.s.pendingTask, null); assert.equal(s.state, "reponse");
  s.onSpeaker({ type: "start" }); s.onSpeaker({ type: "idle" });
  clock.advance(400); assert.equal(s.state, "ecoute");
});

test("arrière-plan : le micro et la voix sont coupés", async () => {
  const { s, calls } = setup();
  s.tap(); s.onSpeaker({ type: "start" });
  s.suspend();
  assert.equal(s.s.active, false); assert.ok(calls.stopListen >= 1); assert.ok(calls.cancelSpeech >= 1);
});

test("choix de la voix : la plus naturelle en français", () => {
  const voices = [
    { name: "Samantha", lang: "en-US" }, { name: "Thomas", lang: "fr-FR" }, { name: "Amélie (Premium)", lang: "fr-CA" },
    { name: "Microsoft Denise Online (Natural) - French (France)", lang: "fr-FR" }, { name: "eSpeak French", lang: "fr" },
  ];
  assert.match(pickVoice(voices).name, /Denise/);
  assert.equal(pickVoice([{ name: "Alex", lang: "en-US" }]), null);
});

test("synthèse : phrases enchaînées, fin signalée une fois, annulation immédiate, erreur remontée", () => {
  const spoken = []; const synth = { getVoices: () => [], speak: (u) => spoken.push(u), cancel: () => { spoken.length = 0; } };
  class U { constructor(t) { this.text = t; } }
  const sp = new BrowserSpeaker(synth, U); const evs = []; sp.onEvent = (e) => evs.push(e.type);
  sp.say("Un."); sp.say("Deux.");
  const [a, b] = spoken; a.onstart(); a.onend(); b.onstart(); b.onend();
  assert.deepEqual(evs, ["start", "idle"]);
  sp.say("Trois."); spoken.at(-1).onstart(); sp.cancel();
  assert.deepEqual(evs, ["start", "idle", "start", "idle"]);
  sp.say("Quatre."); const d = spoken.at(-1); d.onstart(); d.onerror({ error: "audio-busy" });
  assert.deepEqual(evs.slice(-2), ["start", "error"]);
});

test("filtre d'écho", () => {
  assert.ok(isEcho("trois rendez-vous aujourd'hui", "Vous avez trois rendez-vous aujourd'hui."));
  assert.ok(!isEcho("attends une seconde", "Vous avez trois rendez-vous aujourd'hui."));
});

test("phrase en file : pas de retour au repos avant le premier son ; synthèse muette → erreur puis reprise", async () => {
  const { s, calls, clock, states } = setup();
  s.tap(); s.onListener({ type: "final", text: "Bonjour" }); await flush(); s.onListener({ type: "end" });
  s.onServer({ type: "speech", text: "Bonjour.", task_id: 42 });
  s.onServer({ type: "activity", state: "termine", task_id: 42 });
  assert.equal(s.state, "reponse");
  assert.ok(!states.slice(states.lastIndexOf("reflexion")).includes("repos"));
  clock.advance(5100);                                   // le son n'a jamais démarré
  assert.equal(s.state, "erreur");
  clock.advance(3500);
  assert.ok(calls.listen >= 2); assert.equal(s.state, "ecoute");
});

test("tableau : teinte d'avatar stable, vue résolue, validation liée à la vraie confirmation de la tâche", () => {
  assert.equal(avatarIndex("Sonia"), avatarIndex("Sonia"));
  for (const n of ["", "Lucas", "Élodie", null]) assert.ok(avatarIndex(n) >= 1 && avatarIndex(n) <= 4);

  const list = { vue: "liste", elements: [] }; const withDetail = { ...list, detail: { validation: { question: "?" } } };
  assert.equal(resolveKind(null, false), "accueil");
  assert.equal(resolveKind(list, true), "liste");           // pas de détail : on reste sur la liste
  assert.equal(resolveKind(withDetail, false), "liste");
  assert.equal(resolveKind(withDetail, true), "detail");   // ouvert localement depuis la carte
  assert.equal(resolveKind({ ...withDetail, vue: "detail" }, false), "detail");
  assert.equal(resolveKind({ vue: "succes" }, false), "succes");

  const view = { ...withDetail, vue: "detail", task_id: 12 };
  const confs = [{ id: 1, task_id: 11, status: "en_attente" }, { id: 2, task_id: 12, status: "en_attente" }];
  assert.equal(pendingFor(view, confs).id, 2);
  assert.equal(pendingFor(view, [{ id: 3, task_id: 12, status: "accordee" }]), null);
  assert.equal(pendingFor({ ...view, task_id: null }, [{ id: 4, task_id: null, status: "en_attente" }]), null);
  assert.equal(pendingFor({ ...view, detail: {} }, confs), null);   // pas de question : rien à valider
});
