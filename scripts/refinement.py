"""Refinement measured: every tile of the given documents refined once, read under one source tree, then two trees'
runs compared (lab/src/semantic_pdf_diff_lab/bench/refinement.py).

    set -a; . ./.env; set +a
    git worktree add /tmp/before <commit before a change>
    python scripts/refinement.py run --src /tmp/before/src --out runs/before --fixture f.sqlite --max-cost 0.3 DOC...
    python scripts/refinement.py run --out runs/after --fixture f.sqlite --max-cost 0.3 DOC...
    python scripts/refinement.py report runs/before runs/after

`--src` reads with another tree's product code (the lab's bench is this tree's). Both runs share one fixture, so
the tiles themselves are asked once; seeding it from the controlled corpus's replay.zip replays them for free. A
controlled document is scored against its key in benchmarks/controlled/docs.
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SETTINGS = ROOT / "benchmarks/controlled/settings.json"  # the corpus's settings; refinement_depth is 1
KEYS = ROOT / "benchmarks/controlled/docs"
LEDGER = ROOT / "benchmarks/ledger.jsonl"

def run(src, out, fixture, max_cost, documents, tag, fresh=False):
    sys.path.insert(0, str(Path(src).resolve()))
    from semantic_pdf_diff import ledger, pipeline
    from semantic_pdf_diff.progress import setup_logging
    from semantic_pdf_diff_lab.bench import refinement
    import semantic_pdf_diff
    print(f"reading with {Path(semantic_pdf_diff.__file__).parent}")
    setup_logging(quiet=True)
    before = ledger.spent(LEDGER, round="refinement") if LEDGER.exists() else 0.0
    worst = 0
    with refinement.forced(fresh_halves=fresh):
        for document in map(Path, documents):
            left = max_cost - ((ledger.spent(LEDGER, round="refinement") if LEDGER.exists() else 0.0) - before)
            if left <= 0:
                print(f"cap of ${max_cost} reached")
                return 3
            settings = pipeline.settings_from(SETTINGS, situate=False, refinement_depth=1, max_cost=round(left, 4))
            options = pipeline.RunOptions(mode="proposals", fixture=fixture, fixture_mode="replay-or-record",
                                          ledger=LEDGER, ledger_tags={"round": "refinement", "run": f"{tag}-{document.stem}"})
            code = pipeline.attempt(pipeline.compare_paths, document, document, Path(out) / document.stem, settings, options)
            print(f"{document.name}: exit {code}", flush=True)
            worst = max(worst, code)
    spent = (ledger.spent(LEDGER, round="refinement") if LEDGER.exists() else 0.0) - before
    print(f"spent ${spent:.3f}")
    return worst

def report(before, after):
    sys.path.insert(0, str(ROOT / "src"))
    from semantic_pdf_diff_lab.bench import refinement
    keys = {p.name[:-len(".key.json")]: p for p in KEYS.glob("*.key.json")}
    found = refinement.compare(before, after, keys)
    for name, arms in found.items():
        stores = [Path(folder) / name / "store.sqlite" for folder in (before, after)]
        arms["before"]["checks"], arms["after"]["checks"] = (refinement.checks(s) for s in stores)
        arms["after"]["against before"] = refinement.against(*stores)
    print(json.dumps(found, indent=1))
    totals = {}
    for arms in found.values():
        for arm, counts in arms.items():
            mine = totals.setdefault(arm, {})
            for k, v in counts.items():
                if isinstance(v, dict):
                    for o, n in v.items():
                        mine.setdefault(k, {})[o] = mine.setdefault(k, {}).get(o, 0) + n
                else:
                    mine[k] = mine.get(k, 0) + v
    print(json.dumps(totals, indent=1))

def judge(before, after, folder, models, max_cost, check=False, grown=False):
    """The halves of two runs judged: pairwise per tile (rubric v5), or with check, each half's claims marked."""
    sys.path.insert(0, str(ROOT / "src"))
    from semantic_pdf_diff.ledger import Ledger
    from semantic_pdf_diff_lab.eval.clients import evaluator_settings, folder_client
    from semantic_pdf_diff_lab.bench import refinement
    from semantic_pdf_diff_lab.eval.raters import ModelJudge
    folder = Path(folder)
    built = (refinement.half_checks({"before": before, "after": after}, folder) if check
             else refinement.pairs(before, after, folder, grown,
                                   json.loads(SETTINGS.read_text(encoding="utf-8")).get("image_side")))
    print(f"{built} {'halves' if check else 'tiles'}")
    for model in models:
        settings = evaluator_settings(model, concurrency=8, timeout=600, retries=2, max_cost=max_cost)
        with folder_client(folder, settings) as client:
            client.ledger = Ledger(LEDGER, round="refinement", step="check" if check else "judge", judge=model)
            if check:
                print(model, json.dumps(refinement.check_halves(folder, client, model)))
            else:
                ModelJudge(client, model, "v5").rate(folder)
                print(model, json.dumps(refinement.verdicts(folder, model)))

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    go = sub.add_parser("run", help="read documents with every tile refined once (records answers)")
    go.add_argument("documents", nargs="+")
    go.add_argument("--src", default=str(ROOT / "src"), help="the product's source tree to read with")
    go.add_argument("--out", required=True, help="a folder of per-document stores")
    go.add_argument("--fixture", required=True, help="a .sqlite fixture, shared by the runs compared")
    go.add_argument("--max-cost", type=float, default=0.3, help="for the whole command, in dollars")
    go.add_argument("--tag", default="", help="the ledger's run tag prefix (before, after)")
    go.add_argument("--fresh-halves", action="store_true", help="the halves asked afresh: a run against itself")
    show = sub.add_parser("report", help="the two runs' halves compared, offline")
    show.add_argument("before")
    show.add_argument("after")
    for name, helping in (("judge", "the halves of two runs compared by judges, per tile (records answers)"),
                          ("check", "each half's claims marked by a model against its image (records answers)")):
        rated = sub.add_parser(name, help=helping)
        rated.add_argument("before")
        rated.add_argument("after")
        rated.add_argument("--folder", required=True, help="the batch's folder, with its own fixture")
        rated.add_argument("--model", action="append", required=True)
        rated.add_argument("--max-cost", type=float, default=1.0, help="per model, in dollars")
        if name == "judge":
            rated.add_argument("--grown", action="store_true", help="only tiles whose halves reach past them, shown "
                               "grown to cover every half")
    args = parser.parse_args(argv)
    if args.command in ("judge", "check"):
        return judge(args.before, args.after, args.folder, args.model, args.max_cost, args.command == "check",
                     getattr(args, "grown", False))
    if args.command == "run":
        return run(args.src, args.out, args.fixture, args.max_cost, args.documents, args.tag or Path(args.out).name,
                   args.fresh_halves)
    return report(args.before, args.after)

if __name__ == "__main__":
    sys.exit(main())
