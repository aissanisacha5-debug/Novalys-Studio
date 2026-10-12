// Conversation : conversations multiples, historique, recherche, renommage, archivage, export, suppression,
// messages en Markdown, étapes réelles de l'agent, confirmations en ligne.
import { del, get, patch, post } from "../api.js";
import { btn, clear, confirmCard, download, el, empty, errorBox, handleError, icon, input, md, modal, status, toast, when } from "../ui.js";

const STEP_CLS = { termine: "ok", echec: "err", attente_autorisation: "wait", refuse: "err", ignore: "", en_cours: "", annule: "err" };

export function composer(app, onSend, { placeholder = "Demandez quelque chose à JARVIS…" } = {}) {
  const ta = el("textarea", { id: "composer-input", rows: 1, placeholder, "aria-label": "Message pour JARVIS" });
  const grow = () => { ta.style.height = "auto"; ta.style.height = Math.min(220, ta.scrollHeight) + "px"; };
  ta.addEventListener("input", grow);
  const send = async () => {
    const text = ta.value.trim(); if (!text) return;
    ta.value = ""; grow();
    try { await onSend(text); } catch (e) { ta.value = text; handleError(e); }
  };
  ta.addEventListener("keydown", (e) => { if (e.key === "Enter" && !e.shiftKey && !e.isComposing) { e.preventDefault(); send(); } });
  const mic = el("button", { class: "btn icon mic", type: "button", "data-mic": "", "aria-pressed": String(!!app.voice?.listening), "aria-label": "Parler (Alt+Espace)", title: "Parler (Alt+Espace)" }, icon("mic"));
  mic.addEventListener("click", () => app.voice.toggle());
  if (app.voice?.listening) mic.classList.add("on");
  const sendBtn = el("button", { class: "btn primary icon", type: "button", "aria-label": "Envoyer", title: "Envoyer" }, icon("send"));
  sendBtn.addEventListener("click", send);
  const box = el("div", { class: "composer" },
    el("div", { class: "composer-box" }, ta, mic, sendBtn),
    el("div", { class: "hint" }, el("span", {}, "Entrée pour envoyer, Maj+Entrée pour aller à la ligne"), el("span", {}, "Alt+Espace pour parler"), el("span", {}, "Échap pour interrompre")));
  return { box, ta };
}

function stepLine(s) {
  const res = s.result || {};
  const state = res.state ? status(res.state) : null;
  return el("div", { class: "step " + (STEP_CLS[s.status] || "") },
    el("span", { class: "k" }, s.tool), state, el("span", {}, s.status === "termine" ? (res.verification || "") : (s.error || s.status)),
    res.result ? el("details", { class: "tool-out" }, el("summary", {}, "résultat"), el("pre", {}, JSON.stringify(res.result, null, 2).slice(0, 6000))) : null);
}

