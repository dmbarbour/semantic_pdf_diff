"""Controlled documents: generate the corpus, read it with the pipeline, and score extraction exactly
(lab/src/semantic_pdf_diff_lab/bench/controlled.py; docs/plans/controlled-documents-2026-10-01.md).

    python scripts/controlled.py generate                    # PDFs and answer keys into benchmarks/controlled/docs
    set -a; . ./.env; set +a
    python scripts/controlled.py run --max-cost 0.2          # extraction, recorded into a fixture (resumable)
    python scripts/controlled.py score                       # results.json from the runs' stores, offline
    python scripts/controlled.py run --replay                # read again from the packed fixture, offline
    python scripts/controlled.py run --unaligned             # the PDF pairs only, alignment off (see below)

The same seed gives the same PDFs, so the pipeline asks the same queries and recorded answers replay. Each document
is read alone (extraction, scored into results.json); each revision pair is then compared in revisions mode
(comparisons.json; revisions.py, comparison.py). The corpus is also written as Markdown (docs-md; representations.py),
read and compared the same way, its runs and pairs named "<id>.md"; and as Word documents (docs-docx), "<id>.docx".

With --unaligned the PDF pairs are compared again with alignment off (into "<recorded or replay>-unaligned"): every
retrieval candidate is judged, as before alignment, so most "different" findings aren't changes, and the
explanations (compare.explain) are measured where non-changes abound.
"""
import argparse
import contextlib
import io
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
FOLDER = ROOT / "benchmarks/controlled"
DOCS = FOLDER / "docs"
DOCS_MD = FOLDER / "docs-md"  # the same projects as Markdown (representations.py)
DOCS_DOCX = FOLDER / "docs-docx"  # and as Word documents
WORKING = FOLDER / "fixture.sqlite"   # recorded answers (git-ignored); packed into replay.zip
PACKED = FOLDER / "replay.zip"
RUNS = ROOT / "benchmarks/runs/controlled"
PAIR_RUNS = ROOT / "benchmarks/runs/controlled-pairs"
LEDGER = ROOT / "benchmarks/ledger.jsonl"
# The settings recordings share (scripts/record_runs.py): they shape the queries, so they decide what replays.
BASE_SETTINGS = {"claims_per_request": 20, "output_tokens": 4000, "context_tokens": 262144, "image_tokens": 300}

SETTINGS = FOLDER / "settings.json"  # every setting that shapes a query, resolved when first recorded (committed)

