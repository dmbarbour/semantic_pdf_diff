import html
import json
from pathlib import Path
from collections import Counter

def write_report(data, output):
    output = Path(output)
    output.mkdir(exist_ok=True, parents=True)
    (output/"report.json").write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    esc = lambda x: html.escape(str(x), quote=True)
    evidence = {e["id"]:e for e in data["evidence"]}
    names = {x["id"]: x["name"] for x in data["sources"]}
    occurrences = {}
    for f in data["files"]:
        occurrences.setdefault(f["content"], []).append(f"{names[f['source']]} / {f['path']}")
    where = lambda content: "; ".join(occurrences.get(content, ["unregistered content"]))
    headings = {(x["content"], x["id"]): " > ".join(x["heading_path"]) for x in data.get("sections", [])}
    def card(eid):
        e = evidence[eid]
        image = ('<a href="'+esc(e['image'])+'"><img loading="lazy" src="'+esc(e['image'])+'" alt="Source crop"></a>') if e.get('image') else ''
        verified = {True: '<p>Quote found in PDF text layer.</p>',
                    False: '<p class="warning">Quote not found in the PDF text layer for this region; possible misread or raster-only label.</p>'
                    }.get(e.get('quote_verified'), '')
        loc = e['locator']
        basis = f"<p>Basis: {esc(e['basis'])}</p>" if e.get('basis', 'unknown') != 'unknown' else ''
        heading = headings.get((e['content'], e.get('section', '')), '')
        heading = f" · § {esc(heading)}" if heading else ''
        return f'''<section><h3>{esc(where(e['content']))}{heading} · page {loc['page']} · {esc(e['kind'])}</h3>
        <b>{esc(e['entity'])} — {esc(e['attribute'])}</b><p>{esc(e['value'])} {esc(e['unit'])}</p>
        <p>Conditions: {esc(e['conditions'] or 'unspecified')}</p>{basis}<blockquote>{esc(e['quote'])}</blockquote>{verified}
        <small>{esc(eid)} · {esc(loc['region'])} region, PDF bbox {esc(list(loc['bbox']))} · confidence {e['confidence']:.2f}</small>{image}</section>'''
    counts = Counter(f['relation'] for f in data['findings'])
    issues = [r for r in data['coverage'] if r['status'] != 'complete']
    rows = []
    for f in data['findings']:
        numeric = '<pre>'+esc(json.dumps(f['numeric'],indent=2))+'</pre>' if f.get('numeric') else ''
        rows.append(f'''<article data-relation="{esc(f['relation'])}"><h2>{esc(f['relation'].title())}</h2>
        <p>{esc(f['rationale'])}</p><div class="pair">{card(f['a'])}{card(f['b'])}</div>
        <details><summary>Calculation and matching details</summary>{numeric}<p>Retrieval score {f['retrieval_score']}; model confidence {f['confidence']}</p></details></article>''')
    unmatched = ''.join('<article>'+esc(u['note'])+card(u['id'])+'</article>' for u in data['unmatched'])
    shared = ''.join(card(eid) for eid in data.get('shared', []))
    coverage = ''.join('<tr><td>'+esc(where(r['content']))+'</td><td>'+str(r['page'])+'</td><td>'+esc(r['task'])+'</td><td>'+esc(r['status'])+'</td><td>'+esc('; '.join(r['issues']))+'</td></tr>' for r in data['coverage'])
    page = '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Semantic PDF comparison</title><style>
:root{font-family:system-ui,sans-serif;color:#183047;background:#edf2f6}body{max-width:1200px;margin:32px auto;padding:0 24px}
h1{font-size:36px;letter-spacing:-1px}h2{font-size:20px}h3{font-size:15px;color:#356783}.meta{color:#536879}
article,header,details.coverage{background:white;border:1px solid #d7e1e8;border-radius:12px;padding:22px;margin:18px 0}
.pair{display:grid;grid-template-columns:1fr 1fr;gap:24px}section{min-width:0;padding:12px;background:#f7f9fb;border-radius:8px}
img{display:block;max-width:100%;max-height:500px;margin:14px auto}blockquote{border-left:3px solid #83a9bf;margin:14px 0;padding-left:12px}
small{overflow-wrap:anywhere}table{border-collapse:collapse;width:100%;font-size:13px}td,th{text-align:left;border-bottom:1px solid #d7e1e8;padding:8px}
select,input{padding:10px;border:1px solid #aac0cd;border-radius:6px;margin:8px}pre{white-space:pre-wrap}.warning{color:#854400}summary{cursor:pointer}
@media(max-width:700px){.pair{grid-template-columns:1fr}body{padding:0 12px}}
</style><header><p class="meta">ENGINEERING EVIDENCE REVIEW</p><h1>Semantic PDF comparison</h1>'''
    page += f"<p>{' ↔ '.join(esc(x['name']) for x in data['sources'])}</p><p>Mode: {esc(data['mode'])}</p>"
    page += f"<p>{esc(dict(counts))}</p><p class='warning'>{len(issues)} incomplete, failed or skipped source tasks. {len(data['unmatched'])} claims lack a confirmed counterpart.</p>"
    page += '<p>Model conclusions require review. “Complete” means the extractor reported no local issue, not proof of exhaustive coverage. Unmatched claims do not establish additions or deletions.</p>'
    page += '<p>Revision mode treats the first source as the earlier version and the second as the later one. Proposal mode treats both symmetrically; neither is ranked.</p>'
    page += '<details><summary>Run metadata and limitations</summary><pre>'+esc(json.dumps({k:v for k,v in data.items() if k not in ('evidence','coverage','findings','unmatched')},indent=2))+'</pre></details></header>'
    page += '<label>Show <select id="filter"><option value="all">All relations</option>'+''.join('<option>'+r+'</option>' for r in ['different','equivalent','complementary','uncertain','unrelated'])+'</select></label><input id="query" placeholder="Search findings" aria-label="Search findings">'
    page += '<main>'+''.join(rows)+'</main><details><summary>Unmatched evidence ('+str(len(data['unmatched']))+')</summary>'+unmatched+'</details>'
    page += '<details><summary>Shared evidence ('+str(len(data.get('shared', [])))+'): identical content in both sources, not compared</summary>'+shared+'</details>'
    page += '<details class="coverage"><summary>Source coverage ledger</summary><table><thead><tr><th>File</th><th>Page</th><th>Task</th><th>Status</th><th>Issues</th></tr></thead><tbody>'+coverage+'</tbody></table></details>'
    page += '''<script>function filter(){const r=document.querySelector('#filter').value,q=document.querySelector('#query').value.toLowerCase();document.querySelectorAll('main article').forEach(a=>a.hidden=(r!=='all'&&a.dataset.relation!==r)||!a.textContent.toLowerCase().includes(q))}document.querySelector('#filter').onchange=filter;document.querySelector('#query').oninput=filter;</script></html>'''
    (output/'report.html').write_text(page,encoding='utf-8')
