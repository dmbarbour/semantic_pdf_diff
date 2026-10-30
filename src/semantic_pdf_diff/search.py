"""Search over claims from the command line (docs/plans/search-2026-10-20.md, milestone 2): search.js's query
language, fields and ranking, in Python, for `semantic-pdf-diff search` over stores.

Cards are read by the markup report.py writes them in, as the page reads them, so the page and the command search
the same fields and rank alike; tests hold the two to the same answers (tests/test_search.py). Kept in step with
search.js by hand: a change to one is made to the other.
"""
import math
import re
import unicodedata
from bisect import bisect_left
from .values import claim_value, unit_of

# fields, as a query names them, and what a word found in each weighs: what a claim is about first
WEIGHTS = (3, 3, 2, 1.5, 1.5, 1, 1, 0.5, 0.5)
ENTITY, ATTRIBUTE, VALUE, CONDITIONS, SECTION, QUOTE, CONTEXT, FILE, OTHER = range(len(WEIGHTS))
NAMED = {"entity": ENTITY, "attribute": ATTRIBUTE, "attr": ATTRIBUTE, "value": VALUE, "unit": VALUE,
         "conditions": CONDITIONS, "condition": CONDITIONS, "section": SECTION, "heading": SECTION, "quote": QUOTE,
         "context": CONTEXT, "file": FILE}
# the words like:ID looks for: what a claim is about, and its value's words, not its numbers
ABOUT = {ENTITY, ATTRIBUTE, CONDITIONS, VALUE}
STOP = frozenset("a an and are as at be by for from in into is it its of on or per than that the this to with".split())
K1, B = 1.2, 0.75
LIKE_SHARE = 0.3  # like:ID keeps the claims scoring at least this share of the claim's own score
# by meaning (milestone 5; the embed lever's vectors), as measured: a claim near another at this cosine or more (about
# 90% of judged counterparts, 5% of other claims), a typed query's (meaning:) at this share of the best; a cosine of 1
# scores as much as this (the page's)
NEAR_LEAST, MEANING_SHARE, MEANING_WEIGHT = 0.7, 0.65, 10

# words as searched: case and accents folded, numbers whole and plain ("1,000" is 1000, "15.00" is 15), letters
# and digits apart ("75kW" is "75 kW"); digits are ASCII's, as JavaScript's \d
WORD = re.compile(r"[0-9]+(?:,[0-9]{3}(?![0-9]))*(?:\.[0-9]+)?|[^\W\d_]+")

def fold(text):
    return re.sub("[̀-ͯ]", "", unicodedata.normalize("NFKD", text)).lower()

def is_number(w):
    return "0" <= w[:1] <= "9"

def plain_number(n):
    whole = n.replace(",", "")
    return re.sub(r"\.$", "", re.sub("0+$", "", whole)) if "." in whole else whole

def norm(w):
    return plain_number(w) if is_number(w) else w

def words(text):
    return [norm(w) for w in WORD.findall(fold(text))]

ENTITIES = {"amp": "&", "lt": "<", "gt": ">", "quot": '"', "#x27": "'"}

def plain(html):
    return re.sub(r"&(amp|lt|gt|quot|#x27);", lambda m: ENTITIES[m.group(1)], re.sub(r"<[^>]*>", " ", html))

CARD = re.compile(r'<h3>([\s\S]*?)</h3>\s*<div data-said="(\d+)"></div>([\s\S]*?)<small>')
STATEMENT = re.compile(r"^<b>([\s\S]*?) — ([\s\S]*?)</b><p>([\s\S]*?)</p><p>Conditions: ([\s\S]*?)</p>"
                       r"([\s\S]*?)<blockquote>([\s\S]*?)</blockquote>$")
BOILERPLATE = re.compile(r"^\s*(Quote (not )?found|Read |Found \d+ times)")  # the same on many cards: not searched
LABEL = re.compile(r"^\s*(As printed|Position|Frame|Basis): ")
# a finding's own words: why and its rationale, not what every finding of its relation or kind says
SAME = re.compile(r"<details>[\s\S]*?</details>|<small>[\s\S]*?</small>|<h2>[\s\S]*?</h2>|<b>[\s\S]*?</b>|"
                  r"<p class=['\"]warning['\"]>[\s\S]*?</p>")

