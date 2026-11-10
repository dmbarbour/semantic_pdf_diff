"""Links: subjects of two sources possibly one, kept apart (links.py; docs/plans/tentative-matches-2026-11-07.md,
milestone 2). The owner, 2026-11-07: "Three levels is a start"; plausible matches "should feed links and topics for
now"; revisions' and proposals' evidence weighed apart ("I'll accept these recommendations.")."""
import stubs  # noqa: F401 (a clean environment)
import json
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
                ("plausible", "corresponding", ["name", "properties"]),
            ("Room 104", "Room 105"): ("plausible", "corresponding", ["name", "properties"])})  # no decoy's
        self.assertEqual(len(indexes.built(data)["subjects"]), 7)  # none joined
        revisions = links_of(report(A + B, [], ("a", "b"), mode="revisions"))
        self.assertNotIn(("Room 104", "Room 105"), revisions)  # one document's Room 104 isn't its Room 105
        # (between proposals two designs' rooms may correspond, as NREL's 5 MW turbine and IEA's 15 MW do)
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

class Signals(unittest.TestCase):
    """Milestone 3: names spelled alike, and alike in meaning (the link_meaning lever's)."""
    def test_names_spelled_alike_count_as_names(self):
        a = [claim("A-1", "ca", "flocculation", "stages", "4", "")]
        b = [claim("B-1", "cb", "flocculators", "stage count", "3", "")]
        self.assertEqual(links_of(report(a + b, [], ("a", "b"), mode="proposals")),
                         {("flocculation", "flocculators"): ("possible", "corresponding", ["name"])})

    def test_names_alike_in_meaning_each_the_others_likest(self):
        from semantic_pdf_diff.embed import packed
        a = [claim("A-1", "ca", "sedimentation basins", "length", "159", "ft"),
             claim("A-2", "ca", "sedimentation basins", "width", "47", "ft"), claim("A-3", "ca", "Alum", "dose", "38.8",
                                                                                 "mg/L")]
        b = [claim("B-1", "cb", "clarifiers", "length", "166", "ft"), claim("B-2", "cb", "clarifiers", "width", "33",
                                                                             "ft"),
             claim("B-3", "cb", "settling tanks", "depth", "15", "ft")]
        vectors = {"sedimentation basins": packed([1, 0.2, 0]), "clarifiers": packed([0.95, 0.25, 0.05]),
                   "settling tanks": packed([0.9, 0.1, 0.4]), "Alum": packed([0, 0, 1])}
        data = report(a + b, [], ("a", "b"), mode="proposals", name_vectors={"vectors": vectors})
        found = links_of(data)
        self.assertEqual(found["sedimentation basins", "clarifiers"],
                         ("plausible", "corresponding", ["meaning", "properties"]))
        self.assertNotIn(("sedimentation basins", "settling tanks"), found)  # alike, but not each other's likest
        self.assertNotIn(("Alum", "settling tanks"), found)  # alike in nothing
        self.assertEqual(links_of(report(a + b, [], ("a", "b"), mode="proposals"))["sedimentation basins",
                                                                                   "clarifiers"][0],
                         "possible")  # without the vectors: its properties alone

    def test_the_rerankers_likest_scoring_well_evidence_of_its_own(self):
        a = [claim("A-1", "ca", "Alum", "dose", "38.8", "mg/L")]
        b = [claim("B-1", "cb", "ferric sulfate", "dosage", "18.5", "mg/L"),
             claim("B-2", "cb", "chlorine", "dose rate", "3.7", "mg/L")]
        ranks = {"scores": {"a": {"Alum": {"ferric sulfate": 0.81, "chlorine": 0.42}}}}
        found = links_of(report(a + b, [], ("a", "b"), mode="proposals", subject_ranks=ranks))
        self.assertEqual(found, {("Alum", "ferric sulfate"): ("possible", "corresponding", ["reranked"])})
        low = {"scores": {"a": {"Alum": {"ferric sulfate": 0.31, "chlorine": 0.12}}}}
        self.assertEqual(links_of(report(a + b, [], ("a", "b"), mode="proposals", subject_ranks=low)), {})
        from semantic_pdf_diff.rerank import described
        index = indexes.built(report(a + b, [], ("a", "b"), mode="proposals"))
        self.assertEqual(described(index["subjects"][0]), "Alum: dose")

