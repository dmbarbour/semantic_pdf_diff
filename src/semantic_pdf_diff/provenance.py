"""Content identity and interpreter descriptions.

Content is bytes plus the interpretation they are given, approximated by
SHA-256 of the bytes plus the normalized file extension. Evidence attaches to
content, never to paths.
"""
import hashlib
from importlib import metadata
from pathlib import PurePath
from . import __version__
from .models import Interpreter

# Only aliases known to share an interpretation collapse.
EXTENSION_ALIASES = {".jpeg": ".jpg", ".tif": ".tiff", ".htm": ".html", ".yml": ".yaml", ".markdown": ".md"}

# Settings that shape what extraction sends to the model or how content is chunked.
# Timeouts, retries, call limits, credentials and the endpoint URL are excluded.
EXTRACTION_SETTINGS = ("model", "context_tokens", "output_tokens", "text_bytes", "image_side", "tile_points",
                       "refinement_depth", "vision", "response_format", "temperature", "seed", "max_token_field")
COMPARISON_SETTINGS = ("model", "top_k", "min_score", "max_pairs", "verify_visuals", "aliases",
                       "response_format", "temperature", "seed", "output_tokens", "max_token_field")

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

def library_versions():
    versions = {"semantic-pdf-diff": __version__}
    for package in ("PyMuPDF", "pydantic"):
        try:
            versions[package] = metadata.version(package)
        except metadata.PackageNotFoundError:
            versions[package] = "unknown"
    return versions

def interpreter(role, settings, prompts, names):
    return Interpreter(role=role, model=settings.model, prompt_hash=text_hash(*prompts),
                       settings={name: getattr(settings, name) for name in names}, versions=library_versions())

def extraction_interpreter(settings):
    from .extract import EXTRACT
    from .llm import SYSTEM
    return interpreter("extract", settings, (SYSTEM, EXTRACT), EXTRACTION_SETTINGS)

def comparison_interpreter(settings):
    from .compare import COMPARE
    from .llm import SYSTEM
    return interpreter("compare", settings, (SYSTEM, COMPARE), COMPARISON_SETTINGS)
