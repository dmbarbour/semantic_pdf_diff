"""Cut page slices from fetched samples, for recording and replaying model answers.

Replay fixtures identify content by its bytes, so slices must come out byte-identical
wherever they're made. Cutting is deterministic for a given PyMuPDF version (pinned in
slices.json); with another version the bytes may differ, and the script says so. Slices
are written to samples/slices/ (git-ignored, like the samples themselves).

    python scripts/fetch_samples.py --set wind-reference-turbines --set solar-decathlon-2013
    python scripts/make_slices.py
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = Path(__file__).with_name("slices.json")

def sha256(data):
    return hashlib.sha256(data).hexdigest()

def cut(source, first, last):
    """Pages first..last (1-based) with their outline: the entries in force at the first page
    (so a slice starting mid-section keeps its headings), then those inside. Bytes are deterministic."""
    with pymupdf.open(source) as doc:
        part = pymupdf.open()
        part.insert_pdf(doc, from_page=first - 1, to_page=last - 1, links=False, annots=False)
        entries = [(level, title, page) for level, title, page, *_ in doc.get_toc(simple=False)]
        in_force = {}
        for level, title, page in entries:
            if page < first:
                in_force = {k: v for k, v in in_force.items() if k < level}
                in_force[level] = title
        toc = [[level, title, 1] for level, title in sorted(in_force.items())]
        toc += [[level, title, page - first + 1] for level, title, page in entries if first <= page <= last]
    if toc:
        base, fixed, previous = min(level for level, _, _ in toc), [], 0
        for level, title, page in toc:
            level = min(level - base + 1, previous + 1)
            fixed.append([level, title, page])
            previous = level
        part.set_toc(fixed)
    part.set_metadata({})
    data = part.tobytes(garbage=3, deflate=True, no_new_id=True)
    part.close()
    return data

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--samples", type=Path, default=ROOT / "samples")
    parser.add_argument("--record-hashes", action="store_true", help="maintainers: pin the slices' hashes")
    args = parser.parse_args(argv)
    manifest = json.loads(MANIFEST.read_text())
    out = args.samples / "slices"
    out.mkdir(parents=True, exist_ok=True)
    problems = 0
    for entry in manifest["slices"]:
        source = args.samples / entry["source"]
        if not source.exists():
            print(f"{entry['name']}: missing {source}; run scripts/fetch_samples.py first", file=sys.stderr)
            problems += 1
            continue
        if sha256(source.read_bytes()) != entry["source_sha256"]:
            print(f"{entry['name']}: {source} doesn't match its pinned hash", file=sys.stderr)
            problems += 1
            continue
        data = cut(source, *entry["pages"])
        digest = sha256(data)
        if args.record_hashes:
            entry["sha256"] = digest
        elif digest != entry.get("sha256"):
            print(f"{entry['name']}: slice bytes differ from the pinned hash (PyMuPDF {pymupdf.VersionBind}; "
                  f"slices were pinned with {manifest['pymupdf']}); replay fixtures won't match", file=sys.stderr)
            problems += 1
            continue
        (out / f"{entry['name']}.pdf").write_bytes(data)
        print(f"{entry['name']}.pdf: pages {entry['pages'][0]}-{entry['pages'][1]}")
    if args.record_hashes:
        manifest["pymupdf"] = pymupdf.VersionBind
        MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n")
    return 1 if problems else 0

if __name__ == "__main__":
    sys.exit(main())
