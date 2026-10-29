"""A comparison's report: report.json, and report.html as one file that travels alone, its parts written here once
each, gzipped inside the page and put together by its script (report.js), its crops embedded as a byte budget allows
(crops.py; docs/plans/portable-reports-2026-10-19.md)."""
from . import crops, topics
from .values import claim_value, unit_tables
from .html_pages import embed_json, esc, page as html_page
import base64
import gzip
import json
import re
from importlib import resources
from pathlib import Path
from collections import Counter

def how_read(e):
    """How a claim's table was read, from its derivation: ("rules", the template that made it), ("summary", the
    statistic), ("row", "") for a table row read by itself, or None for a claim from text or a picture."""
    steps = {d["step"]: d.get("detail", "") for d in e.get("derivation", [])}
    if "table-rules" in steps:
        return ("rules", steps["table-rules"])
    if "table-summary" in steps:
        return ("summary", steps["table-summary"])
    if any(step.endswith("-table") for step in steps):
        return ("row", "")
    return None

def read_as(how):
    """A table reading in words."""
    kind, detail = how
    return {"rules": f"by rules a model wrote for its table ({detail})", "summary": f"by a summary ({detail})",
            "row": "its row read by itself"}[kind]

def tables_read(a, b):
    """{"a": how, "b": how} when two compared claims' tables were read differently (one by rules, the other row by
    row; or by different templates), else None: a difference between them may come from the reading, not the source
    (the owner, 2026-10-05: "tracing/reporting how a table was read")."""
    ha, hb = how_read(a), how_read(b)
    if ha is None or hb is None or ha == hb or (ha[0] == hb[0] and ha[0] != "rules"):
        return None
    return {"a": read_as(ha), "b": read_as(hb)}

# An analysis of one source (`semantic-pdf-diff analyze`): its report's mode. It has no findings; every claim is
# listed, in the Claims view, and browsed by topic and searched as a comparison's are.
ONE_SOURCE = "analysis"

def one_source(data):
    return data.get("mode") == ONE_SOURCE

def listed(data):
    """The claims a report lists besides its findings' ({"id"} at least): a comparison's without a counterpart, an
    analysis's every claim."""
    return [{"id": e["id"]} for e in data["evidence"]] if one_source(data) else data["unmatched"]

def traced(data):
    """The report document with each finding between claims whose tables were read differently marked (tables_read),
    settled before the comparison is saved, so the store keeps what the report shows (code review 2026-10-08, D8:
    write_report marked them after the save)."""
    evidence = {e["id"]: e for e in data["evidence"]}
    findings = []
    for f in data["findings"]:
        differ = tables_read(evidence[f["a"]], evidence[f["b"]]) if f["a"] in evidence and f["b"] in evidence else None
        kept = {k: v for k, v in f.items() if k != "tables_read"}
        findings.append({**kept, "tables_read": differ} if differ else kept)
    return {**data, "findings": findings}

# How each format names where a claim is: the unit a page is (a PDF's page, a deck's slide), and the place within it.
PAGE_WORDS = {"pptx": "slide", "xlsx": "sheet", "csv": "file"}
PLACES = {"text": lambda loc: f"lines {loc['lines'][0]}–{loc['lines'][1]}",
          "docx": lambda loc: f"paragraphs {loc['paragraphs'][0]}–{loc['paragraphs'][1]}",
          "pptx": lambda loc: f"slide {loc['page']}, lines {loc['lines'][0]}–{loc['lines'][1]}",
          "xlsx": lambda loc: f"sheet {loc['sheet']}, cells {loc['cells']}",
          "csv": lambda loc: f"lines {loc['file_lines'][0]}–{loc['file_lines'][1]}, fields {loc['fields'][0]}–"
                             f"{loc['fields'][1]}"}

def place(loc):
    """Where a claim is within its page, as its format names it (a PDF's: its box)."""
    named = PLACES.get(loc.get('format'))
    return named(loc) if named else f"PDF bbox {[round(x, 1) for x in loc['bbox']]}"

STYLE = '''
:root{font-family:system-ui,sans-serif}body{max-width:1200px;margin:32px auto;padding:0 24px}
h1{font-size:36px;letter-spacing:-1px}h2{font-size:20px}h3{font-size:15px;color:var(--accent)}.meta{color:var(--muted)}
div.subject table{table-layout:fixed}div.subject th:first-child{width:28%}
article,header,details.coverage,div.subject{background:var(--card);border:1px solid var(--line);\
border-radius:12px;padding:22px;margin:18px 0}
.pair{display:grid;grid-template-columns:1fr 1fr;gap:24px}\
section{min-width:0;padding:12px;background:var(--panel);border-radius:8px}
img{display:block;max-width:100%;max-height:500px;margin:14px auto}\
blockquote{border-left:3px solid var(--rule);margin:14px 0;padding-left:12px}
small{overflow-wrap:anywhere}table{border-collapse:collapse;width:100%;font-size:13px}\
td,th{text-align:left;border-bottom:1px solid var(--line);padding:8px}
select,input{padding:10px;border:1px solid var(--field);border-radius:6px;margin:8px;\
background:var(--card);color:var(--fg)}
pre{white-space:pre-wrap}.warning{color:var(--warn)}summary{cursor:pointer}a{color:var(--accent)}
img.crop{cursor:zoom-in}article.claim img.crop{max-height:160px}img.crop.full,article.claim img.crop.full\
{max-height:none;cursor:zoom-out}\
.shot{position:relative;display:block;width:fit-content;max-width:100%;margin:14px auto}.shot img{margin:0}\
.shot .mark{position:absolute;outline:2px solid var(--bad);outline-offset:2px;border-radius:2px;\
pointer-events:none}.cut{color:var(--muted);font-size:13px}
button.more,.topics button,.views button{padding:10px 16px;margin:8px 0;border:1px solid var(--field);\
border-radius:6px;background:var(--card);color:var(--fg);cursor:pointer}.topics button{padding:6px 10px;margin:4px 2px}\
.topics button.on,.views button.on{background:var(--accent);color:var(--card)}.views{margin:18px 0 4px}\
.views button{font-size:15px;margin-right:6px}.topics button small{color:inherit;opacity:.7}
#query{width:min(28em,90%)}#order-box{white-space:nowrap}mark{background:var(--mark);color:inherit;border-radius:2px}\
.search-help{font-size:13px;margin:0 8px}.search-help ul{margin:6px 0}\
.linked{outline:3px solid var(--accent);outline-offset:3px}\
button.like,button.link{padding:0 6px;border:1px solid var(--field);border-radius:4px;background:var(--card);\
color:var(--accent);cursor:pointer;font-size:12px}\
#also button{padding:4px 8px;margin:2px;border:1px solid var(--field);border-radius:6px;background:var(--card);\
color:var(--fg);cursor:pointer}#also small{opacity:.7}
@media(max-width:700px){.pair{grid-template-columns:1fr}body{padding:0 12px}}
'''
# The page's script: it inflates the report's parts and shows them, and finds what's searched (files beside this one,
# so they read as code).
SCRIPT = "\n".join(resources.files(__package__).joinpath(name).read_text(encoding="utf-8")
                   for name in ("search.js", "report.js"))
