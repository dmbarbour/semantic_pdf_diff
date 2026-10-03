import hashlib
import json
import os
from functools import lru_cache
from typing import Annotated, Literal, get_origin
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator
from .levers import DEFAULT_LEVERS, EVERY_ROLE, Declared, compose, setting_classes

class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")

Basis = Literal["measured", "calculated", "simulated", "projected", "required", "targeted", "asserted", "unknown"]

class Claim(Strict):
    entity: str = Field(min_length=1, max_length=160)
    attribute: str = Field(min_length=1, max_length=160)
    value: str = Field(min_length=1, max_length=300)
    unit: str = Field(default="", max_length=40)
    conditions: str = Field(default="", max_length=300)
    kind: Literal["text", "table", "chart", "diagram"]
    quote: str = Field(min_length=1, max_length=400)
    confidence: float = Field(ge=0, le=1)
    approximate: bool = False
    # Claim context (schema v2). Prompts don't ask for these yet, so they default to
    # "not stated"; the epistemic-status work fills them.
    topic: str = Field(default="", max_length=200)
    basis: Basis = "unknown"
    uncertainty: str = Field(default="", max_length=200)
    context: str = Field(default="", max_length=300)
    role: str = Field(default="", max_length=200)

OPTIONAL_CLAIM_FIELDS = ("unit", "conditions", "approximate", "topic", "basis", "uncertainty", "context", "role")

# Sanity bounds on one answer; the requested maximum is Settings.claims_per_request.
MAX_CLAIMS, MAX_ISSUES = 200, 10

class Extraction(Strict):
    claims: list[Claim] = Field(max_length=MAX_CLAIMS)
    complete: bool
    issues: list[str] = Field(default_factory=list, max_length=MAX_ISSUES)

    @model_validator(mode="before")
    @classmethod
    def salvage(cls, data):
        """Keep valid claims from an imperfect small-model response.

        Unknown keys are dropped and null optional strings become empty. A claim that
        still fails validation is discarded (never repaired) and the result is marked
        incomplete, so salvage is visible in the coverage ledger.
        """
        if not isinstance(data, dict) or not isinstance(data.get("claims"), list):
            return data
        issues = [str(i) for i in data.get("issues") or [] if i is not None]
        claims, dropped = [], 0
        for raw in data["claims"]:
            if not isinstance(raw, dict):
                dropped += 1
                continue
            item = {k: v for k, v in raw.items() if k in Claim.model_fields}
            for k in OPTIONAL_CLAIM_FIELDS:
                if item.get(k) is None:
                    item.pop(k, None)
            if item.get("basis") not in Basis.__args__:
                item.pop("basis", None)  # an unrecognized basis is "unknown", not a broken claim
            try:
                claims.append(Claim.model_validate(item).model_dump())
            except ValidationError:
                dropped += 1
        complete = data.get("complete")
        if dropped:
            issues.append(f"Discarded {dropped} malformed claim(s)")
            complete = False
        if len(claims) > MAX_CLAIMS:
            issues.append(f"Kept first {MAX_CLAIMS} of {len(claims)} claims")
            claims, complete = claims[:MAX_CLAIMS], False
        if len(issues) > MAX_ISSUES:
            issues = issues[:MAX_ISSUES - 1] + [f"{len(issues) - MAX_ISSUES + 1} further issue(s) omitted"]
        return {"claims": claims, "complete": complete, "issues": [i[:500] for i in issues]}

class Source(Strict):
    """A comparison object declared in the store: a name, provenance metadata and the
    roots (files, folders, zip archives) holding its content."""
    name: str = Field(min_length=1, max_length=200, pattern=r"^[^\s@/][^@/]*$")
    kind: Literal["declared", "shortcut", "manifest"] = "declared"
    metadata: dict[str, str] = Field(default_factory=dict)
    roots: list[str] = Field(default_factory=list)
    manifest: str | None = None

class FileRef(Strict):
    """A path within a source that refers to content."""
    source: str
    path: str
    content: str
    metadata: dict[str, str] = Field(default_factory=dict)

