"""The positions lever (docs/plans/claim-context-2026-10-14.md, milestone 1): a list item's label ("Condition 2:")
recorded as where its claims sit, not as one of their conditions."""
import stubs  # noqa: F401 (a clean environment)
import re
import unittest

from semantic_pdf_diff.positions import list_positions, without_label
from semantic_pdf_diff.schema import Extraction, Position
from semantic_pdf_diff.settings import Settings
from semantic_pdf_diff.tasks import ExtractQuery

LEAD = "A link failure is declared when any of the following conditions holds."
SPEC = f"""# Link Specification

## 4 Link Failure Detection

{LEAD}

Condition 1: no acknowledgement is received within 856 ms.

Condition 2: 21 retransmissions fail.

## 5 Pumps

Pump 1: rated at 10 kW.

Pump 2: rated at 12 kW.
"""

def blocks(*texts):
    return [((0, i, 1, i + 1), t) for i, t in enumerate(texts)]

class Finding(unittest.TestCase):
    def test_a_sequence_of_labels_is_a_list_with_its_lead_in(self):
        found = list_positions(blocks("4 Link Failure Detection", LEAD, "Condition 1: no acknowledgement in 856 ms.",
                                      "It is checked each second.", "Condition 2: 21 retransmissions fail."))
        self.assertEqual({box[1]: (p.label, p.lead) for box, p in found.items()},
                         {2: ("Condition 1", LEAD), 4: ("Condition 2", LEAD)})

    def test_bare_and_lettered_labels_count(self):
        found = list_positions(blocks("GENERAL NOTES", "1. ALL DIMENSIONS ARE TO FACE OF FINISH.", "2. SEE SHEET M-1.",
                                      "(a) the first", "(b) the second"))
        self.assertEqual({box[1]: p.label for box, p in found.items()}, {1: "1", 2: "2", 3: "(a)", 4: "(b)"})
        self.assertEqual(found[(0, 1, 1, 2)].lead, "GENERAL NOTES")

    def test_names_and_lone_labels_are_no_list(self):
        # a numbered thing keeps its number (identity); one item alone is no sequence; clause numbers are headings'
        found = list_positions(blocks("Pump 1: 10 kW", "Pump 2: 12 kW", "Figure 1: a pump", "Figure 2: a fan",
                                      "Option B: a second pump.", "Step 3: open the valve.", "7.2. Stream Concurrency",
                                      "7.3. Stream Limits"))
        self.assertEqual(found, {})

    def test_numbers_must_follow_on(self):
        self.assertEqual(list_positions(blocks("Condition 1: a", "Condition 3: b")), {})

class Removing(unittest.TestCase):
    def test_the_label_leaves_the_conditions_and_nothing_else_does(self):
        cases = [("Condition 1", "Condition 1", ""), ("Condition 3; duration 60 s", "Condition 3", "duration 60 s"),
                 ("Condition 3: SNR below 4.3 dB", "Condition 3", "SNR below 4.3 dB"), ("note 2", "2", ""),
                 ("at 2 bar, 20 °C", "2", "at 2 bar, 20 °C"), ("item b", "(b)", ""),
                 ("when congested", "Condition 1", "when congested")]
        for conditions, label, kept in cases:
            with self.subTest(conditions=conditions):
                self.assertEqual(without_label(conditions, Position(label=label)), kept)

class ByQuote(unittest.TestCase):
    def test_a_claim_any_task_read_takes_the_position_of_the_item_holding_its_quote(self):
        # a picture's claim (the overview's) quoting a list item is placed as the text task's claims are, so the
        # two readings keep the same conditions and merge
        from types import SimpleNamespace
        from semantic_pdf_diff.tasks import TaskCore
        core = SimpleNamespace(s=Settings(positions="provenance"), positions={}, listed={})
        TaskCore.find_positions(core, 1, blocks(LEAD, "Condition 1: no acknowledgement is received within 856 ms.",
                                                "Condition 2: 21 retransmissions fail."))
        position = TaskCore.position_by_quote(core, 1)
        self.assertEqual(position("Condition 1: no acknowledgement is received within 856 ms."),
                         Position(label="Condition 1", lead=LEAD))
        self.assertIsNone(position("Pump 1: 10 kW"))
        self.assertIsNone(TaskCore.position_by_quote(core, 2))  # a page without list items

class Model:
    """Reads each 'N ms', 'N retransmissions' or 'N kW' in a text task, putting the item's label in conditions as
    readers did ("Condition 1"); records each query."""
    def __init__(self, **settings):
        self.s = Settings(**settings)
        self.calls, self.cache_hits, self.usage, self.queries = 0, 0, {}, []

    def ask(self, prompt, schema, images=(), key=None):
        query = ExtractQuery.read(prompt)
        self.queries.append(query)
        claims = []
        for line in query.data.splitlines():
            label = re.match(r"(Condition \d|Pump \d)", line)
            for value, unit in re.findall(r"(\d+) (ms|retransmissions|kW)", line):
                claims.append({"entity": "link", "attribute": unit, "value": value, "kind": "text",
                               "quote": f"{value} {unit}", "conditions": label.group(1) if label else "",
                               "confidence": 0.9})
        return Extraction(claims=claims, complete=True)

class Pipeline(unittest.TestCase):
    def read(self, positions):
        from test_textdocs import extract
        import test_textdocs
        model_class, test_textdocs.Model = test_textdocs.Model, Model
        try:
            evidence, _, _, model = extract("spec.md", SPEC, positions=positions)
        finally:
            test_textdocs.Model = model_class
        return {e.value: e for e in evidence}, model

    def test_as_provenance_a_list_items_label_is_its_position(self):
        found, model = self.read("provenance")
        self.assertEqual((found["856"].conditions, found["856"].position),
                         ("", Position(label="Condition 1", lead=LEAD)))
        self.assertEqual(found["21"].position.label, "Condition 2")
        self.assertEqual((found["10"].conditions, found["10"].position), ("Pump 1", None))  # a name, not a position
        self.assertNotIn("position", found["10"].model_dump())

    def test_off_the_claims_are_as_read_and_the_queries_the_same(self):
        off, asked_off = self.read("conditions")
        self.assertEqual((off["856"].conditions, off["856"].position), ("Condition 1", None))
        _, asked_on = self.read("provenance")
        self.assertEqual([q.data for q in asked_off.queries], [q.data for q in asked_on.queries])

    def test_the_judge_never_sees_a_position(self):
        from semantic_pdf_diff.compare import PROVENANCE_FIELDS
        found, _ = self.read("provenance")
        self.assertNotIn("position", found["856"].model_dump(exclude=PROVENANCE_FIELDS))

if __name__ == "__main__":
    unittest.main()
