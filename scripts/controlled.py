"""Controlled documents: generate the corpus, read it with the pipeline, and score extraction exactly
(lab/src/semantic_pdf_diff_lab/bench/controlled.py; docs/plans/controlled-documents-2026-10-01.md).

    python scripts/controlled.py generate                    # PDFs and answer keys into benchmarks/controlled/docs
    set -a; . ./.env; set +a
    python scripts/controlled.py run --max-cost 0.2          # extraction, recorded into a fixture (resumable)
    python scripts/controlled.py score                       # results.json from the runs' stores, offline
    python scripts/controlled.py run --replay                # read again from the packed fixture, offline
    python scripts/controlled.py run --unaligned             # the PDF pairs only, alignment off (see below)
    python scripts/controlled.py run --rows                  # every document's tables read row by row (below)
    python scripts/controlled.py pack                        # replay.zip: the answers the standard runs replay
    python scripts/controlled.py context                     # context.json: each claim's context, offline (below)
    python scripts/controlled.py refresh --jobs 6 --max-cost 2   # all of it after a change, six runs at once
    python scripts/controlled.py run --variant b62.json --jobs 6     # a named variant, into the archive (below)

The same seed gives the same PDFs, so the pipeline asks the same queries and recorded answers replay. Each document
is read alone (extraction, scored into results.json); each revision pair is then compared in revisions mode
(comparisons.json; revisions.py, comparison.py). The corpus is also written as Markdown (docs-md; representations.py),
read and compared the same way, its runs and pairs named "<id>.md"; as Word documents (docs-docx), "<id>.docx"; as
slide decks (docs-pptx), "<id>.pptx"; and as workbooks (docs-xlsx), "<id>.xlsx".

With --unaligned the PDF pairs are compared again with alignment off (into "<recorded or replay>-unaligned"): every
retrieval candidate is judged, as before alignment, so most "different" findings aren't changes, and the
explanations (compare.explain) are measured where non-changes abound.

With --rows every document and pair is read again with every table read row by row (table_rules none), into
"<recorded or replay>-rows": the baseline the standard runs' tables, each read as a model says (tablerules.py), are
scored against by the same keys. Packed with the standard runs.

`context` measures the standard runs' claims' context (lab bench/context.py; docs/plans/claim-context-2026-10-14.md,
milestone 2): misplaced context and conditions grounded in what each request showed, then, against the keys' context
by kind, where each kind landed and, where it was lost, whether the request showed it; and the reader's confidence
against the keys, band by band. Into context.json.

A variant (--variant FILE) is a lever's arm: its settings over the corpus's, on the documents it names, its runs under
benchmarks/runs/controlled/variants/<name> (scripts/paired.py names it), its answers recorded into the archive and
replayed from it. From a frozen worktree (to pin the code), the archive, the ledger and the variants are the main
checkout's.

Recording adds to the working fixture (fixture.sqlite, git-ignored), an archive keeping every answer ever recorded,
every variant's. `pack` exports the committed replay.zip from it: the standard runs replay from fresh stores, reading
the archive, and every answer they're served is copied into a new fixture, which is packed (the --unaligned runs'
answers, other variants' and superseded ones stay in the archive). Nothing is pruned.
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
DOCS_PPTX = FOLDER / "docs-pptx"  # and as slide decks
DOCS_XLSX = FOLDER / "docs-xlsx"  # and as workbooks
# The representations' documents by suffix, in the order they're read and compared (code review 2026-10-08, E4).
REPRESENTATIONS = {".md": DOCS_MD, ".docx": DOCS_DOCX, ".pptx": DOCS_PPTX, ".xlsx": DOCS_XLSX}
from semantic_pdf_diff_lab.bench import recording  # noqa: E402
MAIN = recording.main_checkout(ROOT)  # from a frozen worktree, the main checkout: its archive, ledger and variants
WORKING = MAIN / "benchmarks/controlled/fixture.sqlite"  # the archive of recorded answers (git-ignored)
PACKED = FOLDER / "replay.zip"
RUNS = ROOT / "benchmarks/runs/controlled"
PAIR_RUNS = ROOT / "benchmarks/runs/controlled-pairs"
VARIANTS = MAIN / "benchmarks/runs/controlled/variants"  # a named variant's runs, then its pairs'
VARIANT_PAIRS = MAIN / "benchmarks/runs/controlled-pairs/variants"
LEDGER = recording.ledger(ROOT)
BASE_SETTINGS = recording.BASE_SETTINGS  # the settings recordings share: they shape the queries

SETTINGS = FOLDER / "settings.json"  # every setting that shapes a query, resolved when first recorded (committed)

def settings_file():
    """The corpus's settings: written once, then kept, so replays ask exactly the recorded queries."""
    from semantic_pdf_diff.settings import Settings
    if not SETTINGS.exists():
        SETTINGS.parent.mkdir(parents=True, exist_ok=True)
        SETTINGS.write_text(json.dumps(Settings.from_env(**BASE_SETTINGS).configuration(), indent=2) + "\n")
    return SETTINGS

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    gen = sub.add_parser("generate", help="write the corpus's PDFs and answer keys")
    gen.add_argument("--seed", type=int, action="append", help="default: 1")
    running = sub.add_parser("run", help="extract every document and compare every revision pair (recorded; "
                                         "answers already recorded are free)")
    running.add_argument("--replay", action="store_true", help="from the packed fixture, without calling a model")
    running.add_argument("--responder", help="default: the configured model")
    running.add_argument("--max-cost", type=float, default=0.2)
    running.add_argument("--unaligned", action="store_true", help="only the PDF pairs, compared with alignment off")
    running.add_argument("--rows", action="store_true", help="every document, its tables read row by row")
    running.add_argument("--variant", type=Path, metavar="FILE",
                         help='a named variant (JSON: {"settings": {...}, "only": ["*.pdf", "views*"], "name": ...}): '
                              "its settings over the corpus's, only the documents named, its runs under "
                              "benchmarks/runs/controlled/variants/<name>, its answers in the archive (replayed from "
                              "the archive too)")
    refreshing = sub.add_parser("refresh", help="the corpus after a change: record the standard and row-by-row runs, "
                                             "export replay.zip, replay both, score, measure context")
    refreshing.add_argument("--max-cost", type=float, default=0.2, help="for each of the two recordings")
    packing = sub.add_parser("pack", help="export the answers the standard runs replay into replay.zip (offline)")
    for each in (running, refreshing, packing):
        each.add_argument("--jobs", type=int, default=1, help="runs at once, in processes sharing the fixture")
    running.add_argument("--reset", action="store_true",
                         help="a store bound to other settings clears what changed and reads it again (refresh "
                              "always does)")
    sub.add_parser("score", help="score each run against its key, and each pair's comparison (offline)")
    sub.add_parser("context", help="measure the standard runs' claims' context against the keys (offline)")
    args = parser.parse_args(argv)
    from semantic_pdf_diff_lab.bench import controlled
    if args.command == "generate":
        for project in controlled.corpus(tuple(args.seed or (1,)), knobs=True, revisions=True):
            print(f"{controlled.write(project, DOCS)}: {len(project.facts)} facts")
        from semantic_pdf_diff_lab.bench.controlled import representations, slides, workbooks
        for project, lines in representations.corpus(tuple(args.seed or (1,))):
            print(f"{representations.write(project, lines, DOCS_MD)}")
            print(f"{representations.write_docx(project, lines, DOCS_DOCX)}")
            print(f"{slides.write(DOCS_PPTX, project, slides.deck(project))}")
            print(f"{workbooks.write(DOCS_XLSX, project, workbooks.workbook(project))}")
        for seed in args.seed or (1,):
            for project, data in slides.documents(seed):  # the decks' own difficulties (slides.py)
                print(slides.write(DOCS_PPTX, project, data))
        from semantic_pdf_diff_lab.bench.controlled import word
        for seed in args.seed or (1,):
            for path in word.write(DOCS_DOCX, seed):  # Word's own difficulties (word.py)
                print(path)
        return 0
    if args.command == "run":
        if args.unaligned and args.rows:
            parser.error("--unaligned and --rows are separate runs")
        if args.variant:
            name, config, only = variant(args.variant)
            return run(args.replay, args.responder, args.max_cost, args.unaligned, parser.error, rows=args.rows,
                       jobs=args.jobs, reset=args.reset, fixture=WORKING, runs=VARIANTS / name,
                       pair_runs=VARIANT_PAIRS / name, config=config, only=only)
        return run(args.replay, args.responder, args.max_cost, args.unaligned, parser.error, rows=args.rows,
                   jobs=args.jobs, reset=args.reset)
    if args.command == "pack":
        return pack(args.jobs)
    if args.command == "refresh":
        return refresh(args.max_cost, args.jobs)
    if args.command == "context":
        return context()
    return score()

