"""Links: subjects of two sources possibly one, kept apart (links.py; docs/plans/tentative-matches-2026-11-07.md,
milestone 2). The owner, 2026-11-07: "Three levels is a start"; plausible matches "should feed links and topics for
now"; revisions' and proposals' evidence weighed apart ("I'll accept these recommendations.")."""
import stubs  # noqa: F401 (a clean environment)
import unittest

from semantic_pdf_diff import indexes, indexfiles, links
from semantic_pdf_diff.report import linked_names, subjects_html
from test_indexes import claim, report

A = [claim("A-1", "ca", "Harrow Creek Water Treatment Plant", "design flow", "25.9", "MGD"),
     claim("A-2", "ca", "Harrow Creek Water Treatment Plant", "peak flow", "42.2", "MGD"),
     claim("A-3", "ca", "Alum", "dose", "38.8", "mg/L"), claim("A-4", "ca", "Alum", "maximum dose", "55.7", "mg/L"),
     claim("A-5", "ca", "Room 104", "area", "200", "ft2"), claim("A-6", "ca", "Room 104", "width", "12", "ft")]
B = [claim("B-1", "cb", "Pine Ridge Water Treatment Plant", "design flow", "16.3", "MGD"),
     claim("B-2", "cb", "Pine Ridge Water Treatment Plant", "peak flow", "42.7", "MGD"),
     claim("B-3", "cb", "ferric sulfate", "dose", "18.5", "mg/L"),
     claim("B-4", "cb", "ferric sulfate", "maximum dose", "71.2", "mg/L"),
     claim("B-5", "cb", "Room 105", "area", "200", "ft2"), claim("B-6", "cb", "Room 105", "width", "12", "ft"),
     claim("B-7", "cb", "backwash pump", "capacity", "3228", "gpm")]

def links_of(data):
    """{(subject, other): (level, relation, signals)}, each pair once (the first source's subject first)."""
    out = {}
    for s in indexes.built(data)["subjects"]:
        for x in s.get("links", []):
            if list(s["claims"]) == ["a"]:
                out[s["name"], x["other"]] = (x["level"], x["relation"], x["signals"])
    return out

class Linked(unittest.TestCase):
    def test_two_signals_plausible_one_possible_identifiers_apart_kept_apart(self):
        data = report(A + B, [], ("a", "b"), mode="proposals")
        self.assertEqual(links_of(data), {
            ("Alum", "ferric sulfate"): ("possible", "corresponding", ["properties"]),  # its doses alone
            ("Harrow Creek Water Treatment Plant", "Pine Ridge Water Treatment Plant"):
                ("plausible", "corresponding", ["name", "properties"])})  # Room 104 isn't Room 105; no decoy's
        self.assertEqual(len(indexes.built(data)["subjects"]), 7)  # none joined
        judged = report(A + B, [{"a": "A-3", "b": "B-3", "relation": "different"}], ("a", "b"), mode="proposals")
        self.assertEqual(links_of(judged)["Alum", "ferric sulfate"][0], "plausible")
        doubt = report(A + B, [{"a": "A-3", "b": "B-3", "relation": "uncertain"}], ("a", "b"), mode="proposals")
        self.assertEqual(links_of(doubt)["Alum", "ferric sulfate"][0], "possible")  # doubt isn't evidence

    def test_values_in_common_count_between_revisions_not_proposals(self):
        a = [claim("A-1", "ca", "feed pump", "capacity", "1,200", "gpm"), claim("A-2", "ca", "feed pump", "head", "42",
                                                                                "ft")]
        b = [claim("B-1", "cb", "transfer pump", "flow", "1,200", "gpm"), claim("B-2", "cb", "transfer pump", "TDH",
                                                                                 "42", "ft")]
        self.assertEqual(links_of(report(a + b, [], ("a", "b"), mode="revisions")),
                         {("feed pump", "transfer pump"): ("plausible", "same", ["name", "values"])})
        self.assertEqual(links_of(report(a + b, [], ("a", "b"), mode="proposals")),
                         {("feed pump", "transfer pump"): ("possible", "corresponding", ["name"])})

    def test_the_models_taken_answer_a_link_not_a_match(self):
        taken = {"kind": "match", "source": "a", "subject": "Alum", "other_source": "b", "other": "ferric sulfate",
                 "relation": "corresponding", "taken": True}
        data = report(A + B, [], ("a", "b"), mode="proposals", commentary={"entries": [taken]})
        self.assertEqual(links_of(data)["Alum", "ferric sulfate"], ("plausible", "corresponding",
                                                                      ["properties", "model"]))
        self.assertEqual(next(s for s in indexes.built(data)["subjects"] if s["name"] == "Alum")["matched_by"], "")
        state = {**taken, "relation": "state", "taken": False}
        data = report(A + B, [], ("a", "b"), mode="proposals", commentary={"entries": [state]})
        self.assertEqual(links_of(data)["Alum", "ferric sulfate"][1], "state")  # kept apart, now linked

    def test_a_subjects_links_at_most_three_the_most_evidenced(self):
        a = [claim("A-1", "ca", "tank", "volume", "10", "gal"), claim("A-2", "ca", "tank", "depth", "4", "ft")]
        b = [claim(f"B-{k}{n}", "cb", f"vessel {name}", attribute, value, unit)
             for k, name in enumerate(["north", "south", "east", "west"])
             for n, (attribute, value, unit) in enumerate([("volume", f"2{k}", "gal"), ("depth", f"5{k}", "ft")])]
        found = links_of(report(a + b, [], ("a", "b"), mode="proposals"))
        self.assertEqual(len(found), links.LINKS)

class Shown(unittest.TestCase):
    def test_in_the_index_the_subjects_view_its_search_and_the_topics(self):
        data = report(A + B, [{"a": "A-1", "b": "B-1", "relation": "unrelated"}], ("a", "b"), mode="proposals")
        index = indexes.built(data)
        page = indexfiles.markdown(index)
        self.assertIn("Possibly the counterpart of Pine Ridge Water Treatment Plant (b; plausible: names, properties "
                      "in common)", page)
        shown = subjects_html(index["subjects"], index["sources"])
        self.assertIn("possibly the counterpart of Harrow Creek Water Treatment Plant (a; plausible: names, "
                      "properties in common)", shown)
        named = linked_names(data)  # the plausible link's claims counted as one subject's by the topics
        self.assertEqual(named["A-1"], "Pine Ridge Water Treatment Plant")
        self.assertEqual(named["B-2"], "Harrow Creek Water Treatment Plant")
        self.assertNotIn("A-3", named)  # alum and ferric sulfate only possibly

if __name__ == "__main__":
    unittest.main()
