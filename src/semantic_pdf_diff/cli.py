"""Command line: compare two sources, and manage declared sources in a store.

    pdf-semantic-diff compare A B [--store DIR]         # files, folders, zips or declared sources' names
    pdf-semantic-diff source add|list|show|update|remove|export|import ...
    pdf-semantic-diff show|gc|report --store DIR ...
    pdf-semantic-diff settings [--config FILE] [--changed]
    pdf-semantic-diff fixtures summary|pack|prune|merge ...
    pdf-semantic-diff review|queries ...                # with the lab installed (semantic-pdf-diff[lab])
"""
import argparse
import csv
import json
import os
import sys
from pathlib import Path
from . import __version__, configuration, crops, fixtures, manifest
from .pipeline import (RunOptions, attempt, check_fixture, declare_paths, document_properties, limits, run,
                       settings_from)
from .schema import Source
from .progress import log, setup_logging
from .report import SPLIT, write_report
from .store import Store, StoreError


# the entry-point group installed extras add commands to (the lab's: review, queries)
COMMANDS = "semantic_pdf_diff.commands"

def lab_commands():
    """{name: command(argv) -> exit code} from installed distributions (pip install semantic-pdf-diff[lab])."""
    from importlib.metadata import entry_points
    return {e.name: e.load() for e in entry_points(group=COMMANDS)}

class Parser(argparse.ArgumentParser):
    """A command's parser: a usage error exits 1, an input error as the exit codes say (argparse's own 2 would read
    as a run with incomplete coverage). Subparsers are made of the same class."""
    def error(self, message):
        self.print_usage(sys.stderr)
        self.exit(1, f'{self.prog}: error: {message}\n')

def main(argv=None, client=None):
    """The command line. client: a model client the comparing commands use (a caller's: tests)."""
    return attempt(command, list(sys.argv[1:] if argv is None else argv), client)

def command(argv, client):
    """The command argv names, run: its exit code."""
    if not argv or argv[0] in ('-h', '--help'):
        print(overview_parser().format_help())
        return 0 if argv else 1
    if argv[0] == '--version':
        print(f'pdf-semantic-diff {__version__}')
        return 0
    if argv[0] == 'help':  # "help source add" is "source add --help"
        argv = [*argv[1:], '--help']
        if argv == ['--help']:
            return command(argv, client)
    if argv[0] == 'source':
        return source_command(argv[1:])
    if argv[0] == 'compare':
        return compare_command(argv[1:], client)
    if argv[0] in ('show', 'gc', 'report'):
        return store_command(argv[0], argv[1:])
    if argv[0] == 'settings':
        return settings_command(argv[1:])
    if argv[0] == 'config':
        return config_command(argv[1:])
    if argv[0] == 'fixtures':
        return fixtures_command(argv[1:])
    lab = lab_commands().get(argv[0])
    if lab:
        return lab(argv[1:])
    hint = f": to compare files, pdf-semantic-diff compare {' '.join(argv[:2])}" if Path(argv[0]).exists() else ""
    print(f"pdf-semantic-diff: no command {argv[0]!r}{hint} (pdf-semantic-diff --help lists them)", file=sys.stderr)
    return 1

# What `pdf-semantic-diff --help` says: someone installing the tool on another machine has only this, not the docs
# (the owner, 2026-10-14: "it doesn't even mention the `source add` options").
COMMANDS_HELP = """\
Evidence-first comparison of engineering documents: competing proposals, or revisions of one design. A vision
model behind an OpenAI-compatible endpoint reads claims from text, tables, charts and drawings; related claims are
paired, and differences are reported with the page and region each claim came from. Nothing is ranked, and a claim
with no counterpart isn't taken as proof of absence.

Commands (pdf-semantic-diff COMMAND --help for each, or pdf-semantic-diff help COMMAND):
  compare     compare two sources: files, folders or zip archives, or sources declared in a store
  source      declare sources in a store and manage them: add, list, show, update, remove, export, import
  show        print a view of a store: its sources, files, evidence, coverage or comparisons
  report      write a store's report again, without model calls
  gc          delete content no declared source uses any more
  config      the user's and a store's settings: show, find, help, set, unset, export, import
  settings    print the settings a run would use, as JSON
  fixtures    recorded model answers, replayed instead of asked (testing)
"""