def variant(path):
    """(name, settings file, document patterns) of a variant defined in a JSON file: {"settings": an overlay on the
    corpus's settings, "only": shell patterns of the documents' file names (default: every document; a pair by its
    earlier document), "name": its folder's (default: the file's stem)}. Its resolved settings and its definition are
    written beside its runs, so a later run of the same name with other settings is refused by the stores (or reset)."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    unknown = set(data) - {"settings", "only", "name", "note"}
    if unknown:
        raise SystemExit(f"{path}: unknown keys {sorted(unknown)} (settings, only, name, note)")
    name = data.get("name") or Path(path).stem
    folder = VARIANTS / name
    folder.mkdir(parents=True, exist_ok=True)
    settings = {**json.loads(settings_file().read_text(encoding="utf-8")), **data.get("settings", {})}
    (folder / "settings.json").write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")
    (folder / "variant.json").write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return name, folder / "settings.json", tuple(data.get("only") or ())

def refresh(max_cost, jobs=1):
    """Every step after a change, in order, stores reset where settings moved: the standard and row-by-row runs
    recorded, replay.zip exported, both replayed from it, scored, context measured. Exit status 1 when a run failed
    or a step did, 3 when a recording reached its cap (rerun to resume); incomplete coverage (2) isn't a failure."""
    steps = [("record", lambda: run(False, None, max_cost, False, jobs=jobs, reset=True)),
             ("record rows", lambda: run(False, None, max_cost, False, rows=True, jobs=jobs, reset=True)),
             ("pack", lambda: pack(jobs)),
             ("replay", lambda: run(True, None, 0, False, jobs=jobs, reset=True)),
             ("replay rows", lambda: run(True, None, 0, False, rows=True, jobs=jobs, reset=True)),
             ("score", score), ("context", context)]
    for name, step in steps:
        code = step()
        print(f"== {name}: exit {code}", flush=True)
        if code not in (0, 2):
            return 3 if code == 3 else 1
    return 0

