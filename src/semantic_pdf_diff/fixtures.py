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
from .recipes import Recipe

SCHEMA_VERSION = 4  # 2: failures recorded; 3: response.used; 4: keyed by the query's hash (see above)
# Each folder evaluated by models (a round's batch, a spot check, a review batch) keeps the answers
# its evaluation asked for (judges, escalation, confirmation, the post-mortem's analyst, query
# checks) in a fixture of its own, packed, out of the main one (the owner: "just so long as it's
# kept out of our main test fixture").
FOLDER_FIXTURE = "replay.zip"
FOLDER_WORKING = "replay.sqlite"  # the working copy beside it (git-ignored)
MODES = ("replay", "replay-or-record", "record-new")

def default_mode(path):
    """The mode a fixture named without one is used in (trials 2026-10-08, finding 1: a new file named alone failed,
    `replay` creating nothing): a .sqlite file records and replays, created if missing; a .zip, or a folder, is
    replayed, as nothing records into one. Strict replay is asked for by name (tests, CI)."""
    path = Path(path)
    return "replay" if path.suffix == ".zip" or path.is_dir() else "replay-or-record"

def check(path, mode):
    """Raise FixtureError if the fixture can't be used in this mode, without opening it: so a run fails before its
    store is bound or a source scanned."""
    path = Path(path)
    if path.is_dir():
        return
    if mode == "replay" and not path.exists():
        raise FixtureError(f"{path}: no such fixture (replay only reads one; name it without --fixture-mode replay "
                           "to create it and record into it)")
    if mode != "replay" and path.suffix == ".zip":
        raise FixtureError(f"{path}: record into a .sqlite fixture, then pack it (pdf-semantic-diff fixtures pack)")
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

def recipe_labels(parts):
    """(recipe hash, role, region, content, task) from a recipe (the caller's key tuple)."""
    recipe = Recipe(parts)
    digest = hashlib.sha256(json.dumps(list(recipe), default=str).encode()).hexdigest()[:16]
    return digest, str(recipe.role), str(recipe.region), str(recipe.content), str(recipe.task)

class Fixture:
    """An open fixture database: storage only (the replay policy is Replayer's). Used from the main thread only.
    readonly: nothing is written, not even which answers were used (fixtures.open's "read")."""

    def __init__(self, path, create=False, readonly=False):
        self.path, self.readonly = Path(path), readonly
        if not self.path.exists() and not create:
            raise FixtureError(f"{self.path}: no such fixture")
        new = not self.path.exists()
        self.db = sqlite3.connect(self.path.resolve().as_uri() + "?mode=ro", uri=True) if readonly else sqlite3.connect(self.path)
        if new:
            with self.db:
                self.db.executescript(SCHEMA)
                self.db.execute("INSERT INTO meta VALUES ('schema_version', ?)", (str(SCHEMA_VERSION),))
        version = self.db.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()
        if not version or int(version[0]) != SCHEMA_VERSION:
            self.db.close()
            raise FixtureError(f"{self.path} has fixture schema {version and version[0]}, expected {SCHEMA_VERSION}")
        if not readonly:
            with self.db:
                self.db.execute(SESSIONS)
        self.used = set()
        self.packed_to = None    # the zip an unpacked fixture came from (see folder_fixture)

    def log_session(self, responders, replayed, recorded, missing):
        """One run's use of this working file, for prune's guard (Replayer.close)."""
        if (replayed or recorded or missing) and not self.readonly:
            with self.db:
                self.db.execute("INSERT INTO session VALUES (?, ?, ?, ?, ?)",
                                (_now(), json.dumps(sorted(responders)), replayed, recorded, missing))

    def close(self):
        if self.used and not self.readonly:
            with self.db:
                now = _now()
                self.db.executemany("UPDATE response SET used=? WHERE query=? AND responder=? AND sample=?",
                                    [(now, *u) for u in sorted(self.used)])
        self.used = set()
        self.db.close()
        if self.packed_to is not None:  # packed again when its packed bytes would differ (packing is reproducible):
            data = packed(self.path)      # an answer that replaced a recorded failure counts, not only new rows
            if not self.packed_to.exists() or self.packed_to.read_bytes() != data:
                self.packed_to.write_bytes(data)
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
        if row is not None:
            self.used.add((query, responder, sample))  # written once, on close
        return row

    def record(self, query, responder, sample=0, *, outcome, answer="", error=None, usage=None, recorded=None,
               description=None, recipe=None):
        """Record an answer (or a failure: outcome `invalid` or `transient`, with its error), with
        the side tables' facts about the query. `recorded` keeps a carried answer's original date."""
        if outcome not in OUTCOMES:
            raise ValueError(f"outcome {outcome!r} is not one of {OUTCOMES}")
        with self.db:
            self.db.execute("INSERT OR REPLACE INTO response VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                            (query, responder, sample, outcome, answer, error, json.dumps(usage or {}, sort_keys=True),
                             recorded or datetime.now(timezone.utc).strftime("%Y-%m-%d"), _now()))
            if description is not None:
                self.db.execute("INSERT OR IGNORE INTO description VALUES (?, ?)",
                                (query, json.dumps(description, sort_keys=True)))
        if recipe is not None:
            self.note_recipe(query, recipe)

    def note_recipe(self, query, recipe):
        """A way the pipeline built a query (for summaries; several recipes may build one query)."""
        if self.readonly:
            return
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

