"""Settings: the endpoint's (how requests travel), beside the platform the levers compose (what a query says), and
how they're loaded from the environment, a file and a caller. Split from models (code review 2026-10-08, C4).
"""
import json
import logging
import os
from functools import lru_cache
from pathlib import Path
from typing import Annotated
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
        """The user's settings (`pdf-semantic-diff config set --user`: user_settings), $OPENAI_BASE_URL, then explicit
        overrides (a store's own settings, a --config file, a run's flags, a caller's). `only`: the fields read from
        the user's settings and the environment (default all).

        The environment is read for the endpoint alone (docs/plans/configuration-in-the-store-2026-10-20.md: the
        owner's four variables); a PDF_DIFF_<NAME> or OPENAI_MODEL still set is ignored, with a warning naming the
        setting that replaces it. Plain Settings() stays deterministic for library callers and fixtures."""
        levers = overrides.pop("levers", None)
        user = user_settings()
        if levers is None and "levers" in user and (only is None or "levers" in only):
            levers = user["levers"]
        target = cls if levers is None else settings_class(tuple(levers))
        retired(target)
        # An explicit legacy json_mode must beat the user's response_format.
        explicit = set(overrides) | ({"response_format"} if "json_mode" in overrides else set())
        values = {k: v for k, v in user.items()
                  if k in target.model_fields and k not in explicit and (only is None or k in only)}
        raw = os.environ.get("OPENAI_BASE_URL", "")
        if raw.strip() and "base_url" not in overrides and (only is None or "base_url" in only):
            values["base_url"] = raw.strip()
        values.update(overrides)
        return target(**values)

def user_path():
    """The user's settings (`config set --user`): $XDG_CONFIG_HOME/semantic-pdf-diff/settings.json, else under
    ~/.config: what belongs to the user's endpoint and machine (the model and its context, concurrency, a reranker),
    shared by every store."""
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.join(os.path.expanduser("~"), ".config")
    return Path(base) / "semantic-pdf-diff" / "settings.json"

def user_settings():
    """The user's settings, {name: value}; none without the file."""
    path = user_path()
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as e:
        raise ValueError(f"{path}: not JSON ({e}); `pdf-semantic-diff config export --user` shows the format") from e
    if not isinstance(data, dict) or not isinstance(data.get("settings"), dict):
        raise ValueError(f'{path}: expected {{"format": 1, "settings": {{...}}}}')
    return dict(data["settings"])

def save_user_settings(values):
    """The user's settings replaced (checked by the caller: configuration.applied)."""
    path = user_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"format": 1, "settings": values}, indent=1, sort_keys=True, ensure_ascii=False) + "\n",
                    encoding="utf-8")

_warned = set()

def retired(target):
    """Warn, once a process, of each environment variable that named a setting before the user's settings did."""
    for field in target.model_fields:
        name = "OPENAI_MODEL" if field == "model" else "PDF_DIFF_" + field.upper()
        if field != "base_url" and (os.environ.get(name) or "").strip() and name not in _warned:
            _warned.add(name)
            logging.getLogger("semantic_pdf_diff").warning(
                "%s is no longer read: `pdf-semantic-diff config set --user %s VALUE` keeps it for every run "
                "(docs/configuration.md)", name, field)

@lru_cache(maxsize=None)
def settings_class(levers=DEFAULT_LEVERS):
    """The settings for an ordered list of levers: endpoint settings beside the composed platform."""
    return type("Settings", (SettingsBase, Endpoint, compose(levers)), {"__module__": __name__})

Settings = settings_class()

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