def pack(jobs=1):
    """replay.zip exported from the archive: the standard runs replayed from fresh stores, reading the archive, and
    the answers they're served copied into a new fixture, packed."""
    import tempfile
    from semantic_pdf_diff import fixtures
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        export = d / "export" / "fixture.sqlite"  # the packed member's name
        export.parent.mkdir()
        said = io.StringIO()
        with contextlib.redirect_stdout(said):
            code = run(True, None, 0, False, fixture=WORKING, runs=d / "runs", pair_runs=d / "pairs", export=export,
                       jobs=jobs)
            if code in (0, 2):
                code = max(code, run(True, None, 0, False, fixture=WORKING, runs=d / "runs", pair_runs=d / "pairs",
                                     rows=True, export=export, jobs=jobs))
        if code not in (0, 2):
            failed = [line for line in said.getvalue().splitlines() if "exit 1" in line or "fixture holds" in line]
            print(f"the replay failed (exit {code}): nothing packed\n  " + "\n  ".join(failed[:20]))
            return code
        fixtures.pack(export, PACKED)
        with fixtures.open(export, "read") as f, fixtures.open(WORKING, "read") as archive:
            count = lambda x: x.db.execute("SELECT COUNT(*) FROM response").fetchone()[0]  # noqa: E731
            kept, held = count(f), count(archive)
    print(f"packed {PACKED}: {kept} answers exported of the archive's {held}")
    return 0

