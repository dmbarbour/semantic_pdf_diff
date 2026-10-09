"""Judging a batch: the pairwise prompts under a rubric, a judge's answers read back as verdicts, and the loop over
a batch's units. Split from rounds.py (milestone 8).
"""
import json
from pathlib import Path

from .. import judgements
from ..rubrics import CLAIM_MARKS, CLAIM_PROBLEMS, PAIR_PROBLEMS, rubric as rubric_of
from .units import _ident, load_batch

def _set_note(shown, total, hidden):
    return (f"all {total} claims" if shown >= total else
            f"{shown} of its {total} claims; {hidden} shared claims not shown are identical in both sets")

def _claims_text(claims, letter=None):
    """One line per claim; numbered (A1, A2, ...) when judges mark them one by one."""
    mark = (lambda k: f"{letter}{k + 1}. ") if letter else (lambda k: "- ")
    return "\n".join(f"{mark(k)}{c['entity']} | {c['attribute']} | {c['value']}{' ' + c['unit'] if c.get('unit') else ''}"
                     f"{' | conditions: ' + c['conditions'] if c.get('conditions') else ''} | quote: {c['quote']}"
                     for k, c in enumerate(claims)) or "(no claims)"

def _grouped(a, b):
    """Two claim lists as ([(index in a, index in b)] shared, [index in a] only in a, [index in b] only in b)."""
    where = {}
    for k, c in enumerate(b):
        where.setdefault(_ident(c), k)
    shared, only_a = [], []
    for k, c in enumerate(a):
        (shared.append((k, where[_ident(c)])) if _ident(c) in where else only_a.append(k))
    paired = {j for _, j in shared}
    return shared, only_a, [k for k in range(len(b)) if k not in paired]

def _whole_view(item, a, b):
    """Rubric v6's page text and grouped claims, and each group's claims in order (to map marks back)."""
    shared, only_a, only_b = _grouped(a, b)
    groups = {"S": [a[i] for i, _ in shared], "A": [a[i] for i in only_a], "B": [b[i] for i in only_b]}
    titles = {"S": "CLAIMS IN BOTH SETS", "A": "CLAIMS ONLY IN SET A", "B": "CLAIMS ONLY IN SET B"}
    claims = "\n\n".join(f"{titles[g]} ({len(c)}):\n{_claims_text(c, g)}" for g, c in groups.items())
    whole = item.get("page_text_full") or item["page_text"]
    if not item["image"]:  # a text format: lines, no images
        view = TEXT_FORMAT + f"The whole page's lines:\n{whole}"
        if item.get("band"):
            view += f"\n\nThis part's lines:\n{item['page_text']}"
        return view, claims, (shared, only_a, only_b)
    view = f"The whole page's text layer:\n{whole}"
    if item.get("band"):
        view = ("The first image shows this part of the page; the second, the whole page with this part "
                f"outlined.\n{view}\n\nThis part's text layer:\n{item['page_text']}")
    return view, claims, (shared, only_a, only_b)

def _claim_marks(entries, shown):
    """A judge's marks for the claims of one set shown to it: [{index, claim, mark, problems}]."""
    out = []
    for entry in entries or ():
        try:
            k = int(entry.get("n")) - 1
        except (TypeError, ValueError, AttributeError):
            continue
        if 0 <= k < len(shown) and entry.get("mark") in CLAIM_MARKS:
            out.append({"index": k, "claim": {f: x for f, x in shown[k].items() if not f.startswith("_")},
                        "mark": entry["mark"],
                        "problems": sorted({str(p).lower() for p in entry.get("problems") or ()} & set(CLAIM_PROBLEMS))})
    return out

# Before a text format's lines (a unit with no image), as the rubrics speak of a page image and its text layer.
TEXT_FORMAT = "(A text format, read as text: there is no page image, and these lines are the source.)\n"

def pair_requests(folder, batch, rubric="v1"):
    """Every judge request a batch makes under a rubric, in order: (item, order, prompt, images,
    a, b, groups), a and b being the claim sets as shown (A first) and groups v6's grouping (or None).
    The prompts are the queries judges answer, and what the folder's fixture finds answers by."""
    folder = Path(folder)
    judged_by = rubric_of(rubric)
    template, numbered, whole = judged_by.prompt(), judged_by.numbered(), judged_by.whole()
    for item in batch["items"]:
        if "page_text" not in item:
            raise ValueError(f"{folder} has no page text: restore it and the images from the public slices "
                             "(rounds.rerender(folder, 'samples/slices'))")
        for order in ("baseline-first", "variant-first"):
            a, b = (item["baseline"], item["variant"]) if order == "baseline-first" else (item["variant"], item["baseline"])
            counts = item.get("counts") or {}
            notes = {side: _set_note(len(item[side]), counts.get(side, len(item[side])), item.get("hidden_shared", 0))
                     for side in ("baseline", "variant")}
            first, second = ("baseline", "variant") if order == "baseline-first" else ("variant", "baseline")
            band = item.get("band")
            if whole and "page_image" not in item:
                raise ValueError(f"rubric {rubric} needs the whole page: run rounds.add_context on {folder} first")
            view, grouped, groups = _whole_view(item, a, b) if whole else ("", "", None)
            # a text format's unit has no image: its lines are its page text (review E3)
            images = ([folder / item["image"]] if item["image"] else []) \
                + ([folder / item["page_image"]] if whole and band and item["page_image"] else [])
            page_text = item["page_text"] if item["image"] else TEXT_FORMAT + item["page_text"]
            prompt = template.format(page=item["page"], family=item["family"], page_text=page_text,
                                     page_view=view, claims=grouped,
                                     a=_claims_text(a, "A" if numbered else None),
                                     b=_claims_text(b, "B" if numbered else None),
                                     sections=" | ".join(item.get("sections") or ()) or "none",
                                     part=(f", part {band[0] + 1} of {band[1]}" + ("" if whole else " (the image shows that part)"))
                                     if band else "",
                                     before=item.get("before") or "(start of the document)",
                                     within=item.get("within") or "nothing numbered",
                                     a_note=notes[first], b_note=notes[second])
            yield item, order, prompt, images, a, b, groups

