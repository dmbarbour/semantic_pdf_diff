import random
import unittest
from semantic_pdf_diff.models import Claim, Evidence, PdfLocator, claim_id
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
        self.assertIn('handrails | material | 2x4 cedar', words)
        # The most informative reading represents it ("material/dimension" says more than "material").
        self.assertEqual((found[0].attribute, found[0].locator.task), ('material/dimension', 'tile:p1:1'))

    def test_distinct_facts_with_one_value_stay_apart(self):
        cases = [
            [sighting('West Module', 'finished floor height', "2' - 9 1/2\""),
             sighting('East Module', 'finished floor height', "2' - 9 1/2\"")],
            [sighting('tower', 'fore-aft stiffness', '291.01E+9', 'N•m2'),
             sighting('tower', 'side-to-side stiffness', '291.01E+9', 'N•m2')],
            [sighting('Door D1', 'identifier', '1.02'), sighting('Window W2', 'identifier', '1.02')],
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

    def test_a_reading_with_conditions_represents_one_without(self):
        found = reconcile([sighting('tower', 'damping ratio', '1', '%', task='text:p1:0', region='text'),
                           sighting('tower', 'damping ratio', '1', '%', 'isolated tower, without rotor-nacelle mass')])
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].conditions, 'isolated tower, without rotor-nacelle mass')

    def test_values_match_across_spacing_and_units_written_into_the_value(self):
        found = reconcile([sighting('pump', 'power', '10', 'kW'), sighting('pump', 'power', '10 kW', task='tile:p1:1')])
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
