"""`semantic-pdf-diff cache` (docs/plans/answers-cache-maintenance-2026-10-20.md): a project's answers copied from
another cache, removed, or kept alone, picked out by the queries its stores logged. The owner, 2026-10-20: "I'm just
using project-local cache for sensitive things. Can't even let it mix without marking home cache CUI or higher. Some
ability to prune or transfer answers would be convenient, though, e.g. fill this cache by taking answers from that one
for a particular project." """
import stubs  # noqa: F401 (a clean environment)
import contextlib
import io
import os
import sqlite3
import stat
import tempfile
import unittest
from pathlib import Path
from semantic_pdf_diff import cli, fixtures
from semantic_pdf_diff.settings import cache_path
from semantic_pdf_diff.store import Store

CONTENT = "sha256:" + "a" * 64 + ".pdf"

def run(*argv):
    """(exit code, stdout, stderr) of a command."""
    with contextlib.redirect_stdout(io.StringIO()) as out, contextlib.redirect_stderr(io.StringIO()) as err:
        code = cli.main([str(a) for a in argv])
    return code, out.getvalue(), err.getvalue()

def store_asking(folder, *queries):
    """A store whose runs asked these queries (its query log)."""
    store = Store(folder)
    for i, query in enumerate(queries):
        store.note_query(query, ("extract", "text", CONTENT, f"text:p{i}:0"), "prompt", [])
    store.close()
    return folder