def run(replay, responder, max_cost, unaligned, error=None, fixture=None, runs=RUNS, pair_runs=PAIR_RUNS, rows=False,
        export=None, jobs=1, reset=False, config=None, only=()):
    """Every document read alone, then every revision pair compared: recorded into the working fixture, or replayed
    (from replay.zip, or `fixture`) into fresh or existing stores under runs and pair_runs; with `export`, every
    answer served or recorded also copied into that fixture. jobs: runs at once, in processes sharing the fixture
    (the documents first, then the pairs, which replay their extraction). reset: a store bound to other settings
    clears what changed and reads it again, instead of refusing. The cost cap is checked as each run starts, so runs
    started together may overshoot it together. config: a settings file other than the corpus's (a variant's); only:
    shell patterns of the documents' file names to read (a pair by its earlier document's)."""
    import fnmatch
    from semantic_pdf_diff import fixtures, ledger
    from semantic_pdf_diff.progress import setup_logging
    fixture = fixture or (PACKED if replay else WORKING)
    out = runs / ("replay" if replay else "recorded")
    if replay and not responder:  # the responder the fixture holds, whatever the environment says
        with fixtures.open(fixture, "read") as f:
            held = f.responders(answered=True)
        if len(held) != 1:
            (error or print)(f"the fixture holds {held}: name one with --responder")
            return 1
        responder = held[0]
    from semantic_pdf_diff_lab.bench.controlled import revisions
    setup_logging(quiet=True)
    # each document alone (the same PDF on both sides: extraction only), then each pair in revisions mode
    batch = [(pdf, pdf, out / pdf.stem, pdf.stem, "proposals") for pdf in sorted(DOCS.glob("*.pdf"))]
    for suffix, folder in REPRESENTATIONS.items():
        batch += [(d, d, out / d.name, d.name, "proposals") for d in sorted(folder.glob(f"*{suffix}"))]
    batch += [(DOCS / f"{p.earlier}.pdf", DOCS / f"{p.later}.pdf", pair_runs / out.name / p.id, f"pair {p.id}",
               "revisions") for p in revisions.pairs()]
    from semantic_pdf_diff_lab.bench.controlled import word
    for suffix, folder in REPRESENTATIONS.items():
        listed = revisions.pairs() + (word.pairs() if suffix == ".docx" else [])  # Word's own: word.py
        batch += [(folder / f"{p.earlier}{suffix}", folder / f"{p.later}{suffix}",
                   pair_runs / out.name / f"{p.id}{suffix}", f"pair {p.id}{suffix}", "revisions") for p in listed
                  if (folder / f"{p.earlier}{suffix}").exists() and (folder / f"{p.later}{suffix}").exists()]
    batch = [job for job in batch if job[4] != "revisions" or not same_document(job[0], job[1])]
    if only:
        batch = [job for job in batch if any(fnmatch.fnmatch(job[0].name, pattern) for pattern in only)]
    overrides = {}
    if unaligned:
        batch = [(a, b, pair_runs / f"{out.name}-unaligned" / folder.name, name + " unaligned", mode)
                 for a, b, folder, name, mode in batch if mode == "revisions" and a.suffix == ".pdf"]
        overrides = {"align": False}
    if rows:
        batch = [(a, b, folder.parent.parent / f"{folder.parent.name}-rows" / folder.name, name + " rows", mode)
                 for a, b, folder, name, mode in batch if a.suffix in (".xlsx", ".docx", ".pptx", ".pdf")]
        overrides = {"table_rules": None}
    before = ledger.spent(LEDGER, round="controlled")
    _BATCH.update(replay=replay, responder=responder, fixture=fixture, export=export, config=config or settings_file(),
                  overrides=overrides, max_cost=max_cost, before=before, reset=reset)
    worst, capped = 0, 0
    for mode in ("proposals", "revisions"):
        for name, code in _each([job for job in batch if job[4] == mode], jobs):
            if code == CAPPED:
                capped += 1
                continue
            print(f"{name}: exit {code}", flush=True)
            worst = max(worst, code)
    if capped:
        print(f"cap of ${max_cost} reached: {capped} runs not started (run again to resume)")
        worst = max(worst, 3)
    if not replay:
        print(f"spent ${ledger.spent(LEDGER, round='controlled') - before:.3f}; run `pack` before committing")
    return worst

