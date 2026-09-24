"""Command line: compare two sources, and manage declared sources in a store.

    pdf-semantic-diff A B --out DIR                     # shortcut: A and B are files, folders or zips
    pdf-semantic-diff compare --store DIR NAME NAME     # declared sources, or --manifest FILE
    pdf-semantic-diff source add|list|show|update|remove|export|import ...
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from . import manifest
from .compare import compare
from .extract import extract_pdf, visual_regions
from .llm import Client, redact_url
from .models import Settings, Source
from .provenance import comparison_interpreter, extraction_interpreter, normalized_extension
from .report import write_report
from .scan import ARCHIVES, Limits, read_origin, scan
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
        return shortcut_command(argv)
    except (OSError, ValueError, RuntimeError) as e:
        print(f'Error: {e}', file=sys.stderr)
        return 1

# --- options shared by commands that run the model ---------------------------------

def add_run_options(parser):
    parser.add_argument('--config', type=Path, help='Settings JSON; overrides environment defaults, CLI flags override it')
    parser.add_argument('--mode', choices=['proposals', 'revisions'], default='proposals')
    parser.add_argument('--model')
    parser.add_argument('--base-url')
    parser.add_argument('--context-tokens', type=int)
    parser.add_argument('--max-calls', type=int)
    parser.add_argument('--top-k', type=int)
    parser.add_argument('--no-vision', action='store_true', help='Explicitly incomplete text-only run')
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
        print(f"{'Updated' if existing else 'Linked'} source {source.name!r} from {path}", file=sys.stderr)
    return source.name

# --- the run -----------------------------------------------------------------------

def plan(sources, settings):
    import pymupdf
    result = []
    for source in sources:
        scanned = scan(source.roots, limits(settings))
        pages = visual = pdfs = 0
        for f in scanned.files:
            if f.content.endswith('.pdf'):
                pdfs += 1
                with pymupdf.open(stream=read_origin(f.origin), filetype='pdf') as doc:
                    pages += len(doc)
                    visual += sum(len(visual_regions(p, settings.tile_points)) for p in doc) if settings.vision else 0
        result.append({'source': source.name, 'files': len(scanned.files), 'pdfs': pdfs, 'pages': pages,
                       'visual_tasks': visual, 'issues': len(scanned.issues)})
    print(json.dumps({'sources': result, 'max_calls': settings.max_calls,
        'note': 'Native text/table extraction, pair comparisons, retries and adaptive refinement add calls; '
                'no API requests made.'}, indent=2))
    return 0

def run(args, settings, store, names, out, force_rescan=False):
    interpreter = extraction_interpreter(settings)
    if args.dry_run:
        print(json.dumps({'would_clear': store.bind(interpreter, reset=True, dry_run=True)}, indent=2))
        return 0
    cleared = store.bind(interpreter, reset=args.reset)
    if cleared:
        print(f"Reset cleared: {json.dumps(cleared)}", file=sys.stderr)
    if settings.rescan == 'auto' or force_rescan:
        for name in names:
            summary = store.rescan(name, limits(settings), document_properties)
            changes = {k: len(summary[k]) for k in ('added', 'removed', 'changed') if summary[k]}
            print(f"Scanned {name}: {summary['files']} files" + (f", {changes}" if changes else ''), file=sys.stderr)
    client = Client(settings, store)
    files = {name: store.files(name) for name in names}
    by_content, coverage, sections = {}, [], {}
    for name in names:
        for file in files[name]:
            if file.content not in by_content:
                by_content[file.content] = extract_content(store, client, name, file, coverage, sections)
    evidence = [e for items in by_content.values() for e in items]
    source_data = [store.source(n).model_dump() for n in names]
    file_data = [f.model_dump() for n in names for f in files[n]]
    scan_issues = [{'source': n, 'path': p, 'reason': r} for n in names for p, r in store.issues(n)]
    interpreters = {'extract': interpreter.model_dump()}
    out.mkdir(parents=True, exist_ok=True)
    (out / 'evidence.json').write_text(json.dumps({'schema_version': 2, 'sources': source_data, 'files': file_data,
        'interpreters': interpreters, 'evidence': [e.model_dump() for e in evidence], 'coverage': coverage,
        'scan_issues': scan_issues}, indent=2, ensure_ascii=False), encoding='utf-8')
    left, right = ([e for c in dict.fromkeys(f.content for f in files[n]) for e in by_content[c]] for n in names)
    print(f"Comparing {len(left)} × {len(right)} extracted claims via retrieval", file=sys.stderr)
    data = compare(left, right, store.folder, client, args.mode)
    interpreters['compare'] = comparison_interpreter(settings).model_dump()
    data.update(schema_version=2, created_at=datetime.now(timezone.utc).isoformat(),
        sources=source_data, files=file_data, interpreters=interpreters, scan_issues=scan_issues,
        sections=[{'content': c, **x.model_dump()} for c, items in sections.items() for x in items],
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

def extract_content(store, client, source, file, coverage, sections):
    """Evidence for one piece of content: from the store, by extraction, or none if uninterpretable."""
    extension = '.' + file.content.rsplit('.', 1)[1] if '.' in file.content else None
    if extension in ARCHIVES:
        return []  # an archive is a container; its members are files in their own right
    if store.is_extracted(file.content):
        print(f'Loaded from store: {file.path}', file=sys.stderr)
        coverage.extend(store.coverage(file.content))
        sections[file.content] = store.sections(file.content)
        return store.evidence(file.content)
    if extension != '.pdf':
        reason = f'No adapter for {extension} files yet' if extension else 'No file extension; not interpreted'
        row = {'content': file.content, 'page': None, 'bbox': None, 'task': 'unsupported', 'image': None,
               'status': 'skipped', 'issues': [reason], 'claims': 0}
        store.record_task(row, [])
        store.mark_extracted(file.content)
        coverage.append(row)
        return []
    print(f'Extracting {file.path}', file=sys.stderr)
    def keep_sections(found):
        sections[file.content] = found
        store.record_sections(file.content, found)
    evidence, ledger = extract_pdf(read_origin(store.origin(source, file.path)), file.content, store.folder, client,
                                   on_task=store.record_task, on_sections=keep_sections)
    # Failed tasks (e.g. the call limit) are retried on the next run; the rest replays from cache.
    if not any(r['status'] == 'failed' for r in ledger):
        store.mark_extracted(file.content)
    coverage.extend(ledger)
    return evidence

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
            print(f'Removed source {args.name!r}; {len(store.orphaned_content())} content item(s) now orphaned', file=sys.stderr)
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
                print(f"Warning: {len(different)} file(s) differ from the manifest's hashes: {different[:5]}", file=sys.stderr)
    return 0

def require(store, name):
    source = store.source(name)
    if source is None:
        raise StoreError(f'no source named {name!r}')
    return source

def print_scan(summary, name):
    print(f"Scanned {name}: {summary['files']} files ({len(summary['added'])} added, {len(summary['removed'])} removed, "
          f"{len(summary['changed'])} changed), {len(summary['issues'])} issue(s)", file=sys.stderr)
    for path, reason in summary['issues'][:20]:
        print(f'  {path}: {reason}', file=sys.stderr)

if __name__ == '__main__':
    sys.exit(main())
