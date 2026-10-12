// Petits outils d'interface : création d'éléments, icônes, Markdown sûr, toasts, modales, statuts.
import { post } from "./api.js";

// replaceChildren accepte ici des tableaux imbriqués et ignore null / undefined / false (comme el()).
const _replace = Element.prototype.replaceChildren;
Element.prototype.replaceChildren = function (...c) {
  return _replace.apply(this, c.flat(Infinity).filter((x) => x !== null && x !== undefined && x !== false));
};

export function el(tag, attrs = {}, ...children) {
  const n = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v === undefined || v === null || v === false) continue;
    if (k === "class") n.className = v;
    else if (k === "html") n.innerHTML = v;            // réservé au Markdown déjà échappé
    else if (k.startsWith("on")) n.addEventListener(k.slice(2), v);
    else if (k === "style" && typeof v === "object") Object.assign(n.style, v);
    else n.setAttribute(k, v === true ? "" : v);
  }
  for (const c of children.flat(Infinity)) {
    if (c === null || c === undefined || c === false) continue;
    n.append(c instanceof Node ? c : document.createTextNode(String(c)));
  }
  return n;
}

export const $ = (s, root = document) => root.querySelector(s);
export const clear = (n) => { while (n.firstChild) n.removeChild(n.firstChild); return n; };

// Icônes (trait 1,5 px, 24×24) — un seul jeu cohérent.
const P = {
  home: "M3 10.5 12 3l9 7.5V20a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z",
  chat: "M4 5h16v11H8l-4 4z",
  mic: "M12 3a3 3 0 0 1 3 3v6a3 3 0 0 1-6 0V6a3 3 0 0 1 3-3zM5 11a7 7 0 0 0 14 0M12 18v3",
  tasks: "M9 6h11M9 12h11M9 18h11M4 6l1 1 2-2M4 12l1 1 2-2M4 18l1 1 2-2",
  folder: "M3 6a1 1 0 0 1 1-1h5l2 2h9a1 1 0 0 1 1 1v10a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1z",
  files: "M7 3h7l5 5v13H7zM14 3v5h5",
  globe: "M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18zM3 12h18M12 3c2.5 2.6 3.8 5.6 3.8 9s-1.3 6.4-3.8 9c-2.5-2.6-3.8-5.6-3.8-9S9.5 5.6 12 3z",
  search: "M11 4a7 7 0 1 0 0 14 7 7 0 0 0 0-14zM20 20l-4-4",
  bolt: "M13 3 5 13h6l-1 8 8-10h-6z",
  brain: "M9 4a3 3 0 0 0-3 3 3 3 0 0 0-2 5 3 3 0 0 0 2 5 3 3 0 0 0 6 1V5a3 3 0 0 0-3-1zM15 4a3 3 0 0 1 3 3 3 3 0 0 1 2 5 3 3 0 0 1-2 5 3 3 0 0 1-6 1",
  calendar: "M4 6h16v14H4zM4 10h16M8 3v4M16 3v4",
  bell: "M6 16V11a6 6 0 1 1 12 0v5l2 2H4zM10 20a2 2 0 0 0 4 0",
  mail: "M3 6h18v12H3zM3 7l9 6 9-6",
  target: "M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18zM12 7a5 5 0 1 0 0 10 5 5 0 0 0 0-10zM12 11a1 1 0 1 0 0 2 1 1 0 0 0 0-2z",
  layout: "M3 4h18v16H3zM3 9h18M9 9v11",
  doc: "M6 3h9l4 4v14H6zM9 12h7M9 16h7M9 8h3",
  plug: "M9 3v5M15 3v5M7 8h10v4a5 5 0 0 1-10 0zM12 17v4",
  inbox: "M4 13l2-8h12l2 8v6H4zM4 13h5l1 2h4l1-2h5",
  history: "M3 12a9 9 0 1 0 3-6.7M3 4v4h4M12 7v5l3 2",
  pulse: "M3 12h4l2-6 4 12 2-6h6",
  shield: "M12 3 5 6v6c0 4.5 3 7.5 7 9 4-1.5 7-4.5 7-9V6z",
  gear: "M12 9a3 3 0 1 0 0 6 3 3 0 0 0 0-6zM19.4 15a1.6 1.6 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.6 1.6 0 0 0-2.7 1.1V21a2 2 0 1 1-4 0v-.1a1.6 1.6 0 0 0-2.7-1.1l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1A1.6 1.6 0 0 0 3.6 15H3a2 2 0 1 1 0-4h.1a1.6 1.6 0 0 0 1.1-2.7l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1A1.6 1.6 0 0 0 9.7 4.4V4a2 2 0 1 1 4 0v.1a1.6 1.6 0 0 0 2.7 1.1l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.6 1.6 0 0 0 1.1 2.7H21a2 2 0 1 1 0 4z",
  chip: "M8 8h8v8H8zM5 5h14v14H5zM9 2v3M15 2v3M9 19v3M15 19v3M2 9h3M2 15h3M19 9h3M19 15h3",
  send: "M4 12 20 4l-6 16-3-7z",
  stop: "M7 7h10v10H7z",
  plus: "M12 5v14M5 12h14",
  x: "M6 6l12 12M18 6 6 18",
  check: "M5 12l5 5 9-10",
  menu: "M4 7h16M4 12h16M4 17h16",
  play: "M8 5v14l11-7z",
  pause: "M8 5v14M16 5v14",
  trash: "M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13",
  download: "M12 4v12M7 11l5 5 5-5M5 20h14",
  speaker: "M4 9h4l5-4v14l-5-4H4zM16 9a4 4 0 0 1 0 6M19 6a8 8 0 0 1 0 12",
  external: "M14 4h6v6M20 4l-9 9M18 14v6H4V6h6",
  edit: "M4 20h4L19 9l-4-4L4 16zM14 6l4 4",
  archive: "M3 5h18v4H3zM5 9v11h14V9M10 13h4",
  refresh: "M20 11a8 8 0 1 0-2.3 5.7M20 4v7h-7",
};
export function icon(name, size) {
  const s = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  s.setAttribute("viewBox", "0 0 24 24"); s.setAttribute("fill", "none"); s.setAttribute("stroke", "currentColor");
  s.setAttribute("stroke-width", "1.5"); s.setAttribute("stroke-linecap", "round"); s.setAttribute("stroke-linejoin", "round");
  s.setAttribute("aria-hidden", "true");
  if (size) { s.style.width = size + "px"; s.style.height = size + "px"; }
  const p = document.createElementNS("http://www.w3.org/2000/svg", "path");
  p.setAttribute("d", P[name] || P.doc); s.append(p); return s;
}

