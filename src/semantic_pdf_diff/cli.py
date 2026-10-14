"""Command line: compare two sources, and manage declared sources in a store.

    pdf-semantic-diff A B --out DIR                     # shortcut: A and B are files, folders or zips
    pdf-semantic-diff compare --store DIR NAME NAME     # declared sources, or --manifest FILE
    pdf-semantic-diff source add|list|show|update|remove|export|import ...
    pdf-semantic-diff show|gc|report --store DIR ...
    pdf-semantic-diff settings [--config FILE] [--changed]
    pdf-semantic-diff fixtures summary|pack|prune|merge ...
    pdf-semantic-diff review|queries ...                # with the lab installed (semantic-pdf-diff[lab])
"""
import argparse
import csv
import json
import sys
from pathlib import Path
from . import __version__, fixtures, manifest
from .pipeline import RunOptions, attempt, compare_paths, document_properties, limits, run, settings_from
from .schema import Source
from .progress import log, setup_logging
from .report import write_report
from .store import Store, StoreError


# the entry-point group installed extras add commands to (the lab's: review, queries)
COMMANDS = "semantic_pdf_diff.commands"

def lab_commands():
    """{name: command(argv) -> exit code} from installed distributions (pip install semantic-pdf-diff[lab])."""
    from importlib.metadata import entry_points
    return {e.name: e.load() for e in entry_points(group=COMMANDS)}

def main(argv=None, client=None):
    """The command line. client: a model client the comparing commands use (a caller's: tests)."""
    return attempt(command, list(sys.argv[1:] if argv is None else argv), client)

def command(argv, client):
    """The command argv names, run: its exit code."""
    if not argv:
        print(shortcut_parser().format_help())
        return 1
    if argv[0] == 'help':  # "help source add" is "source add --help"
        argv = [*argv[1:], '--help']
    if argv[0] == 'source':
        return source_command(argv[1:])
    if argv[0] == 'compare':
        return compare_command(argv[1:], client)
    if argv[0] in ('show', 'gc', 'report'):
        return store_command(argv[0], argv[1:])
    if argv[0] == 'settings':
        return settings_command(argv[1:])
    if argv[0] == 'fixtures':
        return fixtures_command(argv[1:])
    lab = lab_commands().get(argv[0])
    if lab:
        return lab(argv[1:])
    return shortcut_command(argv, client)

# What `pdf-semantic-diff --help` says before and after the two-source options: someone installing the tool on
# another machine has only this, not the docs (the owner, 2026-10-14: "it doesn't even mention the `source add`
# options").
COMMANDS_HELP = """\
Evidence-first comparison of engineering documents: competing proposals, or revisions of one design. A vision
model behind an OpenAI-compatible endpoint reads claims from text, tables, charts and drawings; related claims are
paired, and differences are reported with the page and region each claim came from. Nothing is ranked, and a claim
with no counterpart isn't taken as proof of absence.

Commands (pdf-semantic-diff help COMMAND, or COMMAND --help):
  A B         compare two files, folders or zip archives (the options below)
  compare     compare two sources declared in a store, by name
  source      declare sources in a store and manage them: add, list, show, update, remove, export, import
  show        print a view of a store: its sources, files, evidence, coverage or comparisons
  report      write a store's report again, without model calls
  gc          delete content no declared source uses any more
  settings    print the settings a run would use, and their names for --config
  fixtures    recorded model answers, replayed instead of asked (testing)
"""

START_HELP = """\
Before a first run, name the model and its endpoint (a .env file isn't read):
  export OPENAI_API_KEY=...                            the provider's key
  export OPENAI_BASE_URL=https://provider.example/v1   default: {base_url}
  export OPENAI_MODEL=provider/vision-model            default: {model}
Any other setting goes in a --config JSON file, or the environment as PDF_DIFF_<NAME>: see
`pdf-semantic-diff settings`.

Examples:
  pdf-semantic-diff team-a.pdf team-b.pdf --out result           two proposals; open result/report.html
  pdf-semantic-diff old.pdf new.pdf --mode revisions --out diff   a revision: the earlier one first
  pdf-semantic-diff team-a/ team-b.zip --out result --max-cost 2  stop asking once $2 is reported spent
  pdf-semantic-diff source add team-a --store work --path team-a/ --meta organization="Team A"
  pdf-semantic-diff source add team-b --store work --path team-b.zip
  pdf-semantic-diff compare --store work team-a team-b

The --out (or --store) folder is a store. It receives report.html (keep its assets/ folder beside it), report.json
and evidence.json. A run into it again reuses what was read, and resumes one interrupted.

Exit codes: 0 complete (uncertainty may remain); 2 incomplete coverage or processing failures; 1 an error.
"""

