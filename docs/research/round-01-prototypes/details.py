import pymupdf, re, sys
sys.path.insert(0,'/home/dmbarbour/.claude/jobs/5ac2c167/tmp/research-r1')
from tiles import disp_lines
T='/home/dmbarbour/.claude/jobs/5ac2c167/tmp/research-r1/'
def titles(p):
    out=[]
    for b in p.get_text('dict')['blocks']:
        for l in b.get('lines',[]):
            for s in l['spans']:
                if re.fullmatch(r'[A-H]\d{1,2}',s['text'].strip()) and s['size']>15:
                    out.append((s['text'].strip(), pymupdf.Rect(l['bbox'])*p.rotation_matrix))
    return out
def occ(p, clip):
    boxes=[lb for lb,_ in disp_lines(p)]
    for d in p.get_cdrawings():
        r=pymupdf.Rect(d['rect'])*p.rotation_matrix
        if r.width<0.5*clip.width and r.height<0.5*clip.height: boxes.append(r)
    return [b for b in boxes if b.intersects(clip)]
def widest_gap(boxes, lo, hi, axis, band):
    iv=sorted((b.x0,b.x1) if axis=='x' else (b.y0,b.y1) for b in boxes if b.intersects(band))
    gaps=[]; cur=lo
    for a,z in iv:
        if z<=lo: continue
        if a>cur: gaps.append((cur,min(a,hi)))
        cur=max(cur,z)
        if cur>=hi: break
    if cur<hi: gaps.append((cur,hi))
    gaps=[g for g in gaps if g[1]>g[0]]
    if not gaps: return None
    g=max(gaps,key=lambda g:g[1]-g[0]); return (g[0]+g[1])/2
def viewports(p, area):
    ts=titles(p); boxes=occ(p,area); R={}
    for name,t in ts:
        top=area.y0
        for n2,u in ts:
            if abs(u.x0-t.x0)<150 and u.y1<t.y1-40:
                top=max(top, u.y1+30)  # below U's title + scale line
        R[name]=[t.x0-30, top, area.x1, t.y1+12]
    for name,t in ts:
        r=R[name]
        for n2,u in ts:
            ru=R[n2]
            if u.x0>t.x0+150 and ru[1]<r[3] and ru[3]>r[1]:
                band=pymupdf.Rect(t.x0, max(r[1],ru[1]), u.x0, min(r[3],ru[3]))
                g=widest_gap(boxes,t.x0+150,u.x0+10,'x',band)
                bnd=g if g else u.x0-20
                r[2]=min(r[2],bnd)
                ru[0]=min(ru[0],bnd)  # neighbour may extend left of its title up to the gutter
    for name,t in ts:
        # left bound: gutter to the left neighbour's right edge, else area
        r=R[name]
        lefts=[R[n2][2] for n2,u in ts if u.x0<t.x0-150 and R[n2][1]<r[3] and R[n2][3]>r[1]]
        r[0]=max(lefts) if lefts else area.x0
    return {k:pymupdf.Rect(v) for k,v in R.items()}
for f,area in [('dc-cd-p39-42',pymupdf.Rect(108,72,2123,1512)),('calg-cd-p39-42',pymupdf.Rect(108,72,1830,1512))]:
    d=pymupdf.open(f'samples/slices/{f}.pdf')
    for p in d:
        vs=viewports(p,area)
        print(f,p.number,{k:[round(x) for x in v] for k,v in sorted(vs.items())})
        if p.number==0:
            s=1100/p.rect.width; pix=p.get_pixmap(matrix=pymupdf.Matrix(s,s))
            sh=p.new_shape()
            for k,v in vs.items(): sh.draw_rect(v*p.derotation_matrix)
            sh.finish(color=(1,0,0),width=4); sh.commit()
            p.get_pixmap(matrix=pymupdf.Matrix(s,s)).save(T+f+'-vp.png')
