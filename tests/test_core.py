"""Socle : base, migrations, persistance, configuration versionnée, journal expurgé, mémoire, projets, sauvegardes."""
import unittest

from jarvis.errors import NotFound, ValidationError
from jarvis.logbook import redact
from tests.helpers import TestEnv


class CoreTests(unittest.TestCase):
    def setUp(self):
        self.env = TestEnv()
        self.app = self.env.make_app()

    def tearDown(self):
        self.env.close()

    def test_migrations_et_schema(self):
        self.assertEqual(self.app.db.schema_version(), "0002_complements")
        cols = [r["name"] for r in self.app.db.all("PRAGMA table_info(tasks)")]
        self.assertIn("next_action", cols)
        self.assertEqual(self.app.db.one("PRAGMA integrity_check")["integrity_check"], "ok")

    def test_memoire_persiste_apres_redemarrage(self):
        m = self.app.memory.add("Sacha préfère des réponses courtes.", "preference", "test", "preference", "préférence exprimée")
        self.app.shutdown()
        self.app.db.close()
        app2 = self.env.make_app()
        self.assertEqual(app2.memory.get(m["id"])["content"], "Sacha préfère des réponses courtes.")
        self.assertEqual(app2.settings.get("autonomy.mode"), "execution_supervisee")

    def test_configuration_versionnee_et_restauree(self):
        v0 = self.app.settings.versions()[0]["id"]
        self.app.settings.update({"assistant": {"detail_level": "court"}}, "test")
        self.assertEqual(self.app.settings.get("assistant.detail_level"), "court")
        self.app.settings.restore_version(v0)
        self.assertEqual(self.app.settings.get("assistant.detail_level"), "normal")

    def test_configuration_valide(self):
        with self.assertRaises(ValidationError):
            self.app.settings.update({"autonomy": {"mode": "dieu"}})
        with self.assertRaises(ValidationError):
            self.app.settings.update({"voice": {"volume": 3}})

    def test_journal_expurge_les_secrets(self):
        self.assertNotIn("sk-ant-abcdefghijklmnop", redact("clé sk-ant-abcdefghijklmnopqrstu"))
        self.assertNotIn("hunter2", redact("password=hunter2"))
        self.assertNotIn("4111 1111 1111 1111", redact("carte 4111 1111 1111 1111"))
        self.assertIn("20261012-154900", redact("jarvis-20261012-154900.zip"))
        ev = self.app.logbook.log("test", "token: abcdefghijklmnopqrstuvwxyz123456")
        row = self.app.db.one("SELECT message FROM events WHERE id=?", (ev["id"],))
        self.assertNotIn("abcdefghijklmnopqrstuvwxyz123456", row["message"])

    def test_migration_d_une_base_v01_avec_sauvegarde(self):
        import sqlite3
        from jarvis import paths
        self.app.shutdown()
        self.app.db.close()
        self.app = None
        for ext in ("", "-wal", "-shm"):
            p = paths.db_path().with_name(paths.db_path().name + ext)
            if p.exists():
                p.unlink()
        # base telle que livrée en v0.1 : seulement 0001, avec une donnée
        c = sqlite3.connect(str(paths.db_path()))
        c.executescript((paths.MIGRATIONS_DIR / "0001_init.sql").read_text(encoding="utf-8"))
        c.execute("CREATE TABLE schema_migrations (version TEXT PRIMARY KEY, applied_at TEXT NOT NULL)")
        c.execute("INSERT INTO schema_migrations VALUES ('0001_init', '2026-10-12')")
        c.execute("INSERT INTO memories(type, nature, content, source, status, created_at, updated_at) "
                  "VALUES ('connaissance','fait','Donnée de la v0.1.','test','valide','2026-10-12','2026-10-12')")
        c.commit()
        c.close()
        app = self.env.make_app()
        self.app = app
        self.assertEqual(app.migrations, ["0002_complements"])
        self.assertEqual(app.memory.search("v0.1")[0]["content"], "Donnée de la v0.1.")
        self.assertTrue(list(paths.backups_dir().glob("*avant-migration*")))

    def test_memoire_temporaire_expire(self):
        m = self.app.memory.add("Code d'accès du parking visiteurs B2 aujourd'hui.", "temporaire", expires_at="2000-01-01T00:00:00")
        self.assertEqual(self.app.memory.search("parking"), [])
        self.assertEqual(self.app.memory.purge_expired(), 1)
        t = self.app.memory.add("Rendez-vous chez Da Marco reporté à jeudi.", "temporaire")
        self.assertTrue(t["expires_at"])

    def test_memoire_contradiction_signalee(self):
        self.app.memory.add("Le restaurant Da Marco ferme le lundi.", "connaissance")
        m = self.app.memory.add("Le restaurant Da Marco ferme le mardi.", "connaissance")
        self.assertEqual(m["status"], "a_verifier")
        self.assertEqual(len(m["possible_conflicts"]), 1)

    def test_memoire_refuse_les_secrets(self):
        with self.assertRaises(ValidationError):
            self.app.memory.add("Mon mot de passe Gmail est soleil123", "info_personnelle")
        with self.assertRaises(ValidationError):
            self.app.memory.add("clé sk-ant-api03-abcdefghijklmnop", "connaissance")

    def test_memoire_recherche_doublons_correction_oubli_export(self):
        a = self.app.memory.add("Le restaurant Da Marco ouvre à 19 h.", "connaissance", "test")
        b = self.app.memory.add("le restaurant da marco ouvre à 19 h", "connaissance", "test")
        self.assertTrue(b.get("duplicate_of_existing"))
        self.assertEqual(self.app.memory.search("marco")[0]["id"], a["id"])
        self.app.memory.update(a["id"], content="Le restaurant Da Marco ouvre à 18 h 30.", nature="fait")
        self.assertIn("18 h 30", self.app.memory.get(a["id"])["content"])
        exp = self.app.memory.export()
        self.app.memory.forget(a["id"])
        with self.assertRaises(NotFound):
            self.app.memory.get(a["id"])
        r = self.app.memory.import_(exp)
        self.assertEqual(r["added"], 1)

    def test_memoire_par_projet_isolee_et_supprimable(self):
        p1 = self.app.projects.create("Projet A")
        p2 = self.app.projects.create("Projet B")
        self.app.memory.add("Couleur principale : bleu.", "decision", project_id=p1["id"])
        self.app.memory.add("Couleur principale : rouge.", "decision", project_id=p2["id"])
        res = self.app.memory.search("couleur", project_id=p1["id"])
        self.assertEqual([m["content"] for m in res], ["Couleur principale : bleu."])
        self.assertEqual(self.app.memory.forget_project(p1["id"]), 1)

    def test_projet_ne_se_termine_pas_sans_criteres(self):
        p = self.app.projects.create("Site Da Marco", success_criteria="Site en ligne validé par le client")
        self.app.tasks.create("Valider les textes", kind="todo", project_id=p["id"], start=False)
        with self.assertRaises(ValidationError):
            self.app.projects.update(p["id"], status="termine")
        self.assertIn("Valider les textes", self.app.projects.report(p["id"]))

    def test_sauvegarde_verifiee_et_restauration(self):
        self.app.memory.add("Information à restaurer.", "connaissance")
        b = self.app.backups.create("test")
        self.assertTrue(b["verification"]["ok"])
        self.assertEqual(b["verification"]["counts"]["memories"], 1)
        self.app.memory.add("Information ajoutée après la sauvegarde.", "connaissance")
        name = b["path"].split("/")[-1]
        self.app.backups.restore(name)
        self.app.shutdown()
        self.app.db.close()
        app2 = self.env.make_app()
        self.assertTrue(app2.restored)
        self.assertEqual(len(app2.memory.search("")), 1)

    def test_sauvegarde_ne_contient_pas_de_secret(self):
        import zipfile
        b = self.app.backups.create("test")
        with zipfile.ZipFile(b["path"]) as z:
            self.assertEqual(sorted(z.namelist()), ["config.json", "jarvis.db", "manifest.json"])
            self.assertNotIn(b"token", z.read("config.json").lower().replace(b"tokens", b""))

    def test_diagnostic(self):
        d = self.app.diagnostics.run()
        names = [c["composant"] for c in d["checks"]]
        self.assertIn("Base de données", names)
        self.assertTrue(next(c for c in d["checks"] if c["composant"] == "Base de données")["ok"])


if __name__ == "__main__":
    unittest.main()