class Tested(unittest.TestCase):
    """Milestone 4: a link's evidence tested by code (link_tests) and read by the model against a decoy (link_read)."""
    PUMPS = ([claim(f"A-{n}{k}", "ca", f"P-10{n}", attribute, value, unit)
              for n, cap, head in ((1, "1,200", "40"), (2, "2,400", "60"))
              for k, (attribute, value, unit) in enumerate([("capacity", cap, "gpm"), ("head", head, "ft")])]
             + [claim(f"B-{n}{k}", "cb", f"LL-{n}", attribute, value, unit)
                for n, cap, head in ((1, "1,300", "42"), (2, "2,500", "58"))
                for k, (attribute, value, unit) in enumerate([("capacity", cap, "gpm"), ("head", head, "ft")])])

    def test_siblings_properties_dont_set_a_pair_apart(self):
        judged = [{"a": "A-10", "b": "B-10", "relation": "different"},
                  {"a": "A-10", "b": "B-20", "relation": "different"}]
        off = links_of(report(self.PUMPS, judged, ("a", "b"), mode="proposals"))
        self.assertEqual(off["P-101", "LL-1"][0], "plausible")
        self.assertEqual(off["P-101", "LL-2"][0], "plausible")  # the other pump as plausible: its siblings' properties
        on = links_of(report(self.PUMPS, judged, ("a", "b"), mode="proposals", settings={"link_tests": True}))
        self.assertEqual((on["P-101", "LL-1"][0], on["P-101", "LL-2"][0]), ("possible", "possible"))
        self.assertNotIn(("P-102", "LL-1"), on)  # its siblings' properties alone: no link

    def test_values_that_dont_fit_leave_a_link_possible(self):
        a = [claim("A-1", "ca", "tower", "height", "87.6", "m"), claim("A-2", "ca", "tower", "mass", "347", "t")]
        b = [claim("B-1", "cb", "Tower", "height", "0.8", "Hz"), claim("B-2", "cb", "Tower", "mass", "860", "t")]
        found = [{"a": "A-1", "b": "B-1", "relation": "different"}]
        data = report(a + b, found, ("a", "b"), mode="proposals", settings={"link_tests": True})
        index = indexes.built(data)  # keyed alike: one subject; renamed apart to be linked
        self.assertEqual(len(index["subjects"]), 1)
        b = [claim("B-1", "cb", "steel tube", "height", "0.8", "Hz"), claim("B-2", "cb", "steel tube", "mass", "860",
                                                                             "t")]
        found = links_of(report(a + b, [{"a": "A-1", "b": "B-1", "relation": "different"}], ("a", "b"),
                                mode="proposals", settings={"link_tests": True}))
        self.assertEqual(found["tower", "steel tube"][0], "possible")  # a height isn't a frequency
        b[0] = claim("B-1", "cb", "steel tube", "height", "144", "m")
        found = links_of(report(a + b, [{"a": "A-1", "b": "B-1", "relation": "different"}], ("a", "b"),
                                mode="proposals", settings={"link_tests": True}))
        self.assertEqual(found["tower", "steel tube"][0], "plausible")

    def test_a_link_read_against_a_decoy(self):
        from semantic_pdf_diff import crossmatch
        judged = [{"a": "A-10", "b": "B-10", "relation": "different"}]
        data = report(self.PUMPS, judged, ("a", "b"), mode="proposals")
        asked = crossmatch.links_asked(data, indexes.built(data))
        s, _, other, _, decoy, pair, text = asked[0]
        self.assertEqual((s["name"], other["name"], decoy["name"]), ("P-101", "LL-1", "LL-2"))
        self.assertIn("values left out", text)
        self.assertNotIn("1,300", text)  # proposals' values hidden

        class Picks:
            def __init__(self, pick):
                self.pick = pick

            def ask(self, prompt, schema, images=(), key=None):
                shown = json.loads(prompt[prompt.index('{\n "item"'):])
                linked = next(k for k, v in shown["candidates"].items() if v["name"] == "LL-1")
                return schema.model_validate({"pick": linked if self.pick == "linked" else "", "why": "x"})
        for pick, level in (("linked", "plausible"), ("neither", "possible")):
            read = crossmatch.read_links(data, indexes.built(data), Picks(pick), "proposals", "x")
            entries = [e for e in read["entries"] if e["subject"] == "P-101" and e["other"] == "LL-1"]
            self.assertEqual(entries[0]["relation"], "picked" if pick == "linked" else "neither")
            with_read = report(self.PUMPS, judged, ("a", "b"), mode="proposals", commentary={"entries": entries})
            self.assertEqual(links_of(with_read)["P-101", "LL-1"][0], level)

