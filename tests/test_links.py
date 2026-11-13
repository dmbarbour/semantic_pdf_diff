"""Links: subjects of two sources possibly one, kept apart (links.py; docs/plans/tentative-matches-2026-11-07.md,
milestone 2). The owner, 2026-11-07: "Three levels is a start"; plausible matches "should feed links and topics for
now"; revisions' and proposals' evidence weighed apart ("I'll accept these recommendations.")."""
import stubs  # noqa: F401 (a clean environment)
import json
import unittest
from unittest import mock

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

class Features(unittest.TestCase):
    """Evidence combined numerically, milestone 1: each candidate pair's evidence as numbers beside the rubric's
    booleans, the rubric's levels unchanged."""
    def test_a_pairs_evidence_as_numbers(self):
        judged = [{"a": "A-3", "b": "B-3", "relation": "different", "confidence": 0.8}]
        data = report(A + B, judged, ("a", "b"), mode="proposals")
        index = indexes.built(data)
        names = {i: s["name"] for i, s in enumerate(index["subjects"])}
        found = {(names[c["i"]], names[c["j"]]): c["features"] for c in links.candidates(data, index)}
        plants = found["Harrow Creek Water Treatment Plant", "Pine Ridge Water Treatment Plant"]
        self.assertEqual((plants["properties"], plants["rival"], plants["kinds_differ"], plants["keyed"]),
                         (2, 0, 0, False))
        self.assertEqual(plants["name_share"], round(3 / 7, 3))  # water, treatment, plant of seven words
        self.assertGreater(plants["name_idf"], 0)
        self.assertEqual(plants["value_ratio"], round(25.9 / 16.3, 3))  # the larger of the two flows' ratios
        alum = found["Alum", "ferric sulfate"]
        self.assertEqual((alum["name_share"], alum["verdicts"]), (0.0, [("different", 0.8)]))
        self.assertEqual(alum["value_ratio"], round(38.8 / 18.5, 3))
        self.assertEqual(links_of(data)["Alum", "ferric sulfate"][0], "plausible")  # the levels as before

class Combined(unittest.TestCase):
    """Evidence combined numerically, milestone 3: link_levels "combined", a probability from hand-set weights."""
    @staticmethod
    def pair(**features):
        base = {"name_idf": 0.0, "name_share": 0.0, "spelling": 0.0, "meaning": None, "reranked": None,
                "properties": 0, "rival": 0, "value_ratio": None, "kinds_differ": 0, "values": 0, "keyed": False,
                "model": [], "read": None, "verdicts": [], "grouped": []}
        return {"features": {**base, **features}}

    def test_never_0_nor_1_one_family_alone_under_plausible(self):
        strong = self.pair(spelling=1.0, name_share=1.0, name_idf=3.0, meaning=0.99)
        p, by = links.combined(strong, "proposals")
        self.assertEqual(by["names"], links.FAMILY_CAP)
        self.assertLess(p, links.SHOWN["plausible"])  # names alone, however many points
        key, by = links.combined(self.pair(keyed=True, spelling=1.0, name_share=1.0), "proposals")
        self.assertEqual((by["names"], round(key, 2)), (0, 0.8))  # a key alone (the owner: "only 80%"), the names its
        both = self.pair(spelling=1.0, properties=3, read="picked")
        self.assertGreaterEqual(links.combined(both, "proposals")[0], links.SHOWN["plausible"])
        nothing = self.pair(read="decoy", kinds_differ=2, properties=0, rival=3)
        self.assertGreaterEqual(links.combined(nothing, "proposals")[0], links.CLIP)  # never pinned at 0

    def test_evidence_that_follows_from_other_evidence_counts_less(self):
        siblings = links.contributions(self.pair(properties=2, rival=2, value_ratio=1.1,
                                                 verdicts=[("different", 0.9)]), "proposals")
        alone = links.contributions(self.pair(properties=2, rival=0, value_ratio=1.1,
                                              verdicts=[("different", 0.9)]), "proposals")
        self.assertLess(siblings["judge"][0][1], alone["judge"][0][1])
        keyed = links.contributions(self.pair(keyed=True, read="picked", verdicts=[("different", 0.9)]), "proposals")
        self.assertEqual([w for _, w in keyed["model"] + keyed["judge"]], [0.0, 0.0])  # shown by the key

    def test_links_carry_a_probability_and_each_familys_part(self):
        data = report(A + B, [], ("a", "b"), mode="proposals", settings={"link_levels": "combined"})
        index = indexes.built(data)
        found = [x for s in index["subjects"] for x in s.get("links", [])]
        self.assertTrue(found)
        alum = next(x for x in found if x["other"] == "ferric sulfate")
        said = links.link_said(alum)
        self.assertTrue(said.startswith(f"possibly the counterpart of ferric sulfate (b; {alum['probability']:.2f}: "),
                        said)
        self.assertIn("properties +", said)  # each family's part, signed
        plants = next(s for s in index["subjects"] if len(s["claims"]) == 2)  # milestone 6: joined by evidence
        self.assertEqual((plants["matched_by"], plants["probability"] >= links.MERGE), ("evidence", True))
        for x in found:
            self.assertEqual(x["rubric"], links.COMBINED)
            self.assertTrue(links.CLIP <= x["probability"] <= 1 - links.CLIP)
            self.assertEqual(x["level"], "plausible" if x["probability"] >= links.SHOWN["plausible"] else "possible")
            self.assertTrue(set(x["contributions"]) <= {"names", "model", "properties", "values", "judge",
                                                        "alignment"})

