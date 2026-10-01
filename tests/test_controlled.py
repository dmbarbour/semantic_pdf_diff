"""Controlled documents: generated the same way every time, every fact placed, claims classed exactly."""
import unittest
from semantic_pdf_diff import controlled

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
        for knob in controlled.CHART_KNOBS:
            project = controlled.energy_study(1)
            project.knob = knob
            data, log = controlled.render(project)
            with self.subTest(knob=knob):
                again = controlled.energy_study(1)
                again.knob = knob
                self.assertEqual(controlled.render(again)[0], data)  # scans too, byte for byte
                july = project.fact("opt1.july")
                self.assertEqual([x["form"] for x in july.forms], ["chart"])  # placed by the drawer, whatever's printed
                printed = {p["text"] for p in log if p["facts"] == ["opt1.july"]}
                self.assertEqual(printed, set() if knob in ("axis", "all") else {july.value})  # axis: not printed
                self.assertEqual(july.tolerance, 12.5 if knob in ("axis", "all") else 0.0)  # a quarter of a 50 step
                text = "".join(page.get_text() for page in pymupdf.open("pdf", data))
                self.assertEqual(text == "", knob in ("scan", "all"))  # a scan has no text layer
                self.assertEqual(july.value in text, knob in ("clean", "legend-caption"))  # vector, values printed

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

    def test_a_superseded_value_reported_as_current_is_a_distractor(self):
        project = controlled.roller_coaster(1)
        _, log = controlled.render(project)
        old = project.fact("ride.lift_old")
        s = controlled.score(controlled.key(project, log), [claim(old, conditions="")])
        self.assertEqual(s["outcomes"], {"distractor": 1})
        self.assertEqual(s["found"], 0)

if __name__ == "__main__":
    unittest.main()

class Replay(unittest.TestCase):
    """The committed corpus, read again from its recorded answers, scores as committed."""
    def test_the_corpus_reads_again_to_the_recorded_scores(self):
        import contextlib, io, json, tempfile
        from pathlib import Path
        import pymupdf
        from semantic_pdf_diff import cli, fixtures, rounds
        folder = Path(__file__).resolve().parent.parent / "benchmarks" / "controlled"
        if not (folder / "replay.zip").exists():
            self.skipTest("no recorded corpus")
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            with fixtures.Fixture(fixtures.unpack(folder / "replay.zip", d)) as f:
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
