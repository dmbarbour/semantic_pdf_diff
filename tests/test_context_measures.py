"""Context measures without the model (docs/plans/claim-context-2026-10-14.md, milestone 2): the keys' context by
kind, what a claim's request showed, where each kind landed and, where lost, why."""
import stubs  # noqa: F401 (a clean environment)
import json
import unittest
from pathlib import Path

from semantic_pdf_diff_lab.bench import context
from semantic_pdf_diff_lab.bench.controlled import contexts

ROOT = Path(__file__).resolve().parent.parent
LEAD = "When the link is idle, the following values apply."

def fact(fid, attribute, value, conditions="", ctx=None):
    return {"id": fid, "entity": "link", "aliases": [], "attribute": attribute, "synonyms": [], "value": value,
            "unit": "ms", "conditions": conditions, "forms": [{"form": "prose", "page": 1, "box": [0, 0, 1, 1]}],
            "context": ctx or ({"scope": conditions} if conditions else {})}

KEY = {"facts": [fact("timer.idle", "retransmission timer", "709", "link idle"),
                 fact("timer.congested", "retransmission timer", "856", "link congested"),
                 fact("window.idle", "window", "40", "link idle")],
       "printed": [{"text": v, "page": 1, "role": "fact", "facts": [i]}
                   for v, i in (("709", "timer.idle"), ("856", "timer.congested"), ("40", "window.idle"))]}

def claim(attribute, value, conditions, task="text:p1"):
    return {"entity": "link", "attribute": attribute, "value": value, "unit": "ms", "conditions": conditions,
            "_task": task}

class Keys(unittest.TestCase):
    def test_every_condition_the_generator_writes_is_classed(self):
        unclassed = {f["conditions"] for path in sorted((ROOT / "benchmarks/controlled").glob("docs*/*.key.json"))
                     for f in json.loads(path.read_text(encoding="utf-8"))["facts"]
                     if "unclassed" in f.get("context", {})}
        self.assertEqual(unclassed, set())  # a new condition is classed in contexts.KINDS

    def test_kinds_and_declared_context(self):
        self.assertEqual([contexts.kind_of(c) for c in ("July", "at peak flow", "95th percentile", "maximum",
                                                        "Hall C", "revision B", "ISSUED FOR REVIEW")],
                         ["scope", "scope", "frame", "bound", "subject", "provenance", "sibling"])
        self.assertEqual(contexts.family("lcc-plan-s1-rotated"), "lcc-plan")

class Shown(unittest.TestCase):
    def test_a_request_shows_its_source_not_its_instructions(self):
        from semantic_pdf_diff.tasks import ExtractQuery
        prompt = ExtractQuery("Extract claims with conditions (load, time).", "text", "4 Timers",
                              "", "The timer is 709 ms.").prompt()
        self.assertEqual(context.words(context.shown(prompt)), {"4", "timer", "709", "ms"})
        table = "Decide how rows become claims.\nTABLE: page 1\nCOLUMNS: A: Tag\nYOUR EARLIER ANSWER: link idle"
        self.assertNotIn("idle", context.shown(table))

    def test_grounding_and_misplaced(self):
        self.assertEqual([context.grounding(c, ["The timer is 709 ms when the link is idle."])
                          for c in ("link idle", "idle, congested", "congested", "")],
                         ["grounded", "partly", "unsupported", None])
        self.assertEqual(context.misplaced({"entity": "Room 104", "attribute": "dimension 2",
                                            "conditions": "Condition 3; to face of finish"}),
                         ["numbered in conditions", "numbered in attribute", "frame in conditions"])
        self.assertEqual(context.misplaced({"entity": "Pump 2", "attribute": "capacity", "conditions": "at 2 bar"}),
                         [])

class AgainstKey(unittest.TestCase):
    def test_where_each_scope_landed_and_why_one_was_lost(self):
        claims = [claim("retransmission timer", "709", "link idle"),           # kept
                  claim("retransmission timer", "856", "", task="text:p2"),    # lost, though its request said it
                  claim("window", "40", "link congested")]                     # a neighbour's scope instead
        shown = {"text:p1": [LEAD + " Timer 709 ms. Window 40 ms."],
                 "text:p2": ["When the link is congested, the timer is 856 ms."]}
        result = context.against_key(KEY, claims, shown)
        self.assertEqual(result["placed"]["scope"], {"conditions": 1, "nowhere": 2})  # a neighbour's: nowhere
        self.assertEqual(result["audit"]["scope"], {"shown, not used": 1, "misapplied": 1})

    def test_not_shown_and_image_only(self):
        claims = [claim("retransmission timer", "856", "", task="text:p2"),
                  claim("retransmission timer", "709", "", task="tile:p1:0")]
        result = context.against_key(KEY, claims, {"text:p2": ["The timer is 856 ms."], "tile:p1:0": [""]})
        self.assertEqual(result["audit"]["scope"], {"not shown": 1, "image only": 1})

if __name__ == "__main__":
    unittest.main()
