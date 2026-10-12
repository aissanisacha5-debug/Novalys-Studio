"""Application indépendante (prompt 4) : emplacements séparés et migration sans perte, service et démarrage
automatique (plist, sans chargement réel), fournisseurs indépendants et erreurs d'API, limite d'abonnement,
artefacts construits (.app signé, .dmg vérifié), absence de renvoi vers une interface de chatbot."""
import json
import os
import plistlib
import re
import shutil
import sqlite3
import subprocess
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from jarvis import paths
from jarvis.errors import ProviderError
from tests.helpers import TestEnv, say

ROOT = Path(__file__).resolve().parent.parent


class IndependenceTests(unittest.TestCase):
    def setUp(self):
        self.env = TestEnv()
        self.app = self.env.make_app()

    def tearDown(self):
        self.env.close()

    def test_aucun_renvoi_vers_une_interface_de_chatbot(self):
        pattern = re.compile(r"https?://(www\.)?(claude\.ai|chat\.openai\.com|chatgpt\.com|gemini\.google\.com)", re.I)
        for f in list((ROOT / "web").rglob("*.js")) + list((ROOT / "web").rglob("*.html")) + [ROOT / "macos" / "main.swift"]:
            self.assertIsNone(pattern.search(f.read_text(encoding="utf-8")), f"lien vers un chatbot dans {f}")

    def test_service_et_plist_de_demarrage_automatique(self):
        from jarvis import service
        os.environ["JARVIS_LAUNCHAGENTS_DIR"] = str(self.env.root / "LaunchAgents")
        try:
            r = service.enable_autostart(8765, load=False)
            with open(r["plist"], "rb") as f:
                pl = plistlib.load(f)
            self.assertEqual(pl["Label"], "studio.novalys.jarvis.service")
            self.assertTrue(pl["RunAtLoad"])
            self.assertEqual(pl["KeepAlive"], {"SuccessfulExit": False})
            self.assertTrue(pl["ProgramArguments"][-2].endswith("jarvis.py"))
            info = service.info(self.app)
            self.assertTrue(info["autostart"])
            self.assertIn("eteint", info["states"])
            self.assertTrue(service.disable_autostart(unload=False)["removed"])
            self.assertFalse(service.info(self.app)["autostart"])
        finally:
            os.environ.pop("JARVIS_LAUNCHAGENTS_DIR", None)

    def test_limite_d_abonnement_bloque_la_tache_avec_prochaine_action(self):
        from jarvis.providers.base import Provider

        class Limite(Provider):
            id, label = "limite", "Fournisseur limité"

            def available(self):
                return True, "ok"

            def complete(self, *a, **k):
                raise ProviderError("Limite d'usage de l'abonnement atteinte (réinitialisation : 20:10).", code="limite_usage")

        self.app.providers.register(Limite(self.app))
        self.app.settings.update({"ai": {"provider": "limite", "fallback_model": None}})
        r = self.app.send_message(None, "Bonjour")
        t = self.env.wait_task(r["task_id"])
        self.assertEqual(t["status"], "bloquee")
        self.assertIn("réinitialisation", t["result"])
        self.assertIn("autre fournisseur", t["next_action"])

    def test_fournisseur_compatible_openai_local(self):
        """Code d'intégration testé contre un petit serveur local qui respecte le format de l'API (pas un vrai modèle)."""
        received = {}

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_POST(self):
                received["body"] = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                received["path"] = self.path
                out = json.dumps({"choices": [{"message": {"content": json.dumps(say("Bonjour depuis le serveur local."))}}],
                                  "usage": {"prompt_tokens": 12, "completion_tokens": 7}}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(out)))
                self.end_headers()
                self.wfile.write(out)

        srv = HTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        try:
            base = f"http://127.0.0.1:{srv.server_address[1]}/v1"
            self.app.settings.update({"ai": {"provider": "openai_compatible", "fallback_model": None,
                                             "openai_compatible": {"base_url": base, "model": "modele-local", "label": "Local"}}})
            ok, why = self.app.providers.providers["openai_compatible"].available()
            self.assertTrue(ok, why)
            r = self.app.send_message(None, "Bonjour")
            t = self.env.wait_task(r["task_id"])
            self.assertEqual(t["result"], "Bonjour depuis le serveur local.")
            self.assertEqual(received["path"], "/v1/chat/completions")
            self.assertEqual(received["body"]["model"], "modele-local")
            u = self.app.db.one("SELECT provider, cost_kind, input_tokens FROM ai_usage ORDER BY id DESC LIMIT 1")
            self.assertEqual((u["provider"], u["cost_kind"], u["input_tokens"]), ("openai_compatible", "gratuit_local", 12))
        finally:
            srv.shutdown()

    def test_fournisseur_distant_sans_cle_indisponible_et_erreurs_http(self):
        from jarvis.providers.others import provider_http_error
        self.app.settings.update({"ai": {"openai_compatible": {"base_url": "https://api.exemple.invalid/v1", "model": "m"}}})
        ok, why = self.app.providers.providers["openai_compatible"].available()
        self.assertFalse(ok)
        self.assertIn("clé", why)

        class E:
            def __init__(self, code, headers=None):
                self.code, self.headers = code, headers or {}
        self.assertEqual(provider_http_error("X", E(401)).code, "echec_authentification")
        e = provider_http_error("X", E(429, {"Retry-After": "30"}))
        self.assertEqual((e.code, e.details["retry_after"]), ("limite_debit", "30"))
        self.assertEqual(provider_http_error("X", E(503)).code, "fournisseur_indisponible")


