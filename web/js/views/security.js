// Sécurité : mode et permissions effectives, demandes d'accord en attente, dossiers autorisés, commandes autorisées,
// zones protégées, secrets (trousseau), outils et niveaux de risque.
import { get, patch } from "../api.js";
import { btn, confirmCard, el, errorBox, field, handleError, input, loading, modal, select, toast } from "../ui.js";

export async function render(view, params, app) {
  const page = el("div", { class: "page" }, loading());
  view.append(page);
  async function load() {
    let s, confs, tools, secrets;
    try { [s, confs, tools, secrets] = await Promise.all([get("/api/settings"), get("/api/confirmations"), get("/api/tools"), get("/api/secrets")]); } catch (e) { return page.replaceChildren(errorBox(e)); }
    const perm = s.permissions;
    const modeSel = select(Object.entries(s.modes).map(([k]) => [k, k.replace("_", " ")]), perm.mode);
    modeSel.addEventListener("change", async () => { try { await patch("/api/settings", { autonomy: { mode: modeSel.value } }); } catch (e) { handleError(e); modeSel.value = perm.mode; setTimeout(load, 800); } });
    page.replaceChildren(
      confs.length ? [el("h3", { style: { marginTop: 0 } }, `Demandes d'accord en attente (${confs.length})`), ...confs.map((c) => el("div", { style: { marginBottom: "10px" } }, confirmCard(c, load)))] : null,
      el("div", { class: "grid-2" },
        el("div", { class: "panel" }, el("h3", { style: { marginTop: 0 } }, "Mode de fonctionnement"), field("Mode actif", modeSel),
          el("p", { class: "small muted" }, s.modes[perm.mode]),
          el("dl", { class: "kv", style: { marginTop: "10px" } }, el("dt", {}, "Sans confirmation"), el("dd", {}, perm.sans_confirmation.join(", ") || "rien"),
            el("dt", {}, "Avec confirmation"), el("dd", {}, perm.avec_confirmation.join(", ") || "—"), el("dt", {}, "Interdit"), el("dd", {}, perm.interdits.join(", ") || "—")),
          el("p", { class: "small faint" }, "Changer de mode demande votre confirmation et n'accorde aucun autre droit (dossiers, commandes et connecteurs restent inchangés).")),
        el("div", { class: "panel" }, el("h3", { style: { marginTop: 0 } }, "Secrets (trousseau macOS)"),
          el("p", { class: "small muted" }, "Les clés et jetons sont stockés dans le trousseau, jamais dans la base, les journaux, les conversations ou les sauvegardes. Nova n'en affiche jamais la valeur."),
          el("div", { class: "list" }, ...secrets.map((x) => el("div", { class: "row" }, el("span", { class: "badge " + (x.present ? "ok" : "plain") }, x.present ? "enregistré" : "absent"), el("div", { class: "main-col small" }, x.label),
            btn(x.present ? "Remplacer" : "Ajouter", () => {
              const v = input({ type: "password", autocomplete: "off" });
              modal(x.label, field("Valeur (stockée dans le trousseau)", v), ["close", (c) => btn("Enregistrer", async () => { await (await import("../api.js")).post("/api/secrets", { name: x.name, value: v.value }); c(); toast("Secret enregistré dans le trousseau."); load(); }, { cls: "primary" })]);
            }, { cls: "sm ghost" })))))),
      el("h3", {}, "Dossiers autorisés"),
      el("table", { class: "table" }, el("tbody", {}, ...s.settings.allowed_dirs.map((d, i) => el("tr", {}, el("td", { class: "mono" }, d.path), el("td", {}, el("span", { class: "badge " + (d.mode === "rw" ? "wait" : "plain") }, d.mode === "rw" ? "lecture et écriture" : "lecture seule")), el("td", { class: "small" }, d.label || ""),
        el("td", {}, btn("Retirer", async () => { try { await patch("/api/settings", { allowed_dirs: s.settings.allowed_dirs.filter((_, j) => j !== i) }); } catch (e) { handleError(e); setTimeout(load, 800); } }, { cls: "sm ghost" })))))),
      btn("Ajouter un dossier", () => {
        const p = input({ placeholder: "/Users/sachaaissani/Documents/Clients" }), m = select([["r", "Lecture seule"], ["rw", "Lecture et écriture"]], "r"), l = input({ placeholder: "Libellé" });
        modal("Autoriser un dossier", el("div", { class: "form" }, field("Chemin absolu", p), field("Accès", m), field("Libellé", l)),
          ["close", (c) => btn("Demander l'autorisation", async () => { c(); try { await patch("/api/settings", { allowed_dirs: [...s.settings.allowed_dirs, { path: p.value, mode: m.value, label: l.value }] }); } catch (e) { handleError(e); setTimeout(load, 800); } }, { cls: "primary" })]);
      }, { cls: "sm", icon: "plus" }),
      el("h3", {}, "Zones toujours protégées"),
      el("p", { class: "small muted" }, "Jamais accessibles : ", el("span", { class: "mono" }, perm.zones_interdites.join("  "))),
      el("p", { class: "small muted" }, "Jamais modifiables par l'agent : ", el("span", { class: "mono" }, perm.zones_protegees_ecriture.join("  "))),
      el("h3", {}, "Commandes autorisées"),
      el("p", { class: "small muted" }, "Sans shell ; opérateurs |, ;, &&, >, $() refusés ; commandes dangereuses (rm, sudo, curl, chmod, osascript, launchctl…) toujours bloquées ; opérations Git ou d'installation sensibles soumises à confirmation."),
      el("p", { class: "mono" }, s.settings.shell.allowed_commands.join("  ")),
      el("h3", {}, `Outils (${tools.length})`),
      el("table", { class: "table" }, el("thead", {}, el("tr", {}, ...["Outil", "Risque", "Disponible", "Vérification", "Délai"].map((h) => el("th", {}, h)))),
        el("tbody", {}, ...tools.map((t) => el("tr", {}, el("td", {}, el("span", { class: "mono" }, t.id), el("div", { class: "faint xs" }, t.description)),
          el("td", {}, el("span", { class: "badge " + ({ faible: "plain", modere: "wait", eleve: "err" }[t.risk] || "plain") }, t.risk)),
          el("td", {}, t.available ? el("span", { class: "badge ok" }, "oui") : el("span", { class: "badge plain", title: t.unavailable_reason }, "non")),
          el("td", { class: "small muted" }, t.verification), el("td", { class: "small faint" }, `${t.timeout_s} s`))))));
  }
  await load();
}