class CombinedProperties(unittest.TestCase):
    """Evidence combined numerically, milestone 4: properties possibly one by weight, and the numbers said."""
    def test_names_values_and_the_judge_by_weight_another_unit_kind_against_not_a_veto(self):
        a = [claim("A-1", "ca", "plant", "design flow (average day)", "25.9", "MGD")]
        b = [claim("B-1", "cb", "plant", "average day flow", "16.3", "MGD"), claim("B-2", "cb", "plant", "flow", "3",
                                                                                 "Hz")]
        keys, judged = links.property_evidence(report(a + b, [], ("a", "b"), mode="proposals"))
        p, by = links.property_combined(["design flow (average day)"], ["A-1"], ["average day flow"], ["B-1"], keys,
                                        judged)
        self.assertEqual(by, {"names": 1.5, "values": 1.0})
        self.assertGreaterEqual(p, links.SHOWN["plausible"])
        p, by = links.property_combined(["design flow (average day)"], ["A-1"], ["flow"], ["B-2"], keys, judged)
        self.assertEqual(by, {"names": 1.5, "values": -2.5})  # a frequency isn't a flow: strongly against
        self.assertLess(p, links.SHOWN["possible"])

    def test_gaps_given_otherwise_by_weight_and_link_gaps_saying_their_number(self):
        a = [claim("A-1", "ca", "P-101", "design flow (average day)", "25.9", "MGD"),
             claim("A-2", "ca", "P-101", "head", "40", "ft")]
        b = [claim("B-1", "cb", "P-101", "average day flow", "16.3", "MGD"), claim("B-2", "cb", "P-101", "head", "42",
                                                                                   "ft")]
        data = report(a + b, [], ("a", "b"), mode="proposals", settings={"property_links": True,
                                                                         "link_levels": "combined"})
        self.assertEqual(indexes.built(data)["gaps"], [])  # each plausibly given under the other's name
        coagulants = A[2:4] + B[2:4] + [claim("B-8", "cb", "ferric sulfate", "storage", "30", "days")]
        data = report(coagulants, [{"a": "A-3", "b": "B-3", "relation": "different"}], ("a", "b"), mode="proposals",
                      settings={"link_gaps": True, "link_levels": "combined"})
        with mock.patch.object(links, "MERGE", 0.9):  # a link, not one group: the merge cut above it
            (gap,) = indexes.built(data)["gaps"]
        self.assertRegex(gap["why"], r"^if it's the counterpart of ferric sulfate \(b; 0\.\d\d\): it gives 30 days")

