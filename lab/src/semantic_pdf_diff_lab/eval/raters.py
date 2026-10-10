"""Raters: a model judging pairs (ModelJudge), a person's spot-check answers (Person), a mechanical quote check
(QuoteCheck), each rating a batch into verdict records (judgements.py). Split from judgements.py, which the rounds'
judging imports while these call it (code review 2026-10-08, E8: the lab's import cycles).
"""
import json
from pathlib import Path

from .judgements import HUMAN, Record, read

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
        from semantic_pdf_diff.quotes import excerpted
        from .rounds import load_batch
        batch = load_batch(folder)
        out = []
        for item in batch["items"]:
            text = item.get("page_text_full") or item["page_text"]
            for side in ("baseline", "variant"):
                for k, c in enumerate(item[side]):
                    out.append(Record(self.name, self.kind, "quote", item["id"], side=side, index=k,
                                      answer={"found": excerpted(c.get("quote", ""), text)}))
        return out
