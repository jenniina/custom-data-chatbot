"""Local/Cloud Run launcher with persistent PostgreSQL support."""
import os
from contextlib import nullcontext
from django.core.management import call_command

def listen_address(hosted, environ=None):
    """Cloud Run's injected PORT wins; 8501 is only the desktop default."""
    environ = os.environ if environ is None else environ
    try:
        port = int(environ.get("PORT", "8080" if hosted else "8501"))
    except (TypeError, ValueError):
        raise ValueError("PORT must be an integer between 1 and 65535.") from None
    if not 1 <= port <= 65535:
        raise ValueError("PORT must be an integer between 1 and 65535.")
    return ("0.0.0.0" if hosted else "127.0.0.1"), port

def main():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "webapp.settings")
    import django
    print("Startup: loading Django configuration. Configuration errors below prevent the port from opening.", flush=True)
    django.setup()
    from django.conf import settings
    host, port = listen_address(settings.HOSTED)
    print(f"Startup: target address {host}:{port} (PORT environment variable takes precedence).", flush=True)
    from django.db import connection, transaction
    # Multiple instances may start simultaneously; serialize database setup.
    with transaction.atomic() if connection.vendor == "postgresql" else nullcontext():
        if connection.vendor == "postgresql":
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_advisory_xact_lock(194381, 2)")
        for command in ("migrate", "init_library", "sync_admin", "clearsessions"):
            print(f"Startup: running {command}.", flush=True)
            options = {"interactive": False, "verbosity": 0} if command == "migrate" else {}
            call_command(command, **options)
    call_command("collectstatic", interactive=False, verbosity=0)
    from waitress import serve
    from webapp.wsgi import application
    print(f"Startup: launching HTTP server on {host}:{port}.", flush=True)
    proxy = {"trusted_proxy": "*", "trusted_proxy_headers": {"x-forwarded-proto"}} if settings.HOSTED else {}
    serve(application, host=host, port=port, threads=4, max_request_body_size=22 * 1024 * 1024, **proxy)

if __name__ == "__main__":
    main()