CAPPED = -3  # a run not started: the cap was reached (exit 3)
_BATCH = {}  # what every run of a batch shares, set before the worker processes fork

def _each(batch, jobs):
    """(name, exit code) of each run, in processes when jobs > 1 (see recording.forked)."""
    from semantic_pdf_diff_lab.bench.recording import forked
    yield from forked(_one, batch, jobs)

def _one(job):
    """One run of the batch (_BATCH): (its name, its exit code, or CAPPED)."""
    from semantic_pdf_diff import ledger, pipeline
    a, b, folder, name, mode = job
    c = _BATCH
    options = pipeline.RunOptions(mode=mode, fixture=c["fixture"], export=c["export"], reset=c["reset"],
                                  fixture_mode="replay" if c["replay"] else "record-new", responder=c["responder"])
    if c["replay"]:  # the model named as recorded, whatever the environment says (its name is in the stores' binding)
        settings = pipeline.settings_from(c["config"], situate=False, base_url=pipeline.NO_MODEL, model=c["responder"],
                                          **c["overrides"])
    else:
        left = c["max_cost"] - (ledger.spent(LEDGER, round="controlled") - c["before"])
        if left <= 0:
            return name, CAPPED
        settings = pipeline.settings_from(c["config"], situate=False, max_cost=round(left, 4), **c["overrides"])
        options.ledger, options.ledger_tags = LEDGER, {"round": "controlled", "run": name.replace(" ", "-")}
    return name, pipeline.attempt(pipeline.compare_paths, a, b, folder, settings, options)

def context():
    """context.json: the standard runs' context measures (bench/context.py), per run and summed, with the sums
    printed."""
    from semantic_pdf_diff_lab.bench import context as measures
    runs = RUNS / "recorded"
    if not runs.exists():
        print(f"no runs in {runs}: run first")
        return 1
    inventory = measures.measure(runs)
    key_of = lambda run: json.loads(key_path(run).read_text(encoding="utf-8"))  # noqa: E731
    keyed = measures.measure_keys(runs, key_of)
    out = {"totals": {"inventory": measures.totals(inventory), **measures.sum_keys(keyed),
                      "reliability": measures.reliability(runs, key_of)},
           "runs": {run: {"inventory": inventory.get(run, {}), "keyed": keyed.get(run, {})}
                    for run in sorted(set(inventory) | set(keyed))}}
    (FOLDER / "context.json").write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(out["totals"], indent=1))
    return 0