# What the search box takes (search.js), beside it.
SEARCH_HELP = ('<details class="search-help"><summary>How to search</summary><ul>'
               '<li><code>feed pump</code>: both words, in any order, as the start of a word (<i>pump</i> finds '
               '<i>pumps</i>); case and accents ignored. Numbers match whole: <code>75</code> doesn\'t find 750, '
               '<code>1,000</code> finds 1000, <code>75kW</code> finds 75 kW.</li>'
               '<li><code>"feed pump"</code>: the words in a row. <code>-gearbox</code>: without it. '
               '<code>blade OR rotor</code>: either.</li>'
               '<li>Values compared, across units: <code>&gt;50kW</code> (or <code>&gt;50 kW</code>) finds 0.075 MW '
               'too; <code>&lt;=0.1MW</code>, <code>value:10-20mm</code> (a range), <code>value:75kW</code> (that '
               'value). Without a unit, numbers compare as written. A range or bound a claim states (50–60, '
               '≤ 39) is found where it meets the search\'s.</li>'
               '<li>In one part of a claim: <code>entity:</code>, <code>attribute:</code>, <code>value:</code> (with '
               'its unit), <code>conditions:</code>, <code>quote:</code>, <code>section:</code>, <code>file:</code> (a '
               'file\'s name is searched only so); '
               '<code>page:12</code> or <code>page:10-20</code>.</li>'
               '<li><code>like:</code> and a claim\'s id, as each card\'s <i>Claims like this</i> searches: the claims '
               'sharing enough of the words of what it\'s about (its entity, attribute, conditions, and its value\'s '
               'words), most alike first; where the claims were embedded (<code>embed_model</code>), near it in '
               'meaning too. <code>near:</code> and an id: by meaning alone. <code>meaning:"…"</code>, what\'s typed '
               'by meaning, is the command line\'s.</li>'
               '<li>In the claims view, the claims the findings pair with those found come after them, as their '
               'counterparts. Where a counterpart names what was searched otherwise (<i>nominal power</i> for '
               '<i>rated output</i>), its name is offered as a search. Where the model was asked the documents\' '
               'other names for one thing (<code>search_names</code>), a search for one name finds the others\' '
               'claims too, after the rest, each marked.</li>'
               '<li>Found items come most relevant first: words in what a claim is about count most, then its value, '
               'conditions and section, then its quote. The page\'s address keeps the search, to bookmark or send.'
               '</li></ul></details>')

class Cards:
    """A report's claims as cards: each with where it is, what it says, its quote and how it was read. Called with a
    claim's id, it gives the card's place in a finding or list; each card is written once (html), and the page's
    script puts it in each place. What a claim says (its statement and quote) is written once however many claims
    say it (said: {its HTML: its index}), and cards refer to it (the owner, 2026-10-19: "shared structure for subsets
    of identical claims"). crop(claim) gives a card's crop: an embedded image, or why there's none."""
    def __init__(self, data, crop=lambda e: ''):
        self.evidence, self.crop = {e["id"]: e for e in data["evidence"]}, crop
        self.html, self.said, self.said_of = {}, {}, {}
        self.occurrences = {}
        for f in data["files"]:
            self.occurrences.setdefault(f["content"], []).append(f"{f['source']} / {f['path']}")
        self.headings = {(x["content"], x["id"]): " > ".join(x["heading_path"]) for x in data.get("sections", [])}
        self.records = {(r["content"], r["id"]): r for r in data.get("records", [])}

    def context(self, e):
        """Where a claim sits and what reaches it, as its records and position say (the records lever): its name as
        printed, its list item and the list's lead-in, the table, notes and legends it's under."""
        lines = []
        if e.get("printed"):
            lines.append(f"As printed: {esc(e['printed'])}")
        position = e.get("position")
        if position:
            listed = self.records.get((e["content"], position.get("list", "")), {})
            lead = listed.get("text") or position.get("lead", "")
            lines.append(f"Position: {esc(position['label'])}" + (f" of “{esc(clip(lead))}”" if lead else ""))
        for rid in e.get("records", []):
            r = self.records.get((e["content"], rid))
            if r and r["kind"] != "list":
                lines.append(f"{esc(r['kind'].capitalize())}: {esc(r['label'])}"
                             + (f" — {esc(clip(r['text']))}" if r.get("text") else ""))
        return "".join(f"<p>{line}</p>" for line in lines)

    def where(self, content):
        return "; ".join(self.occurrences.get(content, ["unregistered content"]))

    def __call__(self, eid):
        if eid not in self.html:
            self.html[eid] = self.card(eid)
        return f'<div data-card="{esc(eid)}"></div>'

    def card(self, eid):
        e = self.evidence[eid]
        image = self.crop(e)
        verified = {True: '<p>Quote found in the file\'s text.</p>' if e['locator'].get('format') in PLACES
                    else '<p>Quote found in PDF text layer.</p>',
                    False: '<p class="warning">Quote not found in the PDF text layer for this region; possible misread '
                           'or raster-only label.</p>'
                    }.get(e.get('quote_verified'), '')
        loc = e['locator']
        basis = f"<p>Basis: {esc(e['basis'])}</p>" if e.get('basis', 'unknown') != 'unknown' else ''
        frame = f"<p>Frame: {esc(e['frame'])}</p>" if e.get('frame') else ''
        others = e.get('occurrences', [])[1:] if len(e.get('occurrences', [])) > 1 else []
        seen_by = sorted({o['locator']['region'] for o in e.get('occurrences', [])})
        also = (f"<p>Found {len(e['occurrences'])} times ({esc(', '.join(seen_by))}): "
                + esc('; '.join(f"p.{o['locator']['page']} {o['locator']['region']}" for o in e['occurrences']))
                + "</p>") if others else ''
        how = how_read(e)
        read = f"<p>Read {esc(read_as(how))}.</p>" if how else ''
        heading = self.headings.get((e['content'], e.get('section', '')), '')
        heading = f" · § {esc(heading)}" if heading else ''
        said = (f"<b>{esc(e['entity'])} — {esc(e['attribute'])}</b><p>{esc(e['value'])} {esc(e['unit'])}</p>"
                f"<p>Conditions: {esc(e['conditions'] or 'unspecified')}</p>{frame}{basis}"
                f"<blockquote>{esc(e['quote'])}</blockquote>")
        self.said_of[eid] = self.said.setdefault(said, len(self.said))
        return f'''<section><h3>{esc(self.where(e['content']))}{heading} · \
{PAGE_WORDS.get(loc.get('format'), 'page')} {loc['page']} · {esc(e['kind'])}</h3>
        <div data-said="{self.said_of[eid]}"></div>{self.context(e)}{verified}{read}{also}
        <small>{esc(eid)} · {esc(loc['region'])} region, {esc(place(loc))} · confidence {e['confidence']:.2f}</small>\
{image}</section>'''

CLIP = 160  # characters of a record's text shown beside a claim

def clip(text):
    text = " ".join(text.split())
    return text if len(text) <= CLIP else text[:CLIP - 1].rstrip() + "…"

def finding_html(f, card):
    """One finding: its relation (and kind, if explained), why, and its two claims' cards."""
    numeric = '<pre>'+esc(json.dumps(f['numeric'],indent=2))+'</pre>' if f.get('numeric') else ''
    title = f['relation'].title() + (' (settled without a model)' if f.get('settled') else '')
    why = f.get('explanation')
    if why:
        title += ': ' + KINDS[why['kind']][0].lower()
        why = (f"<p><b>{esc(KINDS[why['kind']][1])}.</b> {esc(why['rationale'])}"
               f" <small>(explanation confidence {why['confidence']})</small></p>")
    editorial = "".join(f"<p>Editorial: {esc(note)}</p>" for note in f.get('editorial', ()))
    editorial += "".join(f"<p class='warning'>Context changed: {esc(RECORD_KINDS.get(label, label))} (see Context "
                         "changes)</p>" for label in f.get('context_changed', ()))
    differ = (f"<p class='warning'>Their tables were read differently: A {esc(f['tables_read']['a'])}; B "
              f"{esc(f['tables_read']['b'])}. The difference may come from the "
              "reading.</p>") if f.get('tables_read') else ''
    rerank = f"; reranker's score {f['rerank_score']}" if 'rerank_score' in f else ''
    how = 'alignment' if f.get('settled') else 'model'
    return f'''<article data-relation="{esc(f['relation'])}" \
data-kind="{esc(f.get('explanation', {}).get('kind', ''))}"><h2>{esc(title)}</h2>
        {why or ''}<p>{esc(f['rationale'])}</p>{editorial}{differ}<div class="pair">{card(f['a'])}{card(f['b'])}</div>
        <details><summary>Calculation and matching details</summary>{numeric}<p>Retrieval score \
{f['retrieval_score']}{rerank}; {how} confidence {f['confidence']}</p></details></article>'''

