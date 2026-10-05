"""A persistent, content-addressed evidence store: a folder holding store.sqlite.

One process writes to a store at a time. Evidence and coverage are written per
task in their own transactions; a rerun resumes by replaying cached model
responses. The store is bound to its extraction interpreter: a run with a
different one is rejected unless the affected derived data is reset. Cached responses are
kept through a reset: they're keyed by the query that reached the model (and the model), so
unchanged queries replay and changed ones are asked afresh.

Each content item records the version of the reader that extracted it ("docx/1"; extract.READERS),
or "unsupported" where none could. A run re-reads an item whose reader has changed since (or one
that has gained a reader): its tasks are made again, and those whose queries didn't change replay.
"""
import json
import os
import sqlite3
from pathlib import Path
from .levers import ALL_REGIONS, TEXTUAL, VISUAL, setting_regions  # noqa: F401 (the region names, for callers)
from .regions import crops_of, region_of  # noqa: F401 (region_of, for callers)
from .models import Evidence, Figure, FileRef, Interpreter, Section, Settings, Source, merge_occurrences

SCHEMA_VERSION = 8  # 8: responses cached by query hash and model; the query log

SCHEMA = """
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE source (name TEXT PRIMARY KEY, data TEXT NOT NULL, manifest_hash TEXT, issues TEXT NOT NULL DEFAULT '{}');
-- extracted: 0, or the version of the reader that extracted it ("docx/1"), or "unsupported"
CREATE TABLE content (id TEXT PRIMARY KEY, size INTEGER NOT NULL, extracted INTEGER NOT NULL DEFAULT 0);
CREATE TABLE file (source TEXT NOT NULL REFERENCES source(name) ON DELETE CASCADE, path TEXT NOT NULL,
                   content TEXT NOT NULL REFERENCES content(id), size INTEGER NOT NULL, origin TEXT NOT NULL,
                   disk TEXT NOT NULL, disk_stat TEXT NOT NULL, metadata TEXT NOT NULL, PRIMARY KEY (source, path));
CREATE TABLE interpreter (role TEXT PRIMARY KEY, description TEXT NOT NULL);
CREATE TABLE section (content TEXT NOT NULL REFERENCES content(id), id TEXT NOT NULL, data TEXT NOT NULL,
                      PRIMARY KEY (content, id));
CREATE TABLE task (content TEXT NOT NULL REFERENCES content(id), task TEXT NOT NULL, region TEXT NOT NULL,
                   row TEXT NOT NULL, PRIMARY KEY (content, task));
-- One row per occurrence: a claim (id) sighted by one task. Loading merges them.
CREATE TABLE evidence (id TEXT NOT NULL, content TEXT NOT NULL REFERENCES content(id), task TEXT NOT NULL,
                       region TEXT NOT NULL, data TEXT NOT NULL, PRIMARY KEY (id, content, task));
CREATE INDEX evidence_content ON evidence(content);
-- Responses by the query that reached the model and the model (llm.Client._cache_key).
CREATE TABLE response_cache (key TEXT PRIMARY KEY, kind TEXT NOT NULL, region TEXT NOT NULL,
                             query TEXT NOT NULL, response TEXT NOT NULL, content TEXT NOT NULL DEFAULT '');
-- Diagnostics: each query's recipe (how the pipeline built it: role, region, content, task, ...)
-- and its text, to see what a task was asked. Never used to find answers.
CREATE TABLE query (hash TEXT NOT NULL, recipe TEXT NOT NULL, role TEXT NOT NULL, region TEXT NOT NULL,
                    content TEXT NOT NULL, task TEXT NOT NULL, prompt TEXT NOT NULL, images TEXT NOT NULL,
                    PRIMARY KEY (hash, recipe));
CREATE INDEX query_task ON query(content, task);
-- Situating results per content: figures, unresolved references, issues, complete.
CREATE TABLE situation (content TEXT PRIMARY KEY REFERENCES content(id), data TEXT NOT NULL);
CREATE TABLE comparison (id INTEGER PRIMARY KEY AUTOINCREMENT, created TEXT NOT NULL, data TEXT NOT NULL);
-- Views for `show` and for anyone querying the store directly.
CREATE VIEW source_files AS
    SELECT f.source, f.path, f.content, f.size, c.extracted FROM file f JOIN content c ON c.id = f.content;
CREATE VIEW evidence_occurrences AS
    SELECT f.source, f.path, e.id AS evidence, json_extract(e.data, '$.locator.page') AS page, e.region,
           json_extract(e.data, '$.entity') AS entity, json_extract(e.data, '$.attribute') AS attribute,
           json_extract(e.data, '$.value') AS value, json_extract(e.data, '$.unit') AS unit,
           json_extract(e.data, '$.quote') AS quote
    FROM evidence e JOIN file f ON f.content = e.content;
CREATE VIEW coverage_by_source AS
    SELECT f.source, json_extract(t.row, '$.status') AS status, COUNT(*) AS tasks
    FROM task t JOIN (SELECT DISTINCT source, content FROM file) f ON f.content = t.content
    GROUP BY f.source, status;
CREATE VIEW orphaned_content AS
    SELECT id AS content, size FROM content WHERE id NOT IN (SELECT content FROM file);
CREATE VIEW comparisons AS
    SELECT id, created, json_extract(data, '$.mode') AS mode, json_extract(data, '$.sources[0].name') AS first,
           json_extract(data, '$.sources[1].name') AS second, json_array_length(data, '$.findings') AS findings
    FROM comparison;
"""