def help_text(parser, epilog=None, description=None):
    """parser with its text shown as written (examples keep their lines)."""
    parser.formatter_class = argparse.RawDescriptionHelpFormatter
    if description:
        parser.description = description
    if epilog:
        parser.epilog = epilog
    return parser

def default(name):
    from .settings import Settings
    return Settings.model_fields[name].get_default(call_default_factory=True)

# --- options shared by commands that run the model ---------------------------------

def add_log_options(parser):
    parser.add_argument('-q', '--quiet', action='store_true', help='Warnings and errors only')
    parser.add_argument('-v', '--verbose', action='count', default=0, help='-v: tasks; -vv: also each model request')
    parser.add_argument('--log-file', type=Path, help='Also write a detailed log here')

def start_logging(args):
    setup_logging(getattr(args, 'verbose', 0), getattr(args, 'quiet', False), getattr(args, 'log_file', None))

def add_run_options(parser):
    reading = parser.add_argument_group('comparing and reading')
    reading.add_argument('--mode', choices=['proposals', 'revisions'], default='proposals',
                         help='Proposals (the default): two competing designs, side by side. revisions: the first '
                              'source is the earlier revision of one design and the second the later; differences '
                              'are named as changes (a value or its conditions changed, renamed, restated, moved)')
    reading.add_argument('--config', type=Path,
                         help='A settings JSON file, e.g. {"concurrency": 6}; `pdf-semantic-diff settings` lists '
                              'every setting. The environment gives defaults, the file overrides them, and these '
                              'flags override both')
    reading.add_argument('--no-vision', action='store_true',
                         help='Read text only: no pictures of pages, tables, charts or drawings. The report says '
                              'what went unread')
    reading.add_argument('--no-situate', action='store_true',
                         help='Skip the figure and section summaries ("about" statements) that place claims')
    reading.add_argument('--top-k', type=int,
                         help=f'Claims of the other source each claim is compared with (default: {default("top_k")})')
    model = parser.add_argument_group('the model')
    model.add_argument('--model', help=f'The model identifier the provider uses (default: $OPENAI_MODEL, else '
                                       f'{default("model")})')
    model.add_argument('--base-url', help=f'The provider\'s OpenAI-compatible API, with /v1 where it needs it '
                                          f'(default: $OPENAI_BASE_URL, else {default("base_url")})')
    model.add_argument('--context-tokens', type=int,
                       help=f'The model\'s context window in tokens; queries are sized to fit '
                            f'(default: {default("context_tokens")})')
    budget = parser.add_argument_group('budget')
    budget.add_argument('--max-calls', type=int,
                        help=f'The most requests to send, retries not counted (default: {default("max_calls")})')
    add_budget_options(budget)
    store = parser.add_argument_group('the store')
    store.add_argument('--reset', action='store_true',
                       help='A store remembers the model and settings it was read with, and refuses a run with '
                            'others, saying what differs: --reset clears what they change, then runs')
    store.add_argument('--dry-run', action='store_true',
                       help='With --reset: say what would be cleared, and change nothing')
    add_log_options(parser.add_argument_group('output'))
    recorded = parser.add_argument_group('recorded answers (testing, and runs without the model)')
    recorded.add_argument('--fixture', type=Path,
                          help='Answers fixture: answers recorded in it are replayed, not asked again. A .sqlite '
                               'file also records new answers (created if missing); a .zip is replayed only')
    recorded.add_argument('--fixture-mode', choices=fixtures.MODES,
                          help='replay: fail requests with no recorded answer (tests, CI); replay-or-record (a '
                               ".sqlite file's default): ask the model and record, recorded failures asked again; "
                               'record-new: record only requests never asked')
    recorded.add_argument('--responder', help='Whose recorded answers to use or record (default: the model name)')
    recorded.add_argument('--fresh-regions', default='', metavar='REGIONS',
                          help='A/A control: answer extraction for these regions (e.g. tile,figure,overview) afresh, '
                               'as a second sample of each query')

