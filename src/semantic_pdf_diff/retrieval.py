"""Retrieval: the candidate pairs of claims a comparison judges, by shared words and values. Split from compare.py
(code review 2026-10-08, D6).
"""
import math
import re
from collections import Counter, defaultdict

def words(text, aliases):
    text = text.casefold()
    for alias, canonical in sorted(aliases.items(), key=lambda p: -len(p[0])):
        text = re.sub(r"(?<!\w)" + re.escape(alias.casefold()) + r"(?!\w)", canonical.casefold(), text)
    return re.findall(r"[^\W_]+", text, re.UNICODE)

def candidates(left, right, settings):
    """Bidirectional top-k union; supports one-to-many and many-to-one, no page alignment."""
    all_e = left + right
    docs = [Counter(words(f"{e.entity} {e.entity} {e.attribute} {e.attribute} {e.conditions} {e.value}", settings.aliases)) for e in all_e]
    df = Counter(t for d in docs for t in d)
    vectors = []
    for d in docs:
        v = {t: (1 + math.log(n)) * (1 + math.log((len(docs)+1)/(df[t]+1))) for t,n in d.items()}
        norm = math.sqrt(sum(x*x for x in v.values())) or 1
        vectors.append({t:x/norm for t,x in v.items()})
    inverted = defaultdict(list)
    for j, v in enumerate(vectors[len(left):]):
        for t, weight in v.items():
            inverted[t].append((j,weight))
    left_hits, right_hits = defaultdict(list), defaultdict(list)
    for i, v in enumerate(vectors[:len(left)]):
        scores = defaultdict(float)
        for t, weight in v.items():
            for j, w in inverted[t]:
                scores[j] += weight*w
        for j, score in scores.items():
            if score >= settings.min_score:
                left_hits[i].append((score, j))
                right_hits[j].append((score, i))
    pairs = {}
    for i,hits in left_hits.items():
        for score,j in sorted(hits, reverse=True)[:settings.top_k]:
            pairs[i,j] = score
    for j,hits in right_hits.items():
        for score,i in sorted(hits, reverse=True)[:settings.top_k]:
            pairs[i,j] = score
    return sorted([(i,j,s) for (i,j),s in pairs.items()], key=lambda x:(-x[2],x[0],x[1]))

# Bump when the way comparison prompts are assembled changes, not only the template.
