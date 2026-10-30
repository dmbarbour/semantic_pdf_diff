"""A glossary's terms as words (docs/plans/indexes-and-glossaries-2026-10-29.md): text folded as found, a term that
describes a mark drawn, and, for the reader and the comparison (milestone 5), the terms looked up in words (Terms).
Pure: they import it without the glossary's reading (glossary.py), which reaches the store and the scanner.
"""
import re
from collections import defaultdict

def fold(text):
    """Text as found: case, spacing, dashes and quotes folded."""
    text = str(text).casefold().translate(str.maketrans("–—‐‑’‘“”", "----''\"\""))
    return " ".join(text.split())

def drawn(term):
    """Whether a term describes a mark drawn ("[circle with M]"), not a name printed."""
    return term.startswith("[") and term.endswith("]") and len(term) > 2

PAGE = re.compile(r"\bpage (\d+)$")  # where a sheet's term is defined: "E-001.pdf, page 4"
SHORT = 80  # characters: a meaning longer than this is a definition, not a name
# Common words a list may define too ("OF" outside face, "IF" inside face, "NO." number): a term only where printed in
# capitals apart from capitals (_apart), as on a sheet "TOP OF STEEL" holds the word
WORDS = frozenset("a an and are as at be but by do for from if in is it no not of on or so the to up we".split())

def _found(terms, flags=0):
    """One pattern finding any of terms as a word, a plural's too ("SBs"), the longest first, its words apart by any
    spacing; None for none."""
    if not terms:
        return None
    alternation = "|".join(r"\s+".join(map(re.escape, t.split())) for t in sorted(terms, key=lambda t: (-len(t), t)))
    return re.compile(rf"(?<![\w&-])({alternation})s?(?![\w&-])", flags)

def _apart(text, m):
    """Whether what m found stands apart from the words beside it: neither printed in capitals."""
    before = re.findall(r"[A-Za-z]+", text[max(0, m.start() - 40):m.start()])[-1:]
    after = re.findall(r"[A-Za-z]+", text[m.end():m.end() + 40])[:1]
    return not any(len(w) > 1 and w.isupper() for w in before + after)

class Terms:
    """Glossary entries as the reader and the comparison look them up: each term with its meanings, by reach (its
    document's, a discipline's sheets', or a sheet's on that page), the nearest holding where it's defined: a sheet's
    legend, then its discipline's list, then the document's ("EF" each face on a structural sheet, exhaust fan on
    another). A term of one character, or a mark described, isn't looked for: "A" and "[circle]" aren't words a claim
    would use as defined. A term with a capital past its first letter ("SWD", "pH") is matched as printed; another
    ("Clearwell") whatever its case; a common word (WORDS) only in capitals, apart from capitals.

    For alignment, a meaning written out is folded into its term (abbreviated): an abbreviation is one word whichever
    way it's written. Spelling "PDCP" out instead made two properties sharing it, "PDCP layer integrity protection"
    and "PDCP layer ciphering", share four words of six, and settled as one (TS 38.300, 2026-10-30)."""

    def __init__(self, entries, disciplines=None):
        """disciplines: a document's pages' disciplines ({page: "S"}, glossary.read's), where a discipline's list
        reaches its sheets; a discipline's entries hold nowhere else."""
        # (term, its scope): meanings; a scope None (its document's), a discipline's letter, or a page (a sheet's)
        self.meanings = defaultdict(set)
        for e in entries:
            term = " ".join(e["term"].split())  # its words one space apart, as they're looked up
            if len(term) < 2 or drawn(term):
                continue
            reach, scope = e.get("reach", "document"), None
            if reach == "discipline":
                scope = e["discipline"]
            elif reach != "document":
                at = PAGE.search(e["where"])
                if at is None:
                    continue
                scope = int(at.group(1))
            self.meanings[term, scope].add(e["meaning"])
        self.disciplines = {int(page): d for page, d in (disciplines or {}).items()}
        terms = {t for t, _ in self.meanings}
        exact = {t for t in terms if any(c.isupper() for c in t[1:])}
        self.by_fold = {t.casefold(): t for t in sorted(terms - exact, reverse=True)}
        self.patterns = [(p, f) for p, f in ((_found(exact), None), (_found(terms - exact, re.IGNORECASE),
                                                                     self.by_fold)) if p is not None]
        # a meaning of two words or more, of a term its documents define one way and the only term so defined, at
        # most 80 characters (longer is a definition); and a meaning's last words, two or more of three or more,
        # where no other meaning ends so ("detention time", of "hydraulic detention time")
        # (its document's and its disciplines' meanings: one meaning of them all)
        over = defaultdict(set)
        for (t, scope), ms in self.meanings.items():
            if not isinstance(scope, int):
                over[t] |= ms
        given = defaultdict(set)
        for t, ms in over.items():
            if len(ms) == 1:
                m = fold(next(iter(ms)))
                if len(m) <= SHORT and len(m.split()) >= 2:
                    given[m].add(t)
        self.named = {m: next(iter(ts)) for m, ts in given.items() if len(ts) == 1}
        tails = defaultdict(set)
        for m, t in self.named.items():
            words = m.split()
            for k in range(1, len(words) - 1):
                tails[" ".join(words[k:])].add(t)
        self.named.update({tail: next(iter(ts)) for tail, ts in tails.items() if len(ts) == 1 and tail not in given})
        self.spelled = _found(set(self.named), re.IGNORECASE)

    def _terms(self, text):
        for pattern, folded in self.patterns:
            for m in pattern.finditer(text):
                found = " ".join(m.group(1).split())  # found across a line break too ("parent \nnode")
                term = folded[found.casefold()] if folded else found
                if fold(term).rstrip(".") in WORDS and not (found.isupper() and _apart(text, m)):
                    continue  # the word, not the term: "of the wall", "TOP OF STEEL"
                yield m, term

    def defined(self, term, page=None):
        """A term's meanings on a page: its sheet's, else its discipline's, else its document's."""
        for scope in (page, self.disciplines.get(page), None):
            if self.meanings.get((term, scope)):
                return self.meanings[term, scope]
        return set()

    def used(self, texts, page=None):
        """{term: its meanings, "; " between}: the terms these words use (texts), as defined where they are (their
        page's sheet, its discipline, their document)."""
        out = {}
        for text in texts:
            for _, term in self._terms(str(text or "")):
                meanings = self.defined(term, page)
                if meanings:
                    out[term] = "; ".join(sorted(meanings, key=lambda m: (fold(m), m)))
        return dict(sorted(out.items()))

    def shown(self, text, page=None):
        """The terms these words use, as a reader is shown them ("HDT = hydraulic detention time; SWD = side water
        depth"; "" for none): each with its meanings of at most SHORT characters, " / " between them; a term whose
        meaning the words spell out too left out (an abbreviations list's row, "side water depth (SWD)")."""
        words, out = fold(text), []
        for term in self.used([text], page):
            meanings = sorted((m for m in self.defined(term, page) if len(m) <= SHORT), key=lambda m: (fold(m), m))
            if meanings and not any(re.search(rf"(?<!\w){re.escape(fold(m))}(?!\w)", words) for m in meanings):
                out.append(f"{term} = " + " / ".join(meanings))
        return "; ".join(out)

    def abbreviated(self, text):
        """text with each meaning written out as its term ("a side water depth of" as "a SWD of", "detention time"
        as "HDT"): what alignment weighs, never what's shown."""
        text = str(text or "")
        return self.spelled.sub(lambda m: self.named[fold(m.group(1))], text) if self.spelled else text
