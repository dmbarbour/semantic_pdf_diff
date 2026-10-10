"""Judges, checkers and analysts: their queries can't be changed by the environment, one cost cap covers a whole
command, and spot checks and rounds refuse documents not marked public (code review 2026-10-01, items 2 and 9)."""
import stubs  # noqa: F401 (a clean environment)
import os
import unittest
from unittest.mock import patch
from semantic_pdf_diff_lab.eval import rounds
from semantic_pdf_diff.llm import Budget, evaluator_settings
from semantic_pdf_diff.settings import EVALUATOR_SETTINGS, Settings

class EvaluatorSettings(unittest.TestCase):
    def test_the_environment_reaches_the_endpoint_only(self):
        quiet = evaluator_settings("judge-model")
        with patch.dict(os.environ, {"PDF_DIFF_RESPONSE_FORMAT": "json_object", "PDF_DIFF_SEED": "7",
                                     "PDF_DIFF_OUTPUT_TOKENS": "999", "PDF_DIFF_TIMEOUT": "33"}):
            loud = evaluator_settings("judge-model")
        self.assertEqual((loud.response_format, loud.seed, loud.output_tokens),
                         (quiet.response_format, quiet.seed, quiet.output_tokens))  # what shapes the query: fixed
        self.assertEqual(loud.timeout, 33)                                         # how it travels: configurable
        self.assertEqual(quiet.output_tokens, EVALUATOR_SETTINGS["output_tokens"])
        self.assertEqual(quiet.model_dump(exclude={"timeout"}),
                         Settings(model="judge-model", **EVALUATOR_SETTINGS).model_dump(exclude={"timeout"}))

    def test_a_small_context_profile_in_the_environment_doesnt_break_judges(self):
        # code review 2026-10-08, C9: the whole environment was validated, against the judges' own budget
        with patch.dict(os.environ, {"PDF_DIFF_CONTEXT_TOKENS": "4096"}):
            self.assertEqual(evaluator_settings("judge-model").context_tokens, EVALUATOR_SETTINGS.get(
                "context_tokens", Settings().context_tokens))

    def test_runtime_settings_must_be_endpoint_settings(self):
        self.assertEqual(evaluator_settings("m", concurrency=3, max_cost=1.5).max_cost, 1.5)
        with self.assertRaises(ValueError):
            evaluator_settings("m", output_tokens=100)

class CommandBudget(unittest.TestCase):
    def test_one_cap_across_the_clients_of_a_command(self):
        class Spent:
            def __init__(self, cost): self.cost = cost
        budget = Budget(1.0)
        self.assertEqual(budget.settings(), {"max_cost": 1.0})
        budget.add(Spent(0.75))
        self.assertEqual(budget.settings(), {"max_cost": 0.25})  # the next model gets what's left, not another $1
        budget.add(Spent(0.30))
        self.assertTrue(budget.exhausted())
        self.assertEqual(Budget(None).settings(), {})               # no cap
        with self.assertRaises(ValueError):
            Budget(0)                                               # once read as "no cap"

class PublicSlices(unittest.TestCase):
    MANIFEST = {"slices": [{"name": "open-a", "public": True}, {"name": "open-b", "public": True},
                           {"name": "client-c"}],
                "runs": [{"name": "fine", "slices": ["open-a", "open-b"]}, {"name": "leaky", "slices": ["open-a", "client-c"]}]}

    def test_runs_of_private_or_unknown_documents_are_refused(self):
        self.assertEqual(rounds.private_slices(["fine"], self.MANIFEST), [])
        self.assertEqual(rounds.private_slices(["fine", "leaky"], self.MANIFEST), ["client-c"])
        self.assertEqual(rounds.private_slices(["mystery"], self.MANIFEST), ["mystery"])  # unknown: refused too

if __name__ == "__main__":
    unittest.main()