def add_budget_options(parser):
    parser.add_argument('--max-cost', type=float,
                        help='Stop sending once the provider-reported cost reaches this many dollars (a response '
                             'without a reported cost counts nothing, with a warning)')
    parser.add_argument('--ledger', type=Path, help='Append every response\'s reported cost to this JSON-lines file')
    parser.add_argument('--ledger-tag', action='append', default=[], metavar='KEY=VALUE',
                        help='Tag ledger records, e.g. round=r01 step=record (repeatable)')


def load_settings(args):
    """The environment, then --config, then the flags."""
    flags = {name: getattr(args, name)
             for name in ['model', 'base_url', 'context_tokens', 'max_calls', 'top_k', 'max_cost']
             if getattr(args, name, None) is not None}
    if getattr(args, 'no_vision', False):
        flags['vision'] = False
    if getattr(args, 'no_situate', False):
        flags['situate'] = False
    return settings_from(getattr(args, 'config', None), **flags)


# --- shortcut: two paths ------------------------------------------------------------

def shortcut_parser():
    commands = COMMANDS_HELP + "".join(f"  {name:<11} the lab's (semantic-pdf-diff[lab])\n"
                                       for name in sorted(lab_commands()))
    parser = argparse.ArgumentParser(prog='pdf-semantic-diff', usage='%(prog)s A B [--out DIR] [options]\n'
                                     '       %(prog)s COMMAND [options]   (COMMAND: see below)')
    help_text(parser, START_HELP.format(base_url=default('base_url'), model=default('model')), commands)
    parser.add_argument('--version', action='version', version=f'%(prog)s {__version__}')
    parser.add_argument('a', type=Path, help='The first source (a file, folder or zip archive): proposal A, or the '
                                             'earlier revision')
    parser.add_argument('b', type=Path, help='The second: proposal B, or the later revision')
    parser.add_argument('--out', type=Path, default=Path('diff-output'),
                        help='The store folder, created if missing (default: diff-output). It receives the reports '
                             'too')
    add_run_options(parser)
    return parser

def shortcut_command(argv, client=None):
    args = shortcut_parser().parse_args(argv)
    start_logging(args)
    settings = load_settings(args)
    return compare_paths(args.a, args.b, args.out, settings, RunOptions.from_args(args), client)


# --- compare declared sources ---------------------------------------------------------

def compare_parser():
    parser = help_text(argparse.ArgumentParser(prog='pdf-semantic-diff compare'), COMPARE_EXAMPLES,
                       'Compare two sources declared in a store (`pdf-semantic-diff source add`), by name. Each is '
                       'rescanned first,\nso files edited, added or removed since are picked up.')
    parser.add_argument('sources', nargs='*', help='The two sources\' names: proposal A then B, or the earlier '
                                                   'revision then the later')
    parser.add_argument('--manifest', action='append', type=Path, default=[],
                        help='A manifest file as a source, linked live: re-imported when it changes')
    parser.add_argument('--store', type=Path, required=True, help='The store folder holding the sources')
    parser.add_argument('--report', type=Path, help='Report folder (default: the store folder)')
    add_run_options(parser)
    return parser

def compare_command(argv, client=None):
    args = compare_parser().parse_args(argv)
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

def fixtures_parser():
    parser = argparse.ArgumentParser(prog='pdf-semantic-diff fixtures',
                                     description='Replay fixtures of recorded answers.')
    commands = parser.add_subparsers(dest='command', required=True, metavar='COMMAND')
    def sub_parser(name, help):
        return commands.add_parser(name, help=help, description=help)
    summary = sub_parser('summary', help='What a fixture holds: requests, answers per responder, tokens')
    summary.add_argument('fixture', type=Path, help='A .sqlite or .zip fixture')
    pack = sub_parser('pack', help='Zip a fixture reproducibly (unchanged data gives identical bytes)')
    pack.add_argument('fixture', type=Path, help='The .sqlite working fixture')
    pack.add_argument('target', type=Path, help='The .zip to write')
    prune = sub_parser('prune', help='Drop answers not replayed or recorded since a time (after prompt changes)')
    prune.add_argument('fixture', type=Path, help='The .sqlite working fixture')
    prune.add_argument('--unused-since', required=True, help='ISO time, e.g. noted before replaying every run')
    prune.add_argument('--responder', help="Only this responder's answers (default: every responder's)")
    prune.add_argument('--dry-run', action='store_true', help='Say what would be dropped, change nothing')
    prune.add_argument('--force', action='store_true',
                       help='prune even if no run since then used the fixture, a run missed requests, '
                            'or most answers go')
    merge = sub_parser('merge', help="Copy in the answers other fixtures hold that a working fixture lacks (the "
                                         "same queries, so the same answers: a variant's recording seeds another's)")
    merge.add_argument('fixture', type=Path, help='the .sqlite working fixture, created if missing')
    merge.add_argument('sources', type=Path, nargs='+', help='.zip or .sqlite fixtures')
    return parser

