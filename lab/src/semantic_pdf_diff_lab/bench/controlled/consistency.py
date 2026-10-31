"""Planted inconsistencies and gaps (docs/plans/single-document-analysis-2026-10-28.md, milestones 3 to 5): a pump
station's design report written twice from one seed, planted and clean, so the second pass and the gaps found by code
are scored exactly. The owner, 2026-10-31: "The proposed next steps seem good to me. Please proceed." (the second pass
scored rather than judged by eye).

- **Planted** (the key's "planted"): a value restated otherwise in another section, under no other condition (a
  contradiction); a sibling missing a property (a schedule's blank cell); a placeholder ("TBD"); a figure or table
  cited and not in the document.
- **In both twins** (the key's "pairs" and "implied"; never findings): a value restated alike, or in other units; a
  value restated under another condition (on the standby generator, at runout); a total the document implies and
  doesn't state.
- **The clean twin** prints the planted places right: its contradictions restated alike, every cell filled, its
  references to tables it has. What's found there is false.
- **Scored** (scored()) from an analysis's report.json against its key: each claim bound to its fact as the corpus's
  scorer binds it (score.classify), then each planted item found or not, by the second pass (contradictions, likely
  gaps, inferences) or by code (gaps), each pair's relations, what's found and not planted, and what the second
  pass's suspicions were by the scorer's classes.
"""
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from .corpus import render
from .model import Draw, Fact, Project

STATION = ("Millbrook Pump Station", ("Millbrook PS", "the station", "pump station"))
WET_WELL = ("Wet well", ("the wet well", "wet well"))
FORCE_MAIN = ("Force main", ("the force main", "force main", "discharge force main"))
ODOUR = ("Odour control unit", ("odour control", "odor control", "carbon unit"))
PUMP = {"capacity": ("capacity", ("flow", "rated flow", "rated capacity"), "gpm", "Capacity (gpm)", (1200, 2400, 0)),
        "tdh": ("total dynamic head", ("TDH", "head", "rated head"), "ft", "TDH (ft)", (60, 120, 1)),
        "motor": ("motor power", ("motor", "motor rating", "power"), "hp", "Motor (hp)", (40, 125, 0)),
        "npshr": ("NPSH required", ("NPSHr", "NPSH", "net positive suction head required"), "ft", "NPSHr (ft)",
                  (8, 20, 1)),
        "speed": ("speed", ("motor speed", "rpm", "rated speed"), "rpm", "Speed (rpm)", (1150, 1780, 0))}
VALVE = {"size": ("size", ("diameter", "nominal size"), "in", "Size (in)", (4, 24, 0)),
         "rating": ("pressure rating", ("rating", "pressure class"), "psi", "Rating (psi)", (125, 300, 0)),
         "cv": ("flow coefficient", ("Cv", "valve coefficient"), "", "Cv", (150, 4800, 0)),
         "stroke": ("stroke time", ("opening time", "closing time"), "s", "Stroke time (s)", (10, 90, 1))}
PUMPS = ("P-301", "P-302", "P-303", "P-304")
VALVES = ("V-11", "V-12", "V-13", "V-14", "V-15")
TWINS = ("planted", "clean")
VALUE_NAMED = re.compile(r"^[-+]?[\d,.]+$")  # a property named by a value (a table read without its header)

