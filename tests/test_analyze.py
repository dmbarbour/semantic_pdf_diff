"""`semantic-pdf-diff analyze`: one source read and reported, no comparison (single-document analysis, milestone 1).
The owner, 2026-10-29: "I'd like to focus on two things that will be immediately useful to me: single document
outputs, and building indexes and glossaries"; "I say "single document" but I really mean "single source" that might
be a folder of docs."
"""
import stubs  # noqa: F401 (a clean environment)
import contextlib
import io
import json
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from stubs import prompt_of, request_body, serving
from semantic_pdf_diff import cli, topics
from semantic_pdf_diff.report import browsing, unpacked
from test_embed import endpoint
from test_portable_report import BROWSERS

def run(*argv):
    with contextlib.redirect_stdout(io.StringIO()) as out, contextlib.redirect_stderr(io.StringIO()) as err:
        code = cli.main([str(a) for a in argv])
    return code, out.getvalue(), err.getvalue()

def plant(folder):
    """A source of two documents: pumps and fans in one, blowers in the other; 15 claims."""
    folder.mkdir()
    (folder / "machines.md").write_text("# Machines\n\n" + "".join(
        f"pump{k} | rated power | {10 + k} | kW\n\nfan{k} | air flow | {k + 1} | cms\n\n" for k in range(5)))
    (folder / "blowers.md").write_text("# Blowers\n\n" + "".join(f"blower{k} | discharge head | {20 + k} | m\n\n"
                                                                 for k in range(5)))
    return folder

def asked(state):
    """test_embed's stub endpoint, each request's prompt kept."""
    serve = endpoint(state)

    def post(handler):
        if not handler.path.endswith("/embeddings"):
            body = request_body(handler)
            state.setdefault("prompts", []).append(prompt_of(body["messages"][1]["content"]))
            handler.rfile = io.BytesIO(json.dumps(body).encode())
            handler.headers.replace_header("Content-Length", str(len(json.dumps(body).encode())))
        return serve(handler)
    return post

def drawn(page):
    """What a headless browser draws of a page (its scripts left out), or None without one."""
    browser = next((b for b in map(shutil.which, BROWSERS) if b), None)
    if browser is None:
        return None
    flags = ["--headless", "--no-sandbox", "--disable-gpu", "--virtual-time-budget=10000", "--dump-dom"]
    done = subprocess.run([browser, *flags, page], capture_output=True, text=True, timeout=120)
    return re.sub(r"<script.*?</script>", "", done.stdout, flags=re.S)

class Analyze(unittest.TestCase):
    def test_a_folder_of_documents_is_one_source_reported_without_comparing(self):
        state = {"embedded": [], "names": 0}
        with tempfile.TemporaryDirectory() as d, serving(asked(state)) as url:
            root = Path(d)
            config = root / "settings.json"
            config.write_text(json.dumps({"search_names": True, "topic_names": False}))
            code, out, _ = run("analyze", plant(root / "plant"), "--store", root / "out", "--base-url", url,
                               "--config", config, "--no-situate")
            data = json.loads((root / "out" / "report.json").read_text())
            page = unpacked((root / "out" / "report.html").read_text())
            shown = drawn((root / "out" / "report.html").as_uri())
            asked_first = len(state["prompts"])
            again, _, _ = run("analyze", root / "plant", "--store", root / "out", "--base-url", url, "--config",
                              config, "--no-situate")
            rewritten, _, _ = run("report", "--store", root / "out")
            searched, found, _ = run("search", "blower3", "--store", root / "out")
        self.assertEqual((code, again, rewritten, searched), (0, 0, 0, 0))
        self.assertIn(f"Report: {root / 'out' / 'report.html'}", out)
        self.assertEqual(data["mode"], "analysis")
        self.assertEqual([s["name"] for s in data["sources"]], ["plant"])
        self.assertEqual(len(data["files"]), 2)
        self.assertEqual(len(data["evidence"]), 15)
        self.assertEqual((data["findings"], data["unmatched"]), ([], []))
        self.assertFalse(any("Compare exactly" in p for p in state["prompts"]))  # nothing judged
        names = [p for p in state["prompts"] if "Find the names" in p]
        self.assertEqual(len(names), 1)
        self.assertIn("names an engineering source gives the same thing", names[0])
        self.assertIn("in the claims of a source (a document, or a set of them),", names[0])
        self.assertEqual(data["synonyms"]["items"], [])  # (the stub's names aren't this source's: none kept)
        self.assertEqual(len(state["prompts"]), asked_first)  # run again: every answer from the cache
        self.assertIn("<h1>Source analysis</h1>", page)
        self.assertIn("<p>plant: 15 claims read from 2 files</p>", page)
        self.assertIn('<button data-view="findings" hidden>Findings 0</button><button data-view="claims" '
                      'class="on">Claims 15</button>', page)
        self.assertNotIn("lack a confirmed counterpart", page)
        self.assertNotIn("Not compared", page)
        self.assertRegex(page, r'<select id="file"><option value="all">All files</option><option value="0">'
                               r'\S*blowers\.md</option><option value="1">\S*machines\.md</option></select>')
        way, topic_of, _ = browsing(data)  # one source's topics needn't be found on two sides
        self.assertIsNotNone(way)
        self.assertEqual(len(topic_of), 15)
        self.assertIn("Its claims, by topic", page)
        self.assertIn("blower3", found)
        if shown is not None:  # the page opens on its claims: it has no findings
            self.assertIn("15 of 15 claims", shown)
            self.assertEqual(shown.count("<article"), 15)

    def test_one_sides_topics(self):
        said = [{"rated", "power"}] * 5 + [{"air", "flow"}] * 5 + [{"discharge", "head"}] * 5
        way = topics.split(said, ["plant"] * 15, 3, "by property", one=True)
        self.assertEqual(len(way.topics), 3)
        self.assertEqual(way.measures["both_sides"], 1.0)
        # a comparison's, though its claims shown are one side's: only words both sides have, as before
        self.assertEqual(topics.split(said, ["a"] * 15, 3, "by property").topics, [])
        self.assertEqual(topics.split(said, ["a"] * 10 + ["b"] * 5, 3, "by property").topics, [])
        self.assertIn("a source's claims by", topics.names_prompt([way], [], one=True))
        self.assertIn("a comparison by", topics.names_prompt([way], []))

    def test_a_declared_source_by_name(self):
        state = {"embedded": [], "names": 0}
        with tempfile.TemporaryDirectory() as d, serving(asked(state)) as url:
            root = Path(d)
            plant(root / "plant")
            config = root / "settings.json"
            config.write_text(json.dumps({"search_names": False, "topic_names": False}))
            added, _, _ = run("source", "add", "works", "--store", root / "out", "--path", root / "plant")
            code, _, _ = run("analyze", "works", "--store", root / "out", "--base-url", url, "--config", config,
                             "--no-situate")
            data = json.loads((root / "out" / "report.json").read_text())
        self.assertEqual((added, code), (0, 0))
        self.assertEqual([s["name"] for s in data["sources"]], ["works"])

    def test_an_analysis_takes_no_comparing_options(self):
        with contextlib.redirect_stderr(io.StringIO()) as err, self.assertRaises(SystemExit):
            cli.analyze_parser().parse_args(["x", "--top-k", "3"])  # (--mode would be read as --model's prefix)
        self.assertIn("unrecognized arguments: --top-k", err.getvalue())

if __name__ == "__main__":
    unittest.main()
