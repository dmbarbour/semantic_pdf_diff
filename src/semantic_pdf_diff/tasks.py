"""What every reader does with an extraction task (docs/plans/multi-format-adapters-2026-09-23.md, milestone 1): queue
the request, check the answer's quotes, make evidence and coverage rows, follow exactly repeated blocks, refine a
partial answer, and the text and table tasks themselves, which take text segments and a reader for their context
whatever the format. A reader (extract's PDF job, textjob's text job) supplies its parts: where a task sits (a page
and a box: PDF points, or lines of a text file), its sections, its context reader, and the locator a claim gets.
Split from extract.py; PDF requests are byte for byte what they were (tests/test_golden_requests.py).
"""
import hashlib
import re
import json
from dataclasses import dataclass
from pathlib import Path

from .llm import CallLimitReached, NotRecorded
from .schema import DerivationStep, Evidence, Extraction, claim_id, coverage_row, merge_occurrences
from .progress import log
from .quotes import covered, quoted
from .regions import region_of

# Text shorter than this is not split further during refinement.
# Bump when prompt assembly or task construction changes, not only the template text;
# it is part of the extraction interpreter. 2: section heading path in prompts.
# 3: exactly repeated table rows follow their first occurrence. 4: claims per request configurable.
# 5: headings by position on the page; table rows located by their own box.
# 6: rules for unfamiliar charts, attributes free of conditions, parts of a whole; figure tasks.
PROMPT_VERSION = 6

EXTRACT = '''Extract atomic engineering claims from this one source. Return JSON:
{"claims":[{"entity":"component/system", "attribute":"property or directed relationship",
"value":"literal value or target", "unit":"literal unit or empty", "conditions":"load, scenario, time, tolerances, scope",
"kind":"text|table|chart|diagram", "quote":"short exact supporting text or visible labels",
"confidence":0.0, "approximate":false}], "complete":true, "issues":[]}
Maximum {max_claims} claims. Set complete=false if content is clipped, ambiguous, unreadable, or more claims remain.
For tables associate row labels, column headers and units. For charts preserve series, axes, units,
operating point and trend; estimated plotted readings MUST be approximate. For diagrams extract
labeled components and directed connections; never invent direction on unmarked edges.
Preserve negation, requirements versus proposed capabilities, ranges and inequality signs.
Extract evidence only, not commentary. Use a short canonical entity and attribute; keep numeric value separate from unit.
The attribute names the property only: put conditions (e.g. "at theta = 0", "at rated speed") in conditions.
If a value is one of several parts (one layer, one material, one member), say what it is part of in the attribute
(e.g. "spar cap material"), not "composition".
If you are not sure how to read a chart, diagram or drawing convention, say so in issues, lower confidence, and mark
readings approximate; do not guess what an unexplained symbol, colour or line style means.
'''

@dataclass(frozen=True)
class ExtractQuery:
    """An extraction request's text in parts: the one owner of its layout (code review 2026-10-01, A1: prompts were
    assembled inline and parsed back at markers in three places). prompt() is the bytes sent; read() takes a logged
    prompt back into its parts, so no reader splits at markers of its own."""
    instructions: str  # the template with its claim cap filled, then the rules (the configuration's, the region's)
    region: str
    heading: str = ""  # the headings the region falls under
    context: str = ""  # CONTEXT_NOTE and the levers' lines
    data: str = ""     # the source data: text, a table row, or an image task's note and text layer
    continuation: str = ""  # CONTINUATION_NOTE and the claims earlier requests for this task returned

    def prompt(self):
        return (self.instructions + "\nSource type: " + self.region + (f"\nSection: {self.heading}" if self.heading else "")
                + (f"\n{self.context}" if self.context else "")
                + (f"\n{self.continuation}" if self.continuation else "") + "\nSOURCE DATA:\n" + self.data)

    @property
    def request(self):
        """The part after the instructions: what this task, not every task, was given."""
        return self.prompt()[len(self.instructions) + 1:]

    @classmethod
    def read(cls, prompt):
        instructions, _, rest = prompt.partition("\nSource type: ")
        head, _, data = rest.partition("\nSOURCE DATA:\n")
        region, _, tail = head.partition("\n")
        heading = ""
        if tail.startswith("Section: "):
            heading, _, tail = tail[len("Section: "):].partition("\n")
        context, mark, continued = tail.partition(CONTINUATION_NOTE)
        return cls(instructions, region, heading, context.rstrip("\n") if mark else tail, data,
                   mark + continued if mark else "")

