"""A report's indexes (indexes.py) and their files (indexfiles.py): docs/plans/indexes-and-glossaries-2026-10-29.md,
milestone 1. The owner, 2026-10-29: "building indexes and glossaries, e.g. of claims, diagrams, subjects", and of
the files: "An excel file is also a good representation for indices.\""""
import stubs  # noqa: F401 (a clean environment)
import csv
import io
import json
import tempfile
import unittest
from pathlib import Path

from semantic_pdf_diff import indexes, indexfiles, report as reports
from semantic_pdf_diff.align import TAG
from semantic_pdf_diff.schema import Evidence, PdfLocator
from semantic_pdf_diff.report import unpacked
from stubs import serving
from test_analyze import asked, drawn, plant, run

def claim(cid, content, entity, attribute, value, unit, page=1):
    return Evidence(id=cid, content=content, locator=PdfLocator(page=page, bbox=(0, 0, 1, 1), region="text", task="t"),
                    entity=entity, attribute=attribute, value=value, unit=unit, kind="text", quote=f"{value} {unit}",
                    confidence=.9).model_dump()

def report(evidence, findings=(), sources=("a",), **more):
    files = [{"source": s, "path": f"{s}.pdf", "content": f"c{s}"} for s in sources]
    return {"sources": [{"name": s} for s in sources], "files": files, "evidence": list(evidence),
            "findings": list(findings), **more}

ONE = [claim("A-1", "ca", "P-101 feed pump", "rated power", "10", "kW"),
       claim("A-2", "ca", "P-101", "head", "42", "m", page=3),
       claim("A-3", "ca", "P-102 pump", "rated power", "12", "kW"),
       claim("A-4", "ca", "P-102 pump", "Rated  power", "12.5", "kW", page=9)]

class Reproducible(unittest.TestCase):
    def test_names_alike_but_for_case_ordered_the_same_whatever_the_hash_seed(self):
        # a recorded report's index differed between processes: "Height" and "height" tie on natural's case folding
        # and a set's order, which the hash seed sets, decided; and a kind of tagged items named by its most said
        # word, "track" or "element" tying (2026-11-11)
        import os
        import subprocess
        import sys
        script = """
import json
from semantic_pdf_diff import indexes
from test_indexes import claim, report
claims = [claim("A-1", "ca", "Camelback", "height", "41", "ft"), claim("A-2", "ca", "Camelback", "Height", "42", "ft"),
          claim("A-3", "ca", "Camelback", "fall height", "40", "ft")]
claims += [claim(f"T-{k}", "ca", f"E{k} track element", "height", str(10 + k), "ft") for k in range(1, 4)]
index = indexes.built(report(claims))
print(json.dumps([index["subjects"], index["kinds"]], sort_keys=True))
"""
        here = os.path.dirname(os.path.abspath(__file__))
        seen = {subprocess.run([sys.executable, "-c", script], cwd=here, capture_output=True, text=True, check=True,
                               env={**os.environ, "PYTHONHASHSEED": str(seed)}).stdout for seed in range(8)}
        self.assertEqual(len(seen), 1)

