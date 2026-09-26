"""Document storage and search, with SQLite for desktop use."""

import json
from contextlib import contextmanager
from pathlib import Path
import sqlite3

import numpy as np

DEFAULT_PRESENTATION = {
    "title": "Context Me",
    "caption": "Your documents. Your questions. Answers with sources.",
    "explanation": "Ask about the background, experiences, preferences, or plans described in these documents.",
}


class Library:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    def initialize(self):
        with self.connect(write=True) as db:
            schema = """
                CREATE TABLE IF NOT EXISTS presentation (
                    name TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS documents (
                    id TEXT PRIMARY KEY, source TEXT NOT NULL, model TEXT NOT NULL,
                    payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS chunks (
                    id TEXT PRIMARY KEY, document_id TEXT NOT NULL,
                    payload TEXT NOT NULL, embedding TEXT NOT NULL,
                    FOREIGN KEY(document_id) REFERENCES documents(id) ON DELETE CASCADE);
            """
            for statement in schema.split(";"):
                if statement.strip():
                    db.execute(statement)

    @contextmanager
    def connect(self, write=False):
        db = sqlite3.connect(self.path, timeout=30)
        db.execute("PRAGMA foreign_keys = ON")
        try:
            with db:
                if write:
                    db.execute("BEGIN IMMEDIATE")
                yield db
        finally:
            db.close()

    def documents(self):
        with self.connect() as db:
            return db.execute("SELECT id, source, model FROM documents ORDER BY source").fetchall()

    def presentation(self):
        with self.connect() as db:
            saved = dict(db.execute("SELECT name, value FROM presentation").fetchall())
        return {name: saved.get(name, default) for name, default in DEFAULT_PRESENTATION.items()}

    def save_presentation(self, title, caption, explanation):
        values = {"title": title.strip(), "caption": caption.strip(), "explanation": explanation.strip()}
        if not values["title"]:
            raise ValueError("Please enter a title.")
        for name, maximum in (("title", 120), ("caption", 500), ("explanation", 3000)):
            if len(values[name]) > maximum:
                raise ValueError(f"The {name} must be at most {maximum} characters.")
        with self.connect(write=True) as db:
            db.executemany("INSERT INTO presentation (name, value) VALUES (?, ?) "
                           "ON CONFLICT (name) DO UPDATE SET value = excluded.value", values.items())

    def add(self, document, client, model):
        with self.connect() as db:
            existing = db.execute("SELECT payload, model FROM documents WHERE id = ?", (document["document_id"],)).fetchone()
        payload = json.dumps(document, sort_keys=True, ensure_ascii=False)
        if existing == (payload, model):
            return False
        if any(row[2] != model for row in self.documents()):
            raise ValueError("The library uses another embedding model. Remove existing documents before changing it.")
        vectors = []
        for offset in range(0, len(document["chunks"]), 32):
            batch = document["chunks"][offset:offset + 32]
            result = client.embeddings.create(model=model, input=[c["text"] for c in batch])
            embeddings = sorted(result.data, key=lambda item: item.index)
            if [item.index for item in embeddings] != list(range(len(batch))):
                raise ValueError("OpenAI returned an incomplete embedding batch. Nothing was saved.")
            vectors.extend(item.embedding for item in embeddings)
        matrix = np.asarray(vectors, dtype=float)
        if matrix.ndim != 2 or not np.isfinite(matrix).all() or (np.linalg.norm(matrix, axis=1) == 0).any():
            raise ValueError("OpenAI returned invalid embeddings. Nothing was saved.")
        # Atomic replacement: an API or database failure leaves the old document intact.
        with self.connect(write=True) as db:
            # Recheck after embedding: another publisher may have changed the model.
            models = db.execute("SELECT DISTINCT model FROM documents").fetchall()
            if any(row[0] != model for row in models):
                raise ValueError("The library uses another embedding model. Remove existing documents before changing it.")
            db.execute("DELETE FROM documents WHERE id = ?", (document["document_id"],))
            db.execute("INSERT INTO documents VALUES (?, ?, ?, ?)",
                       (document["document_id"], document["source"], model, payload))
            for chunk, vector in zip(document["chunks"], vectors):
                enriched = dict(chunk, source=document["source"])
                db.execute("INSERT INTO chunks VALUES (?, ?, ?, ?)",
                           (document["document_id"] + ":" + chunk["id"], document["document_id"],
                            json.dumps(enriched, ensure_ascii=False), json.dumps(vector)))
        return True

    def remove(self, document_id):
        with self.connect(write=True) as db:
            db.execute("DELETE FROM documents WHERE id = ?", (document_id,))

    def search(self, question, client, limit=6):
        docs = self.documents()
        if not docs:
            return []
        model = docs[0][2]
        result = client.embeddings.create(model=model, input=question)
        query = np.asarray(result.data[0].embedding, dtype=float)
        with self.connect() as db:
            rows = db.execute("SELECT chunks.payload, chunks.embedding FROM chunks "
                              "JOIN documents ON documents.id = chunks.document_id "
                              "WHERE documents.model = ? ORDER BY chunks.id", (model,)).fetchall()
        if not rows:
            return []
        vectors = np.asarray([json.loads(row[1]) for row in rows], dtype=float)
        if query.ndim != 1 or query.shape[0] != vectors.shape[1] or not np.isfinite(query).all() or np.linalg.norm(query) == 0:
            raise ValueError("Search embedding is invalid or incompatible. Rebuild your library.")
        scores = (vectors @ query) / (np.linalg.norm(vectors, axis=1) * np.linalg.norm(query))
        order = np.argsort(-scores)[:limit]
        return [dict(json.loads(rows[i][0]), score=float(scores[i])) for i in order]