export async function render(view, params, app) {
  let convId = params[0] ? Number(params[0]) : app.currentConv;
  let showArchived = false, query = "";
  const list = el("div", { class: "conv-list" });
  const inner = el("div", { class: "messages-inner" });
  const msgs = el("div", { class: "messages", "aria-live": "polite" }, inner);
  const { box } = composer(app, async (text) => {
    const r = await post("/api/chat", { text, conversation_id: convId || null });
    if (!convId) { convId = r.conversation_id; app.currentConv = convId; history.replaceState(null, "", `#/conversation/${convId}`); loadList(); }
    await loadMessages();
  });
  view.append(el("div", { class: "chat" }, list, el("div", { class: "chat-main" }, msgs, box)));

  async function loadList() {
    let convs = [];
    try { convs = await get(`/api/conversations?archived=${showArchived ? 1 : 0}&q=${encodeURIComponent(query)}`); } catch (e) { return list.replaceChildren(errorBox(e)); }
    const search = input({ placeholder: "Rechercher…", value: query, "aria-label": "Rechercher une conversation" });
    search.addEventListener("change", () => { query = search.value; loadList(); });
    clear(list).append(
      el("div", { style: { display: "flex", gap: "6px", marginBottom: "8px" } },
        btn("Nouvelle", () => { convId = null; app.currentConv = null; history.replaceState(null, "", "#/conversation"); loadMessages(); loadList(); }, { cls: "sm primary", icon: "plus" }),
        btn(showArchived ? "Actives" : "Archives", () => { showArchived = !showArchived; loadList(); }, { cls: "sm ghost", icon: "archive" })),
      el("div", { style: { marginBottom: "8px" } }, search),
      ...(convs.length ? convs.map((c) => el("div", { class: "row click", "aria-current": String(c.id === convId), tabindex: 0,
        onclick: () => { convId = c.id; app.currentConv = c.id; history.replaceState(null, "", `#/conversation/${c.id}`); loadMessages(); loadList(); },
        onkeydown: (e) => { if (e.key === "Enter") e.currentTarget.click(); } },
        el("div", { class: "main-col" }, el("div", { class: "t small" }, c.title), el("div", { class: "d xs" }, (c.project_name ? c.project_name + " – " : "") + when(c.updated_at))),
        el("span", { class: "faint xs" }, c.n))) : [el("div", { class: "faint small" }, showArchived ? "Aucune archive." : "Aucune conversation.")]));
  }

  async function loadMessages() {
    if (!convId) {
      document.querySelector("#page-sub").textContent = "Nouvelle conversation";
      return clear(inner).append(empty("Que puis-je faire pour vous ?", "Une question, un site à créer, des fichiers à organiser, une recherche à mener : écrivez ou parlez."));
    }
    let c;
    try { c = await get(`/api/conversations/${convId}`); } catch (e) { return clear(inner).append(errorBox(e)); }
    const prov = app.state?.provider;
    const sub = document.querySelector("#page-sub"); clear(sub).append(c.title + " ",
      prov ? el("span", { class: "badge " + (prov.available ? "plain" : "err"), title: "Le texte de la conversation est envoyé à ce fournisseur pour générer les réponses." },
        `${prov.label}${prov.available ? "" : " — indisponible"}`) : null, " ",
      btn("Renommer", async () => {
        const i = input({ value: c.title });
        modal("Renommer la conversation", i, ["close", (close) => btn("Enregistrer", async () => { await patch(`/api/conversations/${c.id}`, { title: i.value }); close(); loadMessages(); loadList(); }, { cls: "primary" })]);
      }, { cls: "sm ghost", icon: "edit" }),
      btn(c.archived ? "Désarchiver" : "Archiver", async () => { await patch(`/api/conversations/${c.id}`, { archived: !c.archived }); toast(c.archived ? "Conversation restaurée." : "Conversation archivée."); loadList(); }, { cls: "sm ghost", icon: "archive" }),
      btn("Exporter", async () => { const r = await get(`/api/conversations/${c.id}/export`); download(`conversation-${c.id}.md`, r.markdown); }, { cls: "sm ghost", icon: "download" }),
      btn("Supprimer", async () => {
        modal("Supprimer cette conversation ?", el("p", { class: "muted" }, "Les messages seront définitivement supprimés. Les tâches et la mémoire restent."),
          ["close", (close) => btn("Supprimer définitivement", async () => { await del(`/api/conversations/${c.id}`); close(); convId = null; app.currentConv = null; loadMessages(); loadList(); }, { cls: "danger" })]);
      }, { cls: "sm ghost", icon: "trash" }));
    clear(inner);
    for (const m of c.messages) {
      if (m.role === "user") {
        inner.append(el("div", { class: "msg user" }, el("div", { class: "who" }, m.meta?.source === "voix" ? "Sacha (voix)" : "Sacha", " ", when(m.created_at)), el("div", { class: "body" }, m.content)));
      } else if (m.role === "assistant") {
        const meta = m.meta || {};
        const stepsBox = el("div");
        const line = el("div", { class: "state-line" }, meta.result_state ? status(meta.result_state) : null, meta.status && meta.status !== "terminee" ? status(meta.status) : null,
          meta.tools_used ? `${meta.tools_used} action(s) exécutée(s)` : null,
          meta.task_id && meta.tools_used ? btn("Voir les étapes", async () => {
            if (stepsBox.childNodes.length) return clear(stepsBox);
            const t = await get(`/api/tasks/${meta.task_id}`);
            stepsBox.append(el("div", { class: "steps" }, ...t.steps.filter((s) => s.kind === "outil").map(stepLine)));
          }, { cls: "sm ghost" }) : null,
          btn("Lire", () => app.voice.speak(m.content), { cls: "sm ghost", icon: "speaker", title: "Lire à voix haute" }),
          meta.status && ["bloquee", "echouee", "attente_reponse"].includes(meta.status) && meta.task_id ? btn("Reprendre", async () => { await post(`/api/tasks/${meta.task_id}/resume`); loadMessages(); }, { cls: "sm ghost", icon: "play" }) : null);
        inner.append(el("div", { class: "msg assistant" }, el("div", { class: "who" }, "JARVIS ", when(m.created_at)), el("div", { class: "body" }, md(m.content)),
          meta.next_action ? el("div", { class: "small rare" }, "Prochaine action : ", meta.next_action) : null, line, stepsBox));
      }
    }
    if (c.running_task) await showRunning(c.running_task.id);
    msgs.scrollTop = msgs.scrollHeight;
  }

  let live = null;
  async function showRunning(taskId) {
    let t;
    try { t = await get(`/api/tasks/${taskId}`); } catch { return; }
    live?.remove();
    const toolSteps = t.steps.filter((s) => s.kind === "outil");
    const lastModel = [...t.steps].reverse().find((s) => s.kind === "modele" && s.result);
    const pending = t.confirmations.filter((x) => x.status === "en_attente");
    live = el("div", { class: "msg assistant" }, el("div", { class: "who" }, "JARVIS"),
      lastModel?.result?.message && toolSteps.length ? el("div", { class: "body" }, md(lastModel.result.message)) : null,
      lastModel?.result?.plan?.length ? el("div", { class: "small muted" }, el("b", {}, "Plan : "), lastModel.result.plan.join(" ; ")) : null,
      toolSteps.length ? el("div", { class: "steps" }, ...toolSteps.map(stepLine)) : null,
      ...pending.map((p) => confirmCard({ ...p, args: null }, () => setTimeout(loadMessages, 400))),
      t.status === "en_cours" ? el("div", { class: "thinking" }, el("span", { class: "pulse" }), toolSteps.length ? "JARVIS travaille…" : "JARVIS réfléchit…",
        btn("Interrompre", async () => { await post(`/api/tasks/${taskId}/cancel`); }, { cls: "sm ghost", icon: "stop" })) : null,
      t.status === "pause" ? el("div", { class: "thinking" }, "En pause.", btn("Reprendre", async () => { await post(`/api/tasks/${taskId}/resume`); }, { cls: "sm" })) : null);
    inner.append(live);
    msgs.scrollTop = msgs.scrollHeight;
  }

  const off = app.on((ev) => {
    if (ev.type === "message" && ev.conversation_id === convId) loadMessages();
    if ((ev.type === "task" || ev.type === "event" || ev.type === "confirmation") && convId) {
      clearTimeout(view._t); view._t = setTimeout(async () => {
        const c = await get(`/api/conversations/${convId}`).catch(() => null);
        if (c?.running_task) showRunning(c.running_task.id);
      }, 250);
    }
  });
  await Promise.all([loadList(), loadMessages()]);
  document.querySelector("#composer-input")?.focus();
  return () => off();
}