def fixtures_command(argv):
    args = fixtures_parser().parse_args(argv)
    if args.command == 'merge':
        if args.fixture.suffix != '.sqlite':
            print(f'{args.fixture}: merge into a .sqlite working fixture (then pack it)', file=sys.stderr)
            return 1
        with fixtures.open(args.fixture, 'record') as fixture:
            try:
                added = {str(source): fixture.merge(source) for source in args.sources}
            except (fixtures.FixtureError, OSError) as e:
                print(e, file=sys.stderr)
                return 1
        print(json.dumps({"answers_added": added}))
        return 0
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


# --- settings ------------------------------------------------------------------------

SETTINGS_HELP = """\
Print the settings a run would use, as JSON: the defaults, then the environment's, then --config's. Any of them can
go in a --config file ({"concurrency": 6}), or the environment as PDF_DIFF_<NAME> (PDF_DIFF_CONCURRENCY=6); the
model and endpoint as OPENAI_MODEL and OPENAI_BASE_URL. The API key (OPENAI_API_KEY) is never printed.

Settings that shape what's asked (extraction, levers) are bound to a store: a run with others is refused, saying
what differs, unless --reset is given.
"""

def settings_parser():
    parser = help_text(argparse.ArgumentParser(prog='pdf-semantic-diff settings'), description=SETTINGS_HELP)
    parser.add_argument('--config', type=Path, help='A settings JSON file, applied over the environment')
    parser.add_argument('--changed', action='store_true',
                        help='Only the settings that differ from the defaults (a starting --config file)')
    return parser

def settings_command(argv):
    from .llm import redact_url
    from .settings import Settings
    args = settings_parser().parse_args(argv)
    settings = settings_from(args.config)
    from .levers import declared
    dumped = settings.model_dump(mode='json')
    endpoint = {k: v for k, v in dumped.items() if declared(Settings, k).kind == 'endpoint'}  # model and endpoint first
    shown = {**endpoint, 'base_url': redact_url(endpoint['base_url']), **settings.configuration()}
    if args.changed:
        defaults = {**Settings().model_dump(mode='json'), **Settings().configuration()}
        shown = {k: v for k, v in shown.items() if v != defaults.get(k)}
    print(json.dumps(shown, indent=2, ensure_ascii=False))
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

SOURCE_HELP = """\
A source is a named set of files: one proposal, or one revision of a design. It's declared once in a store, with
provenance metadata, and compared by name (`pdf-semantic-diff compare`). Its roots are files, folders (read with
their subfolders) and zip archives, rescanned on every comparison.
"""

SOURCE_EXAMPLES = """\
Examples:
  pdf-semantic-diff source add team-a --store work --path team-a/ --path addendum.pdf --meta organization="Team A"
  pdf-semantic-diff source add team-b --store work --path team-b.zip --meta revision=C
  pdf-semantic-diff source list --store work
  pdf-semantic-diff source show team-a --store work          its files, and those skipped and why
  pdf-semantic-diff compare --store work team-a team-b
  pdf-semantic-diff source export team-a --store work --output team-a.source.json --with-hashes
"""

COMPARE_EXAMPLES = """\
Examples:
  pdf-semantic-diff compare --store work team-a team-b
  pdf-semantic-diff compare --store work rev-b rev-c --mode revisions --report reports/b-to-c
  pdf-semantic-diff compare --store work --manifest team-a.source.json team-b
"""

