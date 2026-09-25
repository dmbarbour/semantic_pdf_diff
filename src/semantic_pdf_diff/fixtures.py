"""Replay fixtures: recorded model answers, keyed by meaning, for offline runs and model comparisons.

A fixture is a SQLite file (zipped when committed). Each request the pipeline makes is
identified by its semantic key (the response-cache key: task kind, content, locator, input
hash, crop) plus a fingerprint of the interpreter that shaped it (prompts and output-shaping
settings, but not the model or library versions). Answers are stored per responder, so one
fixture can hold several models' answers to the same requests.

Modes (see Client): `replay` serves recorded answers and fails on anything unrecorded;
`replay-or-record` serves recorded answers and records live answers for the rest.
"""
import hashlib
import io
import json
import sqlite3
import zipfile
from datetime import datetime, timezone
from pathlib import Path

SCHEMA_VERSION = 1
MODES = ("replay", "replay-or-record")

SCHEMA = """
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
-- One row per request: what was asked. Prompts are kept so answers can be read and judged.
CREATE TABLE request (key TEXT NOT NULL, interpreter TEXT NOT NULL, kind TEXT NOT NULL, region TEXT NOT NULL,
                      content TEXT NOT NULL, key_parts TEXT NOT NULL, prompt TEXT NOT NULL, images TEXT NOT NULL,
                      schema TEXT NOT NULL, PRIMARY KEY (key, interpreter));
-- One row per answer: a responder's reply to a request.
CREATE TABLE response (key TEXT NOT NULL, interpreter TEXT NOT NULL, responder TEXT NOT NULL, answer TEXT NOT NULL,
                       usage TEXT NOT NULL, recorded TEXT NOT NULL, PRIMARY KEY (key, interpreter, responder));
-- The interpreter descriptions behind each fingerprint, for reading.
CREATE TABLE interpreter (fingerprint TEXT PRIMARY KEY, role TEXT NOT NULL, description TEXT NOT NULL);
"""

class FixtureError(RuntimeError):
    pass

class NotRecorded(FixtureError):
    pass

def fingerprint(interpreter):
    """What shapes an answer besides the model: prompts and output-shaping settings.

    The model is the responder; library versions are left out so that an upgrade that
    changes nothing a request depends on doesn't invalidate recorded answers (if it does
    change the input, the input hash in the key changes)."""
    settings = {k: v for k, v in interpreter.settings.items() if k != "model"}
    data = json.dumps({"role": interpreter.role, "prompt_hash": interpreter.prompt_hash, "settings": settings},
                      sort_keys=True)
    return hashlib.sha256(data.encode()).hexdigest()[:16]

class Fixture:
    """An open fixture database. Used from the main thread only."""

    def __init__(self, path, create=False):
        self.path = Path(path)
        if not self.path.exists() and not create:
            raise FixtureError(f"{self.path}: no such fixture")
        new = not self.path.exists()
        self.db = sqlite3.connect(self.path)
        if new:
            with self.db:
                self.db.executescript(SCHEMA)
                self.db.execute("INSERT INTO meta VALUES ('schema_version', ?)", (str(SCHEMA_VERSION),))
        version = self.db.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()
        if not version or int(version[0]) != SCHEMA_VERSION:
            self.db.close()
            raise FixtureError(f"{self.path} has fixture schema {version and version[0]}, expected {SCHEMA_VERSION}")
        self.served, self.recorded, self.missing = 0, 0, []

    def close(self):
        self.db.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def answer(self, key, interpreter, responder):
        row = self.db.execute("SELECT answer FROM response WHERE key=? AND interpreter=? AND responder=?",
                              (key, interpreter, responder)).fetchone()
        return row[0] if row else None

    def record(self, key, interpreter, responder, *, kind, region, content, key_parts, prompt, images, schema,
               answer, usage=None, description=None, role=""):
        with self.db:
            self.db.execute("INSERT OR IGNORE INTO request VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                            (key, interpreter, kind, region, content, json.dumps(key_parts, default=str), prompt,
                             json.dumps(images), schema))
            self.db.execute("INSERT OR REPLACE INTO response VALUES (?, ?, ?, ?, ?, ?)",
                            (key, interpreter, responder, answer, json.dumps(usage or {}, sort_keys=True),
                             datetime.now(timezone.utc).strftime("%Y-%m-%d")))
            if description is not None:
                self.db.execute("INSERT OR IGNORE INTO interpreter VALUES (?, ?, ?)",
                                (interpreter, role, json.dumps(description, sort_keys=True)))
        self.recorded += 1

    def summary(self):
        """Requests and answers per responder, kind and interpreter, with token usage."""
        rows = self.db.execute("""
            SELECT r.responder, q.kind, r.interpreter, COUNT(*), SUM(json_extract(r.usage, '$.prompt_tokens')),
                   SUM(json_extract(r.usage, '$.completion_tokens'))
            FROM response r JOIN request q ON q.key = r.key AND q.interpreter = r.interpreter
            GROUP BY r.responder, q.kind, r.interpreter ORDER BY r.responder, q.kind, r.interpreter""").fetchall()
        return {
            "requests": self.db.execute("SELECT COUNT(*) FROM request").fetchone()[0],
            "contents": [c for (c,) in self.db.execute("SELECT DISTINCT content FROM request WHERE content != '' ORDER BY content")],
            "answers": [{"responder": a, "kind": b, "interpreter": c, "answers": d, "prompt_tokens": e or 0,
                         "completion_tokens": f or 0} for a, b, c, d, e, f in rows],
        }

def pack(fixture, target):
    """Zip a fixture reproducibly: rows in sorted order, fixed timestamps, so unchanged data
    packs to identical bytes."""
    source = sqlite3.connect(fixture)
    memory = sqlite3.connect(":memory:")
    memory.executescript(SCHEMA)
    for table, order in (("meta", "key"), ("request", "key, interpreter"), ("response", "key, interpreter, responder"),
                         ("interpreter", "fingerprint")):
        rows = source.execute(f"SELECT * FROM {table} ORDER BY {order}").fetchall()
        if rows:
            marks = ",".join("?" * len(rows[0]))
            memory.executemany(f"INSERT INTO {table} VALUES ({marks})", rows)
    memory.commit()
    source.close()
    data = memory.serialize() if hasattr(memory, "serialize") else _dump(memory)
    memory.close()
    info = zipfile.ZipInfo(Path(fixture).name, date_time=(2000, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(info, bytes(data))
    Path(target).write_bytes(buffer.getvalue())

def _dump(db):  # pragma: no cover - Python < 3.11 lacks Connection.serialize
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        copy = sqlite3.connect(Path(d) / "f.sqlite")
        db.backup(copy)
        copy.close()
        return (Path(d) / "f.sqlite").read_bytes()

def unpack(archive, folder):
    """Extract a zipped fixture's database into folder; returns its path."""
    with zipfile.ZipFile(archive) as z:
        (name,) = [n for n in z.namelist() if n.endswith(".sqlite")]
        target = Path(folder) / Path(name).name
        target.write_bytes(z.read(name))
    return target
