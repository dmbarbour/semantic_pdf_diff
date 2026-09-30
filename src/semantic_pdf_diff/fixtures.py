"""Replay fixtures: how each model answered each query, for offline runs and model comparisons.

A query is what reaches a model (system and user text, image bytes, response format and
generation settings), named by its hash (llm.query_hash). A fixture holds triples: how
responder M answered query H, as its `sample`-th answer (0 unless asked for another, as the A/A
control does), with the outcome: `ok`, `invalid` (a failure of the model's: replayed as a failure)
or `transient` (timeouts, server errors: asked again when recording). Everything else is rebuilt
from the sample documents, so replaying the same runs forms the same reports. A changed query has
another hash: it's a miss, never a stale answer. (docs/plans/content-addressed-queries-2026-09-28.md)

Side tables hold what's convenient for summaries, never used for lookup: facts about each
query's own content (`description`) and how the pipeline built it (`recipe`: role, content,
task; possibly several per query). Each run's use of a working file is logged (`session`, not
packed) for prune's guard.

Modes (see Client): `replay` serves recorded answers and fails on anything unrecorded;
`replay-or-record` serves recorded answers and records live answers for the rest, asking
recorded failures again; `record-new` records only what was never asked, replaying the model's
failures as failures (a variant's run then differs from its baseline only where the variant
changes a query) and asking transient ones again.
"""
import hashlib
import io
import json
import sqlite3
import zipfile
from datetime import datetime, timezone
from pathlib import Path

SCHEMA_VERSION = 4  # 2: failures recorded; 3: response.used; 4: keyed by the query's hash (see above)
# Each folder evaluated by models (a round's batch, a spot check, a review batch) keeps the answers
# its evaluation asked for (judges, escalation, confirmation, the post-mortem's analyst, query
# checks) in a fixture of its own, packed, out of the main one (the owner: "just so long as it's
# kept out of our main test fixture").
FOLDER_FIXTURE = "replay.zip"
MODES = ("replay", "replay-or-record", "record-new")
OUTCOMES = ("ok", "invalid", "transient")

SCHEMA = """
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
-- The main table, and the only one lookups read: a responder's answer to a query, or its failure.
CREATE TABLE response (query TEXT NOT NULL, responder TEXT NOT NULL, sample INTEGER NOT NULL, outcome TEXT NOT NULL,
                       answer TEXT NOT NULL, error TEXT, usage TEXT NOT NULL, recorded TEXT NOT NULL, used TEXT,
                       PRIMARY KEY (query, responder, sample));
-- Facts about a query's own content (source type, sizes, generation settings), for summaries.
CREATE TABLE description (query TEXT PRIMARY KEY, data TEXT NOT NULL);
-- How the pipeline built a query (role, region, content, task and the rest of its recipe), for summaries.
CREATE TABLE recipe (query TEXT NOT NULL, recipe TEXT NOT NULL, role TEXT NOT NULL, region TEXT NOT NULL,
                     content TEXT NOT NULL, task TEXT NOT NULL, parts TEXT NOT NULL, PRIMARY KEY (query, recipe));
"""
# Each run's use of a fixture: what it replayed, recorded and missed. Prune reads it to refuse
# pruning on the strength of a replay that missed (one run with the wrong responder once emptied a
# fixture). Kept only in working files: pack leaves it out, so packed bytes don't change.
SESSIONS = """CREATE TABLE IF NOT EXISTS session (time TEXT NOT NULL, responders TEXT NOT NULL,
                  replayed INTEGER NOT NULL, recorded INTEGER NOT NULL, missing INTEGER NOT NULL)"""

class FixtureError(RuntimeError):
    pass

class NotRecorded(FixtureError):
    pass

