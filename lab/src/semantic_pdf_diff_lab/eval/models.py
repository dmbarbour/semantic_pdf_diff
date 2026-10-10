"""The evaluation's types: a round's specification and criteria, and what judges and the review panel answer.
Moved from the product's models (code review 2026-10-01, A2: the product imported the round's rubrics through them).
"""
from typing import Literal

from pydantic import Field, model_validator

from semantic_pdf_diff.schema import Lenient, Strict

class PanelLabel(Lenient):
    """A panel model's review of one item; checked against the taxonomy afterwards."""
    verdict: str = ""
    fields: dict[str, str] = Field(default_factory=dict)
    flags: list[str] = Field(default_factory=list, max_length=30)
    clarity: str = ""
    confidence: str = ""
    note: str = Field(default="", max_length=1000)

class PanelQuestionLabel(Lenient):
    """A panel model's judgment of one question (a model's input), made without its answer."""
    adequacy: str = ""
    missing: list[str] = Field(default_factory=list, max_length=20)
    worth: str = ""
    blind: str = Field(default="", max_length=2000)
    confidence: str = ""
    note: str = Field(default="", max_length=1000)

class PairVerdict(Lenient):
    """A panel model's comparison of two claim sets for the same page region."""
    better: str = ""
    a_wrong: int | None = None
    b_wrong: int | None = None
    confidence: str = ""
    note: str = Field(default="", max_length=1500)
    a_problems: list[str] = Field(default_factory=list)  # rubric v2 on (rounds.PAIR_PROBLEMS)
    b_problems: list[str] = Field(default_factory=list)
    remarks: str = Field(default="", max_length=1500)    # for the maintainers, optional
    s_claims: list[dict] = Field(default_factory=list)   # rubric v6: claims both sets make, marked once
    a_claims: list[dict] = Field(default_factory=list)   # rubric v5: each claim's mark, by number
    b_claims: list[dict] = Field(default_factory=list)

class Gain(Strict):
    """A gain that lets a "no worse" variant through, named before judging: a mechanical figure
    (rounds.gains) and the relative change it must reach (-0.10: at least ten percent less)."""
    metric: str
    change: float

class Criteria(Strict):
    """How a round decides, written into round.json before judging starts (the owner's decision A,
    2026-09-28, docs/plans/query-improvement-2026-09-26.md): a development or combination round
    accepts a win, or "no worse" with a gain named in advance; a held-out round checks that an
    accepted change holds on documents it wasn't chosen on. Any round rejects a clear stratum loss."""
    role: Literal["development", "combination", "held-out"] = "development"
    win_low: float = Field(default=0.50, ge=0, le=1)          # a win: the overall interval lies above this
    noninferior_low: float = Field(default=0.45, ge=0, le=1)  # "no worse": its lower bound is at least this,
    gain: Gain | None = None                                  # and this gain is met (none: not accepted)
    stratum_loss_high: float = Field(default=0.45, ge=0, le=1)  # a stratum whose interval lies below this...
    stratum_min_units: int = Field(default=6, ge=1)           # ...on at least this many units blocks
    # Held-out: the overall mean must exceed held_out_mean and its interval's lower bound reach held_out_low
    # (the owner, 2026-09-30: the middle rule; simulated, 4.5% of rounds of five null variants promote one).
    held_out_mean: float = Field(default=0.50, ge=0, le=1)
    held_out_low: float = Field(default=0.45, ge=0, le=1)
    borderline: float = Field(default=0.03, ge=0)             # a bound this near its threshold is flagged
    watch_min_units: int = Field(default=10, ge=1)            # a stratum below the loss line on this many is watched

class VariantSpec(Strict):
    """A round's variant given in full: its settings file, the unit it's judged by ("page" for
    variants that move claims between kinds), and regions answered afresh (an A/A control)."""
    settings: str
    unit: Literal["family", "page"] = "family"
    fresh: list[str] = Field(default_factory=list)

class QueryChecks(Strict):
    """Strong models check what each variant changed in the queries before judging (rounds hold on flags)."""
    models: list[str] | None = None  # default: run_round.QUERY_CHECKERS
    sample: int = Field(default=30, ge=1)
    cap: float = Field(default=2.0, ge=0)

class PostMortem(Strict):
    """Every lever gets a post-mortem after its round, won, lost or no different (the owner, 2026-09-30):
    random samples of wins and losses, win rates by partition, and a strong model's reading."""
    units: int = Field(default=5, ge=1)              # units sampled from each of wins, losses and splits
    analyst: str | None = "google/gemini-3.1-pro"    # None: the evidence only, no model
    cap: float = Field(default=0.25, ge=0)           # dollars per round for the analyst

class RoundSpec(Strict):
    """A round's round.json, validated: a typo in a key fails instead of silently taking a default
    (the meta-audit: "rubric" misspelt judged with v1). See scripts/run_round.py."""
    name: str
    baseline: str | VariantSpec
    variants: dict[str, str | VariantSpec]
    set: Literal["dev", "heldout", "all"] = "dev"
    extract_only: bool = True
    units: int = Field(default=60, ge=1)
    chunk: int = Field(default=8, ge=1)
    min_units: int = Field(default=16, ge=1)
    cap: float = Field(default=15.0, ge=0)
    judges: list[str] = Field(default_factory=list)
    escalate: list[str] = Field(default_factory=list)
    confirm_judges: list[str] = Field(default_factory=list)
    confirm_units: int = Field(default=16, ge=1)
    rubric: str = "v1"
    query_checks: QueryChecks | None = None
    judge_timeout: int = Field(default=600, ge=1)
    judge_retries: int = Field(default=2, ge=0)
    early_stop: bool = False       # rounds 1-8 stopped early; decided once at a fixed sample since
    criteria: Criteria = Field(default_factory=Criteria)
    postmortem: PostMortem = Field(default_factory=PostMortem)
    hypotheses: str = ""
    note: str = ""

    @model_validator(mode="after")
    def known_rubric(self):
        from .rubrics import RUBRICS
        if self.rubric not in RUBRICS:
            raise ValueError(f"rubric {self.rubric!r} is not one of {sorted(RUBRICS)}")
        return self