class PdfLocator(Strict):
    """Where a claim sits within PDF content: unrotated page coordinates, never a path."""
    format: Literal["pdf"] = "pdf"
    page: int = Field(ge=1)
    bbox: tuple[float, float, float, float]
    region: Literal["text", "table", "tile", "figure", "overview"]
    task: str

class TextLocator(Strict):
    """Where a claim sits within a text file (.txt, .md): its page (a form feed starts one) and its lines, counted
    from 1 through the file; never a path."""
    format: Literal["text"] = "text"
    page: int = Field(ge=1)
    lines: tuple[int, int]
    region: Literal["text", "table"]
    task: str

    @property
    def bbox(self):
        """Its lines as a box, (0, first, 1, last + 1): sections and the task core place text in lines as PDF in points."""
        return (0.0, float(self.lines[0]), 1.0, float(self.lines[1] + 1))

# Each format has its locator shape, told apart by `format`.
Locator = Annotated[PdfLocator | TextLocator, Field(discriminator="format")]

class Section(Strict):
    """A logical part of one piece of content: the unit of context, and later of scheduling."""
    id: str
    first_page: int = Field(ge=1)
    last_page: int = Field(ge=1)
    # Where on its first and last page the section starts and ends (unrotated y); a
    # page can hold the end of one section and the start of the next.
    first_y: float = 0.0
    last_y: float | None = None        # None: to the bottom of last_page
    heading_path: list[str] = Field(default_factory=list)
    origin: Literal["outline", "pages", "headings"]  # headings: a text file's (textdocs.py)
    # Cheap triage signals summed over the section's pages (numbers, units, requirement
    # words, tables, images, vector drawings, text characters); filled as pages are read.
    signals: dict[str, int] = Field(default_factory=dict)
    # Filled by the situating stage.
    about: str = ""
    section_type: str = ""
    density: str = ""
    keywords: list[str] = Field(default_factory=list)

class Lenient(Strict):
    """Model output: unknown keys are dropped, nulls become defaults, and overlong
    strings and lists are cut to their limits rather than failing the answer."""
    @model_validator(mode="before")
    @classmethod
    def tidy(cls, data):
        if not isinstance(data, dict):
            return data
        tidied = {}
        for key, value in data.items():
            if key not in cls.model_fields or value is None:
                continue
            if cls.model_fields[key].annotation is str and isinstance(value, list):  # lines given as a list
                value = "\n".join(map(str, value))
            limit = next((m.max_length for m in cls.model_fields[key].metadata if hasattr(m, "max_length")), None)
            if limit is not None and isinstance(value, (str, list)):
                value = value[:limit]
            tidied[key] = value
        return tidied

class FigureAbout(Lenient):
    about: str = Field(min_length=1, max_length=800)
    role: str = Field(default="", max_length=500)
    keywords: list[str] = Field(default_factory=list, max_length=15)
    label: str = Field(default="", max_length=60)    # an identifier visible in the figure, e.g. "Sheet A-101"
    title: str = Field(default="", max_length=200)   # a title visible in the figure

SECTION_TYPES = ("specification", "requirements", "narrative", "calculation", "data", "drawing", "procedure",
                 "legal", "administrative", "reference", "other")

class SectionAbout(Lenient):
    about: str = Field(min_length=1, max_length=1200)
    type: str = "other"
    density: Literal["low", "medium", "high"] = "medium"
    keywords: list[str] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def known_type(self):
        if self.type not in SECTION_TYPES:
            self.type = "other"
        return self

class Reference(Strict):
    """A sentence citing a figure (or table, sheet, exhibit) by label."""
    page: int
    bbox: tuple[float, float, float, float]
    text: str
    paragraph: str = ""                                  # the text block holding the sentence
    label: str
    evidence: list[str] = Field(default_factory=list)   # claims extracted from the citing text