def recipe_labels(parts):
    """(recipe hash, role, region, content, task) from a recipe (the caller's key tuple)."""
    parts = list(parts)
    role = str(parts[0]) if parts else ""
    region = str(parts[1]) if len(parts) > 1 else ""
    content = str(parts[2]) if role in ("extract", "triage") and len(parts) > 2 else ""
    task = str(parts[3]) if len(parts) > 3 else ""
    digest = hashlib.sha256(json.dumps(parts, default=str).encode()).hexdigest()[:16]
    return digest, role, region, content, task

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
            hint = " (keyed the old way: re-key it by replaying with --rekey-from)" if version and version[0] == "3" else ""
            raise FixtureError(f"{self.path} has fixture schema {version and version[0]}, expected {SCHEMA_VERSION}{hint}")
        with self.db:
            self.db.execute(SESSIONS)
        self.served, self.recorded, self.missing, self.used, self.responders = 0, 0, [], set(), set()
        self.changed = False     # anything recorded since opening (a packed fixture is packed again)
        self.packed_to = None    # the zip an unpacked fixture came from (see folder_fixture)

    def close(self):
        if self.used:
            with self.db:
                now = _now()
                self.db.executemany("UPDATE response SET used=? WHERE query=? AND responder=? AND sample=?",
                                    [(now, *u) for u in sorted(self.used)])
            self.used = set()
        if self.served or self.recorded or self.missing:
            with self.db:
                self.db.execute("INSERT INTO session VALUES (?, ?, ?, ?, ?)",
                                (_now(), json.dumps(sorted(self.responders)), self.served, self.recorded,
                                 len(self.missing)))
            self.served, self.recorded, self.missing = 0, 0, []
        self.db.close()
        if self.packed_to is not None and self.changed:
            pack(self.path, self.packed_to)
        legacy = getattr(self, "legacy", None)  # a schema-3 fixture being re-keyed into this one
        if legacy is not None:
            legacy.close()
        temp = getattr(self, "temp", None)  # an unpacked zip's folder
        if temp is not None:
            temp.cleanup()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def note(self, key, value):
        with self.db:
            self.db.execute("INSERT OR REPLACE INTO meta VALUES (?, ?)", (key, str(value)))

    def meta(self):
        return dict(self.db.execute("SELECT key, value FROM meta"))

    def answer(self, query, responder, sample=0):
        """(outcome, answer, error) as recorded, or None. Marks the answer as used (see prune)."""
        row = self.db.execute("SELECT outcome, answer, error FROM response WHERE query=? AND responder=? AND sample=?",
                              (query, responder, sample)).fetchone()
        self.responders.add(responder)
        if row is not None:
            self.used.add((query, responder, sample))  # written once, on close
        return row

    def record(self, query, responder, sample=0, *, outcome, answer="", error=None, usage=None, recorded=None,
               description=None, recipe=None):
        """Record an answer (or a failure: outcome `invalid` or `transient`, with its error), with
        the side tables' facts about the query. `recorded` keeps a re-keyed answer's original date."""
        if outcome not in OUTCOMES:
            raise ValueError(f"outcome {outcome!r} is not one of {OUTCOMES}")
        self.responders.add(responder)
        with self.db:
            self.db.execute("INSERT OR REPLACE INTO response VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                            (query, responder, sample, outcome, answer, error, json.dumps(usage or {}, sort_keys=True),
                             recorded or datetime.now(timezone.utc).strftime("%Y-%m-%d"), _now()))
            if description is not None:
                self.db.execute("INSERT OR IGNORE INTO description VALUES (?, ?)",
                                (query, json.dumps(description, sort_keys=True)))
        if recipe is not None:
            self.note_recipe(query, recipe)
        self.recorded += 1
        self.changed = True

    def note_recipe(self, query, recipe):
        """A way the pipeline built a query (for summaries; several recipes may build one query)."""
        with self.db:
            self.db.execute("INSERT OR IGNORE INTO recipe VALUES (?, ?, ?, ?, ?, ?, ?)",
                            (query, *recipe_labels(recipe), json.dumps(list(recipe), default=str)))

    def prune(self, before, responder=None, dry_run=False, force=False):
        """Drop answers not used (replayed or recorded) since `before` (ISO time), and side-table
        rows of queries left without answers. Returns the counts, and why it would refuse.

        Refuses (FixtureError; force overrides) when no run used the fixture since `before`,
        when a run since then missed requests (a wrong responder or settings replays nothing,
        and every answer looks unused), or when it would drop more than half the answers."""
        where = "(used IS NULL OR used < ?)" + (" AND responder = ?" if responder else "")
        args = (before, responder) if responder else (before,)
        answers = self.db.execute(f"SELECT COUNT(*) FROM response WHERE {where}", args).fetchone()[0]
        total = self.db.execute("SELECT COUNT(*) FROM response" + (" WHERE responder = ?" if responder else ""),
                                (responder,) if responder else ()).fetchone()[0]
        sessions = [(json.loads(r), m) for r, m in self.db.execute(
            "SELECT responders, missing FROM session WHERE time >= ?", (before,))]
        sessions = [(r, m) for r, m in sessions if not responder or responder in r]
        refused = []
        if not sessions:
            refused.append(f"no run replayed or recorded {responder or 'answers'} since {before}")
        missed = sum(m for _, m in sessions)
        if missed:
            refused.append(f"runs since {before} missed {missed} request(s): their answers may exist under "
                           "another responder or settings")
        if total and answers * 2 > total:
            refused.append(f"it would drop {answers} of {total} answers")
        if refused and not force and not dry_run:
            raise FixtureError("Not pruning: " + "; ".join(refused) + " (force to prune anyway)")
        if not dry_run:
            with self.db:
                self.db.execute(f"DELETE FROM response WHERE {where}", args)
                for table in ("description", "recipe"):
                    self.db.execute(f"DELETE FROM {table} WHERE query NOT IN (SELECT query FROM response)")
            self.db.execute("VACUUM")
        return {"answers_removed": answers, "dry_run": dry_run, "refused": refused if not force else []}

    def summary(self):
        """Answers per responder, role and outcome, with token usage, and the documents recorded
        from (from the side tables: a query's role is its first recipe's)."""
        rows = self.db.execute("""
            SELECT r.responder, COALESCE((SELECT role FROM recipe WHERE recipe.query = r.query ORDER BY recipe LIMIT 1), ''),
                   r.outcome, COUNT(*), SUM(json_extract(r.usage, '$.prompt_tokens')),
                   SUM(json_extract(r.usage, '$.completion_tokens'))
            FROM response r GROUP BY 1, 2, 3 ORDER BY 1, 2, 3""").fetchall()
        return {
            "meta": self.meta(),
            "queries": self.db.execute("SELECT COUNT(DISTINCT query) FROM response").fetchone()[0],
            "contents": [c for (c,) in self.db.execute("SELECT DISTINCT content FROM recipe WHERE content != '' "
                                                       "ORDER BY content")],
            "answers": [{"responder": responder, "role": role, "outcome": outcome, "answers": n,
                         "prompt_tokens": p or 0, "completion_tokens": c or 0}
                        for responder, role, outcome, n, p, c in rows],
        }

