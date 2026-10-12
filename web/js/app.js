// JARVIS — interface principale : navigation, rail d'activité, état du noyau, voix, raccourcis.
import { get, patch, post, stream } from "./api.js";
import { $, btn, clear, confirmCard, el, handleError, hhmm, icon, status, toast } from "./ui.js";
import { Core } from "./core.js";
import { Voice } from "./voice.js";

export const NAV = [
  { g: null, items: [["accueil", "Accueil", "home"], ["conversation", "Conversation", "chat"], ["vocal", "Mode vocal", "mic"]] },
  { g: "Travail", items: [["taches", "Tâches", "tasks"], ["projets", "Projets", "folder"], ["fichiers", "Fichiers", "files"], ["documents", "Documents", "doc"],
    ["navigateur", "Navigateur", "globe"], ["recherche", "Recherche", "search"], ["automatisations", "Automatisations", "bolt"], ["memoire", "Mémoire", "brain"]] },
  { g: "Temps et messages", items: [["agenda", "Agenda", "calendar"], ["rappels", "Rappels", "bell"], ["emails", "E-mails", "mail"]] },
  { g: "Agence", items: [["prospection", "Prospection", "target"], ["sites", "Création de sites", "layout"]] },
  { g: "Système", items: [["applications", "Applications connectées", "plug"], ["notifications", "Notifications", "inbox"], ["historique", "Historique", "history"],
    ["diagnostic", "Diagnostic", "pulse"], ["securite", "Sécurité", "shield"], ["parametres", "Paramètres", "gear"], ["modeles", "Modèles IA", "chip"]] },
];
const TITLES = Object.fromEntries(NAV.flatMap((g) => g.items.map(([id, l]) => [id, l])));
const VIEWS = {
  accueil: "home", conversation: "chat", vocal: "vocal", taches: "tasks", projets: "projects", fichiers: "files", documents: "documents",
  navigateur: "web", recherche: "search", automatisations: "automations", memoire: "memory", agenda: "agenda", rappels: "reminders",
  emails: "email", prospection: "agency", sites: "sites", applications: "connectors", notifications: "notifications", historique: "history",
  diagnostic: "diagnostic", securite: "security", parametres: "settings", modeles: "models",
};

export const app = {
  state: null, listeners: new Set(), core: null, mini: null, voice: null, currentConv: null, transient: null,
  on(fn) { this.listeners.add(fn); return () => this.listeners.delete(fn); },
  emit(ev) { for (const fn of this.listeners) { try { fn(ev); } catch (e) { console.error(e); } } },
  go(hash) { location.hash = hash; },
  setCore(state, transient = false) {
    for (const c of [this.core, this.mini]) c?.set(state);
    const lab = { attente: "Prêt", ecoute: "Écoute active", transcription: "Transcription en cours", reflexion: "Réflexion", outil: "Utilise un outil",
      tache: "Tâche en cours", parle: "JARVIS parle", autorisation: "Attend votre accord", erreur: "Erreur", termine: "Terminé",
      hors_ligne: "Service indisponible" }[state];
    const b = $("#core-badge"); b.textContent = lab;
    b.className = "badge " + ({ autorisation: "wait", erreur: "err", hors_ligne: "err", attente: "plain", termine: "plain" }[state] || "ok");
    clearTimeout(this.transient);
    if (transient) this.transient = setTimeout(() => this.syncCore(), 2600);
    this.emit({ type: "core", state, label: lab });
  },
  syncCore() {
    if (this.offline) return this.setCore("hors_ligne");
    if (this.voice?.listening) return this.setCore(this.voice.interim ? "transcription" : "ecoute");
    if (this.voice?.speaking || this.state?.core?.speaking) return this.setCore("parle");
    const s = this.state?.core?.state || "attente";
    this.setCore(s);
  },
};

function renderNav() {
  const nav = clear($("#nav"));
  for (const g of NAV) {
    const box = el("div", { class: g.g ? "nav-group" : "" }, g.g ? el("span", {}, g.g) : null);
    for (const [id, label, ic] of g.items) box.append(el("a", { href: `#/${id}`, "data-id": id }, icon(ic), el("span", {}, label), el("span", { class: "count", "data-count": id })));
    nav.append(box);
  }
}

function markNav(id) {
  for (const a of document.querySelectorAll(".nav a")) { if (a.dataset.id === id) a.setAttribute("aria-current", "page"); else a.removeAttribute("aria-current"); }
}

