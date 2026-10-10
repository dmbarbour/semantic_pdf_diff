"""Settings: the endpoint's (how requests travel), beside the platform the levers compose (what a query says), and
how they're loaded from the environment, a file and a caller. Split from models (code review 2026-10-08, C4).
"""
import json
import os
from functools import lru_cache
from typing import Annotated, get_args, get_origin
from pydantic import Field, model_validator
from .levers import DEFAULT_LEVERS, EVERY_ROLE, Declared, compose, lever_marks, setting_classes
from .schema import Strict

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
    def from_env(cls, only=None, **overrides):
        """Load environment defaults, then explicit file/CLI/programmatic overrides.

        Keep plain Settings() deterministic for library callers and fixtures.
        Empty environment values are treated as unset. `only`: the fields read from the environment (default all).
        """
        levers = overrides.pop("levers", None)
        target = cls if levers is None else settings_class(tuple(levers))
        values = {}
        names = {"base_url": "OPENAI_BASE_URL", "model": "OPENAI_MODEL"}
        # An explicit legacy json_mode must beat an environment response_format.
        explicit = set(overrides) | ({"response_format"} if "json_mode" in overrides else set())
        for field in [*target.model_fields, "json_mode"]:
            if field in explicit or (only is not None and field not in only):
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
            elif raw.strip().casefold() in ("none", "null") and field in target.model_fields \
                    and type(None) in get_args(target.model_fields[field].annotation):
                values[field] = None  # an optional setting switched off (code review 2026-10-08, C23: table_rules)
            else:
                values[field] = raw.strip()
        values.update(overrides)
        return target(**values)

@lru_cache(maxsize=None)
def settings_class(levers=DEFAULT_LEVERS):
    """The settings for an ordered list of levers: endpoint settings beside the composed platform."""
    return type("Settings", (SettingsBase, Endpoint, compose(levers)), {"__module__": __name__})

Settings = settings_class()

# What every evaluating model (judges, query checkers, the post-mortem's analyst) is asked with.
# Its answers are recorded by query, so these must be the same wherever a folder is judged; the
# transport (concurrency, timeouts, retries, caps) varies by caller and never changes a query.
EVALUATOR_SETTINGS = {"context_tokens": 262144, "output_tokens": 16000, "image_tokens": 3000}

# Each setting's class (levers.Declared), read off the declarations.
SETTING_CLASSES = setting_classes(Settings)

# What each lever added to a query, found by the lines its builder writes (the levers' marks). For
# diagnostics only (the queries dump, docs/plans/content-addressed-queries-2026-09-28.md): a query is found by
# its hash, never by these. Moved from context, which never used them (code review 2026-10-08, C4).
# tests/test_sections.py checks each builder against its mark.
LEVER_MARKS = lever_marks(Settings)

def lever_notes(prompt):
    """{lever: what it added (shortened)} for the levers whose lines a query's text holds."""
    notes = {}
    for lever, mark in LEVER_MARKS:
        found = [m.group(1).strip() for m in mark.finditer(prompt)]
        if found:
            joined = " | ".join(found)
            notes[lever] = joined if len(joined) <= 240 else joined[:237] + "..."
    return notes