def score():
    """results.json and comparisons.json from the runs' stores, with tables printed."""
    from semantic_pdf_diff_lab.bench import controlled
    from semantic_pdf_diff_lab.bench.recording import cut
    from semantic_pdf_diff_lab.eval import rounds
    unfinished = [(run, why) for base in (RUNS, PAIR_RUNS) if base.exists() for which in sorted(base.iterdir())
                  for run in sorted(which.iterdir()) for why in [cut(run)] if why]
    if unfinished:  # what a cap cut followed the order answers came in: resumed, not scored (determinism review, D6)
        print(f"{len(unfinished)} runs unfinished, nothing scored; resume them (run):\n  "
              + "\n  ".join(f"{run}: {why}" for run, why in unfinished[:20]))
        return 1
    results = {}
    for which in ("recorded", "replay", "recorded-rows", "replay-rows"):
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
    from semantic_pdf_diff_lab.bench.controlled import procedures, sheets
    knobbed = [(p, controlled.TABLE_KNOBS) for p in controlled.TABLE_PROJECTS] + \
              [(p, controlled.PROSE_KNOBS) for p in controlled.PROSE_PROJECTS] + \
              [(p, controlled.CHART_KNOBS) for p in controlled.CHART_PROJECTS] + \
              [(p, sheets.SHEET_KNOBS) for p in sheets.SHEET_PROJECTS] + \
              [(p, procedures.PROCEDURE_KNOBS) for p in procedures.PROCEDURE_PROJECTS]
    for which, runs in results.items():  # each knobbed project's knobs beside its clean version
        for project, knobs in knobbed:
            mine = {run[len(project) + 2:].partition("-")[2]: r for run, r in runs.items()
                    if run.startswith(project + "-s") and run[len(project) + 2:].partition("-")[0].isdigit()}
            if not mine:
                continue
            print(f"\n{which} {project}: knob      recall  right  loose  misbound  inexact  wrong unit  misread"
                  "  hallucinated  claims  conditions   misbound by reader; conditions kept by reader")
            for knob in knobs:
                r = mine.get(knob)
                if r:
                    o = r["outcomes"]
                    print(f"  {knob:12s} {r['recall']:7.3f} {r['found_right']:6d} {o.get('loose', 0):6d} "
                          f"{o.get('misbound', 0):9d} {o.get('inexact', 0):8d} {o.get('wrong unit', 0):11d} "
                          f"{o.get('misread', 0):8d} "
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
            if "views" in r:
                v = r["views"]
                print(f"    views {v['found']}/{v['views']} ({v['holder_in_stance']} held in a stance, "
                      f"{v['attitude_in_stance']} with the attitude); readings {v['outcomes']}")
    for which, runs in results.items():  # each Markdown and Word document beside its PDF
        for suffix, name in ((".md", "Markdown"), (".docx", "Word"), (".pptx", "Slides"), (".xlsx", "Excel")):
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
            if "views" in r:  # holders' yes-or-no views (views.py)
                v = r["views"]
                print(f"      views turned round {v['changes_found']}, kept {v['unchanged_confirmed']}, "
                      f"false changes {v['false_changes']}")
            if "kinds" in r:
                k = r["kinds"]
                print(f"      kinds named right {k['right']}/{k['scored']}, value changes named precisely "
                      f"{k['value_change_precision']}: {k['by_claims']}")
    return 0

def key_path(run):
    """A run's key: a PDF's in docs, a Markdown's ("<id>.md") in docs-md, a Word document's ("<id>.docx") in
    docs-docx, a deck's ("<id>.pptx") in docs-pptx, a workbook's ("<id>.xlsx") in docs-xlsx."""
    for suffix, folder in REPRESENTATIONS.items():
        if run.endswith(suffix):
            return folder / f"{run[:-len(suffix)]}.key.json"
    return DOCS / f"{run}.key.json"

def same_document(earlier, later):
    """Whether a pair's two documents are byte for byte the same: a revision whose changes the representation can't
    carry (the procedure diagram's, in Markdown), so there's nothing to compare."""
    return Path(earlier).read_bytes() == Path(later).read_bytes()

def compare_pairs():
    """comparisons.json: each revision pair's comparison scored against the two revisions' keys (PDF, and Markdown as
    "<id>.md")."""
    from semantic_pdf_diff_lab.bench.controlled import comparison, revisions, word
    compared = {}
    for which in ("recorded", "replay", "recorded-unaligned", "replay-unaligned", "recorded-rows", "replay-rows"):
        for pair in revisions.pairs() + word.pairs():
            for suffix in (("", *REPRESENTATIONS) if pair in revisions.pairs() else (".docx",)):
                report = PAIR_RUNS / which / f"{pair.id}{suffix}" / "report.json"
                documents = [key_path(d + suffix).with_name(f"{d}{suffix or '.pdf'}")
                             for d in (pair.earlier, pair.later)]
                if report.exists() and not same_document(*documents):
                    keys = [json.loads(key_path(d + suffix).read_text(encoding="utf-8"))
                            for d in (pair.earlier, pair.later)]
                    compared.setdefault(which, {})[pair.id + suffix] = comparison.score_comparison(
                        *keys, json.loads(report.read_text(encoding="utf-8")))
    (FOLDER / "comparisons.json").write_text(json.dumps(compared, indent=1) + "\n", encoding="utf-8")
    return compared

if __name__ == "__main__":
    sys.exit(main())
