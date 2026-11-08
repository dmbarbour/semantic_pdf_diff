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
    python scripts/controlled.py analyze --jobs 4            # the planted reports analyzed, scored (below)
    python scripts/controlled.py heldout --seed 2 --seed 3 --variant v.json   # held-out proposals pairs (below)

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

`analyze` reads each planted report and its clean twin (docs-analysis; consistency.py) with `analyze`, its second
pass on and situated (references), recorded or replayed as `run` is (a variant's settings over them with --variant),
and scores what the second pass and the gaps found by code found against what's planted: analysis.json (the
standard arm's; docs/plans/single-document-analysis-2026-10-28.md, milestones 3 to 5).

`heldout` measures a change already chosen on held-out proposals pairs (proposals.py; decision 0037: held-out sets
scored only when a change is up for promotion): the seeds named, never development's, generated into heldout/
(git-ignored: the generator makes them again), each pair compared in proposals mode in every format with a variant's
settings over the corpus's, recorded into heldout/fixture.sqlite (its own archive), and scored by role
(comparison.score_proposals) into heldout/<variant>.json, with the links by level for each arm a variant's
link_tests and link_read make: off, the tests, the tests and the reads (the arms rebuilt from the same reports).

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
DOCS_ANALYSIS = FOLDER / "docs-analysis"  # the planted reports and their clean twins, analyzed (consistency.py)
ANALYSIS = {"second_pass": True}  # the analyses' arm over the corpus's settings (a variant's settings over it)
# The representations' documents by suffix, in the order they're read and compared (code review 2026-10-08, E4).
REPRESENTATIONS = {".md": DOCS_MD, ".docx": DOCS_DOCX, ".pptx": DOCS_PPTX, ".xlsx": DOCS_XLSX}
from semantic_pdf_diff_lab.bench import recording  # noqa: E402
MAIN = recording.main_checkout(ROOT)  # from a frozen worktree, the main checkout: its archive, ledger and variants
WORKING = MAIN / "benchmarks/controlled/fixture.sqlite"  # the archive of recorded answers (git-ignored)
PACKED = FOLDER / "replay.zip"
RUNS = ROOT / "benchmarks/runs/controlled"
ANALYSIS_RUNS = ROOT / "benchmarks/runs/controlled-analysis"
PAIR_RUNS = ROOT / "benchmarks/runs/controlled-pairs"
VARIANTS = MAIN / "benchmarks/runs/controlled/variants"  # a named variant's runs, then its pairs'
VARIANT_PAIRS = MAIN / "benchmarks/runs/controlled-pairs/variants"
HELDOUT = MAIN / "benchmarks/controlled/heldout"  # held-out seeds' documents and archive (git-ignored)
HELDOUT_RUNS = MAIN / "benchmarks/runs/controlled-heldout"
LEDGER = recording.ledger(ROOT)
BASE_SETTINGS = recording.BASE_SETTINGS  # the settings recordings share: they shape the queries
ONE_SOURCE = "analysis"  # an analysis's mode (report.ONE_SOURCE)

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
    analyzing = sub.add_parser("analyze", help="analyze the planted reports and their clean twins, their second pass "
                                               "on, and score what's found against what's planted")
    analyzing.add_argument("--replay", action="store_true", help="from the packed fixture, without calling a model")
    analyzing.add_argument("--max-cost", type=float, default=0.2)
    analyzing.add_argument("--jobs", type=int, default=1, help="runs at once, in processes sharing the fixture")
    analyzing.add_argument("--variant", type=Path, metavar="FILE", help="a named variant, as `run --variant` takes")
    held = sub.add_parser("heldout", help="held-out proposals pairs: generate the seeds named, compare in every "
                                          "format with a variant's settings, score by role")
    held.add_argument("--seed", type=int, action="append", required=True, help="never development's (1)")
    held.add_argument("--variant", type=Path, required=True, metavar="FILE", help="as `run --variant` takes")
    held.add_argument("--max-cost", type=float, default=0.2)
    held.add_argument("--jobs", type=int, default=1)
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
        from semantic_pdf_diff_lab.bench.controlled import consistency
        for project in consistency.corpus():  # planted inconsistencies and gaps, and their clean twins
            print(f"{consistency.write(project, DOCS_ANALYSIS)}: {len(project.planted)} planted")
        return 0
    if args.command == "heldout":
        if 1 in args.seed:
            parser.error("seed 1 is development's: held-out seeds are others")
        return heldout(tuple(args.seed), args.variant, args.max_cost, args.jobs)
    if args.command == "run":
        if args.unaligned and args.rows:
            parser.error("--unaligned and --rows are separate runs")
        if args.variant:
            name, config, only = variant(args.variant)
            return run(args.replay, args.responder, args.max_cost, args.unaligned, parser.error, rows=args.rows,
                       jobs=args.jobs, fixture=WORKING, runs=VARIANTS / name,
                       pair_runs=VARIANT_PAIRS / name, config=config, only=only)
        return run(args.replay, args.responder, args.max_cost, args.unaligned, parser.error, rows=args.rows,
                   jobs=args.jobs)
    if args.command == "analyze":
        if args.variant:
            name, config, only = variant(args.variant, base=ANALYSIS, folder=ANALYSIS_RUNS / "variants")
            return analyze(args.replay, args.max_cost, args.jobs, runs=ANALYSIS_RUNS / "variants" / name,
                           config=config, only=only)
        return analyze(args.replay, args.max_cost, args.jobs)
    if args.command == "pack":
        return pack(args.jobs)
    if args.command == "refresh":
        return refresh(args.max_cost, args.jobs)
    if args.command == "context":
        return context()
    return score()

def variant(path, base=None, folder=None):
    """(name, settings file, document patterns) of a variant defined in a JSON file: {"settings": an overlay on the
    corpus's settings, "only": shell patterns of the documents' file names (default: every document; a pair by its
    earlier document), "name": its folder's (default: the file's stem)}. Its resolved settings and its definition are
    written beside its runs; a later run of the same name with other settings reads again what they change."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    unknown = set(data) - {"settings", "only", "name", "note"}
    if unknown:
        raise SystemExit(f"{path}: unknown keys {sorted(unknown)} (settings, only, name, note)")
    name = data.get("name") or Path(path).stem
    folder = (folder or VARIANTS) / name
    folder.mkdir(parents=True, exist_ok=True)
    settings = {**json.loads(settings_file().read_text(encoding="utf-8")), **(base or {}), **data.get("settings", {})}
    (folder / "settings.json").write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")
    (folder / "variant.json").write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return name, folder / "settings.json", tuple(data.get("only") or ())

def refresh(max_cost, jobs=1):
    """Every step after a change, in order, stores reading again what changed: the standard and row-by-row runs
    recorded, replay.zip exported, both replayed from it, scored, context measured. Exit status 1 when a run failed
    or a step did, 3 when a recording reached its cap (rerun to resume); incomplete coverage (2) isn't a failure."""
    steps = [("record", lambda: run(False, None, max_cost, False, jobs=jobs)),
             ("record rows", lambda: run(False, None, max_cost, False, rows=True, jobs=jobs)),
             ("record analyses", lambda: analyze(False, max_cost, jobs, scoring=False)),
             ("pack", lambda: pack(jobs)),
             ("replay", lambda: run(True, None, 0, False, jobs=jobs)),
             ("replay rows", lambda: run(True, None, 0, False, rows=True, jobs=jobs)),
             ("replay analyses", lambda: analyze(True, 0, jobs)),
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
            if code in (0, 2):
                code = max(code, analyze(True, 0, jobs, fixture=WORKING, runs=d / "analyses", export=export,
                                         scoring=False))
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
        export=None, jobs=1, config=None, only=()):
    """Every document read alone, then every revision pair compared: recorded into the working fixture, or replayed
    (from replay.zip, or `fixture`) into fresh or existing stores under runs and pair_runs; with `export`, every
    answer served or recorded also copied into that fixture. jobs: runs at once, in processes sharing the fixture
    (the documents first, then the pairs, which replay their extraction). A store bound to other settings
    reads again what changed. The cost cap is checked as each run starts, so runs
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
    # each proposal pair in proposals mode (proposals.py; docs/plans/tentative-matches-2026-11-07.md, milestone 5)
    from semantic_pdf_diff_lab.bench.controlled import proposals
    batch += [(DOCS / f"{p.earlier}.pdf", DOCS / f"{p.later}.pdf", pair_runs / out.name / p.id, f"pair {p.id}",
               "proposals") for p in proposals.pairs()]
    for suffix, folder in REPRESENTATIONS.items():
        batch += [(folder / f"{p.earlier}{suffix}", folder / f"{p.later}{suffix}",
                   pair_runs / out.name / f"{p.id}{suffix}", f"pair {p.id}{suffix}", "proposals")
                  for p in proposals.pairs()
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
                  overrides=overrides, max_cost=max_cost, before=before)
    worst, capped = 0, 0
    alone = lambda job: job[0] == job[1]  # noqa: E731 (a document read alone)
    for phase in (alone, lambda job: job[4] == "revisions",  # the documents first, then the pairs
                  lambda job: job[4] == "proposals" and not alone(job)):
        for name, code in _each([job for job in batch if phase(job)], jobs):
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

def analyze(replay, max_cost, jobs=1, fixture=None, runs=ANALYSIS_RUNS, export=None, config=None, only=(),
            scoring=True):
    """Each planted report and its clean twin analyzed (docs-analysis), its second pass on (ANALYSIS, or a variant's
    settings in config), situated: recorded into the working fixture, or replayed (from replay.zip, or `fixture`)
    into stores under runs; then scored (consistency.scored) into analysis.json for the standard runs, printed for a
    variant's. Exit status as run's."""
    import fnmatch
    from semantic_pdf_diff import fixtures, ledger
    from semantic_pdf_diff.progress import setup_logging
    fixture = fixture or (PACKED if replay else WORKING)
    out = runs / ("replay" if replay else "recorded")
    responder = None
    if replay:
        with fixtures.open(fixture, "read") as f:
            held = f.responders(answered=True)
        if len(held) != 1:
            print(f"the fixture holds {held}: nothing analyzed")
            return 1
        responder = held[0]
    if config is None:
        config = runs / "settings.json"
        config.parent.mkdir(parents=True, exist_ok=True)
        config.write_text(json.dumps({**json.loads(settings_file().read_text(encoding="utf-8")), **ANALYSIS},
                                     indent=2) + "\n", encoding="utf-8")
    setup_logging(quiet=True)
    batch = [(pdf, None, out / pdf.stem, f"analysis {pdf.stem}", ONE_SOURCE)
             for pdf in sorted(DOCS_ANALYSIS.glob("*.pdf"))
             if not only or any(fnmatch.fnmatch(pdf.name, pattern) for pattern in only)]
    before = ledger.spent(LEDGER, round="controlled")
    _BATCH.update(replay=replay, responder=responder, fixture=fixture, export=export, config=config, overrides={},
                  max_cost=max_cost, before=before)
    worst, capped = 0, 0
    for name, code in _each(batch, jobs):
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
    if scoring and worst in (0, 2):
        scored = score_analyses(out, write=runs == ANALYSIS_RUNS)
        worst = max(worst, 0 if scored else 1)
    return worst

def score_analyses(out, write=True):
    """Each analysis under out scored against its key (consistency.scored), the twins' totals printed; into
    analysis.json when write. Returns the results ({} when none was found)."""
    from semantic_pdf_diff_lab.bench.controlled import consistency
    results = {}
    for pdf in sorted(DOCS_ANALYSIS.glob("*.pdf")):
        report = out / pdf.stem / "report.json"
        if report.exists():
            key = json.loads((DOCS_ANALYSIS / f"{pdf.stem}.key.json").read_text(encoding="utf-8"))
            results[pdf.stem] = consistency.scored(key, json.loads(report.read_text(encoding="utf-8")))
    if not results:
        print(f"no analyses under {out}")
        return {}
    found = {"totals": consistency.totals(results), "documents": results}
    for twin, t in found["totals"].items():
        c, g = t["contradictions"], t["gaps"]
        print(f"{twin} ({t['documents']} documents): contradictions {c['found']}/{c['planted']} found, {c['false']} "
              f"false; under another condition {t['condition']['contradicts']}/{t['condition']['pairs']} said to "
              f"contradict, restated {t['restatement']['contradicts']}/{t['restatement']['pairs']}")
        print("  gaps: " + ", ".join(f"{kind} {g[kind]['by code']}/{g[kind]['planted']} by code ("
                                     f"{g[kind].get('as a blank cell', 0)} as a blank cell), "
                                     f"{g[kind]['read together']} read together"
                                     for kind in ("sibling", "placeholder", "reference"))
              + f"; not planted {g['unplanted']}")
        print(f"  implied {t['implied']['found']}/{t['implied']['planted']} ({t['implied']['inferences']} inferences); "
              f"suspicions {t['suspicions']}; read again {t['reread']}; gaps looked for {t['looked']}; log {t['log']}")
        n = t.get("tensions", {})
        if n.get("levels") or n.get("reconciled") or n.get("elsewhere"):  # asked (the tensions lever)
            print(f"  tensions: of {n['tensions']}, {n['standing']} standing ({n['levels']}), {n['reconciled']} "
                  f"reconciled; elsewhere {n['elsewhere']}")
    if write:
        (FOLDER / "analysis.json").write_text(json.dumps(found, indent=1) + "\n", encoding="utf-8")
    return results

def _one(job):
    """One run of the batch (_BATCH): (its name, its exit code, or CAPPED)."""
    from semantic_pdf_diff import ledger, pipeline
    a, b, folder, name, mode = job
    c = _BATCH
    situate = mode == ONE_SOURCE  # an analysis situates: its references are found there (the gaps cited, not found)
    options = pipeline.RunOptions(mode=mode, fixture=c["fixture"], export=c["export"],
                                  fixture_mode="replay" if c["replay"] else "record-new", responder=c["responder"])
    if c["replay"]:  # the model named as recorded, whatever the environment says (its name is in the stores' binding)
        settings = pipeline.settings_from(c["config"], situate=situate, base_url=pipeline.NO_MODEL,
                                          model=c["responder"], **c["overrides"])
    else:
        left = c["max_cost"] - (ledger.spent(LEDGER, round="controlled") - c["before"])
        if left <= 0:
            return name, CAPPED
        settings = pipeline.settings_from(c["config"], situate=situate, max_cost=round(left, 4), **c["overrides"])
        options.ledger, options.ledger_tags = LEDGER, {"round": "controlled", "run": name.replace(" ", "-")}
    if mode == ONE_SOURCE:
        return name, pipeline.attempt(pipeline.analyze_paths, a, folder, settings, options)
    return name, pipeline.attempt(pipeline.compare_paths, a, b, folder, settings, options)

def heldout(seeds, variant_path, max_cost, jobs=1):
    """Held-out proposals pairs (see the module's note): generated, compared, scored; exit status as run's."""
    from semantic_pdf_diff import ledger
    from semantic_pdf_diff.progress import setup_logging
    from semantic_pdf_diff_lab.bench import controlled
    from semantic_pdf_diff_lab.bench.controlled import proposals, representations, slides, workbooks
    from semantic_pdf_diff_lab.bench.controlled.corpus import PROJECTS
    folders = {".pdf": HELDOUT / "docs", ".md": HELDOUT / "docs-md", ".docx": HELDOUT / "docs-docx",
               ".pptx": HELDOUT / "docs-pptx", ".xlsx": HELDOUT / "docs-xlsx"}
    projects = [PROJECTS[key](seed) for seed in seeds for key in sorted({key for key, *_ in proposals.PAIRS})]
    projects += [project for seed in seeds for _, project in proposals.proposed(seed)]
    for project in projects:
        controlled.write(project, folders[".pdf"])
        lines = representations.markdown(project)
        representations.write(project, lines, folders[".md"])
        representations.write_docx(project, lines, folders[".docx"])
        slides.write(folders[".pptx"], project, slides.deck(project))
        workbooks.write(folders[".xlsx"], project, workbooks.workbook(project))
    name, config, _ = variant(variant_path, folder=HELDOUT_RUNS)
    runs = HELDOUT_RUNS / name
    pairs = [pair for seed in seeds for pair in proposals.pairs(seed)]
    alone = [(f, f, runs / "docs" / f.name, f.name, "proposals") for suffix, folder in folders.items()
             for f in sorted(folder.glob(f"*{suffix}"))]
    compared = [(folders[s] / f"{p.earlier}{s}", folders[s] / f"{p.later}{s}", runs / f"{p.id}{s}", f"pair {p.id}{s}",
                 "proposals") for p in pairs for s in folders]
    setup_logging(quiet=True)
    before = ledger.spent(LEDGER, round="controlled")
    _BATCH.update(replay=False, responder=None, fixture=HELDOUT / "fixture.sqlite", export=None, config=config,
                  overrides={}, max_cost=max_cost, before=before)
    worst, capped = 0, 0
    for batch in (alone, compared):  # the documents first: the pairs replay their extraction
        for run_name, code in _each(batch, jobs):
            if code == CAPPED:
                capped += 1
                continue
            worst = max(worst, code)
            if code not in (0, 2):
                print(f"{run_name}: exit {code}", flush=True)
    print(f"spent ${ledger.spent(LEDGER, round='controlled') - before:.3f}")
    if capped:
        print(f"cap of ${max_cost} reached: {capped} runs not started (run again to resume)")
        return 3
    scored = heldout_scores(pairs, folders, runs)
    (HELDOUT / f"{name}.json").write_text(json.dumps(scored, indent=1) + "\n", encoding="utf-8")
    for arm, levels in scored["totals"].items():
        print(f"{arm:12s} " + "; ".join(f"{level} {c.get('right', 0)} right of {c.get('links', 0)}"
                                         for level, c in sorted(levels.items())))
    return worst

def heldout_scores(pairs, folders, runs):
    """Each held-out pair's links by level in each arm (off, tests, tests and reads), and their totals, from its
    report rebuilt (indexes.built) with the arm's settings."""
    from collections import Counter, defaultdict
    from semantic_pdf_diff import indexes
    from semantic_pdf_diff_lab.bench.controlled import comparison
    arms = {"off": (False, False), "tests": (True, False), "tests+reads": (True, True)}
    units, totals = {}, defaultdict(lambda: defaultdict(Counter))
    for pair in pairs:
        for suffix, folder in folders.items():
            path = runs / f"{pair.id}{suffix}" / "report.json"
            if not path.exists():
                continue
            report = json.loads(path.read_text(encoding="utf-8"))
            keys = [json.loads((folder / f"{d}.key.json").read_text(encoding="utf-8"))
                    for d in (pair.earlier, pair.later)]
            entries = (report.get("commentary") or {}).get("entries", [])
            unit = {}
            for arm, (tests, reads) in arms.items():
                data = {**report, "settings": {**(report.get("settings") or {}), "link_tests": tests},
                        "commentary": {**(report.get("commentary") or {}),
                                       "entries": [e for e in entries if reads or e["kind"] != "link_read"]}}
                data["index"] = indexes.built(data)
                links = comparison.score_proposals(*keys, data)["matching"].get("links", {})
                unit[arm] = links
                for level, c in links.items():
                    totals[arm][level].update(c)
            units[f"{pair.id}{suffix}"] = unit
    return {"totals": {arm: {level: dict(c) for level, c in levels.items()} for arm, levels in totals.items()},
            "units": units}

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
            if "difference_precision" not in r:  # a proposal pair (proposals.py): by role
                print(f"  {pair:30s} proposals: matching {r.get('matching')}; gaps {r.get('gaps_found')} "
                      f"{r.get('gaps')}; findings {r['findings']}")
                continue
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
    from semantic_pdf_diff_lab.bench.controlled import comparison, proposals, revisions, word
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
        for pair in proposals.pairs():  # by role, in proposals mode (proposals.py)
            for suffix in ("", *REPRESENTATIONS):
                report = PAIR_RUNS / which / f"{pair.id}{suffix}" / "report.json"
                if report.exists():
                    keys = [json.loads(key_path(d + suffix).read_text(encoding="utf-8"))
                            for d in (pair.earlier, pair.later)]
                    compared.setdefault(which, {})[pair.id + suffix] = comparison.score_proposals(
                        *keys, json.loads(report.read_text(encoding="utf-8")))
    (FOLDER / "comparisons.json").write_text(json.dumps(compared, indent=1) + "\n", encoding="utf-8")
    return compared

if __name__ == "__main__":
    sys.exit(main())
