"""API locale (jeton, hôte, origine, réglages sensibles), outils fichiers/documents/sites, automatisations."""
import json
import threading
import time
import unittest
import urllib.error
import urllib.request
import zipfile

from jarvis import paths
from jarvis.errors import ValidationError
from jarvis.server import serve
from jarvis.tools.registry import ToolContext
from tests.helpers import TestEnv


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.env = TestEnv()
        self.app = self.env.make_app()
        self.srv = serve(self.app, 0, "jeton-de-test")
        self.port = self.srv.server_address[1]
        # Le contrôle d'hôte dépend du port : on recrée le serveur sur le port attribué.
        self.srv.server_close()
        self.srv = serve(self.app, self.port, "jeton-de-test")
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    def tearDown(self):
        self.srv.shutdown()
        self.srv.server_close()
        self.env.close()

    def req(self, method, path, body=None, token="jeton-de-test", host=None, origin=None):
        h = {"Host": host or f"127.0.0.1:{self.port}"}
        if token:
            h["X-Jarvis-Token"] = token
        if origin:
            h["Origin"] = origin
        data = json.dumps(body).encode() if body is not None else None
        if data:
            h["Content-Type"] = "application/json"
        r = urllib.request.Request(f"http://127.0.0.1:{self.port}{path}", data=data, method=method, headers=h)
        try:
            with urllib.request.urlopen(r, timeout=10) as resp:
                return resp.status, json.loads(resp.read() or b"{}") if "json" in resp.headers.get("Content-Type", "") else resp.read()
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read() or b"{}")

    def test_sante_sans_jeton(self):
        self.assertEqual(self.req("GET", "/api/health", token=None)[0], 200)

    def test_api_exige_le_jeton(self):
        self.assertEqual(self.req("GET", "/api/state", token=None)[0], 401)
        self.assertEqual(self.req("GET", "/api/state", token="faux")[0], 401)
        code, body = self.req("GET", "/api/state")
        self.assertEqual(code, 200)
        self.assertEqual(body["data"]["mode"], "execution_supervisee")

    def test_hote_et_origine_etrangers_refuses(self):
        self.assertEqual(self.req("GET", "/api/state", host="evil.example:80")[0], 403)
        self.assertEqual(self.req("POST", "/api/chat", {"text": "x"}, origin="https://evil.example")[0], 403)

    def test_page_injecte_le_jeton_et_csp(self):
        r = urllib.request.Request(f"http://127.0.0.1:{self.port}/", headers={"Host": f"127.0.0.1:{self.port}"})
        with urllib.request.urlopen(r) as resp:
            html = resp.read().decode()
            self.assertIn("jeton-de-test", html)
            self.assertIn("script-src 'self'", resp.headers["Content-Security-Policy"])

    def test_reglage_sensible_exige_confirmation(self):
        code, body = self.req("PATCH", "/api/settings", {"autonomy": {"mode": "developpement"}})
        self.assertEqual(code, 409)
        self.assertEqual(self.app.settings.get("autonomy.mode"), "execution_supervisee")
        cid = body["error"]["details"]["confirmation_id"]
        code, _ = self.req("POST", f"/api/confirmations/{cid}", {"approve": True})
        self.assertEqual(code, 200)
        self.assertEqual(self.app.settings.get("autonomy.mode"), "developpement")

    def test_reglage_ordinaire_direct(self):
        code, _ = self.req("PATCH", "/api/settings", {"assistant": {"detail_level": "court"}})
        self.assertEqual(code, 200)
        self.assertEqual(self.app.settings.get("assistant.detail_level"), "court")

    def test_tache_creee_puis_annulee_via_api(self):
        code, body = self.req("POST", "/api/tasks", {"title": "Appeler le client", "execute": False})
        self.assertEqual(code, 200)
        tid = body["data"]["id"]
        code, body = self.req("POST", f"/api/tasks/{tid}/cancel")
        self.assertEqual(body["data"]["status"], "annulee")

    def test_parametres_invalides_erreur_structuree(self):
        code, body = self.req("POST", "/api/tools/fichier_lire/invoke", {"args": {"path": 5}})
        self.assertEqual(code, 400)
        self.assertEqual(body["error"]["code"], "parametres_invalides")
        code, body = self.req("POST", "/api/tools/fichier_lire/invoke", {"args": {"path": "inexistant.txt"}})
        self.assertEqual(code, 404)


