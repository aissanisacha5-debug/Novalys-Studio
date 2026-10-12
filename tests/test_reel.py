"""Tests avec le VRAI fournisseur (Claude via Claude Code). Lancés seulement si JARVIS_TEST_REEL=1,
car ils consomment de l'usage de l'abonnement."""
import os
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


if __name__ == "__main__":
    unittest.main()