# What a continued request is told (tasks.TaskCore.consume): the claims returned so far, not to be repeated.
CONTINUATION_NOTE = ("ALREADY EXTRACTED from this same source by an earlier request (do not repeat these; extract the "
                     "claims that remain):")

def continuation(claims):
    """A continued request's note: the claims earlier requests returned, one a line, by entity, attribute and value
    only: enough not to repeat them, and conditions listed were copied onto the claims that followed (a valve's
    stroke time given the "rated point" of the flow coefficients listed before it)."""
    rows = [" | ".join(x for x in (c.entity, c.attribute, f"{c.value} {c.unit}".strip()) if x) for c in claims]
    return CONTINUATION_NOTE + "".join("\n- " + r for r in rows)

def extraction_template(s):
    """The extraction instructions in force: the baseline, or a variant's (with {max_claims} unfilled)."""
    return s.instructions(EXTRACT)

MIN_REFINE_BYTES = 400

def split_utf8(text, limit):
    """Bound all chunks without dropping characters, including non-ASCII PDF text."""
    chunk, size = [], 0
    for char in text:
        n = len(char.encode())
        if size + n > limit and chunk:
            yield "".join(chunk)
            chunk, size = [], 0
        chunk.append(char)
        size += n
    if chunk:
        yield "".join(chunk)

def union(boxes):
    boxes = list(boxes)
    return (min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes))

# An incomplete answer's issue saying the claim limit stopped it ("more steps (17-22) than the 20 claim limit
# allowed"), as a request to continue; not clipping or illegibility, which another request wouldn't mend
LIMIT_SAID = re.compile(r"claim limit|limit of \d+ claims|maximum (?:of )?\d+ claims|\d+[- ]claim (?:limit|maximum|cap)"
                        r"|more (?:claims|facts|steps|items|rows|entries) (?:than|remain)|(?:claims|facts) remain", re.I)