class Weighed(unittest.TestCase):
    """Milestone 6: a link's level from its features' weights (link_levels: weights; proposals only)."""
    def test_a_pairs_score_its_bands_weights_its_level_by_the_thresholds(self):
        data = report(A + B, [{"a": "A-3", "b": "B-3", "relation": "different"}], ("a", "b"), mode="proposals",
                      settings={"link_levels": "weights"})
        index = indexes.built(data)
        plant = next(s for s in index["subjects"] if s["name"] == "Harrow Creek Water Treatment Plant")
        (link,) = plant["links"]
        table = links.weights()
        bands = {"alike": "yes", "properties": "2", "distinct": "yes", "fits": "yes", "judged": "0",
                 "meaning": "absent", "model": "none"}
        expected = round(sum(table["weights"][f].get(b, 0.0) for f, b in bands.items()), 3)
        self.assertEqual((link["score"], link["level"], link["rubric"]), (expected, "plausible", "weights/1"))
        self.assertGreater(link["likely"], 0.9)
        revisions = report(A + B, [], ("a", "b"), mode="revisions", settings={"link_levels": "weights"})
        found = [x for s in indexes.built(revisions)["subjects"] for x in s.get("links", [])]
        self.assertTrue(found and all("score" not in x for x in found))  # revisions keep the rubric

    def test_the_models_pick_raises_a_possible_link_its_neither_lowers_nothing(self):
        def pump(cid, content, name, cap, head, power):
            return [claim(f"{cid}0", content, name, "capacity", cap, "gpm"), claim(f"{cid}1", content, name, "head",
                                                                                  head, "ft"),
                    claim(f"{cid}2", content, name, "motor power", power, "hp")]
        claims = (pump("A-1", "ca", "P-101", "1,200", "40", "75") + pump("B-1", "cb", "LL-1", "1,300", "42", "80")
                  + pump("B-2", "cb", "LL-2", "2,500", "58", "120"))
        judged = [{"a": "A-10", "b": "B-10", "relation": "different"},
                  {"a": "A-11", "b": "B-11", "relation": "different"}]
        read = {"kind": "link_read", "source": "a", "subject": "P-101", "other_source": "b", "other": "LL-1",
                "relation": "picked"}
        settings = {"link_levels": "weights"}

        def level(*entries):
            data = report(claims, judged, ("a", "b"), mode="proposals", settings=settings,
                          commentary={"entries": list(entries)})
            return links_of(data)["P-101", "LL-1"][0]
        self.assertEqual(level(), "possible")  # siblings' properties, the judge's pairing: possible by the weights
        self.assertEqual(level(read), "plausible")
        self.assertEqual(level({**read, "relation": "neither"}), "possible")

class Indexed(unittest.TestCase):
    """Milestone 7: links in the index, explored (link_gaps, linked_values; both off)."""
    PLANTS = (A[:2] + [claim("A-9", "ca", "Harrow Creek Water Treatment Plant", "raw water turbidity", "37.6", "NTU")]
              + B[:2])

    def test_what_a_plausible_links_other_subject_gives_a_gap_if_one_item(self):
        data = report(self.PLANTS, [], ("a", "b"), mode="proposals", settings={"link_gaps": True})
        gaps = [(g["kind"], g["source"], g["subject"], g["property"]) for g in indexes.built(data)["gaps"]]
        self.assertEqual(gaps, [("if_one_item", "b", "Pine Ridge Water Treatment Plant", "raw water turbidity")])
        why = indexes.built(data)["gaps"][0]["why"]
        self.assertTrue(why.startswith("if it's the counterpart of Harrow Creek Water Treatment Plant (a; plausible): "
                                       "it gives 37.6 NTU"))
        off = report(self.PLANTS, [], ("a", "b"), mode="proposals")
        self.assertEqual(indexes.built(off)["gaps"], [])  # off: links feed no gaps

    def test_a_plausible_links_values_beside_kept_apart(self):
        data = report(self.PLANTS, [], ("a", "b"), mode="proposals", settings={"linked_values": True})
        index = indexes.built(data)
        page = indexfiles.markdown(index)
        self.assertIn("Possibly the counterpart of Pine Ridge Water Treatment Plant (b; plausible: names, "
                      "properties in common), its values (not merged):\n  - design flow: 16.3 MGD (b.pdf, page 1)",
                      page)
        shown = subjects_html(index["subjects"], index["sources"])
        self.assertIn("its values (not merged):</p><table><tbody><tr><td>design flow</td>", shown)
        self.assertEqual(len(index["subjects"]), 2)  # not merged