class Subjects(unittest.TestCase):
    def test_a_sources_claims_by_subject_and_property(self):
        index = indexes.built(report(ONE))
        # named as its claims most often name it (the first, of equals)
        self.assertEqual([s["name"] for s in index["subjects"]], ["P-101 feed pump", "P-102 pump"])
        p101, p102 = index["subjects"]
        self.assertEqual(p101["names"], ["P-101", "P-101 feed pump"])
        self.assertEqual([p["name"] for p in p101["properties"]], ["head", "rated power"])
        self.assertEqual(p101["properties"][0]["values"], [{"source": "a", "value": "42", "unit": "m", "conditions": "",
                                                           "claim": "A-2", "where": "a.pdf, page 3"}])
        self.assertEqual([(p["name"], [v["value"] for v in p["values"]]) for p in p102["properties"]],
                         [("rated power", ["12", "12.5"])])  # its wordings one property
        self.assertEqual(indexes.properties(index)[1]["name"], "rated power")
        self.assertEqual([x["subject"] for x in indexes.properties(index)[1]["subjects"]],
                         ["P-101 feed pump", "P-102 pump"])

    def test_a_comparisons_subjects_merged_by_its_findings_else_by_name(self):
        b = [claim("B-1", "cb", "feed pump P-101", "rated power", "11", "kW"),
             claim("B-2", "cb", "fan", "air flow", "3", "m3/s"),
             claim("B-3", "cb", "P-103", "head", "50", "m")]
        a = ONE + [claim("A-5", "ca", "fan", "air flow", "2", "m3/s")]
        index = indexes.built(report(a + b, [{"a": "A-1", "b": "B-1", "relation": "different"}], ("a", "b")))
        by = {s["name"]: s for s in index["subjects"]}
        self.assertEqual(list(by), ["fan", "P-101 feed pump", "P-102 pump", "P-103"])  # A to Z, numbers as numbers
        self.assertEqual((by["P-101 feed pump"]["matched_by"], by["P-101 feed pump"]["claims"]),
                         ("findings", {"a": ["A-1", "A-2"], "b": ["B-1"]}))
        self.assertEqual((by["fan"]["matched_by"], by["fan"]["claims"]), ("name", {"a": ["A-5"], "b": ["B-2"]}))
        self.assertEqual((by["P-103"]["matched_by"], by["P-103"]["claims"]), ("", {"b": ["B-3"]}))
        page = indexfiles.markdown(index)
        self.assertIn("# Index: a ↔ b", page)
        self.assertIn("### P-101 feed pump (also feed pump P-101, P-101)\nClaims: a 2; b 1 (matched by findings)", page)
        self.assertIn("- **head**: a: 42 m (a.pdf, page 3); b: —", page)
        self.assertIn("- **rated power**: a: 10 kW (a.pdf, page 1); b: 11 kW (b.pdf, page 1)", page)

    def test_a_subjects_properties_one_where_findings_pair_them(self):
        """The coaster pair, 2026-10-29: the car's "seating capacity" and "rider capacity", each blank on the other
        side, though a finding paired their claims."""
        a = [claim("A-1", "ca", "car", "seating capacity", "4", "riders")]
        b = [claim("B-1", "cb", "car", "rider capacity", "4", "")]
        index = indexes.built(report(a + b, [{"a": "A-1", "b": "B-1", "relation": "equivalent"}], ("a", "b")))
        (car,) = index["subjects"]
        self.assertEqual([(p["name"], p["names"], [v["claim"] for v in p["values"]]) for p in car["properties"]],
                         [("seating capacity", ["rider capacity", "seating capacity"], ["A-1", "B-1"])])
        self.assertIn("- **seating capacity** (also rider capacity): a: 4 riders (a.pdf, page 1); b: 4 (b.pdf, page 1)",
                      indexfiles.markdown(index))
        apart = indexes.built(report(a + b, [{"a": "A-1", "b": "B-1", "relation": "unrelated"}], ("a", "b")))
        self.assertEqual(len(apart["subjects"][0]["properties"]), 2)  # unrelated: not one property

    def test_proposals_subjects_matched_by_name_or_the_model_not_by_findings_alone(self):
        """The turbine pair (single-document analysis, milestone 7; the owner, answering its design's question D,
        2026-11-07: "All four recommendations look good as a start."): uncertain verdicts linked one turbine's tower
        to a mode of the other's, leaving the other's own tower alone."""
        a = [claim("A-1", "ca", "tower", "height", "87.6", "m"), claim("A-2", "ca", "tower", "mass", "347", "t"),
             claim("A-3", "ca", "NREL 5-MW baseline turbine", "rated power", "5", "MW")]
        b = [claim("B-1", "cb", "first torsional mode", "frequency", "0.8", "Hz"),
             claim("B-2", "cb", "Tower", "height", "144", "m"),
             claim("B-3", "cb", "IEA Wind 15-MW reference turbine", "rated power", "15", "MW")]
        found = [{"a": "A-1", "b": "B-1", "relation": "uncertain"}, {"a": "A-2", "b": "B-1", "relation": "uncertain"}]

        def matched(mode, *entries):
            index = indexes.built(report(a + b, found, ("a", "b"), mode=mode, commentary={"entries": list(entries)}))
            return sorted((s["name"], s["matched_by"], sorted(s["claims"])) for s in index["subjects"])
        self.assertEqual(matched("revisions"), [("IEA Wind 15-MW reference turbine", "", ["b"]),
                                                ("NREL 5-MW baseline turbine", "", ["a"]), ("Tower", "", ["b"]),
                                                ("tower", "findings", ["a", "b"])])  # alignment's items, followed
        self.assertEqual(matched("proposals"), [("IEA Wind 15-MW reference turbine", "", ["b"]),
                                                ("NREL 5-MW baseline turbine", "", ["a"]),
                                                ("first torsional mode", "", ["b"]), ("tower", "name", ["a", "b"])])
        turbines = {"kind": "match", "source": "a", "subject": "NREL 5-MW baseline turbine", "other_source": "b",
                    "other": "IEA Wind 15-MW reference turbine", "relation": "corresponding"}
        self.assertIn(("NREL 5-MW baseline turbine", "model: the corresponding element", ["a", "b"]),
                      matched("proposals", turbines))
        self.assertEqual(len(matched("proposals", {**turbines, "relation": "state"})), 4)  # a state stays apart

    def test_what_another_source_gives_a_matched_subject_a_gap_its_kind_given_elsewhere_first(self):
        """The owner's clearest gap (2026-10-28): "Project A tells you a bunch about Bob including his favorite food,
        while Project B tells you about Bob but did not mention his favorite food"."""
        a = [claim("A-1", "ca", "P-101", "flow", "5", "L/s"), claim("A-2", "ca", "P-101", "head", "40", "m"),
             claim("A-3", "ca", "P-102", "flow", "6", "L/s"), claim("A-4", "ca", "P-102", "NPSH", "3", "m"),
             claim("A-5", "ca", "tower", "height", "87.6", "m"), claim("A-6", "ca", "tower", "mass", "347", "t")]
        b = [claim("B-1", "cb", "P-101", "flow", "5.5", "L/s"), claim("B-2", "cb", "P-101", "NPSH", "2.9", "m", page=4),
             claim("B-3", "cb", "Tower", "height", "144", "m"), claim("B-4", "cb", "Tower", "diameter", "10", "m"),
             claim("B-5", "cb", "P-102", "flow", "6", "L/s")]
        index = indexes.built(report(a + b, [], ("a", "b"), mode="proposals"))
        gaps = [(g["source"], g["subject"], g["property"], g["where"], g["why"], g["claims"]) for g in index["gaps"]
                if g["kind"] == "other_source"]
        self.assertEqual(gaps, [
            ("a", "P-101", "NPSH", "a.pdf, page 1", "b gives 2.9 m (b.pdf, page 4)", ["B-2"]),  # a gives P-102's
            ("a", "tower", "diameter", "a.pdf, page 1", "b gives 10 m (b.pdf, page 1)", ["B-4"]),
            ("b", "P-101", "head", "b.pdf, page 1", "a gives 40 m (a.pdf, page 1)", ["A-2"]),
            ("b", "tower", "mass", "b.pdf, page 1", "a gives 347 t (a.pdf, page 1)", ["A-6"])])  # P-102: b's one claim
        self.assertNotIn("siblings_give", index["gaps"][0])
        page = indexfiles.markdown(index)
        self.assertIn("### Another source gives it\n\n- a: **P-101: NPSH** (a.pdf, page 1; b gives 2.9 m (b.pdf, page "
                      "4))", page)

    def test_kinds_of_items_tagged_and_numbered(self):
        """The owner, 2026-10-30, of items or kinds: "I think we should have indices for both, where feasible.\""""
        evidence = ONE + [claim("A-5", "ca", "P-103 feed pump", "rated power", "9", "kW"),
                          claim("A-6", "ca", "P-103 feed pump", "NPSH required", "3", "m"),
                          claim("A-7", "ca", "Room 104", "area", "12", "m2"),
                          claim("A-8", "ca", "Room 105", "area", "14", "m2"),
                          claim("A-9", "ca", "rotor", "diameter", "120", "m")]
        index = indexes.built(report(evidence))
        found = {k["kind"]: k for k in index["kinds"]}
        self.assertEqual(list(found), ["pump (P)", "Room"])  # A to Z; the rotor is of no kind
        pumps = found["pump (P)"]
        self.assertEqual([index["subjects"][i]["name"] for i in pumps["subjects"]],
                         ["P-101 feed pump", "P-102 pump", "P-103 feed pump"])
        self.assertEqual([(p["name"], p["given"]) for p in pumps["properties"]],
                         [("rated power", 3), ("head", 1), ("NPSH required", 1)])
        page = indexfiles.markdown(index)
        self.assertIn("### pump (P): 3 items\n\n| Item | rated power | head | NPSH required |\n|---|---|---|---|\n"
                      "| P-101 feed pump | 10 kW | 42 m | — |\n| P-102 pump | 12 kW; 12.5 kW | — | — |\n"
                      "| P-103 feed pump | 9 kW | — | 3 m |", page)
        self.assertIn("Given by: rated power 3 of 3; head 1 of 3; NPSH required 1 of 3", page)

    def test_kinds_grouped_by_what_their_items_are(self):
        """Milestone 3, 2026-11-01 (the owner: "Let's try your recommendations on the decisions."): a set's sheets one
        kind by the shape its title blocks print their numbers in; a property named two ways one where its items give
        both alike; a claim naming several items counted for none, a subject whose claims all do left out and
        marked."""
        situation = {"ca": {"figures": [{"id": "f1", "page": 1, "kind": "sheet", "label": "sheet G-001"},
                                        {"id": "f2", "page": 2, "kind": "sheet", "label": "sheet XA-501"}]}}
        rows = [("A-101", "FLOOR PLAN"), ("Sheet E-102", "LIGHTING PLAN"), ("XB-001", "COVER"),
                ("M-301", "SECTIONS")]
        evidence = [claim(f"S-{n}", "ca", name, "sheet name", title, "") for n, (name, title) in enumerate(rows)]
        evidence += [claim(f"T-{n}", "ca", name, "drawing title", title + " AND DETAILS" * (n == 1), "")
                     for n, (name, title) in enumerate(rows[:3])]
        evidence += [claim("X-1", "ca", "XB-101", "drawing title", "ROOF PLAN", ""),
                     claim("X-2", "ca", "XA04", "description", "3/4 bolt", ""),
                     claim("X-3", "ca", "XA05", "description", "louvre", ""),
                     claim("X-4", "ca", "A-401 A-402", "sheet name", "ELEVATIONS", ""),  # rows read as one
                     claim("X-5", "ca", "XB-001 XB-002", "drawing title", "COVER", ""),
                     claim("X-6", "ca", "pump P-101", "flow", "10", "l/s")]
        index = indexes.built(report(evidence, situation=situation))
        found = {k["kind"]: k for k in index["kinds"]}
        self.assertEqual(list(found), ["sheet", "XA-"])  # the components keep their tag's kind
        sheets = found["sheet"]
        self.assertEqual(sorted(index["subjects"][i]["name"] for i in sheets["subjects"]),
                         ["A-101", "M-301", "Sheet E-102", "XB-001", "XB-101"])
        self.assertEqual(sheets["properties"], [{"name": "drawing title", "names": ["drawing title", "sheet name"],
                                                 "given": 5}])  # 4 items each: the first A to Z
        self.assertEqual([g for g in index["gaps"] if g["kind"] == "siblings"], [])  # each gives its title
        several = next(s for s in index["subjects"] if s["name"] == "A-401 A-402")
        self.assertEqual(several["several"], ["A-401", "A-402"])
        self.assertNotIn(index["subjects"].index(several), sheets["subjects"])
        xb = next(s for s in index["subjects"] if s["name"] == "XB-001")  # its claim naming two counted for none
        self.assertEqual([v.get("several", []) for p in xb["properties"] for v in p["values"]],
                         [[], ["XB-001", "XB-002"], []])
        page = indexfiles.markdown(index)
        self.assertIn("### A-401 A-402\nNames several items (A-401, A-402): rows read as one, or a statement about "
                      "several; its kind counts it for none.", page)
        self.assertIn("### sheet: 5 items\n\n| Item | drawing title (also sheet name) |", page)
        self.assertIn("| XB-001 | COVER; COVER |", page)  # its own claims, not the row naming two
        self.assertIn("- **drawing title**: COVER (a.pdf, page 1); COVER [of XB-001, XB-002] (a.pdf, page 1)", page)

        apart = indexes.built(report(evidence))  # no sheets situated: the tags' letters, as before
        self.assertNotIn("sheet", {k["kind"] for k in apart["kinds"]})

    def test_one_things_name_holding_two_tags_names_one_item(self):
        """Rows read as one name items of one shape; a list, items apart by commas, "and" or "or"; but TS 38.300's
        "L2 U2N Relay UE" is one thing (477 of its claims had been counted for none, 2026-11-02)."""
        rows, lists = ["A-102 A-201", "E-102 E-103 E-601", "H-101 SPILL CONTAINMENT, & SCHEDULE S-001 DRAWING"], [
            "SRB0, SRB1, SRB3 and other MAC CEs", "Pumps P-101 and P-102"]
        for name in rows + lists + ["L2 U2N Relay UE", "L2 U2N Relay UE and L2 U2N Remote UE",
                                    "L1/L2 Triggered Mobility", "PC5 U2U Relay RLC Channel", "pump P-101"]:
            tags = TAG.findall(name)
            self.assertEqual((indexes.several(name), indexes.listing(name)),
                             (tags if name in rows else [], tags if name in lists else []), name)

    def test_a_lists_claims_count_for_each_item_it_names(self):
        """Design question 6's follow-up (the owner, 2026-11-02: "Let's go with your recommendations on the
        low-hanging fruit."): a statement about several holds for each; rows read as one still count for none."""
        evidence = [claim(f"F-{n}", "ca", f"pump P-10{n}", "flow", str(9 + n), "l/s") for n in (1, 2, 3)]
        evidence += [claim("L-1", "ca", "Pumps P-101, P-102 and P-103", "rated power", "75", "kW"),
                     claim("L-2", "ca", "P-102 and P-104", "duty", "standby", "")]
        index = indexes.built(report(evidence))
        by_name = {s["name"]: s for s in index["subjects"]}
        self.assertEqual(sorted(by_name), ["P-104", "pump P-101", "pump P-102", "pump P-103"])
        for name in ("pump P-101", "pump P-102", "pump P-103"):
            power = next(p for p in by_name[name]["properties"] if p["name"] == "rated power")
            self.assertEqual([(v["claim"], v["listed"]) for v in power["values"]],
                             [("L-1", ["P-101", "P-102", "P-103"])])
        self.assertEqual(by_name["P-104"]["claims"], {"a": ["L-2"]})  # an item named only in a list (source a)
        self.assertEqual([g["subject"] for g in index["gaps"] if g["property"] == "rated power"],
                         ["P-104"])  # the list gives the three their power: P-104 alone lacks it
        page = indexfiles.markdown(index)
        self.assertIn("- **rated power**: 75 kW [said of P-101, P-102, P-103] (a.pdf, page 1)", page)

    def test_a_value_cut_short_in_a_word_joins_properties(self):
        """A tile's edge cutting a title ("HARDWIRED EQUIPMENT ELECTRICA"): the same property as the whole title the
        sheet index gives (scical, 2026-11-02)."""
        titles = {1: "HARDWIRED EQUIPMENT ELECTRICAL PLAN", 2: "PV WIRING PLAN", 3: "ONE-LINE DIAGRAM"}
        cut = {1: "HARDWIRED EQUIPMENT ELECTRICA", 2: "PV WIRING PLAN", 3: "ONE-LINE DIAG"}
        evidence = [claim(f"A-{n}", "ca", f"E-10{n}", "sheet name", titles[n], "") for n in titles]
        evidence += [claim(f"B-{n}", "ca", f"E-10{n}", "drawing title", cut[n], "") for n in cut]
        (sheets,) = indexes.built(report(evidence))["kinds"]
        self.assertEqual([p["names"] for p in sheets["properties"]], [["drawing title", "sheet name"]])
        self.assertFalse(indexes._cut("ONE", "ONE-LINE DIAGRAM"))  # a word alone isn't a title cut short

    def test_numbers_alike_dont_join_properties(self):
        evidence = [claim(f"{a}-{n}", "ca", f"P-10{n}", a, "12", "kW") for n in range(1, 4) for a in ("A", "B")]
        evidence = [dict(e, attribute={"A": "rated power", "B": "shaft power"}[e["id"][0]]) for e in evidence]
        (pumps,) = indexes.built(report(evidence))["kinds"]
        self.assertEqual([p["names"] for p in pumps["properties"]], [["rated power"], ["shaft power"]])

    def test_figures_and_tables(self):
        situation = {"ca": {"figures": [{"id": "f1", "page": 4, "kind": "figure", "label": "Figure 2",
                                         "caption": "Pump curve", "about": "The pumps' head against flow.",
                                         "claims": ["A-2"], "references": [{"page": 2}]}]}}
        records = [{"content": "ca", "id": "table:p9:0", "kind": "table", "label": "Table 5. Pumps", "page": 9,
                    "items": ["Tag", "Power"]},
                   {"content": "ca", "id": "note:p1:0", "kind": "note", "label": "NOTES", "page": 1}]
        evidence = [dict(ONE[3], records=["table:p9:0"])] + ONE[:3]
        index = indexes.built(report(evidence, situation=situation, records=records))
        self.assertEqual([(f["label"], f["page"], f["kind"], f["claims"], f["cited"]) for f in index["figures"]],
                         [("Figure 2", 4, "figure", ["A-2"], 1), ("Table 5. Pumps", 9, "table", ["A-4"], 0)])
        self.assertEqual(index["figures"][0]["title"], "Pump curve")
        self.assertIn('- **Figure 2 “Pump curve”** (a.pdf, page 4): The pumps\' head against flow; 1 claim; cited once',
                      indexfiles.markdown(index))

