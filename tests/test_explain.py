"""Explaining differences (compare.explain; docs/plans/revision-comparison-2026-10-02.md, milestone 4): in revisions
mode each "different" or "uncertain" finding gets a second call naming its kind, shown its claims' items and where the
other revision still states each value."""
import stubs  # noqa: F401 (a clean environment)
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from test_pipeline import Fake, ev  # noqa: E402

from semantic_pdf_diff.compare import Revisions, compare, explanation_prompt  # noqa: E402
from semantic_pdf_diff.llm import ModelFailure  # noqa: E402
from semantic_pdf_diff.models import Explanation, Settings  # noqa: E402

def pump(id, attribute, value, unit="gpm", entity="Pump P-1"):
    return ev(id, entity=entity, attribute=attribute, value=value, unit=unit, conditions="", quote=f"{value} {unit}")

class Recording(Fake):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.asked = []

    def ask(self, prompt, schema, images=(), key=None):
        self.asked.append((schema, prompt, key))
        return super().ask(prompt, schema, images, key)

class Explain(unittest.TestCase):
    def setUp(self):
        self.left = [pump("A-1", "capacity", "100"), pump("A-2", "head", "50", "ft")]
        self.right = [pump("B-1", "capacity", "120"), pump("B-2", "head", "50", "ft")]

    def test_revisions_differences_are_explained_with_their_kind(self):
        client = Recording(kind="changed")
        result = compare(self.left, self.right, Path("."), client, "revisions")
        different = [f for f in result["findings"] if f["relation"] == "different"]
        self.assertEqual(len(different), 1)
        self.assertEqual(different[0]["explanation"], {"kind": "changed", "rationale": "Fixture explanation",
                                                       "confidence": 0.9})
        self.assertNotIn("explanation", next(f for f in result["findings"] if f.get("settled")))
        self.assertEqual(result["retrieval"]["explained"], {"changed": 1})
        schema, prompt, key = client.asked[-1]
        self.assertIs(schema, Explanation)
        self.assertEqual((key[0], key[1], key[3:]), ("explain", "revisions", ("A-1", "B-1")))
        self.assertIn("Comparison=", prompt)
        self.assertIn('"attribute": "head"', prompt)  # A's item: its other claims

    def test_only_revisions_with_the_lever_and_only_differences(self):
        for client, mode in ((Recording(), "proposals"), (Recording(s=Settings(explain_differences=False)), "revisions"),
                             (Recording(relation="complementary"), "revisions")):
            result = compare(self.left, self.right, Path("."), client, mode)
            self.assertFalse(any("explanation" in f for f in result["findings"]), (mode, client.relation))
            self.assertFalse(any(schema is Explanation for schema, _, _ in client.asked))
        result = compare(self.left, self.right, Path("."), Fake(relation="uncertain"), "revisions")
        self.assertEqual([f["explanation"]["kind"] for f in result["findings"] if f["relation"] == "uncertain"],
                         ["changed"])

    def test_a_failed_explanation_is_unclear_and_marked(self):
        class Failing(Fake):
            def ask(self, prompt, schema, images=(), key=None):
                if schema is Explanation:
                    raise ModelFailure("no answer")
                return super().ask(prompt, schema, images, key)
        result = compare(self.left, self.right, Path("."), Failing(), "revisions")
        why = next(f for f in result["findings"] if f["relation"] == "different")["explanation"]
        self.assertEqual((why["kind"], why["processing_error"]), ("unclear", True))

    def test_the_prompt_says_where_the_other_revision_still_states_a_value(self):
        # members of one list: the later revision still lists X, so X and Z aren't X changed to Z
        member = lambda id, value: ev(id, entity="RA Report", attribute="content", value=value, unit="", conditions="",
                                      quote=value)
        earlier = [member("A-1", "SSB indexes"), member("A-2", "LBT failures")]
        later = [member("B-1", "SSB indexes"), member("B-2", "RSRP threshold indication")]
        a, b = earlier[0], later[1]
        payload = [{"value": a.value}, {"value": b.value}]
        prompt = explanation_prompt(a, b, {"relation": "different", "rationale": "different content"}, payload,
                                    Revisions(earlier, later))
        lines = dict(line.split("=", 1) for line in prompt.splitlines() if "=" in line and line[:1] in "AB")
        self.assertEqual(json.loads(lines["A's value in the later revision"]),
                         [{"entity": "RA Report", "attribute": "content", "value": "SSB indexes"}])
        self.assertEqual(json.loads(lines["B's value in the earlier revision"]), [])
        self.assertEqual([x["value"] for x in json.loads(lines["A's item, earlier revision"])], ["LBT failures"])

    def test_a_counterpart_holding_the_value_is_no_echo(self):
        # conditions changed, value kept: B holds A's value, but B is what A is compared with, not a second statement
        rate = lambda id, conditions: ev(id, entity="filtration", attribute="filtration rate", value="4.1",
                                         unit="gpm/ft²", conditions=conditions, quote=f"{conditions}, 4.1 gpm/ft²")
        a, b = rate("A-1", "one filter out of service"), rate("B-1", "all filters in service")
        prompt = explanation_prompt(a, b, {"relation": "uncertain", "rationale": "conditions differ"},
                                    [{"value": "4.1", "basis": "unknown", "role": ""}, {"value": "4.1"}],
                                    Revisions([a], [b]))
        lines = dict(line.split("=", 1) for line in prompt.splitlines() if "=" in line and line[:1] in "ABQ")
        self.assertEqual((lines["A's value in the later revision"], lines["B's value in the earlier revision"]), ("[]", "[]"))
        self.assertEqual((lines["Quotes"], json.loads(lines["A"])), ("different text", {"value": "4.1"}))

    def test_the_report_counts_differences_by_kind(self):
        from semantic_pdf_diff.report import kinds_html
        findings = [{"explanation": {"kind": "changed"}}, {"explanation": {"kind": "not_same_item"}},
                    {"explanation": {"kind": "not_same_item"}}, {"relation": "equivalent"}]
        html = kinds_html(findings, str)
        self.assertIn("<b>Value changes</b> (1): changed 1", html)
        self.assertIn("<b>Not changes</b> (2): not the same item 2", html)
        self.assertEqual(kinds_html([{"relation": "equivalent"}], str), "")

if __name__ == "__main__":
    unittest.main()