class RelocationTests(unittest.TestCase):
    def test_migration_copie_sans_rien_supprimer(self):
        from jarvis import relocation
        tmp = Path(tempfile.mkdtemp(prefix="jarvis-reloc-"))
        legacy = tmp / "ancien"
        (legacy / "data").mkdir(parents=True)
        (legacy / "workspace" / "sites").mkdir(parents=True)
        (legacy / "workspace" / "sites" / "index.html").write_text("<h1>ok</h1>")
        c = sqlite3.connect(str(legacy / "data" / "jarvis.db"))
        c.execute("CREATE TABLE t(x)")
        c.execute("INSERT INTO t VALUES ('donnée')")
        c.commit()
        c.close()
        saved = (paths.DEFAULT_DATA, paths.LEGACY_ROOTS, os.environ.get("JARVIS_DATA_DIR"), os.environ.get("JARVIS_WORKSPACE"))
        try:
            paths.DEFAULT_DATA = tmp / "support" / "data"
            paths.LEGACY_ROOTS = [legacy]
            os.environ["JARVIS_DATA_DIR"] = str(paths.DEFAULT_DATA)
            os.environ["JARVIS_WORKSPACE"] = str(tmp / "JARVIS")
            info = relocation.migrate_legacy()
            self.assertEqual(info["from"], str(legacy))
            c = sqlite3.connect(str(paths.DEFAULT_DATA / "jarvis.db"))
            self.assertEqual(c.execute("SELECT x FROM t").fetchone()[0], "donnée")
            c.close()
            self.assertTrue((tmp / "JARVIS" / "sites" / "index.html").exists())
            self.assertTrue((legacy / "data" / "jarvis.db").exists(), "l'ancien emplacement est conservé")
            self.assertIsNone(relocation.migrate_legacy(), "jamais deux fois")
        finally:
            paths.DEFAULT_DATA, paths.LEGACY_ROOTS = saved[0], saved[1]
            for k, v in (("JARVIS_DATA_DIR", saved[2]), ("JARVIS_WORKSPACE", saved[3])):
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v
            shutil.rmtree(tmp, ignore_errors=True)


@unittest.skipUnless((ROOT / "dist" / "JARVIS.app").exists(), "application non construite (python3 jarvis.py build)")
class ArtifactTests(unittest.TestCase):
    def test_application_signee_et_complete(self):
        app = ROOT / "dist" / "JARVIS.app"
        with open(app / "Contents" / "Info.plist", "rb") as f:
            info = plistlib.load(f)
        self.assertEqual(info["CFBundleIdentifier"], "studio.novalys.jarvis")
        self.assertIn("NSMicrophoneUsageDescription", info)
        self.assertIn("NSSpeechRecognitionUsageDescription", info)
        self.assertTrue((app / "Contents" / "MacOS" / "JARVIS").stat().st_mode & 0o111)
        self.assertTrue((app / "Contents" / "Resources" / "JARVIS.icns").exists())
        self.assertTrue((app / "Contents" / "Resources" / "app" / "jarvis.py").exists())
        self.assertFalse(list((app / "Contents" / "Resources" / "app").rglob("*.db")), "aucune donnée dans l'application")
        r = subprocess.run(["codesign", "--verify", "--deep", "--strict", str(app)], capture_output=True)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_image_disque_verifiee(self):
        dmgs = list((ROOT / "dist").glob("JARVIS-*.dmg"))
        self.assertTrue(dmgs)
        r = subprocess.run(["hdiutil", "verify", str(dmgs[0])], capture_output=True)
        self.assertEqual(r.returncode, 0, r.stderr)


if __name__ == "__main__":
    unittest.main()