class KindsNamedByTheModel(unittest.TestCase):
    """The confirm_kinds lever (kindcheck.py; the owner, 2026-11-01: "But test the model on Q7 and see how it works
    out."): the rules' kinds shown to the model, which names each and moves the items not of it."""
    class Answering:
        """A client answering every request with one answer, each prompt kept (the dispatcher asks it inline)."""
        def __init__(self, answer):
            self.answer, self.prompts = answer, []

        def ask(self, prompt, schema, images=(), key=None):
            self.prompts.append(prompt)
            return schema.model_validate(self.answer(prompt) if callable(self.answer) else self.answer)

    def test_kinds_renamed_merged_and_items_moved(self):
        from semantic_pdf_diff import kindcheck
        situation = {"ca": {"figures": [{"id": "f1", "page": 1, "kind": "sheet", "label": "sheet G-001"}]}}
        sheets = [("A-101", "FLOOR PLAN"), ("M-301", "SECTIONS"), ("E-102", "LIGHTING")]
        evidence = [claim(f"S-{n}", "ca", name, "sheet name", title, "") for n, (name, title) in enumerate(sheets)]
        evidence += [claim(f"P-{n}", "ca", f"P-30{n}", "flow", str(10 + n), "l/s") for n in (1, 2)]  # pumps, by tag
        evidence += [claim("X-1", "ca", "XA04", "description", "3/4 bolt", ""),
                     claim("X-2", "ca", "XA05", "description", "louvre", "")]
        data = report(evidence, situation=situation)
        index = indexes.built(data)
        self.assertEqual([(k["kind"], len(k["subjects"])) for k in index["kinds"]], [("sheet", 5), ("XA-", 2)])
        shown, kinds, items = kindcheck.dossier(index)
        self.assertEqual(shown["kinds"][0]["items"][3], {"id": "K1.4", "item": "P-301", "gives": {"flow": "11 l/s"}})
        pumps = [i for i, name in items.items() if name.startswith("P-")]

        def answer(prompt):
            return {"kinds": [{"id": "K1", "name": "drawing sheet",
                               "not_of_it": [{"item": i, "kind": "pump"} for i in pumps]
                               + [{"item": "K2.1", "kind": "bolt"}]},  # another kind's item: dropped
                              {"id": "K2", "name": "hardware component"}, {"id": "K9", "name": "pump"}]}
        client = self.Answering(answer)
        data["kind_check"] = kindcheck.confirmed(data, index, client, "analysis", "label")
        self.assertIn('"item": "P-301"', client.prompts[0])
        self.assertEqual(data["kind_check"], {"kinds": [{"rule": "sheet", "name": "drawing sheet",
                                                         "moved": {"P-301": "pump", "P-302": "pump"}},
                                                        {"rule": "XA-", "name": "hardware component"}],
                                              "asked": 1, "failed": 0, "dropped": 2})
        named = indexes.built(data)
        self.assertEqual([(k["kind"], sorted(named["subjects"][i]["name"] for i in k["subjects"]))
                          for k in named["kinds"]],
                         [("drawing sheet", ["A-101", "E-102", "M-301"]), ("hardware component", ["XA04", "XA05"]),
                          ("pump", ["P-301", "P-302"])])
        alike = self.Answering({"kinds": [{"id": "K1", "name": "Component"}, {"id": "K2", "name": "component"}]})
        data["kind_check"] = kindcheck.confirmed(data, index, alike, "analysis", "label")
        self.assertEqual([(k["kind"], len(k["subjects"])) for k in indexes.built(data)["kinds"]],
                         [("Component", 7)])  # named alike: one