def pair_verdict(rubric, v, order, a, b, groups=None):
    """A judge's answer (a PairVerdict's fields, `v`) as the verdict recorded for one order: its
    score for the variant (1 when the variant is better), and wrong counts, problems and claim marks
    by side. a and b are the claim sets as shown (A first), groups v6's grouping (pair_requests)."""
    tags = lambda values: sorted({str(t).strip().lower() for t in values or ()} & set(PAIR_PROBLEMS))
    better = v.get("better")
    variant_is = "B" if order == "baseline-first" else "A"
    score = 0.5 if better not in ("A", "B") else 1.0 if better == variant_is else 0.0
    verdict = {"score": score, "better": better, "confidence": v.get("confidence", ""),
               "baseline_wrong": v.get("a_wrong") if order == "baseline-first" else v.get("b_wrong"),
               "variant_wrong": v.get("b_wrong") if order == "baseline-first" else v.get("a_wrong"),
               "note": v.get("note", "")}
    judged_by = rubric_of(rubric)
    if judged_by.tagged():
        first, second = tags(v.get("a_problems")), tags(v.get("b_problems"))
        verdict.update(baseline_problems=first if order == "baseline-first" else second,
                       variant_problems=second if order == "baseline-first" else first,
                       remarks=v.get("remarks", "").strip())
    if judged_by.numbered():  # each claim's mark, by side (A is the first set shown)
        first, second = ("baseline", "variant") if order == "baseline-first" else ("variant", "baseline")
        if groups is None:
            marks = {first: _claim_marks(v.get("a_claims"), a), second: _claim_marks(v.get("b_claims"), b)}
        else:  # v6: a shared claim's mark counts for both sides, at each side's own index
            shared, only_a, only_b = groups
            at = lambda entries, index, claims: [
                {**m, "index": index[m["index"]]} for m in _claim_marks(entries, [claims[i] for i in index])]
            marks = {first: at(v.get("s_claims"), [i for i, _ in shared], a) + at(v.get("a_claims"), only_a, a),
                     second: at(v.get("s_claims"), [j for _, j in shared], b) + at(v.get("b_claims"), only_b, b)}
        verdict["claims"] = marks
    return verdict

def judge_pairs(folder, client, reviewer, progress=None, limit=None, rubric="v1", only=None, retry_failed=False,
                verdicts_dir="verdicts"):
    """Ask one model to compare every unit (or only those in `only`), in both orders; merges
    into verdicts/<reviewer>.json. Answers are recorded in the batch's replay fixture (see
    fixtures.folder_fixture), so a rerun (e.g. after a budget pause) pays only for what's missing.

    A verdict that fails (a judge timing out on a long unit) isn't asked again on later calls,
    which used to hold every later chunk for another timeout; retry_failed asks such verdicts
    once more (run_round does, when a variant's judging ends): judgements.ask_again. They're
    counted in failures/<reviewer>.json (failures-<x>/ for verdicts-<x>/)."""
    from ..models import PairVerdict
    from ..review import reviewer_file
    folder = Path(folder)
    batch = load_batch(folder)
    target = folder / verdicts_dir / f"{reviewer_file(reviewer)}.json"
    verdicts = judgements.load(target, rubric)
    failed_path = folder / judgements.failures_folder(verdicts_dir) / f"{reviewer_file(reviewer)}.json"
    failed = json.loads(failed_path.read_text(encoding="utf-8")) if failed_path.exists() else {}
    included = {i["id"] for i in batch["items"][:limit]}
    shown = {}  # (unit, order): the claim sets as shown, for reading the answer back

    def wanted():
        for item, order, prompt, images, a, b, groups in pair_requests(folder, batch, rubric):
            if item["id"] not in included or only is not None and item["id"] not in only:
                continue
            attempts = failed.get(f"{item['id']}|{order}", 0)
            if order in verdicts.get(item["id"], {}) or not judgements.ask_again(attempts, retry_failed):
                continue  # judged already, or failed and not (or no longer) retried
            shown[item["id"], order] = (a, b, groups)
            yield (item["id"], order), prompt, PairVerdict, images, ("judge", item["id"], rubric, order)

    answers, errors = judgements.rate(client, wanted(), progress)
    failures = [f"{unit} {order}: {error}" for (unit, order), error in errors.items()]
    for unit, order in errors:
        failed[f"{unit}|{order}"] = failed.get(f"{unit}|{order}", 0) + 1
    for (unit, order), value in answers.items():
        failed.pop(f"{unit}|{order}", None)
        verdicts.setdefault(unit, {})[order] = pair_verdict(rubric, value.model_dump(), order, *shown[unit, order])
    if verdicts:
        judgements.save(target, reviewer, verdicts, rubric)
    if failed or failed_path.exists():
        failed_path.parent.mkdir(exist_ok=True)
        failed_path.write_text(json.dumps(failed, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return target, len(verdicts), failures
