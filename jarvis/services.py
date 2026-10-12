"""Services macOS natifs : trousseau (secrets), notifications, voix, infos système, applications."""
from __future__ import annotations

import datetime as dt
import os
import re
import shutil
import signal
import subprocess
import threading
from typing import Any, Dict, List, Optional, Tuple

from .db import Database, now
from .errors import JarvisError, ValidationError

KEYCHAIN_SERVICE = "studio.novalys.jarvis"
SECRET_NAMES = {"anthropic_api_key": "Clé API Anthropic", "openai_compatible_key": "Clé du fournisseur compatible OpenAI",
                "github_token": "Jeton GitHub",
                "netlify_token": "Jeton Netlify", "vercel_token": "Jeton Vercel"}


# -- Secrets (trousseau macOS) ----------------------------------------------------
class Secrets:
    """Les secrets vivent dans le trousseau macOS, jamais dans la base, les journaux ou le code."""

    def _ok_name(self, name: str) -> None:
        if name not in SECRET_NAMES:
            raise ValidationError("Nom de secret non prévu.", {"autorises": list(SECRET_NAMES)})

    def has(self, name: str) -> bool:
        if name not in SECRET_NAMES or not shutil.which("security"):
            return False
        r = subprocess.run(["security", "find-generic-password", "-s", KEYCHAIN_SERVICE, "-a", name],
                           capture_output=True, timeout=10)
        return r.returncode == 0

    def get(self, name: str) -> Optional[str]:
        self._ok_name(name)
        r = subprocess.run(["security", "find-generic-password", "-s", KEYCHAIN_SERVICE, "-a", name, "-w"],
                           capture_output=True, timeout=10)
        return r.stdout.decode().strip() if r.returncode == 0 else None

    def set(self, name: str, value: str) -> None:
        self._ok_name(name)
        if not value or len(value) > 4096:
            raise ValidationError("Valeur de secret invalide.")
        r = subprocess.run(["security", "add-generic-password", "-U", "-s", KEYCHAIN_SERVICE, "-a", name, "-w", value],
                           capture_output=True, timeout=10)
        if r.returncode != 0:
            raise JarvisError("Enregistrement dans le trousseau impossible.", code="trousseau")

    def delete(self, name: str) -> None:
        self._ok_name(name)
        subprocess.run(["security", "delete-generic-password", "-s", KEYCHAIN_SERVICE, "-a", name],
                       capture_output=True, timeout=10)

    def status(self) -> List[Dict[str, Any]]:
        return [{"name": k, "label": v, "present": self.has(k)} for k, v in SECRET_NAMES.items()]


# -- Notifications -------------------------------------------------------------------
def _in_quiet_hours(cfg: Dict[str, Any]) -> bool:
    q = cfg.get("quiet_hours") or {}
    if not q.get("enabled"):
        return False
    t = dt.datetime.now().strftime("%H:%M")
    s, e = q.get("start", "22:00"), q.get("end", "08:00")
    return (s <= t or t < e) if s > e else (s <= t < e)


class Notifier:
    PRIORITY = {"erreur": "haute", "confirmation": "haute", "limite": "haute", "automatisation_echec": "haute",
                "projet_bloque": "normale", "integration": "normale", "tache_terminee": "normale", "rappel": "haute"}

    def __init__(self, db: Database, settings, bus):
        self.db = db
        self.settings = settings
        self.bus = bus

    def notify(self, kind: str, title: str, body: str = "") -> Dict[str, Any]:
        cfg = self.settings.get("notifications", {})
        prio = self.PRIORITY.get(kind, "normale")
        delivered = 0
        if cfg.get("enabled", True) and kind in cfg.get("kinds", []) and cfg.get("macos", True) and not _in_quiet_hours(cfg):
            # Contenu masqué par défaut : l'écran verrouillé ne montre qu'un titre générique.
            shown = "Ouvrez JARVIS pour voir le détail." if cfg.get("hide_content", True) else body[:180]
            delivered = 1 if macos_notification(f"JARVIS — {title}", shown) else 0
        nid = self.db.insert("INSERT INTO notifications(ts, kind, priority, title, body, delivered_macos) VALUES (?,?,?,?,?,?)",
                             (now(), kind, prio, title[:200], body[:2000], delivered))
        n = {"id": nid, "kind": kind, "priority": prio, "title": title, "body": body, "delivered_macos": delivered}
        self.bus.publish({"type": "notification", "notification": n})
        return n

    def list(self, unread_only: bool = False, limit: int = 100) -> List[Dict[str, Any]]:
        return self.db.all("SELECT * FROM notifications" + (" WHERE read=0" if unread_only else "") + " ORDER BY id DESC LIMIT ?", (limit,))

    def mark_read(self, nid: Optional[int] = None) -> None:
        if nid is None:
            self.db.execute("UPDATE notifications SET read=1")
        else:
            self.db.execute("UPDATE notifications SET read=1 WHERE id=?", (nid,))