class Glossary(unittest.TestCase):
    def test_terms_merged_across_sources_and_marked_where_defined_differently(self):
        def term(t, meaning, source, page=2):
            return {"term": t, "meaning": meaning, "kind": "abbreviation", "source": source, "content": f"c{source}",
                    "where": f"{source}.pdf, page {page}", "block": "ABBREVIATIONS", "how": "model"}
        found = {"terms": [term("TYP", "typical", "a"), term("TYP.", "Typical", "b"), term("FF", "far face", "a"),
                           term("FF", "finished floor", "b"), term("UNO", "unless noted otherwise", "b")]}
        index = indexes.built(report([], sources=("a", "b"), glossary=found))
        self.assertEqual([(t["term"], len(t["meanings"]), t.get("differs", False)) for t in index["glossary"]],
                         [("FF", 2, True), ("TYP", 2, False), ("UNO", 1, False)])
        page = indexfiles.markdown(index)
        self.assertIn("- **FF** (abbreviation): a: far face (a.pdf, page 2); b: finished floor (b.pdf, page 2) — "
                      "defined differently", page)
        self.assertIn("- **UNO** (abbreviation): a: —; b: unless noted otherwise (b.pdf, page 2)", page)
        header, rows = indexfiles.tables(index, {})["glossary"]
        self.assertEqual(rows[0], ["FF", "abbreviation", "far face", "a", "a.pdf, page 2", "document", "ABBREVIATIONS",
                                   "model", "yes", ""])
        from semantic_pdf_diff.report import search_names
        self.assertIn(["UNO", "unless noted otherwise"], search_names({"glossary": found})["glossary"])

