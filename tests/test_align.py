"""Alignment for revisions mode (align.py; docs/plans/revision-comparison-2026-10-02.md): which items correspond is
decided before any value is judged, so the judge sees changes, not look-alikes."""
import stubs  # noqa: F401 (a clean environment)
import unittest
from types import SimpleNamespace

from semantic_pdf_diff import align

def claim(entity, attribute, value, unit="", conditions=""):
    return SimpleNamespace(entity=entity, attribute=attribute, value=value, unit=unit, conditions=conditions,
                           approximate=False)

def pairs(found, left, right, which="judge"):
    """A correspondence's pairs as readable (entity, attribute, value) couples."""
    show = lambda c: (c.entity, c.attribute, c.value)
    return {(show(left[i]), show(right[j])) for i, j, _ in getattr(found, which)}

class Alignment(unittest.TestCase):
    def test_a_name_by_position_follows_its_values(self):
        # The image reader names rows by position; a pump inserted above moves every blower down a row, so
        # "blower 5" is B-402 in the earlier revision and B-401 in the later.
        left = [claim("B-402", "power", "57", "hp"), claim("B-402", "speed", "3,552", "rpm"),
                claim("B-402", "pressure", "8.95", "psig"),
                claim("blower 5", "power", "57", "hp"), claim("blower 5", "speed", "3,552", "rpm"),
                claim("blower 5", "pressure", "8.95", "psig"),
                claim("B-401", "power", "49", "hp"), claim("B-401", "speed", "3,153", "rpm")]
        right = [claim("B-402", "power", "57", "hp"), claim("B-402", "speed", "3,552", "rpm"),
                 claim("B-402", "pressure", "10.22", "psig"),
                 claim("blower 6", "power", "57", "hp"), claim("blower 6", "speed", "3,552", "rpm"),
                 claim("blower 6", "pressure", "10.22", "psig"),
                 claim("B-401", "power", "49", "hp"), claim("B-401", "speed", "3,153", "rpm"),
                 claim("blower 5", "power", "49", "hp"), claim("blower 5", "speed", "3,153", "rpm")]
        found = align.align(left, right)
        judged = pairs(found, left, right)
        self.assertTrue(judged)
        self.assertTrue(all(a[1] == b[1] == "pressure" for a, b in judged))  # only the changed pressure is judged
        compared = judged | pairs(found, left, right, "settled")
        self.assertFalse({(a, b) for a, b in compared if a[2] in ("57", "3,552") and b[2] in ("49", "3,153")})
        self.assertEqual(found.unaligned, ([], []))

    def test_two_of_a_kind_are_never_one_item_changed(self):
        left = [claim("Option 1, chilled beams", "peak cooling load", "818", "tons"),
                claim("Option 1, chilled beams", "first cost", "20.8", "$M"),
                claim("Option 2, VAV baseline", "peak cooling load", "1,067", "tons"),
                claim("Option 2, VAV baseline", "first cost", "9.4", "$M")]
        right = [claim("Option 1, chilled beams", "peak cooling load", "818", "tons"),
                 claim("Option 1, chilled beams", "first cost", "21.3", "$M"),
                 claim("Option 2, VAV baseline", "peak cooling load", "1,067", "tons"),
                 claim("Option 2, VAV baseline", "first cost", "9.4", "$M")]
        found = align.align(left, right)
        self.assertEqual(pairs(found, left, right), {(("Option 1, chilled beams", "first cost", "20.8"),
                                                       ("Option 1, chilled beams", "first cost", "21.3"))})
        self.assertEqual(len(found.settled), 3)

    def test_an_item_only_in_one_revision_is_added_or_removed_and_not_compared(self):
        left = [claim("Lift hill", "height", "178", "ft"), claim("Station", "platform length", "105", "ft"),
                claim("Camelback", "height", "100", "ft"), claim("Revision C", "date", "2026-03-14")]
        right = [claim("Lift hill", "height", "178", "ft"), claim("Helix", "height", "110", "ft"),
                 claim("Camelback", "height", "100", "ft"), claim("Revision C", "date", "2026-03-14"),
                 claim("Revision D", "date", "2026-04-02")]
        found = align.align(left, right)
        self.assertEqual(found.judge, [])
        self.assertEqual(([left[i].entity for i in found.unaligned[0]], [right[j].entity for j in found.unaligned[1]]),
                         (["Station"], ["Helix", "Revision D"]))

    def test_a_near_tie_goes_to_the_judge_and_nothing_is_settled(self):
        # one valve's two values, each found under another item later (a split?): neither home leads
        left = [claim("valve", "flow coefficient", "450"), claim("valve", "stroke time", "12.5", "s")]
        right = [claim("valve A", "flow coefficient", "450"), claim("valve B", "stroke time", "12.5", "s")]
        found = align.align(left, right)
        self.assertEqual(found.settled, [])
        self.assertEqual(len(found.judge), 2)
        self.assertEqual(found.summary["ambiguous_items"], [1, 2])

    def test_a_value_kept_under_other_conditions_is_judged_not_settled(self):
        left = [claim("Filters", "filtration rate", "4.1", "gpm/ft²", "with one filter out of service"),
                claim("Filters", "area per filter", "404", "ft²")]
        right = [claim("Filters", "filtration rate", "4.1", "gpm/ft²", "with all filters in service"),
                 claim("Filters", "area per filter", "404", "ft²")]
        found = align.align(left, right)
        self.assertEqual(pairs(found, left, right), {(("Filters", "filtration rate", "4.1"),
                                                       ("Filters", "filtration rate", "4.1"))})
        self.assertEqual(len(found.settled), 1)

    def test_a_condition_named_in_the_attribute_is_judged_not_settled(self):
        left = [claim("raw water", "95th percentile turbidity", "37.6", "NTU", "measured over five years"),
                claim("raw water", "peak flow", "42.2", "MGD")]
        right = [claim("raw water", "99th percentile turbidity", "37.6", "NTU", "measured over five years"),
                 claim("raw water", "peak flow", "42.2", "MGD")]
        found = align.align(left, right)
        self.assertEqual(pairs(found, left, right), {(("raw water", "95th percentile turbidity", "37.6"),
                                                       ("raw water", "99th percentile turbidity", "37.6"))})

    def test_a_condition_moved_between_attribute_and_conditions_is_still_seen(self):
        left = [claim("raw water", "turbidity", "37.6", "NTU", "95th percentile, measured over five years")]
        right = [claim("raw water", "99th percentile turbidity", "37.6", "NTU", "measured over five years")]
        found = align.align(left, right)
        self.assertEqual((found.settled, len(found.judge)), ([], 1))

    def test_the_new_value_is_judged_beside_a_superseded_one(self):
        # the later revision says "raised from 178 ft to 230 ft": the old height read twice, the new once
        left = [claim("lift hill", "height", "178", "ft"), claim("lift hill", "drop", "237", "ft")]
        right = [claim("lift hill", "height", "230", "ft", "revision B"), claim("lift hill", "drop", "237", "ft"),
                 claim("lift hill", "height", "178", "ft", "revision A (implied by 'raised from')")]
        found = align.align(left, right)
        self.assertIn((("lift hill", "height", "178"), ("lift hill", "height", "230")), pairs(found, left, right))

    def test_a_count_by_any_name_pairs_by_its_value(self):
        left = [claim("Ridgeback roller coaster", "number of inversions", "5"), claim("Ridgeback roller coaster",
                                                                                     "track length", "6,694", "ft")]
        right = [claim("Ridgeback", "inversion count", "5"), claim("Ridgeback", "track length", "6,694", "ft")]
        found = align.align(left, right)
        self.assertEqual((len(found.settled), found.judge), (2, []))

    def test_a_fact_filed_under_another_entity_still_pairs_by_its_value(self):
        left = [claim("first drop", "peak g", "2.3", "g"), claim("first drop", "maximum vertical acceleration", "3.8", "g"),
                claim("Ridgeback", "track length", "6,694", "ft")]
        right = [claim("First drop", "peak g", "2.3", "g"), claim("Ridgeback", "track length", "6,694", "ft"),
                 claim("Ridgeback", "maximum vertical acceleration", "3.8", "g")]
        found = align.align(left, right)
        self.assertIn((("first drop", "maximum vertical acceleration", "3.8"),
                       ("Ridgeback", "maximum vertical acceleration", "3.8")), pairs(found, left, right))

    def test_a_renamed_item_is_matched_by_its_values_and_listed(self):
        left = [claim("P-101B", "capacity", "5,590", "gpm"), claim("P-101B", "head", "64.9", "ft"),
                claim("P-101A", "capacity", "5,151", "gpm")]
        right = [claim("P-201B", "capacity", "5,590", "gpm"), claim("P-201B", "head", "64.9", "ft"),
                 claim("P-101A", "capacity", "5,151", "gpm")]
        found = align.align(left, right)
        self.assertEqual((len(found.settled), found.judge), (3, []))
        self.assertEqual(found.summary["renamed_items"], [["P-101B", "P-201B"]])

    def test_readers_phrasing_conditions_differently_doesnt_stop_a_settlement(self):
        left = [claim("D112", "width", "6'-0\"", conditions="Door Schedule"),
                claim("D112", "width", "6'-0\"", conditions="face of finish")]
        right = [claim("D112", "width", "6'-0\"", conditions="face of finish"),
                 claim("D112", "width", "6'-0\"", conditions="Room: MECHANICAL 112")]
        found = align.align(left, right)
        self.assertEqual(found.judge, [])
        self.assertEqual({i for i, _, _ in found.settled}, {0, 1})  # every reading settled, one pair each
        self.assertEqual({j for _, j, _ in found.settled}, {0, 1})

    def test_a_generic_attribute_pairs_by_value_only(self):
        # "dimension 1" names no property: its value finds its reading (the depth, unchanged); only the width, named
        # in both revisions, is judged
        left = [claim("MEETING 102", "dimension 1", "24'-0\""), claim("MEETING 102", "width", "30'-6\"")]
        right = [claim("MEETING 102", "dimension 1", "32'-6\""), claim("MEETING 102", "depth", "24'-0\""),
                 claim("MEETING 102", "width", "32'-6\"")]
        found = align.align(left, right)
        self.assertEqual(pairs(found, left, right), {(("MEETING 102", "width", "30'-6\""),
                                                       ("MEETING 102", "width", "32'-6\""))})
        self.assertEqual(pairs(found, left, right, "settled"), {(("MEETING 102", "dimension 1", "24'-0\""),
                                                                 ("MEETING 102", "depth", "24'-0\""))})

    def test_a_split_and_a_merge_are_candidates_with_their_evidence(self):
        left = [claim("P-101A", "capacity", "5,151", "gpm"), claim("P-101A", "head", "96.8", "ft"),
                claim("P-101C", "capacity", "7,650", "gpm"), claim("P-101C", "head", "62.1", "ft"),
                claim("V-310", "Cv", "450"), claim("V-311", "Cv", "300")]
        right = [claim("P-101A", "capacity", "5,151", "gpm"), claim("P-101A", "head", "96.8", "ft"),
                 claim("P-101E", "capacity", "4,102", "gpm"), claim("P-101E", "head", "63.4", "ft"),
                 claim("P-101F", "capacity", "3,548", "gpm"), claim("P-101F", "head", "60.9", "ft"),
                 claim("V-31", "Cv", "750")]
        found = align.align(left, right)
        kinds = {g["kind"]: g for g in found.groups}
        split = kinds["split candidate"]
        self.assertEqual((split["earlier"], split["later"]), (["P-101C"], ["P-101E", "P-101F"]))
        self.assertEqual(split["evidence"]["sums"], [{"attribute": "capacity", "whole": "7,650", "parts": ["4,102", "3,548"]}])
        self.assertEqual(kinds["matched"]["earlier"], ["P-101A"])
        self.assertEqual(found.judge, [])  # candidates are shown, not compared claim by claim
        self.assertEqual((found.regrouped[0], found.regrouped[1]), ([2, 3], [2, 3, 4, 5]))
        # two valves become one: V-310 and V-311 share a stem with V-31 only if their tags say so; here they don't,
        # so they're unaligned, each on its side
        self.assertEqual(sorted(g["kind"] for g in found.groups if g["kind"] == "unaligned"), ["unaligned"] * 3)
        merged = align.align([claim("Room 104A", "area", "1,200", "ft²"), claim("Room 104B", "area", "800", "ft²")],
                             [claim("Room 104", "area", "2,000", "ft²")])
        merge = next(g for g in merged.groups if g["kind"] == "merge candidate")
        self.assertEqual((merge["earlier"], merge["later"], len(merge["evidence"]["sums"])),
                         (["Room 104A", "Room 104B"], ["Room 104"], 1))

    def test_values_compare_in_their_units_and_words_as_words(self):
        key = lambda value, unit="": align.value_key(claim("x", "y", value, unit))
        self.assertEqual(key("1.2", "MW"), key("1,200", "kW"))
        self.assertEqual(key("2'-9 1/2\""), ("in", 33.5))
        self.assertEqual(key("2026-04-02"), ("date", "2026-04-02"))
        self.assertEqual(key("D103"), ("id", "D103"))
        # words are a value too, their case, spacing and punctuation folded; a number inside them is part of them
        self.assertEqual(key("ROOM 102 ENLARGED, DOOR D103 WIDENED"), ("text", "room 102 enlarged door d103 widened"))
        self.assertEqual(key("MUST  close the connection."), key("must close the connection"))
        self.assertNotEqual(key("0..160"), key("0..2040"))  # ranges are words, not their first number
        self.assertEqual(key("63.3 mph"), key("63.3", "mph"))  # the unit written in the value
        # a bound, a tolerance and a currency are part of the value (code review 2026-10-08, D1); "about" isn't
        self.assertNotEqual(key("≤ 5", "NTU"), key("≥ 5", "NTU"))
        self.assertNotEqual(key("<5"), key(">5"))
        self.assertEqual(key("<=5"), key("≤ 5"))
        self.assertNotEqual(key("±0.5", "mm"), key("0.5", "mm"))
        self.assertNotEqual(key("$5"), key("5"))
        self.assertEqual(key("about 5", "m"), key("5", "m"))
        self.assertEqual(key("5", "m"), ("length", 5.0))  # unqualified keys are as before
        # every length in inches, however written (code review 2026-10-08, D11 and E19)
        for written in [('33.5"',), ("33.5", "in"), ("33.5 in",), ("2'-9 1/2\"",), ("2'-9½\"",), ("33½ in",)]:
            self.assertEqual(key(*written), ("in", 33.5), written)

