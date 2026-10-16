"""Context measures without the model (docs/plans/claim-context-2026-10-14.md, milestone 2; Measurement, layer 1):
for each claim of a folder of runs, what its context holds, what's in the wrong field, and whether its context's
words were in what its request showed the model.

- **Inventory:** claims with conditions stated, with a list position (provenance), context records kept (by kind)
  and the claims referencing them, names as printed, and the requests' context in bytes: the heading and the
  levers' context lines (`Section:`, neighbouring text, a table's lead-in, stems) against the source data itself.
- **Misplaced:** context in the wrong field, found by pattern: a list position or a reader's numbering ("Condition
  2", "dimension 1", "column 3") in conditions, attribute or entity; frame words ("face of finish", "net") in
  conditions.
- **Grounding:** a claim's conditions' words, looked for in what its request showed (the heading, context lines and
  source data; never the instructions). All found: grounded; some: partly; none: unsupported. A picture's request
  shows its text layer, not what the picture holds, so its unsupported conditions may still be read from the image:
  they're counted apart.

Claims are each reading as its task gave it (every_reading), so a condition one reader gave and another didn't is
measured where it was given. Until 2026-10-15 they were rounds.collect's units, which show a merged claim once per
unit, as its first sighting worded it: a frame only a later sighting gave (the coaster's tiles, after its figure
task) went uncounted.
"""
import re
from collections import Counter, defaultdict
from pathlib import Path

from semantic_pdf_diff.context import CONTEXT_NOTE
from semantic_pdf_diff.tasks import ExtractQuery


# A reader's numbering or a list's label, standing as a name: "Condition 2", "dimension 1", "column 3", "item (b)".
# A hyphen before the word makes a name of it ("BM-Case2", "Load-Case 3"), not a label.
NUMBERED = re.compile(r"(?<![-\w])(?:condition|step|item|note|point|requirement|criterion|rule|stage|dimension|column|"
                      r"row|value|entry|line|field|case)\s*(?:no\.?\s*|#\s*)?\(?(?:\d{1,3}|[a-h]|[ivx]{1,4})\)?(?![\w.])",
                      re.I)
# Words that say how a value is read, not when it holds (Concepts: frame), as readers put them in conditions.
FRAME = re.compile(r"\b(?:face of (?:finish|stud|wall|masonry|concrete)|finish(?:ed)? face|cent(?:er|re) ?lines?|"
                   r"c/l|net|gross|nominal|clear (?:width|height|opening)|above finished floor|a\.?f\.?f\.?|datum|"
                   r"unless (?:otherwise )?noted|typical|typ\.?|not to scale|n\.?t\.?s\.?|scale)\b", re.I)
IMAGE_REGIONS = {"overview", "tile", "figure", "picture", "image"}
STOP = {"the", "a", "an", "of", "for", "per", "each", "at", "in", "on", "to", "and", "or", "with", "is", "are", "by",
        "its", "be", "as", "when", "if", "from", "under", "during", "all", "any", "than", "not", "no", "this", "that"}

def words(text):
    """Content words, folded: case, hyphens and a plural's s; stop words dropped. Numbers kept as written."""
    out = set()
    for w in re.findall(r"[a-z0-9]+(?:[.,][0-9]+)*", str(text).casefold().replace("-", " ")):
        if w in STOP or w == "s":  # "s": a possessive's ("element's")
            continue
        out.add(w[:-1] if len(w) > 3 and w.endswith("s") and not w.endswith("ss") else w)
    return out

# Where a table's request stops showing the table: our opinion, or the model's earlier answer and its problems
TABLE_ENDS = ("\nOUR HEURISTIC OPINION", "\nYOUR EARLIER ANSWER:", "\nYOUR RULES:", "\nWHAT THEY GAVE:")
ROLES = ("extract", "table-rules", "table-review")  # the requests claims come from

def shown(prompt):
    """What a request showed of its source, not its instructions nor answers given before: an extraction's heading,
    context lines and data; a table's description, context, columns and rows (tablerules)."""
    if "\nSOURCE DATA:\n" in prompt:
        q = ExtractQuery.read(prompt)
        return "\n".join((q.heading, q.context.replace(CONTEXT_NOTE, ""), q.data))
    start = prompt.find("TABLE: ")
    if start < 0:
        return ""
    ends = [i for i in (prompt.find(m, start) for m in TABLE_ENDS) if i >= 0]
    return prompt[start:min(ends) if ends else len(prompt)].replace(CONTEXT_NOTE, "")