def lines(html):
    out = [plain(p) for p in html.split("</p>")]
    return [LABEL.sub("", p, count=1) for p in out if p.strip() and not BOILERPLATE.search(p)]

class Doc:
    __slots__ = ("terms", "fields", "length")

    def __init__(self, terms, fields, length):
        self.terms, self.fields, self.length = terms, fields, length

class Index:
    """Cards' and findings' words: each document's words in order, with their fields (-1 ends a field, so a phrase
    stays in one), and each word's documents. add() takes one report's cards ({id: HTML}, their keys prefixed to keep
    several reports' apart), what they say (said: a list of HTML) and its findings (each with its HTML, given a
    `doc`)."""
    def __init__(self):
        self.vocab, self.postings, self.docs = {}, [], []
        self.pages, self.card_doc, self.names, self.values = {}, {}, {}, {}
        self.synonyms, self.vectors = {}, {}  # the vectors: {card: (signed bytes, their length)}
        self._sorted = None

    def _add(self, fields):
        doc, terms, of, length = len(self.docs), [], [], 0
        for field, text in fields:
            for w in words(text):
                t = self.vocab.get(w)
                if t is None:
                    t = self.vocab[w] = len(self.vocab)
                    self.postings.append([])
                if not self.postings[t] or self.postings[t][-1] != doc:
                    self.postings[t].append(doc)
                terms.append(t)
                of.append(field)
                length += WEIGHTS[field]
            terms.append(-1)
            of.append(field)
        self.docs.append(Doc(terms, of, length))
        self._sorted = None
        return doc

    def _card(self, key, html, said):
        found = CARD.search(html)
        if not found:
            return self._add([(OTHER, plain(html))])
        head = plain(found.group(1)).split(" · ")
        head.pop()  # its kind: a filter's
        page = re.search(r"(\d+)\s*$", head.pop() if head else "")
        section = head.pop()[2:] if len(head) > 1 and head[-1].startswith("§ ") else ""
        fields = [(FILE, " · ".join(head)), (SECTION, section)]
        n = int(found.group(2))
        statement = STATEMENT.match(said[n] if n < len(said) else "")
        if statement:
            entity, attribute, value, conditions, more, quote = statement.groups()
            fields += [(ENTITY, plain(entity)), (ATTRIBUTE, plain(attribute)), (VALUE, plain(value))]
            self.names[key] = (plain(entity), plain(attribute))
            if plain(conditions).strip() != "unspecified":
                fields.append((CONDITIONS, plain(conditions)))
            fields += [(CONTEXT, line) for line in lines(more)] + [(QUOTE, plain(quote))]
        fields += [(CONTEXT, line) for line in lines(found.group(3))]
        doc = self._add(fields)
        if page:
            self.pages[doc] = int(page.group(1))
        return doc

    def add(self, cards, said, findings=(), prefix="", values=None):
        for key, html in cards.items():
            self.card_doc[prefix + key] = doc = self._card(prefix + key, html, said)
            if values and values.get(key):
                self.values[doc] = values[key]
        for f in findings:
            f["doc"] = self._add([(OTHER, plain(SAME.sub("", f["html"])))])

    @property
    def sorted(self):
        if self._sorted is None:
            self._sorted = sorted(self.vocab)
            total = sum(d.length for d in self.docs)
            self.average = total / max(1, len(self.docs))
            self.spelled = {t: w for w, t in self.vocab.items()}
        return self._sorted

    def docs_of(self, x):
        if "cards" in x:
            return [self.card_doc.get(x["cards"][0]), self.card_doc.get(x["cards"][1]), x.get("doc")]
        return [self.card_doc.get(x["card"])]

    def expand(self, w):
        """A word's terms: those it begins (letters), or itself (a number, a letter alone)."""
        if is_number(w) or len(w) < 2:
            return [self.vocab[w]] if w in self.vocab else []
        out, i = [], bisect_left(self.sorted, w)
        while i < len(self.sorted) and self.sorted[i].startswith(w):
            out.append(self.vocab[self.sorted[i]])
            i += 1
        return out

    def weight(self, sets, field, doc, whole=False):
        """How much a term's words, in a row, weigh in a document (0: not found); a file's name only when asked for
        (file:), or "mw" would find every claim of "nrel-5mw.pdf". whole: the words are the field's, all of it (another
        name, matched as a claim's name)."""
        d, n = self.docs[doc], 0
        for i in range(len(d.terms) - len(sets) + 1):
            j = 0
            while j < len(sets) and d.terms[i + j] in sets[j]:
                j += 1
            if whole and not ((i == 0 or d.terms[i - 1] == -1) and i + j < len(d.terms) and d.terms[i + j] == -1):
                continue
            if j == len(sets) and (d.fields[i] != FILE if field is None else d.fields[i] == field):
                n += WEIGHTS[d.fields[i]]
        return n

    def hits(self, term):
        """The documents holding a term: {doc: its weight}."""
        out = {}
        if "unknown" in term:
            return out
        if "compare" in term:
            return {doc: 0 for doc, value in self.values.items() if within(term["compare"], value)}
        if "pages" in term:
            low, high = term["pages"]
            return {doc: 0 for doc, page in self.pages.items() if low <= page <= high}
        exact = lambda w: {self.vocab[w]} if w in self.vocab else set()  # noqa: E731 (a whole name's words, as written)
        sets = ([set(term["terms"])] if "terms" in term else
                [exact(w) if term.get("whole") else set(self.expand(w)) for w in term["words"]])
        if any(not s for s in sets):
            return out
        rarest = min(sets, key=lambda s: sum(len(self.postings[t]) for t in s))
        for t in rarest:
            for doc in self.postings[t]:
                if doc in out:
                    continue
                n = self.weight(sets, term.get("field"), doc, term.get("whole", False))
                if n > 0:
                    out[doc] = n
        return out

    def about(self, key):
        """like:ID's terms: the words saying what the claim is about, each its own term, weighing as its field does."""
        doc = self.card_doc.get(key)
        if doc is None:
            return []
        self.sorted  # noqa: B018 (the spelling table)
        d, out = self.docs[doc], {}
        for t, field in zip(d.terms, d.fields):
            if t >= 0 and field in ABOUT:
                out[t] = max(out.get(t, 0), WEIGHTS[field] / WEIGHTS[ENTITY])
        return [{"terms": [t], "field": None, "boost": boost} for t, boost in out.items()
                if len(self.spelled[t]) > 1 and self.spelled[t] not in STOP and not is_number(self.spelled[t])]

    def about_words(self, key):
        return [self.spelled[term["terms"][0]] for term in self.about(key)]

    def cosines(self, vector):
        """{doc: cosine} of every claim with a vector, to a vector (bytes, length): embed.cosine's, as the page's."""
        v, length = vector
        return {self.card_doc[key]: sum(a * b for a, b in zip(v, w)) / (length * other or 1)
                for key, (w, other) in self.vectors.items()}

    def find(self, groups):
        """What a query's groups find: a function giving the items (findings or claims) found among some,
        {item's index: score} in the items' order."""
        self.sorted  # noqa: B018 (the vocabulary sorted, the average length)
        n = len(self.docs)

        def scores(term, out):
            found = self.hits(term)
            idf = math.log(1 + (n - len(found) + 0.5) / (len(found) + 0.5))
            for doc, w in found.items():
                s = w and (term.get("boost") or 1) * idf * w * (K1 + 1) / (
                    w + K1 * (1 - B + B * self.docs[doc].length / self.average))
                out[doc] = out.get(doc, 0) + s

        scored = []
        for group in groups:
            out = {}

            def add(doc, s, out=out):
                out[doc] = out.get(doc, 0) + s
            for term in group["terms"]:
                if "near" in term:  # near:ID: the claims near it in meaning; not it
                    mine, own = self.vectors.get(term["near"]), self.card_doc.get(term["near"])
                    for doc, c in (self.cosines(mine) if mine else {}).items():
                        if doc != own and c >= NEAR_LEAST:
                            add(doc, MEANING_WEIGHT * c)
                    continue
                if "meaning" in term:  # a typed query, embedded by the command line: the claims nearest it
                    cos = self.cosines(term["vector"]) if term.get("vector") else {}
                    best = max(cos.values(), default=0)
                    for doc, c in cos.items():
                        if c >= MEANING_SHARE * best:
                            add(doc, MEANING_WEIGHT * c)
                    continue
                if "like" not in term:
                    scores(term, out)
                    continue
                alike, own = {}, self.card_doc.get(term["like"])
                for one in self.about(term["like"]):
                    scores(one, alike)
                least = LIKE_SHARE * alike.get(own, 0)
                kept = {doc: s for doc, s in alike.items() if doc != own and s >= least}
                mine = self.vectors.get(term["like"])
                if not mine:
                    for doc, s in kept.items():
                        add(doc, s)
                    continue
                # with the claims' vectors, words and meaning blended (measured better than either)
                cos = self.cosines(mine)
                best = max(kept.values(), default=0)
                chosen = set(kept) | {doc for doc, c in cos.items() if doc != own and c >= NEAR_LEAST}
                for doc in chosen:
                    add(doc, MEANING_WEIGHT * (kept.get(doc, 0) / (best or 1) + cos.get(doc, 0)))
            scored.append(out)

        def among(items):
            result = {}
            for i, x in enumerate(items):
                ds, score, kept = self.docs_of(x), 0, True
                for group, hit_docs in zip(groups, scored):
                    hit = False
                    for d in ds:
                        if d is not None and d in hit_docs:
                            hit = True
                            score += 0 if group["not"] else hit_docs[d]
                    if hit == group["not"]:
                        kept = False
                if kept:
                    result[i] = score
            return result
        return among