def header_html(data, listed=True):
    """The report's header: the sources, the mode, the findings counted, the files' differences (unless the files'
    table lists them: listed=False), the caveats and the run's metadata."""
    counts = Counter(f['relation'] for f in data['findings'])
    issues = [r for r in data['coverage'] if r['status'] != 'complete']
    if one_source(data):
        return analysis_header_html(data, issues)
    page = '<header><p class="meta">ENGINEERING EVIDENCE REVIEW</p><h1>Semantic PDF comparison</h1>'
    page += f"<p>{' ↔ '.join(esc(x['name']) for x in data['sources'])}</p><p>Mode: {esc(data['mode'])}</p>"
    if data.get('paused'):
        page += (f"<p class='warning'>Paused: {esc(data['paused'])}. What the cap cut followed the order answers came "
                 "in, so this report isn't reproducible: rerun the same command to resume.</p>")
    differently = sum(1 for f in data['findings'] if f.get('tables_read'))
    retrieval = data.get('retrieval', {})
    if retrieval.get('omitted_by_pair_limit'):
        page += (f"<p class='warning'>{retrieval['omitted_by_pair_limit']} of {retrieval['candidate_pairs']} candidate "
                 f"pairs weren't judged: a comparison judges at most {retrieval['attempted_pairs']}, best first "
                 "(<code>--max-pairs</code>, or <code>max_pairs</code> in a <code>--config</code> file).</p>")
    found = ', '.join(f"{counts[r]} {r}" for r in ('different', 'uncertain', 'complementary', 'equivalent')
                      if counts[r])
    page += f"<p>Findings: {esc(found or 'none')}</p>"
    if counts['unrelated']:  # retrieval's candidates the judge found unrelated: on their claims, not findings
        page += (f"<p>{counts['unrelated']} candidate pairs were judged unrelated: not findings. In the Claims view, "
                 "each claim says what it was compared with.</p>")
    page += kinds_html(data['findings'], esc) + (
        f"<p class='warning'>{differently} findings compare claims whose tables were read differently (by rules, a "
        "summary or row by row): a difference there may come from the reading.</p>" if differently else '') + (
        f"<p class='warning'>{len(issues)} incomplete, failed or skipped source tasks. {len(data['unmatched'])} "
        "claims lack a confirmed counterpart.</p>")
    page += record_changes_html(data.get('record_changes', ()), esc)
    diff = data.get('file_difference')
    if diff and listed:
        render = lambda item: esc(' → '.join(item) if isinstance(item, list) else item)
        page += ('<details><summary>Files: '
                 + ', '.join(f"{len(diff[k])} {k}" for k in ('unchanged', 'modified', 'moved', 'added', 'removed'))
                 + '</summary>')
        page += ''.join(f"<p><b>{k.title()}</b></p><ul>" + ''.join(f"<li>{render(i)}</li>" for i in diff[k]) + "</ul>"
                        for k in ('modified', 'moved', 'added', 'removed', 'unchanged') if diff[k]) + '</details>'
    page += ('<p>Model conclusions require review. “Complete” means the extractor reported no local issue, not proof '
             'of exhaustive coverage. Unmatched claims do not establish additions or deletions.</p>')
    page += ('<p>Revision mode treats the first source as the earlier version and the second as the later one. '
             'Proposal mode treats both symmetrically; neither is ranked.</p>')
    page += ('<details><summary>Run metadata and limitations</summary><p>Every detail is in <code>report.json</code>; '
             'what the page shows elsewhere (groupings, sections, situating, files) is left out here.</p><pre>'
             + esc(json.dumps({k: v for k, v in data.items() if k not in SHOWN_ELSEWHERE}, indent=2))
             + '</pre></details></header>')
    return page

def analysis_header_html(data, issues):
    """An analysis's header: the source, its files and claims counted, the caveats and the run's metadata."""
    files = data.get('files', [])
    page = ('<header><p class="meta">ENGINEERING EVIDENCE REVIEW</p><h1>Source analysis</h1>'
            f"<p>{esc(data['sources'][0]['name'])}: {len(data['evidence'])} claims read from {len(files)} "
            f"file{'s' if len(files) != 1 else ''}</p>")
    if data.get('paused'):
        page += (f"<p class='warning'>Paused: {esc(data['paused'])}. What the cap cut followed the order answers came "
                 "in, so this report isn't reproducible: rerun the same command to resume.</p>")
    if issues:
        page += f"<p class='warning'>{len(issues)} incomplete, failed or skipped source tasks.</p>"
    page += ('<p>Model conclusions require review. “Complete” means the extractor reported no local issue, not proof '
             'of exhaustive coverage.</p>')
    page += ('<details><summary>Run metadata and limitations</summary><p>Every detail is in <code>report.json</code>; '
             'what the page shows elsewhere (sections, situating, files) is left out here.</p><pre>'
             + esc(json.dumps({k: v for k, v in data.items() if k not in SHOWN_ELSEWHERE}, indent=2))
             + '</pre></details></header>')
    return page

# A report document's parts the page shows in their own places, left out of its run metadata (each file's grows with
# the files compared: the revisions' groupings were 208 KB of TS 38.300's 1.4 MB, gzipped).
SHOWN_ELSEWHERE = ('evidence', 'coverage', 'findings', 'unmatched', 'shared', 'groupings', 'sections', 'situation',
                   'records', 'record_changes', 'files', 'file_difference', 'scan_issues', 'index')

RECORD_KINDS = {"note": "Note", "legend": "Legend", "list": "List lead-in", "table": "Table"}

def record_changes_html(changes, esc):
    """Context records restated between the revisions (the record_changes lever), each once with how many claims it
    reaches: what every claim under it means may have changed, whatever its value."""
    if not changes:
        return ''
    def said(side):
        return ' '.join(x for x in (side['text'], ' | '.join(side['items'])) if x)
    def around(a, b):  # both sides from a little before where they first differ
        first = next((i for i, (x, y) in enumerate(zip(a, b)) if x != y), min(len(a), len(b)))
        start = a.rfind(' ', 0, max(0, first - 40)) + 1 if first > 60 else 0
        return [('…' if start else '') + clip(t[start:]) for t in (a, b)]
    items = ''.join(f"<li><b>{esc(RECORD_KINDS.get(c['kind'], c['kind']))}"
                    f"{(' ' + esc(c['label'])) if c['label'] else ''}</b>: “{esc(was)}” → “{esc(now)}”; reaches "
                    f"{len(c['claims'])} claims</li>"
                    for c in changes for was, now in [around(said(c['earlier']), said(c['later']))])
    return (f"<section><h2>Context changes ({len(changes)})</h2><p>A note, lead-in or table heading restated: what "
            f"the claims under it mean may have changed, whatever their values.</p><ul>{items}</ul></section>")

def write_report(data, output, assets=None, budget=crops.DEFAULT_BUDGET, write=True, split=False):
    """Write report.json and report.html, one file holding its crops (rendered into `assets`, default output/assets)
    as far as the byte budget allows, in crops.py's order of value, and its indexes beside them (indexfiles.py).
    Returns the budget's account (crops.Account);
    with write=False, only the account (`report --dry-run`). With split, and more than one pair of files, the page is
    one file a pair of files instead, each under the budget, and an index, in report-split/ (SPLIT)."""
    output = Path(output)
    assets = Path(assets) if assets else output / "assets"
    stored = lambda image: assets / image.split("/", 1)[1] if image.startswith("assets/") else output / image
    saved = data  # report.json: the comparison as the store keeps it
    if not data.get('index'):  # one saved before indexes: built for its files and page, report.json as it was
        from . import indexes
        data = {**data, 'index': indexes.built(data)}
    if write:  # its indexes beside it: index.md, index.xlsx, index/*.csv
        from . import indexfiles
        indexfiles.written(data['index'], {e['id']: e for e in data['evidence']}, output)
    pairs = file_pairs(data) if split else []
    if len(pairs) > 1:
        return write_split(data, output, pairs, stored, budget, write, saved)
    page, account = report_page(data, stored, budget)
    if write:
        output.mkdir(exist_ok=True, parents=True)
        (output/"report.json").write_text(json.dumps(saved, indent=2, ensure_ascii=False), encoding="utf-8")
        (output/'report.html').write_text(page, encoding='utf-8')
    return account

