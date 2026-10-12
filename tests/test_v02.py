"""Compléments v0.2 : état final recoupé, parallélisme, prochaine action, repli IA, diagnostic copiable,
navigateur piloté (réseau requis : page publique de test httpbin.org)."""
import os
import socket
import threading
import time
import unittest

from jarvis import paths
from jarvis.errors import ConfirmationRequired, PermissionDenied, ProviderError
from jarvis.providers.base import Completion, Provider
from jarvis.tools.registry import ToolContext
from tests.helpers import TestEnv, act, say


def online(host="httpbin.org"):
    try:
        socket.create_connection((host, 443), timeout=3).close()
        return True
    except OSError:
        return False


class EngineV02Tests(unittest.TestCase):
    def setUp(self):
        self.env = TestEnv()
        self.app = self.env.make_app()

    def tearDown(self):
        self.env.close()

    def run_chat(self, script):
        self.env.use_script(script)
        r = self.app.send_message(None, "test")
        return self.env.wait_task(r["task_id"])

    def test_le_modele_ne_peut_pas_declarer_un_succes_non_verifie(self):
        t = self.run_chat([say("J'écris.", [act("fichier_ecrire", path="a.txt", content="a"), act("fichier_lire", path="absent.txt")]),
                           say("Tout est parfait.", state="confirme")])
        self.assertEqual(t["result_state"], "partiel")

    def test_echec_total_ramene_a_echoue(self):
        t = self.run_chat([say("Je lis.", [act("fichier_lire", path="absent.txt")]), say("C'est fait.", state="confirme")])
        self.assertEqual(t["result_state"], "echoue")

    def test_reponse_sans_outil_est_sans_objet(self):
        t = self.run_chat([say("Bonjour.", state="confirme")])
        self.assertEqual(t["result_state"], "sans_objet")

    def test_prochaine_action_conservee(self):
        d = say("Fait.")
        d["next_action"] = "Valider les textes avec le client."
        t = self.run_chat([d])
        self.assertEqual(t["next_action"], "Valider les textes avec le client.")
        msg = self.app.conversations.messages(t["conversation_id"])[-1]
        self.assertEqual(msg["meta"]["next_action"], "Valider les textes avec le client.")

    def test_lectures_executees_en_parallele(self):
        for i in range(3):
            (paths.workspace_dir() / f"f{i}.txt").write_text(str(i))
        t = self.run_chat([say("Je lis tout.", [act("fichier_lire", path=f"f{i}.txt") for i in range(3)]), say("Lu.")])
        steps = [s for s in self.app.tasks.detail(t["id"])["steps"] if s["kind"] == "outil"]
        self.assertEqual(len(steps), 3)
        self.assertTrue(all(s["status"] == "termine" for s in steps))
        self.assertTrue(self.app.db.one("SELECT id FROM events WHERE kind='parallele'"))

    def test_repli_vers_un_fournisseur_alternatif(self):
        class Panne(Provider):
            id, label = "panne", "Fournisseur en panne"

            def available(self):
                return True, "ok"

            def complete(self, *a, **k):
                raise ProviderError("surcharge")

        class Secours(Provider):
            id, label = "secours", "Fournisseur de secours"

            def available(self):
                return True, "ok"

            def complete(self, system, prompt, model=None, json_schema=None, timeout_s=60, cancel_event=None):
                d = say("Réponse du secours.")
                return Completion("", d, "s", self.id, cost_kind="gratuit_local")

        self.app.providers.register(Panne(self.app))
        self.app.providers.register(Secours(self.app))
        self.app.settings.update({"ai": {"provider": "panne", "fallback_model": None, "fallback_provider": "secours"}})
        r = self.app.send_message(None, "Bonjour")
        t = self.env.wait_task(r["task_id"])
        self.assertEqual(t["result"], "Réponse du secours.")
        self.assertEqual(self.app.db.one("SELECT count(*) AS n FROM ai_usage WHERE ok=0")["n"], 1)

    def test_rapport_de_diagnostic_sans_donnees_personnelles(self):
        rep = self.app.diagnostics.report()
        self.assertIn("Versions", rep)
        self.assertNotIn(os.path.expanduser("~"), rep)
        self.assertIn("sqlite", rep)


@unittest.skipUnless(os.path.exists("/Applications/Google Chrome.app") and online(), "Chrome ou réseau absent")
class BrowserTests(unittest.TestCase):
    def setUp(self):
        self.env = TestEnv()
        self.app = self.env.make_app()
        self.ctx = ToolContext(self.app, cancel_event=threading.Event())

    def tearDown(self):
        self.env.close()

    def call(self, tool, **args):
        return self.app.tools.invoke(tool, args, self.ctx)

    def open_form(self):
        """httpbin.org est un service public de test parfois indisponible : 3 essais, sinon le test est IGNORÉ (pas réussi)."""
        for _ in range(3):
            r = self.call("navigateur_ouvrir", url="https://httpbin.org/forms/post")
            if r["state"] == "confirme" and r["result"]["fields"]:
                return r
            time.sleep(2)
        self.skipTest(f"httpbin.org indisponible ({r['verification']})")

    def test_formulaire_rempli_verifie_puis_envoye_seulement_apres_accord(self):
        r = self.open_form()
        sels = [f["selector"] for f in r["result"]["fields"]]
        self.assertIn('input[name="custname"]', sels)
        r = self.call("navigateur_remplir", fields={'input[name="custname"]': "Test JARVIS", 'input[name="comments"]': "Essai automatisé"}) \
            if 'input[name="comments"]' in sels else self.call("navigateur_remplir", fields={'input[name="custname"]': "Test JARVIS"})
        self.assertEqual(r["state"], "confirme")
        with self.assertRaises(ConfirmationRequired) as cm:
            self.call("navigateur_envoyer_formulaire", selector="form")
        self.app.permissions.decide(cm.exception.details["confirmation_id"], True)
        r = self.call("navigateur_envoyer_formulaire", selector="form")
        self.assertIn("Test JARVIS", r["result"]["page_text"])         # httpbin renvoie les données reçues
        cap = self.call("navigateur_capture")
        self.assertEqual(cap["state"], "confirme")

    def test_champ_mot_de_passe_jamais_rempli_et_adresse_locale_refusee(self):
        with self.assertRaises(PermissionDenied):
            self.call("navigateur_ouvrir", url="http://127.0.0.1:8765/")
        self.open_form()
        from jarvis.tools.browser import session
        session(self.app).js("document.forms[0].insertAdjacentHTML('beforeend', '<input type=password id=mdp>')")
        with self.assertRaises(PermissionDenied):
            self.call("navigateur_remplir", fields={"#mdp": "secret"})


if __name__ == "__main__":
    unittest.main()
