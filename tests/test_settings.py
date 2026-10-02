"""Every setting keeps to its class (models.SETTING_CLASSES): toggled on its own, through the whole
pipeline, an endpoint setting changes no query that reaches the model, a post-processing one no
extraction query, and a shaping or selecting one changes some query (else it's dead or misfiled).
See docs/plans/content-addressed-queries-2026-09-28.md, milestone 1.
"""
import stubs  # noqa: F401 (a clean environment)
import contextlib
import io
import json
import tempfile
import time
import unittest
from pathlib import Path
import pymupdf
from semantic_pdf_diff import cli
from semantic_pdf_diff.models import SETTING_CLASSES, Settings
from test_concurrency import jittery_model
from test_situate import diagram

# A value other than the default for each setting, chosen not to stop the run (limits stay loose).
TOGGLES = {
    'model': 'another-model', 'image_tokens': 28000, 'max_calls': 1_000_000, 'max_cost': 1000.0, 'retries': 1,
    'timeout': 300.0, 'stream': False, 'concurrency': 2, 'heartbeat_seconds': 5.0,
    'rate_limits': [{'tokens_per_minute': 100_000_000}],
    'context_tokens': 8192, 'safety_tokens': 26000, 'output_tokens': 3000, 'claims_per_request': 10,
    'text_bytes': 400, 'image_side': 800, 'section_depth': 1,
    'extract_prompt': 'List engineering claims as JSON: {"claims": [], "complete": true, "issues": []}',
    'extract_rules': ['Be brief.'], 'visual_rules': ['Read chart axes before values.'], 'context_before': 100,
    'context_after': 100, 'table_context': 60, 'visual_text_layer': 200, 'stem_context': False, 'grow_tiles': False,
    'tile_locator': True, 'references': True, 'response_format': 'json_object', 'seed': 7,
    'max_token_field': 'max_completion_tokens',
    'tile_points': 300, 'refinement_depth': 0, 'vision': False, 'figure_tasks': False, 'tiling': 'grid',
    'sheet_details': True, 'skip_empty': False, 'table_filter': True, 'situate': False, 'verify_visuals': False,
    'top_k': 1, 'min_score': 0.9, 'max_pairs': 1, 'aliases': {'drawing': 'equipment', 'label': 'power'},
    'reconcile': False, 'quote_match': 'exact',
}
# Settings that act only on the drawing sheet: grid tiles (report pages are cut into bands), its details,
# and its frame (a false table); and refinement, which only grid tiles are large enough for (the stub answers
# some tiles "incomplete"). A slower document: most of a run's time is its tiles.
# The budget settings' values bite under the model-neutral defaults (32,768 tokens of context): 8,192, or a
# per-image or safety reserve that leaves little room, changes what situating sends and what's refused.
ON_SHEETS = {'sheet_details', 'grow_tiles', 'skip_empty', 'table_filter', 'refinement_depth'}
# Settings these documents can't exercise, and why (each still needs its class checked elsewhere).
NOT_EXERCISED = {
    'section_pages': 'sections come from page ranges only without an outline; the documents have one',
    'dedupe_repeated': 'needs a table row repeated on three or more pages (tests/test_repeats.py)',
    'base_url': 'the stub model is the endpoint',
    'rescan': 'reads sources, not the documents given on the command line',
    'max_zip_depth': 'archives only', 'max_source_bytes': 'sources only', 'zip_ratio_limit': 'archives only',
    'zip_ratio_min_bytes': 'archives only',
}