class FirmByEvidence(unittest.TestCase):
    """Evidence combined numerically, milestone 6: proposals' firm groups by their evidence's probability (link_levels
    "combined"): the owner, "Firm groups aren't like a 100% on a Bayesian that cannot be shifted by evidence"."""
    def test_a_key_joins_with_its_probability_a_reused_tag_doesnt_its_counterpart_joins_by_evidence(self):
        data = report(Keyed.A + Keyed.B, [], ("a", "b"), mode="proposals",
                      settings={"keyed_links": True, "link_tests": True, "link_levels": "combined"})
        groups = {s["name"]: (s["matched_by"], s.get("probability")) for s in indexes.built(data)["subjects"]
                  if len(s["claims"]) == 2}
        self.assertEqual(set(groups), {"Filter F-1", "Raw water pump P-101A"})
        self.assertEqual(groups["Filter F-1"][0], "name")  # a key, uncontested, its properties alike
        self.assertEqual(groups["Raw water pump P-101A"][0], "evidence")  # with P-201A, not the backwash pump
        self.assertTrue(all(links.MERGE <= p < 1 for _, p in groups.values()))  # never pinned at 1

    def test_a_key_with_no_property_in_common_stays_apart(self):
        claims = OtherNames.A + OtherNames.B
        data = report(claims, [], ("a", "b"), mode="proposals", synonyms={"items": [["chlorine", "UV reactors"]]},
                      settings={"keyed_links": True, "link_levels": "combined"})
        index = indexes.built(data)
        self.assertEqual([s["name"] for s in index["subjects"] if len(s["claims"]) == 2], [])
        chlorine = next(s for s in index["subjects"] if s["name"] == "chlorine")
        link = next(x for x in chlorine["links"] if x["other"] == "UV reactors")  # kept apart: a link, the key and
        self.assertEqual(link["contributions"]["key"], round(2.6 - 0.9, 3))  # its want of a property in common said

class Consumers(unittest.TestCase):
    """Evidence combined numerically, milestone 5: each consumer takes a combined link by its probability."""
    def test_a_combined_link_by_its_probability_a_rubrics_by_its_level(self):
        for use in links.USES:
            self.assertTrue(links.trusted({"probability": links.USES[use], "level": "plausible"}, use))
            self.assertFalse(links.trusted({"probability": links.USES[use] - 0.01, "level": "plausible"}, use))
            self.assertTrue(links.trusted({"level": "plausible"}, use))
            self.assertFalse(links.trusted({"level": "possible"}, use))

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

    def test_a_read_shown_its_subjects_captions(self):
        # milestone 10, step 6 (read_context): a table's caption and the lead-in introducing it, from its claims'
        # records ("Raw water pumps"; the administration building's air handling units' lead-in)
        from semantic_pdf_diff import crossmatch
        from semantic_pdf_diff.records import caption
        table = {"kind": "table", "items": ["Tag", "Capacity (gpm)"],
                 "text": "Above the table: ...The plant's pumps are listed as follows. Table 1. Raw water pumps Tag "
                         "Capacity (gpm) P-101 1,300"}
        self.assertEqual(caption(table), ("Raw water pumps", "The plant's pumps are listed as follows."))
        self.assertEqual(caption({**table, "text": "Table 2. Options Tag"})[1], "")  # nothing introduces it
        judged = [{"a": "A-10", "b": "B-10", "relation": "different"}]
        pumps = [dict(c, records=["table:p1:0"]) if c["content"] == "ca" else c for c in self.PUMPS]
        records = [{"content": "ca", "id": "table:p1:0", **table}]
        for on in (False, True):
            data = report(pumps, judged, ("a", "b"), mode="proposals", records=records, settings={"read_context": on})
            text = crossmatch.links_asked(data, indexes.built(data))[0][-1]
            self.assertEqual('"described as": [\n   "Raw water pumps"' in text, on)

class Weighed(unittest.TestCase):
    """Milestone 6: a link's level from its features' weights (link_levels: weights; proposals only), the table taken
    as fitted on today's candidates (link_weights.json's own, weights/1, is stale: test_a_stale_table)."""
    def setUp(self):
        links.weights()  # read, then stamped as today's for these tests
        stamp = mock.patch.dict(links._WEIGHTS, {"candidates": links.CANDIDATES})
        stamp.start()
        self.addCleanup(stamp.stop)

    def test_a_stale_table_leaves_the_rubric_deciding(self):
        # evidence combined numerically, milestone 0: weights/1 was fitted on candidates/1, and nothing checked it
        data = report(A + B, [], ("a", "b"), mode="proposals", settings={"link_levels": "weights"})
        with mock.patch.dict(links._WEIGHTS, {"candidates": "candidates/1"}), \
                mock.patch.object(links, "_STALE", []), self.assertLogs("semantic_pdf_diff", "WARNING") as logged:
            found = [x for s in indexes.built(data)["subjects"] for x in s.get("links", [])]
            self.assertIsNone(links.weights())
        self.assertTrue(found and all(x["rubric"] == links.RUBRIC and "score" not in x for x in found))
        self.assertIn("fitted on candidates/1", logged.output[0])

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
        self.assertIn("a tag, name or other name both give", links.link_said(pump["links"][1]))
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

