"""Command line: compare two sources, and manage declared sources in a store.

    pdf-semantic-diff A B --out DIR                     # shortcut: A and B are files, folders or zips
    pdf-semantic-diff compare --store DIR NAME NAME     # declared sources, or --manifest FILE
    pdf-semantic-diff source add|list|show|update|remove|export|import ...
    pdf-semantic-diff show|gc|report --store DIR ...
    pdf-semantic-diff fixtures summary|pack|prune ...
    pdf-semantic-diff review|queries ...                # with the lab installed (semantic-pdf-diff[lab])
"""
import argparse
import csv
import json
import sys
from pathlib import Path
from . import fixtures, manifest
from .pipeline import RunOptions, compare_paths, document_properties, limits, run
from .schema import Source
from .settings import Settings
from .progress import log, setup_logging
from .report import write_report
from .store import Store, StoreError


COMMANDS = "semantic_pdf_diff.commands"  # the entry-point group installed extras add commands to (the lab's: review, queries)

def lab_commands():
    """{name: command(argv) -> exit code} from installed distributions (pip install semantic-pdf-diff[lab])."""
    from importlib.metadata import entry_points
    return {e.name: e.load() for e in entry_points(group=COMMANDS)}

def main(argv=None, client=None):
    """The command line. client: a model client the comparing commands use (a caller's: tests)."""
    argv = list(sys.argv[1:] if argv is None else argv)
    try:
        if argv and argv[0] == 'source':
            return source_command(argv[1:])
        if argv and argv[0] == 'compare':
            return compare_command(argv[1:], client)
        if argv and argv[0] in ('show', 'gc', 'report'):
            return store_command(argv[0], argv[1:])
        if argv and argv[0] == 'fixtures':
            return fixtures_command(argv[1:])
        command = argv and lab_commands().get(argv[0])
        if command:
            return command(argv[1:])
        return shortcut_command(argv, client)
    except (OSError, ValueError, RuntimeError) as e:
        print(f'Error: {e}', file=sys.stderr)
        return 1

# --- options shared by commands that run the model ---------------------------------

def add_log_options(parser):
    parser.add_argument('-q', '--quiet', action='store_true', help='Warnings and errors only')
    parser.add_argument('-v', '--verbose', action='count', default=0, help='-v: tasks; -vv: also each model request')
    parser.add_argument('--log-file', type=Path, help='Also write a detailed log here')

def start_logging(args):
    setup_logging(getattr(args, 'verbose', 0), getattr(args, 'quiet', False), getattr(args, 'log_file', None))

def add_run_options(parser):
    add_log_options(parser)
    parser.add_argument('--config', type=Path, help='Settings JSON; overrides environment defaults, CLI flags override it')
    parser.add_argument('--mode', choices=['proposals', 'revisions'], default='proposals')
    parser.add_argument('--model')
    parser.add_argument('--base-url')
    parser.add_argument('--context-tokens', type=int)
    parser.add_argument('--max-calls', type=int)
    parser.add_argument('--top-k', type=int)
    parser.add_argument('--no-vision', action='store_true', help='Explicitly incomplete text-only run')
    parser.add_argument('--no-situate', action='store_true', help='Skip figure and section "about" statements')
    parser.add_argument('--fixture', type=Path,
                        help='Answers fixture: answers recorded in it are replayed, not asked again. A .sqlite file '
                             'also records new answers (created if missing); a .zip is replayed only')
    parser.add_argument('--fixture-mode', choices=fixtures.MODES,
                        help='replay: fail requests with no recorded answer (tests, CI); replay-or-record (a .sqlite '
                             "file's default): ask the model and record, recorded failures asked again; record-new: "
                             'record only requests never asked')
    parser.add_argument('--responder', help='Whose recorded answers to use or record (default: the model name)')
    parser.add_argument('--fresh-regions', default='', metavar='REGIONS',
                        help='A/A control: answer extraction for these regions (e.g. tile,figure,overview) afresh, '
                             'as a second sample of each query')
    add_budget_options(parser)
    parser.add_argument('--reset', action='store_true',
                        help='Clear derived data affected by a changed extraction interpreter, then run')
    parser.add_argument('--dry-run', action='store_true', help='With --reset: report what would be cleared, change nothing')

