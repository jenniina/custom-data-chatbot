"""Use the same persistent PostgreSQL database as Django in hosted deployments."""
from contextlib import contextmanager

from django.conf import settings
from django.db import connection, transaction

from context_me.library import Library


class LibraryCursor:
    """Adapt the library's fixed, parameterized SQL to Django's cursor syntax."""
    def __init__(self, cursor):
        self.cursor = cursor

    def execute(self, sql, params=()):
        self.cursor.execute(sql.replace("?", "%s"), params)
        return self.cursor

    def executemany(self, sql, params):
        self.cursor.executemany(sql.replace("?", "%s"), params)


class PostgresLibrary(Library):
    def __init__(self):
        # Tables are initialized once at startup, not on every page request.
        pass

    @contextmanager
    def connect(self, write=False):
        with transaction.atomic():
            with connection.cursor() as cursor:
                if write:
                    # Serialize publication/removal across instances. Released on rollback too.
                    cursor.execute("SELECT pg_advisory_xact_lock(194381, 1)")
                yield LibraryCursor(cursor)


def library():
    if connection.vendor == "postgresql":
        return PostgresLibrary()
    return Library(settings.DATA_DIR / "library.sqlite3")