def grounding(conditions, texts):
    """grounded, partly or unsupported: how many of conditions' words are in texts (what requests showed); None
    when there are none."""
    want = words(conditions)
    if not want:
        return None
    have = set().union(*(words(t) for t in texts)) if texts else set()
    found = want & have
    return "grounded" if found == want else "partly" if found else "unsupported"

def misplaced(claim):
    """Where this claim holds context in the wrong field: [tag]."""
    tags = []
    for field in ("conditions", "attribute", "entity"):
        if NUMBERED.search(str(claim.get(field, ""))):
            tags.append(f"numbered in {field}")
    if FRAME.search(str(claim.get("conditions", ""))):
        tags.append("frame in conditions")
    return tags

def requests(store, content):
    """{task: [what each of its requests showed]} for one document's requests that claims come from."""
    out = defaultdict(list)
    # a table's requests are logged without their content (tablerules): in a store of two documents, a table task's
    # name may be either's
    for q in store.queries(content=content) + store.queries(content=""):
        if q["role"] in ROLES:
            out[q["task"]].append(shown(q["prompt"]))
    return out

def every_reading(runs_dir):
    """{run: [(content, family, claim)]} for every store under runs_dir: each task's reading of a claim in its own
    words (once per task, quote and wording), from the readers whose regions have a family (as units' are); a claim
    holds its entity, attribute, value, unit, conditions, frame and stance (if any), quote, `_task`, and `_records`
    (the context records it references)."""
    from semantic_pdf_diff.readings import wording
    from semantic_pdf_diff.regions import FAMILY
    from semantic_pdf_diff.store import Store
    from ..eval.documents import contents
    out = defaultdict(list)
    for folder in sorted(p for p in Path(runs_dir).iterdir() if (p / "store.sqlite").exists()):
        with Store.open(folder) as store:
            for content in contents(store):
                seen = set()
                for r in store.evidence(content, reconcile=False):
                    for o in r.occurrences or [r]:
                        family = FAMILY.get(o.locator.region)
                        reading = (o.locator.task, o.quote, wording(r))
                        if not family or reading in seen:
                            continue
                        seen.add(reading)
                        claim = {k: getattr(r, k) for k in ("entity", "attribute", "value", "unit", "conditions")}
                        if r.frame:
                            claim["frame"] = r.frame
                        if r.stance:  # who holds it (milestone 5): its links, holder and attitude
                            claim["stance"] = [link.model_dump() for link in r.stance]
                        if r.uncertainty:  # where a hedge may land (milestone 5)
                            claim["uncertainty"] = r.uncertainty
                        claim.update(quote=o.quote, _task=o.locator.task, _records=list(r.records))
                        out[folder.name].append((content, family, claim))
    return dict(out)

def measure(runs_dir):
    """{run: its document's measures} for every store under runs_dir."""
    from semantic_pdf_diff.store import Store
    out = {}
    for run, claims in sorted(every_reading(runs_dir).items()):
        with Store.open(Path(runs_dir) / run) as store:
            shown_by = {content: requests(store, content) for content in {c for c, _, _ in claims}}
            evidence = [e for content in shown_by for e in store.evidence(content)]
            positioned = sum(1 for e in evidence if e.position)
            kept = Counter(r.kind for content in shown_by for r in store.records(content).values())
            referenced = sum(1 for e in evidence if e.records)
            printed = sum(1 for e in evidence if e.printed)
            sizes = Counter()
            for content in shown_by:
                for q in store.queries(content=content, role="extract"):
                    parts = ExtractQuery.read(q["prompt"])
                    sizes["context"] += len((parts.heading + parts.context).encode())
                    sizes["data"] += len(parts.data.encode())
                    sizes["requests"] += 1
        tally, tags, examples = Counter(), Counter(), defaultdict(list)
        for content, family, claim in claims:
            tally["claims"] += 1
            for tag in misplaced(claim):
                tags[tag] += 1
                if len(examples[tag]) < 3:
                    examples[tag].append(" | ".join(str(claim.get(k, "")) for k in ("entity", "attribute",
                                                                                     "conditions")))
            if not str(claim.get("conditions", "")).strip():
                continue
            tally["with conditions"] += 1
            texts = shown_by[content].get(claim.get("_task"), [])
            image = claim.get("_task", "").split(":")[0] in IMAGE_REGIONS
            status = grounding(claim["conditions"], texts)
            if status is None:
                status = "no content words"
            tally[f"{status}{' (image)' if image and status not in ('grounded', 'no content words') else ''}"] += 1
            if status == "unsupported" and not image and len(examples["unsupported"]) < 3:
                examples["unsupported"].append(f"{claim.get('entity')} | {claim.get('attribute')} | "
                                               f"{claim['conditions']}")
        out[run] = {**dict(sorted(tally.items())), "positioned": positioned, "misplaced": dict(sorted(tags.items())),
                    **({"records": dict(sorted(kept.items())), "with records": referenced} if kept else {}),
                    **({"printed": printed} if printed else {}), "evidence": len(evidence),
                    "context_bytes_per_request": round(sizes["context"] / sizes["requests"]) if sizes["requests"]
                    else 0,
                    "data_bytes_per_request": round(sizes["data"] / sizes["requests"]) if sizes["requests"] else 0,
                    "examples": {k: v for k, v in sorted(examples.items())}}
    return out