class ToolsTests(unittest.TestCase):
    def setUp(self):
        self.env = TestEnv()
        self.app = self.env.make_app()
        self.ctx = ToolContext(self.app, cancel_event=threading.Event())

    def tearDown(self):
        self.env.close()

    def call(self, tool, **args):
        return self.app.tools.invoke(tool, args, self.ctx)

    def test_ecriture_lecture_version_precedente(self):
        r = self.call("fichier_ecrire", path="d/n.md", content="v1")
        self.assertEqual(r["state"], "confirme")
        with self.assertRaises(ValidationError):
            self.call("fichier_ecrire", path="d/n.md", content="v2")
        r = self.call("fichier_ecrire", path="d/n.md", content="v2", mode="overwrite")
        self.assertTrue(r["result"]["previous_version"])
        self.assertEqual(self.call("fichier_lire", path="d/n.md")["result"]["content"], "v2")

    def test_deplacement_copie_comparaison_doublons_archive(self):
        self.call("fichier_ecrire", path="a.txt", content="ligne 1\nligne 2\n")
        self.assertEqual(self.call("fichier_copier", src="a.txt", dst="b.txt")["state"], "confirme")
        self.assertTrue(self.call("fichiers_comparer", a="a.txt", b="b.txt")["result"]["identical"])
        self.assertEqual(self.call("doublons_detecter")["result"]["count"], 1)
        self.assertEqual(self.call("fichier_deplacer", src="b.txt", dst="rangement/b.txt")["state"], "confirme")
        with self.assertRaises(ValidationError):
            self.call("fichier_copier", src="a.txt", dst="rangement/b.txt")   # n'écrase jamais
        self.assertEqual(self.call("archive_creer", paths=["a.txt", "rangement"], dest="archive.zip")["state"], "confirme")
        self.assertEqual(len(self.call("contenu_rechercher", query="ligne 2")["result"]["hits"]), 2)  # a.txt et rangement/b.txt

    def test_documents_formats(self):
        for fmt in ("md", "html", "docx", "xlsx", "csv", "json"):
            content = '{"a": 1}' if fmt == "json" else "# Titre\n\n- point 1\n- point 2\n\n| a | b |\n|---|---|\n| 1 | 2 |"
            args = {"path": f"docs/test.{fmt}", "format": fmt, "content": content, "title": "Test"}
            if fmt in ("xlsx", "csv"):
                args = {"path": f"docs/test.{fmt}", "format": fmt, "rows": [["Nom", "Montant"], ["Site", 900]]}
            r = self.call("document_creer", **args)
            self.assertEqual(r["state"], "confirme", f"{fmt} : {r['verification']}")
        with zipfile.ZipFile(paths.workspace_dir() / "docs" / "test.xlsx") as z:
            self.assertIn("Montant", z.read("xl/worksheets/sheet1.xml").decode())
        text = self.call("fichier_lire", path="docs/test.docx")["result"]["content"]
        self.assertIn("Titre", text)

    def test_document_pdf(self):
        import os
        from jarvis.tools.documents import CHROME
        if not os.path.exists(CHROME):
            self.skipTest("Chrome absent")
        r = self.call("document_creer", path="docs/rapport.pdf", format="pdf", content="# Rapport\n\nTexte.", title="Rapport")
        self.assertEqual(r["state"], "confirme")
        self.assertIn("Rapport", self.call("fichier_lire", path="docs/rapport.pdf")["result"]["content"])

    def test_controle_de_site_detecte_puis_valide(self):
        site = paths.workspace_dir() / "sites" / "demo"
        site.mkdir(parents=True)
        (site / "index.html").write_text("<html><body><img src='x.png'><a href='absent.html'>x</a></body></html>")
        r = self.call("site_controler", dir=str(site))
        self.assertEqual(r["state"], "echoue")
        msgs = " ".join(i["message"] for i in r["result"]["issues"])
        for expected in ("title", "description", "viewport", "lang", "alternatif", "cassé"):
            self.assertIn(expected, msgs)
        (site / "index.html").write_text('<!doctype html><html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">'
                                         '<title>Démo</title><meta name="description" content="Site de démonstration"></head><body><h1>Démo</h1>'
                                         '<a href="contact.html">Contact</a></body></html>')
        (site / "contact.html").write_text('<!doctype html><html lang="fr"><head><meta name="viewport" content="width=device-width"><title>Contact</title>'
                                           '<meta name="description" content="Contact"></head><body><h1>Contact</h1><form action="/merci">'
                                           '<label for="m">E-mail</label><input id="m" type="email"></form></body></html>')
        r = self.call("site_controler", dir=str(site))
        self.assertEqual(r["state"], "confirme", r["result"]["issues"])
        r = self.call("site_preparer_deploiement", dir=str(site))
        self.assertEqual(r["state"], "confirme")
        self.assertFalse(r["result"]["published"])

    def test_apercu_local_puis_arret(self):
        site = paths.workspace_dir() / "s"
        site.mkdir()
        (site / "index.html").write_text("<h1>ok</h1>")
        r = self.call("apercu_lancer", dir=str(site))
        self.assertEqual(r["state"], "confirme", r["verification"])
        self.assertTrue(r["result"]["url"].startswith("http://127.0.0.1:"))
        self.call("processus_arreter", process_id=r["result"]["process_id"])

    def test_automatisations(self):
        s = self.app.scheduler
        with self.assertRaises(ValidationError):
            s.create("trop rapide", {"type": "intervalle", "minutes": 1}, {"type": "bilan_quotidien"})
        a = s.create("bilan", {"type": "quotidien", "heure": "18:30"}, {"type": "bilan_quotidien"})
        self.assertFalse(a["enabled"])
        out = s.run(a["id"], "manuel")
        self.assertTrue(out["ok"], out)
        self.assertTrue(list((paths.workspace_dir() / "rapports").glob("*bilan-quotidien.md")))
        bad = s.create("tests", {"type": "manuel"}, {"type": "tests_projet", "dir": str(paths.workspace_dir())}, max_retries=0)
        self.app.db.execute("UPDATE automations SET stop_after_failures=2, enabled=1 WHERE id=?", (bad["id"],))
        for _ in range(2):
            s.run(bad["id"], "manuel")
        self.assertFalse(s.get(bad["id"])["enabled"], "désactivée après 2 échecs")

    def test_rappel_echu_notifie(self):
        self.app.reminders.add("Appeler Marco", "2020-01-01T09:00")
        self.app.settings.update({"notifications": {"macos": False}})
        self.app.scheduler.tick()
        self.assertEqual(self.app.db.one("SELECT count(*) AS n FROM notifications WHERE kind='rappel'")["n"], 1)
        self.app.scheduler.tick()
        self.assertEqual(self.app.db.one("SELECT count(*) AS n FROM notifications WHERE kind='rappel'")["n"], 1)


if __name__ == "__main__":
    unittest.main()