def _below(a, b, open_):
    tolerance = 1e-9 * max(1, abs(a), abs(b))
    return a < b - tolerance if open_ else a <= b + tolerance

def within(q, value):
    """Whether a value [kind, size, low, high] is within a comparison's bounds: in its kind, converted, or as written
    when the comparison names no unit."""
    kind, size, low, high = value
    if q["kind"] is not None and kind != q["kind"]:
        return False
    scale = 1 if q["kind"] is None else size
    lo, hi = (None if low is None else low * scale), (None if high is None else high * scale)
    return ((lo is None or q["hi"] is None or _below(lo, q["hi"], q["highOpen"]))
            and (q["lo"] is None or hi is None or _below(q["lo"], hi, q["lowOpen"])))

# a value compared (milestone 3: ">50kW", "value:10-20mm", "value:0.075MW"): an operator, a number or a range, and a
# unit, which may be the next word (">50 kW")
NUM = r"[+-]?(?:[0-9][0-9,]*(?:\.[0-9]+)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?"
COMPARED = re.compile(rf"^(<=|>=|<|>|≤|≥)?\s*({NUM})(?:\s*(?:–|-|to)\s*({NUM}))?\s*(\S.*)?$")

def _number(text):
    return float(text.replace(",", ""))

def compared(op, a, b, unit_text):
    """The term comparing a value: its bounds in its unit's base (or as written, without a unit); {"unknown"} for a
    unit the search doesn't know."""
    kind, size = None, 1
    if unit_text:
        known = unit_of(unit_text)
        if not known:
            return {"unknown": unit_text}
        kind, size = known
    x, y = _number(a) * size, (None if b is None else _number(b) * size)
    q = {"lo": x, "hi": x, "lowOpen": False, "highOpen": False, "kind": kind}
    if y is not None:
        q.update(lo=min(x, y), hi=max(x, y))
    elif op in (">", ">=", "≥"):
        q.update(hi=None, lowOpen=op == ">")
    elif op:
        q.update(lo=None, highOpen=op == "<")
    return {"compare": q}

