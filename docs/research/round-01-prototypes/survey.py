import pymupdf, glob, collections, statistics
for f in sorted(glob.glob('samples/slices/*.pdf')):
    doc = pymupdf.open(f)
    print('==', f.split('/')[-1], len(doc))
    for p in doc:
        d = p.get_text('dict')
        sizes = collections.Counter()
        for b in d['blocks']:
            if b['type']!=0: continue
            for l in b['lines']:
                for s in l['spans']:
                    if s['text'].strip(): sizes[round(s['size'],1)] += len(s['text'])
        tot = sum(sizes.values())
        acc=0; p5=None
        for sz in sorted(sizes):
            acc+=sizes[sz]
            if p5 is None and acc>=0.05*tot: p5=sz
        try: nt = len(p.find_tables().tables)
        except Exception as e: nt='ERR'
        print(f" p{p.number} rect={tuple(round(x) for x in p.rect)} rot={p.rotation} blocks={len(d['blocks'])} chars={tot} minsize={min(sizes) if sizes else None} p5={p5} mode={sizes.most_common(1)} tables={nt} drawings={len(p.get_cdrawings())} imgs={len(p.get_images())}")