START_HELP = """\
Before a first run, name the endpoint and the model (a .env file isn't read):
  export OPENAI_API_KEY=...                            the provider's key
  export OPENAI_BASE_URL=https://provider.example/v1   default: {base_url}
  pdf-semantic-diff config set --user model provider/vision-model     default: {model}
A store keeps its own settings: `pdf-semantic-diff config show` lists them, `config set NAME VALUE` sets one
(`config help NAME` says what it does). A run's flags, or a --config JSON file, override them for that run.

Examples:
  pdf-semantic-diff compare team-a.pdf team-b.pdf --store result           two proposals; open result/report.html
  pdf-semantic-diff compare old.pdf new.pdf --mode revisions --store diff  a revision: the earlier one first
  pdf-semantic-diff compare team-a/ team-b.zip --max-cost 2                stop asking once $2 is reported spent
  pdf-semantic-diff source add team-a --store work --path team-a/ --meta organization="Team A"
  pdf-semantic-diff source add team-b --store work --path team-b.zip
  pdf-semantic-diff compare team-a team-b --store work                     declared sources, by name

A comparison's --store folder (diff-output unless named) holds what was read, and receives report.html (one file
to keep or send, its crops inside as --report-budget allows), report.json and evidence.json. A comparison into it
again reuses what was read, and resumes one interrupted.

Exit codes: 0 complete (uncertainty may remain); 2 incomplete coverage or processing failures; 1 an error
(a mistyped command or option too).
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
    reading.add_argument('--mode', choices=['proposals', 'revisions'], default=None,
                         help='Proposals (the default, unless the store\'s mode setting says otherwise): two '
                              'competing designs, side by side. Revisions: the first '
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
    reading.add_argument('--rerank', dest='rerank_model', metavar='MODEL',
                         help='Proposals mode: score each claim\'s candidates with this reranker before the judge '
                              '(e.g. Qwen/Qwen3-Reranker-8B on DeepInfra; elsewhere set rerank_url and rerank_api in '
                              'a --config file); pairs below --rerank-threshold are not judged, the rest best first')
    reading.add_argument('--rerank-threshold', type=int, choices=range(1, 11), metavar='1-10',
                         help=f'With --rerank: the least score a pair is judged with, in hundredths (1-10 for '
                              f'0.01-0.10; default: {default("rerank_threshold")})')
    reading.add_argument('--max-pairs', type=int,
                         help=f'The most candidate pairs the model judges, best first; the report says how many were '
                              f'left unjudged (default: {default("max_pairs")})')
    model = parser.add_argument_group('the model')
    model.add_argument('--model', help=f'The model identifier the provider uses (default: the model setting, '
                                       f'`config set [--user] model NAME`, else {default("model")})')
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
    output = parser.add_argument_group('output')
    add_log_options(output)
    add_report_options(output)
    recorded = parser.add_argument_group('recorded answers (testing, and runs without the model)')
    recorded.add_argument('--fixture', type=Path,
                          help='Answers fixture: answers recorded in it are replayed, not asked again. A .sqlite '
                               'file also records new answers (created if missing); a .zip is replayed only')
    recorded.add_argument('--fixture-mode', choices=fixtures.MODES,
                          help='replay: fail requests with no recorded answer (tests, CI); replay-or-record (a '
                               ".sqlite file's default): ask the model and record, recorded failures asked again; "
                               'record-new: record only requests never asked')
    recorded.add_argument('--responder', help='Whose recorded answers to use or record (default: the model name)')
    recorded.add_argument('--fixture-export', type=Path, metavar='FILE',
                          help='Copy every answer this run is served or records into this .sqlite fixture (created '
                               'if missing), to pack instead of pruning the source; with a new --store, since a '
                               'store already holding a region asks nothing for it')
    recorded.add_argument('--fresh-regions', default='', metavar='REGIONS',
                          help='A/A control: answer extraction for these regions (e.g. tile,figure,overview) afresh, '
                               'as a second sample of each query')

def report_size(text):
    """A report's budget in bytes, from "20MB", "500KB", "1.5GB" or a bare number of megabytes."""
    try:
        return configuration.size(text)
    except ValueError as e:
        raise argparse.ArgumentTypeError(str(e)) from None