def _as_str(s: str) -> str:
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def macos_notification(title: str, body: str) -> bool:
    if not shutil.which("osascript"):
        return False
    script = f"display notification {_as_str(body)} with title {_as_str(title)}"
    try:
        r = subprocess.run(["osascript", "-e", script], capture_output=True, timeout=10)
        return r.returncode == 0
    except Exception:  # noqa: BLE001
        return False


# -- Voix (synthèse native macOS) ------------------------------------------------------
class Voice:
    def __init__(self, settings, bus):
        self.settings = settings
        self.bus = bus
        self._proc: Optional[subprocess.Popen] = None
        self._lock = threading.RLock()
        self._queue: List[str] = []
        self._worker: Optional[threading.Thread] = None
        self._gen = 0
        self.last_audio_start: Optional[float] = None

    def voices(self) -> List[Dict[str, str]]:
        if not shutil.which("say"):
            return []
        out = subprocess.run(["say", "-v", "?"], capture_output=True, timeout=10).stdout.decode("utf-8", "replace")
        res = []
        for line in out.splitlines():
            m = re.match(r"^(.+?)\s{2,}([a-z]{2}_[A-Z]{2})\s+#", line)
            if m:
                res.append({"name": m.group(1).strip(), "locale": m.group(2)})
        return res

    def devices(self) -> List[str]:
        try:
            out = subprocess.run(["say", "-a", "?"], capture_output=True, timeout=10).stdout.decode("utf-8", "replace")
            return [re.sub(r"^\s*\d+\s+", "", l).strip() for l in out.splitlines() if l.strip()]
        except Exception:  # noqa: BLE001
            return []

    @staticmethod
    def clean(text: str) -> str:
        text = re.sub(r"```.*?```", " (bloc de code non lu) ", text, flags=re.S)
        text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
        text = re.sub(r"https?://\S+", " (lien) ", text)
        return re.sub(r"[#*_`>|]", " ", text)

    def _args(self, text: str) -> List[str]:
        cfg = self.settings.get("voice", {})
        vol = max(0.0, min(1.0, float(cfg.get("volume", 0.8))))
        args = ["say", "-v", cfg.get("voice", "Thomas"), "-r", str(int(cfg.get("rate", 190)))]
        dev = cfg.get("output_device")
        if dev and dev != "defaut":
            args += ["-a", dev]
        return args + [f"[[volm {vol:.2f}]] " + text]

    def speak(self, text: str) -> Dict[str, Any]:
        """Lit un texte complet (remplace toute lecture en cours)."""
        cfg = self.settings.get("voice", {})
        if not shutil.which("say"):
            raise JarvisError("Synthèse vocale macOS indisponible.", code="voix_indisponible")
        text = self.clean(text)
        limit = cfg.get("max_spoken_chars", 600)
        if len(text) > limit:
            text = text[:limit].rsplit(" ", 1)[0] + ". La suite est affichée à l'écran."
        self.stop()
        self.enqueue(text)
        return {"speaking": True, "chars": len(text)}

    # File de segments : la lecture commence dès la première phrase disponible (réponse en flux).
    def enqueue(self, segment: str) -> None:
        segment = self.clean(segment).strip()
        if not segment or not shutil.which("say"):
            return
        with self._lock:
            self._queue.append(segment)
            if not (self._worker and self._worker.is_alive()):
                self._worker = threading.Thread(target=self._play, args=(self._gen,), daemon=True)
                self._worker.start()

    def _play(self, gen: int) -> None:
        started = False
        while True:
            with self._lock:
                if gen != self._gen or not self._queue:
                    self._worker = None
                    break
                seg = self._queue.pop(0)
                self._proc = subprocess.Popen(self._args(seg), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
                p = self._proc
            if not started:
                started = True
                self.last_audio_start = __import__("time").time()
            self.bus.publish({"type": "voice", "speaking": True, "text": seg})
            p.wait()
        if started:
            self.bus.publish({"type": "voice", "speaking": False})

    def speaking(self) -> bool:
        return bool((self._proc and self._proc.poll() is None) or self._queue)

    def stop(self) -> bool:
        with self._lock:
            self._gen += 1
            self._queue.clear()
            p = self._proc
            if p and p.poll() is None:
                try:
                    os.killpg(p.pid, signal.SIGTERM)
                except Exception:  # noqa: BLE001
                    p.terminate()
                self.bus.publish({"type": "voice", "speaking": False})
                return True
        return False


# -- Informations système -----------------------------------------------------------------
def system_info() -> Dict[str, Any]:
    info: Dict[str, Any] = {}
    try:
        load = os.getloadavg()
        ncpu = os.cpu_count() or 1
        info["cpu"] = {"load1": round(load[0], 2), "load5": round(load[1], 2), "cores": ncpu,
                       "percent": min(100, round(100 * load[0] / ncpu))}
    except OSError:
        pass
    try:
        total = int(subprocess.run(["sysctl", "-n", "hw.memsize"], capture_output=True, timeout=5).stdout)
        vm = subprocess.run(["vm_stat"], capture_output=True, timeout=5).stdout.decode()
        page = int(re.search(r"page size of (\d+)", vm).group(1))
        get = lambda k: int(re.search(rf"{k}:\s+(\d+)", vm).group(1)) if re.search(rf"{k}:\s+(\d+)", vm) else 0  # noqa: E731
        used = (get("Pages active") + get("Pages wired down") + get("Pages occupied by compressor")) * page
        info["memory"] = {"total_gb": round(total / 1e9, 1), "used_gb": round(used / 1e9, 1), "percent": round(100 * used / total)}
    except Exception:  # noqa: BLE001
        pass
    du = shutil.disk_usage(os.path.expanduser("~"))
    info["disk"] = {"total_gb": round(du.total / 1e9), "free_gb": round(du.free / 1e9), "percent": round(100 * du.used / du.total)}
    return info


SAFE_APP = re.compile(r"^[\w .\-']{1,60}$")


def list_apps() -> List[str]:
    apps = []
    for d in ("/Applications", "/System/Applications", os.path.expanduser("~/Applications")):
        if os.path.isdir(d):
            apps += [f[:-4] for f in os.listdir(d) if f.endswith(".app")]
    return sorted(set(apps), key=str.lower)


def open_app(name: str) -> Tuple[bool, str]:
    if not SAFE_APP.match(name or ""):
        raise ValidationError("Nom d'application invalide.")
    if name not in list_apps():
        raise ValidationError(f"Application « {name} » introuvable sur ce Mac.")
    r = subprocess.run(["open", "-a", name], capture_output=True, timeout=20)
    return r.returncode == 0, r.stderr.decode()[:200]


def app_running(name: str) -> bool:
    r = subprocess.run(["pgrep", "-xf", f".*{re.escape(name)}.app/Contents/MacOS/.*"], capture_output=True, timeout=5)
    if r.returncode == 0:
        return True
    r = subprocess.run(["pgrep", "-f", f"/{name}.app/"], capture_output=True, timeout=5)
    return r.returncode == 0
