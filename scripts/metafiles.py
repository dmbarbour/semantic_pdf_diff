"""Pictures drawn as metafiles, rendered for inspection (docs/plans/multi-format-adapters-2026-09-23.md, "Pictures in
Word documents"): every distinct EMF and WMF in the sample Word documents, drawn into a page by metafiles.draw, each
saved as a PNG with what was drawn and what wasn't, and a summary of them all.

    python scripts/metafiles.py render                      # into benchmarks/metafiles (git-ignored)
    python scripts/metafiles.py render --only 38300-j30 --reference DIR
        # --reference: a folder of other renders named like the pictures' media ("image100.emf.png"), each placed
        # beside ours in "<name>.side.png" for comparison by eye

The samples are public (scripts/fetch_samples.py) and stay in samples/; only findings are committed.
"""
import argparse
import hashlib
import io
import json
import sys
import zipfile
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
SAMPLES = ROOT / "samples"
OUT = ROOT / "benchmarks/metafiles"
DPI = 150  # the PNGs' resolution

def documents():
    """(name, the Word document's bytes) for each .docx in samples/, inside zips too."""
    def members(name, data):
        if name.endswith(".docx"):
            yield Path(name).stem, data
        elif name.endswith(".zip"):
            try:
                archive = zipfile.ZipFile(io.BytesIO(data))
            except zipfile.BadZipFile:
                return
            for member in archive.namelist():
                if member.endswith((".docx", ".zip")) and not member.startswith("__MACOSX"):
                    yield from members(member, archive.read(member))
    for path in sorted(SAMPLES.rglob("*")):
        if path.suffix in (".docx", ".zip"):
            yield from members(path.name, path.read_bytes())

def pictures(only=None):
    """(document, media name, bytes) for each distinct metafile, first sighting kept."""
    seen = set()
    for doc, data in documents():
        if only and only not in doc:
            continue
        try:
            archive = zipfile.ZipFile(io.BytesIO(data))
        except zipfile.BadZipFile:
            continue
        for name in sorted(archive.namelist()):
            if name.startswith("word/media/") and name.lower().endswith((".emf", ".wmf")):
                blob = archive.read(name)
                digest = hashlib.sha256(blob).hexdigest()
                if digest not in seen:
                    seen.add(digest)
                    yield doc, name.rsplit("/", 1)[1], blob

def side_by_side(ours, reference, out):
    import pymupdf
    a, b = pymupdf.open(ours), pymupdf.open(reference)
    width = 1200
    ha = a[0].rect.height * (width / 2) / a[0].rect.width
    hb = b[0].rect.height * (width / 2) / b[0].rect.width
    sheet = pymupdf.open()
    page = sheet.new_page(width=width, height=max(ha, hb))
    page.show_pdf_page(pymupdf.Rect(0, 0, width / 2, ha), pymupdf.open("pdf", a.convert_to_pdf()), 0)
    page.show_pdf_page(pymupdf.Rect(width / 2, 0, width, hb), pymupdf.open("pdf", b.convert_to_pdf()), 0)
    page.get_pixmap(dpi=72).save(out)

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    render = sub.add_parser("render", help="draw every distinct metafile in the samples' Word documents")
    render.add_argument("--only", help="documents whose name contains this")
    render.add_argument("--reference", type=Path, help="a folder of other renders to place beside ours")
    args = parser.parse_args(argv)
    import pymupdf
    from semantic_pdf_diff.metafiles import draw
    results, skipped, failed = [], Counter(), Counter()
    for doc, name, blob in pictures(args.only):
        folder = OUT / doc
        folder.mkdir(parents=True, exist_ok=True)
        entry = {"document": doc, "media": name, "bytes": len(blob)}
        try:
            picture = draw(blob)
        except Exception as e:  # noqa: BLE001 (every failure is a finding)
            entry["error"] = f"{type(e).__name__}: {e}"
            failed[type(e).__name__] += 1
            results.append(entry)
            continue
        page = pymupdf.open("pdf", picture.pdf)[0]
        png = folder / f"{name}.png"
        page.get_pixmap(dpi=DPI).save(png)
        entry.update(format=picture.source_format, emfplus=picture.emfplus_mode,
                     size=[round(picture.width, 1), round(picture.height, 1)], drawn=dict(picture.drawn),
                     skipped=dict(picture.skipped), words=len(page.get_text("words")),
                     diagnostics=list(picture.diagnostics)[:5])
        skipped.update({k: 1 for k in picture.skipped})
        if args.reference and (args.reference / f"{name}.png").exists():
            side_by_side(png, args.reference / f"{name}.png", folder / f"{name}.side.png")
        results.append(entry)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "summary.json").write_text(json.dumps(results, indent=1) + "\n")
    drawn = [r for r in results if "error" not in r]
    print(f"{len(results)} metafiles: {len(drawn)} drawn, {len(results) - len(drawn)} failed {dict(failed)}")
    print(f"  with text: {sum(1 for r in drawn if r['words'])}; words in all: {sum(r['words'] for r in drawn)}")
    print("  pictures with something not drawn as recorded:")
    for reason, n in skipped.most_common():
        print(f"    {n:4d}  {reason}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