class TaskCore:
    """One content item's extraction tasks: the evidence and coverage they make, as tasks finish.

    locator(page, bbox, region, task) -> the Locator a claim gets; derivation: {region: the steps from the bytes
    to a claim}; sections (a SectionIndex) and reader (the context levers' reader) are set once the document is
    open. oversized: the coverage note for a table row too large to send."""

    def __init__(self, job, output, client, dispatch, progress, name, locator, derivation,
                 oversized="Table row exceeds text budget"):
        self.query, self.template = ExtractQuery, extraction_template
        self.content, self.on_task, self.state = job.content, job.on_task, job.state
        self.s, self.output, self.dispatch, self.progress, self.name = client.s, output, dispatch, progress, name
        self.locator, self.derivation, self.oversized = locator, derivation, oversized
        self.evidence, self.coverage, self.repeats = [], [], {}
        self.sections = self.reader = None

    def record(self, row, items=()):
        self.coverage.append(row)
        if self.on_task:
            self.on_task(row, list(items))

    def result(self, sort):
        """(evidence with sightings merged, coverage sorted by sort)."""
        self.coverage.sort(key=sort)
        return merge_occurrences(self.evidence), self.coverage

    def follow(self, entry, page_no, bbox, task, region):
        """Record a repeated block from its first occurrence's result, without a model call."""
        note = f"identical to {entry['task']} on page {entry['page']}; not re-sent"
        step = DerivationStep(step="repeated-block", detail=note)
        section = self.sections.box(page_no, bbox)
        copies = [e.model_copy(update={"locator": self.locator(page_no, tuple(bbox), region, task),
                                       "section": section.id, "derivation": [*e.derivation, step]})
                  for e in entry["found"]]
        row = coverage_row(content=self.content, page=page_no, bbox=list(bbox), task=task, status=entry["row"]["status"],
                           issues=[note], claims=len(copies), duplicate_of=entry["task"])
        self.evidence.extend(copies)
        self.record(row, copies)

    def consume(self, page_no, bbox, task, text, image=None, check=None, locate=None, crop=None, derivation=None,
                then=None, repeat_key=None, repeat_after=1, place=None, context="", extra_images=(), continued=(),
                origin=None, leading=None):
        """Queue one extraction task; when it finishes, record it and call then(status).

        An answer incomplete with its claims at the limit is the model asking for more: the task is asked again
        ("<task>-c<n>", up to the continuation limit), told the claims returned so far (continued), and then(status)
        waits for the last of them.

        repeat_key identifies exactly repeated boilerplate: once `repeat_after` earlier
        sightings prove the repetition, the task follows the first occurrence's result
        instead of calling the model (or is extracted normally if that one failed).

        check(quote) -> bool | None. Native tasks reject claims failing it; visual tasks
        only record the result. locate(quote) narrows a claim's bbox within the task.
        place(quote) -> box or None: where a visual claim's quote sits, to find its section.
        Each claim found becomes one occurrence; sightings of the same claim by other
        tasks are merged into one piece of evidence afterwards (union provenance).
        """
        s, content, state = self.s, self.content, self.state
        region = region_of(task)
        entry = None
        if repeat_key is not None and s.dedupes_repeated_rows():
            entry = self.repeats.setdefault(repeat_key, {"task": task, "page": page_no, "seen": 0, "done": False,
                                                         "ok": False, "found": [], "row": None, "followers": []})
            entry["seen"] += 1
            if entry["task"] != task and entry["seen"] - 1 >= repeat_after:
                again = lambda: self.consume(page_no, bbox, task, text, image, check, locate, crop, derivation, then,
                                             place=place, context=context, extra_images=extra_images)
                if not entry["done"]:
                    entry["followers"].append((lambda: self.follow(entry, page_no, bbox, task, region), again))
                elif entry["ok"]:
                    self.follow(entry, page_no, bbox, task, region)
                else:
                    again()
                return
            if entry["task"] != task:
                entry = None  # an early sighting, extracted normally before repetition is proven
        found = []
        row = coverage_row(content=content, page=page_no, bbox=list(bbox), task=task, image=image, status="complete")
        images = ([self.output / image] if image else []) + [self.output / x for x in extra_images]
        section = self.sections.box(page_no, bbox)  # the heading above the region, not the page's
        # A region spanning sections (a tile, an overview) is told all their headings.
        heading = " | ".join(" > ".join(x.heading_path) for x in self.sections.spanned_box(page_no, bbox)
                             if x.heading_path)
        rules = s.region_rules(region)
        prompt = self.query(self.template(s).replace("{max_claims}", str(s.claims_per_request)) + rules,
                            region, heading, context, text, continuation(continued) if continued else "").prompt()
        key = ("extract", region, content, task, hashlib.sha256(text.encode()).hexdigest(), crop, heading)
        if context:  # only then, so requests without context keep their recorded keys
            key += (hashlib.sha256(context.encode()).hexdigest(),)
        if rules:  # image-task rules aren't in the interpreter's prompt hash (text tasks keep replaying),
            key += ("visual rules", hashlib.sha256(rules.encode()).hexdigest())  # so they're in the key
        if continued:
            key += ("continued", len(continued))

        origin = origin or task
        turn = int(task.rsplit("-c", 1)[1]) if task != origin else 0
        more = []  # the answer's claims, when it asks to be continued
        asked = []  # [True] when it does (it may ask with no claim of its own)

        def finish(result, error):
            state["pending"] -= 1
            if error is not None:
                # not reached: the call limit, the cost cap, or an answer a replay doesn't hold. Nothing was learnt,
                # so it isn't refined; the next run asks it again.
                unreached = isinstance(error, (CallLimitReached, NotRecorded))
                row.update(status="not_reached" if unreached else "failed", issues=[str(error)])
            else:
                handle(result)
            self.evidence.extend(found)
            self.record(row, found)
            self.progress.finish(row["status"])
            # the first occurrence of a repeated block (or a continuation of it): its followers are released after
            # its last turn, with every turn's claims (code review 2026-10-08, A14: only the first turn's)
            lead = entry if entry is not None else leading
            if lead is not None:
                lead["found"].extend(found)
                if not asked:
                    lead.update(done=True, ok=row["status"] in ("complete", "partial"), row=row)
                    for followed, again in lead.pop("followers"):
                        followed() if lead["ok"] else again()
                    lead["followers"] = []
            log.debug("%s %s: %s, %d claim(s)%s", Path(self.name).name, task, row["status"], row["claims"],
                      f" ({'; '.join(row['issues'])[:200]})" if row["issues"] else "")
            if asked:
                self.consume(page_no, bbox, f"{origin}-c{turn + 1}", text, image, check, locate, crop, derivation, then,
                             place=place, context=context, extra_images=extra_images,
                             continued=tuple(continued) + tuple(more), origin=origin, leading=lead)
            elif then:
                then(row["status"])

        def handle(result):
            row["status"] = "complete" if result.complete else "partial"
            row["issues"] = list(result.issues)
            if (not result.complete and turn < s.continuation_limit(region)
                    and (len(result.claims) >= s.claims_per_request or any(LIMIT_SAID.search(i) for i in result.issues))):
                more.extend(result.claims)
                asked.append(True)
                row["issues"].append(f"Continued: the claim limit reached, the rest asked for ({origin}-c{turn + 1})")
            for claim in result.claims:
                verified = check(claim.quote) if check else None
                if not image and not verified:
                    row["status"] = "partial"
                    row["issues"].append("Rejected claim with unsupported literal quote")
                    continue
                eid = claim_id(content, claim)
                if any(e.id == eid for e in found):
                    continue  # the same claim twice in one response: keep the first
                where = tuple(locate(claim.quote) if locate else bbox)
                spot = place(claim.quote) if place else where
                home = self.sections.box(page_no, spot).id if spot is not None else section.id
                found.append(Evidence(**claim.model_dump(), id=eid, content=content, section=home,
                                      locator=self.locator(page_no, where, region, task),
                                      derivation=derivation or self.derivation[region], image=image,
                                      quote_verified=verified))
                row["claims"] += 1

        self.progress.add()
        state["pending"] += 1
        self.dispatch.submit(prompt, Extraction, images, key, finish)

    # --- text and table tasks, the same for every format

    def text_task(self, page_no, segments, task, depth=0, derivation=None, context=None):
        """segments: [(bbox, text)] of consecutive blocks sent together; derivation: the steps to its claims, and
        context: its context lines, if not a text block's (a key-value list's: a table's)."""
        s = self.s
        text = "\n\n".join(t for _, t in segments)
        given = context  # a refined part is given the same override, else gets its own text's context
        context = self.reader.for_text(page_no, segments, text) if given is None else given
        def locate(quote):
            return next((b for b, t in segments if quoted(quote, t)), union(b for b, _ in segments))
        match = lambda q: quoted(q, text) or s.loose_match(q, text)
        self.consume(page_no, union(b for b, _ in segments), task, text, check=match, locate=locate,
                     context=context, derivation=derivation,
                     then=lambda status: self.refine_text(page_no, segments, text, task, depth, status, derivation,
                                                          given))

    def refine_text(self, page_no, segments, text, task, depth, status, derivation=None, context=None):
        if status not in ("partial", "failed") or depth >= self.s.refinement_depth:
            return
        if len(segments) > 1:
            middle = len(segments) // 2
            parts = [segments[:middle], segments[middle:]]
        elif len(text.encode()) > MIN_REFINE_BYTES:
            bbox = segments[0][0]
            parts = [[(bbox, p)] for p in split_utf8(text, max(200, len(text.encode()) // 2))]
        else:
            return
        for i, part in enumerate(parts):
            self.text_task(page_no, part, f"{task}:r{i}", depth + 1, derivation, context)

    def table_task(self, page_no, bbox, task, header, row, columns, depth=0, derivation=None, repeat_key=None):
        """Send one table row with its header; split wide or partial rows by column.

        Column 0 is kept in every split as the provisional row label.
        """
        s = self.s
        pick = lambda cells: [cells[c] if c < len(cells) else None for c in columns]
        head, cells = pick(header), pick(row)
        text = "Header: " + json.dumps(head, ensure_ascii=False) + "\nRow: " + json.dumps(cells, ensure_ascii=False)
        flat = " ".join(str(c) for c in head + cells if c not in (None, ""))
        fits = len(text.encode()) <= s.text_bytes
        splittable = len(columns) > 2
        if not fits and not splittable:
            self.record(coverage_row(content=self.content, page=page_no, bbox=list(bbox), task=task, status="partial",
                                     issues=[self.oversized]))
            return
        if fits:
            def then(status):
                # as text and pictures: only a partial or failed answer is refined; "not reached" (the call limit, an
                # answer a replay lacks) learnt nothing (code review 2026-10-08, A3: it tripled the unreached rows)
                if status in ("partial", "failed") and depth < s.refinement_depth and splittable:
                    self.split_columns(page_no, bbox, task, header, row, columns, depth + 1, derivation)
            context = self.reader.for_table(page_no, bbox, flat)
            if repeat_key is not None and context:  # the same row under another lead-in or stem isn't a repeat
                repeat_key += (hashlib.sha256(context.encode()).hexdigest(),)
            self.consume(page_no, bbox, task, text, derivation=derivation,
                         check=lambda q: quoted(q, text) or covered(q, flat) or s.loose_match(q, text),
                         then=then, repeat_key=repeat_key, repeat_after=2, context=context)
        else:
            self.split_columns(page_no, bbox, task, header, row, columns, depth, derivation)

    def split_columns(self, page_no, bbox, task, header, row, columns, depth, derivation):
        rest = columns[1:]
        middle = (len(rest) + 1) // 2
        for i, part in enumerate([rest[:middle], rest[middle:]]):
            # Budget-driven splits are mandatory; only quality-driven ones use depth.
            self.table_task(page_no, bbox, f"{task}:c{i}", header, row, [columns[0], *part], depth, derivation)
