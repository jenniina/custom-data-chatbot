"""Copy a surviving desktop library without regenerating embeddings."""
from pathlib import Path
import sqlite3

from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from webapp.storage import library


class Command(BaseCommand):
    help = "Copy a local library.sqlite3 into an empty PostgreSQL library. No OpenAI calls."

    def add_arguments(self, parser):
        parser.add_argument("source", type=Path)

    def handle(self, *args, **options):
        if connection.vendor != "postgresql":
            raise CommandError("Set DATABASE_URL to the destination PostgreSQL database first.")
        source = options["source"].resolve()
        if not source.is_file():
            raise CommandError("The source library.sqlite3 file does not exist.")
        # Read only, from a consistent snapshot. Never create or modify the source file.
        db = sqlite3.connect(source.as_uri() + "?mode=ro", uri=True)
        try:
            db.execute("BEGIN")
            documents = db.execute("SELECT id, source, model, payload FROM documents").fetchall()
            chunks = db.execute("SELECT id, document_id, payload, embedding FROM chunks").fetchall()
            presentation = db.execute("SELECT name, value FROM presentation").fetchall()
        except sqlite3.Error:
            raise CommandError("The source is not a readable chatbot library database.") from None
        finally:
            db.close()
        if not documents and not presentation:
            raise CommandError("The source library is empty; nothing was copied.")
        target = library()
        target.initialize()
        with target.connect(write=True) as dest:
            if any(dest.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                   for table in ("documents", "chunks", "presentation")):
                raise CommandError("The destination library must be empty. Existing data was not changed.")
            dest.executemany("INSERT INTO documents (id, source, model, payload) VALUES (?, ?, ?, ?)", documents)
            dest.executemany("INSERT INTO chunks (id, document_id, payload, embedding) VALUES (?, ?, ?, ?)", chunks)
            dest.executemany("INSERT INTO presentation (name, value) VALUES (?, ?)", presentation)
        self.stdout.write(f"Copied {len(documents)} documents and {len(chunks)} passages, including saved embeddings and appearance.")