def station(seed=1, twin="planted"):
    """The report as one twin prints it: planted or clean. Both draw the same values in the same order."""
    planted = twin == "planted"
    d = Draw(f"station-{seed}")
    F, plants, pairs = [], [], []
    add = lambda *a, **k: F.append(Fact(*a, **k)) or F[-1]  # noqa: E731
    population = add("station.population", *STATION, "population served", ("service population", "population"),
                     d.number(8000, 30000), "persons")
    adwf = add("station.adwf", *STATION, "average dry weather flow", ("ADWF", "average flow"), d.number(1.2, 3.9, 2),
               "MGD")
    pwwf = add("station.pwwf", *STATION, "peak wet weather flow", ("PWWF", "peak flow"), d.number(6, 14, 1), "MGD")
    volume = add("wetwell.volume", *WET_WELL, "working volume", ("volume", "storage volume"), d.number(6000, 15000),
                 "gal")
    volume_said = d.number(6000, 15000)  # the planted twin's datasheet says this instead
    diameter = add("wetwell.diameter", *WET_WELL, "diameter", ("inside diameter",), d.number(10, 16), "ft")
    depth = add("wetwell.depth", *WET_WELL, "depth", ("wet well depth", "total depth"), d.number(18, 30, 1), "ft")
    alarm = add("wetwell.alarm", *WET_WELL, "high water alarm elevation", ("high level alarm", "alarm elevation"),
                d.number(410, 440, 1), "ft")
    pumps = {}
    for tag in PUMPS:
        name = (f"Pump {tag}", (tag, f"pump {tag}", f"sewage pump {tag}"))
        pumps[tag] = {k: Fact(f"{tag}.{k}", *name, attribute, synonyms, d.number(*drawn), unit, drawn="table")
                      for k, (attribute, synonyms, unit, _, drawn) in PUMP.items()}
    motor_said, head_said = d.number(40, 125), d.number(60, 120, 1)  # P-302's motor and P-304's head, planted
    at_50 = d.number(900, 1190)
    runout = d.number(2410, 3000)
    valves = {}
    for tag in VALVES:
        name = (f"Valve {tag}", (tag, f"valve {tag}", f"plug valve {tag}"))
        valves[tag] = {k: Fact(f"{tag}.{k}", *name, attribute, synonyms, d.number(*drawn), unit, drawn="table")
                       for k, (attribute, synonyms, unit, _, drawn) in VALVE.items()}
    n = d.rng.randint(4, 19)  # the force main: a length in feet that's a round tenth of a mile
    feet, miles = f"{n * 528:,}", f"{n / 10:g}"
    d.used.update({feet, miles})
    main_ft = add("forcemain.length", *FORCE_MAIN, "length", ("pipe length", "force main length"), feet, "ft")
    main_mi = add("forcemain.length_mi", *FORCE_MAIN, "length", ("pipe length", "force main length"), miles, "mi")
    main_dia = add("forcemain.diameter", *FORCE_MAIN, "diameter", ("pipe diameter", "size"), d.number(10, 18), "in")
    surge = ("Force main surge", ("surge", "transient", "surge analysis"))
    surge_max = add("surge.max", *surge, "maximum transient pressure", ("maximum surge pressure", "peak pressure"),
                    d.number(150, 240), "psi")
    surge_min = add("surge.min", *surge, "minimum transient pressure", ("minimum surge pressure", "lowest pressure"),
                    d.number(2, 9, 1), "psi")
    airflow = d.number(400, 1600)
    carbon = add("odour.carbon", *ODOUR, "carbon bed volume", ("carbon volume", "bed volume"), d.number(60, 180),
                 "ft³")
    fan = add("odour.fan_motor", *ODOUR, "fan motor", ("fan power", "motor"), d.number(2, 9, 1), "hp")

    # the pumps' schedule: P-303's NPSHr blank, P-304's speed TBD (planted)
    blank, tbd = ("P-303", "npshr"), ("P-304", "speed")
    rows = []
    for tag in PUMPS:
        cells = [tag]
        for k in PUMP:
            if planted and (tag, k) == blank:
                cells.append("")
            elif planted and (tag, k) == tbd:
                cells.append("TBD")
            else:
                cells.append(F.append(pumps[tag][k]) or pumps[tag][k].value)
        rows.append(cells)
    valve_rows = []
    for tag in VALVES:
        cells = [tag]
        for k in VALVE:
            if planted and (tag, k) == ("V-14", "rating"):
                cells.append("")
            else:
                cells.append(F.append(valves[tag][k]) or valves[tag][k].value)
        valve_rows.append(cells)
    if planted:
        plants += [{"kind": "sibling", "subject": "P-303", "property": names("npshr")},
                   {"kind": "sibling", "subject": "V-14", "property": names("rating", VALVE)},
                   {"kind": "placeholder", "subject": "P-304", "property": names("speed")}]
    if planted:
        odour = [["Fan airflow (cfm)", "TBD"]]
        plants.append({"kind": "placeholder", "subject": "odour", "property": ["fan airflow", "airflow"]})
    else:
        flow = add("odour.airflow", *ODOUR, "fan airflow", ("airflow", "air flow"), airflow, "cfm")
        odour = [["Fan airflow (cfm)", flow.value]]
    odour += [["Carbon bed volume (ft³)", carbon.value], ["Fan motor (hp)", fan.value]]

    p1, p2, p3, p4 = (pumps[t] for t in PUMPS)
    cond_50 = add("P-301.capacity_50", *_named("P-301"), "capacity", PUMP["capacity"][1], at_50, "gpm",
                  "at 50 Hz on the standby generator")
    cond_runout = add("P-302.capacity_runout", *_named("P-302"), "capacity", PUMP["capacity"][1], runout, "gpm",
                      "at runout")
    pairs += [{"kind": "condition", "facts": ["P-301.capacity", cond_50.id]},
              {"kind": "condition", "facts": ["P-302.capacity", cond_runout.id]},
              {"kind": "restatement", "facts": ["P-301.capacity", "P-301.capacity"]},
              {"kind": "restatement", "facts": ["P-301.tdh", "P-301.tdh"]},
              {"kind": "restatement", "facts": [main_ft.id, main_mi.id]}]
    if planted:  # said again otherwise: P-302's motor, P-304's head, the wet well's volume
        motor = add("P-302.motor_said", *_named("P-302"), "motor power", PUMP["motor"][1], motor_said, "hp")
        head = add("P-304.tdh_said", *_named("P-304"), "total dynamic head", PUMP["tdh"][1], head_said, "ft")
        datasheet_volume = add("wetwell.volume_said", *WET_WELL, "working volume", ("volume", "storage volume"),
                               volume_said, "gal")
        plants += [{"kind": "contradiction", "facts": ["P-302.motor", motor.id]},
                   {"kind": "contradiction", "facts": ["P-304.tdh", head.id]},
                   {"kind": "contradiction", "facts": [volume.id, datasheet_volume.id]}]
        said = {"motor": motor.value, "head": head.value, "volume": datasheet_volume.value}
    else:
        pairs += [{"kind": "restatement", "facts": ["P-302.motor", "P-302.motor"]},
                  {"kind": "restatement", "facts": ["P-304.tdh", "P-304.tdh"]},
                  {"kind": "restatement", "facts": [volume.id, volume.id]}]
        said = {"motor": p2["motor"].value, "head": p4["tdh"].value, "volume": volume.value}
    firm = sum(int(p["capacity"].value.replace(",", "")) for p in (p1, p2, p3))
    implied = [{"what": "firm capacity of P-301, P-302 and P-303 together",
                "values": [f"{firm:,}", str(firm), f"{firm * 1440 / 1e6:.2f}"]}]
    layout = ("The site layout is shown in Figure 4." if planted else
              "The station sits on the existing parcel, beside the access road.")
    surge_said = "Surge pressures are given in Table 7." if planted else "Surge pressures are given in Table 4."
    if planted:
        plants += [{"kind": "reference", "label": "Figure 4"}, {"kind": "reference", "label": "Table 7"}]

    sections = [
        ("1 Design Basis", [
            ("p", f"The {STATION[0]} serves a population of {population.value} persons. Its average dry weather flow "
                  f"is {adwf.value} MGD and its peak wet weather flow {pwwf.value} MGD. {layout}"),
            ("p", f"The wet well provides a working volume of {volume.value} gal between the pump-off level and the "
                  f"lead pump's start level."),
        ]),
        ("2 Pumps", [
            ("p", "Four submersible pumps are installed: P-301, P-302 and P-303 run together at peak wet weather flow, "
                  "and P-304 is the standby."),
            ("table", "Table 1. Pump schedule", ["Tag"] + [PUMP[k][3] for k in PUMP], rows),
            ("p", f"P-301, the lead pump, delivers {p1['capacity'].value} gpm at {p1['tdh'].value} ft. On the standby "
                  f"generator at 50 Hz, P-301 delivers {cond_50.value} gpm."),
            ("p", f"Pump P-302 has a {said['motor']} hp motor; at runout, its capacity rises to {cond_runout.value} "
                  f"gpm. Pump P-304's total dynamic head is {said['head']} ft."),
        ]),
        ("3 Wet Well", [
            ("datasheet", "Table 2. Wet well", [["Working volume (gal)", said["volume"]],
                                                ["Diameter (ft)", diameter.value], ["Depth (ft)", depth.value],
                                                ["High water alarm elevation (ft)", alarm.value]]),
        ]),
        ("4 Force Main and Valves", [
            ("p", f"The force main is {main_ft.value} ft of {main_dia.value}-inch ductile iron pipe. {surge_said}"),
            ("table", "Table 3. Valve schedule", ["Tag"] + [VALVE[k][3] for k in VALVE], valve_rows),
            ("table", "Table 4. Surge analysis", ["Case", "Pressure (psi)"],
             [["Maximum transient pressure", surge_max.value], ["Minimum transient pressure", surge_min.value]]),
            ("p", f"At {main_mi.value} mi, the force main needs no intermediate air release station."),
        ]),
        ("5 Odour Control", [
            ("datasheet", "Table 5. Odour control unit", odour),
        ]),
    ]
    project = Project(f"station-s{seed}-{twin}", f"{STATION[0]}: Design Report", F, sections)
    project.planted, project.pairs, project.implied = plants, pairs, implied
    return project

