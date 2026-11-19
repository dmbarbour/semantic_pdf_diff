"""Tables of statements in the controlled corpus (statements.py; the requirements and textual claims plan, milestone
0): one system's requirements drawn in several shapes, none canonical, their statements placed by their words
and scored by them."""
import stubs  # noqa: F401 (a clean environment)
import unittest

from semantic_pdf_diff_lab.bench.controlled.representations import key, markdown
from semantic_pdf_diff_lab.bench.controlled.score import classify_statement, key_facts, score
from semantic_pdf_diff_lab.bench.controlled.statements import STATEMENT_KNOBS, buoy_requirements, shaped

def project(knob):
    p = buoy_requirements(1)
    p.knob = knob
    return shaped(p)

class Shapes(unittest.TestCase):
    def test_every_shape_prints_its_statements_whole_in_markdown(self):
        for knob in STATEMENT_KNOBS:
            with self.subTest(knob=knob):
                p = project(knob)
                k = key(p, markdown(p))
                statements = [f for f in k["facts"] if f.get("drawn") == "statement"]
                self.assertTrue(statements)
                self.assertEqual(k["absent"], [])
                self.assertTrue(all(f["forms"] for f in statements))

    def test_the_split_shape_prints_no_rationale_and_keys_none(self):
        self.assertFalse(any(f.attribute == "rationale" for f in project("split").facts))
        self.assertTrue(any(f.attribute == "rationale" for f in project("cells").facts))

    def test_a_statement_is_one_sentence_whatever_its_shape(self):
        said = {knob: next(f.value for f in project(knob).facts if f.id == "req2.statement")
                for knob in STATEMENT_KNOBS}
        self.assertEqual(len(set(said.values())), 1)
        self.assertTrue(said["split"].startswith("In the event of a loss of main power, the data logger shall"))

    def test_modality_is_the_basis(self):
        basis = {f.id: f.basis for f in project("cells").facts if f.attribute == "statement"}
        self.assertEqual((basis["req1.statement"], basis["req4.statement"], basis["req5.statement"],
                          basis["req6.statement"]), ("required", "recommended", "permitted", "intended"))

class Scored(unittest.TestCase):
    def setUp(self):
        p = project("cells")
        self.key = key(p, markdown(p))
        self.facts = {f.id: f for f in p.facts}

    def test_whole_fragment_numbers_and_other_words(self):
        st, lo = self.facts["req2.statement"], self.facts["req2.lo"]
        claims = [{"entity": "Data Retention", "attribute": "requirement text", "value": st.value},  # whole
                  {"entity": "data logger", "attribute": "retention", "value": f"at least {lo.value} hours"},
                  {"entity": "data logger", "attribute": "on power loss", "value": "retain every logged record"},
                  {"entity": "x", "attribute": "y", "value": "the moon is made of cheese"}]
        result = score(self.key, claims)
        self.assertEqual(result["outcomes"], {"fragment": 1, "right": 2, "text": 1})
        self.assertEqual(result["found"], 2)

    def test_a_statement_named_otherwise_is_loose(self):
        st = self.facts["req3.statement"]
        statements = [f for f in key_facts(self.key) if f.drawn == "statement"]
        self.assertEqual(classify_statement({"entity": "paint", "attribute": "finish", "value": st.value}, statements),
                         ("loose", "req3.statement"))
        self.assertEqual(classify_statement({"entity": "HMB-REQ-103", "attribute": "text", "value": st.value},
                                            statements), ("right", "req3.statement"))

    def test_keys_without_statements_score_as_before(self):
        from semantic_pdf_diff_lab.bench.controlled.corpus import water_treatment
        p = water_treatment(1)
        k = key(p, markdown(p))
        result = score(k, [{"entity": "pump", "attribute": "notes", "value": "retain every logged record"}])
        self.assertEqual(result["outcomes"], {"text": 1})

if __name__ == "__main__":
    unittest.main()
