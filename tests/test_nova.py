"""Nova (tranche 1) : accueil plein écran, voix jouée par l'appareil, états « recherche » / « exécution » du noyau,
et tests JavaScript de la conversation vocale (exécutés si Node est installé)."""
import queue
import shutil
import subprocess
import threading
import unittest
import urllib.request

from jarvis import paths
from jarvis.server import serve
from jarvis.tools.registry import SEARCH_TOOLS, tool_phase
from tests.helpers import TestEnv, act, say


def drain(q):
    out = []
    while True:
        try:
            out.append(q.get_nowait())
        except queue.Empty:
            return out


class NovaVoiceTests(unittest.TestCase):
    def setUp(self):
        self.env = TestEnv()
        self.app = self.env.make_app([say("Bonjour Sacha. Il est midi.")])
        self.enqueued = []
        self.app.voice.enqueue = self.enqueued.append          # voix du Mac : enregistrée, jamais jouée en test
        self.q = self.app.bus.subscribe()

    def tearDown(self):
        self.app.bus.unsubscribe(self.q)
        self.env.close()

    def test_voix_client_reponse_en_evenements_speech(self):
        r = self.app.send_message(None, "Quelle heure est-il ?", source="voix", voice_out="client")
        self.env.wait_task(r["task_id"])
        speech = [e for e in drain(self.q) if e.get("type") == "speech"]
        self.assertTrue(speech, "aucune phrase envoyée à l'appareil")
        self.assertTrue(all(e["task_id"] == r["task_id"] for e in speech))
        self.assertEqual(" ".join(e["text"] for e in speech).split(), "Bonjour Sacha. Il est midi.".split())
        self.assertEqual(self.enqueued, [], "le Mac ne doit pas parler quand l'appareil lit la réponse")

    def test_voix_mac_inchangee_par_defaut(self):
        r = self.app.send_message(None, "Quelle heure est-il ?", source="voix")
        self.env.wait_task(r["task_id"])
        self.assertTrue(self.enqueued)
        self.assertFalse([e for e in drain(self.q) if e.get("type") == "speech"])

    def test_texte_sans_voix(self):
        r = self.app.send_message(None, "Bonjour", source="texte", voice_out="client")
        self.env.wait_task(r["task_id"])
        self.assertFalse([e for e in drain(self.q) if e.get("type") == "speech"])
        self.assertEqual(self.enqueued, [])

    def test_contexte_conserve_dans_la_conversation(self):
        r1 = self.app.send_message(None, "Je m'appelle Sacha", source="voix", voice_out="client")
        self.env.wait_task(r1["task_id"])
        r2 = self.app.send_message(r1["conversation_id"], "Comment je m'appelle ?", source="voix", voice_out="client")
        self.env.wait_task(r2["task_id"])
        self.assertEqual(r1["conversation_id"], r2["conversation_id"])
        self.assertIn("Je m'appelle Sacha", self.env.provider.prompts[-1])

    def test_phase_recherche_publiee_pour_un_outil_de_lecture(self):
        self.env.use_script([say("Je regarde.", [act("date_heure")]), say("Il est midi.")])
        r = self.app.send_message(None, "Quelle heure ?", source="voix", voice_out="client")
        self.env.wait_task(r["task_id"])
        tools = [e for e in drain(self.q) if e.get("type") == "activity" and e.get("state") == "outil"]
        self.assertEqual([(e["tool"], e["phase"]) for e in tools], [("date_heure", "recherche")])


class NovaPhaseTests(unittest.TestCase):
    def test_classement_des_outils(self):
        self.assertEqual(tool_phase("web_rechercher"), "recherche")
        self.assertEqual(tool_phase("gmail_lire"), "recherche")
        for t in ("fichier_ecrire", "fichier_supprimer", "gmail_brouillon_creer", "commande_executer", "outil_inconnu"):
            self.assertEqual(tool_phase(t), "execution", t)

    def test_outils_de_recherche_existent(self):
        env = TestEnv()
        try:
            ids = set(env.make_app().tools.ids())
            self.assertEqual(SEARCH_TOOLS - ids, set())
        finally:
            env.close()


class NovaPageTests(unittest.TestCase):
    def setUp(self):
        self.env = TestEnv()
        self.app = self.env.make_app()
        srv = serve(self.app, 0, "jeton-nova")
        self.port = srv.server_address[1]
        srv.server_close()
        self.srv = serve(self.app, self.port, "jeton-nova")
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    def tearDown(self):
        self.srv.shutdown()
        self.srv.server_close()
        self.env.close()

    def get(self, path):
        r = urllib.request.Request(f"http://127.0.0.1:{self.port}{path}", headers={"Host": f"127.0.0.1:{self.port}"})
        with urllib.request.urlopen(r, timeout=10) as resp:
            return resp.read().decode("utf-8")

    def test_accueil_nova_et_console(self):
        home = self.get("/")
        self.assertIn('id="nova-core"', home)
        self.assertIn("jeton-nova", home)
        self.assertNotIn("__JARVIS_TOKEN__", home)
        console = self.get("/console")
        self.assertIn('id="shell"', console)
        self.assertIn("jeton-nova", console)

    def test_accueil_sans_texte_de_reponse(self):
        # Aucun élément de conversation sur l'accueil : seul le noyau et un libellé d'état pour les lecteurs d'écran.
        home = self.get("/")
        for forbidden in ("composer", "transcript", "messages", "chat"):
            self.assertNotIn(forbidden, home.lower())

    def test_fichiers_nova_servis(self):
        for f in ("/js/nova/main.js", "/js/nova/session.js", "/js/nova/speaker.js", "/js/nova/listener.js",
                  "/js/nova/states.js", "/js/echo.js", "/css/nova.css"):
            self.assertTrue(self.get(f), f)


@unittest.skipUnless(shutil.which("node"), "Node absent : tests JavaScript de Nova non exécutés")
class NovaJavaScriptTests(unittest.TestCase):
    def test_conversation_vocale_js(self):
        p = subprocess.run(["node", "--test", str(paths.ROOT / "tests" / "js" / "nova.test.mjs")],
                           capture_output=True, text=True, timeout=120, cwd=paths.ROOT)
        self.assertEqual(p.returncode, 0, p.stdout[-3000:] + p.stderr[-2000:])


if __name__ == "__main__":
    unittest.main()
