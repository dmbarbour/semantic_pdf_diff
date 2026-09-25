"""Command line: compare two sources, and manage declared sources in a store.

    pdf-semantic-diff A B --out DIR                     # shortcut: A and B are files, folders or zips
    pdf-semantic-diff compare --store DIR NAME NAME     # declared sources, or --manifest FILE
    pdf-semantic-diff source add|list|show|update|remove|export|import ...
    pdf-semantic-diff show|gc|report --store DIR ...
"""
import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from . import manifest
from .compare import compare, file_difference
from .dispatch import Dispatcher
from .extract import EXTRACT, Job, pdf_sections, run_jobs, text_groups, visual_regions
from .llm import SYSTEM, Client, redact_url
from .models import Settings, Source
from .progress import Progress, log, setup_logging
from .throttle import RateLimiter
from .provenance import comparison_interpreter, extraction_interpreter, normalized_extension, triage_interpreter
from .report import write_report
from .scan import ARCHIVES, Limits, read_origin, scan
from .situate import find_figures, quality, situate
from .store import Store, StoreError

LIMITATIONS = ['Image-token budgeting must be calibrated to the serving backend.',
               'Confidence scores are uncalibrated model self-reports.',
               'Retrieval may miss synonyms and implicit relationships; configure domain aliases.',
               'Small VLMs can misread plots, tables, scales and diagram arrows.',
               'No global engineering consistency proof or automatic proposal ranking.']

def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    try:
        if argv and argv[0] == 'source':
            return source_command(argv[1:])
        if argv and argv[0] == 'compare':
            return compare_command(argv[1:])
        if argv and argv[0] in ('show', 'gc', 'report'):
            return store_command(argv[0], argv[1:])
        return shortcut_command(argv)
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
    parser.add_argument('--plan', action='store_true', help='Inspect sources and estimate visual tasks without API calls')
    parser.add_argument('--reset', action='store_true',
                        help='Clear derived data affected by a changed extraction interpreter, then run')
    parser.add_argument('--dry-run', action='store_true', help='With --reset: report what would be cleared, change nothing')

def load_settings(args):
    options = json.loads(args.config.read_text()) if getattr(args, 'config', None) else {}
    if not isinstance(options, dict):
        raise ValueError(f'{args.config}: settings file must contain a JSON object')
    for name in ['model', 'base_url', 'context_tokens', 'max_calls', 'top_k']:
        if getattr(args, name, None) is not None:
            options[name] = getattr(args, name)
    if getattr(args, 'no_vision', False):
        options['vision'] = False
    if getattr(args, 'no_situate', False):
        options['situate'] = False
    return Settings.from_env(**options)

def limits(settings):
    return Limits(settings.max_zip_depth, settings.max_source_bytes, settings.zip_ratio_limit, settings.zip_ratio_min_bytes)

def document_properties(name, data):
    """Native title and author of a PDF, as extracted provenance for the file."""
    if normalized_extension(name) != '.pdf':
        return {}
    import pymupdf
    try:
        with pymupdf.open(stream=data, filetype='pdf') as doc:
            meta = doc.metadata or {}
    except Exception:  # unreadable PDFs are reported by extraction, not here
        return {}
    return {k: ' '.join(meta[k].split()) for k in ('title', 'author') if (meta.get(k) or '').strip()}

# --- shortcut: two paths ------------------------------------------------------------

def shortcut_command(argv):
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
    names = shortcut_names([args.a, args.b])
    if args.plan:
        return plan([Source(name=n, kind='shortcut', roots=[str(p.resolve())]) for n, p in zip(names, [args.a, args.b])],
                    settings)
    with Store(args.out) as store:
        for name, path in zip(names, [args.a, args.b]):
            existing = store.source(name)
            if existing and existing.kind != 'shortcut':
                raise StoreError(f"{args.out} already has a declared source named {name!r}; use 'compare' instead")
            store.save_source(Source(name=name, kind='shortcut', roots=[str(path.resolve())]), replace=True)
        return run(args, settings, store, names, args.out, force_rescan=True)