class OtherNames(unittest.TestCase):
    """Milestone 3: the names one thing goes by join its subjects, match them across sources and join properties."""
    @staticmethod
    def term(t, meaning, source="a"):
        return {"term": t, "meaning": meaning, "kind": "abbreviation", "source": source, "content": f"c{source}",
                "where": f"{source}.pdf, page 2", "block": "ABBREVIATIONS", "how": "model", "reach": "document"}

    def test_a_sources_subjects_named_as_one_things_names_joined(self):
        evidence = [claim("A-1", "ca", "AHU", "airflow", "3", "m3/s"),
                    claim("A-2", "ca", "air handling unit", "rated power", "5", "kW"),
                    claim("A-3", "ca", "air handling unit", "NPSH", "2", "m"),
                    claim("A-4", "ca", "air handling unit", "net positive suction head", "2.1", "m")]
        glossary = {"terms": [self.term("AHU", "air handling unit"), self.term("NPSH", "net positive suction head")]}
        (ahu,) = indexes.built(report(evidence, glossary=glossary))["subjects"]
        self.assertEqual(sorted(ahu["names"]), ["AHU", "air handling unit"])
        self.assertEqual([(p["name"], len(p["values"])) for p in ahu["properties"]],
                         [("airflow", 1), ("NPSH", 2), ("rated power", 1)])  # NPSH, its meaning: one property

    def test_subjects_matched_across_sources_by_other_names(self):
        evidence = [claim("A-1", "ca", "fan coil unit", "airflow", "3", "m3/s"),
                    claim("B-1", "cb", "FCU", "airflow", "4", "m3/s"),
                    claim("A-2", "ca", "feed pump", "head", "40", "m"),
                    claim("B-2", "cb", "boiler feed pump", "head", "42", "m")]
        data = report(evidence, sources=("a", "b"), glossary={"terms": [self.term("FCU", "fan coil unit", "b")]},
                      synonyms={"items": [["feed pump", "boiler feed pump"]], "properties": []})
        by = {s["name"]: s for s in indexes.built(data)["subjects"]}
        self.assertEqual((by["fan coil unit"]["matched_by"], by["fan coil unit"]["claims"]),
                         ("other names", {"a": ["A-1"], "b": ["B-1"]}))
        self.assertEqual(by["feed pump"]["claims"], {"a": ["A-2"], "b": ["B-2"]})
        self.assertEqual(len(by), 2)

    def test_the_models_other_names_join_properties_that_can_be_one(self):
        """Planted reports: the model gave "Pressure", "Maximum transient pressure" and "Minimum transient pressure" as
        other names of one property, and the index joined the maximum and the minimum."""
        evidence = [claim("A-1", "ca", "force main", "maximum transient pressure", "174", "psi"),
                    claim("A-2", "ca", "force main", "minimum transient pressure", "2.9", "psi"),
                    claim("A-3", "ca", "force main", "SIZE W", "8", "in"),
                    claim("A-4", "ca", "force main", "size width", "8", "in"),
                    claim("A-5", "ca", "force main", "rated output", "40", "hp"),
                    claim("A-6", "ca", "force main", "nominal power", "40", "hp")]
        data = report(evidence, synonyms={"items": [], "properties": [
            ["Pressure", "maximum transient pressure", "minimum transient pressure"], ["SIZE W", "size width"],
            ["rated output", "nominal power"]]})
        (main,) = indexes.built(data)["subjects"]
        self.assertEqual(sorted(sorted(p["names"]) for p in main["properties"]),
                         [["SIZE W", "size width"], ["maximum transient pressure"], ["minimum transient pressure"],
                          ["nominal power", "rated output"]])
        self.assertFalse(indexes.kin("DRB connection target", "SRB connection target"))
        self.assertFalse(indexes.kin("volume", "working volume"))  # a name and a more general one
        self.assertTrue(indexes.kin("uplink transmit timing", "uplink transmission timing"))
        self.assertTrue(indexes.kin("dimension", "dimensions"))

    def test_a_sheets_symbol_isnt_a_name(self):
        sym = {**self.term("W", "washer"), "kind": "symbol", "reach": "sheet", "sheet": "sheet E-1"}
        alias = indexes.aliases({"glossary": {"terms": [sym, self.term("[square]", "washer")]}})
        self.assertIsNone(alias("W"))
        self.assertIsNone(alias("washer"))