def add_report_options(parser):
    parser.add_argument('--split', action=argparse.BooleanOptionalAction, default=None,
                        help=f'With more than one pair of files: a report file a pair (its findings, and those '
                             f'reaching other files) and an index, in {SPLIT}/, a folder to zip and send, each file '
                             'within --report-budget; for comparisons too large for one file (default: the store\'s '
                             'split setting, else off)')
    parser.add_argument('--report-budget', type=report_size, default=None, metavar='SIZE',
                        help='report.html is one file holding its crops, in order of value (the findings to check, '
                             'and claims read from charts, diagrams and tables, first) until it reaches this size '
                             f'(default: the store\'s report_budget, else {crops.DEFAULT_BUDGET // 1_000_000}MB; a '
                             'bare number is megabytes; 0 embeds none). `report --dry-run` says what a budget leaves '
                             'out')

def add_budget_options(parser):
    parser.add_argument('--max-cost', type=float,
                        help='Stop sending once the provider-reported cost reaches this many dollars (a response '
                             'without a reported cost counts nothing, with a warning)')
    parser.add_argument('--ledger', type=Path, help='Append every response\'s reported cost to this JSON-lines file')
    parser.add_argument('--ledger-tag', action='append', default=[], metavar='KEY=VALUE',
                        help='Tag ledger records, e.g. round=r01 step=record (repeatable)')


def load_settings(args, layer=None):
    """The environment, then the store's own settings (layer: configuration.py's), then --config, then the
    flags."""
    flags = {name: getattr(args, name)
             for name in ['model', 'base_url', 'context_tokens', 'max_calls', 'top_k', 'max_pairs', 'max_cost',
                          'rerank_model', 'rerank_threshold']
             if getattr(args, name, None) is not None}
    if getattr(args, 'no_vision', False):
        flags['vision'] = False
    if getattr(args, 'no_situate', False):
        flags['situate'] = False
    own = {k: v for k, v in (layer or {}).items() if k not in configuration.RUN_OPTIONS}
    return settings_from(getattr(args, 'config', None), layer=own, **flags)


def overview_parser():
    """What `pdf-semantic-diff --help` prints: the commands, how to start, examples (each command parses its own)."""
    commands = COMMANDS_HELP + "".join(f"  {name:<11} the lab's (semantic-pdf-diff[lab])\n"
                                       for name in sorted(lab_commands()))
    parser = Parser(prog='pdf-semantic-diff', usage='%(prog)s COMMAND [options]')
    help_text(parser, START_HELP.format(base_url=default('base_url'), model=default('model')), commands)
    parser.add_argument('--version', action='version', version=f'%(prog)s {__version__}',
                        help="show the program's version and exit")
    return parser


# --- compare ---------------------------------------------------------------------------

COMPARE_HELP = """\
Compare two sources. Each is a file, folder or zip archive, or the name of a source declared in the store
(`pdf-semantic-diff source add`); a declared name is taken before a path. Sources are rescanned first, so files
edited, added or removed since are picked up.
"""

COMPARE_EXAMPLES = """\
Examples:
  pdf-semantic-diff compare team-a.pdf team-b.pdf --store result
  pdf-semantic-diff compare old.pdf new.pdf --mode revisions --store diff --max-cost 2
  pdf-semantic-diff compare team-a team-b --store work  sources declared in work
  pdf-semantic-diff compare rev-b rev-c --store work --mode revisions --report reports/b-to-c
  pdf-semantic-diff compare --store work --manifest team-a.source.json team-b
"""

def compare_parser():
    parser = help_text(Parser(prog='pdf-semantic-diff compare',
                                               usage='%(prog)s SOURCE SOURCE [--store DIR] [options]'),
                       COMPARE_EXAMPLES, COMPARE_HELP)
    parser.add_argument('sources', nargs='*', metavar='SOURCE',
                        help='Two sources (a file, folder or zip, or a declared source\'s name): proposal A then B, '
                             'or the earlier revision then the later')
    parser.add_argument('--store', type=Path, default=default_store(),
                        help='The store folder, created if missing (default: diff-output). It keeps what was read, '
                             'for the next comparison, and receives the reports unless --report names another')
    parser.add_argument('--report', type=Path, help='Report folder (default: the store folder)')
    parser.add_argument('--manifest', action='append', type=Path, default=[],
                        help='A manifest file (source export) as a source, linked live: re-imported when it changes')
    add_run_options(parser)
    return parser

