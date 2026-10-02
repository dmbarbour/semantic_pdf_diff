"""The lab's commands, added to `pdf-semantic-diff` through the "semantic_pdf_diff.commands" entry points
(code review 2026-10-01, A2; architecture clean-up, milestone 8): review panels, and query dumps and checks.

    pdf-semantic-diff review sample|import|judge|consensus|agreement|scores|page ...
    pdf-semantic-diff queries dump|check|flagged ...
"""
import argparse
import json
from pathlib import Path

from semantic_pdf_diff.cli import add_budget_options, add_log_options, start_logging
from semantic_pdf_diff.llm import Budget, evaluator_settings, folder_client
from semantic_pdf_diff.pipeline import RunOptions, attach_ledger, budget_note
from semantic_pdf_diff.progress import Progress, log

from . import queries, review

def queries_command(argv):
    parser = argparse.ArgumentParser(prog='pdf-semantic-diff queries',
        description='Queries as the model saw them: dump a sample from runs, and have strong models check them.')
    sub = parser.add_subparsers(dest='command', required=True)
    dump = sub.add_parser('dump', help="Sample queries from a folder of runs (their stores' query logs) into a page")
    dump.add_argument('runs', type=Path, help='A folder of runs (each with its store), e.g. benchmarks/runs/r09/excerpts')
    dump.add_argument('--out', type=Path, required=True, help='Folder to write the dump to')
    dump.add_argument('--against', type=Path, help="A baseline's runs: show only what changed, as diffs")
    dump.add_argument('--sample', type=int, default=30)
    dump.add_argument('--seed', type=int, default=1)
    dump.add_argument('--lever', help='Only queries where this lever added something (see extract.LEVER_MARKS)')
    dump.add_argument('--role', choices=['extract', 'triage', 'compare', 'all'], default='extract')
    check = sub.add_parser('check', help='Checker models look for obvious errors in a dump\'s queries')
    check.add_argument('folder', type=Path)
    check.add_argument('--model', action='append', required=True, help='Checker model; repeatable')
    add_budget_options(check)
    add_log_options(check)
    args = parser.parse_args(argv)
    if args.command == 'dump':
        summary = queries.dump(args.runs, args.out, args.against, args.sample, args.seed, args.lever, args.role)
        print(f"{summary['shown']} of {summary['candidates']} queries -> {args.out / 'index.html'}")
        return 0
    start_logging(args)
    budget = Budget(args.max_cost)  # for the whole command, not each model
    for model in args.model:
        if budget.exhausted():
            log.warning(f'cost cap of ${args.max_cost:.2f} reached before checking with {model}')
            return 3
        # Reasoning models think at length: 4,000 output tokens truncated most of Qwen's and Kimi's
        # answers in the first trial (paid for, and lost). Few at a time, so a cap overshoots little.
        settings = evaluator_settings(model, concurrency=4, timeout=600, retries=1, **budget.settings())
        with folder_client(args.folder, settings) as client:
            attach_ledger(client, RunOptions.from_args(args))
            progress = Progress(f'check {model}', client, heartbeat=settings.heartbeat_seconds)
            target, count, failures = queries.check(args.folder, client, model, progress)
            progress.close()
        budget.add(client)
        for failure in failures[:5]:
            log.warning(f'{model}: {failure}')
        print(f"{model}: {count} checks -> {target}; ${client.cost:.3f}")
        note = budget_note(client)
        if note:
            log.warning(note)
            return 3
    flagged, in_change = queries.flagged(args.folder), queries.flagged(args.folder, in_change=True)
    print(f"{len(flagged)} flagged, {len(in_change)} in what changed: {args.folder / 'index.html'}")
    return 0