class Reach(unittest.TestCase):
    """The owner, 2026-10-30: "think on how much provenance or context should be tracked in the glossary, e.g. a
    legend that is `[red square] = Foo` isn't much useful beyond that diagram unless unusually consistent.\""""
    def test_a_sheets_symbols_reach_that_sheet_unless_alike_on_others(self):
        def sym(term, meaning, page, sheet):
            return {"term": term, "meaning": meaning, "kind": "symbol", "source": "set", "content": "cset",
                    "where": f"set.pdf, page {page}", "block": "LEGEND", "how": "picture", "reach": "sheet",
                    "sheet": sheet}
        found = {"terms": [sym("[red square]", "FOO", 3, "sheet E-201"),
                           sym("[circle with M]", "MOTOR", 4, "sheet E-202"),
                           sym("[circle with M]", "MOTOR", 5, "sheet E-203"),
                           sym("W", "WASHER RECEPTACLE", 4, "sheet E-202"),
                           {"term": "TYP", "meaning": "typical", "kind": "convention", "source": "set",
                            "content": "cset", "where": "set.pdf, page 2", "block": "ABBREVIATIONS", "how": "model",
                            "reach": "document"}]}
        index = indexes.built(report([], sources=("set",), glossary=found))
        by = {t["term"]: t for t in index["glossary"]}
        self.assertEqual((by["[red square]"]["reach"], by["[red square]"].get("consistent")), ("sheet", None))
        self.assertEqual(by["[circle with M]"]["consistent"], 2)
        self.assertEqual(by["TYP"]["reach"], "document")
        page = indexfiles.markdown(index)
        self.assertIn("- **[red square]** (symbol): FOO (set.pdf, page 3) — sheet E-201 only", page)
        self.assertIn("— alike on 2 sheets", page)
        from semantic_pdf_diff.report import search_names
        named = search_names({"glossary": found})["glossary"]
        self.assertEqual(named, [["TYP", "typical"]])  # not a sheet's letter, nor a mark described

    def test_a_disciplines_list_holds_on_its_sheets(self):
        def entry(meaning, source, reach="discipline", where="set.pdf, page 23"):
            return {"term": "EF", "meaning": meaning, "kind": "abbreviation", "source": source, "content": "c" + source,
                    "where": where, "block": "ABBREVIATIONS", "how": "model", "reach": reach,
                    **({"discipline": "S", "sheet": "sheet S-001"} if reach == "discipline" else {})}
        one = {"terms": [entry("EACH FACE", "a")]}
        index = indexes.built(report([], sources=("a",), glossary=one))
        (ef,) = index["glossary"]
        self.assertEqual((ef["reach"], indexes.reach_said(ef)), ("discipline", "S sheets only"))
        self.assertIn("EACH FACE (set.pdf, page 23; S sheets)", indexfiles.markdown(index))
        self.assertEqual(indexes.aliases({"glossary": one})("EF"), indexes.aliases({"glossary": one})("each face"))
        # a discipline's and the document's meanings in one source differ by design; two sources' S sheets don't agree
        mixed = {"terms": [entry("EACH FACE", "a"), entry("EXHAUST FAN", "a", "document", "set.pdf, page 2")]}
        self.assertNotIn("differs", indexes.built(report([], sources=("a",), glossary=mixed))["glossary"][0])
        two = {"terms": [entry("EACH FACE", "a"), entry("END FRAME", "b")]}
        self.assertTrue(indexes.built(report([], sources=("a", "b"), glossary=two))["glossary"][0]["differs"])