class LegacyFixture:
    """A schema-3 fixture (keyed by a hand-picked tuple and an interpreter fingerprint), read only
    to re-key its answers: Client(rekey_from=...) replays runs, finds each query here under its old
    key, and keeps the answer when the prompt and images it rebuilt are the ones recorded."""

    def __init__(self, path):
        self.path = Path(path)
        self.temp = None
        if self.path.suffix == ".zip":
            import tempfile
            self.temp = tempfile.TemporaryDirectory(prefix="fixture-v3-")
            self.path = unpack(self.path, self.temp.name)
        self.db = sqlite3.connect(f"file:{self.path}?mode=ro", uri=True)
        version = self.db.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()
        if not version or version[0] != "3":
            raise FixtureError(f"{path}: not a schema-3 fixture")
        self.fingerprints = {}
        self.matched, self.stale = 0, 0

    def close(self):
        self.db.close()
        if self.temp is not None:
            self.temp.cleanup()

    def lookup(self, recipe, settings, sample, responder, prompt, images):
        """(answer, error, usage, recorded) recorded for this recipe, if the recorded prompt and
        image hashes are exactly what the query now sends; else None (stale, or never recorded)."""
        role = recipe[0]
        if role not in self.fingerprints:
            from . import provenance
            make = {"extract": provenance.extraction_interpreter, "triage": provenance.triage_interpreter,
                    "compare": provenance.comparison_interpreter}.get(role)
            self.fingerprints[role] = _legacy_fingerprint(make(settings)) if make else ""
        parts = list(recipe)
        if parts[0] == "compare":  # the comparison's settings hash was left out of fixture keys
            parts[2] = ""
        key = hashlib.sha256(json.dumps(parts, sort_keys=True, default=str).encode()).hexdigest()
        row = self.db.execute(
            "SELECT q.prompt, q.images, r.answer, r.error, r.usage, r.recorded FROM request q JOIN response r "
            "ON r.key = q.key AND r.interpreter = q.interpreter WHERE q.key=? AND q.interpreter=? AND r.responder=?",
            (key, self.fingerprints[role], responder + ("#fresh" if sample else ""))).fetchone()
        if row is None:
            return None
        if row[0] != prompt or json.loads(row[1]) != list(images):
            self.stale += 1
            return None
        self.matched += 1
        return row[2], row[3], json.loads(row[4] or "{}"), row[5]