SPLIT = "report-split"  # a split report's folder, beside report.json
# the index's links to its parts carry its address on (#claims&q=pump), so each part opens on that view and search
CARRY = ('<script>document.addEventListener("click", (e) => {const a = e.target.closest("a[href]"); '
         'if (a && location.hash && !a.getAttribute("href").includes("#")) a.href = a.getAttribute("href") '
         '+ location.hash;});</script>')

def write_split(data, output, pairs, stored, budget, write, saved=None):
    """One report file a pair of files (its findings, those reaching other pairs' files too, and its claims without a
    counterpart), each under the budget, and index.html listing them: a folder to zip and send, for comparisons too
    large for one file (the owner, 2026-10-19: "or distribution with a zip folder"). The account adds up the parts'."""
    folder = output / SPLIT
    total = crops.Account(budget)
    parts, counted = [], set()
    for i, (kind, a, b) in enumerate(pairs):
        note = (f'<p class="meta">Part {i + 1} of {len(pairs)} of a split report ({esc(pair_name(kind, a, b))}): '
                '<a href="index.html">every pair of files</a></p>')
        page, account = report_page(part_of(data, kind, a, b), stored, budget, note)
        name = f"{i + 1:02d}-" + re.sub(r"[^A-Za-z0-9._-]+", "-", Path((b or a)[0]).stem).strip("-") + ".html"
        parts.append((name, page))
        total.page += account.page
        total.size += account.size
        total.wanted += [c for c in account.wanted if c.image not in counted]
        counted |= {c.image for c in account.wanted}
        total.chosen |= account.chosen
        total.names.update(account.names)
    files = file_index(pairs)
    split = (f'<p class="meta">A split report: a file a pair of files, {len(pairs)} in this folder beside this '
             'index. Keep them together (zip the folder to send it); each opens on its own too.</p>')
    index = html_page('Semantic PDF comparison', split + header_html(data, listed=False) + files_html(
        data, pairs, files, total, Cards(data).where, links=[name for name, _ in parts]) + CARRY, STYLE)
    total.size += len(index.encode())
    if write:
        folder.mkdir(exist_ok=True, parents=True)
        (output/"report.json").write_text(json.dumps(saved or data, indent=2, ensure_ascii=False), encoding="utf-8")
        (folder / "index.html").write_text(index, encoding="utf-8")
        for name, page in parts:
            (folder / name).write_text(page, encoding="utf-8")
    return total

def part_of(data, kind, a, b):
    """The report document of one pair of files: its findings (with those reaching other pairs' files), its claims
    without a counterpart, and what those claims need to be shown."""
    mine = {x[1] for x in (a, b) if x}
    content = {e['id']: e['content'] for e in data['evidence']}
    findings = [f for f in data['findings'] if content.get(f['a']) in mine or content.get(f['b']) in mine]
    unmatched = [u for u in data['unmatched'] if content.get(u['id']) in mine]
    shared = [x for x in data.get('shared', []) if content.get(x) in mine]
    ids = {x for f in findings for x in (f['a'], f['b'])} | {u['id'] for u in unmatched} | set(shared)
    shown = {content[x] for x in ids if x in content} | mine
    keep = lambda rows: [r for r in rows if r.get('content') in shown]
    paths = [x[0] for x in (a, b) if x]
    difference = {k: [] for k in ('unchanged', 'modified', 'moved', 'added', 'removed')}
    difference[kind].append(paths if kind in ('modified', 'moved') else paths[0])
    return {**data, 'findings': findings, 'unmatched': unmatched, 'shared': shared,
            'evidence': [e for e in data['evidence'] if e['id'] in ids], 'coverage': keep(data['coverage']),
            'sections': keep(data.get('sections', [])), 'records': keep(data.get('records', [])),
            'situation': {c: x for c, x in data.get('situation', {}).items() if c in mine},
            'files': [f for f in data.get('files', []) if f['content'] in shown], 'file_difference': difference,
            'groupings': [g for g in data.get('groupings', []) if ids & set(g['earlier_claims'] + g['later_claims'])],
            'record_changes': [c for c in data.get('record_changes', []) if ids & set(c['claims'])]}

def report_page(data, stored, budget, note=''):
    """report.html's text (note above it), its crops embedded as the budget allows, and the budget's account."""
    shown = ordered(data['findings'])
    where = Cards(data).where
    def label(e):
        loc = e['locator']
        return (f"{where(e['content'])}, {PAGE_WORDS.get(loc.get('format'), 'page')} {loc['page']}, "
                f"{loc.get('task', loc.get('region', ''))}: {e['entity']} — {e['attribute']}")
    account = crops.Account(budget, names={f['content']: where(f['content']) for f in data.get('files', [])})
    account.wanted = crops.wanted({e["id"]: e for e in data["evidence"]}, shown, listed(data),
                                  data.get('shared', []), label, lambda image: stored(image).exists(),
                                  crop_finder(data))
    mime, encode = crops.encoder()
    crops.encode(account.wanted, stored, encode)
    account.page = len(page_html(data, shown, stored, [], account, mime, note).encode())  # every crop left out
    chosen = crops.choose(account.wanted, budget - account.page)
    while True:  # the page's text changes a little with what's embedded: never over budget for it
        account.chosen = {c.image for c in chosen}
        page = page_html(data, shown, stored, chosen, account, mime, note)
        account.size = len(page.encode())
        if account.size <= budget or not chosen:
            break
        chosen.pop()
    return page, account

def page_vectors(vectors, cards):
    """The claims' vectors a page's search reads (the embed lever's): {"dimensions", "vectors", "of": {card: index}},
    only those of its cards; none without them."""
    if not vectors or not vectors.get('vectors'):
        return None
    kept, of = {}, {}
    for card in cards:
        if card in vectors['of']:
            of[card] = kept.setdefault(vectors['of'][card], len(kept))
    return {"dimensions": vectors['dimensions'], "vectors": [vectors['vectors'][i] for i in kept], "of": of}

def ordered(findings):
    """Findings in the order a report shows them: explained differences first, value changes leading (KINDS' order);
    the rest as found."""
    order = {k: i for i, k in enumerate(KINDS)}
    return sorted(findings, key=lambda f: order.get(f.get('explanation', {}).get('kind'), len(KINDS)))

def file_index(pairs):
    """Each file's content numbered as the page's file filter numbers it: in the pairs' order."""
    return {c: i for i, c in enumerate(dict.fromkeys(x[1] for _, a, b in pairs for x in (a, b) if x and x[1]))}

def report_topics(data):
    """The candidate ways of splitting a report's claims into topics (topics.ways), and the claims, each with its
    side (its source), in the report's order: the findings', the unmatched, the shared."""
    order = [x for f in data['findings'] for x in (f['a'], f['b'])] + [u['id'] for u in listed(data)]
    ids = list(dict.fromkeys(order + list(data.get('shared', []))))
    evidence = {e['id']: e for e in data['evidence']}
    side = {}
    for f in data.get('files', []):
        side.setdefault(f['content'], f['source'])
    claims = [{**evidence[x], 'side': side.get(evidence[x]['content'], '')} for x in ids if x in evidence]
    return (topics.ways(claims, [c['side'] for c in claims], one_source(data)) if claims else []), claims

def browsing(data):
    """The topics a report's findings are browsed by, each shown claim's, and their names: (the way, {claim id: its
    topic's index}, names); the model's way and names where it chose (the topic_names lever), else the most even
    way named by its words; no way for fewer than two topics."""
    found, claims = report_topics(data)
    chosen = data.get('topics', {})
    way = next((w for w in found if w.name == chosen.get('way') and w.topics == chosen.get('topics')), None)
    names = chosen.get('names') if way else None
    way = way or topics.best(found)
    if way is None or len(way.topics) < 2:
        return None, {}, []
    return (way, {c['id']: t for c, t in zip(claims, way.placed) if t is not None},
            names or [topics.label(words) for words in way.topics])

def crop_finder(data):
    """crop_of(claim): its crop, the image it was read from, else its task's (a table's its rules were written from:
    the task's coverage row records it)."""
    of_task = {(r['content'], r['task']): r['image'] for r in data.get('coverage', []) if r.get('image')}
    return lambda e: e.get('image') or of_task.get((e['content'], e['locator'].get('task')))

