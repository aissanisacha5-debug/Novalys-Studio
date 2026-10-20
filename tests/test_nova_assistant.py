"""Nova assistant : mémoire consultable et effaçable, tri Gmail (à répondre / à relancer), automatisations par la
conversation (confirmations), reprise après incident, état de persistance, réponse orale, liste des voix du Mac."""
import os
import threading
import unittest
from unittest import mock

from jarvis.agent.engine import system_prompt
from jarvis.errors import ConfirmationRequired
from jarvis.services import parse_voices
from jarvis.tools import assistant
from jarvis.tools.registry import ToolContext
from tests.helpers import TestEnv


def fil(i, **kw):
    base = {"id": f"t{i}", "subject": f"Sujet {i}", "correspondent": "client@exemple.fr", "last_date": "2020-01-01T10:00:00Z",
            "last_from_me": False, "asks_me": False, "i_asked": False, "evidence": "", "automated": False}
    return {**base, **kw}


class TriGmailTests(unittest.TestCase):
    def test_regles_de_tri(self):
        r = assistant.classify([
            fil(1, asks_me=True, evidence="Peux-tu m'envoyer le devis ?"),
            fil(2, last_from_me=True, i_asked=True, evidence="Tu me dis si ça te va ?"),
            fil(3, last_from_me=True, i_asked=False),                       # ancien mais rien n'était demandé
            fil(4, asks_me=True, automated=True),
            fil(5, last_from_me=True, i_asked=True, last_date="2999-01-01T00:00:00Z"),   # délai non atteint
        ], relance_after=3)
        self.assertEqual([x["thread_id"] for x in r["a_repondre"]], ["t1"])
        self.assertEqual([x["thread_id"] for x in r["a_relancer"]], ["t2"])
        self.assertEqual(r["a_relancer"][0]["preuve"], "Tu me dis si ça te va ?")
        self.assertEqual({x["thread_id"] for x in r["rien_a_faire"]}, {"t3", "t4", "t5"})

    def test_resultat_non_verifie_n_est_pas_classe(self):
        env = TestEnv()
        try:
            app = env.make_app()
            fake = {"data": {"threads": [fil(1, asks_me=True)]}, "calls": [], "missing_tools": [], "tool_errors": []}
            ctx = ToolContext(app, None, None, threading.Event(), None, "general")
            with mock.patch.object(assistant, "run_claude_connector", return_value=fake):
                r = assistant.h_gmail_triage(ctx, {})
            self.assertEqual(r["_state"], "non_verifie")
            self.assertEqual(r["a_repondre"], [])
            fake["calls"] = [{"tool": "mcp__claude_ai_Gmail__search_threads"}]
            with mock.patch.object(assistant, "run_claude_connector", return_value=fake):
                r = assistant.h_gmail_triage(ctx, {"jours": 7})
            self.assertEqual(r["_state"], "confirme")
            self.assertEqual(r["a_repondre"][0]["thread_id"], "t1")
            self.assertIn("newer_than:7d", r["requete"])
        finally:
            env.close()