class OtherNames(unittest.TestCase):
    """Milestone 16: between proposals, subjects joined by other names alone one only where they share a property, and
    the model's groups not chaining one document's names (other_names_fit; off). The gotchas review: other names chain
    and ignore disagreement."""
    A = [claim("A-1", "ca", "Option B: chlorine contact", "capital cost", "2.82", "$M"),
         claim("A-2", "ca", "Option B: chlorine contact", "contact time", "49", "min"),
         claim("A-3", "ca", "chlorine", "dosage", "3.3", "mg/L")]
    B = [claim("B-1", "cb", "sodium hypochlorite", "dosage", "2.1", "mg/L"),
         claim("B-2", "cb", "UV reactors", "capital cost", "6.35", "$M"),
         claim("B-3", "cb", "UV reactors", "annual energy use", "771", "MWh/yr")]

    def built(self, on, groups):
        return indexes.built(report(self.A + self.B, [], ("a", "b"), mode="proposals", synonyms={"items": groups},
                                    settings={"keyed_links": True, "other_names_fit": on}))

    def test_a_chain_through_the_other_documents_name_joins_nothing(self):
        chained = [["Option B: chlorine contact", "sodium hypochlorite"], ["chlorine", "sodium hypochlorite"]]
        off = next(s for s in self.built(False, chained)["subjects"] if len(s["claims"]) == 2)
        self.assertEqual(off["names"], ["Option B: chlorine contact", "chlorine", "sodium hypochlorite"])
        on = self.built(True, chained)
        self.assertEqual([s["name"] for s in on["subjects"] if len(s["claims"]) == 2], [])
        option = next(s for s in on["subjects"] if s["name"] == "Option B: chlorine contact")
        self.assertEqual([(x["other"], x["level"], x["signals"]) for x in option["links"]],
                         [("sodium hypochlorite", "plausible", ["keyed"])])  # no property shared: a link

    def test_other_names_sharing_a_property_one(self):
        on = self.built(True, [["chlorine", "sodium hypochlorite"]])
        self.assertEqual([(s["name"], s["matched_by"]) for s in on["subjects"] if len(s["claims"]) == 2],
                         [("chlorine", "other names")])