def document(path, rating, sheet=False):
    """A report page (numbered heading, values, an abbreviation, a ruled table with a lead-in, a
    captioned figure, blank paper), a page citing them, and with `sheet` a drawing sheet with details."""
    doc = pymupdf.open()
    report = doc.new_page(width=595, height=842)
    report.insert_text((60, 70), '3.1 Pump Station', fontsize=14, fontname='hebo')
    body = ("The pump station uses a proportional-integral (PI) controller to hold pressure. "
            f"Pump P-1 is rated {rating} kW at 1450 rpm and runs on duty while P-2 stands by. ") * 3
    report.insert_textbox(pymupdf.Rect(60, 85, 535, 190), body, fontsize=9)
    report.insert_text((60, 212), 'Table 1: Equipment ratings', fontsize=9)
    xs, ys = [60, 220, 380, 535], [220, 240, 260, 280]
    for x in xs:
        report.draw_line(pymupdf.Point(x, ys[0]), pymupdf.Point(x, ys[-1]))
    for y in ys:
        report.draw_line(pymupdf.Point(xs[0], y), pymupdf.Point(xs[-1], y))
    for r, row in enumerate([['Item', 'Power', 'Speed'], ['Pump P-1', f'{rating} kW', '1450 rpm'],
                             ['Fan F-2', '3 kW', '900 rpm']]):
        for c, text in enumerate(row):
            report.insert_text((xs[c] + 4, ys[r] + 14), text, fontsize=9)
    diagram(report, 80, 320)
    report.insert_text((80, 500), 'Figure 1: Pump curve', fontsize=9)
    cited = doc.new_page(width=595, height=842)
    cited.insert_text((60, 70), '3.2 Controls', fontsize=14, fontname='hebo')
    cited.insert_text((60, 100), 'a. The PI gains give 12 kW of margin (Figure 1, Table 1).', fontsize=9)
    cited.insert_text((60, 115), 'b. The standby pump starts within 5 s of a trip.', fontsize=9)
    if not sheet:
        doc.set_toc([[1, '3 Pumps', 1], [2, '3.1 Pump Station', 1], [2, '3.2 Controls', 2]])
        return saved(doc, path)
    sheet = doc.new_page(width=2448, height=1584)
    sheet.draw_rect(pymupdf.Rect(108, 72, 2394, 1512))
    sheet.draw_line(pymupdf.Point(2124, 72), pymupdf.Point(2124, 1512))
    sheet.insert_text((2210, 1480), 'M-101', fontsize=50)
    sheet.insert_text((2150, 1400), 'PUMP DETAILS', fontsize=20)
    for name, title, x, y in [('D1', 'PUMP BASE', 250, 700), ('D2', 'VALVE PIT', 1200, 700)]:
        diagram(sheet, x + 50, y - 400)
        for i in range(12):
            sheet.insert_text((x + 60, y - 420 + 14 * i), f'{i + 1}" TYP', fontsize=9)
        sheet.insert_text((x, y), name, fontsize=25, fontname='cour')
        sheet.insert_text((x + 50, y), title, fontsize=25)
    doc.set_toc([[1, '3 Pumps', 1], [2, '3.1 Pump Station', 1], [2, '3.2 Controls', 2], [1, 'Drawings', 3]])
    return saved(doc, path)

def saved(doc, path):
    """Saved byte for byte alike in every process: no creation date, no fresh document id. Claims' ids hash
    the document's bytes, and requests list claims in id order (tests/test_golden_requests.py)."""
    doc.set_metadata({})
    doc.save(path, garbage=3, deflate=True, no_new_id=True)
    doc.close()
    return path

class SettingsKeepToTheirClass(unittest.TestCase):
    longMessage = False  # the sets of digests say nothing; the counts in each message do
    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.TemporaryDirectory()
        cls.root = Path(cls.dir.name)
        cls.docs = {False: (document(cls.root / 'a.pdf', 10), document(cls.root / 'b.pdf', 12)),
                    True: (document(cls.root / 'a-sheet.pdf', 10, True), document(cls.root / 'b-sheet.pdf', 12, True))}
        cls.stack = contextlib.ExitStack()
        cls.url, cls.state = cls.stack.enter_context(jittery_model())
        cls.base = {False: cls.run_with('baseline', {})}

    @classmethod
    def tearDownClass(cls):
        cls.stack.close()
        cls.dir.cleanup()

    @classmethod
    def run_with(cls, name, settings, sheet=False):
        """The queries (role, digest of what reached the model) of one run with these settings."""
        config = cls.root / f'{name}.json'
        config.write_text(json.dumps(settings))
        cls.state['queries'] = []
        a, b = cls.docs[sheet]
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            cli.main([str(a), str(b), '--out', str(cls.root / name), '--base-url', cls.url, '--config', str(config)])
        return set(cls.state['queries'])

    def test_every_setting_is_classified(self):
        self.assertEqual(set(SETTING_CLASSES), set(Settings.model_fields))
        self.assertEqual(set(TOGGLES) | set(NOT_EXERCISED), set(Settings.model_fields))
        defaults = Settings()
        for name, value in TOGGLES.items():
            self.assertNotEqual(getattr(defaults, name), Settings(**{name: value}).__getattribute__(name), name)

    def test_each_setting_keeps_to_its_class(self):
        self.assertEqual({role for role, _ in self.base[False]}, {'extract', 'triage', 'compare'})  # every stage
        extraction = lambda queries: {q for q in queries if q[0] == 'extract'}
        for name, value in TOGGLES.items():
            kind, sheet = SETTING_CLASSES[name], name in ON_SHEETS
            with self.subTest(setting=name, kind=kind):
                if sheet not in self.base:
                    self.base[sheet] = self.run_with('baseline-sheet', {}, sheet)
                base, queries = self.base[sheet], self.run_with(name, {name: value}, sheet)
                changed = f"{name} ({kind}): {len(queries - base)} queries new, {len(base - queries)} gone"
                if kind == 'endpoint':
                    self.assertEqual(queries, base, changed)
                elif kind == 'post':
                    self.assertEqual(extraction(queries), extraction(base), changed + " (extraction)")
                else:
                    self.assertNotEqual(queries, base, f"{name} ({kind}) changed no query: dead, or misfiled")


