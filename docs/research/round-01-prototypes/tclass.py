import pymupdf, glob, re
NUM=re.compile(r'^[-+−]?\d')
def classify(page, t):
    rows=t.extract(); cells=[c for r in rows for c in r]
    filled=[str(c) for c in cells if c not in (None,'') and str(c).strip()]
    fill=len(filled)/max(len(cells),1)
    bb=pymupdf.Rect(t.bbox)
    words=page.get_text('words', clip=bb)
    cellrects=[pymupdf.Rect(c) for c in t.cells if c]
    split=0
    for w in words:
        wr=pymupdf.Rect(w[:4])
        if wr.width<=0: continue
        for c in cellrects:
            i=wr & c
            if not i.is_empty and 0.15 < i.width/wr.width < 0.85 and i.height>0.5*wr.height: split+=1; break
    splitf=split/max(len(words),1)
    area=abs(bb)/abs(page.rect)
    # chart-ness: curve items and nonaxis short segments within bbox
    curves=0
    for d in page.get_drawings():
        if pymupdf.Rect(d['rect']) in bb+(-2,-2,2,2):
            curves+=sum(1 for it in d['items'] if it[0]=='c') + (len(d['items']) if len(d['items'])>8 else 0)
    longcell=sum(1 for c in filled if len(c)>80)/max(len(filled),1)
    reasons=[]
    if area>0.5: reasons.append('area')
    if fill<0.5: reasons.append(f'fill{fill:.2f}')
    if splitf>0.05: reasons.append(f'split{splitf:.2f}')
    if len(rows)<2 or t.col_count<2: reasons.append('tiny')
    if len(words)<6: reasons.append('fewwords')
    if longcell>0.3: reasons.append('paragraph')
    if curves>20: reasons.append(f'curves{curves}')
    return reasons
for f in sorted(glob.glob('samples/slices/*.pdf')):
    doc=pymupdf.open(f); keep=rej=0
    for p in doc:
        for i,t in enumerate(p.find_tables().tables):
            r=classify(p,t)
            if r: rej+=1
            else: keep+=1
            if not r or 'nrel' in f or 'rules' in f or 'iea' in f: print(f.split('/')[-1][:8],p.number,i,'KEEP' if not r else 'REJ',r)
    print(f.split('/')[-1], 'keep',keep,'reject',rej)