class Series(unittest.TestCase):
    """Between proposals, units of two series (a bank's pumps, tagged P-101A to C and IP-1 to 3) aren't paired by their
    numbering: not by the model's groups, nor its match, nor the judge's pairings, nor the tags' spelling (the owner,
    2026-11-12: "If it's just three fungible pumps coordinating in a shared role, then how would it make sense to match
    them one to one?")."""
    def pumps(self, tags):
        return [claim(f"{s}-{k}{n}", f"c{s}", f"{name} {tag}", attribute, value, unit)
                for s, name, tags_ in (("a", "Raw water pump", tags[0]), ("b", "Intake pump", tags[1]))
                for n, tag in enumerate(tags_)
                for k, (attribute, value, unit) in enumerate((("capacity", f"{5000 + 100 * n}", "gpm"),
                                                             ("total dynamic head", "96", "ft")))]

    def built(self, tags, matches=()):
        groups = [[f"Raw water pump {x}", f"Intake pump {y}"] for x, y in zip(*tags)]
        entries = [{"kind": "match", "source": "a", "subject": f"Raw water pump {x}", "other_source": "b",
                    "other": f"Intake pump {y}", "relation": "corresponding", "taken": True} for x, y in matches]
        data = report(self.pumps(tags), [], ("a", "b"), mode="proposals", synonyms={"items": groups},
                      commentary={"entries": entries},
                      settings={"keyed_links": True, "other_names_fit": True, "link_levels": "combined"})
        data["index"] = indexes.built(data)
        return data

    def test_a_series_is_told_apart_by_its_tags_alone(self):
        from semantic_pdf_diff.align import series
        named = {("a", "Raw water pump P-101A"), ("a", "P-101B"), ("a", "P-102 sump pump"), ("b", "IP-1")}
        self.assertEqual(series(named), {("a", "Raw water pump P-101A"): "P-101A", ("a", "P-101B"): "P-101B"})

    def test_the_models_groups_and_match_pair_no_units_of_two_series(self):
        tags = (("P-101A", "P-101B", "P-101C"), ("IP-1", "IP-2", "IP-3"))
        data = self.built(tags, matches=[("P-101A", "IP-1")])
        self.assertEqual([s["name"] for s in data["index"]["subjects"] if len(s["claims"]) == 2], [])
        subjects = data["index"]["subjects"]
        by = {(subjects[c["i"]]["name"], subjects[c["j"]]["name"]): c for c in links.candidates(data, data["index"])}
        picked = by["Intake pump IP-1", "Raw water pump P-101A"]
        self.assertTrue(picked["features"]["series"])
        self.assertEqual(links.contributions(picked, "proposals")["model"],
                         [("the model's match (corresponding), units of two series", 0.0)])
        self.assertLess(links.combined(picked, "proposals")[0], links.SHOWN["possible"])

    def test_two_banks_are_linked_as_sets(self):
        from semantic_pdf_diff import indexfiles
        from semantic_pdf_diff.report import subjects_html
        tags = (("P-101A", "P-101B", "P-101C"), ("IP-1", "IP-2", "IP-3"))
        data = self.built(tags)
        found = data["index"]["sets"]
        self.assertEqual([sorted(x["sources"][s]["members"] for s in x["sources"]) for x in found],
                         [[["Intake pump IP-1", "Intake pump IP-2", "Intake pump IP-3"],
                           ["Raw water pump P-101A", "Raw water pump P-101B", "Raw water pump P-101C"]]])
        self.assertGreaterEqual(found[0]["probability"], links.SHOWN["possible"])
        self.assertEqual([(p["name"], p["a"], p["b"]) for p in found[0]["properties"]],
                         [("capacity", "5000 to 5200 gpm", "5000 to 5200 gpm"),
                          ("total dynamic head", "96 ft", "96 ft")])
        md = indexfiles.markdown(data["index"])
        self.assertIn("## Sets", md)
        self.assertIn("One of a bank, possibly the counterpart as a set of Intake pump IP-1, Intake pump IP-2, "
                      "Intake pump IP-3 (b; ", md)
        self.assertIn("one of a bank, possibly the counterpart as a set of",
                      subjects_html(data["index"]["subjects"], ["a", "b"]))

    def test_a_numbering_scheme_of_other_roles_is_no_bank(self):
        claims = [claim(f"a-{n}", "ca", f"{role} pump P-101{x}", "capacity", f"{3000 + n}", "gpm")
                  for n, (role, x) in enumerate((("Backwash", "A"), ("Sludge", "B"), ("Washwater recycle", "C")))]
        claims += [claim(f"b-{n}", "cb", f"Raw water pump P-201{x}", "capacity", f"{5000 + n}", "gpm")
                   for n, x in enumerate("ABC")]
        data = report(claims, [], ("a", "b"), mode="proposals", settings={"link_levels": "combined"})
        index = indexes.built(data)
        self.assertEqual([(src, len(members)) for src, members in links.banks(index)], [("b", 3)])
        self.assertNotIn("sets", index)

    def test_one_unit_each_still_joined_by_the_models_groups(self):
        data = self.built((("P-101",), ("IP-1",)))
        self.assertEqual([(s["name"], s["matched_by"]) for s in data["index"]["subjects"] if len(s["claims"]) == 2],
                         [("Raw water pump P-101", "other names")])

class Generic(unittest.TestCase):
    """Between proposals, a name of a document's parts alone ("sheet", "detail", "grid line") is no key, and those words
    aren't a name's evidence (the first link panel on real pairs, 2026-11-12: two Solar Decathlon houses' drawings
    joined "sheet" with "sheet" at 0.96, two different sheets)."""
    def built(self, a_name, b_name):
        claims = [claim("A-1", "ca", a_name, "scale", "1/4 in = 1 ft", ""),
                  claim("A-2", "ca", a_name, "date", "2013", ""),
                  claim("B-1", "cb", b_name, "scale", "3/8 in = 1 ft", ""),
                  claim("B-2", "cb", b_name, "date", "2012", "")]
        data = report(claims, [], ("a", "b"), mode="proposals",
                      settings={"keyed_links": True, "other_names_fit": True, "link_levels": "combined"})
        data["index"] = indexes.built(data)
        return data

    def test_a_document_part_alone_is_no_key(self):
        from semantic_pdf_diff.align import generic
        self.assertEqual([generic(n) for n in ("sheet", "Grid line", "the detail", "component F", "Section A",
                                               "project")], [True, True, True, False, False, False])
        joined = lambda data: [s["matched_by"] for s in data["index"]["subjects"] if len(s["claims"]) == 2]  # noqa
        self.assertEqual(joined(self.built("detail", "detail")), [])
        self.assertEqual(joined(self.built("project", "project")), ["name"])

    def test_a_document_part_numbered_is_a_placeholder(self):
        # the link panel on mechanical drawings (2026-11-13): a grid bubble "component 6" and a schedule's row
        # "unspecified component 6" joined at 0.82 by their number; revisions of two houses' drawings by theirs
        from semantic_pdf_diff.align import placeholder
        names = ("component 6", "unspecified component 6", "revision 2", "Sheet M-101", "M-101", "HEAT PUMP HP-1",
                 "Room 104")
        self.assertEqual([placeholder(n) for n in names],
                         [True, True, True, True, False, False, False])
        joined = lambda data: [s["matched_by"] for s in data["index"]["subjects"] if len(s["claims"]) == 2]  # noqa
        self.assertEqual(joined(self.built("revision 1", "revision 1")), [])  # nor their number in common
        first, merges = [], links.merges  # the first pass's candidates, as the merge weighs them
        with mock.patch.object(links, "merges", lambda d, i: first.append(links.candidates(d, i)) or merges(d, i)):
            self.built("component 6", "unspecified component 6")
        pair = first[0][0]
        self.assertTrue(pair["features"]["placeholders"])
        said = links.contributions(pair, "proposals")["names"]
        self.assertFalse([w for name, w in said if name.startswith("spelled alike") and w > 0])  # the number's

    def test_a_document_parts_words_spell_nothing(self):
        data = self.built("Grid line", "Grid Line 4")
        subjects = data["index"]["subjects"]
        pair = next(c for c in links.candidates(data, data["index"]))
        self.assertEqual(pair["features"]["spelling"], 0.0)
        self.assertNotIn("names", links.contributions(pair, "proposals"))
        self.assertEqual(sorted(s["name"] for s in subjects), ["Grid Line 4", "Grid line"])

