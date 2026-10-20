// Rappels : création, liste, échéances. Notification macOS à l'échéance tant que Nova est ouvert.
import { get, post } from "../api.js";
import { btn, el, empty, errorBox, field, input, toast } from "../ui.js";

export async function render(view, params, app) {
  const title = input({ placeholder: "Ex. Rappeler le restaurant Da Marco" });
  const due = input({ type: "datetime-local" });
  const body = el("div");
  view.append(el("div", { class: "page narrow" },
    el("div", { class: "panel" }, el("div", { class: "form-row" }, field("Rappel", title), field("Échéance", due)),
      el("div", { style: { marginTop: "12px" } }, btn("Ajouter le rappel", async () => { await post("/api/reminders", { title: title.value, due_at: due.value }); title.value = ""; toast("Rappel enregistré."); load(); }, { cls: "primary" }))),
    el("p", { class: "small faint" }, "La notification s'affiche si Nova est ouvert à l'échéance (vérification toutes les 20 secondes). Nova ne démarre pas automatiquement avec le Mac."),
    body));
  async function load() {
    let rs; try { rs = await get("/api/reminders?all=1"); } catch (e) { return body.replaceChildren(errorBox(e)); }
    if (!rs.length) return body.replaceChildren(empty("Aucun rappel.", "Ajoutez-en un, ou dites « rappelle-moi de… » à Nova."));
    const now = new Date().toISOString().slice(0, 16);
    body.replaceChildren(el("div", { class: "list" }, ...rs.map((r) => el("div", { class: "row" },
      el("span", { class: "badge " + (r.done ? "plain" : r.due_at < now ? "wait" : "ok") }, r.done ? "fait" : r.due_at < now ? "échu" : "à venir"),
      el("div", { class: "main-col" }, el("div", { class: "t small" }, r.title), el("div", { class: "d xs" }, r.due_at.replace("T", " ") + (r.notified ? " – notifié" : ""))),
      r.done ? el("span", {}) : btn("Fait", async () => { await post(`/api/reminders/${r.id}/done`); load(); }, { cls: "sm ghost", icon: "check" })))));
  }
  await load();
}
