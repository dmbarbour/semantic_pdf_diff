import pymupdf, glob, sys
sys.path.insert(0,'/home/dmbarbour/.claude/jobs/5ac2c167/tmp/research-r1')
from tiles import disp_lines
def swatches(p):
    out=[]
    for d in p.get_drawings():
        r=pymupdf.Rect(d['rect'])
        its=d['items']
        if len(its)>3: continue
        if 6<=r.width<=40 and r.height<=12:  # short horizontal stroke or small filled marker
            if d.get('fill') is not None and r.height<3 and r.width>10: pass
            col=d.get('color') or d.get('fill')
            out.append((r,col))
    return out
def legends(p):
    L=[(pymupdf.Rect(l['bbox']),''.join(s['text'] for s in l['spans']).strip()) for b in p.get_text('dict')['blocks'] for l in b.get('lines',[])]
    ents=[]
    for r,col in swatches(p):
        cy=(r.y0+r.y1)/2
        for lb,t in L:
            if 0<=lb.x0-r.x1<=12 and lb.y0-2<=cy<=lb.y1+2 and len(t)<=40:
                ents.append((r|lb,t,col)); break
    # group entries stacked vertically with same x0
    groups=[]
    for e in sorted(ents,key=lambda e:(round(e[0].x0),e[0].y0)):
        for g in groups:
            last=g[-1][0]
            if abs(e[0].x0-last.x0)<4 and 0<=e[0].y0-last.y1<=12: g.append(e); break
        else: groups.append([e])
    return [g for g in groups if len(g)>=2]
for f in sorted(glob.glob('samples/slices/*.pdf')):
    if '-cd-' in f: continue
    d=pymupdf.open(f)
    for p in d:
        for g in legends(p):
            bb=g[0][0]
            for e in g: bb|=e[0]
            print(f.split('/')[-1][:10],p.number,[round(x) for x in bb],len(g),[e[1][:22] for e in g][:4])
