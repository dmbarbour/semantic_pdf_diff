import stubs  # noqa: F401 (a clean environment)
from stubs import source_data
import itertools
import tempfile
import unittest
from pathlib import Path
import pymupdf
from semantic_pdf_diff.extract import extract_pdf
from semantic_pdf_diff.models import Claim, Evidence, Extraction, PdfLocator, Settings, Source, claim_id, merge_occurrences
from semantic_pdf_diff.provenance import content_id, extraction_interpreter
from semantic_pdf_diff.store import Store

CID = 'sha256:' + 'c' * 64 + '.pdf'
FACT = {'entity': 'Primary pump', 'attribute': 'rated power', 'value': '10', 'unit': 'kW', 'kind': 'text',
        'quote': '10 kW', 'confidence': .8}

def sighting(region, page=1, bbox=(0, 0, 100, 100), task=None, **changes):
    claim = Claim(**{**FACT, **changes})
    return Evidence(**claim.model_dump(), id=claim_id(CID, claim), content=CID,
                    locator=PdfLocator(page=page, bbox=bbox, region=region, task=task or f'{region}:p{page}'))

class Identity(unittest.TestCase):
    def test_what_makes_the_same_claim(self):
        base = Claim(**FACT)
        same = [{'quote': 'Rated power 10 kW'}, {'confidence': .3}, {'kind': 'chart'},
                {'entity': '  primary   PUMP '}, {'attribute': 'Rated Power'}]
        for change in same:
            with self.subTest(change=change):
                self.assertEqual(claim_id(CID, Claim(**{**FACT, **change})), claim_id(CID, base))
        different = [{'unit': 'KW'}, {'value': '12'}, {'approximate': True}, {'basis': 'measured'},
                     {'conditions': 'design load'}]
        for change in different:
            with self.subTest(change=change):
                self.assertNotEqual(claim_id(CID, Claim(**{**FACT, **change})), claim_id(CID, base))
        self.assertNotEqual(claim_id('sha256:' + 'd' * 64 + '.pdf', base), claim_id(CID, base))

class Merging(unittest.TestCase):
    def test_order_never_matters(self):
        sightings = [sighting('overview', confidence=.95), sighting('tile', bbox=(0, 0, 50, 50), task='tile:p1:0'),
                     sighting('tile', bbox=(0, 0, 40, 40), task='tile:p1:1', quote='Rated power 10 kW'),
                     sighting('text', page=3, bbox=(0, 0, 300, 20), task='text:p3:0.0')]
        results = {tuple(e.model_dump_json() for e in merge_occurrences(order))
                   for order in itertools.permutations(sightings)}
        self.assertEqual(len(results), 1)
        (merged,) = merge_occurrences(sightings)
        self.assertEqual(merged.locator.task, 'text:p3:0.0')  # native before visual
        self.assertEqual(merged.confidence, .95)
        self.assertEqual([o.locator.task for o in merged.occurrences], ['overview:p1', 'tile:p1:0', 'tile:p1:1', 'text:p3:0.0'])
        (visual,) = merge_occurrences(sightings[:3])
        self.assertEqual(visual.locator.task, 'tile:p1:1')  # tile before overview, then the smallest region

class Extraction_(unittest.TestCase):
    class Model:
        """Every task that can see '10 kW' reports the same fact, quoted its own way."""
        def __init__(self, **settings):
            self.s = Settings(**settings)
            self.calls, self.cache_hits, self.usage = 0, 0, {}
        def ask(self, prompt, schema, images=(), key=None):
            data = source_data(prompt)
            if images or '10 kW' in data:
                quote = '10 kW' if not images else 'Pump 10 kW'
                return Extraction(claims=[{**FACT, 'quote': quote, 'kind': 'chart' if images else 'text'}], complete=True)
            return Extraction(claims=[], complete=True)

    def pdf(self, root):
        doc = pymupdf.open()
        for _ in range(2):
            doc.new_page(width=500, height=500).insert_text((40, 40), 'Pump rated power 10 kW')
        path = root / 'two.pdf'; doc.save(path); doc.close()
        return path, content_id(path.read_bytes(), path.name)

    def test_one_claim_across_passes_and_pages(self):
        with tempfile.TemporaryDirectory() as d:
            path, cid = self.pdf(Path(d))
            evidence, coverage = extract_pdf(path, cid, Path(d), self.Model(tile_points=300))
            self.assertEqual(len(evidence), 1)
            e = evidence[0]
            regions = {o.locator.region for o in e.occurrences}
            self.assertEqual(regions, {'text', 'tile', 'overview'})
            self.assertEqual({o.locator.page for o in e.occurrences}, {1, 2})
            self.assertEqual((e.locator.region, e.locator.page), ('text', 1))

    def test_store_is_order_independent_and_replay_idempotent(self):
        with tempfile.TemporaryDirectory() as d, Store(Path(d) / 'store') as store:
            path, cid = self.pdf(Path(d))
            store.save_source(Source(name='two', roots=[str(path)]))
            store.rescan('two')
            recorded = []
            evidence, _ = extract_pdf(path, cid, store.folder, self.Model(tile_points=300),
                                      on_task=lambda row, found: recorded.append((row, found)))
            for row, found in reversed(recorded):  # finish tasks in the opposite order
                store.record_task(row, found)
            self.assertEqual([e.model_dump() for e in store.evidence(cid)], [e.model_dump() for e in evidence])
            for row, found in recorded:  # replaying every task changes nothing
                store.record_task(row, found)
            self.assertEqual([e.model_dump() for e in store.evidence(cid)], [e.model_dump() for e in evidence])
            store.bind(extraction_interpreter(Settings(tile_points=300)))
            store.bind(extraction_interpreter(Settings(tile_points=200)), reset=True)  # clears visual sightings only
            (kept,) = store.evidence(cid)
            self.assertEqual(kept.id, evidence[0].id)
            self.assertEqual({o.locator.region for o in kept.occurrences}, {'text'})

if __name__ == '__main__':
    unittest.main()
