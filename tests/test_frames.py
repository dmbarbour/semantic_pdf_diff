"""Frames apart from conditions (the split_conditions lever; docs/plans/claim-context-2026-10-14.md, milestone 4):
the reader's conditions hold scope, a claim's frame (what a value is measured to, a datum, net or gross) has a field
of its own, and a tolerance goes with the value."""
import stubs  # noqa: F401 (a clean environment)
import unittest

from semantic_pdf_diff.levers import CONDITIONS_RULE, CONDITIONS_SPEC, SPLIT_RULE, SPLIT_SPEC
from semantic_pdf_diff.schema import Claim, Extraction, claim_id
from semantic_pdf_diff.settings import Settings
from semantic_pdf_diff.tasks import extraction_template

WIDTH = dict(entity="Room 101", attribute="width", value="12'-6\"", kind="text", quote="12'-6\"", confidence=0.9)

class Template(unittest.TestCase):
    def test_the_reader_is_asked_for_a_frame_only_when_on(self):
        off, on = extraction_template(Settings()), extraction_template(Settings(split_conditions=True))
        self.assertIn(CONDITIONS_SPEC, off)
        self.assertNotIn('"frame"', off)
        self.assertIn(SPLIT_SPEC, on)
        self.assertIn(SPLIT_RULE, on)
        self.assertNotIn(CONDITIONS_SPEC, on)
        self.assertEqual(on.count(CONDITIONS_RULE), 1)  # the rule kept, the frame's added after it

    def test_a_prompt_of_its_own_is_left_as_it_is(self):
        mine = 'List claims as JSON: {"claims": [], "complete": true, "issues": []}'
        self.assertEqual(extraction_template(Settings(extract_prompt=mine, split_conditions=True)),
                         extraction_template(Settings(extract_prompt=mine)))

class Tables(unittest.TestCase):
    def test_the_table_rules_are_asked_for_a_frame_only_when_on(self):
        from semantic_pdf_diff.levers import TABLE_FRAME, TABLE_SPLIT
        from semantic_pdf_diff.tablerules import RULES
        self.assertEqual(Settings().table_rules_text(RULES), RULES)
        on = Settings(split_conditions=True).table_rules_text(RULES)
        self.assertIn(TABLE_FRAME, on)
        self.assertIn(TABLE_SPLIT, on)

    def test_a_rules_frame_fills_like_its_conditions(self):
        from semantic_pdf_diff import tablerules as tr
        from test_tablerules import Applying, pumps
        rule = {**Applying.RULES["claims"][0], "frame": "at the pump's rated point"}
        rules = tr.Rules.model_validate({**Applying.RULES, "claims": [rule]})
        made = tr.row_claims(rules, pumps(), 0)
        self.assertEqual([f["frame"] for f, _, _ in made], ["at the pump's rated point"] * 2)
        self.assertIn("frame at the pump's rated point", tr.describe_rule(rules.claims[0]))
        plain = tr.row_claims(tr.Rules.model_validate(Applying.RULES), pumps(), 0)
        self.assertEqual([f["frame"] for f, _, _ in plain], ["", ""])

class Field(unittest.TestCase):
    def test_an_answers_frame_and_tolerance_are_kept(self):
        answer = Extraction.model_validate({"claims": [{**WIDTH, "frame": "to face of finish",
                                                        "uncertainty": "± 1/4\""}], "complete": True})
        self.assertEqual((answer.claims[0].frame, answer.claims[0].uncertainty), ("to face of finish", "± 1/4\""))
        self.assertEqual(Extraction.model_validate({"claims": [{**WIDTH, "frame": None}], "complete": True})
                         .claims[0].frame, "")

    def test_a_claim_without_a_frame_keeps_its_id_and_one_with_a_frame_is_another(self):
        import hashlib
        import json
        plain = Claim(**WIDTH)
        before = ["c", "room 101", "width", "12'-6\"", "", "", False, "unknown"]  # the id as named before frames
        self.assertEqual(claim_id("c", plain),
                         "ev-" + hashlib.sha256(json.dumps(before).encode()).hexdigest()[:16])
        face, stud = (Claim(**WIDTH, frame=f) for f in ("to face of finish", "to centreline of stud"))
        self.assertEqual(len({claim_id("c", plain), claim_id("c", face), claim_id("c", stud)}), 3)

    def test_evidence_without_a_frame_is_written_as_before(self):
        from test_pipeline import ev
        self.assertNotIn("frame", ev().model_dump())
        self.assertEqual(ev(frame="to face of finish").model_dump()["frame"], "to face of finish")

class Uses(unittest.TestCase):
    def test_readings_in_different_frames_are_not_one_fact(self):
        from semantic_pdf_diff.readings import same_fact
        from test_pipeline import ev
        face, stud = ev("A-1", frame="to face of finish"), ev("A-2", frame="to centreline of stud")
        self.assertFalse(same_fact(face, stud))
        self.assertTrue(same_fact(face, ev("A-3")))  # one unstated: no conflict

    def test_a_value_kept_in_another_frame_is_judged_not_settled(self):
        from semantic_pdf_diff import align
        from test_align import claim, pairs
        left = [claim("Room 101", "width", "12'-6\"", "ft-in", frame="to face of finish"),
                claim("Room 101", "depth", "14'-0\"", "ft-in")]
        right = [claim("Room 101", "width", "12'-6\"", "ft-in", frame="to centreline of stud"),
                 claim("Room 101", "depth", "14'-0\"", "ft-in")]
        found = align.align(left, right)
        self.assertEqual(pairs(found, left, right), {(("Room 101", "width", "12'-6\""),
                                                       ("Room 101", "width", "12'-6\""))})
        self.assertEqual(len(found.settled), 1)  # the depth, in no stated frame

    def test_the_frame_is_shown_where_conditions_are(self):
        from semantic_pdf_diff.compare import pair_request
        from semantic_pdf_diff.explain import _brief
        from test_pipeline import ev
        a = ev("A-1", frame="to face of finish")
        self.assertEqual(_brief(a)["frame"], "to face of finish")
        self.assertIn('"frame": "to face of finish"', pair_request(Settings(), "revisions", a, ev("B-1"))[0])

if __name__ == "__main__":
    unittest.main()