class Properties(unittest.TestCase):
    """Milestone 8: a property possibly given under another name (property_links; off)."""
    def test_names_values_and_the_judge_two_families_plausible_another_unit_kind_rules_out(self):
        a = [claim("A-1", "ca", "plant", "design flow (average day)", "25.9", "MGD")]
        b = [claim("B-1", "cb", "plant", "average day flow", "16.3", "MGD"), claim("B-2", "cb", "plant", "flow", "3",
                                                                                 "Hz")]
        data = report(a + b, [], ("a", "b"), mode="proposals")
        keys, judged = links.property_evidence(data)
        self.assertEqual(links.property_alike(["design flow (average day)"], ["A-1"], ["average day flow"], ["B-1"],
                                              keys, judged), ("plausible", ["name", "values"]))
        self.assertEqual(links.property_alike(["design flow (average day)"], ["A-1"], ["flow"], ["B-2"], keys,
                                              judged), (None, []))  # a frequency isn't a flow
        data = report(a + b, [{"a": "A-1", "b": "B-2", "relation": "different"}], ("a", "b"), mode="proposals")
        keys, judged = links.property_evidence(data)
        self.assertEqual(links.property_alike(["capacity"], ["A-1"], ["rating"], ["B-1"], keys, judged),
                         ("possible", ["values"]))

    def test_a_gap_given_under_another_name_not_counted(self):
        a = [claim("A-1", "ca", "P-101", "design flow (average day)", "25.9", "MGD"),
             claim("A-2", "ca", "P-101", "head", "40", "ft")]
        b = [claim("B-1", "cb", "P-101", "average day flow", "16.3", "MGD"), claim("B-2", "cb", "P-101", "head", "42",
                                                                                   "ft")]
        gaps = lambda on: [(g["source"], g["property"]) for g in indexes.built(report(  # noqa: E731
            a + b, [], ("a", "b"), mode="proposals", settings={"property_links": on}))["gaps"]]
        self.assertEqual(sorted(gaps(False)), [("a", "average day flow"), ("b", "design flow (average day)")])
        self.assertEqual(gaps(True), [])

class Keyed(unittest.TestCase):
    """Milestone 14: between proposals, a tag both designs give isn't one item where their properties say otherwise
    (keyed_links; off). The gotchas review: "P-101 in two designs is a numbering habit, not identity"."""
    A = [claim("A-1", "ca", "Raw water pump P-101A", "capacity", "6261", "gpm"),
         claim("A-2", "ca", "Raw water pump P-101A", "total dynamic head", "112", "ft"),
         claim("A-3", "ca", "Raw water pump P-101A", "motor power", "287", "hp"),
         claim("A-4", "ca", "Filter F-1", "filtration rate", "3.2", "gpm/ft2"),
         claim("A-5", "ca", "Filter F-1", "area", "836", "ft2")]
    B = [claim("B-1", "cb", "Backwash pump P-101A", "capacity", "3395", "gpm"),
         claim("B-2", "cb", "Backwash pump P-101A", "total dynamic head", "67.9", "ft"),
         claim("B-3", "cb", "Raw water pump P-201A", "capacity", "7739", "gpm"),
         claim("B-4", "cb", "Raw water pump P-201A", "total dynamic head", "137", "ft"),
         claim("B-5", "cb", "Raw water pump P-201A", "motor power", "210", "hp"),
         claim("B-6", "cb", "Filter F-1", "filtration rate", "4.1", "gpm/ft2"),
         claim("B-7", "cb", "Filter F-1", "area", "910", "ft2")]

    def built(self, on, findings=(), mode="proposals", **more):
        return indexes.built(report(self.A + self.B, list(findings), ("a", "b"), mode=mode,
                                    settings={"keyed_links": on, "link_tests": True}, **more))

    @staticmethod
    def firm(index):
        return sorted(s["name"] for s in index["subjects"] if len(s["claims"]) == 2)

    def test_a_tag_both_give_another_fitting_better_a_plausible_link_not_one(self):
        self.assertEqual(self.firm(self.built(False)), ["Filter F-1", "Raw water pump P-101A"])
        on = self.built(True)
        self.assertEqual(self.firm(on), ["Filter F-1"])  # P-101A shares 3 properties with P-201A, 2 with its tag's
        pump = next(s for s in on["subjects"] if s["name"] == "Raw water pump P-101A")
        self.assertEqual([(x["other"], x["level"], x["signals"]) for x in pump["links"]],
                         [("Raw water pump P-201A", "plausible", ["name", "properties"]),
                          ("Backwash pump P-101A", "plausible", ["name", "keyed"])])  # the owner: "A plausible link"
        self.assertIn("a tag or name both give", links.link_said(pump["links"][1]))
        self.assertEqual(self.firm(self.built(True, mode="revisions")), ["Filter F-1", "Raw water pump P-101A"])

    def test_the_judge_and_the_model_shown_them_by_their_key_say_nothing_more(self):
        judged = self.built(True, [{"a": "A-1", "b": "B-1", "relation": "different"}])
        self.assertEqual(self.firm(judged), ["Filter F-1"])  # alignment paired them by the tag
        match = {"kind": "match", "source": "a", "subject": "Raw water pump P-101A", "other_source": "b",
                 "other": "Backwash pump P-101A", "relation": "corresponding"}
        self.assertEqual(self.firm(self.built(True, commentary={"entries": [match]})), ["Filter F-1"])

    def test_one_where_nothing_fits_better_by_two_properties(self):
        a = [claim("A-1", "ca", "Chlorine feed", "dose", "2.1", "mg/L"),
             claim("A-2", "ca", "Chlorine feed", "maximum dose", "4.4", "mg/L")]
        b = [claim("B-1", "cb", "Chlorine feed", "dosage", "4.0", "mg/L"),
             claim("B-2", "cb", "Alum feed", "dose", "38", "mg/L")]
        built = lambda more: indexes.built(report(a + b + more, [], ("a", "b"), mode="proposals",  # noqa: E731
                                                  settings={"keyed_links": True}))
        self.assertEqual(self.firm(built([])), ["Chlorine feed"])  # the alum feed's one property alike: too little
        alum = [claim("B-3", "cb", "Alum feed", "maximum dose", "55", "mg/L")]
        self.assertEqual(self.firm(built(alum)), [])  # two: it fits better

    def test_kept_apart_the_models_match_joins_the_counterpart(self):
        match = {"kind": "match", "source": "a", "subject": "Raw water pump P-101A", "other_source": "b",
                 "other": "Raw water pump P-201A", "relation": "corresponding"}
        index = self.built(True, commentary={"entries": [match]})
        joined = next(s for s in index["subjects"] if len(s["claims"]) == 2 and s["name"] != "Filter F-1")
        self.assertEqual((joined["matched_by"], sorted(joined["names"])),
                         ("model: the corresponding element", ["Raw water pump P-101A", "Raw water pump P-201A"]))

