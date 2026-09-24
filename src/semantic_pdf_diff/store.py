"""A persistent, content-addressed evidence store: a folder holding store.sqlite.

One process writes to a store at a time. Evidence and coverage are written per
task in their own transactions; a rerun resumes by replaying cached model
responses. The store is bound to its extraction interpreter: a run with a
different one is rejected unless the affected derived data is reset.
"""
import json
import os
import sqlite3
from pathlib import Path
from .models import Evidence, FileRef, Interpreter, Section, Source

SCHEMA_VERSION = 3

SCHEMA = """
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE source (id TEXT PRIMARY KEY, name TEXT NOT NULL, kind TEXT NOT NULL, metadata TEXT NOT NULL);
CREATE TABLE content (id TEXT PRIMARY KEY, size INTEGER NOT NULL, extracted INTEGER NOT NULL DEFAULT 0);
CREATE TABLE file (source TEXT NOT NULL REFERENCES source(id), path TEXT NOT NULL,
                   content TEXT NOT NULL REFERENCES content(id), metadata TEXT NOT NULL, PRIMARY KEY (source, path));
CREATE TABLE interpreter (role TEXT PRIMARY KEY, description TEXT NOT NULL);
CREATE TABLE section (content TEXT NOT NULL REFERENCES content(id), id TEXT NOT NULL, data TEXT NOT NULL,
                      PRIMARY KEY (content, id));
CREATE TABLE task (content TEXT NOT NULL REFERENCES content(id), task TEXT NOT NULL, region TEXT NOT NULL,
                   row TEXT NOT NULL, PRIMARY KEY (content, task));
CREATE TABLE evidence (id TEXT PRIMARY KEY, content TEXT NOT NULL REFERENCES content(id), task TEXT NOT NULL,
                       region TEXT NOT NULL, data TEXT NOT NULL);
CREATE INDEX evidence_content ON evidence(content);
CREATE TABLE response_cache (key TEXT PRIMARY KEY, kind TEXT NOT NULL, region TEXT NOT NULL,
                             request_hash TEXT NOT NULL, response TEXT NOT NULL);
CREATE TABLE comparison (id INTEGER PRIMARY KEY AUTOINCREMENT, created TEXT NOT NULL, data TEXT NOT NULL);
"""

# Extraction regions that a changed extraction setting affects; anything not listed
# (model, prompts, library versions, sampling and output options) affects them all.
ALL_REGIONS = frozenset({"text", "table", "tile", "overview", "vision", "table-detection"})
VISUAL = frozenset({"tile", "overview", "vision"})
SETTING_REGIONS = {
    "tile_points": VISUAL, "image_side": VISUAL, "vision": VISUAL,
    "text_bytes": frozenset({"text", "table"}),
}

class StoreError(RuntimeError):
    pass

class StoreInUse(StoreError):
    pass

class InterpreterMismatch(StoreError):
    def __init__(self, role, differences, regions):
        self.role, self.differences, self.regions = role, differences, regions
        shown = "; ".join(f"{k}: {a!r} -> {b!r}" for k, (a, b) in differences.items())
        super().__init__(f"The store's {role} interpreter differs ({shown}). Rerun with --reset to clear the affected "
                         f"derived data ({', '.join(sorted(regions))} extraction and all comparisons), "
                         "--reset --dry-run to preview, or use a new store.")

def region_of(task):
    """'tile:3-r0' -> 'tile'; 'table-detection' and 'vision' are their own regions."""
    return task.split(":")[0]

def interpreter_differences(old, new):
    """Flattened {field: (old, new)} for differing parts of two interpreter descriptions."""
    diff = {}
    for key in sorted(set(old) | set(new)):
        a, b = old.get(key), new.get(key)
        if isinstance(a, dict) and isinstance(b, dict):
            diff.update({f"{key}.{k}": v for k, v in interpreter_differences(a, b).items()})
        elif a != b:
            diff[key] = (a, b)
    return diff

def affected_regions(differences):
    regions = set()
    for key in differences:
        name = key.split(".", 1)[1] if key.startswith("settings.") else None
        regions |= SETTING_REGIONS.get(name, ALL_REGIONS)
    return regions

