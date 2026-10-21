// Tableau de Nova : section titrée, cartes horizontales (une carte active se développe), vue détaillée à deux
// panneaux et écran de succès. Le contenu vient uniquement des vues envoyées par le service (outil nova_afficher) ;
// tout est construit avec textContent (jamais de HTML venant des données : un e-mail peut contenir n'importe quoi).

const SVG = "http://www.w3.org/2000/svg";
const ICONS = {
  rappel: "M12 7v5l3 2M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18z",
  email: "M4 6h16v12H4zM4 7l8 6 8-6",
  document: "M7 3h7l4 4v14H7zM14 3v4h4M9.5 12h5M9.5 16h5",
  appel: "M5 4h4l2 5-2.5 1.5a11 11 0 0 0 5 5L15 13l5 2v4a2 2 0 0 1-2 2A16 16 0 0 1 3 6a2 2 0 0 1 2-2z",
  tache: "M5 12.5l4.5 4.5L19 7.5",
  agenda: "M4 6h16v14H4zM4 10h16M8 3v5M16 3v5",
  check: "M5 12.5l4.5 4.5L19 7.5",
};

const AVATARS = ["var(--nova-av-1)", "var(--nova-av-2)", "var(--nova-av-3)", "var(--nova-av-4)"];

// Couleur d'avatar stable pour un nom (1 à 4), sans donnée inventée : seulement une teinte.
export function avatarIndex(name) {
  let h = 0; for (const c of String(name || "")) h = (h * 31 + c.codePointAt(0)) >>> 0;
  return (h % 4) + 1;
}

// Quelle vue afficher : la vue demandée, ou le détail ouvert localement depuis la carte qui le porte.
export function resolveKind(view, localDetail) {
  if (!view) return "accueil";
  if (view.vue === "succes") return "succes";
  if (view.vue === "detail" || (localDetail && view.detail)) return "detail";
  return "liste";
}

// La question de validation n'est active que si le moteur attend réellement UNE confirmation pour la tâche qui a
// affiché la vue. Plusieurs confirmations en attente pour cette tâche : ambigu, rien n'est validable ici (console).
export function pendingFor(view, confirmations) {
  if (!view?.detail?.validation || view.task_id == null) return null;
  const mine = (confirmations || []).filter((c) => c.status === "en_attente" && c.task_id === view.task_id);
  return mine.length === 1 ? mine[0] : null;
}

// Ce que le moteur va réellement exécuter, décrit par le serveur (jamais par le texte du modèle).
export function actionLabel(c) {
  if (!c) return "";
  return [c.action || c.tool, c.target && !String(c.action || "").includes(c.target) ? c.target : null].filter(Boolean).join(" · ");
}

function el(tag, cls, text) {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (text != null) n.textContent = text;
  return n;
}
function icon(name) {
  const s = document.createElementNS(SVG, "svg"); s.setAttribute("viewBox", "0 0 24 24"); s.setAttribute("aria-hidden", "true");
  const p = document.createElementNS(SVG, "path"); p.setAttribute("d", ICONS[name] || ICONS.tache); s.append(p); return s;
}

export class Board {
  constructor(root, { onApprove, onChange } = {}) {
    Object.assign(this, { root, onApprove, onChange });
    this.view = null; this.kind = "accueil"; this.selected = null; this.localDetail = false;
    this.pending = null; this.awaiting = null; this.done = null;
  }

  get visible() { return this.kind !== "accueil"; }
  get canApprove() { return this.kind === "detail" && !!this.pending && !this.awaiting; }

  show(view) {
    const sameList = view && this.view && view.vue === "liste" && this.kind === "liste" && !this.localDetail &&
      view.titre === this.view.titre && view.elements.map((e) => e.id).join() === this.view.elements.map((e) => e.id).join();
    this.view = view; this.done = null; this.awaiting = null;
    if (view?.vue !== "detail") this.localDetail = false;
    if (sameList) { this.select(view.selection || null, { keep: true }); return; }
    this.selected = view?.selection || null;
    this.render();
  }

