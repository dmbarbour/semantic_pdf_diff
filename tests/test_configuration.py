import stubs  # noqa: F401 (a clean environment)
from stubs import user_settings
import argparse
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from semantic_pdf_diff.settings import Settings
from semantic_pdf_diff.cli import add_run_options, load_settings
from semantic_pdf_diff.llm import Client

class ConfigurationTests(unittest.TestCase):
    def test_the_users_settings_the_endpoint_and_the_key(self):
        # the owner's four variables (docs/plans/configuration-in-the-store-2026-10-20.md): the endpoint and the key
        # from the environment, every other setting the user's (`config set --user`) or a store's
        env = {'OPENAI_BASE_URL':'http://example.test/v1', 'OPENAI_API_KEY':'test-only-key'}
        with patch.dict(os.environ, env), user_settings({'model':'small-vlm', 'max_calls':27, 'timeout':3.5,
                                                         'vision':False, 'aliases':{'chw':'chilled water'}}):
            s=Settings.from_env()
            self.assertEqual(s.base_url,env['OPENAI_BASE_URL'])
            self.assertEqual(s.model,'small-vlm')
            self.assertEqual(s.max_calls,27)
            self.assertEqual(s.timeout,3.5)
            self.assertFalse(s.vision)
            self.assertEqual(s.aliases,{'chw':'chilled water'})
            self.assertEqual(Client(s,None).api_key,'test-only-key')
            self.assertNotIn('test-only-key',s.model_dump_json())

    def test_an_optional_setting_can_be_switched_off_by_the_user(self):
        # code review 2026-10-08, C23: "none" failed validation as a number
        with user_settings({"table_rules": None}):
            self.assertIsNone(Settings.from_env().table_rules)
        with user_settings({"table_rules": 12}):
            self.assertEqual(Settings.from_env().table_rules, 12)

    def test_an_old_variable_is_ignored_with_a_warning_naming_its_setting(self):
        from semantic_pdf_diff import settings as module
        module._warned.discard('PDF_DIFF_CONCURRENCY')
        with patch.dict(os.environ, {'PDF_DIFF_CONCURRENCY':'32', 'OPENAI_MODEL':'old-way'}), \
                self.assertLogs('semantic_pdf_diff', 'WARNING') as logged:
            s=Settings.from_env()
        self.assertEqual((s.concurrency, s.model), (Settings().concurrency, Settings().model))
        self.assertIn('PDF_DIFF_CONCURRENCY is no longer read: `pdf-semantic-diff config set --user concurrency VALUE`',
                      '\n'.join(logged.output))

    def test_the_answers_cache_is_the_users(self):
        from semantic_pdf_diff.settings import cache_path
        with patch.dict(os.environ, {'PDF_DIFF_CACHE': '/c', 'XDG_CACHE_HOME': '/x', 'HOME': '/h'}):
            self.assertEqual(cache_path(), Path('/c/answers.sqlite'))
            del os.environ['PDF_DIFF_CACHE']
            self.assertEqual(cache_path(), Path('/x/semantic-pdf-diff/answers.sqlite'))
            del os.environ['XDG_CACHE_HOME']
            self.assertEqual(cache_path(), Path('/h/.cache/semantic-pdf-diff/answers.sqlite'))

    def test_empty_fallback_and_invalid_values(self):
        with patch.dict(os.environ, {'OPENAI_BASE_URL':'  '}, clear=True):
            self.assertEqual(Settings.from_env(),Settings())
        for name,value in [('max_calls','oops'),('vision','maybe'),('aliases','{')]:
            with self.subTest(name=name), user_settings({name:value}):
                with self.assertRaises(ValueError): Settings.from_env()

    def test_explicit_overrides_ignore_invalid_user_settings(self):
        with user_settings({'model':'users-model','max_calls':'oops','aliases':'invalid'}):
            s=Settings.from_env(model='explicit-model',max_calls=7,aliases={})
            self.assertEqual(s.model,'explicit-model')
            self.assertEqual(s.max_calls,7)
            self.assertEqual(s.aliases,{})

    def test_flags_over_a_config_file_over_the_users_settings(self):
        with tempfile.TemporaryDirectory() as directory, user_settings({'max_calls':13}):
            root=Path(directory)
            config=root/'config.json';config.write_text('{"max_calls": 17}')
            for extra,expected in [([],13),(['--config',str(config)],17),
                                   (['--config',str(config),'--max-calls','19'],19)]:
                parser=argparse.ArgumentParser();add_run_options(parser)
                self.assertEqual(load_settings(parser.parse_args(extra)).max_calls,expected)

    def test_the_pairs_judged_are_capped_by_a_flag(self):
        # the owner, 2026-10-19: "That 1000 item cap seems arbitrary, it should be configurable at least."
        parser=argparse.ArgumentParser();add_run_options(parser)
        with patch.dict(os.environ,{},clear=True):
            self.assertEqual(load_settings(parser.parse_args([])).max_pairs,1000)
            self.assertEqual(load_settings(parser.parse_args(['--max-pairs','5000'])).max_pairs,5000)
            self.assertEqual(load_settings(parser.parse_args(['--rerank','m'])).rerank_model,'m')

if __name__=='__main__': unittest.main()