class Several(unittest.TestCase):
    def test_a_side_naming_several_tagged_items_counts_against_a_pair(self):
        # two houses' drawings: each "sheets" subject holding several sheets' numbers (the first link panel, 2026-11-12)
        claims = [claim("A-1", "ca", "drawing sheets", "sheet number", "S-522", ""),
                  claim("A-2", "ca", "drawing sheets", "sheet number", "S-601", ""),
                  claim("A-3", "ca", "drawing sheets", "drawn by", "TEAM A", ""),
                  claim("B-1", "cb", "drawing sheets", "sheet number", "A-301", ""),
                  claim("B-2", "cb", "drawing sheets", "drawn by", "TEAM B", "")]
        data = report(claims, [], ("a", "b"), mode="proposals", settings={"link_levels": "combined"})
        data["index"] = indexes.built(data)
        pair = links.candidates(data, data["index"])
        self.assertEqual([c["features"]["several"] for c in pair], [2])
        self.assertIn(("a side names several items", -1.5), links.contributions(pair[0], "proposals")["names"])

class Media(unittest.TestCase):
    """Milestone 10's function family: the medium a subject handles, from its units (values.MEDIA). Spruce Lake's
    administration building filters pass air (cfm/ft²), the plant's filters water (gpm/ft²): one kind of unit, flow
    per area, two media."""
    def candidate(self, a_claims, b_claims):
        data = report(a_claims + b_claims, [], ("a", "b"), mode="proposals", settings={"link_levels": "combined"})
        data["index"] = indexes.built(data)
        return next(c for c in links.candidates(data, data["index"]))

    def test_media_differing_count_against_a_pair(self):
        from semantic_pdf_diff.values import medium
        self.assertEqual([medium(u) for u in ("gpm/ft²", "CFM", "MGD", "psi", "")],
                         ["liquid", "air", "liquid", None, None])
        c = self.candidate([claim("A-1", "ca", "filters", "filtration rate", "346", "cfm/ft²")],
                           [claim("B-1", "cb", "filters", "filtration rate", "4.2", "gpm/ft²")])
        self.assertEqual((c["features"]["media"], c["features"]["mixed"]), ([["air"], ["liquid"]], False))
        self.assertIn(("handles another medium", -2.0), links.contributions(c, "proposals")[links.FUNCTION])

    def test_a_property_given_in_two_media_is_two_things(self):
        c = self.candidate([claim("A-1", "ca", "Filters", "filtration rate", "486", "cfm/ft²"),
                            claim("A-2", "ca", "Filters", "filtration rate", "2.8", "gpm/ft²")],
                           [claim("B-1", "cb", "filtration", "filtration rate", "4.2", "gpm/ft²")])
        self.assertTrue(c["features"]["mixed"])
        self.assertEqual(links.contributions(c, "proposals")[links.FUNCTION],
                         [("a side gives a property in two media", -2.0)])  # the media share water: no other point

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
