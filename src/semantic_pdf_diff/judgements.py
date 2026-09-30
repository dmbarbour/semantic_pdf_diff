"""Judgement records: every rater's answers about a batch's units, in one shape.

A rater is a model judge, a person, or a mechanical check (the quote check). A record says who
rated and what kind of rater it is, the question, the target (a unit; for a claim, its side and
index; the order the sets were shown, where there was one), the answer, and its status: answered,
or failed after some attempts. No rater is ground truth: the weighted quality estimates (plans
index) weigh records from all of them.

Verdict files keep their layout, so rounds can still be re-decided offline from them alone; this
adapter is the one place that reads it. The rule for asking again after a failure lives here too.
(docs/plans/content-addressed-queries-2026-09-28.md, item 7)
"""
import json
from dataclasses import dataclass, field
from pathlib import Path

QUESTIONS = {
    "pair": "which of two claim sets is better (answer: score 1 when the variant's, 0 the baseline's, 0.5 the same; "
            "None when a person can't tell), with confidence, wrong counts, problems, note and remarks",
    "claim": "is this claim a faithful reading, bound to the right thing (answer: mark ok, wrong or unsure; problems)",
    "quote": "is this claim's quote on its page, as excerpts of the text layer (answer: found)",
}
KINDS = ("model", "person", "check")
MAX_ATTEMPTS = 2  # a failed verdict is asked once more at most, when a variant's judging ends
HUMAN = "verdicts-human"  # people's verdicts (spot checks); every other verdicts folder holds judges'

@dataclass
class Record:
    rater: str
    kind: str                # model, person or check
    question: str            # pair, claim or quote (QUESTIONS)
    unit: str
    order: str = ""          # baseline-first or variant-first: how the sets were shown (people see one order)
    side: str = ""           # claim, quote: baseline or variant
    index: int = -1          # claim, quote: the claim's index in its side's list (pairs.json)
    answer: dict = field(default_factory=dict)
    status: str = "answered"  # or failed
    attempts: int = 1

def failures_folder(verdicts_dir):
    """Where a verdicts folder's failed verdicts are counted: failures/ for verdicts/, failures-<x>/
    for verdicts-<x>/. (All folders once shared failures/: a unit that failed twice under one rubric
    was then never asked under another.)"""
    return "failures" + verdicts_dir[len("verdicts"):] if verdicts_dir.startswith("verdicts") else f"{verdicts_dir}-failures"

def ask_again(attempts, retry_failed=False):
    """Whether to ask for a verdict that has failed `attempts` times: one that never failed is
    asked; a failed one only when retrying failures, and only until MAX_ATTEMPTS."""
    return not attempts or retry_failed and attempts < MAX_ATTEMPTS

def read(folder, verdicts_dir="verdicts"):
    """The records in one verdicts folder, in file order: each verdict a pair record (per order
    shown), each marked claim a claim record, and each verdict still failed a failed pair record."""
    folder = Path(folder)
    kind = "person" if verdicts_dir == HUMAN else "model"
    out, names = [], {}
    for path in sorted((folder / verdicts_dir).glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        rater = names[path.name] = data["reviewer"]
        for unit, orders in data["verdicts"].items():
            for order, v in orders.items():
                out.append(Record(rater, kind, "pair", unit, order=order,
                                  answer={k: x for k, x in v.items() if k != "claims"}))
                for side, claims in (v.get("claims") or {}).items():
                    for c in claims:
                        out.append(Record(rater, kind, "claim", unit, order=order, side=side, index=c["index"],
                                          answer={"mark": c["mark"], "problems": c.get("problems", []),
                                                  "claim": c.get("claim")}))
    for path in sorted((folder / failures_folder(verdicts_dir)).glob("*.json")):
        rater = names.get(path.name, path.stem)  # a judge that never answered has no verdicts file to name it
        for key, attempts in json.loads(path.read_text(encoding="utf-8")).items():
            unit, _, order = key.partition("|")
            out.append(Record(rater, kind, "pair", unit, order=order, status="failed", attempts=attempts))
    return out

def answered(records, question="pair"):
    return [r for r in records if r.question == question and r.status == "answered"]

def by_rater(records):
    """{rater: {unit: {order: answer}}} of answered pair records, raters and units in record order."""
    out = {}
    for r in answered(records):
        out.setdefault(r.rater, {}).setdefault(r.unit, {})[r.order] = r.answer
    return out

# --- raters ---------------------------------------------------------------------------------------

class ModelJudge:
    """A model comparing each unit's two claim sets in both orders (rounds.judge_pairs), its
    answers recorded in the folder's fixture. `errors` holds the last rating's failures, for notes."""
    kind = "model"

    def __init__(self, client, name=None, rubric="v1", verdicts_dir="verdicts"):
        self.client, self.name = client, name or client.s.model
        self.rubric, self.verdicts_dir, self.errors = rubric, verdicts_dir, []

    def rate(self, folder, limit=None, only=None, retry_failed=False, progress=None):
        from .rounds import judge_pairs
        _, _, self.errors = judge_pairs(folder, self.client, self.name, progress, limit, self.rubric, only, retry_failed,
                                        self.verdicts_dir)
        return [r for r in read(folder, self.verdicts_dir) if r.rater == self.name]

class Person:
    """A person's spot-check answers (downloaded from the spot-check page), as verdicts."""
    kind = "person"

    def __init__(self, answers_file):
        self.answers_file = Path(answers_file)
        self.name = json.loads(self.answers_file.read_text(encoding="utf-8")).get("reviewer")

    def rate(self, folder):
        from .rounds import import_spotcheck
        import_spotcheck(folder, self.answers_file)
        return [r for r in read(folder, HUMAN) if r.rater == self.name]

class QuoteCheck:
    """A mechanical rater: is each claim's quote on its page, read as extraction's quote matching
    reads excerpts? A heuristic, weighed as one: a quote found says little about the claim's binding,
    and quotes read from images (visual units) are rarely in the text layer."""
    kind, name = "check", "quote-check"

    def rate(self, folder):
        from .extract import excerpted
        batch = json.loads((Path(folder) / "pairs.json").read_text(encoding="utf-8"))
        out = []
        for item in batch["items"]:
            text = item.get("page_text_full") or item["page_text"]
            for side in ("baseline", "variant"):
                for k, c in enumerate(item[side]):
                    out.append(Record(self.name, self.kind, "quote", item["id"], side=side, index=k,
                                      answer={"found": excerpted(c.get("quote", ""), text)}))
        return out