class Kinds(unittest.TestCase):
    """Milestone 15: values in units the product's table doesn't know weighed by kind and size (unit_kinds; off). The
    gotchas review: "150 psi and 1,034 kPa never meet"."""
    A = [claim("A-1", "ca", "intake pump", "capacity", "5,151", "gpm"),
         claim("A-2", "ca", "intake pump", "total dynamic head", "96.8", "ft")]
    B = [claim("B-1", "cb", "low-lift pump", "capacity", "325.0", "L/s"),
         claim("B-2", "cb", "low-lift pump", "total dynamic head", "29.5", "m")]

    def built(self, on):
        return indexes.built(report(self.A + self.B, [], ("a", "b"), mode="proposals",
                                    settings={"unit_kinds": on, "link_tests": True}))

    def test_a_metric_design_fits_a_us_one(self):
        link = lambda index: next(x for s in index["subjects"] for x in s.get("links", []))  # noqa: E731
        off = link(self.built(False))
        self.assertEqual((off["level"], off["evidence"].get("misfit")), ("possible", True))  # gpm and L/s apart
        on = link(self.built(True))
        self.assertEqual((on["level"], on["signals"], on["evidence"].get("misfit")),
                         ("plausible", ["name", "properties"], None))

    def test_measured_by_kind_and_size(self):
        from semantic_pdf_diff.schema import Evidence
        gpm, lps, ft = (links.measured(Evidence.model_validate(c), True) for c in (self.A[0], self.B[0], self.A[1]))
        self.assertEqual((gpm[0], lps[0], ft[0]), ("flow", "flow", "length"))
        self.assertAlmostEqual(gpm[1] / lps[1], 1.0, places=3)  # 5,151 gpm is 325.0 L/s
        self.assertAlmostEqual(ft[1], 96.8 * 0.3048, places=6)
        self.assertEqual(links.measured(Evidence.model_validate(self.A[0])), ("gpm", 5151.0))  # off: as written

    def test_property_values_of_one_kind_across_units(self):
        a = [claim("A-1", "ca", "plant", "design flow", "5,151", "gpm")]
        b = [claim("B-1", "cb", "plant", "flow", "325.0", "L/s")]
        for on, expected in ((False, (None, [])), (True, ("plausible", ["name", "values"]))):
            data = report(a + b, [], ("a", "b"), mode="proposals", settings={"unit_kinds": on})
            keys, judged = links.property_evidence(data)
            self.assertEqual(links.property_alike(["design flow"], ["A-1"], ["flow"], ["B-1"], keys, judged),
                             expected)  # off: gpm and L/s another kind each, ruled out

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
