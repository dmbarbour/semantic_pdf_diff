"""How well a run read each page (quality.py; the run-quality report, milestone 1): what it recorded of its own
reading, counted by file and page, each kind apart, in the report's Reading view and the run's last lines."""
import stubs  # noqa: F401 (a clean environment)
import re
import unittest

from semantic_pdf_diff import quality
from semantic_pdf_diff.report import quality_html
from semantic_pdf_diff.retiling import CUT_NOTE
from semantic_pdf_diff.tablestructure import AS_LEFT
from semantic_pdf_diff.tasks import REJECTED

A, B = "sha256:a.pdf", "sha256:b.pdf"

def row(content, page, task, status="complete", issues=(), image=None):
    return {"content": content, "page": page, "task": task, "status": status, "issues": list(issues),
            "claims": 0, **({"image": image} if image else {})}

def claim(eid, content, page, image=None, verified=True):
    return {"id": eid, "content": content, "locator": {"page": page}, "quote_verified": verified,
            **({"image": image} if image else {})}

def report():
    coverage = [
        row(A, 1, "text:p1:0", "partial", [REJECTED, REJECTED]),  # two claims dropped: not "cut short" too
        row(A, 1, "tile:p1:0", "partial", ["The text is clipped at the right edge"], image="t.png"),
        row(A, 1, "tile:p1:1", image="u.png"),
        row(A, 2, "text:p2:0", "failed", ["ModelFailure: HTTP 500"]),
        row(A, 2, "table:p2:t0", issues=[f"{AS_LEFT}: the rules failed twice"]),
        row(A, 2, "tile:p2:0", "partial", ["Continued: the claim limit reached, the rest asked for (tile:p2:0-c1)"],
            image="v.png"),
        row(A, 3, "tile:p3:0", issues=[f"{CUT_NOTE} bottom edge"], image="w.png"),
        row(A, 4, "text:p4:0"),
        row(B, 1, "text:p1:0", "not_reached"),
    ]
    evidence = [claim("e1", A, 1), claim("e2", A, 1, image="t.png", verified=False),
                claim("e3", A, 1, image="u.png"), claim("e4", A, 4), claim("e5", A, 4, image="x.png", verified=None)]
    commentary = {"entries": [{"kind": "suspicion", "relation": "misread", "claims": ["e4"]},
                              {"kind": "reread", "relation": "otherwise", "claims": ["e1"]},
                              {"kind": "reread", "relation": "as_claimed", "claims": ["e3"]},
                              {"kind": "relation", "relation": "contradicts", "claims": ["e1", "e4"]}]}
    files = [{"source": "s", "path": "b.pdf", "content": B}, {"source": "s", "path": "dir/a file.pdf", "content": A}]
    return {"coverage": coverage, "evidence": evidence, "commentary": commentary, "files": files}

class Counted(unittest.TestCase):
    def test_each_kind_by_page_with_what_its_counted_of(self):
        found = {(p["content"], p["page"]): p for p in quality.pages(report())}
        self.assertEqual(list(found), [(B, 1), (A, 1), (A, 2), (A, 3), (A, 4)])  # the files' order, then pages'
        one = found[(A, 1)]
        self.assertEqual(one["counts"], {"dropped": 2, "short": 1, "cut": 1, "unverified": 1, "reread": 1})
        self.assertEqual([quality.said(one, k) for k in ("dropped", "short", "cut", "unverified")],
                         ["2 of 3", "1 of 3", "1 of 2", "1 of 2"])  # 1 kept from text; 2 tiles; 2 checked
        self.assertEqual(found[(A, 2)]["counts"], {"failed": 1, "tables": 1})  # continued: not cut short
        self.assertEqual(found[(A, 3)]["counts"], {"cut": 1})  # the edges an answer named
        self.assertEqual(found[(A, 4)]["counts"], {"doubted": 1})  # a contradiction is the document's, not ours
        self.assertEqual(found[(B, 1)]["counts"], {"unread": 1})
        self.assertEqual(quality.said(found[(A, 2)], "tables"), "1")

    def test_the_runs_line_and_the_reports_view(self):
        self.assertEqual(quality.lines(report()), [
            "Read with problems: 5 of 5 pages (failed 1, not read 1, cut short 1, quotes not found 2, quotes "
            "unverified 1, text cut 2, tables as mended 1, doubted 1, read again otherwise 1): the report's Reading "
            "view lists them"])
        self.assertEqual(quality.lines({"coverage": [row(A, 1, "text:p1:0")], "evidence": [], "files": []}), [])
        shown, troubled = quality_html(report(), lambda content: {A: "s / dir/a file.pdf", B: "s / b.pdf"}[content])
        self.assertEqual(troubled, 5)
        self.assertIn('<th title="claims dropped, their quote not in the text they were read from (of the claims its '
                      'text gave, kept or dropped)">Quotes not found</th>', shown)
        self.assertIn('<li>s / dir/a file.pdf: 4 of 4 pages; the most on pages 1 (6), 2 (2), 3 (1), 4 (1)</li>',
                      shown)
        first = re.search(r'<tr data-text[^>]*>.*?</tr>', shown.split('<tbody>')[1]).group(0)
        self.assertIn('data-places="[[&quot;s / b.pdf&quot;,1,1]]"', first)
        page_one = next(r for r in re.findall(r'<tr data-text.*?</tr>', shown) if '<td>1</td>' in r and 'a file' in r)
        self.assertIn('<a href="#claims&q=file%3A%22dir%2Fa%20file.pdf%22%20page%3A1" title="Its claims">3</a>',
                      page_one)  # its claims, by a search for its file and page
        self.assertEqual(quality_html({"coverage": [], "evidence": [], "files": []}, str), ('', 0))

if __name__ == "__main__":
    unittest.main()