def totals(measures):
    """The runs' measures summed (examples left out; bytes averaged over runs)."""
    out = Counter()
    for m in measures.values():
        for k, v in m.items():
            if isinstance(v, int) and not k.endswith("_per_request"):
                out[k] += v
            elif k == "misplaced":
                for tag, n in v.items():
                    out[tag] += n
            elif k == "records":
                for kind, n in v.items():
                    out[f"{kind} records"] += n
    return dict(sorted(out.items()))

# --- against keys (Measurement, layers 2 and 3) ---------------------------------------------------------------------

KINDS = ("scope", "frame", "subject", "bound", "provenance", "sibling", "holder")
OUTSIDE = ("provenance", "sibling")  # kinds that belong in none of a claim's words
# A claim's stance (who holds it), its words, then the context records it references (the records lever: a sheet's
# notes, a list's lead-in, a table's title, headers and lead-in), whose text a claim holds by reference rather than in
# its words
FIELDS = ("stance", "frame", "conditions", "entity", "attribute", "records")
# Where a kind belongs in a claim: scope in conditions, frame in its own field (the split_conditions lever's) or in
# conditions (readers without it), a subject in the entity, a bound in the attribute or conditions; provenance in none
# of them; a holder (a reported view's: milestone 5) in the claim's stance, or wherever its words name it. Scope,
# frame and subject may also be held by a record reaching the claim (the plan's Concepts: stored once and
# referenced)
HOME = {"scope": {"conditions", "records"}, "frame": {"frame", "conditions", "records"},
        "subject": {"entity", "conditions", "records"}, "bound": {"attribute", "conditions"}, "provenance": set(),
        "sibling": set(), "holder": {"stance", "entity", "conditions", "attribute", "records"}}
CONVENTION_WORDS = {"width", "depth", "length", "east", "west", "north", "south"}
GEOMETRY_WORDS = {"horizontal", "vertical", "drawn", "x", "y"}

def _text(value):
    """A claim's field as words: a stance stored as links (a run's evidence) gives its holders."""
    if isinstance(value, list):
        return "; ".join(str(x.get("holder", "")) if isinstance(x, dict) else str(x) for x in value)
    return value or ""

ATTITUDES = ("propos", "support", "oppos", "report", "agree", "object")

def _attitude(text):
    """An attitude's root ("proposes", "proposed": "propos"), or the text folded when it names none."""
    text = str(text or "").casefold()
    return next((root for root in ATTITUDES if root in text), text.strip())

def _attitudes(stance):
    """The attitudes a claim's stance holds: its links' (a run's evidence stores them as dicts)."""
    if not isinstance(stance, list):
        return set()
    return {_attitude(x.get("attitude", "")) for x in stance if isinstance(x, dict)}

# A keyed hedge's words, as a claim may say them ("expected" as "expect", "tentative" as "tentatively")
HEDGE_WORDS = {"expected": ("expect",), "likely": ("likely", "probabl"), "tentative": ("tentativ",),
               "preliminary": ("preliminar",), "working assumption": ("working assumption", "assum")}
# Where a hedge may land, in order: its link's strength (the stance), then the claim's words
HEDGE_FIELDS = ("stance", "uncertainty", "conditions", "attribute", "value", "entity")

def _hedged(claim, hedge):
    """The field a claim says a keyed hedge in first (HEDGE_FIELDS), or None."""
    roots = HEDGE_WORDS.get(hedge, (hedge,))
    for field in HEDGE_FIELDS:
        value = claim.get(field) or ""
        text = " ".join(str(x.get("strength", "")) for x in value if isinstance(x, dict)) \
            if isinstance(value, list) else str(value)
        if any(root in text.casefold() for root in roots):
            return field
    return None