def add_budget_options(parser):
    parser.add_argument('--max-cost', type=float, help='Stop sending once the provider-reported cost reaches this many dollars')
    parser.add_argument('--ledger', type=Path, help='Append every response\'s reported cost to this JSON-lines file')
    parser.add_argument('--ledger-tag', action='append', default=[], metavar='KEY=VALUE',
                        help='Tag ledger records, e.g. round=r01 step=record (repeatable)')


def load_settings(args):
    options = json.loads(args.config.read_text()) if getattr(args, 'config', None) else {}
    if not isinstance(options, dict):
        raise ValueError(f'{args.config}: settings file must contain a JSON object')
    for name in ['model', 'base_url', 'context_tokens', 'max_calls', 'top_k', 'max_cost']:
        if getattr(args, name, None) is not None:
            options[name] = getattr(args, name)
    if getattr(args, 'no_vision', False):
        options['vision'] = False
    if getattr(args, 'no_situate', False):
        options['situate'] = False
    return Settings.from_env(**options)


# --- shortcut: two paths ------------------------------------------------------------

def shortcut_command(argv, client=None):
    parser = argparse.ArgumentParser(prog='pdf-semantic-diff',
        description='Evidence-first comparison of two sources (files, folders or zip archives) using a small '
                    'OpenAI-compatible VLM. See also: pdf-semantic-diff source --help, compare --help.')
    parser.add_argument('a', type=Path, help='First source: proposal A, or the earlier revision')
    parser.add_argument('b', type=Path, help='Second source: proposal B, or the later revision')
    parser.add_argument('--out', type=Path, default=Path('diff-output'),
                        help='Store folder; also receives report.html, report.json and evidence.json')
    add_run_options(parser)
    args = parser.parse_args(argv)
    start_logging(args)
    settings = load_settings(args)
    return compare_paths(args.a, args.b, args.out, settings, RunOptions.from_args(args), client)


# --- compare declared sources ---------------------------------------------------------

def compare_command(argv, client=None):
    parser = argparse.ArgumentParser(prog='pdf-semantic-diff compare', description='Compare two sources declared in a store.')
    parser.add_argument('sources', nargs='*', help='Names of declared sources')
    parser.add_argument('--manifest', action='append', type=Path, default=[],
                        help='A manifest file as a source, linked live: re-imported when it changes')
    parser.add_argument('--store', type=Path, required=True)
    parser.add_argument('--report', type=Path, help='Report folder (default: the store folder)')
    add_run_options(parser)
    args = parser.parse_args(argv)
    start_logging(args)
    settings = load_settings(args)
    with Store(args.store) as store:
        names = list(args.sources)
        for path in args.manifest:
            names.append(link_manifest(store, path))
        if len(names) != 2:
            raise ValueError(f'compare needs exactly two sources, got {len(names)}')
        missing = [n for n in names if store.source(n) is None]
        if missing:
            raise StoreError(f"no declared source named {', '.join(map(repr, missing))} in {args.store}")
        return run(RunOptions.from_args(args), settings, store, names, args.report or args.store, client=client)

def link_manifest(store, path):
    """Declare or refresh a source linked to a manifest file; returns its name."""
    source, _, digest = manifest.load(path, kind='manifest')
    existing = store.source(source.name)
    if existing and (existing.kind != 'manifest' or existing.manifest != source.manifest):
        raise StoreError(f"source {source.name!r} already exists and isn't linked to {path}")
    if not existing or store.manifest_hash(source.name) != digest:
        store.save_source(source, replace=True, manifest_hash=digest)
        log.info(f"{'Updated' if existing else 'Linked'} source {source.name!r} from {path}")
    return source.name

