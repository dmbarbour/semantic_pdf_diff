"""Spot checks: people judging the same pairs as the panel, blind, and how their verdicts compare with the
judges'. Split from rounds.py (milestone 8).
"""
import json
import random
import re
from collections import Counter, defaultdict
from pathlib import Path

from .. import judgements
from ..rubrics import CLAIM_MARKS, CLAIM_PROBLEMS, PAIRWISE, PAIR_PROBLEMS, rubric as rubric_of
from .units import _ident
from .judging import _set_note
from .decisions import interval, region, unit_scores

# --- spot checks: people judging the same pairs as the panel ------------------------------

SPOTCHECK_FORMAT = "semantic-pdf-diff-spotcheck-answers"
BETTER = [{"name": "A", "label": "A is better"}, {"name": "B", "label": "B is better"},
          {"name": "same", "label": "About the same"}, {"name": "unsure", "label": "Can't tell"}]
SURE = [{"name": "high", "label": "Sure"}, {"name": "medium", "label": "Fairly sure"}, {"name": "low", "label": "Guessing"}]

def write_spotcheck(folder, seed=3):
    """spotcheck.html: a batch's units for a person, blind (each unit's sets shown as A and B in
    a random order, recorded in spotcheck-order.json beside it), with the judges' questions."""
    folder = Path(folder)
    batch = json.loads((folder / "pairs.json").read_text(encoding="utf-8"))
    rng = random.Random(seed)
    order, items = {}, []
    def public(item, claims, side, other):
        """Claims for the page: without internals, with the input a text or table claim was read
        from, and the position of the same claim in the other set (marked together)."""
        twins = {_ident(c): k for k, c in enumerate(item[other])}
        sources = item.get("sources") or {}
        if set(sources) <= {"baseline", "variant"}:  # each side's own inputs (batches before 2026-09-28: shared)
            sources = sources.get(side) or {}
        out = []
        for c in claims:
            shown = {k: v for k, v in c.items() if not k.startswith("_")}
            task = c.get("_task") or ""
            read = sources.get(task)
            shown["source"] = read if read else ("read from an image of this part of the page"
                                                 if task.startswith(("tile", "figure", "overview")) else "")
            shown["twin"] = twins.get(_ident(c))
            out.append(shown)
        return out
    for item in batch["items"]:
        first = rng.choice(("baseline", "variant"))
        second = "variant" if first == "baseline" else "baseline"
        order[item["id"]] = first
        counts = item.get("counts") or {}
        note = lambda side: _set_note(len(item[side]), counts.get(side, len(item[side])), item.get("hidden_shared", 0))
        band = item.get("band")
        document = re.sub(r"-[0-9a-f]{8}$", "", item["run"])
        items.append({"id": item["id"], "image": item["image"], "page_text": item["page_text"],
                      "title": f"{document}, page {item['page']}, {item['family']} content"
                               + (f", part {band[0] + 1} of {band[1]}" if band else ""),
                      "headings": " | ".join(item.get("sections") or ()), "before": item.get("before", ""),
                      "within": item.get("within", ""), "A": public(item, item[first], first, second),
                      "B": public(item, item[second], second, first), "page_image": item.get("page_image", ""),
                      "page_text_full": item.get("page_text_full", ""),
                      "a_note": note(first), "b_note": note(second)})
    howto = PAIRWISE.split("Which set is better?")[1].split("{rubric}")[0].strip() + " " + rubric_of("v4").guidance().strip()
    data = {"format": SPOTCHECK_FORMAT, "batch": folder.name, "items": items, "howto": " ".join(howto.split()),
            "problems": [{"name": k, "label": k, "help": v} for k, v in PAIR_PROBLEMS.items()],
            "claim_problems": [{"name": k, "label": "duplicate" if k == "duplicates" else k, "help": v}
                               for k, v in CLAIM_PROBLEMS.items()],
            "better": BETTER, "confidence": SURE}
    (folder / "spotcheck-order.json").write_text(json.dumps(order, indent=2) + "\n")
    from semantic_pdf_diff.html_pages import fill
    page = fill((Path(__file__).parent.parent / "spotcheck_page.html").read_text(encoding="utf-8"), folder.name, data)
    (folder / "spotcheck.html").write_text(page, encoding="utf-8")
    return folder / "spotcheck.html"