class Report(unittest.TestCase):
    def test_unchanged_files_change_no_status_or_grouping(self):
        """Revisions with an unchanged file are aligned in two passes; a claim's outcome comes from every pass it was
        in (code review 2026-10-08, D2: a later claim pass 1 aligned was "possibly added or removed" because pass 2
        found no counterpart among the unchanged file's claims, and groupings contradicted each other)."""
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).parent))
        from test_pipeline import Fake, ev
        from semantic_pdf_diff.compare import compare
        earlier = [ev("X-1", entity="P-1", attribute="capacity", value="100", unit="gpm"),
                   ev("X-2", entity="P-1", attribute="head", value="50", unit="ft"),
                   ev("X-3", entity="M-7", attribute="power", value="10", unit="kW")]
        unchanged = [ev("U-1", entity="F-1", attribute="flow", value="2000", unit="cfm"),
                     ev("U-2", entity="F-1", attribute="power", value="3", unit="kW")]
        later = [ev("Y-1", entity="P-1", attribute="capacity", value="120", unit="gpm"),
                 ev("Y-2", entity="P-1", attribute="head", value="50", unit="ft"),
                 ev("Y-3", entity="P-1", attribute="NPSH required", value="12", unit="ft"),
                 ev("Y-4", entity="V-9", attribute="size", value="4", unit="in")]
        alone = compare(earlier, later, Path("."), Fake(relation="different"), "revisions")
        both = compare(earlier + unchanged, later + unchanged, Path("."), Fake(relation="different"), "revisions")
        statuses = lambda r: {u["id"]: u["status"] for u in r["unmatched"]}
        self.assertEqual(statuses(alone), {"X-3": "unaligned", "Y-3": "not_compared", "Y-4": "unaligned"})
        self.assertEqual(statuses(both), statuses(alone))
        shape = lambda r: [(g["kind"], g["earlier_claims"], g["later_claims"]) for g in r["groupings"]]
        self.assertEqual(shape(both), shape(alone))
        self.assertEqual([(f["a"], f["b"]) for f in both["findings"]], [(f["a"], f["b"]) for f in alone["findings"]])
        self.assertEqual([x["pass"] for x in both["retrieval"]["alignment"]],
                         ["earlier own against later own and shared", "shared against later own"])

    def test_the_report_shows_the_groupings_and_marks_regrouped_claims(self):
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).parent))
        from test_pipeline import Fake, ev
        from semantic_pdf_diff.compare import compare
        from semantic_pdf_diff.report import groupings_html
        left = [ev("A-1", entity="P-101A", attribute="capacity", value="5151", unit="gpm"),
                ev("A-2", entity="P-101C", attribute="capacity", value="7650", unit="gpm")]
        right = [ev("B-1", entity="P-101A", attribute="capacity", value="5151", unit="gpm"),
                 ev("B-2", entity="P-101E", attribute="capacity", value="4102", unit="gpm"),
                 ev("B-3", entity="P-101F", attribute="capacity", value="3548", unit="gpm")]
        result = compare(left, right, Path("."), Fake(relation="different"), "revisions")
        kinds = sorted(g["kind"] for g in result["groupings"])
        self.assertEqual(kinds, ["matched", "split candidate"])
        self.assertEqual({u["id"]: u["status"] for u in result["unmatched"]},
                         {"A-2": "regrouped", "B-2": "regrouped", "B-3": "regrouped"})
        matched = next(g for g in result["groupings"] if g["kind"] == "matched")
        self.assertEqual(matched["outcome"]["settled"], 1)
        self.assertIn("split candidate", groupings_html(result["groupings"], str))
        self.assertEqual(compare(left, right, Path("."), Fake(relation="different"), "proposals")["groupings"], [])

class Lever(unittest.TestCase):
    def test_revisions_align_and_proposals_keep_retrieval(self):
        from semantic_pdf_diff.models import Settings
        left = [claim("Pump P-1", "capacity", "100", "gpm"), claim("Pump P-2", "capacity", "200", "gpm")]
        right = [claim("Pump P-1", "capacity", "100", "gpm"), claim("Pump P-2", "capacity", "250", "gpm")]
        s = Settings()
        revisions = s.correspondence(left, right, "revisions")
        self.assertEqual((len(revisions.settled), len(revisions.judge)), (1, 1))
        proposals = s.correspondence(left, right, "proposals")
        self.assertEqual(proposals.settled, [])
        self.assertEqual(proposals.judge, s.candidates(left, right))
        self.assertEqual(Settings(align=False).correspondence(left, right, "revisions").judge, s.candidates(left, right))

if __name__ == "__main__":
    unittest.main()
