import json
import os
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")

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

class Extraction(Strict):
    claims: list[Claim] = Field(max_length=12)
    complete: bool
    issues: list[str] = Field(default_factory=list, max_length=10)

class Evidence(Claim):
    id: str
    document: Literal["A", "B"]
    page: int
    bbox: tuple[float, float, float, float]
    source: str
    image: str | None = None

class Judgment(Strict):
    relation: Literal["equivalent", "different", "complementary", "unrelated", "uncertain"]
    rationale: str = Field(min_length=1, max_length=800)
    confidence: float = Field(ge=0, le=1)
    same_conditions: bool

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
    top_k: int = Field(default=4, ge=1, le=30)
    min_score: float = Field(default=0.10, ge=0, le=1)
    max_pairs: int = Field(default=1000, ge=1)
    vision: bool = True
    verify_visuals: bool = True
    json_mode: bool = False
    max_token_field: Literal["max_tokens", "max_completion_tokens"] = "max_tokens"
    aliases: dict[str, str] = Field(default_factory=dict)

    @classmethod
    def from_env(cls, **overrides):
        """Load environment defaults, then explicit file/CLI/programmatic overrides.

        Keep plain Settings() deterministic for library callers and fixtures.
        Empty environment values are treated as unset.
        """
        values = {}
        names = {"base_url": "OPENAI_BASE_URL", "model": "OPENAI_MODEL"}
        for field in cls.model_fields:
            if field in overrides:
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