class Gaps(unittest.TestCase):
    """What a source doesn't give, found by code (single-document analysis, milestone 5): weak, each with where it was
    expected and why."""
    def test_a_sibling_lacking_what_most_give_a_reference_not_found_and_a_placeholder(self):
        pumps = [claim(f"A-{n}{k}", "ca", f"P-10{n} pump", attribute, value, unit, page=n)
                 for n in (1, 2, 3) for k, (attribute, value, unit) in enumerate([("rated power", f"1{n}", "kW"),
                                                                                  ("head", f"4{n}", "m")])]
        pumps.append(claim("A-9", "ca", "P-104 pump", "rated power", "TBD", "", page=4))  # no head: 3 of 4 give it
        data = report(pumps, situation={"ca": {"unresolved": [{"page": 2, "label": "Table 5", "evidence": [],
                                                                "text": "as given in Table 5"}]}})
        index = indexes.built(data)
        said = [(g["kind"], g["subject"], g["property"], g["where"]) for g in index["gaps"]]
        self.assertEqual(said, [("siblings", "P-104 pump", "head", "a.pdf, page 4"),
                                ("reference", "Table 5", "", "a.pdf, page 2"),
                                ("placeholder", "P-104 pump", "rated power", "a.pdf, page 4")])
        self.assertEqual(index["gaps"][0]["why"],
                         "3 of its 4 pump (P) items give it: P-101 pump, P-102 pump, P-103 pump")
        page = indexfiles.markdown(index)
        self.assertIn("## What it doesn't give", page)
        self.assertIn("- **Table 5** (a.pdf, page 2; cited, not found in the document: “as given in Table 5”)", page)
        self.assertEqual(indexfiles.tables(index, {e["id"]: e for e in pumps})["gaps"][0],
                         ["Gap", "Source", "Subject", "Property", "Where", "Why", "Looked for", "Claims"])
        # looked for where it would be (dossiers.looks): what was found there beside the gap
        data["commentary"] = {"entries": [{"kind": "looked", "source": "a", "subject": "P-104 pump", "claims": [],
                                           "relation": "not_given", "text": "Head", "where": "a.pdf, page 4"}]}
        index = indexes.built(data)
        self.assertEqual(index["gaps"][0]["looked"], "a.pdf, page 4: not given")
        self.assertIn("4 pump (P) items give it: P-101 pump, P-102 pump, P-103 pump); looked for on a.pdf, page 4: not "
                      "given", indexfiles.markdown(index))
        self.assertEqual(indexfiles.tables(index, {e["id"]: e for e in pumps})["gaps"][1][0][6],
                         "a.pdf, page 4: not given")
        self.assertNotIn("looked", index["gaps"][2])  # a placeholder isn't looked for

    def test_gaps_looked_for_the_readers_misses_first_those_with_no_place_last(self):
        pumps = [claim(f"A-{n}{k}", "ca", f"P-10{n} pump", attribute, value, unit, page=n)
                 for n in (1, 2, 3, 4, 5) for k, (attribute, value, unit) in enumerate([("rated power", f"1{n}", "kW"),
                                                                                        ("head", f"4{n}", "m")])
                 if n < 4 or attribute != "head"]
        looked = lambda subject, relation, **more: {"kind": "looked", "source": "a", "subject": subject,  # noqa: E731
                                                    "claims": [], "relation": relation, "text": "head",
                                                    "where": "a.pdf, page 4", **more}
        data = report(pumps, commentary={"entries": [looked("P-104 pump", "no_place"),
                                                     looked("P-105 pump", "given", value="45 m")]})
        gaps = indexes.built(data)["gaps"]
        self.assertEqual([(g["subject"], g["look"], g["looked"]) for g in gaps],
                         [("P-105 pump", "given", "a.pdf, page 4: it gives 45 m"),
                          ("P-104 pump", "no_place", "a.pdf, page 4: no place for it there")])

    def test_a_tables_cell_left_blank_where_most_rows_fill_its_column(self):
        """A table's cells as read (its record's): a cell left blank in a column most of its rows fill (the owner,
        2026-10-31: "Proceed with items 3, 4 and 5")."""
        cells = [["Tag", "Duty", "Capacity (gpm)", "Notes"], ["Raw water pumps", "", "", ""],
                 ["P-301", "Duty", "1,318", ""], ["P-302", "Duty", "1,898", "VFD"], ["P-303", "Standby", "", ""],
                 ["", "", "1,449", ""]]  # no name: a merged cell's continuation, likely
        data = report([], records=[{"content": "ca", "id": "table:p2:0", "kind": "table", "label": "Pump schedule",
                                    "page": 2, "cells": cells}])
        gaps = [(g["kind"], g["subject"], g["property"], g["where"], g["why"]) for g in indexes.built(data)["gaps"]]
        self.assertEqual(gaps, [("blank", "P-303", "Capacity (gpm)", "a.pdf, page 2, “Pump schedule”",
                                 "left blank in its table: 2 of its 3 rows give it")])  # Notes: 1 of 3 isn't most
        self.assertEqual(indexes.table_place({"content": "ca", "label": "page 2, table 3", "page": 2},
                                             {"path": "a.pdf"}), "a.pdf, page 2, table 3")

    def test_more_than_half_must_give_it_of_three_at_least(self):
        two = [claim("A-1", "ca", "P-101", "head", "40", "m"), claim("A-2", "ca", "P-101", "flow", "5", "L/s"),
               claim("A-3", "ca", "P-102", "flow", "6", "L/s")]
        self.assertEqual(indexes.built(report(two))["gaps"], [])  # two items: no siblings' gap
        half = two + [claim("A-4", "ca", "P-103", "flow", "7", "L/s"), claim("A-5", "ca", "P-104", "flow", "8", "L/s"),
                      claim("A-6", "ca", "P-104", "head", "41", "m")]
        self.assertEqual(indexes.built(report(half))["gaps"], [])  # head 2 of 4: half isn't most

class Files(unittest.TestCase):
    def test_csv_a_row_a_value(self):
        index = indexes.built(report(ONE))
        header, rows = indexfiles.tables(index, {e["id"]: e for e in ONE})["subjects"]
        text = indexfiles.csv_text(header, rows)
        read = list(csv.reader(io.StringIO(text)))
        self.assertEqual(read[0], ["Subject", "Property", "Value", "Unit", "Conditions", "Source", "Where", "Claim"])
        self.assertEqual(read[1], ["P-101 feed pump", "head", "42", "m", "", "a", "a.pdf, page 3", "A-2"])
        self.assertEqual(len(read), 5)

    def test_the_workbook_an_index_its_subjects_collapsing(self):
        import openpyxl
        index = indexes.built(report(ONE))
        evidence = {e["id"]: e for e in ONE}
        data = indexfiles.workbook(index, evidence)
        self.assertEqual(data, indexfiles.workbook(index, evidence))  # the same bytes for the same index
        book = openpyxl.load_workbook(io.BytesIO(data))
        self.assertEqual(book.sheetnames, ["About", "Subjects", "Kinds", "Properties", "Claims", "Figures",
                                           "Glossary", "Gaps"])
        subjects = book["Subjects"]
        self.assertEqual(subjects.freeze_panes, "A2")
        self.assertEqual(subjects.auto_filter.ref, "A1:H7")  # the header, 2 subjects' rows and their 4 values
        rows = [[c.value for c in row] for row in subjects.iter_rows(min_row=2)]
        self.assertEqual(rows[0][:2], ["P-101 feed pump", "2 properties, 2 claims; also P-101"])
        self.assertEqual(rows[1], ["P-101 feed pump", "head", 42, "m", None, "a", "a.pdf, page 3", "A-2"])  # a number
        self.assertEqual([subjects.row_dimensions[n].outlineLevel for n in range(2, 8)], [0, 1, 1, 0, 1, 1])
        self.assertTrue(subjects["A2"].font.b)
        self.assertEqual(book["About"]["B1"].value, "a")
        self.assertEqual(book["Claims"].max_row, 5)

    def test_every_table_is_named_so_one_left_from_an_earlier_report_is_removed(self):
        index = indexes.built(report(ONE))
        index["inconsistencies"] = [{"source": "a", "subject": "P-101", "said": ["42 m", "61 m"], "where": ["", ""],
                                     "read again": ["", ""], "why": "", "claims": ["A-1", "A-2"]}]
        self.assertEqual(set(indexfiles.tables(index, {e["id"]: e for e in ONE})), set(indexfiles.TABLES))
        with tempfile.TemporaryDirectory() as d:
            folder = Path(d)
            indexfiles.written(index, {e["id"]: e for e in ONE}, folder)
            (folder / "index" / "notes.csv").write_text("mine")
            indexfiles.written(indexes.built(report(ONE)), {e["id"]: e for e in ONE}, folder)  # it found none
            files = sorted(p.name for p in (folder / "index").iterdir())
        self.assertNotIn("inconsistencies.csv", files)  # the earlier report's, gone (the owner: "logically fresh")
        self.assertIn("notes.csv", files)  # a file no report writes, kept

    def test_a_unit_of_dash_is_none(self):
        self.assertEqual(indexfiles.said({"value": "1.5", "unit": "-", "conditions": "at -100 deg"}),
                         "1.5 (at -100 deg)")

    def test_tags_and_long_numbers_stay_text(self):
        self.assertIn("<v>1200</v>", indexfiles.cell("A1", "1,200"))
        for text in ("007", "1234567890123456", "12 kW", "P-101"):
            self.assertIn('t="inlineStr"', indexfiles.cell("A1", text), text)

