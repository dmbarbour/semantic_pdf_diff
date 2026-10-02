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

    def test_values_compare_in_their_units_and_only_numbers_tags_lengths_and_dates_count(self):
        key = lambda value, unit="": align.value_key(claim("x", "y", value, unit))
        self.assertEqual(key("1.2", "MW"), key("1,200", "kW"))
        self.assertEqual(key("2'-9 1/2\""), ("in", 33.5))
        self.assertEqual(key("2026-04-02"), ("date", "2026-04-02"))
        self.assertEqual(key("D103"), ("id", "D103"))
        self.assertIsNone(key("ROOM 102 ENLARGED, DOOR D103 WIDENED"))
        self.assertIsNone(key("steel"))

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
