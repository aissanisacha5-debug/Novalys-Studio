"""Sécurité : périmètre des dossiers, zones interdites, modes, confirmations à usage unique, commandes, réseau."""
import os
import threading
import unittest

from jarvis import paths
from jarvis.errors import ConfirmationRequired, PermissionDenied, ToolUnavailable, ValidationError
from jarvis.tools.registry import ToolContext
from tests.helpers import TestEnv


class SecurityTests(unittest.TestCase):
    def setUp(self):
        self.env = TestEnv()
        self.app = self.env.make_app()
        self.ctx = ToolContext(self.app, cancel_event=threading.Event())

    def tearDown(self):
        self.env.close()

    def call(self, tool, **args):
        return self.app.tools.invoke(tool, args, self.ctx)

    # -- périmètre -----------------------------------------------------------------
    def test_acces_hors_perimetre_refuse(self):
        (self.env.outside / "secret.txt").write_text("x")
        with self.assertRaises(PermissionDenied):
            self.call("fichier_lire", path=str(self.env.outside / "secret.txt"))
        with self.assertRaises(PermissionDenied):
            self.call("fichier_ecrire", path=str(self.env.outside / "x.txt"), content="x")

    def test_remontee_de_dossier_refusee(self):
        with self.assertRaises(PermissionDenied):
            self.call("fichier_ecrire", path="../dehors/evasion.txt", content="x")
        self.assertFalse((self.env.outside / "evasion.txt").exists())

    def test_lien_symbolique_vers_l_exterieur_refuse(self):
        (self.env.outside / "cible.txt").write_text("secret")
        os.symlink(str(self.env.outside), str(paths.workspace_dir() / "raccourci"))
        with self.assertRaises(PermissionDenied):
            self.call("fichier_lire", path="raccourci/cible.txt")

    def test_zones_systeme_et_secrets_interdites(self):
        for p in ("~/.ssh/id_rsa", "~/Library/Keychains/login.keychain-db", "/etc/passwd"):
            with self.assertRaises(PermissionDenied, msg=p):
                self.app.permissions.resolve_path(p)
        (paths.workspace_dir() / ".env").write_text("CLE=1")
        with self.assertRaises(PermissionDenied):
            self.call("fichier_lire", path=".env")

    def test_donnees_internes_de_jarvis_illisibles(self):
        with self.assertRaises(PermissionDenied):
            self.app.permissions.resolve_path(str(paths.data_dir() / "jarvis.db"))

    def test_code_de_jarvis_et_memoire_cypher_proteges_en_ecriture(self):
        self.app.settings.update({"allowed_dirs": [{"path": str(paths.ROOT.parent), "mode": "rw"}]})
        for target in (paths.ROOT / "jarvis" / "permissions.py", paths.CYPHER_DIR / "memoire" / "x.csv"):
            with self.assertRaises(PermissionDenied, msg=str(target)):
                self.app.permissions.resolve_path(str(target), write=True)

    # -- modes -----------------------------------------------------------------------
    def test_mode_assistance_interdit_l_ecriture(self):
        self.app.settings.update({"autonomy": {"mode": "assistance"}})
        with self.assertRaises(PermissionDenied):
            self.call("fichier_ecrire", path="a.txt", content="x")
        self.call("dossier_lister")

    def test_mode_conversation_interdit_tout_outil(self):
        self.app.settings.update({"autonomy": {"mode": "conversation"}})
        with self.assertRaises(PermissionDenied):
            self.call("dossier_lister")

    # -- confirmations -----------------------------------------------------------------
    def test_confirmation_a_usage_unique_et_liee_aux_arguments(self):
        f = paths.workspace_dir() / "a.txt"
        f.write_text("a")
        with self.assertRaises(ConfirmationRequired) as cm:
            self.call("fichier_supprimer", path="a.txt")
        cid = cm.exception.details["confirmation_id"]
        self.assertTrue(f.exists(), "rien ne doit être supprimé avant l'accord")
        self.app.permissions.decide(cid, True)
        (paths.workspace_dir() / "b.txt").write_text("b")
        with self.assertRaises(ConfirmationRequired):      # autre cible : l'accord ne s'applique pas
            self.call("fichier_supprimer", path="b.txt")
        r = self.call("fichier_supprimer", path="a.txt")
        self.assertEqual(r["state"], "confirme")
        self.assertFalse(f.exists())
        f.write_text("a")
        with self.assertRaises(ConfirmationRequired):      # l'accord a été consommé
            self.call("fichier_supprimer", path="a.txt")

    def test_confirmation_refusee_ne_s_execute_pas(self):
        (paths.workspace_dir() / "c.txt").write_text("c")
        with self.assertRaises(ConfirmationRequired) as cm:
            self.call("fichier_supprimer", path="c.txt")
        self.app.permissions.decide(cm.exception.details["confirmation_id"], False)
        with self.assertRaises(ConfirmationRequired):
            self.call("fichier_supprimer", path="c.txt")
        self.assertTrue((paths.workspace_dir() / "c.txt").exists())

    # -- commandes -------------------------------------------------------------------------
    def test_commande_autorisee(self):
        r = self.call("commande_executer", command="echo bonjour")
        self.assertEqual(r["result"]["exit_code"], 0)
        self.assertIn("bonjour", r["result"]["output"])

    def test_commandes_dangereuses_bloquees(self):
        for cmd in ("rm -rf /", "sudo ls", "curl https://exemple.fr", "chmod 777 x", "osascript -e beep", "bash -c ls"):
            with self.assertRaises(PermissionDenied, msg=cmd):
                self.call("commande_executer", command=cmd)
        rows = self.app.db.all("SELECT command FROM shell_history WHERE blocked=1")
        self.assertGreaterEqual(len(rows), 6)

    def test_operateurs_de_shell_refuses(self):
        for cmd in ("ls | grep a", "echo a; rm b", "echo a > f", "echo $(whoami)", "echo `id`"):
            with self.assertRaises(PermissionDenied, msg=cmd):
                self.call("commande_executer", command=cmd)

    def test_commande_hors_liste_et_chemin_hors_perimetre(self):
        with self.assertRaises(PermissionDenied):
            self.call("commande_executer", command="nmap localhost")
        with self.assertRaises(PermissionDenied):
            self.call("commande_executer", command=f"cat {self.env.outside}/x")

    def test_commande_sensible_demande_confirmation(self):
        with self.assertRaises(ConfirmationRequired):
            self.call("commande_executer", command="git push origin main")
        with self.assertRaises(ConfirmationRequired):
            self.call("commande_executer", command="python3 -c print(1)")

    def test_delai_maximum_tue_la_commande(self):
        import time
        from jarvis.errors import JarvisError
        (paths.workspace_dir() / "attente.py").write_text("import time\ntime.sleep(30)\n")
        t0 = time.time()
        with self.assertRaises(JarvisError) as cm:
            self.call("commande_executer", command="python3 attente.py", timeout_s=1)
        self.assertEqual(cm.exception.code, "delai_depasse")
        self.assertLess(time.time() - t0, 8)

    # -- registre ----------------------------------------------------------------------------
    def test_outil_inexistant_et_arguments_invalides(self):
        with self.assertRaises(ToolUnavailable):
            self.call("formater_le_disque")
        with self.assertRaises(ValidationError):
            self.call("fichier_lire")                         # paramètre obligatoire manquant
        with self.assertRaises(ValidationError):
            self.call("fichier_lire", path=42)                # mauvais type
        with self.assertRaises(ValidationError):
            self.call("fichier_lire", path="a", pirate=True)  # paramètre inconnu

    def test_lecture_web_d_adresses_locales_refusee(self):
        for url in ("http://127.0.0.1:8765/api/state", "http://localhost/", "http://192.168.1.1/"):
            with self.assertRaises(PermissionDenied, msg=url):
                self.call("web_lire_page", url=url)

    def test_brouillon_vers_adresse_ambigue_refuse(self):
        with self.assertRaises(ValidationError):
            self.call("email_brouillon_preparer", to=["pas une adresse"], subject="x", body="y")
        r = self.call("email_brouillon_preparer", to=["contact@exemple.fr"], subject="Test", body="Bonjour")
        self.assertFalse(r["result"]["sent"])

    def test_connecteur_gmail_indisponible_tant_que_non_active(self):
        with self.assertRaises(ToolUnavailable):
            self.call("gmail_rechercher", query="test")


if __name__ == "__main__":
    unittest.main()
