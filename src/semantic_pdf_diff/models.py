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

MAX_CLAIMS, MAX_ISSUES = 12, 10

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
    """A comparison object: a folder, an archive, a single file or a manifest."""
    id: str
    name: str
    kind: Literal["file", "folder", "zip", "manifest"]
    metadata: dict[str, str] = Field(default_factory=dict)

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
    heading_path: list[str] = Field(default_factory=list)
    origin: Literal["outline", "pages"]

class DerivationStep(Strict):
    step: str
    detail: str = ""

class Evidence(Claim):
    id: str
    content: str
    locator: Locator
    section: str = ""
    derivation: list[DerivationStep] = Field(default_factory=list)
    image: str | None = None
    # True: quote found in the PDF text layer; False: the region has a text layer but
    # the quote is absent (possible misread, or raster labels); None: not checkable.
    quote_verified: bool | None = None

class Interpreter(Strict):
    """Everything besides the bytes that shapes derived data for one role."""
    role: Literal["extract", "embed", "summarize", "compare"]
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

class Settings(Strict):
    model: str = "gemma-4"
    base_url: str = "http://localhost:8000/v1"
    context_tokens: int = Field(default=8192, ge=2048)
    output_tokens: int = Field(default=1400, ge=256)
    image_tokens: int = Field(default=1200, ge=1)
    safety_tokens: int = Field(default=400, ge=100)
    max_calls: int = Field(default=500, ge=1)
    retries: int = Field(default=2, ge=0, le=5)
    timeout: float = Field(default=120, gt=0)
    text_bytes: int = Field(default=1800, ge=200)
    image_side: int = Field(default=1000, ge=256, le=2000)
    tile_points: int = Field(default=420, ge=100)
    refinement_depth: int = Field(default=1, ge=0, le=3)
    # Sections come from the PDF outline down to this depth, else fixed page ranges.
    section_depth: int = Field(default=2, ge=1, le=6)
    section_pages: int = Field(default=20, ge=1, le=1000)
    top_k: int = Field(default=4, ge=1, le=30)
    min_score: float = Field(default=0.10, ge=0, le=1)
    max_pairs: int = Field(default=1000, ge=1)
    vision: bool = True
    verify_visuals: bool = True
    response_format: Literal["none", "json_object", "json_schema"] = "none"
    temperature: float | None = Field(default=0.0, ge=0, le=2)
    seed: int | None = None
    max_token_field: Literal["max_tokens", "max_completion_tokens"] = "max_tokens"
    aliases: dict[str, str] = Field(default_factory=dict)
    # Debugging: verify that a semantic cache hit was recorded for a byte-identical request.
    cache_check: bool = False

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
            if field == "aliases":
                try:
                    values[field] = json.loads(raw)
                except ValueError as exc:
                    raise ValueError(f"{name} must be a JSON object mapping aliases to canonical names") from exc
            else:
                values[field] = raw.strip()
        values.update(overrides)
        return cls(**values)

    @model_validator(mode="after")
    def capacity(self):
        if self.context_tokens <= self.output_tokens + self.safety_tokens + 600:
            raise ValueError("Context must leave room for prompts after output and safety reserves")
        return self
