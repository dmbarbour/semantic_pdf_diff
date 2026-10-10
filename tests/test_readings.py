import stubs  # noqa: F401 (a clean environment)
import random
import unittest
from semantic_pdf_diff.schema import Claim, Evidence, PdfLocator, claim_id
from semantic_pdf_diff.readings import reconcile

CID = 'sha256:' + 'c' * 64 + '.pdf'

def sighting(entity, attribute, value, unit='', conditions='', page=1, bbox=(0, 0, 400, 400), task='tile:p1:0',
             region='tile'):
    claim = Claim(entity=entity, attribute=attribute, value=value, unit=unit, conditions=conditions, kind='diagram',
                  quote=value, confidence=0.8)
    return Evidence(**claim.model_dump(), id=claim_id(CID, claim), content=CID,
                    locator=PdfLocator(page=page, bbox=bbox, region=region, task=task))

class Readings(unittest.TestCase):
    def test_readings_of_one_note_become_one_claim_with_every_wording(self):
        found = reconcile([
            sighting('handrails', 'material', '2x4 cedar', task='tile:p1:0'),
            sighting('Handrail', 'material/dimension', '2x4 Cedar', task='tile:p1:1', bbox=(200, 0, 600, 400)),
            sighting('handrails', 'material', '2x4 cedar', task='overview:p1', region='overview', bbox=(0, 0, 2448, 1584)),
        ])
        self.assertEqual(len(found), 1)
        words = {o.wording for o in found[0].occurrences}
        self.assertEqual(len(found[0].occurrences), 3)  # every reading stays a sighting
        self.assertIn('Handrail | material/dimension | 2x4 Cedar', words)
        self.assertEqual(found[0].locator.task, 'tile:p1:0')  # the most local reading represents it

    def test_distinct_facts_with_one_value_stay_apart(self):
        cases = [
            [sighting('West Module', 'finished floor height', "2' - 9 1/2\""),
             sighting('East Module', 'finished floor height', "2' - 9 1/2\"")],
            [sighting('tower', 'fore-aft stiffness', '291.01E+9', 'N•m2'),
             sighting('tower', 'side-to-side stiffness', '291.01E+9', 'N•m2')],
            [sighting('Door D1', 'identifier', '1.02'), sighting('Window W2', 'identifier', '1.02')],
            [sighting('MODULE A - PV STRUCTURAL MEMBER', 'member profile', 'L3X3X1/4'),
             sighting('MODULE B - PV STRUCTURAL MEMBER', 'member profile', 'L3X3X1/4')],
            [sighting('pump', 'power', '10', 'kW'), sighting('pump', 'power', '10', 'kW', page=2)],  # other page
            [sighting('pump', 'power', '10', 'kW'), sighting('pump', 'power', '10', 'kW', bbox=(500, 500, 900, 900))],
        ]
        for pair in cases:
            with self.subTest(pair[0].entity):
                self.assertEqual(len(reconcile(pair)), 2)

    def test_conditions_must_agree_among_all_readings(self):
        found = reconcile([
            sighting('rotor', 'speed', '12.1', 'rpm'),
            sighting('rotor', 'speed', '12.1', 'rpm', 'at rated wind speed', task='tile:p1:1'),
            sighting('rotor', 'speed', '12.1', 'rpm', 'during start-up', task='tile:p1:2'),
        ])
        self.assertEqual(len(found), 2)  # the unconditioned reading doesn't join both

    def test_the_local_reading_represents_one_with_conditions_from_a_wide_region(self):
        found = reconcile([sighting('member', 'section', 'W10X12', task='table:p1:0', region='table', bbox=(0, 0, 200, 50)),
                           sighting('member', 'section', 'W10X12', conditions='Structure South Elevation - Main',
                                    task='overview:p1', region='overview', bbox=(0, 0, 2448, 1584))])
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].conditions, '')  # the wide region's condition stays a wording, not the claim
        self.assertIn('member | section | W10X12 | Structure South Elevation - Main',
                      {o.wording for o in found[0].occurrences})

    def test_a_generic_reading_does_not_gather_distinct_facts(self):
        found = reconcile([sighting('beam', 'section', 'W10X15', task='text:p1:0', region='text', bbox=(0, 0, 300, 300)),
                           sighting('Floor Beam @ Grid 4', 'section', 'W10X15', task='tile:p1:0'),
                           sighting('Floor Beam @ Grid 5', 'section', 'W10X15', task='tile:p1:1')])
        self.assertEqual(len(found), 2)  # grid 4 and grid 5 stay apart

    def test_values_match_across_spacing_and_units_written_into_the_value(self):
        found = reconcile([sighting('pump', 'power', '10', 'kW'), sighting('pump', 'power', '10 kW', task='tile:p1:1')])
        self.assertEqual(len(found), 1)

    def test_a_units_case_and_a_decimal_comma_tell_values_apart(self):
        # code review 2026-10-08, D9: "5 MW" merged with "5 mW" (decision 0005), and "12,50" with "1,250"
        apart = [('5', 'MW', '5', 'mW'), ('12,50', '', '1,250', '')]
        for v1, u1, v2, u2 in apart:
            with self.subTest(v1=v1, v2=v2):
                found = reconcile([sighting('cell', 'power', v1, u1), sighting('cell', 'power', v2, u2, task='tile:p1:1')])
                self.assertEqual(len(found), 2)
        alike = [('1,250', '', '1250', ''), ('5', 'kw', '5', 'kW'), ('TBC', '', 'tbc', '')]
        for v1, u1, v2, u2 in alike:
            with self.subTest(v1=v1, v2=v2):
                found = reconcile([sighting('cell', 'power', v1, u1), sighting('cell', 'power', v2, u2, task='tile:p1:1')])
                self.assertEqual(len(found), 1)

    def test_result_does_not_depend_on_order(self):
        claims = [sighting('handrails', 'material', '2x4 cedar', task=f'tile:p1:{i}') for i in range(3)] + \
                 [sighting('Handrail', 'material/size', '2x4 cedar', task='tile:p1:9'),
                  sighting('pump', 'power', '10', 'kW')]
        expected = [e.model_dump() for e in reconcile(claims)]
        for seed in range(5):
            shuffled = claims[:]
            random.Random(seed).shuffle(shuffled)
            self.assertEqual([e.model_dump() for e in reconcile(shuffled)], expected)

if __name__ == '__main__':
    unittest.main()

class ReconcileScales(unittest.TestCase):
    """reconcile runs on every load of a store: 4,000 claims took 27 s when every claim was compared with every
    cluster (code review 2026-10-01, item 13)."""
    def test_thousands_of_claims_reconcile_quickly(self):
        import time
        from semantic_pdf_diff.readings import reconcile
        claims = [sighting(f'Pump P-{i % 900}', 'rated power', str(i % 1500), 'kW', page=1 + i % 20,
                           task=f'text:p{1 + i % 20}:{i % 7}', region='text') for i in range(4000)]
        started = time.monotonic()
        reconcile(claims)
        self.assertLess(time.monotonic() - started, 5)

    def test_thousands_of_claims_of_one_value_reconcile_quickly(self):
        """Each claim was compared with every cluster of its value: 4,000 rooms of one area took 50 s (code review
        2026-10-08, D5); only clusters seen on its pages can take it."""
        import time
        claims = [sighting(f'Room {i}', 'area', '25', 'm2', page=1 + i % 20, task=f'text:p{1 + i % 20}:0',
                           region='text') for i in range(4000)]
        started = time.monotonic()
        self.assertEqual(len(reconcile(claims)), 4000)
        self.assertLess(time.monotonic() - started, 5)