  clear() { this.view = null; this.localDetail = false; this.done = null; this.render(); }

  // Retour : détail → liste ; liste → accueil.
  back() {
    if (this.kind === "detail" && this.view?.vue !== "detail") { this.localDetail = false; this.render(); return true; }
    if (this.visible) { this.clear(); return true; }
    return false;
  }

  select(id, { keep = false } = {}) {
    if (!this.view || this.kind !== "liste") return;
    const card = id && this.root.querySelector(`.nova-card[data-id="${CSS.escape(id)}"]`);
    // Une carte active qui porte le détail l'ouvre au second toucher.
    if (!keep && id && id === this.selected && this.view.detail?.element === id) { this.localDetail = true; this.render(); return; }
    this.selected = card ? id : null;
    for (const c of this.root.querySelectorAll(".nova-card")) {
      const on = c.dataset.id === this.selected;
      c.classList.toggle("on", on); c.setAttribute("aria-expanded", String(on));
    }
    this.root.querySelector(".nova-list")?.classList.toggle("has-on", !!this.selected);
  }

  setConfirmations(list) {
    this.pending = pendingFor(this.view, list);
    this.syncValidate();
  }

  approve() {
    if (!this.canApprove) return false;
    this.awaiting = { confirmation: this.pending.id, task: this.pending.task_id };
    this.syncValidate();
    this.onApprove?.(this.pending.id);
    return true;
  }

  // Fin réelle de la tâche validée : succès seulement si le moteur l'a terminée.
  taskFinished(taskId, ok) {
    if (!this.awaiting || this.awaiting.task !== taskId) return;
    const v = this.view?.detail?.validation || {}; this.awaiting = null;
    if (ok) { this.done = { titre: v.succes, detail: v.succes_detail }; this.render(); }
    else this.syncValidate();
  }

  // Le bouton peut être en cours d'insertion (transition) : on garde une référence directe.
  syncValidate() {
    const btn = this.validateBtn;
    if (!btn) return;
    btn.disabled = !this.canApprove;
    btn.classList.toggle("ready", this.canApprove);
    btn.classList.toggle("sending", !!this.awaiting);
    const real = btn.querySelector(".real");
    if (real) real.textContent = this.pending ? `Action réelle : ${actionLabel(this.pending)}` : "";
  }

  approveFailed() { this.awaiting = null; this.setConfirmations([]); }

  // -- rendu ------------------------------------------------------------------------------------------------
  render() {
    this.kind = this.done ? "succes" : resolveKind(this.view, this.localDetail);
    this.validateBtn = null;
    const old = [...this.root.children];
    for (const o of old) { o.classList.add("leaving"); setTimeout(() => o.remove(), 300); }
    this.onChange?.(this.kind);
    if (this.kind === "accueil") return;
    const wrap = el("div", "nova-view");
    wrap.append(this.head());
    if (this.kind === "liste") wrap.append(this.list());
    else if (this.kind === "detail") wrap.append(this.detail());
    else wrap.append(this.success());
    // la nouvelle vue entre pendant que l'ancienne s'efface
    setTimeout(() => this.root.append(wrap), old.length ? 180 : 0);
  }

  head() {
    const h = el("header", "nova-head");
    h.append(el("h2", null, this.view.titre), el("span", "rule"));
    if (this.view.meta) h.append(el("span", "meta", this.view.meta));
    return h;
  }

  list() {
    const box = el("div", "nova-list");
    this.view.elements.forEach((it, i) => box.append(this.card(it, i)));
    box.classList.toggle("has-on", !!this.selected);
    return box;
  }

