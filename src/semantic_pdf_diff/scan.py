"""Turn a source's roots (files, folders, zip archives) into files and content.

Zip archives are read in memory, never extracted to disk, and nested archives
are opened recursively. Safety limits are generous backstops against
pathological input; anything they stop is reported, never silently dropped.
"""
import hashlib
import io
import os
import zipfile
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from .provenance import normalized_extension

CLUTTER = {"__MACOSX", ".DS_Store", "Thumbs.db", "desktop.ini"}
ARCHIVES = {".zip"}

@dataclass(frozen=True)
class Limits:
    max_depth: int = 8                          # nested archive levels
    max_source_bytes: int = 50 * 1024 ** 3      # total uncompressed bytes read per source
    ratio_limit: float = 1000.0                 # compression ratio considered a bomb...
    ratio_min_bytes: int = 100 * 1024 ** 2      # ...but only for members at least this large

@dataclass
class ScannedFile:
    path: str            # display path within the source, archive members as 'a.zip!/b.pdf'
    content: str         # 'sha256:<hex><ext>', or 'sha256:<hex>' when not interpretable
    size: int
    origin: tuple        # (root, member, member, ...) to re-read the bytes later

@dataclass
class ScanResult:
    files: list = field(default_factory=list)
    issues: list = field(default_factory=list)   # (path, reason) for everything not scanned
    bytes_read: int = 0

def content_of(data, name):
    """Content ID; files without an extension get a bare hash and are never interpreted."""
    digest = "sha256:" + hashlib.sha256(data).hexdigest()
    extension = normalized_extension(name)
    return digest + extension if extension else digest

def hidden(parts):
    return any(p.startswith(".") or p in CLUTTER for p in parts)

def label(root):
    return Path(root).name or str(root)

def scan(roots, limits=Limits()):
    """Scan roots (absolute or relative paths) into files and content."""
    result = ScanResult()
    labels = {}
    for root in roots:
        root = Path(root)
        name = label(root)
        labels[name] = labels.get(name, 0) + 1
        prefix = name if labels[name] == 1 else f"{name}[{labels[name]}]"
        if root.is_dir():
            for directory, subdirs, names in os.walk(root):
                here = Path(directory).relative_to(root)
                # Hidden folders are reported once and never descended into.
                for name in sorted(subdirs):
                    if hidden([name]):
                        result.issues.append((f"{prefix}/{(here / name).as_posix()}", "hidden"))
                subdirs[:] = sorted(d for d in subdirs if not hidden([d]))
                for name in sorted(names):
                    relative = (here / name).as_posix()
                    if hidden([name]):
                        result.issues.append((f"{prefix}/{relative}", "hidden"))
                        continue
                    path = Path(directory) / name
                    _add(result, f"{prefix}/{relative}", path.read_bytes, (str(root), relative), limits, 0)
        elif root.is_file():
            _add(result, prefix, root.read_bytes, (str(root),), limits, 0)
        else:
            result.issues.append((str(root), "not found"))
    return result

def _add(result, display, read, origin, limits, depth):
    data = read()
    if result.bytes_read + len(data) > limits.max_source_bytes:
        result.issues.append((display, f"skipped: source exceeds {limits.max_source_bytes} bytes"))
        return
    result.bytes_read += len(data)
    result.files.append(ScannedFile(display, content_of(data, display), len(data), origin))
    if normalized_extension(display) in ARCHIVES:
        _archive(result, display, data, origin, limits, depth)

def _archive(result, display, data, origin, limits, depth):
    if depth >= limits.max_depth:
        result.issues.append((display, f"skipped: archive nested deeper than {limits.max_depth} levels"))
        return
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as e:
        result.issues.append((display, f"unreadable archive: {e}"))
        return
    for info in sorted(archive.infolist(), key=lambda i: i.filename):
        if info.is_dir():
            continue
        member = PurePosixPath(info.filename)
        if member.is_absolute() or ".." in member.parts or info.filename.startswith(("/", "\\")):
            result.issues.append((f"{display}!/{info.filename}", "rejected: unsafe path"))
            continue
        if hidden(member.parts):
            result.issues.append((f"{display}!/{info.filename}", "hidden"))
            continue
        if info.flag_bits & 0x1:
            result.issues.append((f"{display}!/{info.filename}", "skipped: encrypted"))
            continue
        if (info.file_size >= limits.ratio_min_bytes and info.compress_size
                and info.file_size / info.compress_size > limits.ratio_limit):
            result.issues.append((f"{display}!/{info.filename}", "skipped: compression ratio exceeds limit"))
            continue
        _add(result, f"{display}!/{member.as_posix()}", lambda info=info: archive.read(info),
             origin + (member.as_posix(),), limits, depth + 1)

def read_origin(origin):
    """Re-read a scanned file's bytes from its origin (root, then archive members)."""
    root, *rest = origin
    if rest and Path(root).is_dir():
        data = (Path(root) / rest[0]).read_bytes()
        rest = rest[1:]
    else:
        data = Path(root).read_bytes()
    for member in rest:
        data = zipfile.ZipFile(io.BytesIO(data)).read(member)
    return data

def stat_key(path):
    """(size, mtime_ns) for the fast path that skips rehashing unchanged files."""
    st = os.stat(path)
    return st.st_size, st.st_mtime_ns