def _wanted(fact, text):
    """The words of a context item that a claim would have to say: its own, less the fact's names'."""
    names = words(" ".join((fact.entity, fact.attribute, *fact.synonyms, *fact.aliases)))
    return words(text) - names or words(text)

def against_key(key_data, claims, shown_by_task):
    """One document's context per kind against its key: {kind: {where it landed: facts}}, the audit of each lost
    item {kind: {not shown|shown, not used|misapplied|image only: facts}}, names resting on unprinted conventions, and
    a reported view's attitude (milestone 5) in a reading's stance, another attitude there, or none; and where a
    keyed hedge landed (HEDGE_FIELDS' first, or nowhere).
    claims: dicts with entity, attribute, value, unit, conditions and _task, and records (the text of the records the
    claim references, if any); shown_by_task: {task: [texts shown]}."""
    from .controlled.score import bounds, classify, key_facts
    facts = key_facts(key_data)
    numeric = [f for f in facts if not f.relation]
    by_id = {f.id: f for f in facts}
    readings = defaultdict(list)  # fact id -> the claims reading it right or loosely
    for c in claims:
        if c.get("relation"):
            continue
        outcome, fid = classify(c, numeric, key_data["printed"])
        if fid and outcome in ("right", "loose"):
            readings[fid].append(c)
    placed, audit, named, attitudes = defaultdict(Counter), defaultdict(Counter), Counter(), Counter()
    hedges = Counter()
    examples = defaultdict(list)
    for fid, mine in sorted(readings.items()):
        fact = by_id[fid]
        ctx = fact.context or {}
        for kind in KINDS:
            if not ctx.get(kind):
                continue
            # a bound is said in many ways ("shall not exceed", "at least"): the scorer's reading of bounds decides
            said_in = (lambda text, limit=bounds(ctx[kind]): bounds(text) & limit) if kind == "bound" else \
                (lambda text, want=_wanted(fact, ctx[kind]): want & words(text))
            landed = {field for c in mine for field in FIELDS if said_in(_text(c.get(field, "")))}
            where = next((f for f in FIELDS if f in landed), "nowhere")
            placed[kind][where] += 1
            if kind in OUTSIDE:
                audit[kind]["kept out" if not landed else "in " + where] += 1
                continue
            if landed & HOME[kind]:
                continue
            want = _wanted(fact, ctx[kind])
            # lost or misplaced: was it in what the requests showed? A neighbour's scope said instead: misapplied
            others = set().union(*(_wanted(f, f.context.get(kind, "")) for f in facts
                                   if f.entity == fact.entity and f.id != fid and (f.context or {}).get(kind)))
            said = set().union(*(words(c.get("conditions", "") + " " + c.get("frame", "")) for c in mine))
            texts = [t for c in mine for t in shown_by_task.get(c.get("_task"), [])]
            image = all(c.get("_task", "").split(":")[0] in IMAGE_REGIONS for c in mine)
            if said & (others - want):
                verdict = "misapplied"
            elif any(said_in(t) for t in texts) if kind == "bound" else \
                    want <= set().union(*(words(t) for t in texts)) if texts else False:
                verdict = "shown, not used"
            else:
                verdict = "image only" if image else "not shown"
            audit[kind][verdict] += 1
            if len(examples[f"{kind}: {verdict}"]) < 3:
                examples[f"{kind}: {verdict}"].append(f"{fid}: wanted {ctx[kind]!r}; read "
                                                      + " / ".join(f"{c.get('attribute')} | {c.get('conditions')}"
                                                                   for c in mine[:2]))
        if ctx.get("attitude"):
            held = set().union(*(_attitudes(c.get("stance")) for c in mine)) - {""}
            attitudes["in its stance" if _attitude(ctx["attitude"]) in held else "another" if held else "none"] += 1
        if ctx.get("hedge"):  # where a reading says it, the first field by HEDGE_FIELDS' order
            landed = {_hedged(c, ctx["hedge"]) for c in mine} - {None}
            hedges[next((f for f in HEDGE_FIELDS if f in landed), "nowhere")] += 1
        if ctx.get("named_by"):
            said = set().union(*(words(f"{c.get('attribute', '')} {c.get('conditions', '')}") for c in mine))
            named["by an unprinted convention" if said & CONVENTION_WORDS else
                  "by geometry as drawn" if said & GEOMETRY_WORDS else "otherwise"] += 1
    return {"placed": {k: dict(v) for k, v in placed.items()}, "audit": {k: dict(v) for k, v in audit.items()},
            "named": dict(named), **({"attitudes": dict(attitudes)} if attitudes else {}),
            **({"hedges": dict(hedges)} if hedges else {}),
            "examples": dict(examples)}