def shortcut_names(paths):
    """Source names from the paths' final components, made unique."""
    names = []
    for path in paths:
        base = path.resolve().name or 'source'
        name, n = base, 2
        while name in names:
            name, n = f'{base}-{n}', n + 1
        names.append(name)
    return names

# --- compare declared sources ---------------------------------------------------------

def compare_command(argv):
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
        if args.plan:
            return plan([store.source(n) for n in names], settings)
        return run(args, settings, store, names, args.report or args.store)

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

# --- the run -----------------------------------------------------------------------

def plan(sources, settings):
    """Estimate calls, tokens and time without calling the model."""
    import pymupdf
    scaffold = len((SYSTEM + EXTRACT).encode()) + 160   # prompt text per request; bytes overestimate tokens
    answer = settings.output_tokens // 2                # assume answers use half the output reserve
    rows, calls, tokens = [], 0, 0
    for source in sources:
        scanned = scan(source.roots, limits(settings))
        pdfs = pages = text_calls = text_bytes = visual = situating = 0
        for f in scanned.files:
            if not f.content.endswith('.pdf'):
                continue
            pdfs += 1
            with pymupdf.open(stream=read_origin(f.origin), filetype='pdf') as doc:
                pages += len(doc)
                for page in doc:
                    groups = text_groups(page, settings.text_bytes)
                    text_calls += len(groups)
                    text_bytes += sum(len(t.encode()) for _, segments in groups for _, t in segments)
                    if settings.vision:
                        visual += len(visual_regions(page, settings.tile_points))
                if settings.situate:  # one request per labelled figure and per section
                    situating += (sum(1 for f in find_figures(doc) if f.label)
                                  + len(pdf_sections(doc, settings.section_depth, settings.section_pages)[0]))
        estimate = (text_calls * (scaffold + answer) + text_bytes
                    + visual * (scaffold + settings.image_tokens + answer)
                    + situating * (scaffold + settings.image_tokens + answer))  # text excluded: roughly one more read
        estimate += text_bytes if situating else 0
        calls, tokens = calls + text_calls + visual + situating, tokens + estimate
        rows.append({'source': source.name, 'files': len(scanned.files), 'pdfs': pdfs, 'pages': pages,
                     'text_tasks': text_calls, 'visual_tasks': visual, 'situating_tasks': situating, 'estimated_tokens': estimate,
                     'issues': len(scanned.issues)})
    tpm, _ = RateLimiter(settings.rate_limits).limits()
    print(json.dumps({'sources': rows, 'total': {
        'calls': calls, 'tokens': tokens, 'tokens_per_minute_limit_now': tpm,
        'minutes_at_that_limit': round(tokens / tpm, 1) if tpm else None},
        'max_calls': settings.max_calls,
        **({'warning': f'about {calls} calls are expected but max_calls is {settings.max_calls}; '
                       'the run would stop early (raise --max-calls)'} if calls > settings.max_calls else {}),
        'note': 'Estimates exclude table rows (found during extraction), refinement, retries and comparisons; '
                'image tokens use the configured image_tokens, so calibrate it for your server. No API requests made.'},
        indent=2))
    return 0