class Searched(unittest.TestCase):
    """The index's views' rows as the page's search reads them (search.js's rows): their claims, and their own
    places, from where they're written."""
    def test_a_rows_places_and_claims(self):
        self.assertEqual(reports.placed("a", "a.pdf, page 2, “Pump schedule”"), ["a / a.pdf", 2, 2])
        self.assertEqual(reports.placed("a", "set.pdf, pages 3–5"), ["a / set.pdf", 3, 5])
        self.assertEqual(reports.placed("", "spec.docx, “Table 4 Timers”"), ["spec.docx", None, None])
        self.assertEqual(reports.placed("b", "Smith, page 9.pdf, page 2", {"Smith, page 9.pdf"}),
                         ["b / Smith, page 9.pdf", 2, 2])  # a name with a comma, its page not the name's
        self.assertEqual(reports.placed("b", "deck.pptx, slide 4"), ["b / deck.pptx", 4, 4])
        self.assertEqual(reports.placed("b", "x.pdf", ["x.pdf"], 7), ["b / x.pdf", 7, 7])  # a figure's own page
        self.assertEqual(reports.searched("P-101 Feed Pump", ["A-1", "A-2", "A-1"], [["a / a.pdf", 2, 2]]),
                         'data-text="p-101 feed pump" data-claims="A-1 A-2" '
                         'data-places="[[&quot;a / a.pdf&quot;,2,2]]"')
        self.assertEqual(reports.searched("CFD"), 'data-text="cfd"')

class Written(unittest.TestCase):
    def test_an_analysis_writes_its_index_beside_its_report(self):
        state = {"embedded": [], "names": 0}
        with tempfile.TemporaryDirectory() as d, serving(asked(state)) as url:
            root = Path(d)
            config = root / "settings.json"
            config.write_text(json.dumps({"search_names": False, "topic_names": False}))
            code, _, _ = run("analyze", plant(root / "plant"), "--store", root / "out", "--base-url", url, "--config",
                             config, "--no-situate")
            out = root / "out"
            data = json.loads((out / "report.json").read_text())
            page = (out / "index.md").read_text()
            files = sorted(p.name for p in (out / "index").iterdir())
            (out / "index.md").unlink()
            again, _, _ = run("report", "--store", out)  # written again with the report
            rewritten = (out / "index.md").read_text()
            book = (out / "index.xlsx").read_bytes()
            shown = unpacked((out / "report.html").read_text())
            searched = drawn((out / "report.html").as_uri() + "#subjects&q=blower")
            # the search's language on the other views too (the owner, 2026-11-06: "the search doesn't work properly
            # for things like `file:` or `page:` as described in the search help")
            by_file = drawn((out / "report.html").as_uri() + "#subjects&q=file%3Amachines")
            not_by_file = drawn((out / "report.html").as_uri() + "#subjects&q=-file%3Amachines%20page%3A1")
            by_value = drawn((out / "report.html").as_uri() + "#subjects&q=%22discharge%20head%22%20%3E21m")
        self.assertEqual((code, again), (0, 0))
        self.assertEqual(len(data["index"]["subjects"]), 15)
        self.assertEqual(files, ["claims.csv", "figures.csv", "gaps.csv", "glossary.csv", "kinds.csv",
                                 "properties.csv", "subjects.csv"])
        self.assertIn("# Index: plant", page)
        self.assertRegex(page, r"### blower0\n\n- \*\*discharge head\*\*: 20 m \(\S*blowers\.md, lines \d+–\d+\)")
        self.assertEqual(page, rewritten)
        self.assertEqual(book[:2], b"PK")
        self.assertIn('<button data-view="subjects">Subjects 15</button>', shown)  # the page's views
        self.assertRegex(shown, r'<div class="subject" data-text="blower0 discharge head" data-claims="ev-[0-9a-f]+">'
                                r'<h3>blower0</h3><table>'
                                r'<thead><tr><th>Property</th><th>Values</th></tr></thead><tbody><tr><td>discharge '
                                r'head</td><td><a href="#claim=[^"]+">20 m</a>')
        if searched is not None:  # a search shows the subjects holding its words
            self.assertIn("5 of 15 subjects", searched)
            self.assertIn("10 of 15 subjects", by_file)  # its claims' files: pumps and fans, not blowers
            self.assertIn("5 of 15 subjects", not_by_file)
            self.assertIn("3 of 15 subjects", by_value)  # its own words, and its claims' values: 22, 23 and 24 m

if __name__ == "__main__":
    unittest.main()