def source_parser():
    parser = help_text(argparse.ArgumentParser(prog='pdf-semantic-diff source'), SOURCE_EXAMPLES,
                       'Declare sources in a store, and manage them.\n\n' + SOURCE_HELP)
    commands = parser.add_subparsers(dest='command', required=True, metavar='COMMAND')
    def command(name, help, description=None):
        sub = help_text(commands.add_parser(name, help=help, description=description or help), SOURCE_EXAMPLES)
        sub.add_argument('--store', type=Path, required=True, help='The store folder (created if missing)')
        sub.add_argument('--config', type=Path, help='Settings JSON (only its archive limits apply here)')
        add_log_options(sub)
        return sub
    add = command('add', 'Declare a source and scan it',
                  'Declare a source and scan it: the files it holds are listed, and any skipped (a type not read, '
                  'an\narchive past its limits) are named with why.\n\n' + SOURCE_HELP)
    add.add_argument('name', help='A name for the source, used by compare (e.g. team-a, rev-c)')
    add.add_argument('--path', action='append', type=Path, required=True,
                     help='A root: file, folder or zip (repeatable)')
    add.add_argument('--meta', action='append', default=[], metavar='KEY=VALUE',
                     help='Provenance metadata kept with the source (source list, manifests), e.g. --meta '
                          'organization="Team A" --meta revision=C (repeatable)')
    command('list', 'List declared sources')
    show = command('show', "Show a source's definition, files and scan issues")
    show.add_argument('name', help="The source's name")
    update = command('update', 'Change a source and rescan it')
    update.add_argument('name', help="The source's name")
    update.add_argument('--path', action='append', type=Path, help='Replace the roots (repeatable)')
    update.add_argument('--meta', action='append', default=[], metavar='KEY=VALUE',
                        help='Set metadata; KEY= removes it')
    remove = command('remove', 'Unregister a source (its content stays until gc)')
    remove.add_argument('name', help="The source's name")
    exporting = command('export', 'Write a manifest for a source',
                        "Write a manifest for a source: its name, metadata and roots as JSON, to declare it in another "
                        "store\n(source import), or to link it live (compare --manifest).")
    exporting.add_argument('name', help="The source's name")
    exporting.add_argument('--output', type=Path, help='Manifest file (default: standard output)')
    exporting.add_argument('--with-hashes', action='store_true',
                           help='Include content hashes so recipients can check files')
    importing = command('import', 'Declare a source from a manifest (a copy, not a live link)')
    importing.add_argument('manifest', type=Path, help='A manifest file (from source export)')
    importing.add_argument('--name', help='Declare under another name')
    return parser

def source_command(argv):
    args = source_parser().parse_args(argv)
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

def store_parser(command):
    parser = argparse.ArgumentParser(prog=f'pdf-semantic-diff {command}')
    parser.add_argument('--store', type=Path, required=True, help='The store folder')
    add_log_options(parser)
    if command == 'show':
        parser.description = 'Print a view of the store.'
        parser.add_argument('view', choices=Store.VIEWS, metavar='VIEW',
                            help='sources: their roots, file counts and metadata; source_files: every file; '
                                 'evidence_occurrences: every claim read, where; coverage_by_source: what was read '
                                 "and what wasn't; orphaned_content: content no source uses (gc removes it); "
                                 'comparisons: the comparisons run, with their ids')
        parser.add_argument('--format', choices=['md', 'csv', 'jsonl'], default='md',
                            help='A Markdown table (the default), CSV, or JSON lines')
    elif command == 'gc':
        parser.description = ('Delete content no declared source uses any more (after source remove or update), '
                              'with its evidence, tasks, sections, cached responses and crops.')
        parser.add_argument('--dry-run', action='store_true', help='Report what would be removed, change nothing')
        parser.add_argument('--orphaned-sources', action='store_true',
                            help='Also remove sources whose linked manifest file no longer exists')
    else:
        parser.description = 'Regenerate a report from a saved comparison, without model calls.'
        parser.add_argument('--comparison', type=int, help='Comparison id (see: show comparisons); default: latest')
        parser.add_argument('--out', type=Path, help='Report folder (default: the store folder)')
    return parser

def store_command(command, argv):
    args = store_parser(command).parse_args(argv)
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
    log.info(f"Scanned {name}: {summary['files']} files ({len(summary['added'])} added, "
             f"{len(summary['removed'])} removed, {len(summary['changed'])} changed), "
             f"{len(summary['issues'])} issue(s)")
    for path, reason in summary['issues'][:20]:
        log.info(f'  {path}: {reason}')

if __name__ == '__main__':
    sys.exit(main())
