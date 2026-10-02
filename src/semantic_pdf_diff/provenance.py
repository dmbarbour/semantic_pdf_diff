"""Content identity and interpreter descriptions.

Content is bytes plus the interpretation they are given, approximated by
SHA-256 of the bytes plus the normalized file extension. Evidence attaches to
content, never to paths.
"""
import hashlib
import os
from datetime import datetime, timezone
from importlib import metadata
from pathlib import PurePath
from . import __version__
from .levers import declared, lever_settings, role_settings
from .models import Interpreter, Settings

# Only aliases known to share an interpretation collapse.
EXTENSION_ALIASES = {".jpeg": ".jpg", ".tif": ".tiff", ".htm": ".html", ".yml": ".yaml", ".markdown": ".md"}

# The settings each role's stored results depend on (levers.Declared roles): what shapes what it sends to the
# model or how content is chunked. Timeouts, retries, call limits, credentials and the endpoint URL are excluded.
EXTRACTION_SETTINGS = role_settings(Settings, "extract")
TRIAGE_SETTINGS = role_settings(Settings, "triage")
COMPARISON_SETTINGS = role_settings(Settings, "compare")

def normalized_extension(name):
    """Lowercase extension with known aliases collapsed, or None if there is none."""
    suffix = PurePath(name).suffix.lower()
    if not suffix or suffix == ".":
        return None
    return EXTENSION_ALIASES.get(suffix, suffix)

def content_id(data, name):
    """'sha256:<hex>.<ext>' for bytes interpreted by their file extension."""
    extension = normalized_extension(name)
    if extension is None:
        raise ValueError(f"{name}: files without an extension are not interpreted")
    return "sha256:" + hashlib.sha256(data).hexdigest() + extension

def text_hash(*parts):
    return hashlib.sha256("\x00".join(parts).encode()).hexdigest()[:16]

def now():
    """The time outputs are stamped with: now, or SOURCE_DATE_EPOCH (seconds since 1970, UTC) when
    set, the reproducible-builds convention, so replays can form byte-identical reports."""
    fixed = os.environ.get("SOURCE_DATE_EPOCH", "").strip()
    return datetime.fromtimestamp(int(fixed), timezone.utc) if fixed else datetime.now(timezone.utc)

def library_versions():
    versions = {"semantic-pdf-diff": __version__}
    for package in ("PyMuPDF", "pydantic"):
        try:
            versions[package] = metadata.version(package)
        except metadata.PackageNotFoundError:
            versions[package] = "unknown"
    return versions

LEVERS = lever_settings()  # the settings levers own (levers.py)

def interpreter(role, settings, prompts, names):
    """A role's binding: every setting it depends on, resolved. Levers were once bound only when they differed
    from the defaults of the day, so a moved default went unnoticed and old evidence was served as current
    (code review 2026-10-01, item 4). Extraction binds its levers' order too. (Recorded answers don't depend on
    this: fixtures and caches are keyed by the query that reached the model.)"""
    values = {name: getattr(settings, name) for name in names}
    if role == "extract":  # the levers that act on extraction, in order (a comparison lever doesn't rebind it)
        cls = type(settings)
        values["levers"] = [lever.lever_name for lever in cls.lever_classes
                            if any(role in declared(cls, f).roles for f in lever.model_fields)]
    return Interpreter(role=role, model=settings.model, prompt_hash=text_hash(*prompts), settings=values,
                       versions=library_versions())

def extraction_interpreter(settings):
    from .extract import PROMPT_VERSION, extraction_template
    from .llm import SYSTEM
    return interpreter("extract", settings, (SYSTEM, extraction_template(settings), f"v{PROMPT_VERSION}"),
                       role_settings(type(settings), "extract"))

def triage_interpreter(settings):
    from .situate import PROMPT_VERSION, SITUATE_FIGURE, SITUATE_SECTION
    from .llm import SYSTEM
    return interpreter("triage", settings, (SYSTEM, SITUATE_FIGURE, SITUATE_SECTION, f"v{PROMPT_VERSION}"),
                       role_settings(type(settings), "triage"))

def comparison_interpreter(settings):
    from .compare import COMPARE, PROMPT_VERSION
    from .llm import SYSTEM
    return interpreter("compare", settings, (SYSTEM, COMPARE, f"v{PROMPT_VERSION}"), role_settings(type(settings), "compare"))
