"""The pipeline a comparison runs: bind the store, scan the sources, extract, situate, compare, report. Moved out
of the command line (code review 2026-10-01, A3: scripts built command lines to run it), so scripts call
compare_paths() with settings and RunOptions, and the CLI only parses arguments into them.
"""
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

from . import fixtures, provenance
from .compare import compare, file_difference
from .dispatch import Dispatcher
from .extract import Job, reader_for, run_jobs
from .llm import Client, redact_url
from .models import EvidenceDocument, Report, Situation, Source, coverage_row
from .progress import Progress, log
from .provenance import comparison_interpreter, extraction_interpreter, normalized_extension, triage_interpreter
from .readings import reconcile
from .report import write_report
from .scan import ARCHIVES, Limits, read_origin
from .situate import quality, situate
from .store import Store, StoreError

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

NO_MODEL = "http://127.0.0.1:9/v1"  # an address nothing answers: for replays that must never reach a model

def settings_from(config=None, **overrides):
    """Settings as the CLI's --config gives them (the environment, then the file), then overrides."""
    from .models import Settings
    options = json.loads(Path(config).read_text()) if config else {}
    return Settings.from_env(**{**options, **overrides})

def attempt(run_it, *args, **kwargs):
    """A run's exit code, an error reported as the CLI reports one (exit 1)."""
    try:
        return run_it(*args, **kwargs)
    except (OSError, ValueError, RuntimeError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

@dataclass
class RunOptions:
    """What a run takes besides its settings: how to compare, whether to reset a store bound to other settings, and
    where answers come from and costs go."""
    mode: str = "proposals"           # proposals or revisions
    reset: bool = False               # clear derived data a changed interpreter affects, then run
    dry_run: bool = False             # with reset: report what would be cleared, change nothing
    fixture: Path | None = None       # replay fixture (.sqlite, or a .zip to replay)
    fixture_mode: str = "replay"      # fixtures.MODES
    responder: str | None = None      # whose recorded answers (default: the model's name)
    fresh_regions: tuple = ()         # the A/A control's regions, answered afresh
    ledger: Path | None = None        # every response's reported cost appended here
    ledger_tags: dict = field(default_factory=dict)

    @classmethod
    def from_args(cls, args):
        get = lambda name, default=None: getattr(args, name, default)
        return cls(mode=get("mode", "proposals"), reset=bool(get("reset", False)), dry_run=bool(get("dry_run", False)),
                   fixture=get("fixture"), fixture_mode=get("fixture_mode", "replay"), responder=get("responder"),
                   fresh_regions=tuple(r for r in (get("fresh_regions", "") or "").split(",") if r),
                   ledger=get("ledger"),
                   ledger_tags=dict(t.split("=", 1) for t in (get("ledger_tag", []) or []) if "=" in t))

def compare_paths(a, b, out, settings, options=None):
    """Compare two sources given as paths (files, folders or zips), each a shortcut source in the store at `out`:
    the CLI's `pdf-semantic-diff A B --out DIR`. Returns its exit code (0, 2 incomplete, 3 paused for budget)."""
    options = options or RunOptions()
    names = shortcut_names([Path(a), Path(b)])
    with Store(out) as store:
        for name, path in zip(names, [Path(a), Path(b)]):
            existing = store.source(name)
            if existing and existing.kind != 'shortcut':
                raise StoreError(f"{out} already has a declared source named {name!r}; use 'compare' instead")
            store.save_source(Source(name=name, kind='shortcut', roots=[str(Path(path).resolve())]), replace=True)
        return run(options, settings, store, names, Path(out), force_rescan=True)

LIMITATIONS = ['Image-token budgeting must be calibrated to the serving backend.',
               'Confidence scores are uncalibrated model self-reports.',
               'Retrieval may miss synonyms and implicit relationships; configure domain aliases.',
               'Small VLMs can misread plots, tables, scales and diagram arrows.',
               'No global engineering consistency proof or automatic proposal ranking.']

def attach_ledger(client, options):
    if options.ledger:
        from .ledger import Ledger
        client.ledger = Ledger(options.ledger, **options.ledger_tags)
    return client

def budget_note(client):
    """A line saying the run paused for budget, if it did (the process exits 3)."""
    reason = getattr(client, 'out_of_budget', None)
    return f"Paused: {reason}. Rerun the same command to resume; finished work is kept." if reason else None

def run(options, settings, store, names, out, force_rescan=False):
    interpreter = extraction_interpreter(settings)
    triage = triage_interpreter(settings) if settings.situate else None
    if options.dry_run:
        would = {'extract': store.bind(interpreter, reset=True, dry_run=True)}
        if triage:
            would['triage'] = store.bind(triage, reset=True, dry_run=True)
        print(json.dumps({'would_clear': would}, indent=2))
        return 0
    # Check both before clearing either, so a rejected run changes nothing.
    for role in filter(None, (interpreter, triage)):
        if not options.reset:
            store.bind(role, dry_run=True)
    for role in filter(None, (interpreter, triage)):
        cleared = store.bind(role, reset=options.reset)
        if cleared:
            log.info(f"Reset cleared ({role.role}): {json.dumps(cleared)}")
    if store.set_reconcile(settings.reconciles()):
        log.info("Readings merging changed: situating results will be redone")
    if settings.rescan == 'auto' or force_rescan:
        for name in names:
            summary = store.rescan(name, limits(settings), document_properties)
            changes = {k: len(summary[k]) for k in ('added', 'removed', 'changed') if summary[k]}
            log.info(f"Scanned {name}: {summary['files']} files" + (f", {changes}" if changes else ''))
    client = make_client(options, settings, store)
    try:
        files = {name: store.files(name) for name in names}
        progress = Progress('extract', client, heartbeat=settings.heartbeat_seconds)
        by_content, coverage, sections = extract_sources(store, client, names, files, progress)
        progress.close()
        situations = situate_sources(store, client, names, files, by_content, sections, coverage) if triage else {}
        evidence = [e for items in by_content.values() for e in items]
        situation_data = {c: Situation(figures=[f.model_dump() for f in figures], unresolved=[r.model_dump() for r in unresolved],
                                       issues=issues, quality=checks).model_dump()
                          for c, (figures, unresolved, issues, checks) in sorted(situations.items())}
        source_data = [store.source(n).model_dump() for n in names]
        file_data = [f.model_dump() for n in names for f in files[n]]
        scan_issues = [{'source': n, 'path': p, 'reason': r} for n in names for p, r in store.issues(n)]
        interpreters = {'extract': interpreter.model_dump(), **({'triage': triage.model_dump()} if triage else {})}
        out.mkdir(parents=True, exist_ok=True)
        document = EvidenceDocument(sources=source_data, files=file_data, interpreters=interpreters,
            evidence=[e.model_dump() for e in evidence], coverage=coverage,
            sections=[{'content': c, **x.model_dump()} for c, items in sorted(sections.items()) for x in items],
            situation=situation_data, scan_issues=scan_issues)
        (out / 'evidence.json').write_text(json.dumps(document.model_dump(), indent=2, ensure_ascii=False), encoding='utf-8')
        left, right = ([e for c in dict.fromkeys(f.content for f in files[n]) for e in by_content[c]] for n in names)
        log.info(f"Comparing {len(left)} × {len(right)} extracted claims via retrieval")
        progress = Progress('compare', client, heartbeat=settings.heartbeat_seconds)
        data = compare(left, right, store.folder, client, options.mode, progress=progress)
        progress.close()
        interpreters['compare'] = comparison_interpreter(settings).model_dump()
        data = Report(**data, created_at=provenance.now().isoformat(),
            sources=source_data, files=file_data, interpreters=interpreters, scan_issues=scan_issues,
            file_difference=file_difference(files[names[0]], files[names[1]]),
            sections=document.sections, situation=situation_data, evidence=document.evidence, coverage=coverage,
            settings={**settings.model_dump(), 'base_url': redact_url(settings.base_url)},
            usage={'api_calls': client.calls, 'cache_hits': client.cache_hits, **client.usage, **fixture_usage(client)},
            limitations=LIMITATIONS).model_dump()
        store.save_comparison(data['created_at'], data)
        write_report(data, out, assets=store.folder / 'assets')
        incomplete = (any(r['status'] not in ('complete',) for r in coverage) or not left or not right
                      or data['retrieval']['omitted_by_pair_limit'] > 0 or any(f.get('processing_error') for f in data['findings']))
        print(f"Report: {out / 'report.html'}" + (' (incomplete source coverage)' if incomplete else ''))
        note = budget_note(client)
        if note:
            log.warning(note)
            return 3
        # 2 makes automation aware of incomplete processing; uncertainty still appears
        # in the report even when all tasks completed successfully.
        return 2 if incomplete else 0
    finally:  # also on failure, so the answers this run used stay marked as used
        if getattr(client, 'replay', None) is not None:
            client.close()

def make_client(options, settings, store):
    fixture = None
    if options.fixture:
        try:
            fixture = fixtures.open(options.fixture, 'replay' if options.fixture_mode == 'replay' else 'record')
        except fixtures.FixtureError as e:
            raise ValueError(str(e)) from e
        if options.fixture_mode != 'replay':  # text and rendering depend on it: replay tests compare versions
            import pymupdf
            fixture.note('pymupdf', pymupdf.VersionBind)
    if fixture is None:
        return attach_ledger(Client(settings, store), options)
    fresh = list(options.fresh_regions)
    return attach_ledger(Client(settings, store, fixture=fixture, mode=options.fixture_mode, responder=options.responder,
                                fresh_regions=fresh), options)

def fixture_usage(client):
    replay = getattr(client, 'replay', None)  # test doubles have none
    if replay is None:
        return {}
    if replay.missing:
        log.warning(f"Replay: {len(replay.missing)} request(s) have no answer from {replay.responder}; "
                    f"first: {replay.missing[0]}")
    used = replay.usage()
    log.info(f"Fixture {replay.fixture.path.name}: {used['replayed']} answers replayed, {used['recorded']} recorded, "
             f"{used['missing']} missing")
    return {'fixture': used}

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
            elif reader_for(extension) is None:
                reason = ("Reading .docx files needs python-docx: pip install 'semantic-pdf-diff[office]'"
                          if extension == '.docx' else f'No adapter for {extension} files yet' if extension
                          else 'No file extension; not interpreted')
                row = coverage_row(content=file.content, task='unsupported', status='skipped', issues=[reason])
                store.record_task(row, [])
                store.mark_extracted(file.content)
                by_content[file.content] = []
                coverage.append(row)
            else:
                by_content[file.content] = None  # claimed by this source's queue
                queue.append(pdf_job(store, name, file, by_content, coverage, sections, reader_for(extension)))
        queues.append(queue)
    if any(queues):
        log.info(f"Extracting {sum(map(len, queues))} document(s): " + ', '.join(
            f'{name} {len(q)}' for name, q in zip(names, queues)))
        run_jobs(queues, store.folder, client, progress=progress)
    coverage.sort(key=lambda r: (r['content'], r['page'] or 0, r['task']))  # independent of completion order
    return by_content, coverage, sections

def situate_sources(store, client, names, files, by_content, sections, coverage):
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
            # Situated once every task has run, even if some failed: a failed task shouldn't hold
            # back the rest. Evidence that changes later (a retry succeeding) invalidates it.
            if content in situations or not content.endswith('.pdf') or by_content.get(content) is None \
                    or any(r['content'] == content and r['status'] == 'not_reached' for r in coverage):
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

def pdf_job(store, source, file, by_content, coverage, sections, reader=None):
    def keep_sections(found):
        sections[file.content] = found
        store.record_sections(file.content, found)
    def done(evidence, ledger):
        # Rows from an earlier run's tasks that this run didn't have (an interrupted run's refinements) go:
        # the store holds what this run found, so a later run that loads it reads the same.
        store.keep_tasks(file.content, [r['task'] for r in ledger])
        for row in ledger:
            if row['task'] == 'open':
                log.warning(f"Couldn't read {file.path}: {'; '.join(row['issues'])}")
        # Failed or unreached tasks (e.g. the call limit) are retried on the next run; the rest replays from cache.
        if not any(r['status'] in ('failed', 'not_reached') for r in ledger):
            store.mark_extracted(file.content)
        # Readings of one fact by different tasks become one claim when the store's runs merge them
        # (loaded evidence gets the same from store.evidence).
        by_content[file.content] = reconcile(evidence) if store.reconciles() and evidence else evidence
        coverage.extend(ledger)
        log.debug(f'Extracted {file.path}: {len(evidence)} claim(s)')
    return Job(file.content, lambda: read_origin(store.origin(source, file.path)), store.record_task, keep_sections, done,
               reader=reader)

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
