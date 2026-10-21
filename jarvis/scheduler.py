"""Automatisations et planificateur (parties 18 et 19).

Un fil d'exécution vérifie toutes les 20 s : automatisations dues, rappels échus,
tâches en attente de dépendances, rétention du journal. Les automatisations sont
persistées en base (elles survivent au redémarrage de JARVIS ; elles ne tournent
que lorsque JARVIS est ouvert). Aucune ne contourne les permissions : leurs
actions passent par le registre d'outils et le moteur d'agent.
"""
from __future__ import annotations

import datetime as dt
import fnmatch
import os
import threading
import time
import traceback
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

from .db import dumps, loads, now
from .errors import JarvisError, NotFound, ValidationError
from .tools.registry import ToolContext

TRIGGERS = {"intervalle": "Toutes les N minutes", "quotidien": "Chaque jour à une heure donnée", "date": "Une fois, à une date",
            "dossier": "Fichier ajouté dans un dossier autorisé", "evenement": "Événement interne (ex. fin de tâche)",
            "manuel": "Lancement manuel uniquement"}
ACTIONS = {"bilan_quotidien": "Préparer le bilan du jour (tâches, retards, rappels)",
           "taches_en_retard": "Analyser les tâches en retard et notifier",
           "etat_projets": "Vérifier l'état des projets (blocages)",
           "tests_projet": "Exécuter les tests d'un projet",
           "liens_site": "Vérifier les liens d'un site",
           "rapport_hebdo": "Produire le rapport hebdomadaire",
           "agent": "Confier un objectif à un agent (permissions et confirmations inchangées)"}


def _tz(a) -> ZoneInfo:
    try:
        return ZoneInfo(a.get("timezone") or "Europe/Paris")
    except Exception:  # noqa: BLE001
        return ZoneInfo("Europe/Paris")


def compute_next(trigger: Dict[str, Any], tzname: str, after: Optional[dt.datetime] = None) -> Optional[str]:
    tz = ZoneInfo(tzname or "Europe/Paris")
    base = after or dt.datetime.now(tz)
    t = trigger.get("type")
    if t == "intervalle":
        m = int(trigger.get("minutes", 60))
        return (base + dt.timedelta(minutes=max(1, m))).isoformat(timespec="seconds")
    if t == "quotidien":
        hh, mm = map(int, str(trigger.get("heure", "08:00")).split(":"))
        days = trigger.get("jours") or [1, 2, 3, 4, 5, 6, 7]
        cand = base.replace(hour=hh, minute=mm, second=0, microsecond=0)
        if cand <= base:
            cand += dt.timedelta(days=1)
        for _ in range(8):
            if cand.isoweekday() in days:
                return cand.isoformat(timespec="seconds")
            cand += dt.timedelta(days=1)
        return None
    if t == "date":
        q = dt.datetime.fromisoformat(trigger["quand"])
        if q.tzinfo is None:
            q = q.replace(tzinfo=tz)
        return q.isoformat(timespec="seconds") if q > base else None
    if t == "dossier":
        return (base + dt.timedelta(minutes=1)).isoformat(timespec="seconds")
    if t == "evenement":
        return (base + dt.timedelta(seconds=30)).isoformat(timespec="seconds")
    return None


def validate(trigger: Dict[str, Any], action: Dict[str, Any], app) -> None:
    if trigger.get("type") not in TRIGGERS:
        raise ValidationError("Déclencheur inconnu.", {"declencheurs": TRIGGERS})
    if action.get("type") not in ACTIONS:
        raise ValidationError("Action inconnue.", {"actions": ACTIONS})
    if trigger["type"] == "intervalle" and int(trigger.get("minutes", 0)) < 5:
        raise ValidationError("Intervalle minimum : 5 minutes (évite les boucles).")
    if trigger["type"] == "quotidien":
        try:
            hh, mm = map(int, str(trigger.get("heure", "")).split(":"))
            assert 0 <= hh < 24 and 0 <= mm < 60
        except Exception:  # noqa: BLE001
            raise ValidationError("Heure invalide (HH:MM).")
    if trigger["type"] == "dossier":
        app.permissions.resolve_path(trigger.get("path", ""))
    if trigger["type"] == "evenement" and trigger.get("kind") not in ("tache_fin", "outil_erreur", "autorisation_demandee"):
        raise ValidationError("Événement : tache_fin, outil_erreur ou autorisation_demandee.")
    if action["type"] == "agent" and not (action.get("objectif") or "").strip():
        raise ValidationError("Objectif de l'agent requis.")
    if action["type"] == "tests_projet":
        app.permissions.resolve_path(action.get("dir", ""), write=True)


