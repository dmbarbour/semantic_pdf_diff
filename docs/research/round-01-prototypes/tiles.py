import pymupdf, glob, math, sys
sys.path.insert(0,'src')
from semantic_pdf_diff.extract import tiles
def disp_lines(page):
    out=[]
    for b in page.get_text('dict')['blocks']:
        for l in b.get('lines',[]):
            t=''.join(s['text'] for s in l['spans']).strip()
            if t: out.append((pymupdf.Rect(l['bbox'])*page.rotation_matrix, t))
    return out
def expand(tile, lines, page, cap=0.25):
    r=pymupdf.Rect(tile); lim=tile+(-cap*tile.width,-cap*tile.height,cap*tile.width,cap*tile.height)
    for _ in range(3):
        grown=False
        for lb,_t in lines:
            i=lb & r
            if i.is_empty or lb in r: continue
            u=r|lb
            if u in lim: r=u; grown=True
        if not grown: break
    return r & page.rect
def shrink(tile, lines):
    """alternative: pull edges inward to exclude lines cut (keep if cutting loses little)."""
    return tile
side=420
for f in sorted(glob.glob('samples/slices/*.pdf')):
    doc=pymupdf.open(f); tot=cut=cut2=uncov=uncov2=0; area=area2=0
    for p in doc:
        L=disp_lines(p)
        ts=list(tiles(p.rect, side)) if max(p.rect.width,p.rect.height)>side else [p.rect]
        es=[expand(t,L,p) for t in ts]
        for t,e in zip(ts,es):
            area+=abs(t); area2+=abs(e)
            for lb,_ in L:
                if (lb & t).is_empty is False and lb not in t: cut+=1
                if (lb & e).is_empty is False and lb not in e: cut2+=1
        for lb,_ in L:
            tot+=1
            if not any(lb in t for t in ts): uncov+=1
            if not any(lb in e for e in es): uncov2+=1
    print(f.split('/')[-1], f'lines={tot} tiles/page={len(ts)} cut(tile,line)={cut} -> {cut2}  lines_in_no_tile={uncov} -> {uncov2}  area x{area2/area:.2f}')
