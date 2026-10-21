"""Nova (tranche 1) : accueil plein écran, voix jouée par l'appareil, états « recherche » / « exécution » du noyau,
et tests JavaScript de la conversation vocale (exécutés si Node est installé)."""
import json
import queue
import shutil
import subprocess
import threading
import unittest
import urllib.request

from jarvis import paths
from jarvis.errors import ValidationError
from jarvis.server import serve
from jarvis.tools.nova import normalize_view
from jarvis.tools.registry import SEARCH_TOOLS, ToolContext, tool_phase
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
        self.assertIn('id="nova-orb"', home)
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
                  "/js/nova/states.js", "/js/nova/board.js", "/js/echo.js", "/css/nova.css"):
            self.assertTrue(self.get(f), f)

    def api(self, method, path):
        r = urllib.request.Request(f"http://127.0.0.1:{self.port}{path}", method=method,
                                   headers={"Host": f"127.0.0.1:{self.port}", "X-Jarvis-Token": "jeton-nova"})
        with urllib.request.urlopen(r, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))["data"]

    def test_vue_nova_lue_puis_effacee(self):
        self.assertIsNone(self.api("GET", "/api/nova/view")["view"])
        ctx = ToolContext(self.app, 7, None, threading.Event(), None, "general")
        self.app.tools.invoke("nova_afficher", DEMO["liste"], ctx)
        view = self.api("GET", "/api/nova/view")["view"]
        self.assertEqual([e["id"] for e in view["elements"]], ["lucas", "sonia", "thomas"])
        self.assertEqual(view["task_id"], 7)
        q = self.app.bus.subscribe()
        try:
            self.api("DELETE", "/api/nova/view")
            ev = q.get(timeout=2)
            while ev.get("type") != "nova_view":
                ev = q.get(timeout=2)
            self.assertIsNone(ev["view"])
        finally:
            self.app.bus.unsubscribe(q)
        self.assertIsNone(self.api("GET", "/api/nova/view")["view"])


DEMO = json.loads((paths.ROOT / "tests" / "fixtures" / "nova_demo.json").read_text(encoding="utf-8"))


class NovaAffichageTests(unittest.TestCase):
    def test_vue_liste_normalisee(self):
        v = normalize_view(DEMO["liste"])
        self.assertEqual(v["vue"], "liste")
        lucas = v["elements"][0]
        self.assertEqual(lucas["badge"], {"texte": "Froid", "ton": "froid"})
        self.assertEqual(lucas["action"]["label"], "Action recommandée")
        self.assertIsNone(v["detail"])

    def test_vue_detail_et_validation(self):
        v = normalize_view(dict(DEMO["liste"], detail=DEMO["detail"]))
        self.assertEqual(v["vue"], "detail")
        self.assertEqual(v["detail"]["gauche"]["total"], {"label": "Investissement", "valeur": "8 500 €"})
        self.assertEqual(v["detail"]["validation"]["succes"], "Proposition envoyée")

    def test_refus_des_vues_invalides(self):
        base = DEMO["liste"]
        bad = [dict(base, titre=""), dict(base, vue="tableau"), dict(base, selection="inconnu"),
               dict(base, elements=[{"nom": "A", "badge": {"texte": "x", "ton": "violet"}}]),
               dict(base, elements=[{"id": "a", "nom": "A"}, {"id": "a", "nom": "B"}]),
               dict(base, elements=[{"nom": "A"}] * 9), dict(base, vue="detail"),
               dict(base, elements=[{"nom": "<b>" + "x" * 200}])]
        for a in bad:
            with self.assertRaises(ValidationError, msg=str(a)[:120]):
                normalize_view(a)

    def test_outil_publie_la_vue_et_le_prompt_dit_nova(self):
        env = TestEnv()
        try:
            app = env.make_app()
            q = app.bus.subscribe()
            ctx = ToolContext(app, 3, None, threading.Event(), None, "general")
            r = app.tools.invoke("nova_afficher", dict(DEMO["liste"], selection="sonia"), ctx)
            self.assertTrue(r["ok"], r)
            ev = q.get(timeout=2)
            while ev.get("type") != "nova_view":
                ev = q.get(timeout=2)
            self.assertEqual(ev["view"]["selection"], "sonia")
            self.assertEqual(app.nova_view["task_id"], 3)
            self.assertEqual(app.tools.get("nova_afficher").risk, "faible")
            app.tools.invoke("nova_effacer", {}, ctx)
            self.assertIsNone(app.nova_view)
            self.assertEqual(app.settings.get("assistant.name"), "Nova")
        finally:
            env.close()


@unittest.skipUnless(shutil.which("node"), "Node absent : tests JavaScript de Nova non exécutés")
class NovaJavaScriptTests(unittest.TestCase):
    def test_conversation_vocale_js(self):
        p = subprocess.run(["node", "--test", str(paths.ROOT / "tests" / "js" / "nova.test.mjs")],
                           capture_output=True, text=True, timeout=120, cwd=paths.ROOT)
        self.assertEqual(p.returncode, 0, p.stdout[-3000:] + p.stderr[-2000:])


if __name__ == "__main__":
    unittest.main()
