"""Spot checks: a person judges the same pairs as the panel, blind, on a page of their own.

    # a batch comparing round 0's output with the champion's, on the documents both covered
    python scripts/spotcheck.py build benchmarks/spotchecks/sc01 \\
        --baseline benchmarks/runs/r02/baseline --baseline benchmarks/runs/r02h/baseline \\
        --variant benchmarks/runs/r09b/fragments --variant benchmarks/runs/r09h/fragments --units 16
    python scripts/spotcheck.py judge benchmarks/spotchecks/sc01      # the panel's verdicts (needs .env)
    # open benchmarks/spotchecks/sc01/spotcheck.html, answer, download the answers file, then:
    python scripts/spotcheck.py import benchmarks/spotchecks/sc01 spotcheck-sc01-david.json
    python scripts/spotcheck.py compare benchmarks/spotchecks/sc01
    # the panel again with another rubric (verdicts in verdicts-v6/), and people against that:
    python scripts/spotcheck.py judge benchmarks/spotchecks/sc01 --rubric v6
    python scripts/spotcheck.py compare benchmarks/spotchecks/sc01 --rubric v6
"""
import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from semantic_pdf_diff_lab.bench import recording  # noqa: E402
LEDGER = ROOT / recording.LEDGER
MANIFEST = json.loads((ROOT / "scripts/slices.json").read_text())
DOCUMENTS = {s["name"]: s.get("family") for s in MANIFEST["slices"]}

def combine(dirs, target):
    """One folder of runs (symlinks) from several round folders, with the first one's settings."""
    target.mkdir(parents=True, exist_ok=True)
    for source in dirs:
        for run in sorted(p for p in source.iterdir() if (p / "store.sqlite").exists()):
            link = target / run.name
            if not link.exists():
                link.symlink_to(os.path.relpath(run.resolve(), target))
    settings = dirs[0] / "settings.json"
    (target / "settings.json").write_text(settings.read_text() if settings.exists() else "{}")
    return target

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("build", help="sample changed units and write spotcheck.html")
    build.add_argument("folder", type=Path)
    build.add_argument("--baseline", type=Path, action="append", required=True)
    build.add_argument("--variant", type=Path, action="append", required=True)
    build.add_argument("--units", type=int, default=16)
    build.add_argument("--claims", type=int, default=15, help="claims per unit before it's cut into bands")
    build.add_argument("--seed", type=int, default=1)
    context = sub.add_parser("context", help="add full context to an existing spot check (same units)")
    context.add_argument("folder", type=Path)
    context.add_argument("--units", type=int, default=16)
    context.add_argument("--claims", type=int, default=15)
    context.add_argument("--seed", type=int, default=1)
    judge = sub.add_parser("judge", help="the panel's verdicts on the same units")
    judge.add_argument("folder", type=Path)
    judge.add_argument("--rubric", default="v4", help="v4 (sc01's first verdicts, in verdicts/); others in verdicts-<rubric>/")
    judge.add_argument("--judge", action="append", default=[])
    judge.add_argument("--escalate", action="append", default=[])
    judge.add_argument("--max-cost", type=float, default=1.0)
    imp = sub.add_parser("import", help="a person's answers file, as verdicts")
    imp.add_argument("folder", type=Path)
    imp.add_argument("answers", type=Path)
    compare = sub.add_parser("compare", help="people against the panel")
    compare.add_argument("folder", type=Path)
    compare.add_argument("--rubric", default="v4", help="the panel's verdicts under this rubric")
    args = parser.parse_args(argv)
    from semantic_pdf_diff_lab.eval import rounds
    verdicts = lambda rubric: "verdicts" if rubric == "v4" else f"verdicts-{rubric}"

    if args.command == "build":
        # spot checks commit their units' page images and claims, like rounds: public slices only
        private = rounds.private_slices([p.name for d in args.baseline + args.variant for p in d.iterdir()
                                         if (p / "store.sqlite").exists()], MANIFEST)
        if private:
            print(f"Refusing: slices not marked public in scripts/slices.json: {', '.join(private)}")
            return 2
        base = combine(args.baseline, args.folder / "sources" / "baseline")
        var = combine(args.variant, args.folder / "sources" / "variant")
        shared = {p.name for p in base.iterdir()} & {p.name for p in var.iterdir()}
        for side in (base, var):  # only documents both sides read
            for p in side.iterdir():
                if p.is_symlink() and p.name not in shared:
                    p.unlink()
        batch = rounds.build_batch(base, var, args.folder, n=args.units, seed=args.seed, limit=args.claims)
        rounds.add_context(args.folder, base, var, n=args.units, seed=args.seed, limit=args.claims)
        print(f"{len(batch['items'])} units; page: {rounds.write_spotcheck(args.folder)}")
    elif args.command == "context":
        sources = args.folder / "sources"
        rounds.add_context(args.folder, sources / "baseline", sources / "variant", n=args.units, seed=args.seed,
                           limit=args.claims)
        print(f"Context added; page: {rounds.write_spotcheck(args.folder)}")
    elif args.command == "judge":
        from semantic_pdf_diff_lab.eval.raters import ModelJudge
        from semantic_pdf_diff.ledger import Ledger
        from semantic_pdf_diff_lab.eval.clients import folder_client
        from semantic_pdf_diff_lab.eval.clients import Budget, evaluator_settings
        judges = args.judge or ["XiaomiMiMo/MiMo-V2.6-Pro"]
        escalate = args.escalate or ["Qwen/Qwen3.5-397B-A17B"]
        budget = Budget(args.max_cost)  # for the whole command: every judge and escalation shares it

        class Paused(Exception):
            pass

        def ask(model, only=None, retry_failed=False):
            if budget.exhausted():
                raise Paused(f"the cap of ${args.max_cost:.2f} is spent")
            settings = evaluator_settings(model, concurrency=16, timeout=900, retries=0, **budget.settings())
            with folder_client(args.folder, settings) as client:
                client.ledger = Ledger(LEDGER, round="spotcheck", step="judge", variant=args.folder.name, judge=model)
                records = ModelJudge(client, model, args.rubric, verdicts(args.rubric)).rate(
                    args.folder, only=only, retry_failed=retry_failed)
            budget.add(client)
            if client.out_of_budget:
                raise Paused(client.out_of_budget)
            return records
        try:
            for model in judges:
                ask(model)
                ask(model, retry_failed=True)
            unsettled = rounds.unsettled(args.folder, judges, verdicts_dir=verdicts(args.rubric))
            for model in escalate:
                if unsettled:
                    ask(model, only=unsettled)
                    ask(model, only=unsettled, retry_failed=True)
        except Paused as why:  # no decision on partial verdicts: rerunning resumes, answers already paid replay
            print(f"Paused: {why}")
            return 3
        print(json.dumps(rounds.decide(args.folder, verdicts_dir=verdicts(args.rubric), documents=DOCUMENTS), indent=2))
    elif args.command == "import":
        from semantic_pdf_diff_lab.eval.raters import Person
        person = Person(args.answers)
        records = person.rate(args.folder)
        print(f"Imported {person.name}: {sum(r.question == 'pair' for r in records)} units, "
              f"{sum(r.question == 'claim' for r in records)} claims marked")
    else:
        print(json.dumps(rounds.anchor(args.folder, verdicts_dir=verdicts(args.rubric)), indent=2))
    return 0

if __name__ == "__main__":
    sys.exit(main())