def review_command(argv):
    parser = argparse.ArgumentParser(prog='pdf-semantic-diff review',
        description='Review batches: sample results, label them (people and a panel of models), measure agreement.')
    sub = parser.add_subparsers(dest='command', required=True)
    sample = sub.add_parser('sample', help='Sample claims, about statements and claim pairs from stores into a batch')
    sample.add_argument('batch', type=Path, help='Batch folder to create')
    sample.add_argument('--store', action='append', required=True, metavar='LABEL=DIR',
                        help='A store to sample, labelled by who produced it (hidden from reviewers); repeatable')
    sample.add_argument('--claims', type=int, default=12, help='Claims per store (round-robin over claim kinds)')
    sample.add_argument('--abouts', type=int, default=4, help='About statements per store')
    sample.add_argument('--pairs', type=int, default=4, help='Claim pairs per store (round-robin over relations)')
    sample.add_argument('--seed', type=int, default=1)
    add = sub.add_parser('import', help="Check a reviewer's labels file and add it to the batch")
    add.add_argument('batch', type=Path)
    add.add_argument('labels', type=Path, nargs='+')
    panel = sub.add_parser('judge', help='Ask models to review a batch, each as its own reviewer')
    panel.add_argument('batch', type=Path)
    panel.add_argument('--model', action='append', required=True, help='Model name at the configured endpoint; repeatable')
    panel.add_argument('--limit', type=int, help='Only the first N items (to check cost first)')
    panel.add_argument('--stage', choices=['answers', 'questions'], default='answers',
                       help='Judge the answers (default), or the questions blind (the inputs, without answers)')
    add_budget_options(panel)
    add_log_options(panel)
    agree = sub.add_parser('consensus', help='Consensus verdicts and reviewer reliability, estimated from all labels '
                                             '(Dawid-Skene), with contested items to discuss; no reviewer is referee')
    agree.add_argument('batch', type=Path)
    agree.add_argument('--gate', action='store_true', help='Use the usable-or-not question instead of the full verdict')
    agree.add_argument('--stage', choices=['answers', 'questions'], default='answers')
    questions = sub.add_parser('question-agreement', help='Agreement between reviewers on the questions (inputs)')
    questions.add_argument('batch', type=Path)
    for name, help in (('agreement', 'Agreement between reviewers: verdicts, flags, clarity, confidence'),
                       ('scores', 'Verdicts per responder, item type and claim kind, per reviewer'),
                       ('page', 'Rewrite the review page (after a taxonomy change)')):
        sub.add_parser(name, help=help).add_argument('batch', type=Path)
    args = parser.parse_args(argv)
    if args.command == 'sample':
        stores = []
        for spec in args.store:
            label, _, path = spec.partition('=')
            if not path:
                raise ValueError(f'--store {spec!r}: use LABEL=DIR')
            stores.append((label, Path(path)))
        batch = review.sample(stores, args.batch, args.claims, args.abouts, args.pairs, args.seed)
        asked = sum(1 for i in batch['items'] if i.get('request'))
        print(f"{len(batch['items'])} items: first judge the questions blind ({asked} recorded) in "
              f"{args.batch / 'questions.html'}, then the answers in {args.batch / 'review.html'}")
    elif args.command == 'import':
        for path in args.labels:
            target, count = review.import_labels(args.batch, path)
            print(f'{count} labels from {path} -> {target}')
    elif args.command == 'judge':
        start_logging(args)
        budget = Budget(args.max_cost)  # for the whole command, not each model
        for model in args.model:
            if budget.exhausted():
                log.warning(f'cost cap of ${args.max_cost:.2f} reached before judging with {model}')
                return 3
            settings = evaluator_settings(model, concurrency=16, timeout=600, retries=2, **budget.settings())
            with folder_client(args.batch, settings) as client:
                attach_ledger(client, RunOptions.from_args(args))
                progress = Progress(f'judge {model}', client, heartbeat=settings.heartbeat_seconds)
                target, count, failures = review.judge(args.batch, client, model, args.limit, progress, args.stage)
                progress.close()
            budget.add(client)
            for failure in failures[:5]:
                log.warning(f'{model}: {failure}')
            print(f"{model}: {count} labels -> {target}; {client.calls} calls, "
                  f"{client.usage['prompt_tokens']} prompt and {client.usage['completion_tokens']} completion tokens, "
                  f"${client.cost:.3f}")
            note = budget_note(client)
            if note:
                log.warning(note)
                return 3
    elif args.command == 'consensus':
        print(json.dumps(review.consensus(args.batch, gate=args.gate, stage=args.stage), indent=2))
    elif args.command == 'question-agreement':
        print(json.dumps(review.question_agreement(args.batch), indent=2))
    elif args.command == 'agreement':
        print(json.dumps(review.agreement(args.batch), indent=2))
    elif args.command == 'scores':
        print(json.dumps(review.scores(args.batch), indent=2))
    else:
        review.write_page(args.batch, json.loads((args.batch / 'batch.json').read_text(encoding='utf-8')))
        print(f"Rewrote {args.batch / 'questions.html'} and {args.batch / 'review.html'}")
    return 0
