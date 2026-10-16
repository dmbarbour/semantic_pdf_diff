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
        self.assertEqual(context.misplaced({"entity": "BM-Case2", "attribute": "report", "conditions": ""}), [])

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

    def test_a_scope_a_record_holds_is_held_by_reference(self):
        # the lead-in as the claim's list record's text: in place by reference, not lost
        held = {**claim("retransmission timer", "709", ""), "records": LEAD}
        result = context.against_key(KEY, [held], {"text:p1": [LEAD]})
        self.assertEqual(result["placed"]["scope"], {"records": 1})
        self.assertEqual(result["audit"], {})

    def test_a_holder_is_kept_in_the_claims_stance_or_its_words(self):
        # milestone 5: a proposal's company, as the claim's stance (stored as links) or in its conditions
        key = {**KEY, "facts": [fact("timer.idle", "retransmission timer", "709",
                                     ctx={"holder": "Avelin", "attitude": "proposes"})] + KEY["facts"][1:]}
        stanced = {**claim("retransmission timer", "709", ""), "stance": [{"holder": "Avelin", "attitude": "proposes"}]}
        said = claim("retransmission timer", "709", "proposed by Avelin")
        unheld = claim("retransmission timer", "709", "")
        place = lambda c: context.against_key(key, [c], {"text:p1": [""]})["placed"].get("holder")  # noqa: E731
        self.assertEqual((place(stanced), place(said), place(unheld)),
                         ({"stance": 1}, {"conditions": 1}, {"nowhere": 1}))

class Readings(unittest.TestCase):
    def test_every_reading_counts_a_frame_only_a_later_sighting_gave(self):
        # one fact read by two tasks, merged into one claim: the first sighting has no frame, the second does
        import tempfile
        from types import SimpleNamespace
        from unittest.mock import patch
        from semantic_pdf_diff.schema import Claim, Evidence, PdfLocator, claim_id
        from semantic_pdf_diff.store import Store
        content = 'sha256:' + 'c' * 64 + '.pdf'
        with tempfile.TemporaryDirectory() as d, \
                patch.object(Store, 'files', lambda self, source=None: [SimpleNamespace(content=content)]):
            with Store(Path(d) / 'run1') as store:
                store.db.execute("INSERT INTO content (id, size) VALUES (?, 1)", (content,))
                for task, frame in (('figure:p1:0', ''), ('tile:p1:0', 'above the station platform')):
                    c = Claim(entity='E1', attribute='height', value='120', unit='ft', kind='diagram', quote='E1 120',
                              confidence=.9, frame=frame)
                    store.record_task({'content': content, 'page': 1, 'task': task, 'status': 'complete',
                                       'claims': 1},
                                      [Evidence(**c.model_dump(), id=claim_id(content, c), content=content,
                                                locator=PdfLocator(page=1, bbox=(0, 0, 9, 9),
                                                                   region=task.split(':')[0], task=task))])
                store.set_reconcile(True)
            (readings,) = context.every_reading(Path(d)).values()
        self.assertEqual(sorted((c['_task'], c.get('frame')) for _, _, c in readings),
                         [('figure:p1:0', None), ('tile:p1:0', 'above the station platform')])

if __name__ == "__main__":
    unittest.main()