def crop_html(e, embedded, stored, crop_of):
    """A card's crop: its embedded image (enlarged by a click), the claim marked on it where it's known, or why it
    has none."""
    image = crop_of(e)
    if not image:
        return ''
    if image in embedded:
        alt = "The image the model read" if e.get('image') else "The table its rules were written from"
        mark = e.get('mark')
        box = (f'<i class="mark" style="left:{mark[0]:.1%};top:{mark[1]:.1%};width:{mark[2] - mark[0]:.1%};'
               f'height:{mark[3] - mark[1]:.1%}"></i>') if mark else ''
        return (f'<span class="shot"><img class="crop" data-crop="{embedded[image]}" alt="{alt}" '
                f'title="Click to enlarge">{box}</span>')
    if not stored(image).exists():
        return f"<p class='cut'>Crop not found in the store ({esc(image)}).</p>"
    return (f"<p class='cut'>Crop left out for the report's size budget ({esc(e['locator'].get('task', ''))}): "
            "see Crops left out.</p>")

def page_html(data, shown, stored, chosen, account, mime="image/webp", note=''):
    """report.html: its parts gzipped inside it (each card once), the chosen crops, and the script showing them;
    note above them (a split report's part says so)."""
    embedded = {c.image: i for i, c in enumerate(chosen)}
    crop_of = crop_finder(data)
    card = Cards(data, lambda e: crop_html(e, embedded, stored, crop_of))
    pairs = file_pairs(data)
    paths = own_files(data) if one_source(data) else {}  # an analysis's files, each filtered by alone
    files = file_index(pairs) if not paths else {c: i for i, c in enumerate(paths)}
    page = note + header_html(data, listed=len(pairs) <= 1) + crops_note(account)
    if len(pairs) > 1:
        page += files_html(data, pairs, files, account, card.where)
    shown = [f for f in shown if f['relation'] != 'unrelated']  # retrieval's misses: on their claims, not findings
    findings = [{"relation": f['relation'], "kind": f.get('explanation', {}).get('kind', ''),
                 "cards": [f['a'], f['b']], "html": finding_html(f, card),
                 "files": [files.get(card.evidence[x]['content'], -1) for x in (f['a'], f['b'])]} for f in shown]
    for f, record in zip(shown, findings):  # equivalent, and saying the same in both: folded unless asked for
        record["same"] = f['relation'] == 'equivalent' and card.said_of[f['a']] == card.said_of[f['b']]
    way, topic_of, names = browsing(data)
    for f, record in zip(shown, findings):
        record["topics"] = [topic_of.get(f['a'], -1), topic_of.get(f['b'], -1)]
    sides = [s['name'] for s in data['sources']]
    claims = claim_records(data, card, files, topic_of, sides)
    one = one_source(data)  # an analysis: its claims alone, no findings, no sides or how claims fared
    if way:
        page += topic_coverage_html(claims, names, sides)
    index = data.get('index') or {}
    subjects, figures = index.get('subjects', []), index.get('figures', [])
    page += ('<div class="views"><button data-view="findings"' + (' hidden' if one else ' class="on"')
             + '>Findings ' + str(len(findings)) + '</button><button data-view="claims"'
             + (' class="on"' if one else '') + '>Claims ' + str(len(claims)) + '</button>'
             + (f'<button data-view="subjects">Subjects {len(subjects)}</button>' if subjects else '')
             + (f'<button data-view="figures">Figures and tables {len(figures)}</button>' if figures else '')
             + '</div>')
    page += ('<span data-for="findings"><label>Show <select id="filter"><option value="all">All relations</option>'
             + ''.join('<option>' + r + '</option>' for r in ['different', 'equivalent', 'complementary', 'uncertain'])
             + '</select></label>')
    if any('explanation' in f for f in data['findings']):
        page += ('<label>Kind <select id="kind"><option value="all">All kinds</option>'
                 +''.join(f'<option value="{k}">{esc(v[0])}</option>' for k, v in KINDS.items())+'</select></label>')
    same = sum(1 for record in findings if record["same"])
    if same:
        page += (f'<label><input type="checkbox" id="same" checked> Fold the {same} equivalent findings whose two '
                 'claims say the same</label>')
    hide = ' hidden' if one else ''
    page += ('</span><span data-for="claims" hidden><label' + hide + '>Side <select id="side"><option value="all">'
             'Both sources</option>'
             + ''.join(f'<option value="{i}">{esc(name)}</option>' for i, name in enumerate(sides))
             + '</select></label><label' + hide + '>Claims <select id="status"><option value="all">However they fared'
             '</option>'
             + ''.join(f'<option value="{k}">{esc(v)}</option>' for k, v in STATUSES.items()
                       if any(c['status'] == k for c in claims))
             + '</select></label><label>Read as <select id="claimkind"><option value="all">Any kind</option>'
             + ''.join(f'<option>{k}</option>' for k in ('text', 'table', 'chart', 'diagram'))
             + '</select></label><label id="counterparts-box" hidden><input type="checkbox" id="counterparts" checked> '
             + ('and their counterparts and other names' if data.get('synonyms', {}).get('items')
                or data.get('synonyms', {}).get('properties') else 'and their counterparts') + '</label></span>')
    if len(pairs) > 1:
        page += ('<label>File <select id="file"><option value="all">All files</option>'
                 + ''.join(f'<option value="{pair_key(a, b, files)}">{esc(pair_name(kind, a, b))}</option>'
                           for kind, a, b in pairs) + '</select></label>')
    elif len(paths) > 1:
        page += ('<label>File <select id="file"><option value="all">All files</option>'
                 + ''.join(f'<option value="{files[c]}">{esc(path)}</option>' for c, path in paths.items())
                 + '</select></label>')
    page += ('<input id="query" type="search" placeholder="Search: words, &quot;a phrase&quot;, -without, entity:…" '
             'aria-label="Search the findings or claims shown"> <label id="order-box" hidden>Order <select id="order">'
             '<option value="relevance">Most relevant first</option><option value="listed">As listed</option></select>'
             '</label><span id="count" class="meta"></span><div id="also" class="meta" hidden></div>' + SEARCH_HELP)
    if way:
        named = 'named by the model; ' if data.get('topics', {}).get('names') else ''
        title = (f'({esc(way.name)}{"; named by the model" if named else ""})' if one else
                 f'found in both sources ({esc(way.name)}; {named}a finding is in its claims\' topics)')
        page += ('<div class="topics"><span class="meta" title="Claims split by the words of what they are about, '
                 f'{title}">Topics:</span>'
                 + ''.join(f'<button data-topic="{t}" title="{esc(", ".join(words))}">{esc(name)} <small></small>'
                           '</button>' for t, (words, name) in enumerate(zip(way.topics, names)))
                 + '<button data-topic="-1">In no topic <small></small></button></div>')
    page += subjects_html(subjects, index.get('sources', [])) + figures_html(figures, len(sides) > 1)
    page += '<main></main>'
    page += groupings_html(data.get('groupings', []), esc)
    page += situating(data.get('situation', {}), data.get('sections', []), card.where, esc)
    issues_found = ''.join('<tr><td>'+esc(i['source'])+'</td><td>'+esc(i['path'])+'</td><td>'+esc(i['reason'])
                           +'</td></tr>' for i in data.get('scan_issues', []))
    page += ('<details class="coverage"><summary>Files not scanned ('+str(len(data.get('scan_issues', [])))
             +'): hidden, unsafe or over limits</summary><table><thead><tr><th>Source</th><th>Path</th><th>Reason</th>'
             '</tr></thead><tbody>'+issues_found+'</tbody></table></details>')
    from .retiling import path_text, tile_lines
    coverage = ''.join('<tr><td>'+esc(card.where(r['content']))+'</td><td>'
                       +esc(r['page'] if r['page'] is not None else '')+'</td><td>'+esc(r['task'])
                       +(f" ({esc(path_text(r['tiling']))})" if r.get('tiling') else '')+'</td><td>'
                       +esc(r['status'])+'</td><td>'+esc('; '.join(r['issues']))+'</td></tr>' for r in data['coverage'])
    tiles = ''.join(f'<p class="meta">{esc(line)}.</p>' for line in tile_lines(data['coverage']))
    page += ('<details class="coverage"><summary>Source coverage ledger</summary>' + tiles
             + '<table><thead><tr><th>File</th>'
             '<th>Page</th><th>Task</th><th>Status</th><th>Issues</th></tr></thead><tbody>'+coverage
             +'</tbody></table></details>')
    page += crops_left_out_html(account)
    units, folded, kinds = unit_tables()  # what the search compares values in (search.js, values.py)
    values = {eid: v for eid in card.html if (v := claim_value(card.evidence[eid])) is not None}
    parts = {"page": page, "findings": findings, "claims": claims, "cards": card.html, "said": list(card.said),
             "values": values, "units": units, "folded": folded, "kinds": kinds,
             "synonyms": {k: data.get('synonyms', {}).get(k, []) for k in ('items', 'properties')},
             "vectors": page_vectors(data.get('vectors'), card.html)}
    packed = json.dumps(parts, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    packed = base64.b64encode(gzip.compress(packed, 9, mtime=0)).decode("ascii")  # mtime=0: the same bytes each time
    images = embed_json({"type": mime, "data": [c.data for c in chosen]})
    body = ('<div id="report"><p class="meta">Opening the report…</p></div><noscript><p class="warning">This report '
            'is shown by its script: open it in a browser with JavaScript on.</p></noscript>'
            f'<script type="application/gzip" id="report-data">{packed}</script>'
            f'<script type="application/json" id="report-crops">{images}</script><script>{SCRIPT}</script>')
    return html_page('Source analysis' if one else 'Semantic PDF comparison', body, STYLE)

def subjects_html(subjects, sources):
    """The Subjects view (indexes.py): each subject, its other names and its properties, each value linked to its
    claim's card; in a comparison a column a source, "—" where one gives nothing (weak: not saying isn't absence).
    A search shows the subjects whose words it has (data-text)."""
    if not subjects:
        return ''
    many = len(sources) > 1
    def values(vs):
        return '<br>'.join(f'<a href="#claim={esc(v["claim"])}">{esc(said_of(v))}</a> <small>{esc(v["where"])}</small>'
                           for v in vs) or '—'
    out = []
    for s in subjects:
        names = [n for n in s['names'] if n.casefold() != s['name'].casefold()]  # ("Airfoil" isn't also "airfoil")
        meta = ([f"also {', '.join(names[:8])}"] if names else []) + (
            ['claims: ' + ', '.join(f"{src} {len(s['claims'].get(src, []))}" for src in sources)
             + (f" (matched by {s['matched_by']})" if s['matched_by'] else '')] if many else [])
        heads = ''.join(f'<th>{esc(src)}</th>' for src in sources) if many else '<th>Values</th>'
        rows = ''.join(
            f"<tr><td>{esc(p['name'])}</td>"
            + (''.join(f"<td>{values([v for v in p['values'] if v['source'] == src])}</td>" for src in sources)
               if many else f"<td>{values(p['values'])}</td>") + '</tr>' for p in s['properties'])
        words = ' '.join([s['name'], *names, *(p['name'] for p in s['properties'])]).casefold()
        out.append(f'<div class="subject" data-text="{esc(words)}"><h3>{esc(s["name"])}</h3>'
                   + (f'<p class="meta">{esc("; ".join(meta))}</p>' if meta else '')
                   + f'<table><thead><tr><th>Property</th>{heads}</tr></thead><tbody>{rows}</tbody></table></div>')
    return ('<section data-for="subjects" class="index" hidden><p class="meta">Each subject as its claims name it '
            '(a tag, else its words), its properties and every value given, each linked to its claim'
            + ('; a source giving nothing for one is marked “—”: not saying isn\'t evidence of absence' if many else '')
            + '. Also in index.md and index.xlsx, beside this page.</p>' + ''.join(out) + '</section>')

def said_of(v):
    unit = '' if v['unit'] in ('', '-') else v['unit']  # "-": none
    return ' '.join(x for x in (str(v['value']), unit) if x) + (f" ({v['conditions']})" if v['conditions'] else '')

def figures_html(figures, many):
    """The Figures and tables view: each figure, drawing sheet and table, where it is, what it's about, and its
    claims (the first linked)."""
    if not figures:
        return ''
    rows = ''.join(
        f'<tr data-text="{esc(" ".join([f["label"], f["title"], f["about"], f["file"]]).casefold())}">'
        + (f'<td>{esc(f["source"])}</td>' if many else '')
        + f'<td>{esc(f["file"])}</td><td>{esc(f["page"] if f["page"] is not None else "")}</td>'
        f'<td>{esc(f["kind"])}</td><td>{esc(f["label"])}</td><td>{esc(f["title"])}</td><td>{esc(f["about"])}</td>'
        + (f'<td><a href="#claim={esc(f["claims"][0])}">{len(f["claims"])}</a></td>' if f['claims'] else '<td>0</td>')
        + '</tr>' for f in figures)
    heads = ('<th>Source</th>' if many else '') + ''.join(
        f'<th>{h}</th>' for h in ('File', 'Page', 'Kind', 'Label', 'Title or caption', 'About', 'Claims'))
    return ('<section data-for="figures" class="index" hidden><p class="meta">The figures, drawing sheets and tables '
            'found, with what situating said each is about (PDFs, when it ran) and the claims read from it.</p>'
            f'<table><thead><tr>{heads}</tr></thead><tbody>{rows}</tbody></table></section>')

# How a claim fared in the comparison, as the claims view filters it.
STATUSES = {"findings": "In findings", "compared": "Compared, no counterpart", "unaligned": "Possibly added or removed",
            "regrouped": "In a split or merge candidate", "ranked_out": "Ranked out before judging",
            "not_compared": "Not compared", "shared": "In both sources", "read": "Read (one source)"}

def claim_records(data, card, files, topic_of, sides):
    """Every claim of both sources, as the claims view lists them (the owner, 2026-10-20: "an easily searchable
    database of claims even without the comparisons"): each with its side, file, topic, kind, how it fared (STATUSES)
    and its card; a claim compared without a counterpart lists what it was compared with and why it wasn't one (the
    pairs judged unrelated, which aren't findings)."""
    from collections import defaultdict
    unrelated, related = defaultdict(list), defaultdict(Counter)
    for f in data['findings']:
        if f['relation'] == 'unrelated':
            unrelated[f['a']].append((f['b'], f['rationale']))
            unrelated[f['b']].append((f['a'], f['rationale']))
        else:
            related[f['a']][f['relation']] += 1
            related[f['b']][f['relation']] += 1
    lone, shared = {u['id']: u for u in data['unmatched']}, set(data.get('shared', []))
    side = {}
    for f in data.get('files', []):
        side.setdefault(f['content'], sides.index(f['source']) if f['source'] in sides else -1)
    brief = lambda e: f"{e['entity']} — {e['attribute']}: {e['value']} {e['unit']}".strip()
    records = []
    ordered = sorted(data['evidence'], key=lambda e: (side.get(e['content'], -1), files.get(e['content'], -1),
                                                      e['content'], e['locator']['page'], e['locator'].get('task', ''),
                                                      e['id']))
    for e in ordered:
        eid, compared = e['id'], ''
        if len(sides) == 1:  # an analysis: nothing to say of how it fared
            status, said = 'read', ''
        elif eid in shared:
            status, said = 'shared', 'In both sources: the same content, not compared'
        elif related[eid]:
            status, said = 'findings', 'In findings: ' + ', '.join(f"{n} {r}" for r, n in sorted(related[eid].items()))
        elif unrelated[eid] or lone.get(eid, {}).get('status') == 'no_confirmed_counterpart':
            status = 'compared'
            said = (f"Compared with {len(unrelated[eid])} claim{'s' if len(unrelated[eid]) != 1 else ''} of the other "
                    "source; none is its counterpart" if unrelated[eid] else lone[eid]['note'])
            compared = ''.join(f"<li>{esc(brief(card.evidence[o]))} <small>— {esc(why)}</small></li>"
                               for o, why in unrelated[eid] if o in card.evidence)
            compared = (f"<details><summary>What it was compared with</summary><ul>{compared}</ul></details>"
                        if compared else '')
        elif lone.get(eid, {}).get('status') in ('unaligned', 'regrouped', 'ranked_out'):
            status, said = lone[eid]['status'], lone[eid]['note']
        else:
            status, said = 'not_compared', lone.get(eid, {}).get('note', 'Not compared')
        said = f'<p class="meta">{esc(said)}</p>' if said else ''
        html = f'<article class="claim">{said}{card(eid)}{compared}</article>'
        records.append({"card": eid, "side": side.get(e['content'], -1), "kind": e['kind'], "status": status,
                        "files": [files.get(e['content'], -1)], "topics": [topic_of.get(eid, -1)], "html": html})
    return records

def topic_coverage_html(claims, names, sides):
    """Each topic's claims on each side, and how many are in findings: where the two sources overlap, and where one
    is silent."""
    count = Counter((c['topics'][0], c['side'], c['status'] == 'findings') for c in claims)
    rows = ''
    found = ((lambda t, s: '') if len(sides) == 1  # one source: nothing is in findings
             else (lambda t, s: f" <small>({count[t, s, True]} in findings)</small>"))
    for t, name in [*enumerate(names), (-1, 'In no topic')]:
        cells = ''.join(f"<td>{count[t, s, True] + count[t, s, False]}{found(t, s)}</td>" for s in range(len(sides)))
        if any(count[t, s, x] for s in range(len(sides)) for x in (True, False)):
            rows += (f'<tr><td>{esc(name)}</td>{cells}<td><button class="pick-topic" data-topic="{t}">Claims</button>'
                     '</td></tr>')
    heads = ''.join(f'<th>{esc(name)}</th>' for name in sides)
    said = 'What each source says, by topic' if len(sides) > 1 else 'Its claims, by topic'
    return (f'<details class="coverage" open><summary>{said}</summary><table><thead><tr>'
            f'<th>Topic</th>{heads}<th></th></tr></thead><tbody>{rows}</tbody></table></details>')

def own_files(data):
    """An analysis's files: {content: its path}, by path (a content at two paths, by the first)."""
    paths = {}
    for f in sorted(data.get('files', []), key=lambda f: f['path']):
        paths.setdefault(f['content'], f['path'])
    return paths

def file_pairs(data):
    """The compared files in pairs, as the files' difference has them: (kind, the first source's (path, content), the
    second's), a missing side None; modified and moved pairs, then files removed and added, then unchanged ones (on
    both sides, the same content)."""
    diff = data.get('file_difference')
    names = [s['name'] for s in data.get('sources', [])]
    if not diff or len(names) != 2:
        return []
    sides = [{f['path']: f['content'] for f in data.get('files', []) if f['source'] == name} for name in names]
    at = lambda side, path: (path, sides[side].get(path))
    return ([(kind, at(0, pa), at(1, pb)) for kind in ('modified', 'moved') for pa, pb in diff[kind]]
            + [('removed', at(0, p), None) for p in diff['removed']]
            + [('added', None, at(1, p)) for p in diff['added']]
            + [('unchanged', at(1, p), at(1, p)) for p in diff['unchanged']])

def pair_key(a, b, files):
    """A file pair's files, as the page's file filter names them ("3,4": their indexes)."""
    return ",".join(str(files[x[1]]) for x in dict.fromkeys(x for x in (a, b) if x and x[1] in files))

def pair_name(kind, a, b):
    if kind in ('modified', 'moved'):
        return f"{a[0]} → {b[0]}" + (" (moved)" if kind == 'moved' else "")
    return f"{(a or b)[0]} ({kind})"

def files_html(data, pairs, files, account, where, links=None):
    """The files compared, a row a pair: its findings by relation (those reaching a file of another pair counted
    apart), its claims without a counterpart, and its crops embedded; each a button showing its findings, or with
    links (a split report's index), a link to its own file."""
    evidence = {e['id']: e['content'] for e in data['evidence']}
    rows = []
    for i, (kind, a, b) in enumerate(pairs):
        mine = {x[1] for x in (a, b) if x}
        touching = [f for f in data['findings'] if evidence.get(f['a']) in mine or evidence.get(f['b']) in mine]
        across = sum(1 for f in touching if not (evidence.get(f['a']) in mine and evidence.get(f['b']) in mine))
        counts = Counter(f['relation'] for f in touching)
        found = ', '.join(f"{counts[r]} {r}" for r in ('different', 'uncertain', 'complementary', 'equivalent',
                                                         'unrelated') if counts[r]) or 'none'
        lone = sum(1 for u in data['unmatched'] if evidence.get(u['id']) in mine)
        wanted = [c for c in account.wanted if c.content in mine]
        shown = sum(1 for c in wanted if c.image in account.chosen)
        rows.append(f"<tr><td>{esc(pair_name(kind, a, b))}</td><td>{esc(found)}"
                    + (f" <small>({across} reaching other files)</small>" if across else "")
                    + f"</td><td>{lone}</td><td>{f'{shown} of {len(wanted)}' if wanted else '—'}</td><td>"
                    + (f'<a href="{esc(links[i])}">Open</a>' if links else
                       f'<button class="pick" data-files="{pair_key(a, b, files)}">Show</button>' if touching else '')
                    + "</td></tr>")
    diff = data['file_difference']
    summary = ', '.join(f"{len(diff[k])} {k}" for k in ('modified', 'moved', 'added', 'removed', 'unchanged')
                        if diff[k])
    return ('<details class="coverage" open><summary>Files: ' + esc(summary) + '</summary><table><thead><tr>'
            '<th>File</th><th>Findings</th><th>Without a counterpart</th><th>Crops embedded</th><th></th></tr></thead>'
            '<tbody>' + ''.join(rows) + '</tbody></table></details>')

def crops_note(account):
    """The header's word on crops the budget left out (none: nothing to say)."""
    cut = account.cut
    if not cut:
        return ''
    return (f"<p class='warning'>{len(cut)} of {len(account.wanted)} crops left out for the report's size budget of "
            f"{crops.sized(account.budget)}, the findings to check and pictured claims first: see Crops left out."
            "</p>")

def crops_left_out_html(account):
    """The crops the budget left out, in the order they'd have been embedded."""
    cut = account.cut
    if not cut:
        return ''
    rows = ''.join(f"<tr><td>{esc(crops.GROUPS[c.group])}</td><td>{esc(c.label)}</td><td>{crops.sized(c.size)}"
                   "</td></tr>" for c in cut)
    return (f'<details class="coverage"><summary>Crops left out ({len(cut)})</summary><p>The report is one file; its '
            f"crops fill the size budget ({crops.sized(account.budget)}) in order of value: claims in different "
            "or uncertain findings, then complementary ones and claims possibly added or removed, then the rest; "
            "within each, claims read from a chart, diagram or table, or whose quote isn't in the page's text, first. "
            "<code>semantic-pdf-diff report --report-budget SIZE</code> writes it again with another budget, and "
            "<code>--dry-run</code> says what that would leave out.</p><table><thead><tr><th>Shown in</th>"
            f"<th>Crop</th><th>Size</th></tr></thead><tbody>{rows}</tbody></table></details>")

def unpacked(page):
    """A report page's HTML as its script shows it: every finding, then every claim (for tests and tools)."""
    import html
    found = re.search(r'<script type="application/gzip" id="report-data">([^<]*)</script>', page)
    parts = json.loads(gzip.decompress(base64.b64decode(found.group(1))))
    cards = lambda text: re.sub(r'<div data-card="([^"]*)"></div>',
                                lambda m: parts["cards"][html.unescape(m.group(1))], text)
    fill = lambda text: re.sub(r'<div data-said="(\d+)"></div>', lambda m: parts["said"][int(m.group(1))], cards(text))
    return parts["page"].replace("<main></main>", "<main>" + "".join(fill(f["html"]) for f in parts["findings"])
                                 + "</main>" + "".join(fill(c["html"]) for c in parts["claims"]))

# A difference's kind (explain.py): its name, and what it means, in the order the report lists them.
KINDS = {"changed": ("Changed", "The same item and property under the same conditions; its value was revised"),
         "conditions": ("Conditions changed",
                        "The same item and property; the conditions or scope it's stated for changed"),
         "renamed": ("Renamed", "The same item and value under a new name, tag or number"),
         "moved": ("Moved", "The same statement in another section, table or row"),
         "restated": ("Restated", "The same meaning in other words, units, precision or format"),
         "split_or_merge": ("Split or merge", "One item became several, or several became one"),
         "renumbered": ("Renumbered", "The same statement at another place in its list (the editorial lever)"),
         "misread": ("Misread", "A claim doesn't say what its source says"),
         "not_same_item": ("Not the same item", "Different items or properties, paired by the comparison"),
         "unclear": ("Unclear", "The evidence doesn't decide")}
# The kinds as a reader weighs them: value changes, editorial changes, and differences that aren't changes.
KIND_GROUPS = (("Value changes", ("changed", "conditions")),
               ("Editorial changes", ("renamed", "moved", "restated", "split_or_merge", "renumbered")),
               ("Not changes", ("misread", "not_same_item")), ("Unclear", ("unclear",)))

def kinds_html(findings, esc):
    """The explained differences, and the editorial notes on findings, counted by kind in their groups (empty when
    there are none)."""
    found = Counter(f['explanation']['kind'] for f in findings if 'explanation' in f)
    found.update(note.split(":", 1)[0] for f in findings for note in f.get('editorial', ()))
    if not found:
        return ''
    parts = []
    for group, kinds in KIND_GROUPS:
        mine = [f"{KINDS[k][0].lower()} {found[k]}" for k in kinds if found[k]]
        if mine:
            parts.append(f"<b>{esc(group)}</b> ({sum(found[k] for k in kinds)}): {esc(', '.join(mine))}")
    return "<p>Differences explained or noted: " + "; ".join(parts) + "</p>"

GROUPING_ORDER = ("split candidate", "merge candidate", "ambiguous", "renamed", "attached", "unaligned", "matched")

def _evidence(value):
    """A grouping's evidence as words: sums as sums ("capacity: 7,650 = 4,102 + 3,548"), candidates with their
    scores, lists as lists."""
    if isinstance(value, list) and value and isinstance(value[0], dict) and 'parts' in value[0]:
        return '; '.join(f"{x['attribute']}: {x['whole']} = {' + '.join(x['parts'])}" for x in value)
    if isinstance(value, dict):
        return ', '.join(f"{k} {v}" for k, v in value.items())
    if isinstance(value, list):
        return ', '.join(map(str, value))
    return str(value)

def groupings_html(groupings, esc):
    """How alignment grouped the revisions' items, as it saw them (revisions mode): the unusual first, matched last."""
    if not groupings:
        return ''
    counts = Counter(g['kind'] for g in groupings)
    rows = []
    for g in sorted(groupings, key=lambda g: (GROUPING_ORDER.index(g['kind']) if g['kind'] in GROUPING_ORDER else 99,
                                                g['earlier'], g['later'])):
        evidence = '; '.join(f"{k.replace('_', ' ')}: {_evidence(v)}" for k, v in g.get('evidence', {}).items()
                             if v not in ([], {}, None))
        outcome = ', '.join(f"{v} {k.replace('_', ' ')}" for k, v in g.get('outcome', {}).items() if v)
        rows.append(f"<tr><td>{esc(g['kind'])}</td><td>{esc(', '.join(g['earlier']) or '—')}</td>"
                    f"<td>{esc(', '.join(g['later']) or '—')}</td><td>{esc(evidence)}</td><td>{esc(outcome)}</td></tr>")
    return ('<details class="coverage"><summary>How the revisions were grouped: '
            + esc(', '.join(f"{n} {k}" for k, n in sorted(counts.items(), key=lambda x: GROUPING_ORDER.index(x[0])
                                                                           if x[0] in GROUPING_ORDER else 99)))
            + '</summary><p>Alignment groups each revision\'s claims into items and decides which items correspond '
              'before any value is judged. This is how it saw them, not a verdict: split and merge candidates come '
              'from related names and values that add up, and aren\'t confirmed.</p>'
              '<table><thead><tr><th>Grouping</th><th>Earlier</th><th>Later</th><th>Evidence</th><th>Outcome</th></tr>'
              '</thead><tbody>' + ''.join(rows) + '</tbody></table></details>')

def situating(situation, sections, where, esc):
    """Figures, section "abouts" and their quality checks, per content."""
    if not situation:
        return ''
    flagged = sum(len(x['quality']['flags']) for x in situation.values())
    out = [f'<details class="coverage"><summary>Situating: figures and sections ({flagged} quality flags)</summary>',
           '<p>Model-written "about" statements place figures and sections in context. Quality flags are mechanical '
           'checks: values in an "about", terms not grounded in its material, odd lengths, missing statements.</p>']
    for content, x in situation.items():
        q = x['quality']
        flags = {}
        for flag in q['flags']:
            flags.setdefault(flag['target'], []).append(f"{flag['check']}: {flag['detail']}")
        show = lambda target: ('<p class="warning">' + esc('; '.join(flags[target]))  # noqa: B023 (called at once)
                               + '</p>') if target in flags else ''  # noqa: B023 (called at once)
        refs = q['references']
        rate = f"{refs['rate']:.0%}" if refs['rate'] is not None else 'n/a'
        fq = q['figures']
        sources = ', '.join(f"{fq[k]} from {k[len('labelled_from_'):].replace('_', ' ')}" for k in fq
                            if k.startswith('labelled_from_') and fq[k])
        out.append(f"<h3>{esc(where(content))}</h3><p>{fq['total']} figures, {fq['total'] - fq['unlabelled']} labelled"
                   f"{' (' + esc(sources) + ')' if sources else ''}, {fq['labelled_uncited']} of those never cited; "
                   f"{refs['resolved']} references resolved, {refs['unresolved']} unresolved ({rate} resolved).</p>")
        rows = ''.join(f"<tr><td>{esc(s['heading_path'] and ' > '.join(s['heading_path']) or s['id'])}</td>"
                       f"<td>{s['first_page']}–{s['last_page']}</td><td>{esc(s.get('section_type', ''))}</td>"
                       f"<td>{esc(s.get('density', ''))}</td><td>{esc(s.get('about', ''))}{show(s['id'])}"
                       f"<small>{esc(', '.join(s.get('keywords', [])))}</small></td></tr>"
                       for s in sections if s['content'] == content)
        out.append('<table><thead><tr><th>Section</th><th>Pages</th><th>Type</th><th>Density</th><th>About</th></tr>'
                   f'</thead><tbody>{rows}</tbody></table>')
        cited = lambda f: '; '.join('p.%d' % r['page'] for r in f['references']) or 'none'
        figures = x['figures']
        if figures:
            name = lambda f: (f['caption'] or ' · '.join(filter(None, [f['label'], f.get('title')]))
                              or 'unlabelled ' + f['kind'])
            rows = ''.join(f"<tr><td>{esc(name(f))}</td><td>{f['page']}</td>"
                           f"<td>{esc(f['about'])}{(' <i>' + esc(f['role']) + '</i>') if f['role'] else ''}"
                           f"{show(f['id'])}</td>"
                           f"<td>{esc(cited(f))}</td></tr>"
                           for f in figures)
            out.append('<table><thead><tr><th>Figure</th><th>Page</th><th>About</th><th>Cited on</th></tr></thead>'
                       f'<tbody>{rows}</tbody></table>')
        if x['unresolved']:
            out.append('<p>Unresolved references (possibly missed figures):</p><ul>' + ''.join(
                f"<li>p.{r['page']}: {esc(r['text'])}</li>" for r in x['unresolved'][:50]) + '</ul>')
        failed = [i for i in x['issues'] if i['failed']]
        if failed:
            out.append('<p class="warning">'
                       + esc(f"{len(failed)} situating request(s) failed; the next run retries them.") + '</p>')
    return ''.join(out) + '</details>'