def measure_keys(runs_dir, key_of):
    """{run: against_key's result} for every store under runs_dir; key_of(run) is its key's data."""
    from semantic_pdf_diff.store import Store
    out = {}
    for run, claims in sorted(every_reading(runs_dir).items()):
        with Store.open(Path(runs_dir) / run) as store:
            shown_by, held = {}, {}
            for content in {c for c, _, _ in claims}:
                for task, texts in requests(store, content).items():
                    shown_by.setdefault(task, []).extend(texts)
                held[content] = store.records(content)
        out[run] = against_key(key_of(run), [{**c, "records": _held_text(held[content], c["_records"])}
                                             for content, _, c in claims], shown_by)
    return out

def _held_text(records, ids):
    """The text of the records named by ids: each record's label, text and items."""
    return " ".join(" ".join([r.label, r.text, *r.items]) for r in map(records.get, ids) if r)

def record_texts(store, content):
    """{claim id: the text of the context records it references} for one document: each record's label, text and
    items."""
    records = store.records(content)
    def text(r):
        return " ".join([r.label, r.text, *r.items])
    return {e.id: " ".join(text(records[r]) for r in e.records if r in records)
            for e in store.evidence(content) if e.records}

def sum_keys(results):
    """against_key's results summed over runs (examples left out)."""
    out = {"placed": defaultdict(Counter), "audit": defaultdict(Counter), "named": Counter(), "attitudes": Counter(),
           "hedges": Counter()}
    for r in results.values():
        out["attitudes"].update(r.get("attitudes", {}))
        out["hedges"].update(r.get("hedges", {}))
        for part in ("placed", "audit"):
            for kind, where in r[part].items():
                out[part][kind].update(where)
        out["named"].update(r["named"])
    return {"placed": {k: dict(sorted(v.items())) for k, v in sorted(out["placed"].items())},
            "audit": {k: dict(sorted(v.items())) for k, v in sorted(out["audit"].items())},
            "named": dict(sorted(out["named"].items())),
            **({"attitudes": dict(sorted(out["attitudes"].items()))} if out["attitudes"] else {}),
            **({"hedges": dict(sorted(out["hedges"].items()))} if out["hedges"] else {})}

# --- our own link: calibration (Measurement, layer 7) --------------------------------------------------------------

BANDS = (0.5, 0.7, 0.8, 0.9, 0.95, 1.0)  # a band's upper edge (the last includes 1.0)

def reliability(runs_dir, key_of):
    """The reader's confidence against the keys: {reader: {band: {"readings", "right", "share"}}} (all readers, then
    text, table rules and image tasks apart), each reading (a claim's
    sighting by one task, with that task's confidence) counted by its claim's outcome (scored: numbers only; "text"
    and distractors left out). Right counts; loose, misbound, misread and the rest don't."""
    from semantic_pdf_diff.store import Store
    from .controlled.score import classify, key_facts
    tally = defaultdict(Counter)
    for folder in sorted(p for p in Path(runs_dir).iterdir() if (p / "store.sqlite").exists()):
        key_data = key_of(folder.name)
        numeric = [f for f in key_facts(key_data) if not f.relation]
        with Store.open(folder) as store:
            for f in store.files():
                for e in store.evidence(f.content):
                    outcome, _ = classify(e.model_dump(), numeric, key_data["printed"])
                    if outcome in ("text", "distractor"):
                        continue
                    for o in e.occurrences or [e]:
                        band = next(b for b in BANDS if o.confidence < b or b == 1.0)
                        reader = "table rules" if o.locator.task.startswith("rules:") else \
                            "image" if o.locator.region in IMAGE_REGIONS else "text"
                        for which in ("all", reader):
                            tally[(which, band)]["readings"] += 1
                            tally[(which, band)]["right"] += outcome == "right"
    out = defaultdict(dict)
    for (which, b), t in sorted(tally.items()):
        out[which][f"<{b}" if b < 1.0 else "<=1.0"] = {**t, "share": round(t["right"] / t["readings"], 3)}
    return dict(out)