class Figure(Strict):
    """A figure found mechanically: a drawing cluster or image, a caption, or both."""
    id: str
    page: int
    bbox: tuple[float, float, float, float]
    kind: Literal["figure", "table", "sheet", "exhibit"] = "figure"
    label: str | None = None           # e.g. "figure 3" or "sheet A-101"
    label_source: Literal["", "caption", "title block", "model"] = ""
    caption: str = ""
    title: str = ""                    # a title from the title block or read by the model
    region: bool = True                # False: a caption whose drawing wasn't found
    references: list[Reference] = Field(default_factory=list)
    claims: list[str] = Field(default_factory=list)       # visual claims found inside the figure
    # Filled by the situating requests.
    about: str = ""
    role: str = ""
    keywords: list[str] = Field(default_factory=list)

class DerivationStep(Strict):
    step: str
    detail: str = ""

class Occurrence(Strict):
    """One sighting of a claim by one extraction task."""
    locator: Locator
    section: str = ""
    kind: Literal["text", "table", "chart", "diagram"]
    quote: str
    quote_verified: bool | None = None
    confidence: float = Field(ge=0, le=1)
    image: str | None = None
    derivation: list[DerivationStep] = Field(default_factory=list)
    # How this sighting worded the claim ("entity | attribute | value unit | conditions"), when
    # it was merged with the claim as another reading of the same fact (see readings.reconcile).
    wording: str = ""

class Evidence(Claim):
    """A claim within one piece of content.

    The ID derives from the content and the claim's identity only (see claim_id), so
    it doesn't depend on where or in which order the claim was found. Locator, section,
    quote, image and derivation are those of the representative occurrence; all
    sightings are listed in `occurrences` (empty for a single, unmerged sighting).
    """
    id: str
    content: str
    locator: Locator
    section: str = ""
    derivation: list[DerivationStep] = Field(default_factory=list)
    image: str | None = None
    # True: quote found in the PDF text layer; False: the region has a text layer but
    # the quote is absent (possible misread, or raster labels); None: not checkable.
    quote_verified: bool | None = None
    occurrences: list[Occurrence] = Field(default_factory=list)

def claim_id(content, claim):
    """Evidence ID from content and claim identity: entity, attribute, value and conditions
    (whitespace-normalized, case-folded), unit (exact: mW is not MW), approximate and basis."""
    fold = lambda text: " ".join(str(text).split()).casefold()
    identity = [content, fold(claim.entity), fold(claim.attribute), fold(claim.value), claim.unit.strip(),
                fold(claim.conditions), claim.approximate, claim.basis]
    return "ev-" + hashlib.sha256(json.dumps(identity).encode()).hexdigest()[:16]

# Representative occurrence: native before visual, tile before overview, then the
# smallest region, then page and task order.
REGION_RANK = {"text": 0, "table": 0, "figure": 1, "tile": 2, "overview": 3}

def representative_rank(e):
    x0, y0, x1, y1 = e.locator.bbox
    return REGION_RANK.get(e.locator.region, 3), (x1 - x0) * (y1 - y0), e.locator.page, e.locator.task

def merge_occurrences(sightings):
    """Group single-sighting evidence by claim ID into claims whose provenance is the union
    of their occurrences. The result doesn't depend on the order of `sightings`."""
    groups = {}
    for e in sightings:
        groups.setdefault(e.id, []).append(e)
    merged = []
    for items in groups.values():
        items.sort(key=representative_rank)
        occurrences = [Occurrence(locator=i.locator, section=i.section, kind=i.kind, quote=i.quote,
                                  quote_verified=i.quote_verified, confidence=i.confidence, image=i.image,
                                  derivation=i.derivation)
                       for i in sorted(items, key=lambda i: (i.locator.page, i.locator.task))]
        merged.append(items[0].model_copy(update={"confidence": max(i.confidence for i in items),
                                                  "occurrences": occurrences}))
    return sorted(merged, key=lambda e: (e.locator.page, e.locator.task, e.id))

class Interpreter(Strict):
    """Everything besides the bytes that shapes derived data for one role."""
    role: Literal["extract", "triage", "embed", "summarize", "compare"]
    model: str
    prompt_hash: str
    settings: dict
    versions: dict[str, str]

class Judgment(Strict):
    relation: Literal["equivalent", "different", "complementary", "unrelated", "uncertain"]
    rationale: str = Field(min_length=1, max_length=800)
    confidence: float = Field(ge=0, le=1)
    same_conditions: bool

    @model_validator(mode="before")
    @classmethod
    def drop_unknown(cls, data):
        if isinstance(data, dict):
            return {k: v for k, v in data.items() if k in cls.model_fields}
        return data