def _named(tag):
    return (f"Pump {tag}", (tag, f"pump {tag}", f"sewage pump {tag}"))

def names(key, columns=PUMP):
    """A schedule column's property as a gap may name it: its attribute, synonyms and label, and its position ("column
    3", the tag's column the first), as a reader names a table's columns when it loses their header."""
    attribute, synonyms, _, label, _ = columns[key]
    return [attribute, *synonyms, re.sub(r"\s*\(.*\)$", "", label), f"column {list(columns).index(key) + 2}"]

def corpus(seeds=(1, 2)):
    return [station(seed, twin) for seed in seeds for twin in TWINS]

def keyed(project, log):
    """The answer key (corpus.key) with what's planted, the pairs and what's implied."""
    from .corpus import key
    return {**key(project, log), "planted": project.planted, "pairs": project.pairs, "implied": project.implied}

def write(project, folder):
    """<id>.pdf and <id>.key.json into folder; returns the PDF's path."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    data, log = render(project)
    pdf = folder / f"{project.id}.pdf"
    pdf.write_bytes(data)
    (folder / f"{project.id}.key.json").write_text(json.dumps(keyed(project, log), indent=1, ensure_ascii=False)
                                                   + "\n", encoding="utf-8")
    return pdf

# --- scoring -------------------------------------------------------------------------------------

def scored(key, data):
    """An analysis's report.json (data) scored against its key: {"contradictions", "pairs", "gaps", "implied",
    "suspicions"}, each count exact (see the module's docstring)."""
    from semantic_pdf_diff import indexes
    from .score import classify, key_facts
    facts = [f for f in key_facts(key) if not f.relation]
    bound, classes = {}, {}
    for e in data.get("evidence", []):
        classes[e["id"]], bound[e["id"]] = classify(e, facts, key["printed"])
    entries = (data.get("commentary") or {}).get("entries", [])
    pair = lambda a, b: tuple(sorted((str(a), str(b))))  # noqa: E731 (a claim bound to no fact: "None")
    said = defaultdict(list)  # a pair of facts: the relations said between their claims
    for entry in entries:
        if entry["kind"] == "relation":
            said[pair(*(bound.get(c) for c in entry["claims"]))].append(entry["relation"])
    planted = [p for p in key["planted"] if p["kind"] == "contradiction"]
    known = {pair(*p["facts"]) for p in planted}
    false = sorted({p for p, relations in said.items() if "contradicts" in relations and p not in known})
    out = {"contradictions": {"planted": len(planted),
                              "found": sum("contradicts" in said.get(pair(*p["facts"]), ()) for p in planted),
                              "said": {" / ".join(p["facts"]): said.get(pair(*p["facts"]), []) for p in planted},
                              "false": len(false), "false pairs": [" / ".join(p) for p in false]}}
    for kind in ("condition", "restatement"):  # the traps: said, but never contradicts
        mine = [p for p in key["pairs"] if p["kind"] == kind]
        out[kind] = {"pairs": len(mine), "contradicts": sum("contradicts" in said.get(pair(*p["facts"]), ())
                                                            for p in mine),
                     "said": {" / ".join(p["facts"]): said.get(pair(*p["facts"]), []) for p in mine}}
    gaps = indexes.built(data)["gaps"]
    matched = set()
    out["gaps"] = {}
    for kind in ("sibling", "placeholder", "reference"):
        mine = [p for p in key["planted"] if p["kind"] == kind]
        found = {"planted": len(mine), "by code": 0, "read together": 0}
        for p in mine:
            hits = [k for k, g in enumerate(gaps) if gap_matches(g, p)]
            matched.update(hits)
            found["by code"] += any(gaps[k]["kind"] != "likely" for k in hits)
            found["read together"] += any(gaps[k]["kind"] == "likely" for k in hits)
        out["gaps"][kind] = found
    unplanted = defaultdict(int)
    for k, g in enumerate(gaps):
        if k not in matched:  # a property named by a value: a misread table's, not the gap finder's
            unplanted[g["kind"] + (" (named by a value)" if VALUE_NAMED.match(g["property"]) else "")] += 1
    out["gaps"]["unplanted"] = dict(sorted(unplanted.items()))
    inferences = [fold(e.get("text", "")) for e in entries if e["kind"] == "inference"]
    out["implied"] = {"planted": len(key["implied"]),
                      "found": sum(any(any(v in text for v in i["values"]) for text in inferences)
                                   for i in key["implied"]),
                      "inferences": len(inferences)}
    contradicted = {f for p in planted for f in p["facts"]}
    evidence = {e["id"]: e for e in data.get("evidence", [])}
    suspected = defaultdict(lambda: defaultdict(int))  # a suspicion's kind: its claims' classes
    for e in entries:
        if e["kind"] == "suspicion":
            c = e["claims"][0]
            named = VALUE_NAMED.match(str(evidence.get(c, {}).get("attribute", "")))
            suspected[e.get("relation", "")]["planted contradiction" if bound.get(c) in contradicted else
                                             "named by a value" if named else classes.get(c, "unknown")] += 1
    out["suspicions"] = {k: dict(sorted(v.items())) for k, v in sorted(suspected.items())}
    out["claims"] = {"claims": len(classes), "classes": dict(sorted(Counter(classes.values()).items()))}
    out["log"] = {k: (data.get("commentary") or {}).get(k, 0) for k in ("subjects", "dropped", "failed")}
    return out

def gap_matches(gap, plant):
    """Whether a gap found is a planted one: a reference by its label; a sibling's or a placeholder by its subject's
    tag and a name of its property (as the index names a property: "NPSHr", "NPSH required", "column 5"); a
    placeholder also by its property's name in the subject and property read ("Fan" "airflow": its "TBD" read
    under another subject)."""
    if plant["kind"] == "reference":
        return gap["kind"] == "reference" and fold(plant["label"]) in fold(gap["subject"] + " " + gap["why"])
    if gap["kind"] == "reference":
        return False
    said = fold(gap["property"])
    if fold(plant["subject"]) in fold(gap["subject"]):
        return bool(said) and any(fold(n) in said or said == fold(n) for n in plant["property"])
    return plant["kind"] == gap["kind"] == "placeholder" and any(fold(n) in fold(gap["subject"] + " " + said)
                                                                 for n in plant["property"] if " " in n)

def fold(text):
    return " ".join(str(text).casefold().split())

def totals(results):
    """Each twin's scores summed over its documents ({id: scored}): {"planted": {...}, "clean": {...}}."""
    out = {}
    for twin in TWINS:
        mine = [r for name, r in sorted(results.items()) if name.endswith(f"-{twin}")]
        if not mine:
            continue
        add = lambda *path, mine=mine: sum(_at(r, path) for r in mine)  # noqa: E731
        out[twin] = {
            "documents": len(mine),
            "contradictions": {k: add("contradictions", k) for k in ("planted", "found", "false")},
            **{kind: {k: add(kind, k) for k in ("pairs", "contradicts")} for kind in ("condition", "restatement")},
            "gaps": {**{kind: {k: add("gaps", kind, k) for k in ("planted", "by code", "read together")}
                        for kind in ("sibling", "placeholder", "reference")},
                     "unplanted": dict(sorted(Counter(k for r in mine for k, n in r["gaps"]["unplanted"].items()
                                                      for _ in range(n)).items()))},
            "implied": {k: add("implied", k) for k in ("planted", "found", "inferences")},
            "suspicions": {kind: dict(sorted(Counter(c for r in mine for c, n in r["suspicions"].get(kind, {}).items()
                                                     for _ in range(n)).items()))
                           for kind in sorted({k for r in mine for k in r["suspicions"]})},
            "log": {k: add("log", k) for k in ("subjects", "dropped", "failed")}}
    return out

def _at(data, path):
    for k in path:
        data = data.get(k, 0) if isinstance(data, dict) else 0
    return data