def run(args, settings, store, names, out, force_rescan=False):
    interpreter = extraction_interpreter(settings)
    triage = triage_interpreter(settings) if settings.situate else None
    if args.dry_run:
        would = {'extract': store.bind(interpreter, reset=True, dry_run=True)}
        if triage:
            would['triage'] = store.bind(triage, reset=True, dry_run=True)
        print(json.dumps({'would_clear': would}, indent=2))
        return 0
    # Check both before clearing either, so a rejected run changes nothing.
    for role in filter(None, (interpreter, triage)):
        if not args.reset:
            store.bind(role, dry_run=True)
    for role in filter(None, (interpreter, triage)):
        cleared = store.bind(role, reset=args.reset)
        if cleared:
            log.info(f"Reset cleared ({role.role}): {json.dumps(cleared)}")
    if settings.rescan == 'auto' or force_rescan:
        for name in names:
            summary = store.rescan(name, limits(settings), document_properties)
            changes = {k: len(summary[k]) for k in ('added', 'removed', 'changed') if summary[k]}
            log.info(f"Scanned {name}: {summary['files']} files" + (f", {changes}" if changes else ''))
    client = Client(settings, store)
    files = {name: store.files(name) for name in names}
    progress = Progress('extract', client, heartbeat=settings.heartbeat_seconds)
    by_content, coverage, sections = extract_sources(store, client, names, files, progress)
    progress.close()
    situations = situate_sources(store, client, names, files, by_content, sections) if triage else {}
    evidence = [e for items in by_content.values() for e in items]
    situation_data = {c: {'figures': [f.model_dump() for f in figures], 'unresolved': [r.model_dump() for r in unresolved],
                          'issues': issues, 'quality': checks}
                      for c, (figures, unresolved, issues, checks) in sorted(situations.items())}
    source_data = [store.source(n).model_dump() for n in names]
    file_data = [f.model_dump() for n in names for f in files[n]]
    scan_issues = [{'source': n, 'path': p, 'reason': r} for n in names for p, r in store.issues(n)]
    interpreters = {'extract': interpreter.model_dump(), **({'triage': triage.model_dump()} if triage else {})}
    out.mkdir(parents=True, exist_ok=True)
    (out / 'evidence.json').write_text(json.dumps({'schema_version': 2, 'sources': source_data, 'files': file_data,
        'interpreters': interpreters, 'evidence': [e.model_dump() for e in evidence], 'coverage': coverage,
        'sections': [{'content': c, **x.model_dump()} for c, items in sorted(sections.items()) for x in items],
        'situation': situation_data, 'scan_issues': scan_issues}, indent=2, ensure_ascii=False), encoding='utf-8')
    left, right = ([e for c in dict.fromkeys(f.content for f in files[n]) for e in by_content[c]] for n in names)
    log.info(f"Comparing {len(left)} × {len(right)} extracted claims via retrieval")
    progress = Progress('compare', client, heartbeat=settings.heartbeat_seconds)
    data = compare(left, right, store.folder, client, args.mode, progress=progress)
    progress.close()
    interpreters['compare'] = comparison_interpreter(settings).model_dump()
    data.update(schema_version=2, created_at=datetime.now(timezone.utc).isoformat(),
        sources=source_data, files=file_data, interpreters=interpreters, scan_issues=scan_issues,
        file_difference=file_difference(files[names[0]], files[names[1]]),
        sections=[{'content': c, **x.model_dump()} for c, items in sorted(sections.items()) for x in items],
        situation=situation_data,
        evidence=[e.model_dump() for e in evidence], coverage=coverage,
        settings={**settings.model_dump(), 'base_url': redact_url(settings.base_url)},
        usage={'api_calls': client.calls, 'cache_hits': client.cache_hits, **client.usage}, limitations=LIMITATIONS)
    store.save_comparison(data['created_at'], data)
    write_report(data, out, assets=store.folder / 'assets')
    incomplete = (any(r['status'] not in ('complete',) for r in coverage) or not left or not right
                  or data['retrieval']['omitted_by_pair_limit'] > 0 or any(f.get('processing_error') for f in data['findings']))
    print(f"Report: {out / 'report.html'}" + (' (incomplete source coverage)' if incomplete else ''))
    # 2 makes automation aware of incomplete processing; uncertainty still appears
    # in the report even when all tasks completed successfully.
    return 2 if incomplete else 0

