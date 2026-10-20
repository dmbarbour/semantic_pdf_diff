"""Command line: compare two sources, and manage declared sources in a store.

    semantic-pdf-diff compare A B [--store DIR]         # files, folders, zips or declared sources' names
    semantic-pdf-diff source add|list|show|update|remove|export|import ...
    semantic-pdf-diff show|gc|report --store DIR ...
    semantic-pdf-diff settings [--config FILE] [--changed]
    semantic-pdf-diff fixtures summary|pack|prune|merge ...
    semantic-pdf-diff cache show|copy|remove|prune ...   # the answers cache
    semantic-pdf-diff search WORDS... [--store DIR ...]  # stores' claims, as a report's search finds them
    semantic-pdf-diff review|queries ...                # with the lab installed (semantic-pdf-diff[lab])
"""
import argparse
import csv
import json
import os
import sys
from pathlib import Path
from . import __version__, configuration, crops, fixtures, manifest
from .pipeline import (RunOptions, attempt, check_fixture, declare_paths, document_properties, limits, require_model,
                       run, settings_from)
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
        print(f'semantic-pdf-diff {__version__}')
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
    if argv[0] == 'cache':
        return cache_command(argv[1:])
    if argv[0] == 'search':
        return search_command(argv[1:])
    lab = lab_commands().get(argv[0])
    if lab:
        return lab(argv[1:])
    hint = f": to compare files, semantic-pdf-diff compare {' '.join(argv[:2])}" if Path(argv[0]).exists() else ""
    print(f"semantic-pdf-diff: no command {argv[0]!r}{hint} (semantic-pdf-diff --help lists them)", file=sys.stderr)
    return 1

# What `semantic-pdf-diff --help` says: someone installing the tool on another machine has only this, not the docs
# (the owner, 2026-10-14: "it doesn't even mention the `source add` options").
COMMANDS_HELP = """\
Evidence-first comparison of engineering documents: competing proposals, or revisions of one design. A vision
model behind an OpenAI-compatible endpoint reads claims from text, tables, charts and drawings; related claims are
paired, and differences are reported with the page and region each claim came from. Nothing is ranked, and a claim
with no counterpart isn't taken as proof of absence.

Commands (semantic-pdf-diff COMMAND --help for each, or semantic-pdf-diff help COMMAND):
  compare     compare two sources: files, folders or zip archives, or sources declared in a store
  source      declare sources in a store and manage them: add, list, show, update, remove, export, import
  show        print a view of a store: its sources, files, evidence, coverage or comparisons
  report      write a store's report again, without model calls
  search      search a store's claims, or several stores', as a report's search box does
  gc          delete content no declared source uses any more
  config      the user's and a store's settings: show, find, help, set, unset, export, import
  settings    print the settings a run would use, as JSON
  cache       the answers cache: show it; copy, remove or prune a project's answers
  fixtures    recorded model answers, replayed instead of asked (testing)
"""