class Replayer:
    """The replay policy over a fixture (code review 2026-10-01, A1: it was split between llm.Client and Fixture):
    which recorded answer a request gets (its sample), what's replayed and what's asked again, how an answer's
    outcome is recorded, and the counts. The client is transport and its cache; the fixture is storage.

    Modes: `replay` serves recorded answers and recorded failures, and marks anything unrecorded;
    `replay-or-record` serves recorded answers and asks again for the rest, recorded failures included;
    `record-new` replays the model's failures as failures too, asking only transient ones again.
    fresh_regions: the A/A control's extraction regions, answered afresh as another sample of the same query."""

    def __init__(self, fixture, mode="replay", responder="", fresh_regions=()):
        if mode not in MODES:
            raise ValueError(f"mode {mode!r} is not one of {MODES}")
        self.fixture, self.mode, self.responder = fixture, mode, responder
        self.fresh_regions = frozenset(fresh_regions or ())
        self.replayed, self.recorded, self.missing = 0, 0, []

    def sample(self, key):
        """Which answer to a query this run wants: 0, or 1 for the A/A control's fresh regions."""
        recipe = Recipe(key or ())
        return 1 if recipe.role == "extract" and recipe.region in self.fresh_regions else 0

    def lookup(self, query, key, parse):
        """("answer", parse(recorded)), ("failure", its error), ("ask", None) to ask the model, or ("unrecorded",
        None) when replaying a query nothing answers. parse may raise; then nothing was served."""
        row = self.fixture.answer(query, self.responder, self.sample(key))
        if row is not None and key is not None:
            self.fixture.note_recipe(query, key)
        if row is not None and row[0] != "ok" and (self.mode == "replay" or self.mode == "record-new" and row[0] == "invalid"):
            self.replayed += 1
            return "failure", row[2]
        if row is not None and row[0] == "ok":  # recorded failures in record modes fall through: asked again
            value = parse(row[1])
            self.replayed += 1
            return "answer", value
        if self.mode == "replay" and row is None:
            self.missing.append(list(key) if key else [query])
            return "unrecorded", None
        return "ask", None

    def record(self, query, key, answer, error, usage=None, description=None):
        """An answer, or the model's failure (error: its text), unless only replaying."""
        if self.mode == "replay":
            return
        from .llm import transient
        outcome = "ok" if error is None else "transient" if transient(error) else "invalid"
        self.fixture.record(query, self.responder, self.sample(key), outcome=outcome, answer=answer, error=error,
                            usage=usage, description=description, recipe=key)
        self.recorded += 1

    def usage(self):
        return {"path": str(self.fixture.path), "responder": self.responder, "mode": self.mode,
                "replayed": self.replayed, "recorded": self.recorded, "missing": len(self.missing)}

    def close(self):
        self.fixture.log_session({self.responder}, self.replayed, self.recorded, len(self.missing))
        self.fixture.close()

def open(path, mode="read"):  # noqa: A001 (fixtures.open, as the module's reader)
    """A fixture, open for one use (code review 2026-10-01, A1: five ways to open one, three working-file
    conventions, and read-only uses that could write):
    - read: to look at; nothing is written. A .zip is read from a temporary copy.
    - replay: answers served are marked used (prune's guard). A .zip is replayed from a temporary copy.
    - record: a .sqlite working file, created if missing; a .zip is refused (record, then pack).
    A folder is its own fixture (folder_fixture), whatever the mode."""
    import tempfile
    path = Path(path)
    if path.is_dir():
        return folder_fixture(path)
    if mode not in ("read", "replay", "record"):
        raise ValueError(f"mode {mode!r} is not read, replay or record")
    if path.suffix == ".zip":
        if mode == "record":
            raise FixtureError(f"{path}: record into a .sqlite fixture, then pack it (pdf-semantic-diff fixtures pack)")
        temp = tempfile.TemporaryDirectory(prefix="fixture-")
        fixture = Fixture(unpack(path, temp.name), readonly=mode == "read")
        fixture.temp = temp  # removed when the fixture closes
        return fixture
    return Fixture(path, create=mode == "record", readonly=mode == "read")

def pack(fixture, target):
    """Zip a fixture reproducibly: rows in key order, last-use times and sessions left out, fixed
    timestamps, so re-packing unchanged answers gives identical bytes (and a quiet git history)."""
    Path(target).write_bytes(packed(fixture))

def packed(fixture):
    """The bytes pack writes."""
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
    return buffer.getvalue()

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
    """A folder's own fixture, open for use. Answers are recorded in a working file beside the zip
    (FOLDER_WORKING, git-ignored), so each is kept the moment it's paid for: a crash once lost a run's
    answers from a temporary copy. On opening, answers the zip holds that the working file lacks
    (pulled from elsewhere) are merged in; on closing, the zip is packed again when the working file
    holds anything the zip lacks (compared as packed bytes). Packing is reproducible: a run that only replays
    leaves the zip's bytes."""
    import tempfile
    archive, working = Path(folder) / FOLDER_FIXTURE, Path(folder) / FOLDER_WORKING
    working.parent.mkdir(parents=True, exist_ok=True)
    fixture = Fixture(working, create=True)
    if archive.exists():
        with tempfile.TemporaryDirectory(prefix="folder-fixture-") as temp:
            path = unpack(archive, temp)
            with fixture.db:
                fixture.db.execute("ATTACH DATABASE ? AS packed", (str(path),))
                for table in ("response", "description", "recipe"):
                    fixture.db.execute(f"INSERT OR IGNORE INTO main.{table} SELECT * FROM packed.{table}")
            fixture.db.execute("DETACH DATABASE packed")
    fixture.packed_to = archive
    return fixture

def unpack(archive, folder):
    """Extract a zipped fixture's database into folder; returns its path."""
    with zipfile.ZipFile(archive) as z:
        (name,) = [n for n in z.namelist() if n.endswith(".sqlite")]
        target = Path(folder) / Path(name).name
        target.write_bytes(z.read(name))
    return target