class SettingsTablesAgree(unittest.TestCase):
    """The tables that say what each setting does are kept by hand until they're generated from the levers'
    declarations (architecture clean-up, milestone 3). Until then they must agree."""
    # Known gaps, each with its fix: remove an entry when it's fixed.
    UNBOUND = {}  # image_tokens and safety_tokens were, until clean-up milestone 2 (review item 3)

    def test_shaping_settings_are_bound_by_a_role(self):
        from semantic_pdf_diff import provenance as P
        bound = set(P.EXTRACTION_SETTINGS) | set(P.TRIAGE_SETTINGS) | set(P.COMPARISON_SETTINGS) | set(P.LEVERS)
        shaping = {k for k, v in SETTING_CLASSES.items() if v == "shaping"}
        self.assertEqual(shaping - bound, set(self.UNBOUND))  # a new unbound one fails; so does a fixed one left listed

    def test_interpreters_hold_no_transport(self):
        from semantic_pdf_diff import provenance as P
        bound = set(P.EXTRACTION_SETTINGS) | set(P.TRIAGE_SETTINGS) | set(P.COMPARISON_SETTINGS) | set(P.LEVERS)
        self.assertEqual({k for k in bound if SETTING_CLASSES[k] == "endpoint"}, {"model"})  # the model answers

    def test_levers_scopes_and_marks_name_real_settings(self):
        from semantic_pdf_diff import extract, provenance as P, store
        self.assertLessEqual(set(P.LEVERS), set(Settings.model_fields))
        self.assertLessEqual(set(store.SETTING_REGIONS), set(Settings.model_fields))
        self.assertFalse({k for k in store.SETTING_REGIONS if SETTING_CLASSES[k] == "endpoint"})
        # a lever without a scope clears every region when changed: only the instructions should
        self.assertEqual(set(P.LEVERS) - set(store.SETTING_REGIONS), {"extract_prompt", "extract_rules"})
        marks = {name for name, _ in extract.LEVER_MARKS}
        self.assertLessEqual(marks - set(P.LEVERS), {"figure_tasks", "section"})  # notes that aren't levers

class DefaultsFitTheirBudget(unittest.TestCase):
    """The shipped defaults must fit their own context budget: once, 4,000 output tokens left 3,792 of an
    8,192-token context for input, and a plain comparison was refused 172 of 178 times (code review 2026-10-01).
    Recordings and the other tests run under other profiles, so only this one runs the defaults as shipped."""
    def test_a_plain_comparison_is_refused_nothing(self):
        import os
        from unittest.mock import patch
        clean = {k: v for k, v in os.environ.items() if not k.startswith(("PDF_DIFF_", "OPENAI_"))}
        with tempfile.TemporaryDirectory() as d, jittery_model() as (url, _), patch.dict(os.environ, clean, clear=True):
            root = Path(d)
            a, b = document(root / "a.pdf", 10, True), document(root / "b.pdf", 12, True)
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                cli.main([str(a), str(b), "--out", str(root / "out"), "--base-url", url])
            report = json.loads((root / "out" / "report.json").read_text())
        refused = [f["rationale"] for f in report["findings"] if "budget" in str(f.get("rationale"))]
        issues = [i for row in report["coverage"] for i in row.get("issues", []) if "budget" in i]
        self.assertEqual((refused, issues), ([], []))
        self.assertTrue(report["findings"])

if __name__ == '__main__':
    unittest.main()