# a query: groups, each to be found (or, with "-", not), by any of its terms ("a OR b"); a term: words in a row (a
# phrase), in one field or any; a value compared; page:N or page:N-M; like:ID
TERM = re.compile(r'(-?)(?:([A-Za-z]+):)?(?:"([^"]*)"?|(\S+))')

def parse(text):
    groups, either = [], False
    tokens = [(m.group(0), m.group(1), m.group(2), m.group(3), m.group(4)) for m in TERM.finditer(text)]
    i = -1
    while i + 1 < len(tokens):
        i += 1
        whole, not_, name, quoted, bare = tokens[i]
        if not not_ and not name and quoted is None and bare in ("OR", "|"):
            either = bool(groups)
            continue
        key, raw = (name or "").lower(), bare if quoted is None else quoted
        value = COMPARED.match(raw) if key == "value" or (not key and quoted is None) else None
        # a comparison: an operator, or value: with a range or a known unit ("value:3.5:1" stays words)
        ranged = value and (value.group(3) is not None or (value.group(4) is not None and unit_of(value.group(4))))
        term = None
        if value and (value.group(1) or (key == "value" and ranged)):
            unit_text = value.group(4)
            following = tokens[i + 1] if i + 1 < len(tokens) else None
            if (not unit_text and following and not following[1] and not following[2] and following[3] is None
                    and unit_of(following[4])):
                unit_text = following[4]
                i += 1
            term = compared(value.group(1), value.group(2), value.group(3), unit_text)
        elif key in ("like", "near", "meaning"):
            term = {key: raw}
        elif key == "page":
            pages = re.fullmatch(r"([0-9]+)(?:-([0-9]+))?", raw)
            if pages:
                term = {"pages": (int(pages.group(1)), int(pages.group(2) or pages.group(1)))}
        else:
            ws = words(raw if key in NAMED else re.sub("^-", "", whole))
            # a word such as "of" or "the", typed bare, isn't asked for: "power of the pump" finds "pump power"
            asked = quoted is not None or any(w not in STOP for w in ws)
            if ws and asked:
                term = {"words": ws, "field": NAMED.get(key)}
        if term is None:
            continue
        if either and not not_:
            groups[-1]["terms"].append(term)
        else:
            groups.append({"not": bool(not_), "terms": [term]})
        either = False
    return groups

