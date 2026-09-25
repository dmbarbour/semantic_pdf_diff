import hashlib
import json
import os
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

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
    region: Literal["text", "table", "tile", "overview"]
    task: str

# Other formats add their own locator shapes, discriminated by `format`.
Locator = PdfLocator

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
    origin: Literal["outline", "pages"]
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

class PanelLabel(Lenient):
    """A panel model's review of one item; checked against the taxonomy afterwards."""
    verdict: str = ""
    flags: list[str] = Field(default_factory=list, max_length=30)
    clarity: str = ""
    confidence: str = ""
    note: str = Field(default="", max_length=1000)

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
REGION_RANK = {"text": 0, "table": 0, "tile": 1, "overview": 2}

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

class Settings(Strict):
    model: str = "gemma-4"
    base_url: str = "http://localhost:8000/v1"
    context_tokens: int = Field(default=8192, ge=2048)
    output_tokens: int = Field(default=1400, ge=256)
    # Claims asked for per extraction request; raise with output_tokens (about 150 tokens per claim).
    claims_per_request: int = Field(default=6, ge=1, le=100)
    image_tokens: int = Field(default=1200, ge=1)
    safety_tokens: int = Field(default=400, ge=100)
    # A safety stop against runaway runs, not a budget: throughput is governed by rate_limits.
    max_calls: int = Field(default=100_000, ge=1)
    retries: int = Field(default=2, ge=0, le=5)
    timeout: float = Field(default=120, gt=0)
    text_bytes: int = Field(default=1800, ge=200)
    image_side: int = Field(default=1000, ge=256, le=2000)
    tile_points: int = Field(default=420, ge=100)
    refinement_depth: int = Field(default=1, ge=0, le=3)
    # Sections come from the PDF outline down to this depth, else fixed page ranges.
    section_depth: int = Field(default=2, ge=1, le=6)
    section_pages: int = Field(default=20, ge=1, le=1000)
    # Extract exactly repeated table rows (same cells, same table position, 3+ pages) once.
    dedupe_repeated: bool = True
    top_k: int = Field(default=4, ge=1, le=30)
    min_score: float = Field(default=0.10, ge=0, le=1)
    max_pairs: int = Field(default=1000, ge=1)
    vision: bool = True
    # Situating stage: figure and section "about" statements after extraction.
    situate: bool = True
    verify_visuals: bool = True
    response_format: Literal["none", "json_object", "json_schema"] = "none"
    temperature: float | None = Field(default=0.0, ge=0, le=2)
    seed: int | None = None
    max_token_field: Literal["max_tokens", "max_completion_tokens"] = "max_tokens"
    aliases: dict[str, str] = Field(default_factory=dict)
    # Debugging: verify that a semantic cache hit was recorded for a byte-identical request.
    cache_check: bool = False
    # Throughput: requests in flight at most (adaptive below this), and rate-limit rules.
    concurrency: int = Field(default=4, ge=1, le=64)
    # Seconds between progress lines when output isn't a terminal.
    heartbeat_seconds: float = Field(default=30.0, gt=0)
    rate_limits: list[RateRule] = Field(default_factory=list)
    # Sources: rescan roots on every run ("auto") or only on `source update` ("manual").
    rescan: Literal["auto", "manual"] = "auto"
    # Archive safety backstops: generous, and anything they stop is reported.
    max_zip_depth: int = Field(default=8, ge=4)
    max_source_bytes: int = Field(default=50 * 1024 ** 3, ge=1)
    zip_ratio_limit: float = Field(default=1000.0, gt=1)
    zip_ratio_min_bytes: int = Field(default=100 * 1024 ** 2, ge=0)

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
    def from_env(cls, **overrides):
        """Load environment defaults, then explicit file/CLI/programmatic overrides.

        Keep plain Settings() deterministic for library callers and fixtures.
        Empty environment values are treated as unset.
        """
        values = {}
        names = {"base_url": "OPENAI_BASE_URL", "model": "OPENAI_MODEL"}
        # An explicit legacy json_mode must beat an environment response_format.
        explicit = set(overrides) | ({"response_format"} if "json_mode" in overrides else set())
        for field in [*cls.model_fields, "json_mode"]:
            if field in explicit:
                continue
            name = names.get(field, "PDF_DIFF_" + field.upper())
            raw = os.environ.get(name)
            if raw is None or not raw.strip():
                continue
            if field in ("aliases", "rate_limits"):
                try:
                    values[field] = json.loads(raw)
                except ValueError as exc:
                    shape = "object mapping aliases to canonical names" if field == "aliases" else "list of rate-limit rules"
                    raise ValueError(f"{name} must be a JSON {shape}") from exc
            else:
                values[field] = raw.strip()
        values.update(overrides)
        return cls(**values)

    @model_validator(mode="after")
    def capacity(self):
        if self.context_tokens <= self.output_tokens + self.safety_tokens + 600:
            raise ValueError("Context must leave room for prompts after output and safety reserves")
        return self