  card(it, i) {
    const on = it.id === this.selected;
    const c = el("div", "nova-card" + (on ? " on" : ""));
    c.dataset.id = it.id; c.style.setProperty("--i", i); c.tabIndex = 0; c.setAttribute("role", "button");
    c.setAttribute("aria-expanded", String(on));
    const row = el("div", "row");
    const av = el("span", "av", [...String(it.nom)][0]?.toUpperCase()); av.setAttribute("aria-hidden", "true"); av.style.setProperty("--av", AVATARS[avatarIndex(it.nom) - 1]);
    const txt = el("div", "txt");
    const l1 = el("div", "l1"); l1.append(el("b", null, it.nom)); if (it.contexte) l1.append(document.createTextNode(` · ${it.contexte}`));
    txt.append(l1); if (it.resume) txt.append(el("div", "l2", it.resume));
    row.append(av, txt);
    if (it.badge) { const b = el("span", "nova-badge", it.badge.texte); b.dataset.ton = it.badge.ton; row.append(b); } else row.append(el("span"));
    const more = el("div", "more"); const inner = el("div", "more-in");
    if (it.details) inner.append(el("p", "details", it.details));
    if (it.action) {
      const a = el("div", "nova-act"); const ic = el("span", "ic"); ic.append(icon(it.action.icone));
      const t = el("div"); t.append(el("div", "lab", it.action.label), el("div", "val", it.action.texte));
      a.append(ic, t); inner.append(a);
    }
    if (it.source && (it.source.type || it.source.date)) inner.append(el("div", "nova-src", ["Source", it.source.type, it.source.date].filter(Boolean).join(" · ")));
    more.append(inner); c.append(row, more);
    const pick = (e) => { e.stopPropagation(); this.select(it.id); };
    c.addEventListener("click", pick);
    c.addEventListener("keydown", (e) => { if (e.key === "Enter") pick(e); });
    return c;
  }

  detail() {
    const d = this.view.detail; const box = el("div", "nova-detail");
    const left = el("article", "nova-panel prop");
    if (d.gauche.surtitre) left.append(el("div", "nova-k over", d.gauche.surtitre));
    for (const s of d.gauche.sections) {
      const sec = el("div", "nova-sec"); sec.append(el("div", "nova-k", s.titre));
      if (s.texte) sec.append(el("p", null, s.texte));
      if (s.puces.length) { const ul = el("ul"); for (const p of s.puces) ul.append(el("li", null, p)); sec.append(ul); }
      left.append(sec);
    }
    if (d.gauche.total) { const t = el("div", "nova-total"); t.append(el("span", "nova-k", d.gauche.total.label), el("span", "v", d.gauche.total.valeur)); left.append(t); }
    const right = el("div", "nova-right");
    const mail = el("article", "nova-panel nova-mail");
    if (d.droite.a || d.droite.sujet) {
      const hdr = el("div", "hdr");
      if (d.droite.a) hdr.append(el("span", "nova-k", "À"), el("span", null, d.droite.a));
      if (d.droite.sujet) hdr.append(el("span", "nova-k", "Sujet"), el("span", null, d.droite.sujet));
      mail.append(hdr);
    }
    if (d.droite.corps) mail.append(el("div", "body", d.droite.corps));
    if (d.droite.piece) {
      const pj = el("div", "nova-pj"); pj.append(el("span", "ic", "PDF"), el("span", "n", d.droite.piece.nom), el("span", "i", d.droite.piece.info || ""));
      mail.append(pj);
    }
    right.append(mail);
    if (d.validation) {
      const b = el("button", "nova-validate"); b.type = "button";
      const q = el("span", "q"); q.append(el("span", null, d.validation.question), el("span", "real"));
      b.append(el("span", "dot"), q, el("span", "kbd", "ESPACE ↵"));
      this.validateBtn = b; this.syncValidate();
      b.addEventListener("click", (e) => { e.stopPropagation(); this.approve(); });
      right.append(b);
    }
    box.append(left, right);
    box.addEventListener("click", (e) => e.stopPropagation());
    return box;
  }

  success() {
    const s = this.done || this.view.succes || { titre: "C'est fait" };
    const box = el("div", "nova-done");
    const ck = el("span", "check"); ck.append(icon("check"));
    box.append(ck, el("h3", null, s.titre));
    if (s.detail) box.append(el("p", null, s.detail));
    return box;
  }
}
