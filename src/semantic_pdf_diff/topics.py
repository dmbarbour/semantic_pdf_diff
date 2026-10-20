"""Topics for browsing a report (docs/plans/portable-reports-2026-10-19.md, milestone 3): the claims a report shows,
split into about √(n/2) topics by the words of what they're about, so a reader can filter before knowing what to search
for. The owner, 2026-10-19: "find candidate cliques of unique words that split the datasets (requirements, in that
case, claim cards in this one) roughly evenly ... If LLMs timed out, we'd just use a heuristic choice. In any case, the
idea is to let users swiftly filter when the Search box is blank page syndrome."

- **A topic** is a few words that occur together (a seed, and words whose claims mostly carry it too), each found on
  both sides: words of one side's alone would make topics of the sources again (cameo_ingest's lesson).
- **Seeds** are taken greedily, each the word covering the most claims still unplaced, up to a little over an even
  share, so topics come out about even.
- **Every claim** is then placed in the topic it shares the rarest words with; one sharing none, where the claims
  sharing its words went; the rest are in no topic.
- **Ways** of splitting are candidates (by subject: entity and attribute; by property: attribute alone; coarser), and
  the one placing the most claims evenly, with both sides in its topics, is shown.
"""
import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field

STOP = frozenset("""a an the of and or for to in on at by with from as is are be was were this that these those its it
into per not no all any each other than then over under between within without about above below up down out off via vs
total value values number type types data item items table figure page section note notes see shown use used using case
cases level levels mode modes condition conditions general based new old one two three first second""".split())
WORDS = 4          # a topic's words, at most
LEAST = 0.005      # a word's share of claims, at least (and 3 claims), to make a topic
MOST = 0.4         # and at most: a word nearly every claim carries splits nothing
SEED_REACH = 1.3   # a seed covers up to this many even shares
TOPIC_REACH = 1.6  # a topic's words cover up to this many
JOINS = 0.5        # a word joins a topic when this share of its unplaced claims carry the topic's words

def stem(word):
    return word[:-1] if word.endswith("s") and not word.endswith(("ss", "us", "is")) and len(word) > 4 else word

def words(text):
    """A text's words, as topics count them: lower case, plurals folded, numbers and the commonest words left out."""
    found = (w.strip("-") for w in re.findall(r"[a-z][a-z0-9\-]+", text.lower()))
    return {stem(w) for w in found if len(w) >= 3 and w not in STOP}

def target(n):
    """How many topics for n claims: about √(n/2), 2 to 15 (cameo_ingest's)."""
    return max(2, min(15, round(math.sqrt(n / 2))))

@dataclass
class Way:
    """One way of splitting: its name, each topic's words, each claim's topic (None: in none), and its measures."""
    name: str
    topics: list
    placed: list
    measures: dict = field(default_factory=dict)

    @property
    def score(self):
        m = self.measures
        return m["placed"] * m["even"] * m["both_sides"]

def split(said, sides, k, name=""):
    """said: each claim's words; sides: each claim's side. Topics of words found on both sides, about k of them."""
    n = len(said)
    by_side = defaultdict(Counter)
    for ws, side in zip(said, sides):
        for w in ws:
            by_side[w][side] += 1
    usable = sorted(w for w, by in by_side.items()
                    if len(by) >= 2 and max(3, n * LEAST) <= sum(by.values()) <= n * MOST)
    idf = {w: math.log(n / sum(by_side[w].values())) for w in usable}
    holders = defaultdict(set)
    for i, ws in enumerate(said):
        for w in ws:
            if w in idf:
                holders[w].add(i)
    share, left, topics, taken = n / k, set(range(n)), [], set()
    while len(topics) < k and left:
        open_ = [w for w in usable if w not in taken and holders[w] & left]
        if not open_:
            break
        seed = max(open_, key=lambda w: min(len(holders[w] & left), share * SEED_REACH))  # first of equals: sorted
        topic, members = [seed], holders[seed] & left
        for w in sorted(open_, key=lambda w: (-len(holders[w] & left), w)):
            if len(topic) >= WORDS:
                break
            mine = holders[w] & left
            reach = max(len(members), share * TOPIC_REACH)  # a word adding no claims may always join
            if w != seed and len(mine & members) >= JOINS * len(mine) and len(members | mine) <= reach:
                topic.append(w)
                members |= mine
        topics.append(topic)
        taken |= set(topic)
        left -= members
    of = {w: t for t, topic in enumerate(topics) for w in topic}
    placed = []
    for ws in said:  # the topic sharing the rarest words
        score = Counter()
        for w in ws:
            if w in of:
                score[of[w]] += idf[w]
        placed.append(max(sorted(score), key=lambda t: score[t]) if score else None)
    went = defaultdict(Counter)  # where the claims carrying each word went
    for ws, t in zip(said, placed):
        if t is not None:
            for w in ws:
                if w in idf:
                    went[w][t] += 1
    for i, ws in enumerate(said):
        if placed[i] is None:
            vote = Counter()
            for w in ws:
                total = sum(went[w].values())
                for t, m in went[w].items():
                    vote[t] += m / total * idf[w]
            if vote:
                placed[i] = max(sorted(vote), key=lambda t: vote[t])
    way = Way(name, topics, placed)
    way.measures = measures(way, sides)
    return way

def measures(way, sides):
    """The share of claims placed, how even the topics are (normalised entropy), and the share of topics holding
    claims of both sides."""
    sizes = Counter(t for t in way.placed if t is not None)
    n, counts = len(way.placed), [sizes[t] for t in range(len(way.topics))]
    total = sum(counts)
    even = (-sum(c / total * math.log(c / total) for c in counts if c) / math.log(len(counts))
            if len(counts) > 1 and total else 0.0)
    held = defaultdict(set)
    for t, side in zip(way.placed, sides):
        if t is not None:
            held[t].add(side)
    both = sum(1 for t in range(len(way.topics)) if len(held[t]) > 1) / len(way.topics) if way.topics else 0.0
    return {"placed": round(total / n, 3) if n else 0.0, "even": round(even, 3), "both_sides": round(both, 3)}

def ways(claims, sides):
    """The candidate ways of splitting claims (dicts with entity and attribute), each side's claims together: by
    subject, by subject coarser, by property."""
    k = target(len(claims))
    subject = [words(f"{c['entity']} {c['attribute']}") for c in claims]
    found = [split(subject, sides, k, "by subject"), split([words(c['attribute']) for c in claims], sides, k,
                                                           "by property")]
    if k > 4:
        found.append(split(subject, sides, max(2, k // 2), "by subject, coarser"))
    return [w for w in found if w.topics]

def best(found):
    """The way shown without the model: the most claims placed, evenly, both sides in its topics."""
    return max(found, key=lambda w: w.score, default=None)

def label(topic):
    """A topic's name without the model: its first words."""
    return ", ".join(topic[:2]).capitalize()