START_HELP = """\
Before a first run, name the endpoint and the model (a .env file isn't read):
  export OPENAI_API_KEY=...                            the provider's key
  export OPENAI_BASE_URL=https://provider.example/v1   default: {base_url}
  semantic-pdf-diff config set --user model provider/vision-model     needed: there's no default
  semantic-pdf-diff config models vision                              the endpoint's models reading images
A store keeps its own settings: `semantic-pdf-diff config show` lists them, `config set NAME VALUE` sets one
(`config help NAME` says what it does). A run's flags, or a --config JSON file, override them for that run.

Examples:
  semantic-pdf-diff compare team-a.pdf team-b.pdf --store result           two proposals; open result/report.html
  semantic-pdf-diff compare old.pdf new.pdf --mode revisions --store diff  a revision: the earlier one first
  semantic-pdf-diff compare team-a/ team-b.zip --max-cost 2                stop asking once $2 is reported spent
  semantic-pdf-diff source add team-a --store work --path team-a/ --meta organization="Team A"
  semantic-pdf-diff source add team-b --store work --path team-b.zip
  semantic-pdf-diff compare team-a team-b --store work                     declared sources, by name

A comparison's --store folder ($SEMANTIC_PDF_DIFF_STORE unless named, else diff-output) holds what was read, and
receives report.html (one file to keep or send, its crops inside as --report-budget allows), report.json and
evidence.json. A comparison into it again reuses what was read, and resumes one interrupted. Every command takes
--store, with the same default. The model's answers are cached ($SEMANTIC_PDF_DIFF_CACHE, else
~/.cache/semantic-pdf-diff; a store keeps the cache its first run used): what was asked once isn't paid for again.

Exit codes: 0 complete (uncertainty may remain); 2 incomplete coverage or processing failures; 1 an error
(a mistyped command or option too); 3 paused for budget (run again to resume); 5 the endpoint failed: a check of
`config test`, or 25 requests in a row (stop_after_failures), which pauses the run.
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
                         help='A settings JSON file, e.g. {"concurrency": 6}; `semantic-pdf-diff settings` lists '
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
                              '(e.g. Qwen/Qwen3-Reranker-8B), asked at the endpoint\'s /rerank unless rerank_api or '
                              'rerank_url says otherwise; pairs below --rerank-threshold are not judged, the rest best '
                              'first')
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
                       help='Start the store over: everything read is read again, its answers from the cache where '
                            'queries are unchanged (sources and settings stay). Without it, a run with other '
                            'settings reads again what they change')
    store.add_argument('--dry-run', action='store_true',
                       help='Say what the run would clear to read again (with --reset: everything), and change '
                            'nothing')
    output = parser.add_argument_group('output')
    add_log_options(output)
    add_report_options(output)
    recorded = parser.add_argument_group('recorded answers (testing, and runs without the model)')
    recorded.add_argument('--fixture', type=Path,
                          help="Answers fixture, instead of the answers cache ($SEMANTIC_PDF_DIFF_CACHE): answers "
                               'recorded in it are replayed, not asked again. A .sqlite file also records new answers '
                               '(created if missing); a .zip is replayed only')
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
    """What `semantic-pdf-diff --help` prints: the commands, how to start, examples (each command parses its own)."""
    commands = COMMANDS_HELP + "".join(f"  {name:<11} the lab's (semantic-pdf-diff[lab])\n"
                                       for name in sorted(lab_commands()))
    parser = Parser(prog='semantic-pdf-diff', usage='%(prog)s COMMAND [options]')
    help_text(parser, START_HELP.format(base_url=default('base_url')), commands)
    parser.add_argument('--version', action='version', version=f'%(prog)s {__version__}',
                        help="show the program's version and exit")
    return parser


# --- compare ---------------------------------------------------------------------------

COMPARE_HELP = """\
Compare two sources. Each is a file, folder or zip archive, or the name of a source declared in the store
(`semantic-pdf-diff source add`); a declared name is taken before a path. Sources are rescanned first, so files
edited, added or removed since are picked up.
"""

COMPARE_EXAMPLES = """\
Examples:
  semantic-pdf-diff compare team-a.pdf team-b.pdf --store result
  semantic-pdf-diff compare old.pdf new.pdf --mode revisions --store diff --max-cost 2
  semantic-pdf-diff compare team-a team-b --store work  sources declared in work
  semantic-pdf-diff compare rev-b rev-c --store work --mode revisions --report reports/b-to-c
  semantic-pdf-diff compare --store work --manifest team-a.source.json team-b