class Scheduler:
    def __init__(self, app):
        self.app = app
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._running: Dict[int, threading.Thread] = {}
        self.last_tick: Optional[str] = None
        self._last_purge = 0.0

    # -- CRUD ----------------------------------------------------------------------------
    def create(self, name: str, trigger: Dict[str, Any], action: Dict[str, Any], conditions: Optional[Dict[str, Any]] = None,
               enabled: bool = False, timezone: str = "Europe/Paris", max_seconds: int = 300, max_retries: int = 1,
               on_error: str = "notifier", stop_after_failures: int = 3) -> Dict[str, Any]:
        validate(trigger, action, self.app)
        aid = self.app.db.insert(
            "INSERT INTO automations(name, enabled, trigger, conditions, action, timezone, max_seconds, max_retries, on_error, "
            "stop_after_failures, next_run, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (name[:120], 1 if enabled else 0, dumps(trigger), dumps(conditions or {}), dumps(action), timezone, max_seconds,
             max_retries, on_error, stop_after_failures, compute_next(trigger, timezone), now()))
        self.app.logbook.log("automatisation", f"Automatisation « {name} » créée ({'active' if enabled else 'désactivée'})", "info")
        return self.get(aid)

    def get(self, aid: int) -> Dict[str, Any]:
        r = self.app.db.one("SELECT * FROM automations WHERE id=?", (aid,))
        if not r:
            raise NotFound("Automatisation introuvable.")
        for k in ("trigger", "conditions", "action", "state"):
            r[k] = loads(r[k], {})
        return r

    def list(self) -> List[Dict[str, Any]]:
        out = []
        for r in self.app.db.all("SELECT id FROM automations ORDER BY id"):
            a = self.get(r["id"])
            a["runs"] = self.app.db.all("SELECT * FROM automation_runs WHERE automation_id=? ORDER BY id DESC LIMIT 5", (a["id"],))
            out.append(a)
        return out

    def set_enabled(self, aid: int, enabled: bool) -> Dict[str, Any]:
        a = self.get(aid)
        self.app.db.execute("UPDATE automations SET enabled=?, fail_streak=0, next_run=? WHERE id=?",
                            (1 if enabled else 0, compute_next(a["trigger"], a["timezone"]), aid))
        self.app.logbook.log("automatisation", f"« {a['name']} » {'activée' if enabled else 'désactivée'}", "info")
        return self.get(aid)

    def delete(self, aid: int) -> None:
        self.get(aid)
        self.app.db.execute("DELETE FROM automations WHERE id=?", (aid,))

    # -- boucle ----------------------------------------------------------------------------
    def recover(self) -> int:
        """Reprise après incident : une exécution restée « en_cours » appartient à un service arrêté brutalement.
        Elle est marquée interrompue (jamais relancée en double) ; la prochaine échéance s'exécutera normalement."""
        rows = self.app.db.all("SELECT r.id, a.name FROM automation_runs r JOIN automations a ON a.id=r.automation_id WHERE r.status='en_cours'")
        for r in rows:
            self.app.db.execute("UPDATE automation_runs SET status='interrompue', finished_at=?, error=? WHERE id=?",
                                (now(), "service arrêté pendant l'exécution", r["id"]))
            self.app.logbook.log("automatisation", f"« {r['name']} » interrompue par un arrêt du service", "attention")
        return len(rows)

    def start(self) -> None:
        self.recover()
        self._thread = threading.Thread(target=self._loop, daemon=True, name="planificateur")
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def alive(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                self.tick()
            except Exception as e:  # noqa: BLE001
                self.app.logbook.log("planificateur", f"Erreur du planificateur : {e}", "erreur", data={"trace": traceback.format_exc()[-800:]})
            self._stop.wait(20)

    def tick(self) -> None:
        self.last_tick = now()
        app = self.app
        for r in app.reminders.due():
            app.db.execute("UPDATE reminders SET notified=1 WHERE id=?", (r["id"],))
            app.notify("rappel", "Rappel", r["title"])
            app.logbook.log("rappel", f"Rappel échu : {r['title']}", "attention")
        app.tasks.start_ready_dependents()
        app.memory.purge_expired()
        app.tasks.notify_due()
        if time.time() - self._last_purge > 86400:
            self._last_purge = time.time()
            n = app.logbook.purge_older_than(app.settings.get("retention.events_days", 180))
            if n:
                app.logbook.log("retention", f"{n} anciens événements supprimés (politique de rétention)", "info")
        nowd = dt.datetime.now(ZoneInfo("Europe/Paris"))
        for a in app.db.all("SELECT id, next_run FROM automations WHERE enabled=1"):
            if a["id"] in self._running and self._running[a["id"]].is_alive():
                continue
            if a["next_run"] and dt.datetime.fromisoformat(a["next_run"]) <= nowd:
                self.run_async(a["id"], "planifie")

    def run_async(self, aid: int, origin: str = "manuel") -> int:
        th = threading.Thread(target=self.run, args=(aid, origin), daemon=True, name=f"auto-{aid}")
        self._running[aid] = th
        th.start()
        return aid

    def _conditions_ok(self, a: Dict[str, Any]) -> Optional[str]:
        c = a["conditions"] or {}
        if c.get("jours_ouvres") and dt.datetime.now(_tz(a)).isoweekday() > 5:
            return "week-end"
        if c.get("si_taches_en_retard"):
            today = dt.date.today().isoformat()
            n = self.app.db.one("SELECT count(*) AS n FROM tasks WHERE due_date < ? AND status NOT IN ('terminee','annulee')", (today,))["n"]
            if not n:
                return "aucune tâche en retard"
        return None

    def _trigger_fired(self, a: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Pour les déclencheurs « dossier » et « événement » : y a-t-il du nouveau ?"""
        t, st = a["trigger"], dict(a["state"] or {})
        if t["type"] == "dossier":
            root = self.app.permissions.resolve_path(t["path"])
            files = sorted(f for f in os.listdir(root) if fnmatch.fnmatch(f, t.get("pattern", "*")) and not f.startswith("."))
            seen = set(st.get("seen", []))
            new = [f for f in files if f not in seen]
            st["seen"] = files[-2000:]
            first = "seen" not in (a["state"] or {})
            self.app.db.execute("UPDATE automations SET state=? WHERE id=?", (dumps(st), a["id"]))
            return None if first or not new else {"nouveaux_fichiers": new}
        if t["type"] == "evenement":
            last = st.get("last_event_id") or self.app.db.one("SELECT coalesce(max(id),0) AS m FROM events")["m"]
            rows = self.app.db.all("SELECT id, message FROM events WHERE id>? AND kind=? ORDER BY id LIMIT 20", (last, t["kind"]))
            st["last_event_id"] = rows[-1]["id"] if rows else last
            self.app.db.execute("UPDATE automations SET state=? WHERE id=?", (dumps(st), a["id"]))
            return {"evenements": [r["message"] for r in rows]} if rows else None
        return {}

    def run(self, aid: int, origin: str = "manuel") -> Dict[str, Any]:
        app = self.app
        a = self.get(aid)
        nxt = compute_next(a["trigger"], a["timezone"])
        app.db.execute("UPDATE automations SET next_run=? WHERE id=?", (nxt, aid))
        payload: Optional[Dict[str, Any]] = {}
        if origin != "manuel":
            skip = self._conditions_ok(a)
            if skip:
                return {"skipped": skip}
            payload = self._trigger_fired(a)
            if payload is None:
                return {"skipped": "rien de nouveau"}
        rid = app.db.insert("INSERT INTO automation_runs(automation_id, started_at, status) VALUES (?,?,?)", (aid, now(), "en_cours"))
        app.logbook.log("automatisation", f"Exécution de « {a['name']} » ({origin})", "info")
        attempts, last_err, output = 0, None, None
        while attempts <= a["max_retries"]:
            attempts += 1
            try:
                output = self._execute(a, payload or {})
                last_err = None
                break
            except Exception as e:  # noqa: BLE001
                last_err = e
                time.sleep(min(10, 2 * attempts))
        if last_err is None:
            app.db.execute("UPDATE automation_runs SET finished_at=?, status='succes', output=? WHERE id=?", (now(), dumps(output)[:20000], rid))
            app.db.execute("UPDATE automations SET last_run=?, run_count=run_count+1, fail_streak=0 WHERE id=?", (now(), aid))
            app.logbook.log("automatisation", f"« {a['name']} » terminée", "succes")
            return {"ok": True, "output": output}
        msg = last_err.message if isinstance(last_err, JarvisError) else str(last_err)
        app.db.execute("UPDATE automation_runs SET finished_at=?, status='echec', error=? WHERE id=?", (now(), msg, rid))
        app.db.execute("UPDATE automations SET last_run=?, run_count=run_count+1, fail_streak=fail_streak+1 WHERE id=?", (now(), aid))
        a = self.get(aid)
        app.logbook.log("automatisation", f"« {a['name']} » en échec : {msg}", "erreur")
        app.notify("automatisation_echec", "Automatisation en échec", f"{a['name']} : {msg}")
        if a["fail_streak"] >= a["stop_after_failures"]:
            self.set_enabled(aid, False)
            app.notify("automatisation_echec", "Automatisation désactivée", f"{a['name']} : {a['fail_streak']} échecs consécutifs")
        return {"ok": False, "error": msg}

    def _execute(self, a: Dict[str, Any], payload: Dict[str, Any]) -> Dict[str, Any]:
        app = self.app
        act = a["action"]
        ctx = ToolContext(app, None, None, threading.Event(), app.permissions.mode(), "general")
        typ = act["type"]
        if typ in ("bilan_quotidien", "rapport_hebdo"):
            return self._report(ctx, weekly=typ == "rapport_hebdo")
        if typ == "taches_en_retard":
            today = dt.date.today().isoformat()
            rows = app.db.all("SELECT id, title, due_date FROM tasks WHERE due_date < ? AND status NOT IN ('terminee','annulee')", (today,))
            if rows:
                app.notify("projet_bloque", f"{len(rows)} tâche(s) en retard", ", ".join(r["title"] for r in rows[:5]))
            return {"en_retard": rows}
        if typ == "etat_projets":
            blocked = [p for p in app.projects.list() if p["tasks_blocked"]]
            if blocked:
                app.notify("projet_bloque", "Projet(s) bloqué(s)", ", ".join(p["name"] for p in blocked))
            return {"projets_bloques": [p["name"] for p in blocked]}
        if typ == "tests_projet":
            return app.tools.invoke("tests_lancer", {"project_dir": act["dir"]}, ctx)
        if typ == "liens_site":
            return app.tools.invoke("web_verifier_liens", {"url": act["url"]}, ctx)
        if typ == "agent":
            obj = act["objectif"] + (f"\n\nDonnées du déclencheur : {dumps(payload)}" if payload else "")
            t = app.tasks.create(obj, f"[auto] {a['name']}", "automatisation", act.get("agent", "general"))
            return {"task_id": t["id"]}
        raise ValidationError("Action inconnue.")

    def _report(self, ctx, weekly: bool) -> Dict[str, Any]:
        app = self.app
        today = dt.date.today()
        since = (today - dt.timedelta(days=7 if weekly else 1)).isoformat()
        done = app.db.all("SELECT title, finished_at FROM tasks WHERE status='terminee' AND finished_at >= ? AND kind!='conversation'", (since,))
        open_ = app.tasks.list("ouvertes", limit=100)
        late = [t for t in open_ if t.get("due_date") and t["due_date"] < today.isoformat()]
        rem = [r for r in app.reminders.list() if r["due_at"][:10] <= (today + dt.timedelta(days=1)).isoformat()]
        usage = app.db.one("SELECT count(*) AS n FROM ai_usage WHERE ts >= ?", (since,))["n"]
        lines = [f"## {'Semaine' if weekly else 'Journée'} du {since} au {today.isoformat()}", "",
                 f"- Tâches terminées : {len(done)}", f"- Tâches ouvertes : {len(open_)} (dont {len(late)} en retard)",
                 f"- Rappels à venir (48 h) : {len(rem)}", f"- Appels IA : {usage}", "", "### Terminé"]
        lines += [f"- {t['title']}" for t in done[:30]] or ["- rien"]
        lines += ["", "### En retard"] + ([f"- {t['title']} (échéance {t['due_date']})" for t in late] or ["- aucune"])
        lines += ["", "### Priorités suggérées"] + [f"{i + 1}. {t['title']}" for i, t in enumerate(sorted(open_, key=lambda t: (-t['priority'], t['id']))[:3])]
        title = "Rapport hebdomadaire" if weekly else "Bilan quotidien"
        res = app.tools.invoke("rapport_produire", {"title": title, "content": "\n".join(lines)}, ctx)
        app.notify("tache_terminee", f"{title} prêt", res["result"]["path"])
        return {"path": res["result"]["path"], "state": res["state"]}

    def defaults(self) -> None:
        """Crée les automatisations d'exemple (désactivées) au premier démarrage."""
        if self.app.db.one("SELECT count(*) AS n FROM automations")["n"]:
            return
        self.create("Bilan quotidien", {"type": "quotidien", "heure": "18:30", "jours": [1, 2, 3, 4, 5]}, {"type": "bilan_quotidien"})
        self.create("Tâches en retard", {"type": "quotidien", "heure": "09:00"}, {"type": "taches_en_retard"}, {"si_taches_en_retard": True})
        self.create("Rapport hebdomadaire", {"type": "quotidien", "heure": "17:00", "jours": [5]}, {"type": "rapport_hebdo"})
        self.create("État des projets", {"type": "quotidien", "heure": "09:05", "jours": [1]}, {"type": "etat_projets"})
