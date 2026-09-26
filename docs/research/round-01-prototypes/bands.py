import pymupdf, glob, sys
sys.path.insert(0,'/home/dmbarbour/.claude/jobs/5ac2c167/tmp/research-r1')
from tiles import disp_lines
def occupancy(page):
    boxes=[lb for lb,_ in disp_lines(page)]
    for d in page.get_cdrawings() if hasattr(page,'get_cdrawings') else page.get_drawings():
        r=pymupdf.Rect(d['rect'])*page.rotation_matrix
        if r.height<0.5*page.rect.height: boxes.append(r)   # ignore page frames
    for im in page.get_image_info():
        boxes.append(pymupdf.Rect(im['bbox'])*page.rotation_matrix)
    return boxes
def bands(page, H=400, minfrac=0.5, pad=4):
    boxes=[b for b in occupancy(page) if not b.is_empty or b.height>0]
    if not boxes: return []
    content=pymupdf.Rect(boxes[0])
    for b in boxes: content|=b
    content=(content+(-pad,-pad,pad,pad))&page.rect
    ys=sorted((b.y0,b.y1) for b in boxes)
    # free intervals in y
    gaps=[]; cur=ys[0][1]
    for y0,y1 in ys[1:]:
        if y0>cur+1: gaps.append((cur,y0))
        cur=max(cur,y1)
    out=[]; top=content.y0
    while content.y1-top>H:
        cands=[g for g in gaps if top+minfrac*H <= (g[0]+g[1])/2 <= top+H]
        if cands:
            g=max(cands,key=lambda g:(g[1]-g[0], g[0]))   # widest gap
            cut=(g[0]+g[1])/2; nxt=cut
        else:
            cut=top+H; nxt=cut-0.15*H   # fallback: overlap
        out.append(pymupdf.Rect(content.x0,top,content.x1,cut)); top=nxt
    out.append(pymupdf.Rect(content.x0,top,content.x1,content.y1))
    return out
if __name__=='__main__':
    for f in sorted(glob.glob('samples/slices/*.pdf')):
        if '-cd-' in f: continue
        doc=pymupdf.open(f); cut=uncov=tot=n=0; px=[]
        for p in doc:
            L=disp_lines(p); bs=bands(p); n+=len(bs)
            for b in bs:
                # pixels per point for ~645k px budget
                px.append((645000/ (b.width*b.height))**0.5)
                for lb,_ in L:
                    if not (lb&b).is_empty and lb not in b: cut+=1
            for lb,_ in L:
                tot+=1
                if not any(lb in b for b in bs): uncov+=1
        print(f.split('/')[-1], f'bands={n} ({n/len(doc):.1f}/page) cut={cut} uncovered={uncov}/{tot} px/pt min={min(px):.2f} median={sorted(px)[len(px)//2]:.2f}')
