"""Controlled documents: generated the same way every time, every fact placed, claims classed exactly."""
import stubs  # noqa: F401 (a clean environment)
from stubs import slow
import unittest
from semantic_pdf_diff_lab.bench import controlled

class Generation(unittest.TestCase):
    def test_the_same_seed_gives_the_same_pdf_and_every_fact_is_placed(self):
        for name, make in controlled.PROJECTS.items():
            with self.subTest(project=name):
                project = make(1)
                data, log = controlled.render(project)
                self.assertEqual(controlled.render(make(1))[0], data)  # byte for byte
                self.assertNotEqual(controlled.render(make(2))[0], data)  # another seed, other values
                self.assertTrue(all(f.forms for f in project.facts))  # raises in render otherwise, too
                values = [f.value for f in project.facts]
                self.assertEqual(len(values), len(set(values)))  # a value names one fact
                roles = {p["role"] for p in log}
                self.assertTrue({"fact", "structure"} <= roles)

    def test_facts_are_found_in_prose_and_tables(self):
        project = controlled.water_treatment(1)
        controlled.render(project)
        forms = {x["form"] for f in project.facts for x in f.forms}
        self.assertEqual(forms, {"prose", "table"})
        pump = project.fact("P-101A.capacity")
        self.assertEqual([x["form"] for x in pump.forms], ["table"])

