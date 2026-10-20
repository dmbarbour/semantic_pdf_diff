"""The pipeline a comparison runs: bind the store, scan the sources, extract, situate, compare, report. Moved out
of the command line (code review 2026-10-01, A3: scripts built command lines to run it), so scripts call
compare_paths() with settings and RunOptions, and the CLI only parses arguments into them.
"""
import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

from . import crops, fixtures, provenance, topics
from .compare import compare, file_difference
from .dispatch import Dispatcher
from .jobs import Job, reader_for, reader_version, run_jobs
from .llm import Client, redact_url
from .schema import EvidenceDocument, Report, Situation, Source, coverage_row
from .progress import Progress, log
from .provenance import comparison_interpreter, extraction_interpreter, normalized_extension, triage_interpreter
from .readings import reconcile
from .report import SPLIT, report_topics, traced, write_report
from .scan import ARCHIVES, Limits, read_origin
from .situate import quality, situate
from .binding import bind, redone
from .store import Store, StoreError

def limits(settings):
    return Limits(settings.max_zip_depth, settings.max_source_bytes, settings.zip_ratio_limit,
                  settings.zip_ratio_min_bytes)

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

def settings_from(config=None, layer=None, **overrides):
    """Settings as the CLI gives them: the environment, then a store's own (layer: `config set`'s), then the --config
    file, then overrides."""
    from .settings import Settings
    options = json.loads(Path(config).read_text()) if config else {}
    if not isinstance(options, dict):
        raise ValueError(f'{config}: settings file must contain a JSON object')
    return Settings.from_env(**{**(layer or {}), **options, **overrides})