class RateRule(Strict):
    """A throughput ceiling, applying on the given days and hours (local time).

    The first matching rule applies; a rule without days or hours always matches.
    """
    days: str | None = Field(default=None, pattern=r"^(mon|tue|wed|thu|fri|sat|sun)(-(mon|tue|wed|thu|fri|sat|sun))?"
                                                    r"(,(mon|tue|wed|thu|fri|sat|sun)(-(mon|tue|wed|thu|fri|sat|sun))?)*$")
    hours: str | None = Field(default=None, pattern=r"^([01]\d|2[0-3]):[0-5]\d-([01]\d|2[0-4]):[0-5]\d$")
    tokens_per_minute: int | None = Field(default=None, ge=1)
    requests_per_minute: int | None = Field(default=None, ge=1)

class Endpoint(Strict):
    """How requests travel, budgets and limits: never what a query says, so never part of a configuration
    (levers.Platform). The model is the exception: its answers depend on it, so every role binds it."""
    model: Annotated[str, Declared("endpoint", EVERY_ROLE)] = "gemma-4"
    base_url: Annotated[str, Declared("endpoint")] = "http://localhost:8000/v1"
    # A safety stop against runaway runs, not a budget: throughput is governed by rate_limits.
    max_calls: Annotated[int, Declared("endpoint")] = Field(default=100_000, ge=1)
    # Stop sending once the provider-reported cost of this run reaches this many dollars.
    max_cost: Annotated[float | None, Declared("endpoint")] = Field(default=None, gt=0)
    retries: Annotated[int, Declared("endpoint")] = Field(default=2, ge=0, le=5)
    # Seconds without data before giving up. Answers are streamed, so this is between chunks, not
    # for the whole answer (a slow answer cut off by a total timeout is still billed).
    timeout: Annotated[float, Declared("endpoint")] = Field(default=120, gt=0)
    stream: Annotated[bool, Declared("endpoint")] = True
    # Throughput: requests in flight at most (adaptive below this), and rate-limit rules.
    concurrency: Annotated[int, Declared("endpoint")] = Field(default=4, ge=1, le=64)
    # Seconds between progress lines when output isn't a terminal.
    heartbeat_seconds: Annotated[float, Declared("endpoint")] = Field(default=30.0, gt=0)
    rate_limits: Annotated[list[RateRule], Declared("endpoint")] = Field(default_factory=list)

class SettingsBase(Strict):
    """Loading: the environment, then a file's or a caller's settings. A settings file may name its levers in
    order ("levers"); without, the default configuration (levers.DEFAULT_LEVERS)."""

    @model_validator(mode="before")
    @classmethod
    def own_levers(cls, data):
        # A configuration's data names its levers; a class composed of others can't hold it.
        if isinstance(data, dict) and "levers" in data:
            data = dict(data)
            levers = tuple(data.pop("levers"))
            if levers != cls.levers:
                raise ValueError(f"these settings are for levers {list(cls.levers)}, not {list(levers)}: "
                                 "build them with Settings.configured(levers=...) or from_env")
        return data

    @model_validator(mode="before")
    @classmethod
    def legacy_json_mode(cls, data):
        # json_mode (0.1.x) maps onto response_format; an explicit response_format wins.
        if isinstance(data, dict) and "json_mode" in data:
            data = dict(data)
            legacy = data.pop("json_mode")
            if isinstance(legacy, str):
                legacy = legacy.strip().lower() in ("1", "true", "yes", "on")
            data.setdefault("response_format", "json_object" if legacy else "none")
        return data

    @classmethod
    def configured(cls, levers=None, **values):
        """Settings for a configuration: its levers in order (None: the default) and its values."""
        return (cls if levers is None else settings_class(tuple(levers)))(**values)

    @classmethod
    def from_env(cls, **overrides):
        """Load environment defaults, then explicit file/CLI/programmatic overrides.

        Keep plain Settings() deterministic for library callers and fixtures.
        Empty environment values are treated as unset.
        """
        levers = overrides.pop("levers", None)
        target = cls if levers is None else settings_class(tuple(levers))
        values = {}
        names = {"base_url": "OPENAI_BASE_URL", "model": "OPENAI_MODEL"}
        # An explicit legacy json_mode must beat an environment response_format.
        explicit = set(overrides) | ({"response_format"} if "json_mode" in overrides else set())
        for field in [*target.model_fields, "json_mode"]:
            if field in explicit:
                continue
            name = names.get(field, "PDF_DIFF_" + field.upper())
            raw = os.environ.get(name)
            if raw is None or not raw.strip():
                continue
            if field in target.model_fields and get_origin(target.model_fields[field].annotation) in (list, dict):
                try:
                    values[field] = json.loads(raw)
                except ValueError as exc:
                    shape = {"aliases": "object mapping aliases to canonical names",
                             "rate_limits": "list of rate-limit rules"}.get(field, "list of strings")
                    raise ValueError(f"{name} must be a JSON {shape}") from exc
            else:
                values[field] = raw.strip()
        values.update(overrides)
        return target(**values)

