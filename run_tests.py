"""Run all tests with temporary storage and no real credentials or API calls."""
import os
from tempfile import TemporaryDirectory

if __name__ == "__main__":
    with TemporaryDirectory() as tmp:
        os.environ.update(CONTEXT_ME_LOAD_LOCAL_CONFIG="false", CONTEXT_ME_HOSTED="false",
                          CONTEXT_ME_DATA_DIR=tmp, DATABASE_URL="", ADMIN_PASSWORD="", OPENAI_API_KEY="fake-test-key",
                          OPENAI_EMBEDDING_MODEL="embedding-model", DJANGO_SETTINGS_MODULE="webapp.settings")
        os.environ.pop("K_SERVICE", None)
        import django
        django.setup()
        from django.core.management import call_command
        call_command("collectstatic", interactive=False, verbosity=0)
        call_command("test", "tests", verbosity=2)
