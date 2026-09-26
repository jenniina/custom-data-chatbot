"""Parse private database settings without including credentials in errors."""
from django.core.exceptions import ImproperlyConfigured


def database_config(url, data_dir, cloud_run=False, allow_temporary=False):
    if not url:
        if cloud_run and not allow_temporary:
            raise ImproperlyConfigured(
                "Cloud Run requires DATABASE_URL for persistent PostgreSQL storage. "
                "Local SQLite files disappear when an instance stops.")
        return {"ENGINE": "django.db.backends.sqlite3", "NAME": data_dir / "web.sqlite3",
                "OPTIONS": {"timeout": 30}}
    if not url.startswith(("postgres://", "postgresql://")):
        raise ImproperlyConfigured("DATABASE_URL must be a PostgreSQL connection URL.")
    import psycopg
    try:
        options = psycopg.conninfo.conninfo_to_dict(url)
    except psycopg.Error:
        raise ImproperlyConfigured("DATABASE_URL is invalid. Copy the PostgreSQL connection URL from your provider.") from None
    if not all(options.get(key) for key in ("host", "dbname", "user", "password")):
        raise ImproperlyConfigured("DATABASE_URL must include host, database name, username and password.")
    local = options["host"] in ("localhost", "127.0.0.1", "::1")
    options.setdefault("sslmode", "disable" if local else "require")
    if not local and options["sslmode"] not in ("require", "verify-ca", "verify-full"):
        raise ImproperlyConfigured("Remote DATABASE_URL must require TLS (sslmode=require or verify-full).")
    options.setdefault("connect_timeout", "15")
    config = {"ENGINE": "django.db.backends.postgresql", "CONN_MAX_AGE": 0,
              "CONN_HEALTH_CHECKS": True, "DISABLE_SERVER_SIDE_CURSORS": True}
    for source, target in (("dbname", "NAME"), ("user", "USER"), ("password", "PASSWORD"),
                           ("host", "HOST"), ("port", "PORT")):
        config[target] = options.pop(source, "")
    options["prepare_threshold"] = None  # Compatible with transaction-mode poolers.
    config["OPTIONS"] = options
    return config
