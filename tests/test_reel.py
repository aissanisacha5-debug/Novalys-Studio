"""Tests avec le VRAI fournisseur (Claude via Claude Code). Lancés seulement si JARVIS_TEST_REEL=1,
car ils consomment de l'usage de l'abonnement."""
import os
import socket
import unittest

from jarvis import paths
from tests.helpers import TestEnv


@unittest.skipUnless(os.environ.get("JARVIS_TEST_REEL") == "1", "JARVIS_TEST_REEL=1 pour lancer les tests réels")
class RealProviderTests(unittest.TestCase):
    def setUp(self):
        self.env = TestEnv()
        self.app = self.env.make_app()
        self.app.settings.update({"ai": {"model": "haiku"}})

    def tearDown(self):
        self.env.close()

    def test_reponse_reelle(self):
        r = self.app.send_message(None, "Réponds seulement : OK.")
        t = self.env.wait_task(r["task_id"], timeout=180)
        self.assertEqual(t["status"], "terminee")
        self.assertIn("OK", t["result"].upper())
        u = self.app.db.one("SELECT provider, cost_kind FROM ai_usage")
        self.assertEqual((u["provider"], u["cost_kind"]), ("claude_code", "inclus_abonnement"))

    def test_creation_de_fichier_reelle(self):
        r = self.app.send_message(None, "Crée le fichier essai/reel.txt contenant exactement le mot JARVIS, puis termine.")
        t = self.env.wait_task(r["task_id"], timeout=240)
        self.assertEqual(t["status"], "terminee", t["result"])
        self.assertEqual((paths.workspace_dir() / "essai" / "reel.txt").read_text().strip(), "JARVIS")


    def test_parcours_complet_par_l_api_et_persistance_apres_redemarrage(self):
        """Démarrage → interface → demande → tâche → outil → résultat → compte rendu → redémarrage → toujours consultable."""
        import json
        import threading
        import urllib.request
        from jarvis.server import serve
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]
        srv = serve(self.app, port, "jeton")
        threading.Thread(target=srv.serve_forever, daemon=True).start()

        def call(method, path, body=None):
            req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", method=method, data=json.dumps(body).encode() if body else None,
                                         headers={"Host": f"127.0.0.1:{port}", "X-Jarvis-Token": "jeton", "Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read())["data"] if "json" in r.headers.get("Content-Type", "") else r.read()

        html = call("GET", "/")
        self.assertIn(b"JARVIS", html)
        r = call("POST", "/api/chat", {"text": "Crée le fichier parcours/ok.md avec le titre « Parcours validé », vérifie-le et rends compte."})
        t = self.env.wait_task(r["task_id"], timeout=240)
        self.assertEqual(t["status"], "terminee", t["result"])
        steps = [(s["tool"], s["status"], s["args"]) for s in self.app.tasks.detail(t["id"])["steps"] if s["kind"] == "outil"]
        self.assertTrue((paths.workspace_dir() / "parcours" / "ok.md").exists(), (t["result"], steps))
        self.assertIn("Parcours validé", (paths.workspace_dir() / "parcours" / "ok.md").read_text())
        conv = call("GET", f"/api/conversations/{r['conversation_id']}")
        self.assertEqual([m["role"] for m in conv["messages"]], ["user", "assistant"])
        srv.shutdown()
        srv.server_close()
        self.app.shutdown()
        self.app.db.close()
        app2 = self.env.make_app()
        self.assertEqual(app2.tasks.detail(r["task_id"])["status"], "terminee")
        self.assertEqual(len(app2.conversations.messages(r["conversation_id"])), 2)


if __name__ == "__main__":
    unittest.main()