class AssistantOutilsTests(unittest.TestCase):
    def setUp(self):
        self.env = TestEnv()
        os.environ["JARVIS_LAUNCHAGENTS_DIR"] = str(self.env.root / "LaunchAgents")
        self.app = self.env.make_app()
        self.ctx = lambda: ToolContext(self.app, None, None, threading.Event(), None, "general")

    def tearDown(self):
        os.environ.pop("JARVIS_LAUNCHAGENTS_DIR", None)
        self.env.close()

    def call(self, tool, **args):
        return self.app.tools.invoke(tool, args, self.ctx())

    def approve_and_call(self, tool, **args):
        with self.assertRaises(ConfirmationRequired):
            self.call(tool, **args)
        conf = [c for c in self.app.permissions.pending() if c["tool"] == tool][0]
        self.app.permissions.decide(conf["id"], True)
        return self.call(tool, **args)

    def test_memoire_lister_puis_oublier(self):
        m = self.app.memory.add("Sacha préfère les réunions le matin", "preference", "test", "preference")
        listed = self.call("memoire_lister")["result"]["souvenirs"]
        self.assertIn(m["id"], [x["id"] for x in listed])
        r = self.call("memoire_oublier", memory_id=m["id"])
        self.assertEqual(r["state"], "confirme")
        self.assertNotIn(m["id"], [x["id"] for x in self.call("memoire_lister")["result"]["souvenirs"]])

    def test_automatisation_creation_confirmee_desactivation_immediate(self):
        r = self.approve_and_call("automatisation_creer", nom="Retards du matin", declencheur={"type": "quotidien", "heure": "08:30"},
                                  action={"type": "taches_en_retard"}, activer=True)
        aid = r["result"]["automatisation"]["id"]
        self.assertTrue(r["result"]["automatisation"]["active"])
        off = self.call("automatisation_activer", id=aid, actif=False)            # couper ne demande jamais d'accord
        self.assertEqual(off["state"], "confirme")
        self.assertFalse(self.app.scheduler.get(aid)["enabled"])
        with self.assertRaises(ConfirmationRequired):
            self.call("automatisation_activer", id=aid, actif=True)
        run = self.call("automatisation_executer", id=aid)
        self.assertIn("en_retard", run["result"]["resultat"])
        runs = self.app.db.all("SELECT status FROM automation_runs WHERE automation_id=?", (aid,))
        self.assertEqual([x["status"] for x in runs], ["succes"])

    def test_automatisation_invalide_refusee(self):
        with self.assertRaises(Exception):
            self.approve_and_call("automatisation_creer", nom="Trop souvent", declencheur={"type": "intervalle", "minutes": 1},
                                  action={"type": "bilan_quotidien"})

    def test_reprise_apres_incident(self):
        a = self.app.scheduler.create("Essai", {"type": "manuel"}, {"type": "etat_projets"})
        self.app.db.insert("INSERT INTO automation_runs(automation_id, started_at, status) VALUES (?,?,?)", (a["id"], "2026-01-01", "en_cours"))
        self.assertEqual(self.app.scheduler.recover(), 1)
        self.assertEqual(self.app.db.one("SELECT status FROM automation_runs WHERE automation_id=?", (a["id"],))["status"], "interrompue")
        self.assertEqual(self.app.scheduler.recover(), 0)

    def test_persistance_dite_honnetement(self):
        st = self.call("service_etat")["result"]["persistance"]
        self.assertFalse(st["demarrage_automatique"])
        self.assertIn("tant que Nova", st["explication"])
        self.assertEqual(self.app.tools.get("service_demarrage_auto_activer").risk, "eleve")

    def test_reponse_orale_seulement_pour_la_voix(self):
        oral = system_prompt(self.app, [], "general", "execution_supervisee", spoken=True)
        ecrit = system_prompt(self.app, [], "general", "execution_supervisee")
        self.assertIn("RÉPONSE ORALE", oral)
        self.assertNotIn("RÉPONSE ORALE", ecrit)
        self.assertIn("memoire_oublier", ecrit)


class VoixMacTests(unittest.TestCase):
    def test_voix_reglee_sur_la_reference(self):
        env = TestEnv()
        try:
            app = env.make_app()
            args = app.voice._args("Bonjour")
            self.assertEqual(args[:5], ["say", "-v", "Thomas", "-r", "200"])
            self.assertIn("[[pbas 42]] Bonjour", args[-1])
            app.settings.update({"voice": {"pitch": 0}}, "test")
            self.assertNotIn("pbas", app.voice._args("Bonjour")[-1])
            with self.assertRaises(Exception):
                app.settings.update({"voice": {"pitch": 99}}, "test")
        finally:
            env.close()

    def test_liste_des_voix_avec_un_seul_espace(self):
        out = ("Thomas (Français (France)) fr_FR    # Bonjour, je m'appelle Thomas.\n"
               "Audrey (Premium)    fr_FR    # Bonjour, je m'appelle Audrey.\n"
               "Reed (French (Canada)) fr_CA    # Bonjour\nAlbert              en_US    # Hello\n")
        names = [v["name"] for v in parse_voices(out)]
        self.assertEqual(names, ["Thomas (Français (France))", "Audrey (Premium)", "Reed (French (Canada))", "Albert"])


    def test_ancien_debit_par_defaut_mis_a_jour_une_seule_fois(self):
        env = TestEnv()
        try:
            app = env.make_app()
            from jarvis.config import Settings
            from jarvis.db import dumps
            prefs = app.settings.all()
            prefs["voice"]["rate"] = 190
            del prefs["voice"]["pitch"]
            app.db.execute("UPDATE settings SET value=? WHERE key='prefs'", (dumps(prefs),))
            s = Settings(app.db)
            self.assertEqual((s.get("voice.rate"), s.get("voice.pitch")), (200, 42))
            s.update({"voice": {"rate": 190}}, "choix de Sacha")
            self.assertEqual(Settings(app.db).get("voice.rate"), 190)      # un choix explicite reste respecté
        finally:
            env.close()


if __name__ == "__main__":
    unittest.main()
