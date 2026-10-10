"""Source manifests: a serialization of a source definition.

Manifests carry a source between users or stores, or capture variations to
experiment with. Users don't maintain them by hand: `source export` writes one
and `source import` (or `--manifest`) reads one. Roots are stored relative to the
manifest's folder where possible, so a manifest travels with its files.
"""
import hashlib
import json
import os
from pathlib import Path
from .schema import Source

FORMAT = "semantic-pdf-diff-source"
VERSION = 1

def export(source, files=(), location=None):
    """Manifest JSON text for a source. files: FileRefs to include as content hashes."""
    base = Path(location).resolve().parent if location else Path.cwd()
    def portable(root):
        try:
            return os.path.relpath(Path(root).resolve(), base)
        except ValueError:  # different drive on Windows
            return str(Path(root).resolve())
    data = {"format": FORMAT, "version": VERSION, "name": source.name, "metadata": source.metadata,
            "roots": [portable(r) for r in source.roots]}
    if files:
        data["files"] = [{"path": f.path, "content": f.content} for f in files]
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"

def load(path, name=None, kind="declared"):
    """Read a manifest file: returns (Source, expected {path: content}, sha256 of the file)."""
    path = Path(path)
    raw = path.read_bytes()
    try:
        data = json.loads(raw)
    except ValueError as e:
        raise ValueError(f"{path}: not a JSON manifest ({e})") from e
    if not isinstance(data, dict) or data.get("format") != FORMAT:
        raise ValueError(f"{path}: not a {FORMAT} manifest")
    if data.get("version") != VERSION:
        raise ValueError(f"{path}: manifest version {data.get('version')} is not supported (expected {VERSION})")
    base = path.resolve().parent
    roots = [str((base / r).resolve()) if not Path(r).is_absolute() else r for r in data.get("roots", [])]
    source = Source(name=name or data["name"], kind=kind, metadata=data.get("metadata", {}), roots=roots,
                    manifest=str(path.resolve()) if kind == "manifest" else None)
    expected = {f["path"]: f["content"] for f in data.get("files", [])}
    return source, expected, hashlib.sha256(raw).hexdigest()

def mismatches(expected, files):
    """Paths whose content differs from, or is missing relative to, a manifest's hashes."""
    actual = {f.path: f.content for f in files}
    return sorted(p for p, c in expected.items() if actual.get(p) != c)
