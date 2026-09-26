import pymupdf, re, collections, sys
MARK = re.compile(r'^\s*(Contest \d+\.|\d+-\d+\.|\d+(?:\.\d+)+\.?|[a-z]\.|\((?:[ivx]+|\d+|[a-z])\)\.?|\d+\.)(?=\s|$)')
def cls(m):
    if m.startswith('Contest'): return 0
    if re.match(r'\d+-\d+\.|\d+(\.\d+)+', m): return 1
    if re.match(r'[a-z]\.', m): return 2
    if m.startswith('('): return 3
    return 4
def margins(doc):
    # repeated lines near top/bottom (digits normalized) on >=50% of pages
    cnt=collections.Counter()
    for p in doc:
        seen=set()
        for b in p.get_text('dict')['blocks']:
            for l in b.get('lines',[]):
                t=re.sub(r'\d+','#',''.join(s['text'] for s in l['spans']).strip())
                y=round(l['bbox'][1]/5)
                if t: seen.add((t,y))
        cnt.update(seen)
    return {k for k,v in cnt.items() if v>=max(2,len(doc)//2)}
def lines(doc):
    rep=margins(doc)
    sizes=collections.Counter()
    for p in doc:
        for b in p.get_text('dict')['blocks']:
            for l in b.get('lines',[]):
                for s in l['spans']: sizes[round(s['size'])]+=len(s['text'])
    body=sizes.most_common(1)[0][0]
    for p in doc:
        for b in p.get_text('dict',sort=True)['blocks']:
            for l in b.get('lines',[]):
                t=''.join(s['text'] for s in l['spans']).strip()
                if not t: continue
                if (re.sub(r'\d+','#',t), round(l['bbox'][1]/5)) in rep: continue
                s0=l['spans'][0]
                heading = (s0['size']>body+0.5 or (s0['flags']&16 and len(t)<60)) and len(t)<90
                yield p.number, l['bbox'], t, heading
def outline(doc):
    stack=[]; out=[]
    pend=None
    for pn,bb,t,head in lines(doc):
        m=MARK.match(t)
        if m:
            c=cls(m.group(1))
            if head and c>1: c=1
            while stack and (stack[-1][0]>=c): stack.pop()
            rest=t[m.end():].strip()
            stack.append([c,m.group(1),rest])
            pend=stack[-1] if not rest else None
        elif pend is not None:
            pend[2]=t; pend=None
        out.append((pn,bb,t,[f"{s[1]} {s[2][:60]}" for s in stack]))
    return out
if __name__=="__main__":
  doc=pymupdf.open(sys.argv[1])
  for pn,bb,t,st in outline(doc):
      if MARK.match(t): print(pn, round(bb[0]), ' > '.join(st))
