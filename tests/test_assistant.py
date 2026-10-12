"""Prompt 5 : mémoire désactivable et temporaire par conversation, tâches modifiables et échéances notifiées,
outils date/heure, notes, réglages (sensibles refusés), scripts approuvés, voix (synthèse et arrêt)."""
import threading
import time
import unittest

from jarvis import paths
from jarvis.errors import NotFound, PermissionDenied, ToolUnavailable, ValidationError
from jarvis.tools.registry import ToolContext
from tests.helpers import TestEnv, act, say


class AssistantTests(unittest.TestCase):
    def setUp(self):
        self.env = TestEnv()
        self.app = self.env.make_app()
        self.app.settings.update({"notifications": {"macos": False}})
        self.ctx = ToolContext(self.app, cancel_event=threading.Event())

    def tearDown(self):
        self.env.close()

    def call(self, tool, **args):
        return self.app.tools.invoke(tool, args, self.ctx)

    def test_memorisation_desactivable(self):
        self.app.settings.update({"memory": {"enabled": False}})
        with self.assertRaises(ToolUnavailable):
            self.call("memoire_enregistrer", content="Préfère le thé.", reason="test")
        self.app.memory.add("Ajout manuel par Sacha.", "connaissance", "saisie de Sacha")   # l'ajout manuel reste possible
        self.assertEqual(len(self.app.memory.search("manuel")), 1)
        self.app.settings.update({"memory": {"enabled": True}})
        self.assertEqual(self.call("memoire_enregistrer", content="Préfère le thé.", reason="test", nature="preference", type="preference")["state"],
                         "confirme")

    def test_effacer_une_conversation_garde_la_memoire_durable(self):
        self.env.use_script([say("Je retiens.", [act("memoire_enregistrer", content="Le devis Da Marco est à envoyer vendredi.", type="temporaire",
                                                     reason="propre à cette conversation"),
                                                 act("memoire_enregistrer", content="Sacha préfère les réponses courtes.", type="preference",
                                                     nature="preference", reason="exprimé par Sacha")]), say("Noté.")])
        r = self.app.send_message(None, "Retiens ça")
        self.env.wait_task(r["task_id"])
        self.assertEqual(len(self.app.memory.search("")), 2)
        res = self.app.conversations.delete(r["conversation_id"])
        self.assertEqual(res["temporary_memories_deleted"], 1)
        left = [m["content"] for m in self.app.memory.search("")]
        self.assertEqual(left, ["Sacha préfère les réponses courtes."])

    def test_modifier_une_tache_et_notifier_son_echeance(self):
        t = self.app.tasks.create("Appeler Da Marco", kind="todo", start=False)
        t = self.app.tasks.update(t["id"], title="Rappeler Da Marco", due_date="2020-01-01T10:00", priority=3)
        self.assertEqual((t["title"], t["priority"]), ("Rappeler Da Marco", 3))
        with self.assertRaises(ValidationError):
            self.app.tasks.update(t["id"], due_date="demain")
        self.assertEqual(self.app.tasks.notify_due(), 1)
        self.assertEqual(self.app.tasks.notify_due(), 0, "une seule notification par échéance")
        self.assertEqual(self.app.db.one("SELECT count(*) AS n FROM notifications WHERE title='Échéance atteinte'")["n"], 1)
        self.app.tasks.cancel(t["id"])
        with self.assertRaises(ValidationError):
            self.app.tasks.update(t["id"], title="x")
        self.assertEqual(self.app.tasks.get(t["id"])["status"], "annulee")

    def test_outil_date_heure(self):
        r = self.call("date_heure")
        self.assertEqual(r["state"], "confirme")
        self.assertEqual(r["result"]["date"], time.strftime("%Y-%m-%d"))
        self.assertEqual(r["result"]["fuseau"], "Europe/Paris")

    def test_note(self):
        r = self.call("note_creer", title="Idées site", content="Galerie photo des plats.")
        self.assertEqual(r["state"], "confirme")
        self.assertIn("/notes/", r["result"]["path"])
        self.assertTrue(r["result"]["path"].startswith(str((paths.workspace_dir() / "notes").resolve())))

    def test_reglages_non_sensibles_seulement(self):
        r = self.call("parametre_modifier", key="voice.volume", value="0,5")
        self.assertEqual((r["state"], self.app.settings.get("voice.volume")), ("confirme", 0.5))
        self.call("parametre_modifier", key="voice.auto_speak", value=True)
        self.assertTrue(self.app.settings.get("voice.auto_speak"))
        with self.assertRaises(ValidationError):                 # hors liste (enum) : refusé à la validation
            self.call("parametre_modifier", key="autonomy.mode", value="developpement")
        from jarvis.tools.data_tools import h_settings_set
        with self.assertRaises(PermissionDenied):                # et refusé par l'outil lui-même
            h_settings_set(self.ctx, {"key": "allowed_dirs", "value": "/"})
        self.assertEqual(self.app.settings.get("autonomy.mode"), "execution_supervisee")
        self.assertIn("modifiables_par_jarvis", self.call("parametres_consulter")["result"])

    def test_scripts_approuves_uniquement(self):
        with self.assertRaises(ToolUnavailable):
            self.call("script_executer", name="bonjour")
        self.app.settings.update({"scripts_approuves": {"bonjour": {"command": "echo bonjour", "description": "test"}}})
        r = self.call("script_executer", name="bonjour", args=["Sacha"])
        self.assertEqual(r["state"], "confirme")
        self.assertIn("bonjour Sacha", r["result"]["output"])
        with self.assertRaises(NotFound):
            self.call("script_executer", name="inconnu")

    def test_synthese_vocale_et_arret_immediat(self):
        import shutil
        if not shutil.which("say"):
            self.skipTest("say absent")
        self.app.settings.update({"voice": {"volume": 0.0}})      # muet pendant les tests
        r = self.app.voice.speak("Ceci est un test de la synthèse vocale de JARVIS, assez long pour être interrompu.")
        self.assertTrue(r["speaking"])
        time.sleep(0.3)
        self.assertTrue(self.app.voice.speaking())
        self.assertTrue(self.app.voice.stop())
        time.sleep(0.3)
        self.assertFalse(self.app.voice.speaking())


if __name__ == "__main__":
    unittest.main()