def fixtures_command(argv):
    parser = argparse.ArgumentParser(prog='pdf-semantic-diff fixtures', description='Replay fixtures of recorded answers.')
    sub = parser.add_subparsers(dest='command', required=True)
    summary = sub.add_parser('summary', help='What a fixture holds: requests, answers per responder, tokens')
    summary.add_argument('fixture', type=Path)
    pack = sub.add_parser('pack', help='Zip a fixture reproducibly (unchanged data gives identical bytes)')
    pack.add_argument('fixture', type=Path)
    pack.add_argument('target', type=Path)
    prune = sub.add_parser('prune', help='Drop answers not replayed or recorded since a time (after prompt changes)')
    prune.add_argument('fixture', type=Path)
    prune.add_argument('--unused-since', required=True, help='ISO time, e.g. noted before replaying every run')
    prune.add_argument('--responder')
    prune.add_argument('--dry-run', action='store_true')
    prune.add_argument('--force', action='store_true',
                       help='prune even if no run since then used the fixture, a run missed requests, or most answers go')
    args = parser.parse_args(argv)
    if args.command == 'prune':
        if args.fixture.suffix != '.sqlite' or not args.fixture.exists():  # a .zip once crashed here
            print(f'{args.fixture}: prune works on a .sqlite working fixture (then pack it again)', file=sys.stderr)
            return 1
        with fixtures.open(args.fixture, 'record') as fixture:
            try:
                print(json.dumps(fixture.prune(args.unused_since, args.responder, args.dry_run, args.force)))
            except fixtures.FixtureError as e:
                print(e, file=sys.stderr)
                return 1
        return 0
    if args.command == 'summary':
        with fixtures.open(args.fixture, 'read') as fixture:
            print(json.dumps(fixture.summary(), indent=2))
    else:
        fixtures.pack(args.fixture, args.target)
        print(f'Packed {args.target}')
    return 0


# --- source management ---------------------------------------------------------------

def parse_meta(pairs):
    metadata = {}
    for pair in pairs:
        key, sep, value = pair.partition('=')
        if not sep or not key.strip():
            raise ValueError(f'--meta expects KEY=VALUE, got {pair!r}')
        metadata[key.strip()] = value
    return metadata

def source_command(argv):
    parser = argparse.ArgumentParser(prog='pdf-semantic-diff source', description='Manage sources declared in a store.')
    commands = parser.add_subparsers(dest='command', required=True)
    def command(name, help):
        sub = commands.add_parser(name, help=help)
        sub.add_argument('--store', type=Path, required=True)
        sub.add_argument('--config', type=Path, help='Settings JSON (archive limits)')
        add_log_options(sub)
        return sub
    add = command('add', 'Declare a source and scan it')
    add.add_argument('name')
    add.add_argument('--path', action='append', type=Path, required=True, help='A root: file, folder or zip (repeatable)')
    add.add_argument('--meta', action='append', default=[], metavar='KEY=VALUE', help='Provenance metadata (repeatable)')
    command('list', 'List declared sources')
    show = command('show', "Show a source's definition, files and scan issues")
    show.add_argument('name')
    update = command('update', 'Change a source and rescan it')
    update.add_argument('name')
    update.add_argument('--path', action='append', type=Path, help='Replace the roots (repeatable)')
    update.add_argument('--meta', action='append', default=[], metavar='KEY=VALUE', help='Set metadata; KEY= removes it')
    remove = command('remove', 'Unregister a source (its content stays until gc)')
    remove.add_argument('name')
    exporting = command('export', 'Write a manifest for a source')
    exporting.add_argument('name')
    exporting.add_argument('--output', type=Path, help='Manifest file (default: standard output)')
    exporting.add_argument('--with-hashes', action='store_true', help='Include content hashes so recipients can check files')
    importing = command('import', 'Declare a source from a manifest (a copy, not a live link)')
    importing.add_argument('manifest', type=Path)
    importing.add_argument('--name', help='Declare under another name')
    args = parser.parse_args(argv)
    start_logging(args)
    settings = load_settings(args)
    with Store(args.store) as store:
        if args.command == 'add':
            roots = [str(p.resolve()) for p in args.path]
            store.save_source(Source(name=args.name, metadata=parse_meta(args.meta), roots=roots))
            print_scan(store.rescan(args.name, limits(settings), document_properties), args.name)
        elif args.command == 'list':
            for source in store.sources():
                note = ''
                if source.manifest and not Path(source.manifest).exists():
                    note = '  (manifest missing: orphaned)'
                print(f"{source.name}\t{source.kind}\t{len(store.files(source.name))} files\t"
                      f"{json.dumps(source.metadata, ensure_ascii=False)}{note}")
        elif args.command == 'show':
            source = require(store, args.name)
            print(json.dumps({'source': source.model_dump(), 'files': [f.model_dump() for f in store.files(args.name)],
                              'issues': [{'path': p, 'reason': r} for p, r in store.issues(args.name)]},
                             indent=2, ensure_ascii=False))
        elif args.command == 'update':
            source = require(store, args.name)
            metadata = {**source.metadata, **parse_meta(args.meta)}
            metadata = {k: v for k, v in metadata.items() if v != ''}
            roots = [str(p.resolve()) for p in args.path] if args.path else source.roots
            store.save_source(source.model_copy(update={'metadata': metadata, 'roots': roots}), replace=True)
            print_scan(store.rescan(args.name, limits(settings), document_properties), args.name)
        elif args.command == 'remove':
            store.remove_source(args.name)
            log.info(f'Removed source {args.name!r}; {len(store.orphaned_content())} content item(s) now orphaned')
        elif args.command == 'export':
            source = require(store, args.name)
            text = manifest.export(source, store.files(args.name) if args.with_hashes else (), args.output)
            if args.output:
                args.output.write_text(text, encoding='utf-8')
            else:
                sys.stdout.write(text)
        elif args.command == 'import':
            source, expected, _ = manifest.load(args.manifest, name=args.name)
            store.save_source(source)
            print_scan(store.rescan(source.name, limits(settings), document_properties), source.name)
            different = manifest.mismatches(expected, store.files(source.name))
            if different:
                log.warning(f"Warning: {len(different)} file(s) differ from the manifest's hashes: {different[:5]}")
    return 0

