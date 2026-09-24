import contextlib
import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import pymupdf
from semantic_pdf_diff.cli import main
from semantic_pdf_diff.extract import extract_pdf
from semantic_pdf_diff.models import Extraction, Judgment, Settings
from semantic_pdf_diff.provenance import (COMPARISON_SETTINGS, EXTRACTION_SETTINGS, comparison_interpreter,
                                          content_id, extraction_interpreter, normalized_extension)

GOOD = {'entity': 'primary pump', 'attribute': 'rated power', 'value': '10', 'unit': 'kW',
        'kind': 'text', 'quote': '10 kW', 'confidence': .9}

def make_pdf(path, text='Pump rated power 10 kW'):
    doc = pymupdf.open(); page = doc.new_page(width=300, height=300); page.insert_text((40, 40), text)
    doc.save(path); doc.close()
    return path

class Recorder:
    """Answers extraction with one claim quoting '10 kW'; comparison calls are recorded."""
    def __init__(self, **settings):
        self.s = Settings(**settings)
        self.prompts = []
        self.calls, self.cache_hits, self.usage = 0, 0, {}
    def ask(self, prompt, schema, images=()):
        self.prompts.append(prompt)
        if schema is Judgment:
            return Judgment(relation='equivalent', rationale='fixture', confidence=.9, same_conditions=True)
        return Extraction(claims=[GOOD] if 'SOURCE DATA:\nPump' in prompt else [], complete=True)

class ContentTests(unittest.TestCase):
    def test_content_id_uses_bytes_and_normalized_extension(self):
        self.assertEqual(content_id(b'x', 'a.PDF'), content_id(b'x', 'b.pdf'))
        self.assertNotEqual(content_id(b'x', 'a.txt'), content_id(b'x', 'a.md'))
        self.assertEqual(content_id(b'x', 'a.jpeg'), content_id(b'x', 'a.jpg'))
        self.assertTrue(content_id(b'x', 'a.pdf').startswith('sha256:') and content_id(b'x', 'a.pdf').endswith('.pdf'))
        self.assertIsNone(normalized_extension('Makefile'))
        with self.assertRaises(ValueError):
            content_id(b'x', 'README')

    def test_evidence_ids_survive_renames(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            first = make_pdf(root / 'first.pdf')
            second = root / 'renamed copy.pdf'; shutil.copy(first, second)
            ids = []
            for path in (first, second):
                cid = content_id(path.read_bytes(), path.name)
                evidence, _ = extract_pdf(path, cid, root, Recorder(vision=False))
                ids.append([e.id for e in evidence])
                self.assertTrue(all(e.content == cid for e in evidence))
            self.assertTrue(ids[0])
            self.assertEqual(ids[0], ids[1])

    def test_locator_and_derivation(self):
        with tempfile.TemporaryDirectory() as d:
            path = make_pdf(Path(d) / 't.pdf')
            evidence, coverage = extract_pdf(path, content_id(path.read_bytes(), path.name), Path(d), Recorder(vision=False))
            e = evidence[0]
            self.assertEqual((e.locator.format, e.locator.page, e.locator.region), ('pdf', 1, 'text'))
            self.assertEqual([step.step for step in e.derivation], ['pdf-text-layer', 'model-extraction'])
            self.assertTrue(all('content' in r and 'task' in r for r in coverage))

class ClaimContextTests(unittest.TestCase):
    def test_context_fields_default_and_salvage(self):
        result = Extraction.model_validate({'complete': True, 'claims': [
            {**GOOD, 'basis': 'wishful', 'topic': None, 'context': None},
            {**GOOD, 'basis': 'measured', 'uncertainty': '± 0.5 kW', 'role': 'duty pump motor'}]})
        self.assertTrue(result.complete)
        self.assertEqual([c.basis for c in result.claims], ['unknown', 'measured'])
        self.assertEqual(result.claims[0].topic, '')
        self.assertEqual(result.claims[1].uncertainty, '± 0.5 kW')

class InterpreterTests(unittest.TestCase):
    def test_interpreters_hold_only_output_affecting_settings(self):
        s = Settings(timeout=5, max_calls=3, base_url='http://user:secret@host/v1')
        extract = extraction_interpreter(s)
        self.assertEqual(set(extract.settings), set(EXTRACTION_SETTINGS))
        self.assertNotIn('secret', extract.model_dump_json())
        self.assertIn('PyMuPDF', extract.versions)
        self.assertEqual(set(comparison_interpreter(s).settings), set(COMPARISON_SETTINGS))
        self.assertNotEqual(extract.prompt_hash, comparison_interpreter(s).prompt_hash)
        self.assertNotEqual(extract.settings, extraction_interpreter(Settings(tile_points=500)).settings)

class CliTests(unittest.TestCase):
    def run_cli(self, root, a, b):
        client = Recorder(vision=False)
        with patch('semantic_pdf_diff.cli.Client', lambda settings, cache: client), \
             contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
            code = main([str(a), str(b), '--out', str(root / 'out'), '--no-vision'])
        return code, client

    def test_same_content_is_extracted_once_and_never_compared(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            a = make_pdf(root / 'team-a.pdf'); b = root / 'team-b.pdf'; shutil.copy(a, b)
            code, client = self.run_cli(root, a, b)
            report = json.loads((root / 'out/report.json').read_text())
            self.assertEqual(code, 2)  # --no-vision is deliberately incomplete
            self.assertFalse(any('Compare exactly' in p for p in client.prompts))
            self.assertEqual(report['findings'], [])
            self.assertEqual(len(report['shared']), 1)
            self.assertEqual(len({f['content'] for f in report['files']}), 1)
            self.assertIn('team-a.pdf / team-a.pdf; team-b.pdf / team-b.pdf', (root / 'out/report.html').read_text())

    def test_v2_outputs(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            a = make_pdf(root / 'a.pdf'); b = make_pdf(root / 'b.pdf', 'Pump rated power 12 kW, design load')
            code, client = self.run_cli(root, a, b)
            evidence = json.loads((root / 'out/evidence.json').read_text())
            report = json.loads((root / 'out/report.json').read_text())
            self.assertEqual(evidence['schema_version'], 2)
            self.assertEqual([s['id'] for s in evidence['sources']], ['s1', 's2'])
            self.assertEqual(set(evidence['interpreters']), {'extract'})
            self.assertEqual(set(report['interpreters']), {'extract', 'compare'})
            self.assertFalse(any('document' in e for e in evidence['evidence']))
            self.assertFalse(list(root.glob('out/evidence-*.json')))

    def test_same_file_names_get_distinct_source_names(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / 'x').mkdir(); (root / 'y').mkdir()
            a = make_pdf(root / 'x/report.pdf'); b = make_pdf(root / 'y/report.pdf', 'Pump rated power 12 kW')
            with contextlib.redirect_stdout(io.StringIO()) as out:
                main([str(a), str(b), '--plan'])
            names = [s['name'] for s in json.loads(out.getvalue())['sources']]
            self.assertEqual(names, ['report.pdf [s1]', 'report.pdf [s2]'])

if __name__ == '__main__':
    unittest.main()