class Knobs(unittest.TestCase):
    def test_prose_traps_and_layouts_place_every_fact(self):
        texts = {}
        for knob in controlled.PROSE_KNOBS:
            project = controlled.convention_center(1)
            project.knob = knob
            data, log = controlled.render(project)
            self.assertTrue(all(f.forms for f in project.facts))
            texts[knob] = data
            if knob in ("furniture", "all"):  # the running header's numbers are logged, as structure
                self.assertIn("LCC-HC-DB-004", [p["text"] for p in log if p["role"] == "structure"])
        self.assertEqual(len(set(texts.values())), len(texts))  # each knob draws a different document

    def test_tables_are_never_split_across_pages_or_columns(self):
        for make, knob, prefix in ((controlled.equipment_schedules, "dense", "V-3"),
                                   (controlled.track_schedules, "dense", "C-"),
                                   (controlled.convention_center, "two-column", "room")):
            project = make(1)
            project.knob = knob
            controlled.render(project)
            pages = {x["page"] for f in project.facts if f.id.startswith(prefix) for x in f.forms}
            self.assertEqual(len(pages), 1, f"{project.id}-{knob}: {prefix} on pages {pages}")

    def test_charts_under_every_knob(self):
        import pymupdf
        # grouped bars (energy), stacked bars and lines (end use): a fact of each, and its chart's step
        for make, fid, step in ((controlled.energy_study, "opt1.july", 50), (controlled.end_use_study, "fans.july", 50),
                                (controlled.end_use_study, "opt2.july", 100)):
            for knob in controlled.CHART_KNOBS:
                project = make(1)
                project.knob = knob
                data, log = controlled.render(project)
                with self.subTest(project=project.id, fact=fid, knob=knob):
                    again = make(1)
                    again.knob = knob
                    self.assertEqual(controlled.render(again)[0], data)  # scans too, byte for byte
                    self.assertTrue(all(f.forms for f in project.facts))
                    fact = project.fact(fid)
                    self.assertEqual({x["form"] for x in fact.forms}, {"chart"})  # placed by the drawer
                    printed = {p["text"] for p in log if fid in p["facts"]}
                    self.assertEqual(printed, set() if knob in ("axis", "all") else {fact.value})  # axis: not printed
                    self.assertEqual(fact.tolerance, step / 4 if knob in ("axis", "all") else 0.0)
                    text = "".join(page.get_text() for page in pymupdf.open("pdf", data))
                    self.assertEqual(text == "", knob in ("scan", "all"))  # a scan has no text layer

    def test_schematics_place_every_relation_where_each_knob_says(self):
        from semantic_pdf_diff_lab.bench.controlled import schematics
        for make in schematics.SCHEMATIC_PROJECTS.values():
            for knob in schematics.SCHEMATIC_KNOBS:
                project = make(1)
                project.knob = knob
                data, log = controlled.render(project)
                with self.subTest(project=project.id, knob=knob):
                    again = make(1)
                    again.knob = knob
                    self.assertEqual(controlled.render(again)[0], data)  # byte for byte
                    system = project.schematic["system"]
                    links = [f for f in project.facts if f.relation]
                    described = {links[i].id for i, l in enumerate(system.links) if l.kind == "intro"}
                    drawable = [f for f in links if f.id not in described]
                    forms = {x["form"] for f in drawable for x in f.forms}
                    want = {"clean": {"figure", "prose"}, "prose": {"prose"}, "prose-hard": {"prose"},
                            "all": {"figure", "prose"}}.get(knob, {"figure"})
                    self.assertEqual(forms, want)
                    self.assertTrue(all({x["form"] for x in f.forms} == {"prose"} for f in links if f.id in described))
                    if knob == "all":  # half the relations told in words too, the rest only drawn
                        told = sum(1 for f in drawable if any(x["form"] == "prose" for x in f.forms))
                        self.assertEqual(told, len(drawable) // 2)

    def test_no_line_crosses_a_part_in_any_layout(self):
        from semantic_pdf_diff_lab.bench.controlled import schematics as S
        for make in S.SCHEMATIC_PROJECTS.values():
            system = make(1).schematic["system"]
            for folded in (False, True):
                pos, _ = S.layout(system, 504, folded)
                box_w = min(S.BOX_W, 504 / (4 if folded else len(system.path)) - 12)
                box = lambda c: (c[0] - box_w / 2 - 2, c[1] - S.BOX_H / 2 - 2, c[0] + box_w / 2 + 2, c[1] + S.BOX_H / 2 + 2)
                ids = {p.id for p in system.parts}
                for l in system.links:
                    if l.object in ids and l.kind not in ("member", "intro"):  # drawn as lines
                        for q, c in pos.items():
                            if q not in (l.subject, l.object):
                                with self.subTest(system=system.id, folded=folded, link=(l.subject, l.object), part=q):
                                    self.assertFalse(S._crosses(pos[l.subject], pos[l.object], box(c)))

    def test_sheets_under_every_knob(self):
        import pymupdf
        from semantic_pdf_diff_lab.bench.controlled import sheets
        for knob in sheets.SHEET_KNOBS:
            project = sheets.plan_sheet(1)
            project.knob = knob
            data, log = controlled.render(project)
            with self.subTest(knob=knob):
                again = sheets.plan_sheet(1)
                again.knob = knob
                self.assertEqual(controlled.render(again)[0], data)
                page = pymupdf.open("pdf", data)[0]
                self.assertEqual(page.rect.width * page.rect.height, 2592 * 1728)  # ARCH D
                self.assertEqual(page.rotation, 90 if knob in ("rotated", "all") else 0)
                self.assertTrue(all(f.forms for f in project.facts))
                width = project.fact("room101.width")
                self.assertEqual([x["form"] for x in width.forms], ["drawing"])

    def test_prose_knobs_leave_table_projects_alone(self):
        project = controlled.equipment_schedules(1)
        project.knob = "all"
        self.assertFalse(project.has("two-column") or project.has("furniture"))

def claim(fact, **change):
    c = {"entity": fact.entity, "attribute": fact.attribute, "value": f"{fact.value}", "unit": fact.unit,
         "conditions": fact.conditions}
    c.update(change)
    return c

class Scoring(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.project = controlled.water_treatment(1)
        _, log = controlled.render(cls.project)
        cls.key = controlled.key(cls.project, log)

    def test_a_perfect_reading_scores_every_fact(self):
        claims = [claim(f) for f in self.project.facts if f.role == "fact"]
        s = controlled.score(self.key, claims + claims)  # read twice: counted once
        self.assertEqual((s["recall"], s["found_right"], s["missed"]), (1.0, s["facts"], []))
        self.assertEqual(s["outcomes"], {"right": s["facts"]})
        kept, total = map(int, s["conditions_kept"].split("/"))
        self.assertEqual(kept, total)

    def test_each_kind_of_error_is_classed(self):
        p = self.project
        a, b = p.fact("P-101A.capacity"), p.fact("P-101B.capacity")
        page = next(x["text"] for x in self.key["printed"] if x["role"] == "structure")
        claims = [
            claim(a, entity="pump"),                         # vague: three pumps fit "pump"
            claim(a, entity=b.entity),                       # A's capacity filed under B: misbound
            claim(a, attribute="total dynamic head"),        # A's capacity as its head: misbound
            claim(b, value=page),                            # a structural number as a value: misread
            claim(b, value="12,345.6"),                      # printed nowhere: hallucinated
            claim(b, value="9,876", entity="Raw water pump P-101Z"),  # a viable invention: hallucinated
            claim(p.fact("plant.design_flow"), conditions=""),  # right, its condition dropped
            {"entity": "Alum feed", "attribute": "coagulant", "value": "aluminum sulfate"},  # no number: not scored
        ]
        s = controlled.score(self.key, claims)
        self.assertEqual(s["outcomes"], {"hallucinated": 2, "loose": 1, "misbound": 2, "misread": 1, "right": 1,
                                         "text": 1})
        self.assertEqual(s["conditions_kept"], "0/1")
        self.assertIn("P-101B.capacity", s["missed"])
        self.assertNotIn("P-101A.capacity", s["missed"])  # found, loosely

    def test_conditions_only_break_ties(self):
        project = controlled.equipment_schedules(1)
        _, log = controlled.render(project)
        power = project.fact("B-402.motor power")
        # the section's name in conditions ("Process air blower") mustn't pull the value to the blower's airflow
        s = controlled.score(controlled.key(project, log), [claim(power, entity="B-402", attribute="Power",
                                                                   conditions="Process air blower")])
        self.assertEqual(s["outcomes"], {"right": 1})
        # the pump table's label on a blower's value is a misbinding (the stacked table's hazard)
        pressure = project.fact("B-401.discharge pressure")
        s = controlled.score(controlled.key(project, log), [claim(pressure, entity="B-401", attribute="TDH")])
        self.assertEqual(s["outcomes"], {"misbound": 1})

    def test_a_limit_is_kept_however_it_is_put(self):
        self.assertEqual(controlled.bounds("shall not exceed"), {"maximum"})
        self.assertEqual(controlled.bounds("not rated for snow loads above"), {"maximum"})
        self.assertEqual(controlled.bounds("no less than"), {"minimum"})
        self.assertEqual(controlled.bounds("design flow"), set())
        project = controlled.convention_center(1)
        _, log = controlled.render(project)
        noise = project.fact("hallc.noise")
        claims = [claim(noise, attribute="maximum background noise", conditions=""),
                  claim(project.fact("hallc.liveload"), conditions="no less than"),
                  claim(project.fact("roof.snow"), conditions="")]
        s = controlled.score(controlled.key(project, log), claims)
        self.assertEqual(s["conditions_kept"], "2/3")  # the snow load's limit was dropped
        signed = [claim(project.fact("roof.snow"), value=f"<= {project.fact('roof.snow').value}", conditions="")]
        self.assertEqual(controlled.score(controlled.key(project, log), signed)["conditions_kept"], "1/1")
        room = project.fact("room101.seats")  # one reader drops the caption's hall, another keeps it
        twice = [claim(room, entity="Room 101", conditions=""), claim(room, entity="Room 101", conditions="Hall C")]
        s = controlled.score(controlled.key(project, log), twice)
        self.assertEqual((s["claims"], s["conditions_kept"]), (1, "1/1"))

    def test_a_range_stands_for_both_its_bounds(self):
        project = controlled.convention_center(1)
        _, log = controlled.render(project)
        low, high = project.fact("hallc.tmin"), project.fact("hallc.tmax")
        s = controlled.score(controlled.key(project, log), [
            {"entity": "Hall C", "attribute": "indoor design temperature", "value": f"{low.value} to {high.value} °F"},
            {"entity": "Hall C", "attribute": "clear height", "value": "17'-9 1/2\""}])  # feet and inches: one value, printed nowhere
        self.assertEqual(s["outcomes"], {"right": 2, "hallucinated": 1})
        self.assertNotIn("hallc.tmax", s["missed"])

    def test_bars_read_against_an_axis_count_within_a_quarter_step(self):
        project = controlled.energy_study(1)
        project.knob = "axis"
        _, log = controlled.render(project)
        key = controlled.key(project, log)
        july = project.fact("opt1.july")
        bar = lambda v, **k: {"entity": "Option 1, chilled beams", "attribute": "cooling energy",
                              "value": f"{v:g}", "conditions": "July", **k}
        s = controlled.score(key, [bar(july.number + 10)])  # within 12.5
        self.assertEqual(s["outcomes"], {"right": 1})
        s = controlled.score(key, [bar(july.number + 40)])  # the bar named, its height misread
        self.assertEqual((s["outcomes"], s["found"]), ({"inexact": 1}, 0))
        # July's height filed under August is judged against August's bar: to the eye, a misjudged height
        s = controlled.score(key, [bar(july.number, conditions="August")])
        self.assertEqual(s["outcomes"], {"inexact": 1})
        exhibit = project.fact("zone.exhibit")  # bars of two charts near one value: the names choose
        s = controlled.score(key, [{"entity": "Exhibit floor", "attribute": "peak cooling load", "value": exhibit.value}])
        self.assertEqual(s["outcomes"], {"right": 1})
        self.assertNotIn("zone.exhibit", s["missed"])

    def test_relations_score_by_names_from_either_side(self):
        from semantic_pdf_diff_lab.bench.controlled import schematics
        project = schematics.ahu_drawing(1)
        project.knob = "clean"
        _, log = controlled.render(project)
        key = controlled.key(project, log)
        claim = lambda e, a, v: {"entity": e, "attribute": a, "value": v}
        cases = [
            (claim("cooling coil", "upstream of", "supply fan"), {"right": 1}),
            (claim("supply fan", "position", "after the cooling coil"), {"right": 1}),       # the inverse, in words
            (claim("AHU-3", "air path", "mixing box -> filter bank -> cooling coil"), {"right": 2}),  # a path: pairs
            (claim("filter bank", "upstream of", "supply fan"), {"implied": 1}),            # true, two steps on
            (claim("supply fan", "upstream of", "cooling coil"), {"reversed": 1}),
            (claim("motor M-3", "drives", "return fan"), {"wrong": 1}),
            (claim("AHU-3", "components", "mixing box, humidifier"), {"right": 1, "invented": 1}),
            (claim("supply fan", "function", "moves air through the hall"), {"unscored": 1}),
            (claim("Hall C", "served by", "panel LP-2"), {"wrong": 1}),  # (on the air loop, everything is upstream)
            (claim("motor M-3", "drives", "AHU-3"), {"implied": 1}),     # it drives a part of AHU-3
            (claim("panel LP-2", "connects to", "motor M-3"), {"implied": 1}),  # a link, its kind not said
            (claim("panel LP-2", "connects to", "motor M-3 (power)"), {"right": 1}),  # ...and said
        ]
        for c, want in cases:
            with self.subTest(claim=c):
                self.assertEqual(controlled.score(key, [c])["relations"], want)
        both = controlled.score(key, [claim("cooling coil", "upstream of", "supply fan"),
                                      claim("supply fan", "downstream of", "cooling coil")])
        self.assertEqual(both["relations"], {"right": 1})  # one fact, read twice in two ways, counts once

    def test_lengths_compare_in_inches_however_written(self):
        from semantic_pdf_diff_lab.bench.controlled import sheets
        for text, unit, want in (("58'-6\"", "", 702), ("58' 6\"", "", 702), ("58 ft 6 in", "", 702),
                                 ("58.5 ft", "", 702), ("702 in", "", 702), ("58.5", "ft", 702), ("58.5", "", None)):
            self.assertEqual(sheets.inches(text, unit), want, text)
        project = sheets.plan_sheet(1)
        _, log = controlled.render(project)
        key = controlled.key(project, log)
        room = project.fact("room101.width")
        feet = sheets.inches(room.value) / 12
        claim = lambda **c: {"entity": "Meeting 101", "attribute": "width", **c}
        self.assertEqual(controlled.score(key, [claim(value=f"{feet:g}", unit="ft")])["outcomes"], {"right": 1})
        self.assertEqual(controlled.score(key, [claim(value=room.value)])["outcomes"], {"right": 1})
        depth = project.fact("room101.depth")
        self.assertEqual(controlled.score(key, [claim(value=depth.value)])["outcomes"], {"misbound": 1})  # its depth
        s = controlled.score(key, [{"entity": "D101", "attribute": "room", "value": "MEETING 101"}])
        self.assertEqual(s["relations"], {"right": 1})  # the schedule's room column: the door is in that room
        door = project.fact("D104.width")
        s = controlled.score(key, [{"entity": "D104 MEETING 104", "attribute": "dimension", "value": door.value}])
        self.assertEqual(s["outcomes"], {"loose": 1})  # the door and its room both named: vague, not misbound
        split = {"entity": "Meeting 101", "attribute": "width", "value": room.value.split("'")[0],
                 "unit": "'" + room.value.split("'", 1)[1]}  # "23" with "'-0\"" as its unit
        self.assertEqual(controlled.score(key, [split])["outcomes"], {"right": 1})
        date = lambda rev, d: {"entity": f"Revision {rev}", "attribute": "date", "value": d}
        self.assertEqual(controlled.score(key, [date("B", "2026-02-20")])["outcomes"], {"right": 1})
        self.assertEqual(controlled.score(key, [date("A", "2026-02-20")])["outcomes"], {"misbound": 1})
        self.assertEqual(controlled.score(key, [date("A", "2026-02-21")])["outcomes"], {"hallucinated": 1})

    def test_values_carry_their_units(self):
        """Units were ignored: a fact's number in a unit of another kind or size was right (code review 2026-10-01,
        item 10). Now it's a wrong unit when bound to its own fact; one kind compares by magnitude; a unit the
        scorer doesn't know abstains."""
        project = controlled.equipment_schedules(1)
        _, log = controlled.render(project)
        key = controlled.key(project, log)
        air, power = project.fact("B-401.airflow"), project.fact("B-401.motor power")
        outcome = lambda **c: controlled.score(key, [claim(air, **c)])["outcomes"]
        self.assertEqual(outcome(unit="gpm"), {"wrong unit": 1})       # the pump table's unit on a blower
        self.assertEqual(outcome(unit="ft"), {"wrong unit": 1})        # another kind altogether
        self.assertEqual(outcome(unit="SCFM"), {"right": 1})
        self.assertEqual(outcome(unit="", value=f"{air.value} scfm"), {"right": 1})  # the unit in the value
        self.assertEqual(outcome(unit="furlongs"), {"right": 1})        # unknown: the number decides
        kilowatts = f"{power.number * 0.7457:.4g}"                     # hp as kW, rounded as a reader would
        self.assertEqual(controlled.score(key, [claim(power, value=kilowatts, unit="kW")])["outcomes"], {"right": 1})
        s = controlled.score(key, [claim(air), claim(air, unit="gpm")])  # two readings: one right, one not
        self.assertEqual((s["outcomes"], s["found_right"]), ({"right": 1, "wrong unit": 1}, 1))
        s = controlled.score(key, [claim(air, entity="Blower B-402", unit="gpm")])  # bound elsewhere: misbound first
        self.assertEqual(s["outcomes"], {"misbound": 1})

    def test_a_condition_is_kept_by_its_distinctive_words(self):
        """A condition was kept on any shared word ("maximum day" kept "average day"; naming the filters kept
        "with one filter out of service"): code review 2026-10-01, item 10."""
        kept = lambda project, fact, **c: controlled.score(controlled.key(project, controlled.render(project)[1]),
                                                           [claim(fact, **c)])["conditions_kept"]
        plant = controlled.water_treatment(1)
        flow = plant.fact("plant.design_flow")  # "average day"; the peak flow's is "maximum day"
        self.assertEqual(kept(plant, flow, conditions="maximum day"), "0/1")
        self.assertEqual(kept(plant, flow, conditions="avg. day"), "1/1")
        self.assertEqual(kept(plant, plant.fact("chem.alum"), conditions=""), "1/1")  # "average dose" says it
        rate = plant.fact("filters.rate")
        self.assertEqual(kept(plant, rate, conditions=""), "0/1")
        self.assertEqual(kept(plant, rate, conditions="one unit out of service"), "1/1")
        center = controlled.convention_center(1)
        area = center.fact("halls.area")  # an alias carrying the scope says it
        self.assertEqual(kept(center, area, entity="four halls", attribute="total exhibit space", conditions=""), "1/1")

    def test_located_in_is_a_place_or_a_part_by_what_follows(self):
        """"located in" and "in" are phrases of both within and located at; the tie left them unscored (code review
        2026-10-01, item 10)."""
        from semantic_pdf_diff_lab.bench.controlled import relations
        part, place = relations.Thing("AHU-3"), relations.Thing("pupil plane", literal=True)
        fan, stop = relations.Thing("supply fan"), relations.Thing("Lyot stop")
        things = [part, place, fan, stop]
        triple = lambda e, a, v: relations.triples({"entity": e, "attribute": a, "value": v}, things)
        self.assertEqual(triple("supply fan", "located in", "AHU-3"), [(fan, "within", part)])
        self.assertEqual(triple("Lyot stop", "located in", "pupil plane"), [(stop, "located at", place)])
        self.assertEqual(triple("supply fan", "in", "AHU-3"), [(fan, "within", part)])

    def test_fractions_of_an_inch(self):
        from semantic_pdf_diff_lab.bench.controlled import sheets
        for text, want in (("2'-9 1/2\"", 33.5), ("2'-9-1/2\"", 33.5), ("9 1/2\"", 9.5), ("1/2\"", 0.5),
                           ("58 ft 6 1/2 in", 702.5), ("2'-0 1/0\"", None), ("1/8\" = 1'-0\"", None)):
            self.assertEqual(sheets.inches(text), want, text)
        project = sheets.plan_sheet(1)
        _, log = controlled.render(project)
        room = project.fact("room101.width")
        half = sheets.inches(room.value) + 0.5
        written = f"{int(half // 12)}'-{int(half % 12)} 1/2\""
        s = controlled.score(controlled.key(project, log), [{"entity": "Meeting 101", "attribute": "width", "value": written}])
        self.assertEqual(s["outcomes"], {"hallucinated": 1})  # half an inch off: not the room's width, nor 23 feet

    def test_a_superseded_value_reported_as_current_is_a_distractor(self):
        project = controlled.roller_coaster(1)
        _, log = controlled.render(project)
        old = project.fact("ride.lift_old")
        s = controlled.score(controlled.key(project, log), [claim(old, conditions="")])
        self.assertEqual(s["outcomes"], {"distractor": 1})
        self.assertEqual(s["found"], 0)


class Replay(unittest.TestCase):
    """The committed corpus, read again from its recorded answers, scores as committed."""
    def test_the_corpus_reads_again_to_the_recorded_scores(self):
        import contextlib, io, json, tempfile
        from pathlib import Path
        import pymupdf
        from semantic_pdf_diff import cli, fixtures
        from semantic_pdf_diff_lab.eval import rounds
        folder = Path(__file__).resolve().parent.parent / "benchmarks" / "controlled"
        if not (folder / "replay.zip").exists():
            self.skipTest("no recorded corpus")
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            with fixtures.open(folder / "replay.zip", "read") as f:
                recorded_with = f.meta().get("pymupdf")
                responder = f.db.execute("SELECT DISTINCT responder FROM response").fetchone()[0]
            if recorded_with != pymupdf.VersionBind:
                self.skipTest(f"recorded with PyMuPDF {recorded_with}; documents differ under {pymupdf.VersionBind}")
            committed = json.loads((folder / "results.json").read_text())["recorded"]
            for project in controlled.corpus():
                pdf = controlled.write(project, d / "docs")
                self.assertEqual(pdf.read_bytes(), (folder / "docs" / pdf.name).read_bytes())  # generated alike
                with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                    code = cli.main([str(pdf), str(pdf), "--config", str(folder / "settings.json"), "-q", "--no-situate",
                                     "--out", str(d / "runs" / project.id), "--fixture", str(folder / "replay.zip"),
                                     "--fixture-mode", "replay", "--base-url", "http://127.0.0.1:9/v1",
                                     "--responder", responder])
                self.assertIn(code, (0, 2))
            claims = {}
            for (run, _, _, _), unit in rounds.collect(d / "runs").items():
                claims.setdefault(run, []).extend(unit["claims"].values())
            for run, found in claims.items():
                key = json.loads((d / "docs" / f"{run}.key.json").read_text())
                result = controlled.score(key, found)
                self.assertEqual((result["recall"], result["outcomes"]), (committed[run]["recall"], committed[run]["outcomes"]))

@slow
class Corpus(unittest.TestCase):
    """Every committed document is generated again byte for byte, so recorded answers keep replaying (a drawing
    change that moved one chart's bytes once went unnoticed until a run had started)."""
    def test_every_committed_document_is_generated_alike(self):
        import json
        import tempfile
        from pathlib import Path
        import pymupdf
        from semantic_pdf_diff import fixtures
        folder = Path(__file__).resolve().parent.parent / "benchmarks" / "controlled"
        if not (folder / "replay.zip").exists():
            self.skipTest("no recorded corpus")
        with fixtures.open(folder / "replay.zip", "read") as f:
            recorded_with = f.meta().get("pymupdf")
        if recorded_with != pymupdf.VersionBind:
            self.skipTest(f"recorded with PyMuPDF {recorded_with}; documents differ under {pymupdf.VersionBind}")
        projects = controlled.corpus(knobs=True)
        # every committed document is still generated, and every generated one is committed
        self.assertEqual({p.id for p in projects}, {f.stem for f in (folder / "docs").glob("*.pdf")})
        self.assertEqual({p.id for p in projects}, {f.name[:-len(".key.json")] for f in (folder / "docs").glob("*.key.json")})
        for project in projects:
            with self.subTest(document=project.id):
                data, log = controlled.render(project)
                self.assertEqual(data, (folder / "docs" / f"{project.id}.pdf").read_bytes())
                key = json.loads((folder / "docs" / f"{project.id}.key.json").read_text(encoding="utf-8"))
                self.assertEqual(json.loads(json.dumps(controlled.key(project, log), ensure_ascii=False)), key)

if __name__ == "__main__":
    unittest.main()
