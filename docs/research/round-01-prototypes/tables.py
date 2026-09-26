import pymupdf, glob, sys
def metrics(page, t):
    rows = t.extract()
    cells = [c for r in rows for c in r]
    filled = sum(1 for c in cells if c not in (None,'') and str(c).strip())
    ncell = len(cells) or 1
    # ruled lines inside bbox
    bb = pymupdf.Rect(t.bbox)
    h=v=0
    for d in page.get_drawings():
        for it in d['items']:
            if it[0]=='l':
                p,q=it[1],it[2]
                if not (bb+(-2,-2,2,2)).contains(p): continue
                if abs(p.y-q.y)<1 and abs(p.x-q.x)>0.3*bb.width: h+=1
                if abs(p.x-q.x)<1 and abs(p.y-q.y)>0.3*bb.height: v+=1
            elif it[0]=='re':
                r=it[1]
                if r in bb+(-2,-2,2,2):
                    if r.height<2 and r.width>0.3*bb.width: h+=1
                    if r.width<2 and r.height>0.3*bb.height: v+=1
    # long text lines (paragraph-like) inside cells
    avglen = sum(len(str(c)) for c in cells if c)/max(filled,1)
    words = page.get_text('words', clip=bb)
    return dict(rows=len(rows), cols=t.col_count, fill=round(filled/ncell,2), avglen=round(avglen), hrules=h, vrules=v, words=len(words))
for f in sorted(glob.glob('samples/slices/*.pdf')):
    if len(sys.argv)>1 and sys.argv[1] not in f: continue
    doc=pymupdf.open(f)
    for p in doc:
        for strat in ['lines']:
            try: ts=p.find_tables(strategy=strat).tables
            except Exception as e: print(f, p.number, 'ERR', e); continue
            for i,t in enumerate(ts):
                m=metrics(p,t)
                hdr = t.header.names if t.header else None
                print(f.split('/')[-1][:10], p.number, i, [round(x) for x in t.bbox], m, 'ext' if t.header.external else '', str(t.extract()[0])[:90].replace('\n',' '))