def _legacy_fingerprint(interpreter):
    """Schema 3's interpreter fingerprint: prompts and settings, without the model or the levers."""
    from .provenance import LEVERS
    settings = {k: v for k, v in interpreter.settings.items() if k != "model" and k not in LEVERS}
    data = json.dumps({"role": interpreter.role, "prompt_hash": interpreter.prompt_hash, "settings": settings},
                      sort_keys=True)
    return hashlib.sha256(data.encode()).hexdigest()[:16]

def pack(fixture, target):
    """Zip a fixture reproducibly: rows in key order, last-use times and sessions left out, fixed
    timestamps, so re-packing unchanged answers gives identical bytes (and a quiet git history)."""
    source = sqlite3.connect(fixture)
    memory = sqlite3.connect(":memory:")
    memory.executescript(SCHEMA)
    columns = {"response": "query, responder, sample, outcome, answer, error, usage, recorded, NULL"}  # 'used' isn't packed
    for table, order in (("meta", "key"), ("response", "query, responder, sample"), ("description", "query"),
                         ("recipe", "query, recipe")):
        rows = source.execute(f"SELECT {columns.get(table, '*')} FROM {table} ORDER BY {order}").fetchall()
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

def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

def _dump(db):  # pragma: no cover - Python < 3.11 lacks Connection.serialize
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        copy = sqlite3.connect(Path(d) / "f.sqlite")
        db.backup(copy)
        copy.close()
        return (Path(d) / "f.sqlite").read_bytes()

def folder_fixture(folder):
    """A folder's own fixture (FOLDER_FIXTURE), open for use: unpacked to a temporary file, and
    packed back on close when anything was recorded. Packing is reproducible, so a run that
    only replays leaves the zip's bytes as they were."""
    import tempfile
    archive = Path(folder) / FOLDER_FIXTURE
    temp = tempfile.TemporaryDirectory(prefix="folder-fixture-")
    path = unpack(archive, temp.name) if archive.exists() else Path(temp.name) / "replay.sqlite"
    fixture = Fixture(path, create=True)
    fixture.temp, fixture.packed_to = temp, archive
    return fixture

def unpack(archive, folder):
    """Extract a zipped fixture's database into folder; returns its path."""
    with zipfile.ZipFile(archive) as z:
        (name,) = [n for n in z.namelist() if n.endswith(".sqlite")]
        target = Path(folder) / Path(name).name
        target.write_bytes(z.read(name))
    return target
