#!/usr/bin/env python3
"""Download public sample documents and verify them against pinned SHA-256 hashes.

The samples are freely available documents that resemble the tool's intended
inputs (competing proposals, revisions of one design). They are not committed;
this script recreates them. See scripts/samples.json for sources and terms.

    python scripts/fetch_samples.py --list
    python scripts/fetch_samples.py                  # default sets
    python scripts/fetch_samples.py --set ietf-quic-transport
    python scripts/fetch_samples.py --all --make-zips

Every file must match its recorded hash; mismatches are rejected and the next
URL is tried. TLS certificates are always verified. Standard library only.
"""
import argparse
import hashlib
import json
import shutil
import sys
import tempfile
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

MANIFEST = Path(__file__).with_name("samples.json")
DEFAULT_DEST = Path(__file__).resolve().parent.parent / "samples"
USER_AGENT = "semantic-pdf-diff-sample-fetcher/1 (research test corpus)"
CHUNK = 1 << 20
# Fixed timestamp keeps generated zips byte-identical across runs.
ZIP_DATE = (1980, 1, 1, 0, 0, 0)

def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(CHUNK), b""):
            digest.update(block)
    return digest.hexdigest()

def download(url, target, timeout, attempts=4):
    """Stream url into target; returns (sha256, bytes). Retries transient failures."""
    for attempt in range(attempts):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            digest, size = hashlib.sha256(), 0
            with urllib.request.urlopen(request, timeout=timeout) as response, open(target, "wb") as out:
                for block in iter(lambda: response.read(CHUNK), b""):
                    digest.update(block)
                    size += len(block)
                    out.write(block)
            return digest.hexdigest(), size
        except urllib.error.HTTPError as e:
            if e.code not in (408, 429, 500, 502, 503, 504) or attempt == attempts - 1:
                raise
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            if attempt == attempts - 1:
                raise
        time.sleep(5 * 2 ** attempt)  # the Internet Archive throttles bursts

def fetch(entry, target, timeout, record):
    """Ensure target holds the entry's verified bytes. Returns a status string."""
    expected = entry.get("sha256")
    if target.exists() and expected and sha256(target) == expected:
        return "ok (cached)"
    if not expected and not record:
        raise RuntimeError("no pinned sha256 in manifest; run with --record-hashes to pin it")
    target.parent.mkdir(parents=True, exist_ok=True)
    errors = []
    for url in entry["urls"]:
        with tempfile.NamedTemporaryFile(dir=target.parent, prefix=".part-", delete=False) as tmp:
            part = Path(tmp.name)
        try:
            digest, size = download(url, part, timeout)
            if expected and digest != expected:
                errors.append(f"{url}: sha256 mismatch ({digest})")
                continue
            part.replace(target)
            if not expected:
                entry["sha256"], entry["bytes"] = digest, size
                return f"recorded {digest[:12]}… ({size:,} bytes)"
            return f"ok ({size:,} bytes)"
        except (OSError, urllib.error.URLError) as e:
            errors.append(f"{url}: {e}")
        finally:
            part.unlink(missing_ok=True)
    raise RuntimeError("; ".join(errors))

def make_zip(folder, archive):
    """Pack folder deterministically (sorted names, fixed timestamps)."""
    archive.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as z:
        for path in sorted(p for p in folder.rglob("*") if p.is_file()):
            info = zipfile.ZipInfo(f"{folder.name}/{path.relative_to(folder).as_posix()}", ZIP_DATE)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            with open(path, "rb") as src, z.open(info, "w") as dst:
                shutil.copyfileobj(src, dst, CHUNK)

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--set", action="append", dest="sets", metavar="NAME", help="sample set to fetch (repeatable)")
    parser.add_argument("--all", action="store_true", help="fetch every set, including large optional ones")
    parser.add_argument("--list", action="store_true", help="describe the sets and exit")
    parser.add_argument("--dest", type=Path, default=DEFAULT_DEST, help="output folder (default: samples/)")
    parser.add_argument("--make-zips", action="store_true", help="also pack each project folder listed in zip_projects into <set>/zips/")
    parser.add_argument("--timeout", type=float, default=120)
    parser.add_argument("--record-hashes", action="store_true", help="maintainers: pin hashes for entries that lack one")
    args = parser.parse_args(argv)

    manifest = json.loads(MANIFEST.read_text())
    sets = manifest["sets"]
    if args.list:
        for name, spec in sets.items():
            size = sum(f.get("bytes", 0) for f in spec["files"])
            print(f"{name}{' (default)' if spec.get('default') else ''}: {len(spec['files'])} files, {size / 1e6:.0f} MB")
            print(f"  {spec['use']}\n  Terms: {spec['terms']}\n")
        return 0
    unknown = set(args.sets or ()) - set(sets)
    if unknown:
        parser.error(f"unknown set(s): {', '.join(sorted(unknown))}; see --list")
    chosen = list(sets) if args.all else args.sets or [n for n, s in sets.items() if s.get("default")]

    failures, recorded = 0, False
    for name in chosen:
        spec = sets[name]
        print(f"== {name}")
        failed = []
        for entry in spec["files"]:
            target = args.dest / name / entry["path"]
            try:
                status = fetch(entry, target, args.timeout, args.record_hashes)
                recorded |= status.startswith("recorded")
                print(f"  {entry['path']}: {status}")
            except RuntimeError as e:
                failures += 1
                failed.append(entry["path"])
                print(f"  {entry['path']}: FAILED: {e}", file=sys.stderr)
        if args.make_zips:
            for project in spec.get("zip_projects", []):
                folder = args.dest / name / project
                if any(path.startswith(project + "/") for path in failed):
                    print(f"  zips/{folder.name}.zip: skipped (incomplete folder)")
                elif folder.is_dir():
                    make_zip(folder, args.dest / name / "zips" / (folder.name + ".zip"))
                    print(f"  zips/{folder.name}.zip: created")
    if recorded:
        MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n")
        print(f"Pinned new hashes in {MANIFEST}")
    if failures:
        print(f"{failures} file(s) failed", file=sys.stderr)
    return 1 if failures else 0

if __name__ == "__main__":
    sys.exit(main())