def asks(w, b):
    """Whether a word is one a query asks for: letters by their beginnings, numbers (and a letter alone) whole."""
    return w == b if is_number(b) or len(b) < 2 else w.startswith(b)

def _asked(groups):
    return [[t for t in g["terms"] if "words" in t] for g in groups if not g["not"]]

def unknown(groups):
    """The units a query names that the search doesn't know."""
    return [t["unknown"] for g in groups for t in g["terms"] if "unknown" in t]

def covers(groups, text):
    """Whether a name holds every word group a query asks for (fields, phrases' order and pages aside)."""
    ws = words(text)
    holds = lambda t: all(any(asks(w, b) for w in ws) for b in t["words"])  # noqa: E731
    return all(not terms or any(holds(t) for t in terms) for terms in _asked(groups))

def touches(groups, text):
    """Whether a name holds any word a query asks for."""
    ws = words(text)
    return any(any(asks(w, b) for w in ws) for terms in _asked(groups) for t in terms for b in t["words"])

def names(groups, text):
    """Whether a query names a name: finds it, and asks for every word it has ("rated output" names "rated output",
    not "rated output limit"; words such as "of" aside)."""
    ws = [w for w in words(text) if w not in STOP]
    terms = [t for terms in _asked(groups) for t in terms]
    return bool(ws) and covers(groups, text) and all(any(asks(w, b) for t in terms for b in t["words"]) for w in ws)

GLOSSARY = "glossary"  # the other names' kind that's the glossary's: each term with its meanings (report.search_names)

def other_names(groups, synonyms):
    """The other names for what a query names (synonyms: {"items", "properties"}, the model's groups of names, the
    search_names lever; and "glossary", each glossary term with its meanings), each with the query finding it and its
    kind: [(name, groups, kind)]. The model's find claims whose item (or property) is that name, all of it and as
    written (not "diameter" in "rotor diameter"); the glossary's, its words anywhere in a claim (an abbreviation is
    the same words: "side water depth" finds "at an SWD of"). With the query's exclusions and its terms that aren't
    words (values, pages); none for like:."""
    out = []
    if not synonyms or any("like" in t or "near" in t for g in groups for t in g["terms"]):
        return out
    kept = [g for g in groups if g["not"] or not any("words" in t for t in g["terms"])]
    for kind, field in (("items", ENTITY), ("properties", ATTRIBUTE), (GLOSSARY, None)):
        for group in synonyms.get(kind) or []:
            if not any(names(groups, n) for n in group):
                continue
            for name in group:
                ws = words(name)
                if not ws or names(groups, name) or any(o[0] == name for o in out):
                    continue
                term = {"words": ws, "field": field} if field is None else {"words": ws, "field": field, "whole": True}
                out.append((name, [{"not": False, "terms": [term]}] + kept, kind))
    return out

OTHER_NAME_SHARE = 0.5  # a claim found by another name scores half (the page's)

def worded(groups):
    return any(not g["not"] and any("words" in t for t in g["terms"]) for g in groups)

