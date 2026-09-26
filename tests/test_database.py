from pathlib import Path
from unittest import TestCase
from django.core.exceptions import ImproperlyConfigured
from webapp.database import database_config


class DatabaseConfigTests(TestCase):
    def test_desktop_remains_local(self):
        config = database_config("", Path("example"))
        self.assertEqual(config["NAME"], Path("example/web.sqlite3"))

    def test_cloud_run_requires_persistent_database(self):
        with self.assertRaisesRegex(ImproperlyConfigured, "requires DATABASE_URL"):
            database_config("", Path("example"), cloud_run=True)

    def test_postgres_credentials_and_pooler_options(self):
        config = database_config("postgresql://editor:p%40ss%2Fword@db.example/test?sslmode=require&channel_binding=require", Path("example"))
        self.assertEqual(config["PASSWORD"], "p@ss/word")
        self.assertEqual(config["NAME"], "test")
        self.assertEqual(config["OPTIONS"]["channel_binding"], "require")
        self.assertTrue(config["DISABLE_SERVER_SIDE_CURSORS"])
        self.assertIsNone(config["OPTIONS"]["prepare_threshold"])
        self.assertEqual(config["CONN_MAX_AGE"], 0)

    def test_remote_connections_require_tls(self):
        for mode in ("disable", "allow", "prefer"):
            with self.subTest(mode=mode), self.assertRaises(ImproperlyConfigured):
                database_config("postgresql://u:p@db.example/test?sslmode=" + mode, Path("example"))
        config = database_config("postgresql://u:p@db.example/test", Path("example"))
        self.assertEqual(config["OPTIONS"]["sslmode"], "require")

    def test_invalid_urls_do_not_reveal_secrets_or_fall_back(self):
        for url in ("sqlite:///secret", "postgresql://u:TOPSECRET@host/db?bad=1", "postgresql://host/db"):
            with self.subTest(url=url), self.assertRaises(ImproperlyConfigured) as error:
                database_config(url, Path("example"))
            self.assertNotIn("TOPSECRET", str(error.exception))