class Store:
    """Open (creating if needed) a store folder, holding its writer lock until closed."""

    def __init__(self, folder):
        self.folder = Path(folder)
        self.folder.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(self.folder, 0o700)
        self.assets = self.folder / "assets"
        self.assets.mkdir(exist_ok=True, mode=0o700)
        self._lock = open(self.folder / ".lock", "a+")
        try:
            import fcntl
            fcntl.flock(self._lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except ImportError:  # pragma: no cover - non-POSIX platforms run without the lock
            pass
        except OSError as e:
            self._lock.close()
            raise StoreInUse(f"{self.folder} is in use by another process") from e
        path = self.folder / "store.sqlite"
        new = not path.exists()
        self.db = sqlite3.connect(path)
        os.chmod(path, 0o600)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA foreign_keys=ON")
        if new:
            with self.db:
                self.db.executescript(SCHEMA)
                self.db.execute("INSERT INTO meta VALUES ('schema_version', ?)", (str(SCHEMA_VERSION),))
        version = self.db.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()
        if not version or int(version[0]) != SCHEMA_VERSION:
            self.close()
            raise StoreError(f"{path} has schema version {version and version[0]}, expected {SCHEMA_VERSION}; "
                             "use a new store (no migrations during development)")

    def close(self):
        self.db.close()
        self._lock.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    # --- interpreter binding -------------------------------------------------
    def bind(self, interpreter: Interpreter, reset=False, dry_run=False):
        """Bind the store to an interpreter. Returns a summary of what was (or would be) cleared."""
        new = interpreter.model_dump()
        row = self.db.execute("SELECT description FROM interpreter WHERE role=?", (interpreter.role,)).fetchone()
        if row is None:
            if not dry_run:
                with self.db:
                    self.db.execute("INSERT INTO interpreter VALUES (?, ?)", (interpreter.role, json.dumps(new)))
            return {}
        differences = interpreter_differences(json.loads(row[0]), new)
        if not differences:
            return {}
        regions = affected_regions(differences)
        if not reset:
            raise InterpreterMismatch(interpreter.role, differences, regions)
        return self.clear_extraction(regions, dry_run=dry_run, rebind=None if dry_run else new)

    def clear_extraction(self, regions, dry_run=False, rebind=None):
        marks = ",".join("?" * len(regions))
        regions = sorted(regions)
        counts = {
            "tasks": self.db.execute(f"SELECT COUNT(*) FROM task WHERE region IN ({marks})", regions).fetchone()[0],
            "evidence": self.db.execute(f"SELECT COUNT(*) FROM evidence WHERE region IN ({marks})", regions).fetchone()[0],
            "cached_responses": self.db.execute(
                f"SELECT COUNT(*) FROM response_cache WHERE kind='extract' AND region IN ({marks})", regions).fetchone()[0],
            "comparisons": self.db.execute("SELECT COUNT(*) FROM comparison").fetchone()[0],
            "regions": regions,
        }
        if not dry_run:
            with self.db:
                self.db.execute(f"DELETE FROM task WHERE region IN ({marks})", regions)
                self.db.execute(f"DELETE FROM evidence WHERE region IN ({marks})", regions)
                self.db.execute(f"DELETE FROM response_cache WHERE kind='extract' AND region IN ({marks})", regions)
                self.db.execute("DELETE FROM comparison")
                self.db.execute("UPDATE content SET extracted=0")
                if rebind is not None:
                    self.db.execute("UPDATE interpreter SET description=? WHERE role=?", (json.dumps(rebind), rebind["role"]))
        return counts

    # --- sources, files and content -------------------------------------------
    def register(self, source: Source, files, sizes):
        """Record a source and its files; sizes maps content ID to byte size."""
        with self.db:
            self.db.execute("INSERT OR REPLACE INTO source VALUES (?, ?, ?, ?)",
                            (source.id, source.name, source.kind, json.dumps(source.metadata)))
            self.db.execute("DELETE FROM file WHERE source=?", (source.id,))
            for f in files:
                self.db.execute("INSERT OR IGNORE INTO content (id, size) VALUES (?, ?)", (f.content, sizes[f.content]))
                self.db.execute("INSERT INTO file VALUES (?, ?, ?, ?)", (f.source, f.path, f.content, json.dumps(f.metadata)))

    def sources(self):
        return [Source(id=i, name=n, kind=k, metadata=json.loads(m))
                for i, n, k, m in self.db.execute("SELECT id, name, kind, metadata FROM source ORDER BY id")]

    def files(self):
        return [FileRef(source=s, path=p, content=c, metadata=json.loads(m))
                for s, p, c, m in self.db.execute("SELECT source, path, content, metadata FROM file ORDER BY source, path")]

    def is_extracted(self, content):
        row = self.db.execute("SELECT extracted FROM content WHERE id=?", (content,)).fetchone()
        return bool(row and row[0])

    def mark_extracted(self, content):
        with self.db:
            self.db.execute("UPDATE content SET extracted=1 WHERE id=?", (content,))

    def record_sections(self, content, sections):
        with self.db:
            self.db.execute("DELETE FROM section WHERE content=?", (content,))
            for section in sections:
                self.db.execute("INSERT INTO section VALUES (?, ?, ?)", (content, section.id, section.model_dump_json()))

    def sections(self, content):
        return [Section.model_validate_json(d) for (d,) in
                self.db.execute("SELECT data FROM section WHERE content=? ORDER BY rowid", (content,))]

    # --- per-task results ------------------------------------------------------
    def record_task(self, row, evidence):
        """Write one task's coverage row and evidence in a single transaction."""
        region = region_of(row["task"])
        with self.db:
            self.db.execute("DELETE FROM evidence WHERE content=? AND task=?", (row["content"], row["task"]))
            self.db.execute("INSERT OR REPLACE INTO task VALUES (?, ?, ?, ?)",
                            (row["content"], row["task"], region, json.dumps(row)))
            for e in evidence:
                self.db.execute("INSERT OR REPLACE INTO evidence VALUES (?, ?, ?, ?, ?)",
                                (e.id, e.content, e.locator.task, region, e.model_dump_json()))

    def evidence(self, content):
        return [Evidence.model_validate_json(d) for (d,) in
                self.db.execute("SELECT data FROM evidence WHERE content=? ORDER BY rowid", (content,))]

    def coverage(self, content):
        return [json.loads(r) for (r,) in self.db.execute("SELECT row FROM task WHERE content=? ORDER BY rowid", (content,))]

    # --- response cache (semantic keys) ---------------------------------------
    def cached(self, key):
        return self.db.execute("SELECT response, request_hash FROM response_cache WHERE key=?", (key,)).fetchone()

    def cache(self, key, kind, region, request_hash, response):
        with self.db:
            self.db.execute("INSERT OR REPLACE INTO response_cache VALUES (?, ?, ?, ?, ?)",
                            (key, kind, region, request_hash, response))

    def uncache(self, key):
        with self.db:
            self.db.execute("DELETE FROM response_cache WHERE key=?", (key,))

    # --- comparisons -----------------------------------------------------------
    def save_comparison(self, created, data):
        with self.db:
            cursor = self.db.execute("INSERT INTO comparison (created, data) VALUES (?, ?)",
                                     (created, json.dumps(data, ensure_ascii=False)))
        return cursor.lastrowid