def extract_sources(store, client, names, files, progress):
    """Evidence for every content item of the sources: loaded from the store, extracted
    (all sources' PDFs in one fair-share queue), or none if uninterpretable.

    Returns (evidence by content, coverage rows, sections by content).
    """
    by_content, coverage, sections = {}, [], {}
    queues = []
    for name in names:
        queue = []
        for file in files[name]:
            if file.content in by_content:
                continue
            extension = '.' + file.content.rsplit('.', 1)[1] if '.' in file.content else None
            if extension in ARCHIVES:
                by_content[file.content] = []  # a container; its members are files in their own right
            elif store.is_extracted(file.content):
                log.info(f'Loaded from store: {file.path}')
                by_content[file.content] = store.evidence(file.content)
                coverage.extend(store.coverage(file.content))
                sections[file.content] = store.sections(file.content)
            elif extension != '.pdf':
                reason = f'No adapter for {extension} files yet' if extension else 'No file extension; not interpreted'
                row = {'content': file.content, 'page': None, 'bbox': None, 'task': 'unsupported', 'image': None,
                       'status': 'skipped', 'issues': [reason], 'claims': 0}
                store.record_task(row, [])
                store.mark_extracted(file.content)
                by_content[file.content] = []
                coverage.append(row)
            else:
                by_content[file.content] = None  # claimed by this source's queue
                queue.append(pdf_job(store, name, file, by_content, coverage, sections))
        queues.append(queue)
    if any(queues):
        log.info(f"Extracting {sum(map(len, queues))} PDF(s): " + ', '.join(
            f'{name} {len(q)}' for name, q in zip(names, queues)))
        run_jobs(queues, store.folder, client, progress=progress)
    coverage.sort(key=lambda r: (r['content'], r['page'] or 0, r['task']))  # independent of completion order
    return by_content, coverage, sections

def situate_sources(store, client, names, files, by_content, sections):
    """Figures and section "about" statements for each fully extracted PDF: loaded from
    the store, or requested (figures first, then sections, per PDF).

    Quality checks run on every run, for loaded results too.
    Returns {content: (figures, unresolved references, issues, quality)}; sections are updated in place.
    """
    import pymupdf
    situations, todo, loaded = {}, [], []
    for name in names:
        for file in files[name]:
            content = file.content
            if content in situations or not content.endswith('.pdf') or not store.is_extracted(content):
                continue
            found = store.situation(content)
            if found is not None:
                sections[content] = store.sections(content)
                loaded.append((name, file.path, content))
            else:
                todo.append((name, file.path, content))
            situations[content] = found
    open_pdf = lambda name, path: pymupdf.open(stream=read_origin(store.origin(name, path)), filetype='pdf')
    for name, path, content in loaded:
        figures, unresolved, issues = situations[content]
        with open_pdf(name, path) as doc:
            situations[content] += (quality(doc, figures, sections[content], unresolved, by_content[content]),)
    if not todo:
        return situations
    log.info(f"Situating {len(todo)} PDF(s)")
    progress = Progress('situate', client, heartbeat=client.s.heartbeat_seconds)
    with Dispatcher(client) as dispatch:
        for name, path, content in todo:
            with open_pdf(name, path) as doc:
                figures, found, unresolved, issues = situate(doc, content, by_content[content], sections.get(content, []),
                                                             store.folder, client, dispatch, progress)
                checks = quality(doc, figures, found, unresolved, by_content[content])
            store.record_situation(content, figures, found, unresolved, issues)
            sections[content] = found
            situations[content] = (figures, unresolved, issues, checks)
            failed = sum(i['failed'] for i in issues)
            if failed:
                log.warning(f'Situating {path}: {failed} request(s) failed; the next run retries them')
    progress.close()
    return situations

def pdf_job(store, source, file, by_content, coverage, sections):
    def keep_sections(found):
        sections[file.content] = found
        store.record_sections(file.content, found)
    def done(evidence, ledger):
        # Failed or unreached tasks (e.g. the call limit) are retried on the next run; the rest replays from cache.
        if not any(r['status'] in ('failed', 'not_reached') for r in ledger):
            store.mark_extracted(file.content)
        by_content[file.content] = evidence
        coverage.extend(ledger)
        log.debug(f'Extracted {file.path}: {len(evidence)} claim(s)')
    return Job(file.content, lambda: read_origin(store.origin(source, file.path)), store.record_task, keep_sections, done)

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
    with Store(args.store) as store:
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