def attempt(run_it, *args, **kwargs):
    """A run's exit code, an error reported as the CLI reports one (exit 1)."""
    try:
        return run_it(*args, **kwargs)
    except (OSError, ValueError, RuntimeError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

@dataclass
class RunOptions:
    """What a run takes besides its settings: how to compare, whether to start a store over, and where answers come
    from and costs go."""
    mode: str = "proposals"           # proposals or revisions
    reset: bool = False               # start the store over: everything read is read again (binding.bind)
    dry_run: bool = False             # report what the run would clear to read again, change nothing
    fixture: Path | None = None       # replay fixture (.sqlite, or a .zip to replay)
    fixture_mode: str | None = None   # fixtures.MODES; None: the fixture's default (fixtures.default_mode)
    responder: str | None = None      # whose recorded answers (default: the model's name)
    fresh_regions: tuple = ()         # the A/A control's regions, answered afresh
    ledger: Path | None = None        # every response's reported cost appended here
    ledger_tags: dict = field(default_factory=dict)
    export: Path | None = None        # a .sqlite fixture every answer served or recorded is copied into (in fresh
                                      # stores: a store holding a region's claims asks nothing for it)
    report_budget: int = crops.DEFAULT_BUDGET  # report.html's bytes, its crops included as they fit (crops.py)
    split: bool = False               # a report file a pair of files, and an index (report.SPLIT)

    @classmethod
    def from_args(cls, args, layer=None):
        """A run's options from its flags, over a store's own settings (layer) for the mode and the report's."""
        layer = layer or {}
        get = lambda name, default=None: getattr(args, name, default)
        given = lambda name, default: get(name) if get(name) is not None else layer.get(name, default)
        return cls(mode=given("mode", "proposals"), reset=bool(get("reset", False)),
                   dry_run=bool(get("dry_run", False)),
                   fixture=get("fixture"), fixture_mode=get("fixture_mode"), responder=get("responder"),
                   fresh_regions=tuple(r for r in (get("fresh_regions", "") or "").split(",") if r),
                   ledger=get("ledger"), export=get("fixture_export"),
                   report_budget=given("report_budget", crops.DEFAULT_BUDGET), split=bool(given("split", False)),
                   ledger_tags=dict(t.split("=", 1) for t in (get("ledger_tag", []) or []) if "=" in t))

    @property
    def answers_mode(self):
        """The fixture's mode: as asked, else its default (fixtures.default_mode); None without a fixture."""
        if not self.fixture:
            return None
        return self.fixture_mode or fixtures.default_mode(self.fixture)

def compare_paths(a, b, out, settings, options=None, client=None):
    """Compare two sources given as paths (files, folders or zips), each a shortcut source in the store at `out`,
    as `semantic-pdf-diff compare A B --store DIR` does. Returns its exit code (0, 2 incomplete, 3 paused for
    budget)."""
    options = options or RunOptions()
    check_fixture(options)  # before the sources are declared in the store
    with Store(out) as store:
        names = declare_paths(store, out, [Path(a), Path(b)])
        return run(options, settings, store, names, Path(out), force_rescan=True, client=client)

def declare_paths(store, out, paths):
    """Each path (a file, folder or zip) declared a shortcut source in the store at `out`, named by its final
    component; returns their names."""
    names = shortcut_names(paths)
    for name, path in zip(names, paths):
        existing = store.source(name)
        if existing and existing.kind != 'shortcut':
            raise StoreError(f"{out} already has a declared source named {name!r}: compare it by that name")
        store.save_source(Source(name=name, kind='shortcut', roots=[str(Path(path).resolve())]), replace=True)
    return names

LIMITATIONS = ['Image-token budgeting must be calibrated to the serving backend.',
               'Confidence scores are uncalibrated model self-reports.',
               'Retrieval may miss synonyms and implicit relationships; configure domain aliases.',
               'Small VLMs can misread plots, tables, scales and diagram arrows.',
               'No global engineering consistency proof or automatic proposal ranking.']

def check_fixture(options):
    """A fixture that can't be used as asked fails the run before the store is changed (trials 2026-10-08, finding 1:
    the error came after the sources were scanned)."""
    if options.fixture:
        try:
            fixtures.check(options.fixture, options.answers_mode)
        except fixtures.FixtureError as e:
            raise ValueError(str(e)) from e

def attach_ledger(client, options):
    if options.ledger:
        from .ledger import Ledger
        client.ledger = Ledger(options.ledger, **options.ledger_tags)
    return client

def budget_note(client):
    """A line saying the run paused for budget, if it did (the process exits 3)."""
    reason = getattr(client, 'out_of_budget', None)
    return f"Paused: {reason}. Rerun the same command to resume; finished work is kept." if reason else None

def run(options, settings, store, names, out, force_rescan=False, client=None):
    """A comparison of a store's sources: bound and scanned (prepare), read (read_sources), its evidence written
    (write_evidence), compared and reported (compare_and_report). Returns the exit code: 0, 2 incomplete, 3 paused for
    budget. client: a model client to use (a caller's, kept open); by default one made from the options (code review
    2026-10-08, C6: run did all six jobs, and tests patched its client in)."""
    interpreter = extraction_interpreter(settings)
    triage = triage_interpreter(settings) if settings.situate else None
    if options.dry_run:
        would = {'extract': bind(store, interpreter, reset=options.reset, dry_run=True)}
        if triage:
            would['triage'] = bind(store, triage, reset=options.reset, dry_run=True)
        print(json.dumps({'would_clear': would}, indent=2))
        return 0
    prepare(options, settings, store, names, (interpreter, triage), force_rescan)
    own = client is None
    client = make_client(options, settings, store) if own else client
    try:
        read = read_sources(store, client, settings, names, triage)
        document = write_evidence(store, names, read, {'extract': interpreter.model_dump(),
                                                        **({'triage': triage.model_dump()} if triage else {})}, out)
        return compare_and_report(options, settings, store, client, names, read, document, out)
    finally:  # also on failure, so the answers this run used stay marked as used
        if own and getattr(client, 'replay', None) is not None:
            client.close()

def prepare(options, settings, store, names, roles, force_rescan):
    """The store bound to the run's interpreters (what changed settings affect cleared, to be read again; everything,
    with --reset), readings merged as the settings say, the sources scanned."""
    check_fixture(options)
    for role in filter(None, roles):
        cleared = bind(store, role, reset=options.reset)
        if options.reset and cleared:
            log.info(f"Started over ({role.role}): {json.dumps(cleared)}")
        elif cleared:
            log.info(redone(role.role, cleared))
    if store.set_reconcile(settings.reconciles()):
        log.info("Readings merging changed: situating results will be redone")
    if settings.rescan == 'auto' or force_rescan:
        for name in names:
            summary = store.rescan(name, limits(settings), document_properties)
            changes = {k: len(summary[k]) for k in ('added', 'removed', 'changed') if summary[k]}
            log.info(f"Scanned {name}: {summary['files']} files" + (f", {changes}" if changes else ''))

@dataclass
class Read:
    """What a run read: each source's files, the claims by content, coverage, sections, situating results."""
    files: dict
    by_content: dict
    coverage: list
    sections: dict
    situations: dict
    records: dict = None  # {content: {id: ContextRecord}}, as the records lever keeps them

def read_sources(store, client, settings, names, triage):
    """The sources' content extracted, and situated if the run situates."""
    files = {name: store.files(name) for name in names}
    progress = Progress('extract', client, heartbeat=settings.heartbeat_seconds)
    by_content, coverage, sections = extract_sources(store, client, names, files, progress)
    progress.close()
    situations = situate_sources(store, client, names, files, by_content, sections, coverage) if triage else {}
    records = {c: found for c in by_content for found in [store.records(c)] if found}
    return Read(files, by_content, coverage, sections, situations, records)

def write_evidence(store, names, read, interpreters, out):
    """evidence.json, what was read, written before comparing (so it stands if comparing fails); the document."""
    evidence = [e for items in read.by_content.values() for e in items]
    situation_data = {c: Situation(figures=[f.model_dump() for f in figures],
                                   unresolved=[r.model_dump() for r in unresolved],
                                   issues=issues, quality=checks).model_dump()
                      for c, (figures, unresolved, issues, checks) in sorted(read.situations.items())}
    out.mkdir(parents=True, exist_ok=True)
    document = EvidenceDocument(sources=[store.source(n).model_dump() for n in names],
        files=[f.model_dump() for n in names for f in read.files[n]], interpreters=interpreters,
        evidence=[e.model_dump() for e in evidence], coverage=read.coverage,
        sections=[{'content': c, **x.model_dump()} for c, items in sorted(read.sections.items()) for x in items],
        situation=situation_data,
        scan_issues=[{'source': n, 'path': p, 'reason': r} for n in names for p, r in store.issues(n)],
        records=[{'content': c, **r.model_dump()} for c, found in sorted((read.records or {}).items())
                 for r in found.values()])
    (out / 'evidence.json').write_text(json.dumps(document.model_dump(), indent=2, ensure_ascii=False),
                                       encoding='utf-8')
    return document

def compare_and_report(options, settings, store, client, names, read, document, out):
    """The two sides' claims compared, the report saved in the store and written; the exit code."""
    files, by_content, coverage, sections = read.files, read.by_content, read.coverage, read.sections
    left, right = ([e for c in dict.fromkeys(f.content for f in files[n]) for e in by_content[c]] for n in names)
    log.info(f"Comparing {len(left)} × {len(right)} extracted claims via retrieval")
    progress = Progress('compare', client, heartbeat=settings.heartbeat_seconds)
    headings = {(c, x.id): " > ".join(x.heading_path) for c, items in sections.items() for x in items}
    comparing = comparison_interpreter(settings)
    data = compare(left, right, store.folder, client, options.mode, progress=progress, headings=headings,
                   label=provenance.text_hash(comparing.model_dump_json()), records=read.records)
    progress.close()
    if options.mode == 'revisions':
        data['record_changes'] = restated(settings, files[names[0]], files[names[1]], read.records or {}, left, right)
        for f in data['findings']:  # a finding whose claims a restated record reaches says so
            labels = [c['label'] or c['kind'] for c in data['record_changes'] if f['a'] in c['claims']
                      or f['b'] in c['claims']]
            if labels:
                f['context_changed'] = labels
    interpreters = {**document.interpreters, 'compare': comparing.model_dump()}
    data = Report(**data, created_at=provenance.now().isoformat(),
        sources=document.sources, files=document.files, interpreters=interpreters, scan_issues=document.scan_issues,
        file_difference=file_difference(files[names[0]], files[names[1]]),
        sections=document.sections, situation=document.situation, evidence=document.evidence, coverage=coverage,
        records=document.records,
        settings={**settings.model_dump(), 'base_url': redact_url(settings.base_url)},
        limitations=LIMITATIONS, paused=getattr(client, 'paused', None) or '').model_dump()
    data = traced(data)
    if settings.names_topics():  # the model's choice among the topics' ways, and its names (topics.py)
        from .schema import TopicNames
        found, claims = report_topics(data)
        key = ('topics', options.mode, provenance.text_hash(comparing.model_dump_json()))
        data['topics'] = topics.named(found, claims, lambda prompt: client.ask(prompt, TopicNames, (), key))
    store.save_comparison(data['created_at'], data)
    account = write_report(data, out, assets=store.folder / 'assets', budget=options.report_budget,
                           split=options.split)
    # how the run went, apart from the report, which holds only what the answers decide (the determinism review, D9)
    usage = {'api_calls': client.calls, 'cache_hits': client.cache_hits, **client.usage,
             **fixture_usage(client, options.fixture)}
    (out / 'run.json').write_text(json.dumps({'created_at': data['created_at'], 'usage': usage}, indent=2) + '\n',
                                  encoding='utf-8')
    incomplete = (any(r['status'] not in ('complete',) for r in coverage) or not left or not right
                  or data['retrieval']['omitted_by_pair_limit'] > 0
                  or any(f.get('processing_error') or f.get('explanation', {}).get('processing_error')
                         for f in data['findings']))
    split = out / SPLIT / 'index.html'
    page = split if options.split and split.exists() else out / 'report.html'
    print(f"Report: {page}" + (' (incomplete source coverage)' if incomplete else ''))
    omitted = data['retrieval']['omitted_by_pair_limit']
    if omitted:
        print(f"{omitted} of {data['retrieval']['candidate_pairs']} candidate pairs weren't judged: --max-pairs sets "
              f"how many are (now {settings.max_pairs})")
    if account.cut:
        print(crops.summary(account, store.folder))
    note = budget_note(client)
    if note:
        log.warning(note)
        return 3
    # 2 makes automation aware of incomplete processing; uncertainty still appears
    # in the report even when all tasks completed successfully.
    return 2 if incomplete else 0

def restated(settings, earlier, later, records, left, right):
    """The context records restated between two revisions (the record_changes lever), content by content: a file's
    content paired with the other side's at the same path, or the one content each side has."""
    own = lambda files: {f.content for f in files} - ({f.content for f in earlier} & {f.content for f in later})
    a, b = own(earlier), own(later)
    by_path = lambda files, mine: {f.path: f.content for f in files if f.content in mine}
    pairs = [(ca, by_path(later, b)[path]) for path, ca in sorted(by_path(earlier, a).items())
             if path in by_path(later, b)]
    if not pairs and len(a) == 1 and len(b) == 1:
        pairs = [(next(iter(a)), next(iter(b)))]
    return [change for ca, cb in pairs
            for change in settings.changed_records({ca: records.get(ca, {})}, {cb: records.get(cb, {})}, left, right)]

def answers_cache(store):
    """The answers cache a run reads and records into: the user's (settings.cache_path), whatever the store. The
    tests keep one in each store instead (tests/stubs.py), as stores once kept their own. Owner-only, as a store is:
    its answers quote the documents (a folder named by $SEMANTIC_PDF_DIFF_CACHE is left as it is)."""
    from .settings import cache_path
    return open_cache(cache_path())

def open_cache(path):
    """An answers cache, open to record into: created owner-only if missing (its folder too)."""
    if not path.parent.exists():
        path.parent.mkdir(parents=True, mode=0o700)
    cache = fixtures.open(path, 'record')
    os.chmod(path, 0o600)
    return cache

def make_client(options, settings, store):
    fixture = None
    if options.fixture:
        try:
            # an export's source, replayed, is only read: what it served is in the export, not in use marks
            mode = 'record' if options.answers_mode != 'replay' else 'read' if options.export else 'replay'
            fixture = fixtures.open(options.fixture, mode)
            export = fixtures.open(options.export, 'record') if options.export else None
        except fixtures.FixtureError as e:
            raise ValueError(str(e)) from e
        if options.answers_mode != 'replay':  # text and rendering depend on it: replay tests compare versions
            import pymupdf
            fixture.note('pymupdf', pymupdf.VersionBind)
    if fixture is None:
        return attach_ledger(Client(settings, store, cache=answers_cache(store)), options)
    fresh = list(options.fresh_regions)
    return attach_ledger(Client(settings, store, fixture=fixture, mode=options.answers_mode,
                                responder=options.responder, fresh_regions=fresh, export=export), options)

def fixture_usage(client, given=None):
    """The fixture's counts, under the path it was given (a .zip is read from a temporary copy)."""
    replay = getattr(client, 'replay', None)  # test doubles have none
    if replay is None:
        return {}
    if replay.missing:
        log.warning(f"Replay: {len(replay.missing)} request(s) have no answer from {replay.responder}; "
                    f"first: {replay.missing[0]}")
    used = {**replay.usage(), **({'path': str(given)} if given else {})}
    cache = getattr(client, 'caching', False)
    log.info(f"{'Answers cache' if cache else 'Fixture'} {replay.fixture.path.name}: {used['replayed']} answers "
             f"replayed, {used['recorded']} recorded, {used['missing']} missing")
    return {'cache' if cache else 'fixture': used}

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
            elif store.is_extracted(file.content, reader_version(extension)):
                log.info(f'Loaded from store: {file.path}')
                by_content[file.content] = store.evidence(file.content)
                coverage.extend(store.coverage(file.content))
                sections[file.content] = store.sections(file.content)
            elif reader_for(extension) is None:
                reason = (f"Reading {extension} files needs the office extra: pip install 'semantic-pdf-diff[office]'"
                          if extension in ('.docx', '.pptx', '.xlsx', '.xlsm')
                          else f'No adapter for {extension} files yet' if extension
                          else 'No file extension; not interpreted')
                row = coverage_row(content=file.content, task='unsupported', status='skipped', issues=[reason])
                store.record_task(row, [])
                store.mark_extracted(file.content, "unsupported")
                by_content[file.content] = []
                coverage.append(row)
            else:
                by_content[file.content] = None  # claimed by this source's queue
                queue.append(pdf_job(store, name, file, by_content, coverage, sections, reader_for(extension),
                                     reader_version(extension)))
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
                figures, found, unresolved, issues = situate(doc, content, by_content[content],
                                                             sections.get(content, []), store.folder, client, dispatch,
                                                             progress)
                checks = quality(doc, figures, found, unresolved, by_content[content])
            store.record_situation(content, figures, found, unresolved, issues)
            sections[content] = found
            situations[content] = (figures, unresolved, issues, checks)
            failed = sum(i['failed'] for i in issues)
            if failed:
                log.warning(f'Situating {path}: {failed} request(s) failed; the next run retries them')
    progress.close()
    return situations

def pdf_job(store, source, file, by_content, coverage, sections, reader=None, version="pdf/1"):
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
            store.mark_extracted(file.content, version)
        # Readings of one fact by different tasks become one claim when the store's runs merge them
        # (loaded evidence gets the same from store.evidence).
        by_content[file.content] = reconcile(evidence) if store.reconciles() and evidence else evidence
        coverage.extend(ledger)
        log.debug(f'Extracted {file.path}: {len(evidence)} claim(s)')
    return Job(file.content, lambda: read_origin(store.origin(source, file.path)), store.record_task, keep_sections,
               done, reader=reader)

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