let cleanupView = null;
async function route() {
  const [, id = "accueil", ...rest] = (location.hash || "#/accueil").split("/");
  const viewId = VIEWS[id] ? id : "accueil";
  markNav(viewId);
  $("#sidebar").classList.remove("open");
  $("#page-title").textContent = TITLES[viewId];
  $("#page-sub").textContent = "";
  $("#shell").classList.toggle("no-rail", viewId === "conversation");
  cleanupView?.(); cleanupView = null;
  const view = clear($("#view"));
  try {
    const mod = await import(`./views/${VIEWS[viewId]}.js`);
    cleanupView = (await mod.render(view, rest, app)) || null;
  } catch (e) {
    view.append(el("div", { class: "page" }, el("div", { class: "error-box" }, `Cette page n'a pas pu s'afficher : ${e.message}`)));
    console.error(e);
  }
  view.focus?.();
}

// ----- Rail d'activité (tâches en cours, accords, événements, connexions, raccourcis) -----
let railTimer = null;
async function renderRail() {
  const rail = $("#rail");
  let tasks = [], confs = [], events = [];
  try {
    [tasks, confs, events] = await Promise.all([get("/api/tasks?status=ouvertes"), get("/api/confirmations"), get("/api/journal?limit=14")]);
  } catch (e) { return; }
  clear(rail);
  if (confs.length) rail.append(el("section", {}, el("h2", {}, icon("shield"), "À valider ", el("span", { class: "n" }, confs.length)),
    ...confs.slice(0, 3).map((c) => confirmCard(c, () => { renderRail(); refreshState(); }, true))));
  const running = tasks.filter((t) => ["en_cours", "attente_autorisation", "pause", "interrompue", "en_attente", "attente_reponse"].includes(t.status) && t.kind !== "todo");
  rail.append(el("section", {}, el("h2", {}, icon("tasks"), "Tâches actives ", el("span", { class: "n" }, running.length)),
    running.length ? el("div", { class: "list" }, ...running.slice(0, 6).map((t) => el("div", { class: "row click", onclick: () => app.go(`#/taches/${t.id}`) },
      el("span", { class: "dot " + (t.status === "en_cours" ? "ok" : "wait") }), el("div", { class: "main-col" }, el("div", { class: "t small" }, t.title)), status(t.status))))
      : el("div", { class: "empty" }, "Aucune tâche en cours.")));
  rail.append(el("section", {}, el("h2", {}, icon("history"), "Derniers événements"),
    el("div", { class: "events" }, ...events.map((e) => el("div", { class: "event " + e.level }, el("time", {}, hhmm(e.ts)), el("div", { class: "m" }, e.message))))));
  const conns = app.state?.connectors || [];
  rail.append(el("section", {}, el("h2", {}, icon("plug"), "Connexions"),
    el("div", { class: "events" }, ...conns.slice(0, 8).map((c) => el("div", { class: "mode-chip small" }, el("span", { class: "dot " + (c.connected ? "ok" : "") }),
      el("span", { class: c.connected ? "" : "faint" }, c.label), el("span", { class: "sr-only" }, c.connected ? "connecté" : "non connecté"))))));
  rail.append(el("section", {}, el("h2", {}, icon("bolt"), "Raccourcis"),
    el("div", { class: "shortcuts", style: { justifyContent: "flex-start", marginTop: 0 } },
      ...[["Planning de demain", "Prépare mon planning de demain à partir de mes tâches."], ["Bilan du jour", "Fais le bilan de ma journée : tâches terminées, en retard, priorités."],
        ["Diagnostic", "Vérifie l'état de tous tes composants."]].map(([l, p]) => el("button", { type: "button", onclick: () => quickAsk(p) }, l)))));
}
function scheduleRail() { clearTimeout(railTimer); railTimer = setTimeout(renderRail, 350); }

export async function quickAsk(text) {
  try {
    const r = await post("/api/chat", { text, conversation_id: null });
    app.currentConv = r.conversation_id;
    app.go(`#/conversation/${r.conversation_id}`);
  } catch (e) { handleError(e); }
}

