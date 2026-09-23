import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import pymupdf
from semantic_pdf_diff.models import Settings
from semantic_pdf_diff.cli import main
from semantic_pdf_diff.llm import Client

class ConfigurationTests(unittest.TestCase):
    def test_environment_types_and_key(self):
        env = {'OPENAI_BASE_URL':'http://example.test/v1', 'OPENAI_MODEL':'small-vlm',
               'OPENAI_API_KEY':'test-only-key', 'PDF_DIFF_MAX_CALLS':'27',
               'PDF_DIFF_TIMEOUT':'3.5', 'PDF_DIFF_VISION':'false',
               'PDF_DIFF_ALIASES':'{"chw":"chilled water"}'}
        with patch.dict(os.environ, env, clear=True), tempfile.TemporaryDirectory() as directory:
            s=Settings.from_env()
            self.assertEqual(s.base_url,env['OPENAI_BASE_URL'])
            self.assertEqual(s.model,'small-vlm')
            self.assertEqual(s.max_calls,27)
            self.assertEqual(s.timeout,3.5)
            self.assertFalse(s.vision)
            self.assertEqual(s.aliases,{'chw':'chilled water'})
            self.assertEqual(Client(s,Path(directory)).api_key,'test-only-key')
            self.assertNotIn('test-only-key',s.model_dump_json())

    def test_empty_fallback_and_invalid_values(self):
        with patch.dict(os.environ, {'OPENAI_BASE_URL':'  ', 'OPENAI_MODEL':''}, clear=True):
            self.assertEqual(Settings.from_env(),Settings())
        for name,value in [('PDF_DIFF_MAX_CALLS','oops'),('PDF_DIFF_VISION','maybe'),('PDF_DIFF_ALIASES','{')]:
            with self.subTest(name=name), patch.dict(os.environ,{name:value},clear=True):
                with self.assertRaises(ValueError): Settings.from_env()

    def test_explicit_overrides_ignore_invalid_environment(self):
        with patch.dict(os.environ, {'OPENAI_MODEL':'environment-model','PDF_DIFF_MAX_CALLS':'oops',
                                    'PDF_DIFF_ALIASES':'invalid'},clear=True):
            s=Settings.from_env(model='explicit-model',max_calls=7,aliases={})
            self.assertEqual(s.model,'explicit-model')
            self.assertEqual(s.max_calls,7)
            self.assertEqual(s.aliases,{})

    def test_cli_file_environment_precedence(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ,{'PDF_DIFF_MAX_CALLS':'13'},clear=True):
            root=Path(directory)
            pdf=root/'test.pdf'
            doc=pymupdf.open();doc.new_page();doc.save(pdf);doc.close()
            config=root/'config.json';config.write_text('{"max_calls": 17}')
            for extra,expected in [([],13),(['--config',str(config)],17),
                                   (['--config',str(config),'--max-calls','19'],19)]:
                stream=io.StringIO()
                with contextlib.redirect_stdout(stream):
                    code=main([str(pdf),str(pdf),'--plan',*extra])
                self.assertEqual(code,0)
                self.assertEqual(json.loads(stream.getvalue())['max_calls'],expected)

if __name__=='__main__': unittest.main()