# Extraction regions that a changed extraction setting affects (levers.Declared regions); anything not listed
# (model, prompts, library versions, sampling and output options) affects them all.
SETTING_REGIONS = setting_regions(Settings)

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

    @classmethod
    def open(cls, folder):
        """A store opened to read only (code review 2026-10-01, A1): no folder or schema created, no writer's lock
        (a reader neither waits on a run nor stops one), and any write is an error."""
        self = cls.__new__(cls)
        self.folder = Path(folder)
        self.assets = self.folder / "assets"
        self._lock = None
        path = self.folder / "store.sqlite"
        if not path.exists():
            raise StoreError(f"{path}: no such store")
        self.db = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
        version = self.db.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()
        if not version or int(version[0]) != SCHEMA_VERSION:
            self.close()
            raise StoreError(f"{path} has schema version {version and version[0]}, expected {SCHEMA_VERSION}")
        return self

    def close(self):
        self.db.close()
        if self._lock is not None:
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
        if interpreter.role == "triage":
            if not reset:
                raise InterpreterMismatch("triage", differences, {"situating"})
            return self.clear_situating(dry_run=dry_run, rebind=None if dry_run else new)
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
            "comparisons": self.db.execute("SELECT COUNT(*) FROM comparison").fetchone()[0],
            "regions": regions,
        }
        if not dry_run:
            with self.db:
                self.db.execute(f"DELETE FROM task WHERE region IN ({marks})", regions)
                self.db.execute(f"DELETE FROM evidence WHERE region IN ({marks})", regions)
                self.db.execute("DELETE FROM comparison")
                self.db.execute("UPDATE content SET extracted=0")
                self.db.execute("DELETE FROM situation")  # situating reads the evidence
                if rebind is not None:
                    self.db.execute("UPDATE interpreter SET description=? WHERE role=?", (json.dumps(rebind), rebind["role"]))
        return counts

    def clear_situating(self, dry_run=False, rebind=None):
        """Forget situating results (figures, "about" statements); cached answers stay (see above)."""
        counts = {
            "situated_content": self.db.execute("SELECT COUNT(*) FROM situation").fetchone()[0],
            "regions": ["situating"],
        }
        if not dry_run:
            with self.db:
                self.db.execute("DELETE FROM situation")
                for content, sid, data in self.db.execute("SELECT content, id, data FROM section").fetchall():
                    plain = Section.model_validate_json(data).model_copy(
                        update={"about": "", "section_type": "", "density": "", "keywords": []})
                    self.db.execute("UPDATE section SET data=? WHERE content=? AND id=?",
                                    (plain.model_dump_json(), content, sid))
                if rebind is not None:
                    self.db.execute("UPDATE interpreter SET description=? WHERE role=?", (json.dumps(rebind), rebind["role"]))
        return counts

    # --- sources, files and content -------------------------------------------
    def save_source(self, source: Source, replace=False, manifest_hash=None):
        """Declare a source, or update an existing one's definition when replace is set."""
        exists = self.source(source.name) is not None
        if exists and not replace:
            raise StoreError(f"source {source.name!r} is already declared; use 'source update' or another name")
        with self.db:
            self.db.execute("INSERT INTO source (name, data, manifest_hash) VALUES (?, ?, ?) "
                            "ON CONFLICT(name) DO UPDATE SET data=excluded.data, manifest_hash=excluded.manifest_hash",
                            (source.name, source.model_dump_json(), manifest_hash))

    def source(self, name):
        row = self.db.execute("SELECT data FROM source WHERE name=?", (name,)).fetchone()
        return Source.model_validate_json(row[0]) if row else None

    def manifest_hash(self, name):
        row = self.db.execute("SELECT manifest_hash FROM source WHERE name=?", (name,)).fetchone()
        return row[0] if row else None

    def sources(self):
        return [Source.model_validate_json(d) for (d,) in self.db.execute("SELECT data FROM source ORDER BY name")]

    def remove_source(self, name):
        """Unregister a source; its content stays until gc finds it orphaned."""
        with self.db:
            removed = self.db.execute("DELETE FROM source WHERE name=?", (name,)).rowcount
        if not removed:
            raise StoreError(f"no source named {name!r}")

    def rescan(self, name, limits=None, describe=None):
        """Rescan a source's roots and update its files in place. Returns a summary."""
        from .scan import Limits, ScannedFile, scan
        source = self.source(name)
        if source is None:
            raise StoreError(f"no source named {name!r}")
        old, reuse = {}, {}
        for path, content, size, origin, disk, stat, meta in self.db.execute(
                "SELECT path, content, size, origin, disk, disk_stat, metadata FROM file WHERE source=?", (name,)):
            item = ScannedFile(path, content, size, tuple(json.loads(origin)), tuple(json.loads(disk)),
                               tuple(json.loads(stat)), json.loads(meta))
            old[path] = content
            reuse.setdefault(item.disk, [item.disk_stat, [], []])[1].append(item)
        issues = json.loads(self.db.execute("SELECT issues FROM source WHERE name=?", (name,)).fetchone()[0])
        for key, found in issues.items():  # root-level issues (key []) are recomputed by every scan
            if tuple(json.loads(key)) in reuse:
                reuse[tuple(json.loads(key))][2] = [tuple(i) for i in found]
        result = scan(source.roots, limits or Limits(), reuse, describe)
        with self.db:
            self.db.execute("DELETE FROM file WHERE source=?", (name,))
            for f in result.files:
                self.db.execute("INSERT OR IGNORE INTO content (id, size) VALUES (?, ?)", (f.content, f.size))
                self.db.execute("INSERT INTO file VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                                (name, f.path, f.content, f.size, json.dumps(f.origin), json.dumps(f.disk),
                                 json.dumps(f.disk_stat), json.dumps(f.metadata)))
            self.db.execute("UPDATE source SET issues=? WHERE name=?",
                            (json.dumps({json.dumps(list(k)): v for k, v in result.disk_issues.items()}), name))
        new = {f.path: f.content for f in result.files}
        return {"files": len(new), "added": sorted(set(new) - set(old)), "removed": sorted(set(old) - set(new)),
                "changed": sorted(p for p in set(new) & set(old) if new[p] != old[p]),
                "reused_disk_files": result.reused, "issues": result.issues}

    def files(self, source=None):
        query = "SELECT source, path, content, metadata FROM file" + (" WHERE source=?" if source else "")
        return [FileRef(source=s, path=p, content=c, metadata=json.loads(m))
                for s, p, c, m in self.db.execute(query + " ORDER BY source, path", (source,) if source else ())]

    def origin(self, source, path):
        row = self.db.execute("SELECT origin FROM file WHERE source=? AND path=?", (source, path)).fetchone()
        return tuple(json.loads(row[0])) if row else None

    def issues(self, source):
        row = self.db.execute("SELECT issues FROM source WHERE name=?", (source,)).fetchone()
        return [tuple(i) for found in json.loads(row[0]).values() for i in found] if row else []

    def orphaned_content(self):
        return [c for (c,) in self.db.execute("SELECT id FROM content WHERE id NOT IN (SELECT content FROM file)")]

    def is_extracted(self, content, reader):
        """Whether a content item was extracted by this version of its reader (an earlier version's reading, or a
        store from before versions were recorded, doesn't count)."""
        row = self.db.execute("SELECT extracted FROM content WHERE id=?", (content,)).fetchone()
        return bool(row) and row[0] == reader

    def mark_extracted(self, content, reader):
        with self.db:
            self.db.execute("UPDATE content SET extracted=? WHERE id=?", (reader, content))

    def record_sections(self, content, sections):
        with self.db:
            self.db.execute("DELETE FROM section WHERE content=?", (content,))
            for section in sections:
                self.db.execute("INSERT INTO section VALUES (?, ?, ?)", (content, section.id, section.model_dump_json()))

    def sections(self, content):
        return [Section.model_validate_json(d) for (d,) in
                self.db.execute("SELECT data FROM section WHERE content=? ORDER BY rowid", (content,))]

    def record_situation(self, content, figures, sections, unresolved, issues):
        """Figures and section "about" statements for one content, in one transaction.

        Complete (so later runs load it) only when no request failed."""
        data = {"figures": [f.model_dump() for f in figures], "unresolved": [r.model_dump() for r in unresolved],
                "issues": issues, "complete": not any(i["failed"] for i in issues)}
        with self.db:
            for section in sections:
                self.db.execute("UPDATE section SET data=? WHERE content=? AND id=?",
                                (section.model_dump_json(), content, section.id))
            self.db.execute("INSERT OR REPLACE INTO situation VALUES (?, ?)", (content, json.dumps(data)))

    def situation(self, content):
        """(figures, unresolved references, issues) if situating completed, else None."""
        from .models import Reference
        row = self.db.execute("SELECT data FROM situation WHERE content=?", (content,)).fetchone()
        if row is None:
            return None
        data = json.loads(row[0])
        if not data["complete"]:
            return None
        return ([Figure.model_validate(f) for f in data["figures"]],
                [Reference.model_validate(r) for r in data["unresolved"]], data["issues"])

    # --- per-task results ------------------------------------------------------
    def record_task(self, row, evidence):
        """Write one task's coverage row and evidence in a single transaction."""
        region = region_of(row["task"])
        with self.db:
            self.db.execute("DELETE FROM evidence WHERE content=? AND task=?", (row["content"], row["task"]))
            self.db.execute("DELETE FROM situation WHERE content=?", (row["content"],))  # it read the old evidence
            self.db.execute("INSERT OR REPLACE INTO task VALUES (?, ?, ?, ?)",
                            (row["content"], row["task"], region, json.dumps(row)))
            for e in evidence:
                self.db.execute("INSERT OR REPLACE INTO evidence VALUES (?, ?, ?, ?, ?)",
                                (e.id, e.content, row["task"], region, e.model_copy(update={"occurrences": []}).model_dump_json()))

    def evidence(self, content, reconcile=None):
        """Claims for a piece of content, with occurrences merged (order-independent), and readings
        of one fact merged when the store's runs merge them (see set_reconcile), or as asked."""
        claims = merge_occurrences(Evidence.model_validate_json(d) for (d,) in
                                   self.db.execute("SELECT data FROM evidence WHERE content=?", (content,)))
        if self.reconciles() if reconcile is None else reconcile:
            from .readings import reconcile as merge_readings
            claims = merge_readings(claims)
        return claims

    def reconciles(self):
        row = self.db.execute("SELECT value FROM meta WHERE key='reconcile'").fetchone()
        return bool(row and row[0] == "1")

    def set_reconcile(self, on):
        """Whether evidence is read with readings of one fact merged. Situating links figures to claim
        IDs, so changing it forgets situating results. Returns what was cleared, if anything."""
        if bool(on) == self.reconciles():
            return {}
        cleared = self.clear_situating() if self.db.execute("SELECT COUNT(*) FROM situation").fetchone()[0] else {}
        with self.db:
            self.db.execute("INSERT OR REPLACE INTO meta VALUES ('reconcile', ?)", ("1" if on else "0",))
        return cleared

    def keep_tasks(self, content, tasks):
        """Drop a content item's task rows and evidence from tasks not in `tasks` (this run's): an earlier,
        interrupted run's refinement children, say, that this run didn't need."""
        tasks = sorted(set(tasks))
        marks = ",".join("?" * len(tasks)) or "''"
        with self.db:
            dropped = self.db.execute(f"DELETE FROM task WHERE content=? AND task NOT IN ({marks})",
                                      (content, *tasks)).rowcount
            self.db.execute(f"DELETE FROM evidence WHERE content=? AND task NOT IN ({marks})", (content, *tasks))
            if dropped:
                self.db.execute("DELETE FROM situation WHERE content=?", (content,))  # it read the old evidence
        return dropped

    def coverage(self, content):
        return [json.loads(r) for (r,) in self.db.execute("SELECT row FROM task WHERE content=? ORDER BY rowid", (content,))]

    # --- response cache (by query and model) and the query log -----------------
    def cached(self, key):
        return self.db.execute("SELECT response, query FROM response_cache WHERE key=?", (key,)).fetchone()

    def cache(self, key, kind, region, query, response, content=""):
        with self.db:
            self.db.execute("INSERT OR REPLACE INTO response_cache VALUES (?, ?, ?, ?, ?, ?)",
                            (key, kind, region, query, response, content))

    def note_query(self, query, recipe, prompt, images):
        """Log a query's recipe and text (diagnostics: what a task was asked)."""
        from .fixtures import recipe_labels
        digest, role, region, content, task = recipe_labels(recipe)
        with self.db:
            self.db.execute("INSERT OR IGNORE INTO query VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                            (query, json.dumps(list(recipe), default=str), role, region, content, task, prompt,
                             json.dumps(list(images))))

    def queries(self, content=None, task=None, role=None):
        """Logged queries: [{hash, recipe, role, region, content, task, prompt, images}], latest last."""
        where, args = [], []
        for column, value in (("content", content), ("task", task), ("role", role)):
            if value is not None:
                where.append(f"{column}=?")
                args.append(value)
        rows = self.db.execute("SELECT hash, recipe, role, region, content, task, prompt, images FROM query"
                               + (" WHERE " + " AND ".join(where) if where else "") + " ORDER BY rowid", args)
        return [{"hash": h, "recipe": json.loads(r), "role": role_, "region": region, "content": c, "task": t,
                 "prompt": p, "images": json.loads(i)} for h, r, role_, region, c, t, p, i in rows]

    def uncache(self, key):
        with self.db:
            self.db.execute("DELETE FROM response_cache WHERE key=?", (key,))

    # --- views and collection -------------------------------------------------
    VIEWS = ("sources", "source_files", "evidence_occurrences", "coverage_by_source", "orphaned_content", "comparisons")

    def view(self, name):
        """Rows of a named view as dicts; 'sources' summarizes source definitions."""
        if name == "sources":
            return [{"name": s.name, "kind": s.kind, "roots": "; ".join(s.roots), "manifest": s.manifest or "",
                     "files": len(self.files(s.name)), **{f"meta.{k}": v for k, v in s.metadata.items()}}
                    for s in self.sources()]
        if name not in self.VIEWS:
            raise StoreError(f"unknown view {name!r}; choose from {', '.join(self.VIEWS)}")
        cursor = self.db.execute(f"SELECT * FROM {name}")
        columns = [c[0] for c in cursor.description]
        return [dict(zip(columns, row)) for row in cursor]

    def gc(self, dry_run=False, orphaned_sources=False):
        """Delete orphaned content with its derived data and crops. Returns what was (or would be) removed.

        orphaned_sources also removes sources whose linked manifest file no longer exists.
        """
        from pathlib import Path as _Path
        gone = [s.name for s in self.sources() if s.manifest and not _Path(s.manifest).exists()] if orphaned_sources else []
        if gone and not dry_run:
            for name in gone:
                self.remove_source(name)
        orphans = self.orphaned_content()
        if gone and dry_run:  # content only those sources reference would be orphaned too
            marks = ",".join("?" * len(gone))
            orphans = sorted(set(orphans) | {c for (c,) in self.db.execute(
                f"SELECT content FROM file WHERE source IN ({marks}) AND content NOT IN "
                f"(SELECT content FROM file WHERE source NOT IN ({marks}))", gone + gone)})
        crops = [p for c in orphans for p in self.assets.glob(crops_of(c))]
        summary = {"sources": gone, "content": len(orphans), "crops": len(crops), "dry_run": dry_run}
        if orphans:
            marks = ",".join("?" * len(orphans))
            summary["evidence"] = self.db.execute(f"SELECT COUNT(*) FROM evidence WHERE content IN ({marks})", orphans).fetchone()[0]
            summary["cached_responses"] = self.db.execute(
                f"SELECT COUNT(*) FROM response_cache WHERE content IN ({marks})", orphans).fetchone()[0]
            if not dry_run:
                with self.db:
                    for table in ("evidence", "task", "section", "situation", "response_cache", "query"):
                        self.db.execute(f"DELETE FROM {table} WHERE content IN ({marks})", orphans)
                    self.db.execute(f"DELETE FROM content WHERE id IN ({marks})", orphans)
                for path in crops:
                    path.unlink(missing_ok=True)
        return summary

    # --- comparisons -----------------------------------------------------------
    def comparison(self, number=None):
        """A saved comparison's data: the given id, or the latest."""
        query = "SELECT data FROM comparison " + ("WHERE id=?" if number else "ORDER BY id DESC LIMIT 1")
        row = self.db.execute(query, (number,) if number else ()).fetchone()
        if row is None:
            raise StoreError(f"no comparison {number}" if number else "the store has no comparisons yet")
        return json.loads(row[0])

    def save_comparison(self, created, data):
        with self.db:
            cursor = self.db.execute("INSERT INTO comparison (created, data) VALUES (?, ?)",
                                     (created, json.dumps(data, ensure_ascii=False)))
        return cursor.lastrowid
