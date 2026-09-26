"""Disposable PostgreSQL persistence test. Requires Docker; no personal data or OpenAI calls."""
import os
import json
from pathlib import Path
import secrets
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def worker(phase):
    import django
    django.setup()
    from unittest.mock import patch
    from django.conf import settings
    from django.contrib.auth import get_user_model
    from django.core.management import call_command, CommandError
    from django.db import connection, IntegrityError
    from django.test import Client
    from context_me.library import Library
    from tests.test_core import fake_client, sample_document
    from webapp.storage import library
    from serve import main

    # Exercise the real startup/migration path without starting an HTTP listener.
    with patch("waitress.serve"):
        main()
    target = library()
    client = fake_client()
    cookie_path = Path(os.environ["TEST_COOKIE_PATH"])
    if phase == "publish":
        source = Library(settings.DATA_DIR / "source.sqlite3")
        source.add(sample_document(), client, "embedding-model")
        source.save_presentation("Persistent title", "Suomeksi ja englanniksi", "Saved explanation")
        client.embeddings.create.reset_mock()
        call_command("import_library", str(source.path))
        client.embeddings.create.assert_not_called()
        before = target.documents()
        # Exercise PostgreSQL publication, replacement, cascade deletion and rollback.
        extra = sample_document()
        extra["document_id"] = "extra-test-document"
        assert target.add(extra, client, "embedding-model")
        extra["chunks"][0]["text"] = "A revised fictional passage in Helsinki."
        assert target.add(extra, client, "embedding-model")
        with target.connect() as db:
            old_payload = db.execute("SELECT payload FROM documents WHERE id = ?", (extra["document_id"],)).fetchone()[0]
        extra["chunks"].append(extra["chunks"][0])
        try:
            target.add(extra, client, "embedding-model")
        except IntegrityError:
            pass
        else:
            raise AssertionError("Expected duplicate chunk failure")
        with target.connect() as db:
            assert db.execute("SELECT payload FROM documents WHERE id = ?", (extra["document_id"],)).fetchone()[0] == old_payload
        target.remove(extra["document_id"])
        with target.connect() as db:
            assert db.execute("SELECT COUNT(*) FROM chunks WHERE document_id = ?", (extra["document_id"],)).fetchone()[0] == 0
        target.save_presentation("Temporary", "Caption", "Explanation")
        target.save_presentation("Persistent title", "Suomeksi ja englanniksi", "Saved explanation")
        try:
            call_command("import_library", str(source.path))
        except CommandError:
            pass
        else:
            raise AssertionError("Import must reject a populated destination")
        assert target.documents() == before
        browser = Client()
        assert browser.login(username=os.environ["ADMIN_USERNAME"], password=os.environ["ADMIN_PASSWORD"])
        session = browser.session
        session["conversation"] = [{"role": "user", "content": "Persistence test"}]
        session.save()
        cookie_path.write_text(browser.cookies["sessionid"].value)
    else:
        assert target.documents(), "Documents lost after restart"
        assert target.presentation()["title"] == "Persistent title"
        assert "Helsinki" in target.search("Helsinki", client)[0]["text"]
        assert not (settings.DATA_DIR / "library.sqlite3").exists()
        assert not (settings.DATA_DIR / "web.sqlite3").exists()
        browser = Client()
        browser.cookies["sessionid"] = cookie_path.read_text()
        response = browser.get("/admin/library/")
        assert response.status_code == 200, "Administrator session lost after restart"
        assert browser.session["conversation"][0]["content"] == "Persistence test"
        assert get_user_model().objects.get(username=os.environ["ADMIN_USERNAME"]).is_superuser
        with target.connect() as db:
            document = json.loads(db.execute("SELECT payload FROM documents ORDER BY id").fetchone()[0])
        before = target.documents()
        assert not target.add(document, client, "embedding-model"), "Duplicate must not be re-embedded"
        document["chunks"][0]["text"] = "Changed text"
        client.embeddings.create.side_effect = RuntimeError("Simulated API outage")
        try:
            target.add(document, client, "embedding-model")
        except RuntimeError:
            pass
        else:
            raise AssertionError("Expected simulated indexing failure")
        assert target.documents() == before
        with connection.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM chunks")
            assert cursor.fetchone()[0] > 0
    print("PostgreSQL phase passed:", phase)


def main():
    env = dict(os.environ, POSTGRES_PASSWORD=secrets.token_urlsafe(24),
               CONTEXT_ME_LOAD_LOCAL_CONFIG="false", CONTEXT_ME_HOSTED="false",
               DJANGO_SETTINGS_MODULE="webapp.settings", DJANGO_SECRET_KEY=secrets.token_urlsafe(64),
               ADMIN_USERNAME="persistence-editor", ADMIN_PASSWORD=secrets.token_urlsafe(24),
               OPENAI_API_KEY="fake-key", DJANGO_ALLOWED_HOSTS="testserver,localhost,127.0.0.1")
    env.pop("K_SERVICE", None)
    env.pop("ADMIN_PREVIOUS_USERNAME", None)
    container = None
    def docker(*args):
        return subprocess.check_output(["docker", *args], env=env, text=True).strip()
    with tempfile.TemporaryDirectory() as tmp:
        try:
            container = docker("run", "--rm", "-d", "-p", "127.0.0.1::5432", "-e", "POSTGRES_PASSWORD",
                               "-e", "POSTGRES_DB=context_test", "postgres:17-alpine")
            port = docker("port", container, "5432/tcp").rsplit(":", 1)[1]
            env["DATABASE_URL"] = "postgresql://postgres:" + env["POSTGRES_PASSWORD"] + "@127.0.0.1:" + port + "/context_test?sslmode=disable"
            env["TEST_COOKIE_PATH"] = str(Path(tmp) / "session-cookie")
            for _ in range(60):
                result = subprocess.run(["docker", "exec", container, "pg_isready", "-U", "postgres"],
                                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                if result.returncode == 0:
                    break
                time.sleep(.5)
            else:
                raise RuntimeError("Disposable PostgreSQL did not start")
            for phase in ("publish", "restart"):
                env["CONTEXT_ME_DATA_DIR"] = str(Path(tmp) / phase)
                subprocess.run([sys.executable, str(Path(__file__).resolve()), "--worker", phase],
                               cwd=ROOT, env=env, check=True, timeout=120)
            # Two fresh app instances share the same library, account and session.
            children = []
            for number in range(2):
                child_env = dict(env, CONTEXT_ME_DATA_DIR=str(Path(tmp) / f"instance-{number}"))
                children.append(subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "--worker", "shared"],
                                                  cwd=ROOT, env=child_env))
            assert all(child.wait(timeout=120) == 0 for child in children)
            print("PASS: local-library import, fresh-instance persistence, shared sessions, deduplication and failed-update preservation.")
        finally:
            if container:
                docker("rm", "-f", container)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--worker":
        worker(sys.argv[2])
    else:
        main()