def settings_file():
    """The corpus's settings: written once, then kept, so replays ask exactly the recorded queries."""
    from semantic_pdf_diff.models import Settings
    if not SETTINGS.exists():
        SETTINGS.parent.mkdir(parents=True, exist_ok=True)
        SETTINGS.write_text(json.dumps(Settings.from_env(**BASE_SETTINGS).configuration(), indent=2) + "\n")
    return SETTINGS

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    gen = sub.add_parser("generate", help="write the corpus's PDFs and answer keys")
    gen.add_argument("--seed", type=int, action="append", help="default: 1")
    run = sub.add_parser("run", help="extract every document and compare every revision pair (recorded; answers "
                                     "already recorded are free)")
    run.add_argument("--replay", action="store_true", help="from the packed fixture, without calling a model")
    run.add_argument("--responder", help="default: the configured model")
    run.add_argument("--max-cost", type=float, default=0.2)
    run.add_argument("--unaligned", action="store_true", help="only the PDF pairs, compared with alignment off")
    sub.add_parser("score", help="score each run against its key, and each pair's comparison (offline)")
    args = parser.parse_args(argv)
    from semantic_pdf_diff_lab.bench import controlled
    from semantic_pdf_diff import fixtures
    if args.command == "generate":
        for project in controlled.corpus(tuple(args.seed or (1,)), knobs=True, revisions=True):
            print(f"{controlled.write(project, DOCS)}: {len(project.facts)} facts")
        from semantic_pdf_diff_lab.bench.controlled import representations
        for project, lines in representations.corpus(tuple(args.seed or (1,))):
            print(f"{representations.write(project, lines, DOCS_MD)}")
            print(f"{representations.write_docx(project, lines, DOCS_DOCX)}")
        return 0
    if args.command == "run":
        from semantic_pdf_diff import ledger, pipeline
        from semantic_pdf_diff.progress import setup_logging
        out = RUNS / ("replay" if args.replay else "recorded")
        if args.replay and not args.responder:  # the responder the fixture holds, whatever the environment says
            with fixtures.open(PACKED, "read") as f:
                held = [r for (r,) in f.db.execute("SELECT DISTINCT responder FROM response")]
            if len(held) != 1:
                parser.error(f"the fixture holds {held}: name one with --responder")
            args.responder = held[0]
        from semantic_pdf_diff_lab.bench.controlled import revisions
        config = settings_file()
        before = ledger.spent(LEDGER, round="controlled") if LEDGER.exists() else 0.0
        worst = 0
        setup_logging(quiet=True)
        # each document alone (the same PDF on both sides: extraction only), then each pair in revisions mode
        jobs = [(pdf, pdf, out / pdf.stem, pdf.stem, "proposals") for pdf in sorted(DOCS.glob("*.pdf"))]
        jobs += [(md, md, out / md.name, md.name, "proposals") for md in sorted(DOCS_MD.glob("*.md"))]
        jobs += [(d, d, out / d.name, d.name, "proposals") for d in sorted(DOCS_DOCX.glob("*.docx"))]
        jobs += [(DOCS / f"{p.earlier}.pdf", DOCS / f"{p.later}.pdf", PAIR_RUNS / out.name / p.id, f"pair {p.id}",
                  "revisions") for p in revisions.pairs()]
        for folder, suffix in ((DOCS_MD, ".md"), (DOCS_DOCX, ".docx")):
            jobs += [(folder / f"{p.earlier}{suffix}", folder / f"{p.later}{suffix}", PAIR_RUNS / out.name / f"{p.id}{suffix}",
                      f"pair {p.id}{suffix}", "revisions") for p in revisions.pairs()
                     if (folder / f"{p.earlier}{suffix}").exists() and (folder / f"{p.later}{suffix}").exists()]
        overrides = {}
        if args.unaligned:
            jobs = [(a, b, PAIR_RUNS / f"{out.name}-unaligned" / folder.name, name + " unaligned", mode)
                    for a, b, folder, name, mode in jobs if mode == "revisions" and a.suffix == ".pdf"]
            overrides = {"align": False}
        for a, b, folder, name, mode in jobs:
            options = pipeline.RunOptions(mode=mode, fixture=PACKED if args.replay else WORKING,
                                          fixture_mode="replay" if args.replay else "record-new", responder=args.responder)
            if args.replay:
                settings = pipeline.settings_from(config, situate=False, base_url=pipeline.NO_MODEL, **overrides)
            else:
                left = args.max_cost - (ledger.spent(LEDGER, round="controlled") - before)
                if left <= 0:
                    print(f"cap of ${args.max_cost} reached")
                    return 3
                settings = pipeline.settings_from(config, situate=False, max_cost=round(left, 4), **overrides)
                options.ledger, options.ledger_tags = LEDGER, {"round": "controlled", "run": name.replace(" ", "-")}
            code = pipeline.attempt(pipeline.compare_paths, a, b, folder, settings, options)
            print(f"{name}: exit {code}", flush=True)
            worst = max(worst, code)
        if not args.replay:
            fixtures.pack(WORKING, PACKED)
            print(f"packed {PACKED}; spent ${ledger.spent(LEDGER, round='controlled') - before:.3f}")
        return worst
    from semantic_pdf_diff_lab.eval import rounds
    results = {}
    for which in ("recorded", "replay"):
        runs = RUNS / which
        if not runs.exists():
            continue
        claims = {}
        for (run, _, page, family), unit in rounds.collect(runs).items():
            for c in unit["claims"].values():
                claims.setdefault(run, []).append({**c, "_family": family})
        for run, found in sorted(claims.items()):
            key = json.loads(key_path(run).read_text(encoding="utf-8"))
            result = controlled.score(key, found)
            readers = {f: controlled.score(key, [c for c in found if c["_family"] == f])
                       for f in sorted({c["_family"] for c in found})}
            result["by_reader"] = {f: r["recall"] for f, r in readers.items()}
            result["outcomes_by_reader"] = {f: r["outcomes"] for f, r in readers.items()}
            result["conditions_by_reader"] = {f: r["conditions_kept"] for f, r in readers.items()}
            results.setdefault(which, {})[run] = result
    (FOLDER / "results.json").write_text(json.dumps(results, indent=1) + "\n", encoding="utf-8")
    from semantic_pdf_diff_lab.bench.controlled import sheets
    knobbed = [(p, controlled.TABLE_KNOBS) for p in controlled.TABLE_PROJECTS] + \
              [(p, controlled.PROSE_KNOBS) for p in controlled.PROSE_PROJECTS] + \
              [(p, controlled.CHART_KNOBS) for p in controlled.CHART_PROJECTS] + \
              [(p, sheets.SHEET_KNOBS) for p in sheets.SHEET_PROJECTS]
    for which, runs in results.items():  # each knobbed project's knobs beside its clean version
        for project, knobs in knobbed:
            mine = {run[len(project) + 2:].partition("-")[2]: r for run, r in runs.items()
                    if run.startswith(project + "-s") and run[len(project) + 2:].partition("-")[0].isdigit()}
            if not mine:
                continue
            print(f"\n{which} {project}: knob      recall  right  loose  misbound  inexact  wrong unit  misread  hallucinated  claims"
                  "  conditions   misbound by reader; conditions kept by reader")
            for knob in knobs:
                r = mine.get(knob)
                if r:
                    o = r["outcomes"]
                    print(f"  {knob:12s} {r['recall']:7.3f} {r['found_right']:6d} {o.get('loose', 0):6d} "
                          f"{o.get('misbound', 0):9d} {o.get('inexact', 0):8d} {o.get('wrong unit', 0):11d} {o.get('misread', 0):8d} "
                          f"{o.get('hallucinated', 0):13d} {r['claims']:7d}"
                          f"  {r['conditions_kept']:>10s}   "
                          + " ".join(f"{f} {x.get('misbound', 0)}" for f, x in r["outcomes_by_reader"].items())
                          + ("; " + " ".join(f"{f} {k}" for f, k in r["conditions_by_reader"].items())
                             if r["conditions_kept"] != "0/0" else ""))
    from semantic_pdf_diff_lab.bench.controlled import schematics
    for which, runs in results.items():  # schematics: relations and numbers apart
        for project in schematics.SCHEMATIC_PROJECTS:
            mine = {run[len(project) + 2:].partition("-")[2]: r for run, r in runs.items()
                    if run.startswith(project + "-s") and run[len(project) + 2:].partition("-")[0].isdigit()}
            if not mine:
                continue
            print(f"\n{which} {project}: knob      relations found  numbers found   right  implied  reversed  wrong  "
                  "invented  unscored   number outcomes")
            for knob in schematics.SCHEMATIC_KNOBS:
                r = mine.get(knob)
                if r:
                    o, k = r["relations"], r["recall_by_kind"]
                    number = "-" if k["number"] is None else f"{k['number']:.3f}"
                    print(f"  {knob:12s} {k['relation']:15.3f} {number:>14s} {o.get('right', 0):7d} "
                          f"{o.get('implied', 0):8d} {o.get('reversed', 0):9d} {o.get('wrong', 0):6d} "
                          f"{o.get('invented', 0):9d} {o.get('unscored', 0):9d}   {r['outcomes']}")
    print()
    for which, runs in results.items():
        for run, r in runs.items():
            print(f"{which} {run}: recall {r['recall']} ({r['found']}/{r['facts']}, {r['found_right']} right) "
                  f"by form {r['recall_by_form']} by reader {r['by_reader']}; claims {r['claims']} {r['outcomes']}; "
                  f"conditions kept {r['conditions_kept']}")
    for which, runs in results.items():  # each Markdown and Word document beside its PDF
        for suffix, name in ((".md", "Markdown"), (".docx", "Word")):
            other = {run[:-len(suffix)]: r for run, r in runs.items() if run.endswith(suffix)}
            if not other:
                continue
            print(f"\n{which} {name} beside PDF: document                 facts  recall it / pdf   right it / pdf  "
                  "misbound it / pdf  hallucinated it / pdf")
            for doc, r in sorted(other.items()):
                pdf = runs.get(doc, {})
                o, po = r["outcomes"], pdf.get("outcomes", {})
                print(f"  {doc:38s} {r['facts']:5d}  {r['recall']:6.3f} / {pdf.get('recall', float('nan')):5.3f}  "
                      f"{r['found_right']:6d} / {pdf.get('found_right', 0):5d}  {o.get('misbound', 0):8d} / "
                      f"{po.get('misbound', 0):6d}  {o.get('hallucinated', 0):12d} / {po.get('hallucinated', 0):6d}")
    compared = compare_pairs()
    for which, pairs in compared.items():
        print(f"\n{which} revision pairs: pair                         changes  added  removed  unchanged  false  "
              "precision  findings")
        for pair, r in pairs.items():
            precision = "-" if r["difference_precision"] is None else f"{r['difference_precision']:.2f}"
            print(f"  {pair:30s} {r['changes_found']:>7s} {r['additions_found']:>6s} {r['removals_found']:>8s} "
                  f"{r['unchanged_confirmed']:>10s} {r['false_changes']:6d} {precision:>10s}  {r['findings']}")
            for kind in ("changed", "added", "removed", "unchanged"):
                print(f"      {kind}: {r[kind]}")
            print(f"      different: {r['different']}; equivalent: {r['equivalent']}; unmatched {r['unmatched']}; "
                  f"pairs {r['pairs']} (omitted {r['omitted']})")
            if "kinds" in r:
                k = r["kinds"]
                print(f"      kinds named right {k['right']}/{k['scored']}, value changes named precisely "
                      f"{k['value_change_precision']}: {k['by_claims']}")
    return 0