"""

def compare_parser():
    parser = help_text(Parser(prog='semantic-pdf-diff compare',
                                               usage='%(prog)s SOURCE SOURCE [--store DIR] [options]'),
                       COMPARE_EXAMPLES, COMPARE_HELP)
    parser.add_argument('sources', nargs='*', metavar='SOURCE',
                        help='Two sources (a file, folder or zip, or a declared source\'s name): proposal A then B, '
                             'or the earlier revision then the later')
    parser.add_argument('--store', type=Path, default=default_store(),
                        help='The store folder, created if missing (default: $SEMANTIC_PDF_DIFF_STORE, else '
                             './diff-output). It keeps what was read, for the next comparison, and receives the '
                             'reports unless --report names another')
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
    if client is None and not options.dry_run:
        require_model(settings, options)
    with Store(args.store) as store:
        if client is None and not options.fixture:
            from .pipeline import cache_of
            cache_of(store, bind=False)  # a cache other than the store's is refused before its sources change
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
    parser = Parser(prog='semantic-pdf-diff fixtures',
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


# --- search ------------------------------------------------------------------------

SEARCH_HELP = """\
Search the claims of one store or several as a report's search box does, with or without a report written: each
store's latest comparison (--comparison picks another, for one store).
  feed pump            both words, in any order, as the start of words; case and accents ignored
  75  1,000  75kW      numbers whole, however written (75 isn't 750; 1,000 is 1000; 75kW is 75 kW)
  "feed pump"          the words in a row;  -gearbox  without it;  blade OR rotor  either
  entity:pump          one part of a claim: entity, attribute, value (with its unit), conditions, quote, section,
                       file (a file's name is searched only so); page:12 or page:10-20
  >50kW  value:10-20mm values compared across units (0.075 MW is over 50 kW); <=, >=, <; value:75kW for
                       that value; without a unit, numbers as written
  like:ID              the claims sharing enough of what a claim is about, most alike first; near it in meaning
                       too where the claims were embedded (embed_model)
  near:ID              the claims near a claim in meaning;  meaning:"rated output"  what's typed, by meaning (it
                       asks the embedding model the claims were embedded with, once: the answers cache keeps it)
The most relevant first. After the claims found come their counterparts (the claims the comparison paired with
them; --alone leaves them out), and where a counterpart names what was searched otherwise, its name is offered.
Where the model was asked the documents' other names for one thing (search_names), a search for one name finds the
others' claims too, after the rest, each marked.

Quote a query holding a word to leave out, or anything else the shell reads: semantic-pdf-diff search 'pump -gearbox'.

Examples:
  semantic-pdf-diff search rated power --store work
  semantic-pdf-diff search 'entity:pump -gearbox' --store bid-a --store bid-b --limit 50
  semantic-pdf-diff search like:ev-00ce8e6f78324812 --store work
  semantic-pdf-diff search hub height --findings --json
"""

def search_parser():
    parser = Parser(prog='semantic-pdf-diff search', usage='%(prog)s WORDS... [--store DIR ...] [options]',
                    add_help=False)  # no -h: "-heater" leaves heaters out
    help_text(parser, SEARCH_HELP, "Search stores' claims, as a report's search box does.")
    parser.add_argument('--help', action='help', help='show this help and exit')
    parser.add_argument('words', nargs='*', help='the query')
    parser.add_argument('--store', type=Path, action='append', default=[],
                        help='a store (repeat for several; default: $SEMANTIC_PDF_DIFF_STORE, else ./diff-output)')
    parser.add_argument('--comparison', type=int, help='the comparison searched, with one store (default: the latest)')
    parser.add_argument('--findings', action='store_true', help='the findings found, not the claims')
    parser.add_argument('--side', help="only this source's claims (its name, or a part of it)")
    parser.add_argument('--alone', action='store_true', help='the claims found, without their counterparts')
    parser.add_argument('--limit', type=int, default=20, help='at most this many (default 20; 0: every one)')
    parser.add_argument('--json', action='store_true', help='everything found as one JSON document, for tools')
    return parser

def brief(claim):
    """A claim as the command prints it: what it says, then where it is."""
    e = claim['evidence']
    said = f"{e['entity']} — {e['attribute']} = {e['value']} {e['unit']}".strip()
    if e.get('conditions'):
        said += f" ({e['conditions']})"
    loc = e['locator']
    where = f"{claim['where']}, page {loc['page']}" + (f", § {claim['section']}" if claim['section'] else '')
    return said, where

def claim_json(claim):
    e = claim['evidence']
    return {'store': str(claim['store']), 'source': claim['source'], 'id': e['id'], 'file': claim['where'],
            'page': e['locator']['page'], 'section': claim['section'], 'entity': e['entity'],
            'attribute': e['attribute'], 'value': e['value'], 'unit': e['unit'], 'conditions': e['conditions'],
            'quote': e['quote'], 'fared': claim['status']}

def meant(terms, model, dimensions, folder):
    """Each meaning: term's text embedded by the model the claims were, through the store's answers cache (a search
    asked again is free): its vector set on the term. ValueError when the model can't be asked."""
    from . import embed
    from .dispatch import Dispatcher
    from .llm import Client
    from .pipeline import cache_of, open_cache
    from .store import Store
    with Store.open(folder) as store:
        own = store.own_settings()
        cache = open_cache(cache_of(store, bind=False))
    settings = settings_from(layer={**{k: v for k, v in own.items() if k not in configuration.RUN_OPTIONS},
                                    'embed_model': model, 'embed_dimensions': dimensions})
    client = Client(settings, None, cache=cache)
    failed = []
    try:
        with Dispatcher(client) as dispatch:
            for term in terms:
                def done(value, error, term=term):
                    if error is not None:
                        failed.append(f"{term['meaning']!r}: {error}")
                        return
                    v = embed.unpacked(value.vectors[0])
                    term['vector'] = (v, sum(x * x for x in v) ** 0.5)
                dispatch.submit_request(embed.request(settings, [term['meaning']], None, query=True), done)
            dispatch.drain()
    finally:
        client.close()
    if failed:
        raise ValueError(f"meaning: {model} couldn't be asked: {'; '.join(failed)}")

def search_command(argv):
    from . import search as finder
    from .store import Store, StoreError
    parser = search_parser()
    args, rest = parser.parse_known_args(argv)
    unknown = [r for r in rest if r.startswith('--')]
    if unknown:
        parser.error(f"unrecognized arguments: {' '.join(unknown)}")
    query = ' '.join(args.words + rest)  # a word to leave out ("-gearbox") isn't an option
    groups = finder.parse(query)
    if not groups:
        parser.error('nothing to search for: give words (--help says how)')
    stores = args.store or [default_store()]
    if args.comparison and len(stores) > 1:
        parser.error('--comparison picks one store\'s comparison: name one store')
    index, claims, findings, embedded = finder.Index(), [], [], set()
    for n, folder in enumerate(stores):
        try:
            with Store.open(folder) as store:
                data = store.comparison(args.comparison)
        except StoreError as e:
            print(f'{folder}: {e}', file=sys.stderr)
            return 1
        if (data.get('vectors') or {}).get('vectors'):
            embedded.add((data['vectors']['model'], data['vectors']['dimensions']))
        found_claims, found_findings = finder.report_items(data, index, f'{n}:' if len(stores) > 1 else '')
        for x in found_claims + found_findings:
            x['store'] = folder
        claims += found_claims
        findings += found_findings
    for group in groups:  # like:ID and near:ID name a claim by its id, in whichever store holds it
        for term in group['terms']:
            for key in ('like', 'near'):
                if key in term and term[key] not in index.card_doc:
                    term[key] = next((k for k in index.card_doc if k.endswith(':' + term[key])), term[key])
    asked = [term for group in groups for term in group['terms'] if 'meaning' in term]
    if asked:  # what's typed, embedded as the claims were
        if len(embedded) != 1:
            parser.error('meaning: needs the claims embedded, every store\'s by one model (embed_model, then '
                         'compare again)' if not embedded else f"meaning: the stores' claims were embedded by "
                         f"{len(embedded)} models: search them apart")
        meant(asked, *next(iter(embedded)), stores[0])
    view = 'findings' if args.findings else 'claims'
    hits, names, others = finder.search(index, groups, claims, findings, view, paired=not args.alone)
    if view == 'claims' and args.side:
        names_of = sorted({c['source'] for c in claims if c['source']})
        side = [n for n in names_of if n == args.side] or [n for n in names_of if args.side.lower() in n.lower()]
        if len(side) != 1:
            parser.error(f"--side {args.side}: {'no source' if not side else 'several sources'} by that name; the "
                         f"sources: {', '.join(side or names_of)}")
        hits = [h for h in hits if claims[h[0]]['source'] == side[0]]
    shown = hits if not args.limit else hits[:args.limit]
    if args.json:
        items = ([{'score': round(s, 3), 'counterpart': how == 'counterpart',
                   'other_name': how[5:] if how.startswith('name:') else '', **claim_json(claims[i])}
                  for i, s, how in shown]
                 if view == 'claims' else
                 [{'score': round(s, 3), 'store': str(findings[i]['store']), 'relation': findings[i]['relation'],
                   'rationale': findings[i]['finding'].get('rationale', ''),
                   'claims': [claim_json(claims[at[c]]) for c in findings[i]['cards'] if c in at],
                   'other_name': how[5:] if how.startswith('name:') else ''}
                  for at in [{c['card']: k for k, c in enumerate(claims)}] for i, s, how in shown])
        print(json.dumps({'query': query, 'view': view, 'found': len(hits),
                          'counterparts': sum(1 for h in hits if h[2] == 'counterpart'),
                          'by_other_names': sum(1 for h in hits if h[2].startswith('name:')),
                          'names': [n for n, _ in names], 'other_names': others, 'items': items},
                         indent=1, ensure_ascii=False))
        return 0
    via, named = (sum(1 for h in hits if h[2] == 'counterpart'), sum(1 for h in hits if h[2].startswith('name:')))
    how = [f'{via} as counterparts' if via else '', f'{named} by other names' if named else '']
    line = f"{len(hits)} {view} found" + (f" ({', '.join(h for h in how if h)})" if via or named else '')
    if view == 'claims':
        counts = {}
        for i, _, _ in hits:
            counts[claims[i]['source']] = counts.get(claims[i]['source'], 0) + 1
        line += ': ' + '; '.join(f'{n} in {name}' for name, n in counts.items()) if counts else ''
    strange = finder.unknown(groups)
    if strange:
        line += f" (units the search doesn't know: {', '.join(strange)})"
    print(line)
    if names:
        print("The other source's names for it: " + ', '.join(f'"{name}" ({n})' for name, n in names))
    if others:
        print("The model's other names for it: " + ', '.join(f'"{name}"' for name in others))
    at = {c['card']: k for k, c in enumerate(claims)}
    marks = lambda how: ('  [counterpart]' if how == 'counterpart' else  # noqa: E731
                         f'  [named otherwise: {how[5:]}]' if how.startswith('name:') else '')
    for rank, (i, score, how) in enumerate(shown, 1):
        if view == 'claims':
            said, where = brief(claims[i])
            print(f"{rank:>3}. {said}" + marks(how))
            print(f"     {where} · {claims[i]['evidence']['id']}")
            quote = ' '.join(claims[i]['evidence']['quote'].split())
            if quote:
                print(f"     “{quote[:157] + '…' if len(quote) > 158 else quote}”")
        else:
            f = findings[i]
            print(f"{rank:>3}. {f['relation']}" + marks(how))
            for card in f['cards']:
                if card in at:
                    said, where = brief(claims[at[card]])
                    print(f"     {claims[at[card]]['source']}: {said}  ({where})")
    if len(hits) > len(shown):
        print(f"… {len(hits) - len(shown)} more (--limit 0 shows every one)")
    return 0

# --- the answers cache ---------------------------------------------------------------

CACHE_HELP = """\
The answers cache keeps every answer the model gave a run, by the query asked, so what was asked once isn't paid
for again. It's $SEMANTIC_PDF_DIFF_CACHE/answers.sqlite, else the user's (under $XDG_CACHE_HOME or ~/.cache). A
store keeps the cache its first run used (answers_cache), so each action works on the cache the stores it names use
(--store; prune's --keep), else on $SEMANTIC_PDF_DIFF_STORE's (else ./diff-output's); --cache names another. A
project whose documents mustn't mix with others' keeps a cache of its own: point SEMANTIC_PDF_DIFF_CACHE at it
before its first run, or `config set answers_cache` after.

A store logs every query its runs asked, however each was answered, so naming a project's stores (--store) picks
out its answers: to copy them from another cache into this one, or to remove them from this one. Removed answers
are overwritten in the file, not left in its free pages; copies made before (backups, snapshots) aren't touched.

Examples:
  semantic-pdf-diff cache show
  semantic-pdf-diff cache copy ~/.cache/semantic-pdf-diff --store project/store --dry-run
  semantic-pdf-diff cache remove --store old-store --keep current-store
  semantic-pdf-diff cache remove --store project/store --cache ~/.cache/semantic-pdf-diff   from another cache
  semantic-pdf-diff cache prune --keep store-a --keep store-b
  semantic-pdf-diff cache prune --unused-since 2026-09-01
"""

def cache_parser():
    parser = Parser(prog='semantic-pdf-diff cache', usage='%(prog)s ACTION [options]')
    help_text(parser, CACHE_HELP, 'The answers cache: what it holds; a project\'s answers copied from another '
                                  'cache, removed, or kept alone.')
    which = Parser(add_help=False)
    which.add_argument('--cache', type=Path, help='the answers cache: a folder holding answers.sqlite, or the file '
                                                  "(default: the one the stores' runs use)")
    dry = Parser(add_help=False)
    dry.add_argument('--dry-run', action='store_true', help='say what would be copied or removed, change nothing')
    actions = parser.add_subparsers(dest='action', metavar='ACTION', required=True)
    show = actions.add_parser('show', parents=[which], help='where it is, its size, its answers by model and role')
    show.add_argument('--store', type=Path, action='append', default=[],
                      help='the cache this store uses (default: $SEMANTIC_PDF_DIFF_STORE, else ./diff-output)')
    copy = actions.add_parser('copy', parents=[which, dry],
                              help='copy in the answers another cache or fixture holds and this one lacks')
    copy.add_argument('source', type=Path, help="the other cache's folder, or a fixture (.sqlite or .zip)")
    copy.add_argument('--store', type=Path, action='append', default=[],
                      help='only the answers to the queries this store asked (repeat for several)')
    remove = actions.add_parser('remove', parents=[which, dry],
                                help='remove the answers to the queries these stores asked')
    remove.add_argument('--store', type=Path, action='append', default=[],
                        help='a store (repeat for several; default: $SEMANTIC_PDF_DIFF_STORE, else ./diff-output)')
    remove.add_argument('--keep', type=Path, action='append', default=[],
                        help="but not those this store asked too (repeat for several)")
    prune = actions.add_parser('prune', parents=[which, dry],
                               help='keep only the answers these stores asked, or those used since a time')
    either = prune.add_mutually_exclusive_group(required=True)
    either.add_argument('--keep', type=Path, action='append', default=[],
                        help='keep the answers to the queries this store asked (repeat for several)')
    either.add_argument('--unused-since', help='remove the answers not used since this ISO time (2026-09-01)')
    prune.add_argument('--force', action='store_true', help="--unused-since even if no run used the cache since, "
                                                            "a run missed requests, or most answers go")
    return parser

def stores_queries(folders):
    """Every query the stores' runs asked, by hash (a store's answers, whichever cache holds them)."""
    from .store import Store
    queries = set()
    for folder in folders:
        with Store.open(folder) as store:
            queries |= store.query_hashes()
    return queries

def cache_in_use(folders):
    """The answers cache the stores' runs use (pipeline.cache_of), else, with none named, the default store's (one made
    already), else the cache in effect: ValueError where the stores keep their answers apart."""
    from .pipeline import cache_of
    from .settings import cache_path
    if not folders:
        if not (default_store() / 'store.sqlite').exists():
            return cache_path()
        folders = [default_store()]
    caches = {}
    for folder in folders:
        with Store.open(folder) as store:
            try:
                path = cache_of(store, bind=False)
            except ValueError as e:  # $SEMANTIC_PDF_DIFF_CACHE names another: which one is meant isn't guessed
                raise ValueError(f"{e}; or name the cache with --cache") from None
        caches.setdefault(path.resolve(), (path, []))[1].append(str(folder))
    if len(caches) > 1:
        raise ValueError("the stores keep their answers in different caches ("
                         + "; ".join(f"{', '.join(named)}: {path}" for path, named in caches.values())
                         + "): name one with --cache")
    return next(iter(caches.values()))[0]

def cache_command(argv):
    from .pipeline import open_cache
    from .settings import cache_file
    from .store import StoreError
    args = cache_parser().parse_args(argv)
    stores = args.keep if args.action == 'prune' else args.store or (
        [default_store()] if args.action == 'remove' else [])
    try:
        path = cache_file(args.cache) if args.cache else cache_in_use(stores)
    except (StoreError, ValueError) as e:
        print(e, file=sys.stderr)
        return 1
    if args.action == 'show':
        if not path.exists():
            print(f'{path}: no answers cached yet')
            return 0
        with fixtures.open(path, 'read') as cache:
            summary, (first, last, used) = cache.summary(), cache.times()
        size = sum(f.stat().st_size for f in path.parent.glob(path.name + '*'))
        answers = sum(row['answers'] for row in summary['answers'])
        print(f'{path}: {answers} answers to {summary["queries"]} queries, {size / 1e6:.1f} MB')
        if first:
            print(f'recorded {first[:10]} to {last[:10]}' + (f', last used {used[:10]}' if used else ''))
        by_model = {}
        for row in summary['answers']:
            by_model.setdefault(row['responder'], []).append(row)
        for model, rows in sorted(by_model.items()):
            roles = {}
            for row in rows:
                roles[row['role'] or 'other'] = roles.get(row['role'] or 'other', 0) + row['answers']
            failed = sum(row['answers'] for row in rows if row['outcome'] != 'ok')
            print(f'  {model}: {sum(r["answers"] for r in rows)} answers ('
                  + ', '.join(f'{role} {n}' for role, n in sorted(roles.items()))
                  + (f'; {failed} failures' if failed else '') + ')')
        return 0
    try:
        queries = stores_queries(stores) if stores else None
        kept = stores_queries(args.keep) if args.action == 'remove' and args.keep else None
    except StoreError as e:
        print(e, file=sys.stderr)
        return 1
    would = 'would be ' if args.dry_run else ''
    if args.action == 'copy':
        source = cache_file(args.source)
        if not source.exists():
            print(f'{source}: no such cache or fixture', file=sys.stderr)
            return 1
        if source.resolve() == path.resolve():
            print(f'{source}: the cache copied from is the one copied into', file=sys.stderr)
            return 1
        try:
            with open_cache(path) as cache:
                added = cache.merge(source, queries=queries, dry_run=args.dry_run)
        except (fixtures.FixtureError, OSError) as e:
            print(e, file=sys.stderr)
            return 1
        what = f"the {len(queries)} queries {len(stores)} store(s) asked" if queries is not None else 'every query'
        print(f'{added} answers {would}copied from {source} into {path} ({what}; answers it had already are kept)')
        return 0
    if not path.exists():
        print(f'{path}: no answers cached yet')
        return 0
    with fixtures.open(path, 'record') as cache:
        if args.action == 'remove':
            removed = cache.remove(queries, keep=kept, dry_run=args.dry_run)
        elif args.keep:
            removed = cache.remove(keep=queries, dry_run=args.dry_run)
        else:
            try:
                unused = cache.prune(args.unused_since, dry_run=args.dry_run, force=args.force)
            except fixtures.FixtureError as e:
                print(e, file=sys.stderr)
                return 1
            removed = {'answers': unused['answers_removed'], 'queries': 0}
            for reason in unused['refused']:
                print(f'(without --dry-run, prune would refuse: {reason}; --force prunes anyway)')
    print(f"{removed['answers']} answers {would}removed from {path}"
          + (f" ({removed['queries']} queries)" if removed['queries'] else '')
          + ('' if args.dry_run or not removed['answers'] else
             '; overwritten in the file, but not in copies made before (backups, snapshots)'))
    return 0

SETTINGS_HELP = """\
Print the settings a run would use, as JSON: the defaults, then the user's (`config set --user`), then the store's
(`config set`; --store, else $SEMANTIC_PDF_DIFF_STORE's, else ./diff-output's), then --config's. The endpoint is
OPENAI_BASE_URL's; the API key (OPENAI_API_KEY) is never printed. `semantic-pdf-diff config show` lists the
settings with what each does.

Settings that shape what's asked (extraction, levers) are bound to a store: a run with others reads again what they
change, the queries that didn't change answered from the cache.
"""

def default_store():
    """The store a command works on without --store: $SEMANTIC_PDF_DIFF_STORE, else ./diff-output."""
    from .settings import variable
    return Path(variable('STORE') or 'diff-output')

CONFIG_HELP = """\
A store keeps its own settings: set once, they apply to every run in it (a run's flags override them for that
run only). The user's settings (--user) lie under every store's: the endpoint's model and context, concurrency, a
reranker. Names are the settings' own (max_cost, report_budget, rerank_threshold).

  semantic-pdf-diff config show                     the settings most runs set, by group
  semantic-pdf-diff config show comparing           a group's: endpoint, budget, sources, reading, comparing,
                                                    report, levers
  semantic-pdf-diff config show --all               every setting
  semantic-pdf-diff config find table holder        settings whose name or help holds the words
  semantic-pdf-diff config help rerank_threshold    everything about one setting
  semantic-pdf-diff config set max_cost 2           kept in the store; a new store is made for it
  semantic-pdf-diff config unset max_cost           back to the default
  semantic-pdf-diff config export settings.json     the store's own settings, as JSON (to the screen without a file)
  semantic-pdf-diff config import settings.json     every setting in the file, or none if any is wrong (null unsets)
  semantic-pdf-diff config set --user model NAME    the user's, for every store (--user: set, unset, export, import)
  semantic-pdf-diff config test                     the endpoint, the key and each model checked, for a few cents
                                                    (exit 5 when a check fails)
  semantic-pdf-diff config models vision            the endpoint's models reading images: context, price
"""

def config_parser():
    parser = Parser(prog='semantic-pdf-diff config', usage='%(prog)s ACTION [options]')
    help_text(parser, CONFIG_HELP, "The user's and a store's settings: show, find, help, set, unset, export and "
                                  "import; the endpoint checked (test) and its models listed (models).")
    where = Parser(add_help=False)
    where.add_argument('--store', type=Path, default=None,
                       help='The store (default: $SEMANTIC_PDF_DIFF_STORE, else ./diff-output)')
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
    actions.add_parser('test', parents=[where], help='the endpoint, the key and each model the settings name, checked '
                                                    'by asking (a few cents); exit 5 when a check fails')
    listed = actions.add_parser('models', parents=[where], help="the endpoint's models, with what it says of each "
                                                                "(context, price, tags), those the settings name "
                                                                "marked")
    listed.add_argument('words', nargs='*', help='only models whose name or tags hold every word ("vision": those '
                                                 'reading images, where the endpoint says)')
    listed.add_argument('--json', action='store_true', help='every field, as JSON')
    return parser

def config_command(argv):
    """`semantic-pdf-diff config` (configuration.py): a store's own settings shown, explained, set and moved."""
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
    if args.action in ('test', 'models'):
        from . import checkup
        settings = settings_from(layer={k: v for k, v in Store.settings_of(store).items()
                                        if k not in configuration.RUN_OPTIONS})
        if args.action == 'models':
            try:
                print('\n'.join(checkup.listing(settings, ' '.join(args.words), as_json=args.json)))
            except (OSError, ValueError) as e:
                raise ValueError(f"the endpoint's models can't be listed ({type(e).__name__}: {e})") from None
            return 0
        checks, cost = checkup.run(settings)
        print('\n'.join(checkup.lines(settings, checks, cost)))
        try:  # remembered, so a run needn't check again (checkup.first_use)
            from .settings import cache_path
            cache = cache_in_use([store]) if (store / 'store.sqlite').exists() else cache_path()
            checkup.record(checkup.memory_of(cache), settings, checks)
        except (OSError, StoreError, ValueError):
            pass
        return checkup.FAILED if any(c.ok is False for c in checks) else 0
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
        if args.name == 'answers_cache' and value and not args.user:  # from here, as the store will read it
            from .settings import recorded
            given = Path(value).expanduser()
            value = value if value.startswith('~') or given.is_absolute() else recorded(given.resolve(), store)
        changes = {args.name: value}
        values = configuration.applied(own, changes)
    if args.user and 'answers_cache' in changes:
        raise ValueError("answers_cache is a store's: the user's cache is $SEMANTIC_PDF_DIFF_CACHE's, else "
                         "~/.cache/semantic-pdf-diff")
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
        before = configuration.resolved(layers)[name][0]
        if name == 'answers_cache' and moved and before:
            from .settings import located
            old, new = located(before, store), (located(value, store) if value else 'NEW')
            print(f"the answers asked before stay in {old}: `semantic-pdf-diff cache copy {old.parent} --store "
                  f"{store} --cache {new}` brings them")
    return 0

def environment():
    """The environment variables `config show` lists, with what each is now: never the key, only whether it's set."""
    from .settings import cache_path
    value = lambda name, unset: os.environ.get(name) or f"not set: {unset}"  # noqa: E731
    return [('OPENAI_BASE_URL', value('OPENAI_BASE_URL', default('base_url'))),
            ('OPENAI_API_KEY', 'set' if os.environ.get('OPENAI_API_KEY') else 'not set'),
            ('SEMANTIC_PDF_DIFF_STORE', value('SEMANTIC_PDF_DIFF_STORE', './diff-output, without --store')),
            ('SEMANTIC_PDF_DIFF_CACHE', value('SEMANTIC_PDF_DIFF_CACHE', f'answers cached in {cache_path()}'))]
# Every other setting is the user's or a store's (`config set [--user]`): PDF_DIFF_<NAME> and OPENAI_MODEL are no longer
# read, and warn when set (settings.retired), as PDF_DIFF_STORE and PDF_DIFF_CACHE do (settings.variable).

def settings_parser():
    parser = help_text(Parser(prog='semantic-pdf-diff settings'), description=SETTINGS_HELP)
    parser.add_argument('--config', type=Path, help='A settings JSON file, applied over the environment')
    parser.add_argument('--store', type=Path, help='The store whose own settings (`config set`) apply, under --config '
                                                   '(default: $SEMANTIC_PDF_DIFF_STORE, else ./diff-output)')
    parser.add_argument('--changed', action='store_true',
                        help='Only the settings that differ from the defaults (a starting --config file)')
    return parser

def settings_command(argv):
    from .llm import redact_url
    from .settings import Settings
    args = settings_parser().parse_args(argv)
    own = Store.settings_of(args.store or default_store())
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
provenance metadata, and compared by name (`semantic-pdf-diff compare`). Its roots are files, folders (read with
their subfolders) and zip archives, rescanned on every comparison.
"""

SOURCE_EXAMPLES = """\
Examples:
  semantic-pdf-diff source add team-a --store work --path team-a/ --path addendum.pdf --meta organization="Team A"
  semantic-pdf-diff source add team-b --store work --path team-b.zip --meta revision=C
  semantic-pdf-diff source list --store work
  semantic-pdf-diff source show team-a --store work  its files, and those skipped and why
  semantic-pdf-diff compare team-a team-b --store work
  semantic-pdf-diff source export team-a --store work --output team-a.source.json --with-hashes
"""

def source_parser():
    parser = help_text(Parser(prog='semantic-pdf-diff source'), SOURCE_EXAMPLES,
                       'Declare sources in a store, and manage them.\n\n' + SOURCE_HELP)
    commands = parser.add_subparsers(dest='command', required=True, metavar='COMMAND')
    def command(name, help, description=None):
        sub = help_text(commands.add_parser(name, help=help, description=description or help), SOURCE_EXAMPLES)
        sub.add_argument('--store', type=Path, default=default_store(),
                         help='The store folder, created if missing (default: $SEMANTIC_PDF_DIFF_STORE, else '
                              './diff-output)')
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
    parser = Parser(prog=f'semantic-pdf-diff {command}')
    parser.add_argument('--store', type=Path, default=default_store(),
                        help='The store folder (default: $SEMANTIC_PDF_DIFF_STORE, else ./diff-output)')
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
                              'with its evidence, tasks, sections and crops (and the answers a store cached '
                              'itself before the answers cache).')
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