async function refreshState() {
  try {
    app.state = await get("/api/state");
  } catch (e) {
    $("#prov-label").textContent = "Service local injoignable";
    $("#prov-dot").className = "dot err";
    app.offline = true;
    app.setCore("hors_ligne");
    return;
  }
  app.offline = false;
  app.voice?.applySettings(app.state.settings?.voice);
  const s = app.state;
  $("#ver").textContent = "v" + s.version;
  $("#prov-label").textContent = s.provider ? (s.provider.available ? s.provider.label : `${s.provider.label} indisponible`) : "Aucun fournisseur IA";
  $("#prov-dot").className = "dot " + (s.provider?.available ? "ok" : "err");
  $("#mode-label").textContent = "Mode " + s.mode.replace("_", " ");
  const set = (id, n) => { const c = document.querySelector(`[data-count="${id}"]`); if (c) c.textContent = n ? String(n) : ""; };
  set("taches", s.tasks_open); set("notifications", s.notifications_unread); set("securite", s.core.pending_confirmations);
  document.documentElement.dataset.motion = s.settings?.appearance?.animations || "normales";
  app.core?.setMotion(s.settings.appearance.animations); app.mini?.setMotion(s.settings.appearance.animations);
  if (!app.transient) app.syncCore();
  app.emit({ type: "state", state: s });
}

function onEvent(ev) {
  if (ev.type === "voice") { if (app.voice) app.voice.speaking = !!ev.speaking; app.syncCore(); }
  if (ev.type === "activity") {
    const map = { reflexion: "reflexion", outil: "outil", autorisation: "autorisation", erreur: "erreur", termine: "termine" };
    if (map[ev.state]) app.setCore(map[ev.state], ev.state === "termine" || ev.state === "erreur");
    if (ev.state === "calme") { clearTimeout(app._calm); app._calm = setTimeout(() => refreshState(), 400); }
  }
  if (ev.type === "notification" && ev.notification.priority === "haute") toast(ev.notification.title + (ev.notification.body ? " — " + ev.notification.body : ""), ev.notification.kind === "erreur" ? "err" : "wait");
  if (["task", "confirmation", "event", "notification"].includes(ev.type)) scheduleRail();
  if (["task", "confirmation", "notification"].includes(ev.type)) { clearTimeout(app._st); app._st = setTimeout(refreshState, 300); }
  app.emit(ev);
}

async function stopAll() {
  app.voice?.stopListening();
  try { await post("/api/voice/stop"); } catch { /* ignore */ }
  const running = app.state?.core?.running || [];
  for (const id of running) { try { await post(`/api/tasks/${id}/cancel`); } catch (e) { /* déjà finie */ } }
  toast(running.length ? `Interruption : ${running.length} tâche(s) arrêtée(s).` : "Rien en cours : voix et micro coupés.");
  refreshState();
}

function shortcuts() {
  document.addEventListener("keydown", (e) => {
    const typing = /INPUT|TEXTAREA|SELECT/.test(document.activeElement?.tagName);
    if (e.key === "Escape" && !document.querySelector(".overlay")) { if (app.voice?.listening || app.state?.core?.running?.length || app.state?.core?.speaking) stopAll(); }
    if (e.key === "/" && !typing) { e.preventDefault(); const i = document.querySelector("#composer-input"); if (i) i.focus(); else app.go("#/conversation"); }
    if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") { e.preventDefault(); app.go("#/recherche"); }
    if (e.altKey && e.code === "Space") { e.preventDefault(); app.voice?.toggle(); }
  });
}

function boot() {
  renderNav();
  $("#menu-btn").append(icon("menu"));
  $("#menu-btn").addEventListener("click", () => $("#sidebar").classList.toggle("open"));
  $("#stop-all").addEventListener("click", stopAll);
  $("#mic-stop").addEventListener("click", async () => {
    // Couper le micro coupe TOUTE écoute : demande en cours, mains libres et mot d'activation.
    const v = app.voice; if (!v) return;
    v.stopListening();
    if (v.handsFree || v.wakeActive) {
      try { await patch("/api/settings", { voice: { hands_free: false, wake_word: { enabled: false } } }); } catch (e) { handleError(e); }
      v.applySettings({ ...(app.state?.settings?.voice || {}), hands_free: false, wake_word: { enabled: false } });
      toast("Micro coupé : mains libres et mot d'activation désactivés.");
    }
  });
  app.mini = new Core($("#mini-core"), { mini: true });
  app.voice = new Voice(app);
  shortcuts();
  stream(onEvent, (ok) => { if (!ok) { $("#prov-dot").className = "dot wait"; } else refreshState(); });
  addEventListener("hashchange", route);
  refreshState().then(() => { route(); renderRail(); });
  setInterval(refreshState, 15000);
  setInterval(renderRail, 30000);
}
boot();