def counterparts(findings):
    """Each claim's counterparts: the claims findings pair it with ({card: [cards]})."""
    out = {}
    for f in findings:
        a, b = f["cards"]
        out.setdefault(a, []).append(b)
        out.setdefault(b, []).append(a)
    return out

def paired_with(index, groups, found, claims, pairs):
    """The found claims' counterparts the search didn't find ({claim's index: half its counterpart's score}), and the
    other source's names for what was searched ([(name, how many)], six at most), as the page offers them."""
    at = {c["card"]: i for i, c in enumerate(claims)}
    added, names = {}, {}
    for i, score in found.items():
        own = index.names.get(claims[i]["card"], ("", ""))
        for card in pairs.get(claims[i]["card"], ()):
            j = at.get(card)
            if j is None:
                continue
            if j not in found:
                added[j] = max(added.get(j, 0), score / 2)
            for k, name in enumerate(index.names.get(card, ("", ""))):
                if not name.strip() or not touches(groups, own[k]) or covers(groups, name):
                    continue
                key = " ".join(words(name))
                names[key] = (names[key][0] if key in names else name, (names[key][1] if key in names else 0) + 1)
    ranked = sorted(names.values(), key=lambda x: -x[1])[:6]  # stable: the first found first among equals
    return added, ranked

def report_items(data, index, prefix=""):
    """A report's claims and related findings, listed as its page lists them, their cards added to the index (keys
    prefixed: several stores' reports in one index): (claims, findings), each a record as the page's."""
    from .report import Cards, claim_records, file_index, file_pairs, finding_html, ordered
    card = Cards(data)
    findings = [{"relation": f["relation"], "cards": [prefix + f["a"], prefix + f["b"]], "html": finding_html(f, card),
                 "finding": f} for f in ordered(data["findings"]) if f["relation"] != "unrelated"]
    sides = [s["name"] for s in data["sources"]]
    claims = claim_records(data, card, file_index(file_pairs(data)), {}, sides)
    from .report import search_names
    for kind, groups in search_names(data).items():  # the model's other names and the glossary's, every report's
        index.synonyms.setdefault(kind, []).extend(groups)
    vectors = data.get("vectors") or {}
    for claim, i in (vectors.get("of") or {}).items():  # the claims' vectors (the embed lever)
        from .embed import unpacked
        v = unpacked(vectors["vectors"][i])
        index.vectors[prefix + claim] = (v, math.sqrt(sum(x * x for x in v)))
    index.add(card.html, list(card.said), findings, prefix, {k: claim_value(card.evidence[k]) for k in card.html})
    for claim in claims:  # what the command prints of it
        e = card.evidence[claim["card"]]
        claim.update(evidence=e, where=card.where(e["content"]), source=sides[claim["side"]] if claim["side"] >= 0
                     else "", section=card.headings.get((e["content"], e.get("section", "")), ""),
                     card=prefix + claim["card"])
    return claims, findings

def search(index, groups, claims, findings, view="claims", paired=True, side=None):
    """What a query finds in one view, as the page shows it: ([(item's index, score, how)], the other source's names
    for it, the other names [(name, kind)]: the model's and the glossary's, other_names), the most relevant first (ties
    as listed). how: "" (the query found it),
    "counterpart", or the other name that found it ("name:drive"); counterparts and other names only when paired."""
    among = index.find(groups)
    found = {"claims": among(claims), "findings": among(findings)}
    added, offered = (paired_with(index, groups, found["claims"], claims, counterparts(findings)) if worded(groups)
                      else ({}, []))
    how = {"claims": {}, "findings": {}}
    if paired:
        for i, score in added.items():
            found["claims"][i] = score
            how["claims"][i] = "counterpart"
    others = other_names(groups, index.synonyms)
    for name, query, _ in others if paired else ():
        alike = index.find(query)
        for key, items in (("claims", claims), ("findings", findings)):
            for i, score in alike(items).items():
                if i not in found[key]:
                    found[key][i] = score * OTHER_NAME_SHARE
                    how[key][i] = "name:" + name
    hits = found[view]
    kept = [i for i in hits if view == "findings" or side is None or claims[i]["side"] == side]
    kept.sort()  # as listed, then by score: a stable sort keeps the listed order among equals
    kept.sort(key=lambda i: -hits[i])
    return [(i, hits[i], how[view].get(i, "")) for i in kept], offered, [(name, kind) for name, _, kind in others]