@lru_cache(maxsize=None)
def settings_class(levers=DEFAULT_LEVERS):
    """The settings for an ordered list of levers: endpoint settings beside the composed platform."""
    return type("Settings", (SettingsBase, Endpoint, compose(levers)), {"__module__": __name__})

Settings = settings_class()

REPORT_SCHEMA = 2  # report.json and evidence.json (and the comparisons a store saves)

class CoverageRow(Strict):
    """One task's outcome, as a store keeps it and a report shows it: the one owner of its fields (code review
    2026-10-01: six hand-written rows). Rows travel as dicts (row())."""
    content: str
    page: int | None = None
    bbox: list | None = None
    task: str
    image: str | None = None
    status: Literal["complete", "partial", "failed", "skipped", "not_reached"]
    issues: list[str] = Field(default_factory=list)
    claims: int = 0
    duplicate_of: str | None = None  # a repeated block's first occurrence, whose result it follows

    def row(self):
        out = self.model_dump()
        if out["duplicate_of"] is None:
            del out["duplicate_of"]
        return out

def coverage_row(**fields):
    return CoverageRow(**fields).row()

class Situation(Strict):
    """A content item's situating results, as reports carry them."""
    figures: list[dict]
    unresolved: list[dict]
    issues: list
    quality: dict | None = None

class EvidenceDocument(Strict):
    """evidence.json: what was read, written before comparing (so it stands if comparing fails)."""
    schema_version: int = REPORT_SCHEMA
    sources: list[dict]
    files: list[dict]
    interpreters: dict
    evidence: list[dict]
    coverage: list[dict]
    sections: list[dict]
    situation: dict
    scan_issues: list[dict]

class Report(Strict):
    """report.json: the comparison (compare()'s result first) and everything it rests on; report.html is drawn
    from it. A key compare() adds must be added here: a report holds nothing unowned."""
    mode: str
    findings: list[dict]
    unmatched: list[dict]
    shared: list[str]
    retrieval: dict
    # revisions: how alignment grouped the two revisions' items, as it saw them (align.py; empty in proposals)
    groupings: list[dict] = Field(default_factory=list)
    schema_version: int = REPORT_SCHEMA
    created_at: str
    sources: list[dict]
    files: list[dict]
    interpreters: dict
    scan_issues: list[dict]
    file_difference: dict
    sections: list[dict]
    situation: dict
    evidence: list[dict]
    coverage: list[dict]
    settings: dict
    usage: dict
    limitations: list[str]

# What every evaluating model (judges, query checkers, the post-mortem's analyst) is asked with.
# Its answers are recorded by query, so these must be the same wherever a folder is judged; the
# transport (concurrency, timeouts, retries, caps) varies by caller and never changes a query.
EVALUATOR_SETTINGS = {"context_tokens": 262144, "output_tokens": 16000, "image_tokens": 3000}

# Each setting's class (levers.Declared), read off the declarations.
SETTING_CLASSES = setting_classes(Settings)