export function btn(label, onclick, opts = {}) {
  const b = el("button", { class: "btn " + (opts.cls || ""), type: "button", title: opts.title, "aria-label": opts.aria || (opts.iconOnly ? label : undefined), disabled: opts.disabled },
    opts.icon ? icon(opts.icon) : null, opts.iconOnly ? null : label);
  b.addEventListener("click", async (e) => {
    if (b.classList.contains("busy")) return;
    b.classList.add("busy");
    try { await onclick?.(e); } catch (err) { handleError(err, () => onclick?.(e)); } finally { b.classList.remove("busy"); }
  });
  return b;
}

// Markdown sûr : tout est échappé avant mise en forme.
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
export function md(src) {
  const lines = String(src ?? "").replace(/\r\n/g, "\n").split("\n");
  const out = []; let list = null, code = false, table = [];
  const inline = (t) => esc(t)
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
    .replace(/(^|[^*])\*([^*\s][^*]*)\*/g, "$1<em>$2</em>")
    .replace(/\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>')
    .replace(/(^|\s)(https?:\/\/[^\s<]+)/g, '$1<a href="$2" target="_blank" rel="noopener noreferrer">$2</a>');
  const flushTable = () => {
    if (!table.length) return;
    const rows = table.filter((r) => !/^\|?\s*:?-{2,}/.test(r.trim().replace(/^\|/, "")));
    const cells = rows.map((r) => r.trim().replace(/^\||\|$/g, "").split("|").map((c) => c.trim()));
    out.push("<table><thead><tr>" + cells[0].map((c) => `<th>${inline(c)}</th>`).join("") + "</tr></thead><tbody>" +
      cells.slice(1).map((r) => "<tr>" + r.map((c) => `<td>${inline(c)}</td>`).join("") + "</tr>").join("") + "</tbody></table>");
    table = [];
  };
  for (const line of lines) {
    if (line.startsWith("```")) { if (list) { out.push(`</${list}>`); list = null; } out.push(code ? "</code></pre>" : "<pre><code>"); code = !code; continue; }
    if (code) { out.push(esc(line) + "\n"); continue; }
    if (line.trim().startsWith("|")) { table.push(line); continue; }
    flushTable();
    const h = line.match(/^(#{1,4})\s+(.*)/);
    const li = line.match(/^\s*([-*]|\d+[.)])\s+(?:\[( |x)\]\s+)?(.*)/);
    if (li) {
      const kind = /\d/.test(li[1]) ? "ol" : "ul";
      if (list !== kind) { if (list) out.push(`</${list}>`); out.push(`<${kind}>`); list = kind; }
      out.push(`<li>${li[2] === "x" ? "☑ " : li[2] === " " ? "☐ " : ""}${inline(li[3])}</li>`); continue;
    }
    if (list) { out.push(`</${list}>`); list = null; }
    if (h) out.push(`<h${h[1].length + 1}>${inline(h[2])}</h${h[1].length + 1}>`);
    else if (line.trim()) out.push(`<p>${inline(line)}</p>`);
  }
  flushTable(); if (list) out.push(`</${list}>`); if (code) out.push("</code></pre>");
  return el("div", { class: "md", html: out.join("") });
}

export function toast(msg, kind = "") {
  const t = el("div", { class: "toast " + kind, role: kind === "err" ? "alert" : "status" }, msg);
  $("#toasts").append(t);
  setTimeout(() => t.remove(), kind === "err" ? 7000 : 3800);
}

export function handleError(err, retry) {
  if (err?.code === "confirmation_requise") {
    confirmationModal(err.details, retry);
    return;
  }
  toast(err?.message || String(err), "err");
  console.error(err);
}

export function modal(title, body, actions = [], wide = false) {
  const close = () => ov.remove();
  const ov = el("div", { class: "overlay", onclick: (e) => { if (e.target === ov) close(); } },
    el("div", { class: "modal" + (wide ? " wide" : ""), role: "dialog", "aria-modal": "true", "aria-label": title },
      el("h2", {}, title), body,
      el("div", { class: "foot" }, ...actions.map((a) => a === "close" ? btn("Fermer", close, { cls: "ghost" }) : a(close)))));
  document.body.append(ov);
  const onKey = (e) => { if (e.key === "Escape") { close(); document.removeEventListener("keydown", onKey); } };
  document.addEventListener("keydown", onKey);
  setTimeout(() => ov.querySelector("input,textarea,select,button.primary")?.focus(), 30);
  return close;
}

// Carte de confirmation : action, cible, conséquences, données, réversibilité, résultat attendu.
export function confirmCard(c, onDone, compact = false) {
  const card = el("div", { class: "confirm" + (compact ? " compact" : ""), role: "group", "aria-label": "Confirmation requise" },
    el("div", { class: "h" }, icon("shield"), "Confirmation requise", el("span", { class: "badge rare" }, `risque ${c.risk || "élevé"}`)),
    el("dl", {},
      el("dt", {}, "Action"), el("dd", {}, c.action || c.tool),
      c.target ? [el("dt", {}, "Cible"), el("dd", {}, c.target)] : null,
      c.consequences ? [el("dt", {}, "Conséquences"), el("dd", {}, c.consequences)] : null,
      c.data_concerned || c.data ? [el("dt", {}, "Données"), el("dd", {}, c.data_concerned || c.data)] : null,
      [el("dt", {}, "Réversible"), el("dd", {}, c.reversible ? "oui" : "non")],
      c.expected ? [el("dt", {}, "Résultat attendu"), el("dd", {}, c.expected)] : null,
      c.args && !compact ? [el("dt", {}, "Paramètres"), el("dd", { class: "mono" }, JSON.stringify(c.args).slice(0, 400))] : null),
    el("div", { class: "btns" },
      btn("Autoriser cette action", async () => { await post(`/api/confirmations/${c.id || c.confirmation_id}`, { approve: true }); toast("Action autorisée."); onDone?.(true); }, { cls: "primary", icon: "check" }),
      btn("Refuser", async () => { await post(`/api/confirmations/${c.id || c.confirmation_id}`, { approve: false }); toast("Action refusée."); onDone?.(false); }, { cls: "ghost" })));
  return card;
}

export function confirmationModal(details, retry) {
  let close;
  const card = confirmCard({ ...details, id: details.confirmation_id }, async (ok) => {
    close();
    // Action lancée depuis l'interface : une fois autorisée, elle est relancée (la confirmation est à usage unique).
    if (ok && retry && !details.patch) { try { await retry(); } catch (e) { handleError(e); } }
  });
  close = modal("Autoriser ?", card, ["close"]);
}

const STATUS = {
  terminee: ["ok", "Terminée"], en_cours: ["ok", "En cours"], en_attente: ["plain", "En attente"], pause: ["wait", "En pause"],
  attente_autorisation: ["wait", "Attend votre accord"], attente_reponse: ["wait", "Attend votre réponse"], echouee: ["err", "Échouée"],
  bloquee: ["err", "Bloquée"], annulee: ["plain", "Annulée"], interrompue: ["wait", "Interrompue"],
  confirme: ["ok", "Confirmé"], partiel: ["wait", "Partiel"], probable: ["plain", "Probable"], non_verifie: ["wait", "Non vérifié"], bloque: ["err", "Bloqué"], echoue: ["err", "Échoué"],
  sans_objet: ["plain", "Réponse directe"],
  actif: ["ok", "Actif"], idee: ["plain", "Idée"], en_pause: ["wait", "En pause"], termine: ["ok", "Terminé"], archive: ["plain", "Archivé"],
  valide: ["ok", "Valide"], obsolete: ["plain", "Obsolète"], a_verifier: ["wait", "À vérifier"],
  succes: ["ok", "Succès"], echec: ["err", "Échec"],
};
export function status(s) {
  const [cls, label] = STATUS[s] || ["plain", s || "—"];
  return el("span", { class: "badge " + cls }, label);
}

export function when(ts) {
  if (!ts) return "";
  const d = new Date(ts.replace(/([+-]\d\d)(\d\d)$/, "$1:$2"));
  if (isNaN(d)) return ts;
  const now = new Date(); const diff = (now - d) / 1000;
  if (diff < 60) return "à l'instant";
  if (diff < 3600) return `il y a ${Math.floor(diff / 60)} min`;
  if (d.toDateString() === now.toDateString()) return d.toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" });
  return d.toLocaleDateString("fr-FR", { day: "numeric", month: "short" }) + " " + d.toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" });
}
export const hhmm = (ts) => (ts || "").slice(11, 16);

export function empty(title, text, action) {
  return el("div", { class: "empty-state" }, el("b", {}, title), el("span", {}, text), action ? el("div", { style: { marginTop: "14px" } }, action) : null);
}
export const loading = (t = "Chargement…") => el("div", { class: "loading" }, t);
export const errorBox = (e) => el("div", { class: "error-box", role: "alert" }, e?.message || String(e));

export function field(label, input) { return el("label", { class: "field" }, label, input); }
export function input(attrs = {}) { return el("input", { class: "input", ...attrs }); }
export function textarea(attrs = {}) { const t = el("textarea", { class: "textarea", ...attrs }); if (attrs.value) t.value = attrs.value; return t; }
export function select(options, value, attrs = {}) {
  const s = el("select", { class: "select", ...attrs }, ...options.map((o) => {
    const [v, l] = Array.isArray(o) ? o : [o, o];
    return el("option", { value: v, selected: String(v) === String(value) }, l);
  }));
  return s;
}
export function toggle(label, checked, onchange) {
  const i = el("input", { type: "checkbox", role: "switch" }); i.checked = !!checked;
  i.addEventListener("change", () => onchange(i.checked, i));
  return el("label", { class: "switch" }, i, label);
}
export function download(name, text, type = "text/markdown") {
  const a = el("a", { href: URL.createObjectURL(new Blob([text], { type })), download: name });
  document.body.append(a); a.click(); a.remove();
}