def key_path(run):
    """A run's key: a PDF's in docs, a Markdown's ("<id>.md") in docs-md, a Word document's ("<id>.docx") in
    docs-docx."""
    if run.endswith(".md"):
        return DOCS_MD / f"{run[:-3]}.key.json"
    if run.endswith(".docx"):
        return DOCS_DOCX / f"{run[:-5]}.key.json"
    return DOCS / f"{run}.key.json"

def compare_pairs():
    """comparisons.json: each revision pair's comparison scored against the two revisions' keys (PDF, and Markdown as
    "<id>.md")."""
    from semantic_pdf_diff_lab.bench.controlled import comparison, revisions
    compared = {}
    for which in ("recorded", "replay", "recorded-unaligned", "replay-unaligned"):
        for pair in revisions.pairs():
            for suffix in ("", ".md", ".docx"):
                report = PAIR_RUNS / which / f"{pair.id}{suffix}" / "report.json"
                if report.exists():
                    keys = [json.loads(key_path(d + suffix).read_text(encoding="utf-8")) for d in (pair.earlier, pair.later)]
                    compared.setdefault(which, {})[pair.id + suffix] = comparison.score_comparison(
                        *keys, json.loads(report.read_text(encoding="utf-8")))
    (FOLDER / "comparisons.json").write_text(json.dumps(compared, indent=1) + "\n", encoding="utf-8")
    return compared

if __name__ == "__main__":
    sys.exit(main())