def cache_answering(path, answers):
    """A cache holding answers: {query: [the models answering it]}; each answer says something only it says."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with fixtures.open(path, "record") as cache:
        for query, models in answers.items():
            for model in models:
                cache.record(query, model, outcome="ok", answer=f'{{"said": "secret-{query}-{model}"}}',
                             recipe=("extract", "text", CONTENT, f"text:{query}:0"))
    return path

def held(path):
    """(query, model) of each answer a cache holds, and the queries its recipes are about."""
    with contextlib.closing(sqlite3.connect(path)) as db:
        return (sorted(db.execute("SELECT query, responder FROM response")),
                sorted(q for (q,) in db.execute("SELECT DISTINCT query FROM recipe")))

class Copy(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.home = cache_answering(self.root / "home" / "answers.sqlite",
                                    {"q1": ["m1", "m2"], "q2": ["m1"], "q3": ["m1"]})
        self.project = store_asking(self.root / "project" / "store", "q1", "q2", "q9")

    def test_a_projects_answers_alone_fill_another_cache(self):
        target = self.root / "project" / "cache"
        code, out, _ = run("cache", "copy", self.home.parent, "--store", self.project, "--cache", target)
        self.assertEqual(code, 0)
        self.assertIn(f"3 answers copied from {self.home} into {target / 'answers.sqlite'}", out)
        self.assertIn("the 3 queries 1 store(s) asked", out)
        self.assertEqual(held(target / "answers.sqlite"),
                         ([("q1", "m1"), ("q1", "m2"), ("q2", "m1")], ["q1", "q2"]))  # every model's; not q3
        self.assertEqual(stat.S_IMODE(os.stat(target).st_mode), 0o700)
        self.assertEqual(stat.S_IMODE(os.stat(target / "answers.sqlite").st_mode), 0o600)

    def test_a_dry_run_counts_and_copies_nothing_and_answers_held_are_kept(self):
        target = cache_answering(self.root / "other.sqlite", {"q1": ["m1"]})
        code, out, _ = run("cache", "copy", self.home, "--store", self.project, "--cache", target, "--dry-run")
        self.assertEqual((code, out.split(" answers")[0]), (0, "2"))  # q1 by m1 is there already
        self.assertIn("would be copied", out)
        self.assertEqual(held(target)[0], [("q1", "m1")])
        run("cache", "copy", self.home, "--cache", target)  # every answer, without --store
        self.assertEqual(len(held(target)[0]), 4)
        with contextlib.closing(sqlite3.connect(target)) as db:
            said = db.execute("SELECT answer FROM response WHERE query='q1' AND responder='m1'").fetchone()[0]
        self.assertIn("secret-q1-m1", said)

    def test_the_current_cache_unless_another_is_named(self):
        code, out, _ = run("cache", "copy", self.home, "--store", self.project)
        self.assertIn(f"into {cache_path()}", out)
        code, out, _ = run("cache", "show")
        self.assertEqual(code, 0)
        self.assertIn(f"{cache_path()}: 3 answers to 2 queries", out)
        self.assertIn("m1: 2 answers (extract 2)", out)
        self.assertIn("m2: 1 answers (extract 1)", out)

    def test_refusals(self):
        self.assertEqual(run("cache", "copy", self.home, "--cache", self.home)[0], 1)  # into itself
        code, _, err = run("cache", "copy", self.root / "nowhere", "--cache", self.root / "c")
        self.assertEqual(code, 1)
        self.assertIn("no such cache or fixture", err)
        code, _, err = run("cache", "copy", self.home, "--store", self.root / "no-store", "--cache", self.root / "c")
        self.assertEqual(code, 1)
        self.assertIn("no such store", err)
        with self.assertRaises(SystemExit) as refused:  # prune takes --keep or --unused-since
            run("cache", "prune", "--cache", self.home)
        self.assertEqual(refused.exception.code, 1)

class Remove(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.cache = cache_answering(self.root / "answers.sqlite",
                                     {"q1": ["m1", "m2"], "q2": ["m1"], "q3": ["m1"], "q4": ["m1"]})
        self.sensitive = store_asking(self.root / "sensitive", "q1", "q2")
        self.other = store_asking(self.root / "other", "q2", "q3")

    def test_a_stores_answers_leave_and_nothing_of_them_stays_in_the_file(self):
        code, out, _ = run("cache", "remove", "--store", self.sensitive, "--cache", self.cache)
        self.assertEqual(code, 0)
        self.assertIn(f"3 answers removed from {self.cache} (2 queries); overwritten in the file", out)
        self.assertEqual(held(self.cache), ([("q3", "m1"), ("q4", "m1")], ["q3", "q4"]))
        files = b"".join(p.read_bytes() for p in self.root.glob("answers.sqlite*"))
        for gone in (b"secret-q1-m1", b"secret-q1-m2", b"secret-q2-m1"):
            self.assertNotIn(gone, files)
        self.assertIn(b"secret-q3-m1", files)

    def test_answers_another_store_asked_too_can_be_kept(self):
        code, out, _ = run("cache", "remove", "--store", self.sensitive, "--keep", self.other, "--cache", self.cache,
                           "--dry-run")
        self.assertIn("2 answers would be removed", out)
        self.assertEqual(len(held(self.cache)[0]), 5)
        run("cache", "remove", "--store", self.sensitive, "--keep", self.other, "--cache", self.cache)
        self.assertEqual(held(self.cache)[0], [("q2", "m1"), ("q3", "m1"), ("q4", "m1")])

    def test_prune_keeps_what_the_stores_asked(self):
        code, out, _ = run("cache", "prune", "--keep", self.sensitive, "--keep", self.other, "--cache", self.cache)
        self.assertEqual(code, 0)
        self.assertIn("1 answers removed", out)
        self.assertEqual([q for q, _ in held(self.cache)[0]], ["q1", "q1", "q2", "q3"])

    def test_prune_by_age(self):
        with contextlib.closing(sqlite3.connect(self.cache)) as db, db:
            db.execute("UPDATE response SET used = '2026-01-01T00:00:00' WHERE query IN ('q3', 'q4')")
        code, _, err = run("cache", "prune", "--unused-since", "2026-06-01", "--cache", self.cache)
        self.assertEqual(code, 1)  # fixtures prune's guard: no run used the cache since
        self.assertIn("no run replayed or recorded", err)
        code, out, _ = run("cache", "prune", "--unused-since", "2026-06-01", "--cache", self.cache, "--force")
        self.assertIn("2 answers removed", out)
        self.assertEqual(sorted({q for q, _ in held(self.cache)[0]}), ["q1", "q2"])

if __name__ == "__main__":
    unittest.main()
