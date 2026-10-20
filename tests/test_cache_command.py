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
from unittest.mock import patch
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

class Bound(unittest.TestCase):
    """A store bound to its answers cache (the plan's proposal; the owner: "Supporting a configurable cache makes
    sense."): its first run keeps the cache it used, later runs use it whatever the environment says, and a run whose
    SEMANTIC_PDF_DIFF_CACHE names another is refused before the store changes."""
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()
        self.folder = self.root / "project" / "store"

    def bound(self):
        with Store(self.folder) as store:
            return store.own_settings().get("answers_cache")

    def test_the_first_run_binds_the_cache_in_effect_and_later_runs_keep_it(self):
        from semantic_pdf_diff.pipeline import cache_of
        project = self.root / "project" / "answers"
        with patch.dict(os.environ, {"SEMANTIC_PDF_DIFF_CACHE": str(project)}), Store(self.folder) as store:
            self.assertEqual(cache_of(store, bind=False), project / "answers.sqlite")
            self.assertNotIn("answers_cache", store.own_settings())  # bind=False: nothing written
            self.assertEqual(cache_of(store), project / "answers.sqlite")
        self.assertEqual(self.bound(), "../answers")  # beside the store: the project moves whole
        with patch.dict(os.environ, {}, clear=False), Store(self.folder) as store:
            os.environ.pop("SEMANTIC_PDF_DIFF_CACHE", None)  # a shell without the project's export
            self.assertEqual(cache_of(store), project / "answers.sqlite")
        with patch.dict(os.environ, {"SEMANTIC_PDF_DIFF_CACHE": str(self.root / "home-cache")}), \
                Store(self.folder) as store, self.assertRaises(ValueError) as refused:
            cache_of(store)
        self.assertIn(str(project / "answers.sqlite"), str(refused.exception))
        self.assertIn("config set answers_cache", str(refused.exception))

    def test_the_users_cache_is_kept_from_the_home_folder(self):
        from semantic_pdf_diff.pipeline import cache_of
        home = self.root / "home"
        with patch.dict(os.environ, {"HOME": str(home)}), Store(self.root / "work" / "store") as store:
            for name in ("SEMANTIC_PDF_DIFF_CACHE", "XDG_CACHE_HOME"):
                os.environ.pop(name, None)
            self.assertEqual(cache_of(store), home / ".cache" / "semantic-pdf-diff" / "answers.sqlite")
            self.assertEqual(store.own_settings()["answers_cache"], "~/.cache/semantic-pdf-diff")

    def test_config_sets_it_from_the_current_folder_and_says_where_the_old_answers_are(self):
        with Store(self.folder) as store:
            store.save_own_settings({"answers_cache": "../answers"})
        here = os.getcwd()
        os.chdir(self.root)
        try:
            code, out, _ = run("config", "set", "answers_cache", "project/other", "--store", "project/store")
        finally:
            os.chdir(here)
        self.assertEqual(code, 0)
        self.assertEqual(self.bound(), "../other")
        self.assertIn("answers_cache = ../other", out)
        self.assertIn(f"the answers asked before stay in {self.root / 'project' / 'answers' / 'answers.sqlite'}", out)
        self.assertIn("cache copy", out)
        code, _, err = run("config", "set", "answers_cache", "/x", "--user")
        self.assertEqual(code, 1)
        self.assertIn("answers_cache is a store's", err)
        code, out, _ = run("config", "help", "answers_cache", "--store", self.folder)
        self.assertIn("Later runs use it whatever the environment says", out)

    def test_a_run_with_another_cache_is_refused_before_the_store_changes(self):
        with Store(self.folder) as store:
            store.save_own_settings({"answers_cache": "../answers"})
        a, b = self.root / "a.pdf", self.root / "b.pdf"
        for path in (a, b):
            path.write_bytes(b"%PDF-1.4")
        with patch.dict(os.environ, {"SEMANTIC_PDF_DIFF_CACHE": str(self.root / "elsewhere")}):
            code, _, err = run("compare", a, b, "--store", self.folder)
        self.assertEqual(code, 1)
        self.assertIn("keeps its answers in", err)
        with Store(self.folder) as store:
            self.assertEqual(store.sources(), [])

if __name__ == "__main__":
    unittest.main()