def store_command(command, argv):
    parser = argparse.ArgumentParser(prog=f'pdf-semantic-diff {command}')
    parser.add_argument('--store', type=Path, required=True)
    add_log_options(parser)
    if command == 'show':
        parser.description = 'Print a view of the store.'
        parser.add_argument('view', choices=Store.VIEWS)
        parser.add_argument('--format', choices=['md', 'csv', 'jsonl'], default='md')
    elif command == 'gc':
        parser.description = 'Delete orphaned content with its evidence, tasks, sections, cached responses and crops.'
        parser.add_argument('--dry-run', action='store_true', help='Report what would be removed, change nothing')
        parser.add_argument('--orphaned-sources', action='store_true',
                            help='Also remove sources whose linked manifest file no longer exists')
    else:
        parser.description = 'Regenerate a report from a saved comparison, without model calls.'
        parser.add_argument('--comparison', type=int, help='Comparison id (see: show comparisons); default: latest')
        parser.add_argument('--out', type=Path, help='Report folder (default: the store folder)')
    args = parser.parse_args(argv)
    start_logging(args)
    if not (args.store / 'store.sqlite').exists():
        raise StoreError(f'{args.store} is not a store')
    # show and report only read: no writer's lock, so a store can be looked at during a run (review 2026-10-08, C8)
    with (Store(args.store) if command == 'gc' else Store.open(args.store)) as store:
        if command == 'show':
            print_rows(store.view(args.view), args.format)
        elif command == 'gc':
            print(json.dumps(store.gc(dry_run=args.dry_run, orphaned_sources=args.orphaned_sources), indent=2))
        else:
            out = args.out or args.store
            write_report(store.comparison(args.comparison), out, assets=store.folder / 'assets')
            print(f"Report: {out / 'report.html'}")
    return 0

def print_rows(rows, style):
    if style == 'jsonl':
        for row in rows:
            print(json.dumps(row, ensure_ascii=False))
        return
    columns = list(dict.fromkeys(k for row in rows for k in row))
    if style == 'csv':
        writer = csv.DictWriter(sys.stdout, columns, lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)
        return
    cell = lambda v: '' if v is None else str(v).replace('|', '\\|').replace('\n', ' ')
    print('| ' + ' | '.join(columns) + ' |')
    print('|' + '---|' * len(columns))
    for row in rows:
        print('| ' + ' | '.join(cell(row.get(c)) for c in columns) + ' |')

def require(store, name):
    source = store.source(name)
    if source is None:
        raise StoreError(f'no source named {name!r}')
    return source

def print_scan(summary, name):
    log.info(f"Scanned {name}: {summary['files']} files ({len(summary['added'])} added, {len(summary['removed'])} removed, "
             f"{len(summary['changed'])} changed), {len(summary['issues'])} issue(s)")
    for path, reason in summary['issues'][:20]:
        log.info(f'  {path}: {reason}')

if __name__ == '__main__':
    sys.exit(main())
