"""A comparison's report: report.json, and report.html as one file that travels alone, its parts written here once
each, gzipped inside the page and put together by its script (report.js), its crops embedded as a byte budget allows
(crops.py; docs/plans/portable-reports-2026-10-19.md)."""
from . import crops
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
article,header,details.coverage{background:var(--card);border:1px solid var(--line);\
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
img.crop{cursor:zoom-in}img.crop.full{max-height:none;cursor:zoom-out}.cut{color:var(--muted);font-size:13px}
button.more{padding:10px 16px;margin:8px 0;border:1px solid var(--field);border-radius:6px;background:var(--card);\
color:var(--fg);cursor:pointer}
@media(max-width:700px){.pair{grid-template-columns:1fr}body{padding:0 12px}}
'''
# The page's script: it inflates the report's parts and shows them (a file beside this one, so it reads as code).
SCRIPT = resources.files(__package__).joinpath("report.js").read_text(encoding="utf-8")

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
    return f'''<article data-relation="{esc(f['relation'])}" \
data-kind="{esc(f.get('explanation', {}).get('kind', ''))}"><h2>{esc(title)}</h2>
        {why or ''}<p>{esc(f['rationale'])}</p>{editorial}{differ}<div class="pair">{card(f['a'])}{card(f['b'])}</div>
        <details><summary>Calculation and matching details</summary>{numeric}<p>Retrieval score \
{f['retrieval_score']}; {'alignment' if f.get('settled') else 'model'} confidence {f['confidence']}</p></details>\
</article>'''

def header_html(data, listed=True):
    """The report's header: the sources, the mode, the findings counted, the files' differences (unless the files'
    table lists them: listed=False), the caveats and the run's metadata."""
    counts = Counter(f['relation'] for f in data['findings'])
    issues = [r for r in data['coverage'] if r['status'] != 'complete']
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
    page += f"<p>{esc(dict(counts))}</p>" + kinds_html(data['findings'], esc) + (
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

# A report document's parts the page shows in their own places, left out of its run metadata (each file's grows with
# the files compared: the revisions' groupings were 208 KB of TS 38.300's 1.4 MB, gzipped).
SHOWN_ELSEWHERE = ('evidence', 'coverage', 'findings', 'unmatched', 'shared', 'groupings', 'sections', 'situation',
                   'records', 'record_changes', 'files', 'file_difference', 'scan_issues')

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

def write_report(data, output, assets=None, budget=crops.DEFAULT_BUDGET, write=True):
    """Write report.json and report.html, one file holding its crops (rendered into `assets`, default output/assets)
    as far as the byte budget allows, in crops.py's order of value. Returns the budget's account (crops.Account);
    with write=False, only the account (`report --dry-run`)."""
    output = Path(output)
    assets = Path(assets) if assets else output / "assets"
    stored = lambda image: assets / image.split("/", 1)[1] if image.startswith("assets/") else output / image
    # explained differences first, value changes leading (KINDS' order); the rest as found
    order = {k: i for i, k in enumerate(KINDS)}
    shown = sorted(data['findings'], key=lambda f: order.get(f.get('explanation', {}).get('kind'), len(KINDS)))
    where = Cards(data).where
    def label(e):
        loc = e['locator']
        return (f"{where(e['content'])}, {PAGE_WORDS.get(loc.get('format'), 'page')} {loc['page']}, "
                f"{loc.get('task', loc.get('region', ''))}: {e['entity']} — {e['attribute']}")
    account = crops.Account(budget, names={f['content']: where(f['content']) for f in data.get('files', [])})
    account.wanted = crops.wanted({e["id"]: e for e in data["evidence"]}, shown, data['unmatched'],
                                  data.get('shared', []), label, lambda image: stored(image).exists())
    mime, encode = crops.encoder()
    crops.encode(account.wanted, stored, encode)
    account.page = len(page_html(data, shown, stored, [], account, mime).encode())  # every crop left out
    chosen = crops.choose(account.wanted, budget - account.page)
    while True:  # the page's text changes a little with what's embedded: never over budget for it
        account.chosen = {c.image for c in chosen}
        page = page_html(data, shown, stored, chosen, account, mime)
        account.size = len(page.encode())
        if account.size <= budget or not chosen:
            break
        chosen.pop()
    if write:
        output.mkdir(exist_ok=True, parents=True)
        (output/"report.json").write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        (output/'report.html').write_text(page, encoding='utf-8')
    return account

def crop_html(e, embedded, stored):
    """A card's crop: its embedded image (enlarged by a click), or why it has none."""
    image = e.get('image')
    if not image:
        return ''
    if image in embedded:
        return (f'<img class="crop" data-crop="{embedded[image]}" alt="The image the model read" '
                'title="Click to enlarge">')
    if not stored(image).exists():
        return f"<p class='cut'>Crop not found in the store ({esc(image)}).</p>"
    return (f"<p class='cut'>Crop left out for the report's size budget ({esc(e['locator'].get('task', ''))}): "
            "see Crops left out.</p>")

def page_html(data, shown, stored, chosen, account, mime="image/webp"):
    """report.html: its parts gzipped inside it (each card once), the chosen crops, and the script showing them."""
    embedded = {c.image: i for i, c in enumerate(chosen)}
    card = Cards(data, lambda e: crop_html(e, embedded, stored))
    pairs = file_pairs(data)
    files = {c: i for i, c in enumerate(dict.fromkeys(x[1] for _, a, b in pairs for x in (a, b) if x and x[1]))}
    page = header_html(data, listed=len(pairs) <= 1) + crops_note(account)
    if len(pairs) > 1:
        page += files_html(data, pairs, files, account, card.where)
    page += ('<label>Show <select id="filter"><option value="all">All relations</option>'
             +''.join('<option>'+r+'</option>'
                      for r in ['different','equivalent','complementary','uncertain','unrelated'])
             +'</select></label>')
    if any('explanation' in f for f in data['findings']):
        page += ('<label>Kind <select id="kind"><option value="all">All kinds</option>'
                 +''.join(f'<option value="{k}">{esc(v[0])}</option>' for k, v in KINDS.items())+'</select></label>')
    if len(pairs) > 1:
        page += ('<label>File <select id="file"><option value="all">All files</option>'
                 + ''.join(f'<option value="{pair_key(a, b, files)}">{esc(pair_name(kind, a, b))}</option>'
                           for kind, a, b in pairs) + '</select></label>')
    findings = [{"relation": f['relation'], "kind": f.get('explanation', {}).get('kind', ''),
                 "cards": [f['a'], f['b']], "html": finding_html(f, card),
                 "files": [files.get(card.evidence[x]['content'], -1) for x in (f['a'], f['b'])]} for f in shown]
    for f, record in zip(shown, findings):  # equivalent, and saying the same in both: folded unless asked for
        record["same"] = f['relation'] == 'equivalent' and card.said_of[f['a']] == card.said_of[f['b']]
    same = sum(1 for record in findings if record["same"])
    if same:
        page += (f'<label><input type="checkbox" id="same" checked> Fold the {same} equivalent findings whose two '
                 'claims say the same</label>')
    page += ('<input id="query" placeholder="Search findings" aria-label="Search findings"> '
             '<span id="count" class="meta"></span>')
    page += ('<main></main><details data-list="unmatched"><summary>Unmatched evidence ('
             +str(len(data['unmatched']))+')</summary></details>')
    page += groupings_html(data.get('groupings', []), esc)
    page += ('<details data-list="shared"><summary>Shared evidence ('+str(len(data.get('shared', [])))
             +'): identical content in both sources, not compared</summary></details>')
    page += situating(data.get('situation', {}), data.get('sections', []), card.where, esc)
    issues_found = ''.join('<tr><td>'+esc(i['source'])+'</td><td>'+esc(i['path'])+'</td><td>'+esc(i['reason'])
                           +'</td></tr>' for i in data.get('scan_issues', []))
    page += ('<details class="coverage"><summary>Files not scanned ('+str(len(data.get('scan_issues', [])))
             +'): hidden, unsafe or over limits</summary><table><thead><tr><th>Source</th><th>Path</th><th>Reason</th>'
             '</tr></thead><tbody>'+issues_found+'</tbody></table></details>')
    coverage = ''.join('<tr><td>'+esc(card.where(r['content']))+'</td><td>'
                       +esc(r['page'] if r['page'] is not None else '')+'</td><td>'+esc(r['task'])+'</td><td>'
                       +esc(r['status'])+'</td><td>'+esc('; '.join(r['issues']))+'</td></tr>' for r in data['coverage'])
    page += ('<details class="coverage"><summary>Source coverage ledger</summary><table><thead><tr><th>File</th>'
             '<th>Page</th><th>Task</th><th>Status</th><th>Issues</th></tr></thead><tbody>'+coverage
             +'</tbody></table></details>')
    page += crops_left_out_html(account)
    parts = {"page": page,
             "findings": findings,
             "lists": {"unmatched": ['<article>'+esc(u['note'])+card(u['id'])+'</article>' for u in data['unmatched']],
                       "shared": [card(eid) for eid in data.get('shared', [])]},
             "cards": card.html, "said": list(card.said)}
    packed = json.dumps(parts, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    packed = base64.b64encode(gzip.compress(packed, 9, mtime=0)).decode("ascii")  # mtime=0: the same bytes each time
    images = embed_json({"type": mime, "data": [c.data for c in chosen]})
    body = ('<div id="report"><p class="meta">Opening the report…</p></div><noscript><p class="warning">This report '
            'is shown by its script: open it in a browser with JavaScript on.</p></noscript>'
            f'<script type="application/gzip" id="report-data">{packed}</script>'
            f'<script type="application/json" id="report-crops">{images}</script><script>{SCRIPT}</script>')
    return html_page('Semantic PDF comparison', body, STYLE)

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

def files_html(data, pairs, files, account, where):
    """The files compared, a row a pair: its findings by relation (those reaching a file of another pair counted
    apart), its claims without a counterpart, and its crops embedded; each a button showing its findings."""
    evidence = {e['id']: e['content'] for e in data['evidence']}
    rows = []
    for kind, a, b in pairs:
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
                    + (f'<button class="pick" data-files="{pair_key(a, b, files)}">Show</button>' if touching else '')
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
            "<code>pdf-semantic-diff report --report-budget SIZE</code> writes it again with another budget, and "
            "<code>--dry-run</code> says what that would leave out.</p><table><thead><tr><th>Shown in</th>"
            f"<th>Crop</th><th>Size</th></tr></thead><tbody>{rows}</tbody></table></details>")

def unpacked(page):
    """A report page's HTML as its script shows it, with every finding and list open (for tests and tools)."""
    import html
    found = re.search(r'<script type="application/gzip" id="report-data">([^<]*)</script>', page)
    parts = json.loads(gzip.decompress(base64.b64decode(found.group(1))))
    cards = lambda text: re.sub(r'<div data-card="([^"]*)"></div>',
                                lambda m: parts["cards"][html.unescape(m.group(1))], text)
    fill = lambda text: re.sub(r'<div data-said="(\d+)"></div>', lambda m: parts["said"][int(m.group(1))], cards(text))
    out = parts["page"].replace("<main></main>", "<main>" + "".join(fill(f["html"]) for f in parts["findings"])
                                + "</main>")
    for name, items in parts["lists"].items():
        listed = fill("".join(items))
        out = re.sub(f'(<details data-list="{name}"><summary>.*?</summary>)', lambda m: m.group(1) + listed,  # noqa: B023
                     out, count=1, flags=re.S)  # (used at once)
    return out

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