def import_spotcheck(folder, answers_file):
    """A person's spot-check answers as verdicts (verdicts-human/<name>.json), in the judges'
    format: each unit judged in the one order shown; "can't tell" gives no score."""
    from ..review import reviewer_file
    folder = Path(folder)
    data = json.loads(Path(answers_file).read_text(encoding="utf-8"))
    if data.get("format") != SPOTCHECK_FORMAT or data.get("batch") != folder.name:
        raise ValueError(f"{answers_file} isn't a spot-check answers file for {folder.name}")
    order = json.loads((folder / "spotcheck-order.json").read_text())
    items = {i["id"]: i for i in json.loads((folder / "pairs.json").read_text(encoding="utf-8"))["items"]}
    verdicts = {}
    for a in data["answers"]:
        first = order.get(a["item"])
        if first is None:
            continue
        side = {"A": first, "B": "variant" if first == "baseline" else "baseline"}
        marks = {"baseline": [], "variant": []}  # each marked claim, with the claim itself (A1 is baseline[0] or variant[0])
        for letter, claims in (a.get("claims") or {}).items():
            shown = items[a["item"]][side[letter]]
            for k, c in sorted(claims.items(), key=lambda kv: int(kv[0])):
                if int(k) < len(shown) and (c.get("mark") in CLAIM_MARKS or c.get("problems")):
                    claim = {f: v for f, v in shown[int(k)].items() if not f.startswith("_")}
                    marks[side[letter]].append({"index": int(k), "claim": claim, "mark": c.get("mark", ""),
                                                "problems": sorted(set(c.get("problems") or ()) & set(CLAIM_PROBLEMS))})
        better = a.get("better", "")
        score = 0.5 if better == "same" else 1.0 if side.get(better) == "variant" else 0.0 if better in side else None
        key = "baseline-first" if first == "baseline" else "variant-first"
        verdicts[a["item"]] = {key: {"score": score, "better": better, "confidence": a.get("confidence", ""),
                                     "baseline_problems": a.get(f"{'a' if first == 'baseline' else 'b'}_problems", []),
                                     "variant_problems": a.get(f"{'a' if first == 'variant' else 'b'}_problems", []),
                                     "note": a.get("note", ""), "remarks": a.get("note", ""), "claims": marks}}
    return judgements.save(folder / judgements.HUMAN / f"{reviewer_file(data['reviewer'])}.json", data["reviewer"],
                           verdicts)

def _judge_claim_marks(folder, verdicts_dir="verdicts"):
    """{(unit, side, index): mark} from judges who marked claims (rubric v5 on); a claim marked
    differently by judges or orders is taken as unsure."""
    marks = defaultdict(set)
    for r in judgements.answered(judgements.read(folder, verdicts_dir), "claim"):
        marks[(r.unit, r.side, r.index)].add(r.answer["mark"])
    return {k: next(iter(m)) if len(m) == 1 else "unsure" for k, m in marks.items()}

def claim_shares(folder, verdicts_dir="verdicts"):
    """Judges' marks per side (rubric v5): counts, and the share of marked claims that are wrong."""
    counts = {"baseline": Counter(), "variant": Counter()}
    for r in judgements.answered(judgements.read(folder, verdicts_dir), "claim"):
        counts[r.side][r.answer["mark"]] += 1
    return {side: {**dict(c), "wrong_share": round(c["wrong"] / sum(c.values()), 3) if sum(c.values()) else None}
            for side, c in counts.items()}

def anchor(folder, human_dir="verdicts-human", verdicts_dir="verdicts"):
    """People's verdicts against the judges' (in verdicts_dir) on the same units: agreement on
    which side is better, and each side's win rate over the units both judged."""
    folder = Path(folder)
    judges = unit_scores(folder, verdicts_dir=verdicts_dir)
    lean = lambda s: (s > 0.5) - (s < 0.5)
    out = {}
    records = judgements.read(folder, human_dir)
    for name, verdicts in judgements.by_rater(records).items():
        claims = [r for r in judgements.answered(records, "claim") if r.rater == name]  # a person sees one order
        person = {u: next(iter(o.values()))["score"] for u, o in verdicts.items()
                  if next(iter(o.values()))["score"] is not None}
        both = sorted(set(person) & set(judges))
        agree = sum(lean(person[u]) == lean(judges[u]) for u in both)
        opposite = sum(lean(person[u]) * lean(judges[u]) < 0 for u in both)
        fmt = lambda t: None if t is None else {"mean": round(t[0], 3), "low": round(t[1], 3), "high": round(t[2], 3)}
        # Claims marked one by one: the share marked wrong on each side, a measure of each set on its
        # own (a preference between two sets isn't); one rater's view, weighed like any other.
        marked = {"baseline": Counter(), "variant": Counter()}
        for r in claims:
            if r.answer["mark"]:
                marked[r.side][r.answer["mark"]] += 1
        wrong = {side: {**dict(c), "wrong_share": round(c["wrong"] / sum(c.values()), 3) if sum(c.values()) else None}
                 for side, c in marked.items()}
        # Where a judge marked claims too (rubric v5): agreement claim by claim, "unsure" left out.
        judged = _judge_claim_marks(folder, verdicts_dir)
        pairs = [(r.answer["mark"], judged[(r.unit, r.side, r.index)]) for r in claims
                 if (r.unit, r.side, r.index) in judged and r.answer["mark"]
                 and "unsure" not in (r.answer["mark"], judged[(r.unit, r.side, r.index)])]
        claim_agreement = {"claims": len(pairs), "same": sum(a == b for a, b in pairs)} if pairs else None
        out[name] = {"units": len(both), "same_lean": agree, "opposite": opposite, "claims_marked": wrong,
                                 "claim_agreement_with_judges": claim_agreement,
                                 "person_win_rate": fmt(interval([person[u] for u in both], clusters=list(map(region, both)))),
                                 "judges_win_rate": fmt(interval([judges[u] for u in both], clusters=list(map(region, both)))),
                                 "disagreements": [u for u in both if lean(person[u]) * lean(judges[u]) < 0]}
    return out