def compare_command(argv, client=None):
    args = compare_parser().parse_args(argv)
    start_logging(args)
    from .settings import user_settings
    # the user's settings, then the store's own (`config set [--user]`), under --config and the flags
    layer = {**user_settings(), **Store.settings_of(args.store)}
    settings = load_settings(args, layer)
    options = RunOptions.from_args(args, layer)
    check_fixture(options)  # before the store is changed
    with Store(args.store) as store:
        given = [named_or_path(store, args.store, s) for s in args.sources]
        paths = [g for g in given if isinstance(g, Path)]
        declared = iter(declare_paths(store, args.store, paths))
        names = [next(declared) if isinstance(g, Path) else g for g in given]
        names += [link_manifest(store, path) for path in args.manifest]
        if len(names) != 2:
            raise ValueError(f'compare needs exactly two sources, got {len(names)}')
        return run(options, settings, store, names, args.report or args.store, force_rescan=bool(paths),
                   client=client)

def named_or_path(store, folder, given):
    """A declared source's name, or a path (a file, folder or zip) to declare as one."""
    source = store.source(given)
    if source is not None and source.kind != 'shortcut':
        return given
    if Path(given).exists():
        return Path(given)
    if source is not None:  # a path compared before, by the name it was given
        return given
    raise StoreError(f"{given!r} is neither a file, folder or zip archive nor a source declared in {folder}")

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
    parser = Parser(prog='pdf-semantic-diff fixtures',
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
    merge.add_argument('--prefer', action='store_true',
                       help="the sources' answers replace the fixture's own to the same queries (a committed zip "
                            'merged into its archive)')
    return parser

def fixtures_command(argv):
    args = fixtures_parser().parse_args(argv)
    if args.command == 'merge':
        if args.fixture.suffix != '.sqlite':
            print(f'{args.fixture}: merge into a .sqlite working fixture (then pack it)', file=sys.stderr)
            return 1
        with fixtures.open(args.fixture, 'record') as fixture:
            try:
                added = {str(source): fixture.merge(source, prefer=args.prefer) for source in args.sources}
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
Print the settings a run would use, as JSON: the defaults, then the user's (`config set --user`), then a store's
(--store; `config set`), then --config's. The endpoint is OPENAI_BASE_URL's; the API key (OPENAI_API_KEY) is never
printed. `pdf-semantic-diff config show` lists the settings with what each does.

Settings that shape what's asked (extraction, levers) are bound to a store: a run with others is refused, saying
what differs, unless --reset is given.
"""

def default_store():
    """The store a command works on without --store: $PDF_DIFF_STORE, else ./diff-output."""
    return Path(os.environ.get('PDF_DIFF_STORE') or 'diff-output')

CONFIG_HELP = """\
A store keeps its own settings: set once, they apply to every run in it (a run's flags override them for that
run only). The user's settings (--user) lie under every store's: the endpoint's model and context, concurrency, a
reranker. Names are the settings' own (max_cost, report_budget, rerank_threshold).

  pdf-semantic-diff config show                     the settings most runs set, by group
  pdf-semantic-diff config show comparing           a group's: endpoint, budget, sources, reading, comparing,
                                                    report, levers
  pdf-semantic-diff config show --all               every setting
  pdf-semantic-diff config find table holder        settings whose name or help holds the words
  pdf-semantic-diff config help rerank_threshold    everything about one setting
  pdf-semantic-diff config set max_cost 2           kept in the store; a new store is made for it
  pdf-semantic-diff config unset max_cost           back to the default
  pdf-semantic-diff config export settings.json     the store's own settings, as JSON (to the screen without a file)
  pdf-semantic-diff config import settings.json     every setting in the file, or none if any is wrong (null unsets)
  pdf-semantic-diff config set --user model NAME    the user's, for every store (--user: set, unset, export, import)
"""

def config_parser():
    parser = Parser(prog='pdf-semantic-diff config', usage='%(prog)s ACTION [options]')
    help_text(parser, CONFIG_HELP, "The user's and a store's settings: show, find, help, set, unset, export and "
                                  "import.")
    where = Parser(add_help=False)
    where.add_argument('--store', type=Path, default=None,
                       help='The store (default: $PDF_DIFF_STORE, else ./diff-output)')
    where.add_argument('--user', action='store_true',
                       help="the user's settings, shared by every store (set, unset, export, import), not the store's")
    actions = parser.add_subparsers(dest='action', metavar='ACTION')
    show = actions.add_parser('show', parents=[where], help='the settings and their values, by group')
    show.add_argument('group', nargs='?', help=f"one group: {', '.join(configuration.GROUPS)}")
    show.add_argument('--all', action='store_true', help='every setting, the levers\' too')
    show.add_argument('--json', action='store_true', help='every value as JSON, as a run would use them')
    find = actions.add_parser('find', parents=[where], help='settings whose name or help holds the words')
    find.add_argument('words', nargs='+')
    explain = actions.add_parser('help', parents=[where], help='everything about one setting')
    explain.add_argument('name')
    put = actions.add_parser('set', parents=[where], help="set a setting in the store (the user's with --user)")
    put.add_argument('name')
    put.add_argument('value')
    drop = actions.add_parser('unset', parents=[where], help='a setting back to its default')
    drop.add_argument('name')
    out = actions.add_parser('export', parents=[where], help="the store's own settings as JSON (--user: the user's)")
    out.add_argument('file', nargs='?', type=Path)
    take = actions.add_parser('import', parents=[where], help='settings from a JSON file (- for standard input)')
    take.add_argument('file')
    return parser

def config_command(argv):
    """`pdf-semantic-diff config` (configuration.py): a store's own settings shown, explained, set and moved."""
    parser = config_parser()
    args = parser.parse_args(argv or ['show'])
    from .settings import save_user_settings, user_path, user_settings
    store = args.store or default_store()
    user, own = user_settings(), Store.settings_of(store)
    layers = [('user', user), ('store', own)]
    if args.user:  # the layer set, unset, exported or imported
        own = user
    if args.action == 'show' and args.json:
        values = {name: value for name, (value, _) in configuration.resolved(layers).items()}
        print(json.dumps(values, indent=2, ensure_ascii=False))
        return 0
    if args.action in ('show', 'find'):
        made = (store / 'store.sqlite').exists()
        print(f"settings of {store}" + ("" if made else " (no store yet)") + f", over the user's ({user_path()})")
        lines = configuration.show_lines(layers, group=getattr(args, 'group', None),
                                         everything=getattr(args, 'all', False),
                                         find=' '.join(args.words) if args.action == 'find' else None)
        print('\n'.join(lines))
        if args.action == 'show':
            print("more: config show GROUP, config show --all, config find WORDS, config help NAME")
            print('environment variables (neither the user\'s nor the store\'s):')
            for name, value in environment():
                print(f"  {name:<16} {value}")
        return 0
    if args.action == 'help':
        print('\n'.join(configuration.help_lines(args.name, layers)))
        return 0
    if args.action == 'export':
        text = json.dumps(configuration.exported(own), indent=1, ensure_ascii=False) + '\n'
        if args.file is None:
            sys.stdout.write(text)
        else:
            args.file.write_text(text, encoding='utf-8')
            print(f"wrote the settings of {'the user' if args.user else store} to {args.file}")
        return 0
    if args.action == 'import':
        text = sys.stdin.read() if args.file == '-' else Path(args.file).read_text(encoding='utf-8')
        try:
            changes = configuration.imported(json.loads(text))
            values = configuration.applied(own, changes)
        except ValueError as e:
            raise ValueError(f"{args.file}: {e}; nothing was changed") from None
    else:  # set, unset
        value = configuration.parse(args.name, args.value) if args.action == 'set' else None
        if args.action == 'unset' and args.name not in configuration.HELP:
            raise configuration.unknown(args.name)
        changes = {args.name: value}
        values = configuration.applied(own, changes)
    if args.user:
        save_user_settings(values)
        now = configuration.resolved([('user', values), ('store', Store.settings_of(store))])
    else:
        with Store(store) as kept:
            kept.save_own_settings(values)
        now = configuration.resolved([('user', user), ('store', values)])
    for name in changes:
        if name == 'levers':
            print(f"levers = {', '.join(values.get('levers') or ['the default order'])}")
            continue
        value, layer = now[name]
        moved = configuration.shown(name, value) != configuration.shown(
            name, configuration.resolved(layers)[name][0])
        print(f"{name} = {configuration.shown(name, value)}" + (" (the default)" if layer == 'default' else
                                                                ' (the store\'s)' if args.user and layer == 'store'
                                                                else '')
              + (f"; the next run redoes: {configuration.redoes(name)}" if moved else ''))
    return 0

def environment():
    """The environment variables `config show` lists, with what each is now: never the key, only whether it's set."""
    value = lambda name, unset: os.environ.get(name) or f"not set: {unset}"  # noqa: E731
    return [('OPENAI_BASE_URL', value('OPENAI_BASE_URL', default('base_url'))),
            ('OPENAI_API_KEY', 'set' if os.environ.get('OPENAI_API_KEY') else 'not set'),
            ('PDF_DIFF_STORE', value('PDF_DIFF_STORE', './diff-output, without --store'))]
# Every other setting is the user's or a store's (`config set [--user]`): PDF_DIFF_<NAME> and OPENAI_MODEL are no longer
# read, and warn when set (settings.retired).

def settings_parser():
    parser = help_text(Parser(prog='pdf-semantic-diff settings'), description=SETTINGS_HELP)
    parser.add_argument('--config', type=Path, help='A settings JSON file, applied over the environment')
    parser.add_argument('--store', type=Path, help='A store whose own settings (`config set`) apply, under --config')
    parser.add_argument('--changed', action='store_true',
                        help='Only the settings that differ from the defaults (a starting --config file)')
    return parser

def settings_command(argv):
    from .llm import redact_url
    from .settings import Settings
    args = settings_parser().parse_args(argv)
    own = Store.settings_of(args.store) if args.store else {}
    settings = settings_from(args.config, layer={k: v for k, v in own.items() if k not in configuration.RUN_OPTIONS})
    from .levers import declared
    dumped = settings.model_dump(mode='json')
    endpoint = {k: v for k, v in dumped.items() if declared(Settings, k).kind == 'endpoint'}  # model and endpoint first
    shown = {'model': endpoint.pop('model'), 'base_url': redact_url(endpoint.pop('base_url')), **endpoint,
             **settings.configuration()}
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
  pdf-semantic-diff source show team-a --store work  its files, and those skipped and why
  pdf-semantic-diff compare team-a team-b --store work
  pdf-semantic-diff source export team-a --store work --output team-a.source.json --with-hashes
"""

def source_parser():
    parser = help_text(Parser(prog='pdf-semantic-diff source'), SOURCE_EXAMPLES,
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
    parser = Parser(prog=f'pdf-semantic-diff {command}')
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
        add_report_options(parser)
        parser.add_argument('--dry-run', action='store_true',
                            help='Write nothing: say what the budget embeds and leaves out, group by group, and the '
                                 'budget each group needs in full')
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
            from .settings import user_settings
            own = {**user_settings(), **store.own_settings()}  # the report's settings, unless a flag says otherwise
            budget = args.report_budget if args.report_budget is not None else own.get('report_budget',
                                                                                       crops.DEFAULT_BUDGET)
            split = args.split if args.split is not None else own.get('split', False)
            account = write_report(store.comparison(args.comparison), out, assets=store.folder / 'assets',
                                   budget=budget, write=not args.dry_run, split=split)
            if args.dry_run:
                print("\n".join(crops.feedback(account)))
            else:
                page = out / SPLIT / 'index.html' if (out / SPLIT / 'index.html').exists() and split else (
                    out / 'report.html')
                print(f"Report: {page} ({crops.sized(account.size)})")
                if account.cut:
                    print(crops.summary(account, args.store))
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
