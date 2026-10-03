"""Controlled documents: PDFs for fictional projects, generated from a fact sheet and a seed, with every
fact's form and place known, so extraction is scored exactly (docs/plans/controlled-documents-2026-10-01.md).

The owner, 2026-10-01: "generate a few PDFs with known facts to extract for fictional projects. This might
provide a more robust control without relying on yours or my ability to extract facts"; "pseudo-random so we
can still leverage caching and fast testing."

- A project's generator draws its facts from a seed (values random within plausible ranges, so they can't be
  guessed) and lays them out as sections of prose and tables.
- Rendering is HTML laid out by PyMuPDF (Story): the same seed gives the same PDF, byte for byte, so the
  pipeline asks the same queries and recorded answers replay.
- Every number printed is logged with its role (a fact, a distractor such as a superseded value, or a section,
  table or page number), and every fact is located on its page, so a claim can be classed exactly: right,
  loose (the fact's value and attribute, a vague entity), misbound, wrong unit (the fact's number in a unit of
  another kind or size), misread (a non-fact number), hallucinated (a value printed nowhere), and facts missed.
"""
import io
import json
import random
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from semantic_pdf_diff.values import parse_number, printed_value

# --- facts ---------------------------------------------------------------------------------------

@dataclass
class Fact:
    id: str
    entity: str                       # as the document names it
    aliases: tuple                    # other fair names for the entity
    attribute: str
    synonyms: tuple                   # other fair names for the attribute
    value: str                        # as printed
    unit: str = ""
    conditions: str = ""
    basis: str = "proposed"           # required, proposed, measured, calculated
    role: str = "fact"                # fact, or distractor (a superseded value, say)
    forms: list = field(default_factory=list)  # where it's printed: [{"form", "page", "box"}]
    drawn: str = ""                   # the form it was drawn in, when fixed ("table" for a schedule's cells)
    tolerance: float = 0.0            # a value read against a chart's axis: how far off still counts (else exact)
    relation: str = ""                # a relational fact (relations.RELATIONS): entity, relation, value (the object)
    object_aliases: tuple = ()        # the object's other names
    accepts: tuple = ()               # other relations that state it fairly

    @property
    def number(self):
        return None if self.relation else parse_number(self.value)

class Draw:
    """Seeded values, each printed string unique within a document (so a value names one fact)."""
    def __init__(self, seed):
        self.rng, self.used = random.Random(seed), set()

    def number(self, lo, hi, decimals=0):
        for _ in range(1000):
            x = self.rng.uniform(lo, hi)
            text = f"{x:,.{decimals}f}" if decimals else f"{round(x):,}"
            if decimals and text.endswith("0"):
                continue  # no trailing zeros: 1250.5, not 1250.50
            if text not in self.used and parse_number(text) not in {parse_number(u) for u in self.used}:
                self.used.add(text)
                return text
        raise ValueError(f"no unused value in {lo}..{hi}")

    def pick(self, options):
        return self.rng.choice(list(options))

    def slot(self, near, grid):
        """The unused multiple of `grid` nearest to `near` (bars read against an axis, to half its step)."""
        base = round(near / grid)
        for k in sorted(range(-40, 41), key=abs):
            v = (base + k) * grid
            text = f"{v:,g}"
            if v > 0 and text not in self.used:
                self.used.add(text)
                return text
        raise ValueError(f"no unused slot near {near}")

# --- projects ----------------------------------------------------------------------------------

@dataclass
class Project:
    id: str
    title: str
    facts: list
    sections: list    # [(heading, [blocks])]; a block is ("p", text), ("table", caption, header, rows) or ("schedule", Schedule)
    knob: str = "clean"  # how schedules are drawn (TABLE_KNOBS), or prose, pages and charts (kinds)
    texts: dict = None   # {name: (plain, trap)} phrasings, filled from values
    values: dict = None
    kinds: tuple = ()    # the knobs a prose, chart or schematic project is drawn under
    things: list = None  # the named parts a schematic shows: [(name, aliases)]
    edits: list = field(default_factory=list)  # a revision's edits from its base (revisions.py), in the key
    revision_of: str = ""                      # the base document's id, for a revision

    def has(self, knob):
        """Whether a prose, layout or chart knob applies: "all" applies every knob of the project's kind."""
        return knob in self.kinds and self.knob in (knob, "all")

    def fact(self, fact_id):
        return next(f for f in self.facts if f.id == fact_id)

def _phrase(draw, fact, templates):
    """One of a fact's phrasings, filled in."""
    return draw.pick(templates).format(e=fact.entity, a=fact.attribute, v=fact.value, u=fact.unit, c=fact.conditions)

def water_treatment(seed=1):
    """A water treatment plant: design basis, process units, raw water pumps, chemical feed, disinfection options."""
    d = Draw(f"wtp-{seed}")
    plant = ("Harrow Creek Water Treatment Plant", ("Harrow Creek WTP", "the plant", "WTP", "water treatment plant"))
    F = []
    add = lambda *a, **k: F.append(Fact(*a, **k)) or F[-1]
    design = add("plant.design_flow", *plant, "design flow", ("average day flow", "capacity", "rated capacity", "flow"),
                 d.number(12, 30, 1), "MGD", "average day")
    peak = add("plant.peak_flow", *plant, "peak flow", ("maximum day flow", "maximum flow", "peak capacity"),
               d.number(31, 48, 1), "MGD", "maximum day")
    people = add("plant.population", *plant, "population served", ("service population", "population"),
                 d.number(40000, 120000), "persons")
    raw = add("plant.raw_turbidity", *plant, "raw water turbidity", ("source turbidity", "influent turbidity"),
              d.number(8, 40, 1), "NTU", "95th percentile", basis="measured")
    limit = add("plant.finished_turbidity", *plant, "finished water turbidity", ("effluent turbidity", "turbidity limit"),
                d.number(0.1, 0.3, 2), "NTU", "in 95% of monthly samples", basis="required")
    mix = ("Rapid mix basin", ("rapid mix", "rapid-mix basin", "flash mix"))
    mix_t = add("mix.detention", *mix, "detention time", ("hydraulic detention time", "residence time", "HDT"),
                d.number(20, 60), "s", "at design flow", basis="calculated")
    mix_g = add("mix.g", *mix, "velocity gradient", ("G value", "mixing intensity", "G"), d.number(600, 1000), "1/s")
    floc = ("Flocculation basins", ("flocculation", "flocculators", "floc basins"))
    floc_n = add("floc.stages", *floc, "stages", ("number of stages", "stage count"), d.number(3, 4), "")
    floc_t = add("floc.detention", *floc, "total detention time", ("detention time", "flocculation time"),
                 d.number(20, 40, 1), "min", "at design flow", basis="calculated")
    sed = ("Sedimentation basins", ("sedimentation", "settling basins", "clarifiers"))
    sed_n = add("sed.count", *sed, "number of basins", ("count", "basins", "quantity"), d.number(2, 4), "")
    sed_slr = add("sed.loading", *sed, "surface loading rate", ("overflow rate", "SLR", "loading rate"),
                  d.number(0.4, 1.0, 2), "gpm/ft²", "at design flow", basis="calculated")
    sed_l = add("sed.length", *sed, "length", ("basin length",), d.number(120, 200), "ft")
    sed_w = add("sed.width", *sed, "width", ("basin width",), d.number(30, 60), "ft")
    sed_swd = add("sed.depth", *sed, "side water depth", ("SWD", "water depth", "depth"), d.number(12, 16, 1), "ft")
    flt = ("Filters", ("dual-media filters", "filtration", "filter cells"))
    flt_n = add("filters.count", *flt, "number of filters", ("count", "filter count", "quantity"), d.number(6, 12), "")
    flt_rate = add("filters.rate", *flt, "filtration rate", ("loading rate", "hydraulic loading rate"),
                   d.number(2, 6, 1), "gpm/ft²", "with one filter out of service", basis="calculated")
    flt_area = add("filters.area", *flt, "area per filter", ("filter area", "surface area", "area"),
                   d.number(400, 900), "ft²")
    pumps = []
    for tag in ("P-101A", "P-101B", "P-101C"):
        pump = (f"Raw water pump {tag}", (tag, f"pump {tag}", f"raw water pump {tag}"))
        pumps.append((tag,
                      add(f"{tag}.capacity", *pump, "capacity", ("flow", "rated flow", "design flow", "rated capacity"),
                          d.number(4000, 9000), "gpm"),
                      add(f"{tag}.head", *pump, "total dynamic head", ("TDH", "head", "rated head"),
                          d.number(60, 140, 1), "ft"),
                      add(f"{tag}.motor", *pump, "motor power", ("motor", "motor rating", "power"),
                          d.number(100, 300), "hp")))
    alum = add("chem.alum", "Alum feed", ("alum", "aluminum sulfate", "coagulant"), "average dose",
               ("dose", "dosage", "alum dose"), d.number(15, 45, 1), "mg/L", "average day")
    alum_max = add("chem.alum_max", "Alum feed", ("alum", "aluminum sulfate", "coagulant"), "maximum dose",
                   ("maximum dosage", "peak dose"), d.number(50, 80, 1), "mg/L", "maximum day")
    cl = add("chem.chlorine", "Chlorine feed", ("chlorine", "sodium hypochlorite", "disinfectant"), "dose",
             ("dosage", "chlorine dose"), d.number(1.5, 4.5, 1), "mg/L")
    uv = ("Option A, UV disinfection", ("Option A", "UV disinfection", "UV system", "ultraviolet disinfection"))
    cct = ("Option B, chlorine contact basin", ("Option B", "chlorine contact basin", "chlorine contact", "contact basin"))
    uv_cost = add("optA.cost", *uv, "capital cost", ("cost", "construction cost"), d.number(3.1, 6.9, 2), "$M")
    uv_energy = add("optA.energy", *uv, "annual energy use", ("energy use", "energy", "annual energy"),
                    d.number(400, 900), "MWh/yr", basis="calculated")
    cct_cost = add("optB.cost", *cct, "capital cost", ("cost", "construction cost"), d.number(2.0, 3.0, 2), "$M")
    cct_time = add("optB.contact", *cct, "contact time", ("detention time", "CT time"), d.number(30, 90), "min",
                   "at peak flow", basis="calculated")
    prose = lambda f, templates: _phrase(d, f, templates)
    sections = [
        ("1 Design Basis", [
            ("p", f"The {plant[0]} is sized for a design flow of {design.value} MGD (average day) and a peak flow of "
                  f"{peak.value} MGD on the maximum day, serving a population of {people.value} persons."),
            ("p", prose(raw, ["Raw water turbidity reaches {v} {u} ({c}), measured over the last five years.",
                              "Measured over five years, the 95th percentile raw water turbidity is {v} {u}."])
                  + f" Finished water turbidity shall not exceed {limit.value} NTU in 95% of monthly samples."),
        ]),
        ("2 Treatment Process", [
            ("p", f"The rapid mix basin provides a detention time of {mix_t.value} s at design flow, with a velocity "
                  f"gradient of {mix_g.value} 1/s. Flocculation follows in {floc_n.value} stages, for a total "
                  f"detention time of {floc_t.value} min at design flow."),
            ("p", f"There are {sed_n.value} sedimentation basins, each {sed_l.value} ft long and {sed_w.value} ft wide, "
                  f"with a side water depth of {sed_swd.value} ft; the surface loading rate is {sed_slr.value} gpm/ft² "
                  f"at design flow."),
            ("p", f"Filtration uses {flt_n.value} dual-media filters of {flt_area.value} ft² each. With one filter out "
                  f"of service, the filtration rate is {flt_rate.value} gpm/ft²."),
            ("table", "Table 1. Raw water pumps", ["Tag", "Capacity (gpm)", "TDH (ft)", "Motor (hp)"],
             [[tag, c.value, h.value, m.value] for tag, c, h, m in pumps]),
        ]),
        ("3 Chemical Feed", [
            ("p", f"Alum is dosed at {alum.value} mg/L on the average day and up to {alum_max.value} mg/L on the maximum "
                  f"day. Chlorine is fed at {cl.value} mg/L ahead of the clearwell."),
        ]),
        ("4 Disinfection Options", [
            ("p", "Two options were compared for primary disinfection."),
            ("table", "Table 2. Disinfection options", ["", "Option A: UV", "Option B: chlorine contact"],
             [["Capital cost ($M)", uv_cost.value, cct_cost.value],
              ["Annual energy use (MWh/yr)", uv_energy.value, "n/a"],
              ["Contact time at peak flow (min)", "n/a", cct_time.value]]),
        ]),
    ]
    return Project(f"wtp-s{seed}", plant[0], F, sections)

def roller_coaster(seed=1):
    """A steel roller coaster: ride figures, trains, track elements, structure, and a superseded lift height."""
    d = Draw(f"coaster-{seed}")
    ride = ("Ridgeback roller coaster", ("Ridgeback", "the ride", "the coaster", "roller coaster"))
    F = []
    add = lambda *a, **k: F.append(Fact(*a, **k)) or F[-1]
    lift_old = add("ride.lift_old", "Lift hill", ("lift hill", "lift", "chain lift"), "height",
                   ("lift height", "lift hill height"), d.number(150, 190), "ft", "revision A", role="distractor")
    lift = add("ride.lift", "Lift hill", ("lift hill", "lift", "chain lift"), "height",
               ("lift height", "lift hill height"), d.number(195, 230), "ft", "revision B")
    drop = add("ride.drop", "First drop", ("first drop", "drop"), "height", ("drop height",), d.number(180, 240), "ft")
    angle = add("ride.angle", "First drop", ("first drop", "drop"), "angle", ("drop angle",), d.number(70, 85, 1), "°")
    speed = add("ride.speed", *ride, "maximum speed", ("top speed", "speed", "max speed"), d.number(65, 85, 1), "mph")
    length = add("ride.length", *ride, "track length", ("length", "length of track"), d.number(4500, 7000), "ft")
    duration = add("ride.duration", *ride, "ride duration", ("duration", "ride time"), d.number(120, 200), "s")
    inversions = add("ride.inversions", *ride, "inversions", ("number of inversions",), d.number(3, 7), "")
    g_max = add("ride.g_max", *ride, "maximum vertical acceleration", ("maximum g", "peak g-force", "max g", "g-force"),
                d.number(3.6, 4.6, 1), "g", basis="calculated")
    trains = ("Trains", ("train", "ride vehicles", "trains"))
    n_trains = add("trains.count", *trains, "number of trains", ("count", "trains"), d.number(2, 3), "")
    cars = add("trains.cars", *trains, "cars per train", ("cars", "car count", "number of cars"), d.number(5, 8), "")
    riders = add("trains.riders", "Cars", ("car", "train", "trains"), "riders per car",
                 ("riders", "seats per car", "seating capacity", "seats"), d.number(4, 6), "")
    mass = add("trains.mass", *trains, "empty train mass", ("train mass", "empty mass", "mass"),
               d.number(9000, 14000), "lb")
    capacity = add("ride.capacity", *ride, "hourly capacity", ("capacity", "throughput", "riders per hour"),
                   d.number(1100, 1600), "riders/h", basis="calculated")
    elements = []
    for name in ("First drop", "Vertical loop", "Zero-g roll", "Camelback", "Helix"):
        el = (name, (name.lower(),))
        elements.append((name,
                         add(f"el.{name}.height", *el, "height", ("element height", "top height"), d.number(40, 175), "ft")
                         if name != "First drop" else None,
                         add(f"el.{name}.speed", *el, "entry speed", ("speed", "entrance speed"), d.number(40, 64, 1), "mph"),
                         add(f"el.{name}.g", *el, "peak g", ("g-force", "maximum g", "g"), d.number(1.5, 3.5, 1), "g",
                             basis="calculated")))
    supports = add("struct.columns", "Support structure", ("supports", "support columns", "structure"),
                   "number of support columns", ("columns", "support count"), d.number(180, 320), "")
    steel = add("struct.steel", "Support structure", ("supports", "structure", "steel structure"), "steel weight",
                ("steel tonnage", "tonnage", "weight"), d.number(700, 1400), "tons")
    wind = add("struct.wind", "Support structure", ("supports", "structure"), "design wind speed",
               ("wind speed", "wind load speed"), d.number(90, 120), "mph", "3-second gust", basis="required")
    sections = [
        ("1 Ride Overview", [
            ("p", f"Ridgeback is a steel roller coaster with {length.value} ft of track and {inversions.value} inversions. "
                  f"A ride lasts {duration.value} s and reaches a maximum speed of {speed.value} mph."),
            ("p", f"In revision B the lift hill was raised from {lift_old.value} ft to {lift.value} ft. The first drop "
                  f"falls {drop.value} ft at an angle of {angle.value}°, and the maximum vertical acceleration is "
                  f"{g_max.value} g."),
        ]),
        ("2 Trains", [
            ("p", f"The ride operates {n_trains.value} trains of {cars.value} cars, each car seating {riders.value} "
                  f"riders, for an hourly capacity of {capacity.value} riders/h. An empty train weighs {mass.value} lb."),
        ]),
        ("3 Track Elements", [
            ("table", "Table 1. Track elements", ["Element", "Height (ft)", "Entry speed (mph)", "Peak g"],
             [[name, h.value if h else drop.value, s.value, g.value] for name, h, s, g in elements]),
        ]),
        ("4 Structure", [
            ("p", f"The track is carried on {supports.value} support columns using {steel.value} tons of steel. The "
                  f"structure shall withstand a design wind speed of {wind.value} mph (3-second gust)."),
        ]),
    ]
    return Project(f"coaster-s{seed}", "Ridgeback roller coaster", F, sections)

def link_protocol(seed=1):
    """A link protocol's specification, written to the confounders the "why different" pass met in real
    specifications (docs/plans/revision-comparison-2026-10-02.md, milestone 4): two of a kind with nested names (a
    short and an extended short report format), a field beside its length field (Session ID, Session ID Length), a
    list whose members share one attribute's shape (a report's contents), numbered conditions, and values whose
    conditions are given only by a lead-in (the same sentence under two link states)."""
    d = Draw(f"spec-{seed}")
    F = []
    add = lambda *a, **k: F.append(Fact(*a, **k)) or F[-1]
    bits = lambda lo, hi: d.number(lo, hi)  # small whole numbers from 6 up: headings and conditions print 1 to 5
    short = add("short.field", "Short status report", ("short report", "short format", "short status report format"),
                "buffer size field length", ("buffer size field", "field length", "field size"), bits(6, 9), "bits")
    ext = add("ext.field", "Extended short status report",
              ("extended short report", "extended short format", "extended short status report format"),
              "buffer size field length", ("buffer size field", "field length", "field size"), bits(10, 14), "bits")
    groups = add("long.groups", "Long status report", ("long report", "long format", "long status report format"),
                 "maximum channel groups", ("channel groups", "number of channel groups", "groups"), bits(15, 24), "")
    long_field = add("long.field", "Long status report", ("long report", "long format", "long status report format"),
                     "buffer size field length", ("buffer size field", "field length", "field size"), bits(25, 32), "bits")
    field = lambda fid, name, aliases, attribute, value: add(
        fid, name, aliases, attribute, ("length", "size", "field length", "length in bits"), value, "bits")
    version = field("hdr.version", "Version field", ("Version", "version field"), "length", bits(6, 16))
    sid_len = field("hdr.sid_len", "Session ID Length field", ("Session ID Length", "session ID length field"), "length",
                    bits(6, 16))
    sid = field("hdr.sid", "Session ID field", ("Session ID", "session ID"), "maximum length", bits(120, 240))
    pn_len = field("hdr.pn_len", "Packet Number Length field", ("Packet Number Length", "packet number length field"),
                   "length", bits(6, 16))
    pn = field("hdr.pn", "Packet Number field", ("Packet Number", "packet number"), "maximum length", bits(33, 64))
    report = ("Measurement report", ("measurement report", "the report", "report contents"))
    member = lambda fid, what, value: add(fid, *report, f"{what} length", (what, f"{what} size", f"{what} field"),
                                          value, "bits")
    cell = member("meas.cell", "serving cell index", bits(6, 20))
    beam = member("meas.beam", "beam index", bits(6, 20))
    rssi = member("meas.rssi", "received signal strength", bits(6, 20))
    ta = member("meas.ta", "timing advance", bits(6, 20))
    failure = ("Link failure detection", ("link failure", "failure detection", "link failure declaration"))
    ack = add("fail.ack", *failure, "acknowledgement timeout", ("ack timeout", "timeout", "acknowledgement window"),
              d.number(200, 900), "ms", basis="required")
    retx = add("fail.retx", *failure, "consecutive failed retransmissions", ("failed retransmissions", "retransmissions"),
               bits(6, 30), "", basis="required")
    snr = add("fail.snr", *failure, "signal-to-noise threshold", ("SNR threshold", "signal-to-noise ratio"),
              d.number(1.5, 4.5, 1), "dB", basis="required")
    low = add("fail.duration", *failure, "low signal duration", ("duration", "time below threshold"), bits(33, 90), "s",
              basis="required")
    timer = ("Retransmission timer", ("retransmission timer", "RTO", "retransmit timer"))
    window = ("Send window", ("send window", "window", "transmit window"))
    timer_busy = add("timer.congested", *timer, "duration", ("value", "timeout", "timer value"), d.number(300, 900), "ms",
                     "link congested", basis="required")
    window_busy = add("window.congested", *window, "size", ("window size", "packets"), d.number(91, 150), "packets",
                      "link congested", basis="required")
    timer_idle = add("timer.idle", *timer, "duration", ("value", "timeout", "timer value"), d.number(1000, 3000), "ms",
                     "link idle", basis="required")
    window_idle = add("window.idle", *window, "size", ("window size", "packets"), d.number(151, 256), "packets",
                      "link idle", basis="required")
    sections = [
        ("1 Status Report Formats", [
            ("p", f"Three formats carry buffer status to the gateway. The short status report carries the status of one "
                  f"channel group in a buffer size field of {short.value} bits. The extended short status report also "
                  f"carries the status of one channel group, in a buffer size field of {ext.value} bits. The long status "
                  f"report carries up to {groups.value} channel groups, each in a buffer size field of "
                  f"{long_field.value} bits."),
        ]),
        ("2 Header Fields", [
            ("p", "Every packet starts with the header fields of Table 1, in order. Each length field gives the length of "
                  "the field that follows it."),
            ("table", "Table 1. Header fields", ["Field", "Length (bits)"],
             [["Version", version.value], ["Session ID Length", sid_len.value], ["Session ID", f"up to {sid.value}"],
              ["Packet Number Length", pn_len.value], ["Packet Number", f"up to {pn.value}"]]),
        ]),
        ("3 Measurement Report", [
            ("p", "The measurement report contains, in this order:"),
            ("p", f"– the serving cell index, {cell.value} bits;"),
            ("p", f"– the beam index, {beam.value} bits;"),
            ("p", f"– the received signal strength, {rssi.value} bits;"),
            ("p", f"– the timing advance, {ta.value} bits."),
        ]),
        ("4 Link Failure Detection", [
            ("p", "A link failure is declared when any of the following conditions holds."),
            ("p", f"Condition 1: no acknowledgement is received within {ack.value} ms."),
            ("p", f"Condition 2: {retx.value} consecutive retransmissions fail."),
            ("p", f"Condition 3: the signal-to-noise ratio stays below {snr.value} dB for {low.value} s."),
        ]),
        ("5 Timers by Link State", [
            ("p", "When the link is congested, the following values apply."),
            ("p", f"The retransmission timer is {timer_busy.value} ms. The send window is {window_busy.value} packets."),
            ("p", "When the link is idle, the following values apply."),
            ("p", f"The retransmission timer is {timer_idle.value} ms. The send window is {window_idle.value} packets."),
        ]),
    ]
    return Project(f"spec-s{seed}", "Lakeshore Telemetry Link: Protocol Specification", F, sections)

PROJECTS = {"wtp": water_treatment, "coaster": roller_coaster, "spec": link_protocol}

# --- table knobs (milestone 2) -------------------------------------------------------------------
# Schedules rendered clean or with one knob, the same facts either way, so a knob's effect is the difference.
# The situations come from documents read so far (the plan's catalogue): a second table stacked under a
# section row that relabels the columns (spot check sc01, HabEx p4), grouped headers, two values in a cell,
# dense tables (the eye tests), and tables continued across a page break.
TABLE_KNOBS = ("clean", "stacked", "multilevel", "multivalue", "dense", "continued", "all")

@dataclass
class Column:
    label: str          # the leaf label, unit included: "Capacity (gpm)"
    attribute: str      # the fact's attribute
    synonyms: tuple = ()
    unit: str = ""
    group: str = ""     # a spanning header above it (multilevel)

@dataclass
class Schedule:
    """A table of rows by section: each section has its own columns (a stacked section row relabels them)."""
    caption: str
    sections: list      # [(title, entity kind, [Column], [(tag, [value cells])])]
    merge: tuple = ()   # (i, j, label): two columns shown as one cell, "a<br/>b" (multivalue)
    split: int = 0      # rows per small table when clean (a dense schedule split up)

def _schedule_facts(d, sections, F):
    """Draw each cell's value as a fact; returns the sections with values filled in."""
    out = []
    for title, kind, columns, tags, ranges in sections:
        rows = []
        for tag in tags:
            name = f"{kind} {tag}"
            cells = []
            for col, (lo, hi, dec) in zip(columns, ranges):
                f = Fact(f"{tag}.{col.attribute}", name, (tag, f"{kind.lower()} {tag}"), col.attribute, col.synonyms,
                         d.number(lo, hi, dec), col.unit, drawn="table")
                F.append(f)
                cells.append(f.value)
            rows.append((tag, cells))
        out.append((title, kind, columns, rows))
    return out

def equipment_schedules(seed=1):
    """The water treatment plant's equipment schedules: pumps with blowers stacked under them, and valves."""
    d = Draw(f"wtp-tables-{seed}")
    F = []
    pump_cols = [Column("Capacity (gpm)", "capacity", ("flow", "rated flow", "rated capacity"), "gpm", "Rated point"),
                 Column("TDH (ft)", "total dynamic head", ("TDH", "head", "rated head"), "ft", "Rated point"),
                 Column("Power (hp)", "motor power", ("power", "motor", "motor rating"), "hp", "Motor"),
                 Column("Speed (rpm)", "motor speed", ("speed", "rpm"), "rpm", "Motor")]
    blower_cols = [Column("Airflow (scfm)", "airflow", ("flow", "air flow", "capacity"), "scfm", "Rated point"),
                   Column("Pressure (psig)", "discharge pressure", ("pressure", "outlet pressure"), "psig", "Rated point"),
                   Column("Power (hp)", "motor power", ("power", "motor", "motor rating"), "hp", "Motor"),
                   Column("Speed (rpm)", "motor speed", ("speed", "rpm"), "rpm", "Motor")]
    valve_cols = [Column("Cv", "flow coefficient", ("Cv", "valve coefficient"), ""),
                  Column("Rating (psi)", "pressure rating", ("rating", "pressure class"), "psi"),
                  Column("Stroke time (s)", "stroke time", ("opening time", "closing time"), "s")]
    pumps = _schedule_facts(d, [
        ("Raw water pumps", "Pump", pump_cols, ["P-101A", "P-101B", "P-101C"],
         [(4000, 9000, 0), (60, 140, 1), (100, 300, 0), (1150, 1790, 0)]),
        ("Process air blowers", "Blower", blower_cols, ["B-401", "B-402", "B-403"],
         [(1500, 4000, 0), (6, 9, 2), (40, 99, 0), (3000, 3600, 0)])], F)
    valves = _schedule_facts(d, [
        ("Valves", "Valve", valve_cols, [f"V-3{k:02d}" for k in range(1, 21)],
         [(150, 4800, 0), (125, 300, 0), (10, 90, 1)])], F)
    sections = [
        ("1 Equipment", [
            ("p", "The schedules below list the plant's pumps, blowers and valves at their rated points."),
            ("schedule", Schedule("Table 1. Pumps and blowers", pumps, merge=(2, 3, "Motor (hp / rpm)"))),
            ("schedule", Schedule("Table 2. Valve schedule", valves, split=5)),
        ])]
    return Project(f"wtp-tables-s{seed}", "Harrow Creek WTP: Equipment Schedules", F, sections)

def track_schedules(seed=1):
    """The roller coaster's schedules: track elements with brakes stacked under them, and support columns."""
    d = Draw(f"coaster-tables-{seed}")
    F = []
    element_cols = [Column("Height (ft)", "height", ("element height", "top height"), "ft", "Geometry"),
                    Column("Entry speed (mph)", "entry speed", ("speed", "entrance speed"), "mph", "Dynamics"),
                    Column("Vertical g", "peak vertical g", ("vertical g", "peak g", "g-force"), "g", "Dynamics"),
                    Column("Lateral g", "peak lateral g", ("lateral g", "side g"), "g", "Dynamics")]
    brake_cols = [Column("Length (ft)", "length", ("brake length", "section length"), "ft", "Geometry"),
                  Column("Entry speed (mph)", "entry speed", ("speed", "entrance speed"), "mph", "Dynamics"),
                  Column("Exit speed (mph)", "exit speed", ("leaving speed", "final speed"), "mph", "Dynamics"),
                  Column("Fins", "brake fins", ("fins", "fin count", "number of fins"), "", "Dynamics")]
    column_cols = [Column("Footing (ft)", "footing width", ("footing", "footing size"), "ft"),
                   Column("Load (kips)", "design load", ("load", "column load"), "kips"),
                   Column("Base elev. (ft)", "base elevation", ("elevation", "base"), "ft")]
    elements = _schedule_facts(d, [
        ("Track elements", "Element", element_cols, ["E1", "E2", "E3", "E4", "E5"],
         [(40, 175, 0), (40, 64, 1), (1.5, 4.5, 2), (0.3, 1.4, 2)]),
        ("Brakes", "Brake", brake_cols, ["BR1", "BR2", "BR3"],
         [(30, 120, 0), (20, 60, 1), (5, 19, 1), (12, 48, 0)])], F)
    columns = _schedule_facts(d, [
        ("Support columns", "Column", column_cols, [f"C-{k:02d}" for k in range(1, 21)],
         [(4, 12, 1), (50, 400, 0), (700, 760, 1)])], F)
    sections = [
        ("1 Track and Structure", [
            ("p", "Element heights are above the station platform; speeds are design values at the element's entry."),
            ("schedule", Schedule("Table 1. Track elements and brakes", elements, merge=(2, 3, "g (vertical / lateral)"))),
            ("schedule", Schedule("Table 2. Support columns", columns, split=5)),
        ])]
    return Project(f"coaster-tables-s{seed}", "Ridgeback: Track and Structure Schedules", F, sections)

TABLE_PROJECTS = {"wtp-tables": equipment_schedules, "coaster-tables": track_schedules}

# --- prose and layout knobs (milestone 2b) -----------------------------------------------------------
# Traps from the spot check (sc01 items 1-3) and earlier reviews, as phrasings: alternatives under comparison
# (the "2 ton unit" read as a condition), a scope phrase ("across the four mission concepts"), a table whose
# subject is named only in its caption, a requirement and a negation, a range, an abbreviation defined in another
# section, and a component of a component. Each fact has a plain phrasing (clean) and the trap's (traps). Layout
# knobs: page furniture (a running header of numbers that aren't facts) and two columns.
PROSE_KNOBS = ("clean", "traps", "furniture", "two-column", "all")

def convention_center(seed=1):
    """A convention centre expansion's design basis, written to the traps above."""
    d = Draw(f"lcc-{seed}")
    F = []
    add = lambda *a, **k: F.append(Fact(*a, **k)) or F[-1]
    hall = ("Hall C", ("Hall C", "exhibit hall C", "the new hall", "Hall C exhibit hall"))
    area = add("hallc.area", *hall, "exhibit floor area", ("floor area", "exhibit area", "area"), d.number(90000, 160000), "ft²")
    height = add("hallc.height", *hall, "clear ceiling height", ("ceiling height", "clear height"), d.number(28, 45), "ft")
    occupancy = add("hallc.occupancy", *hall, "occupant load", ("occupancy", "capacity", "occupants"),
                    d.number(6000, 14000), "persons")
    total = add("halls.area", "Halls A to D", ("Halls A-D", "the four halls", "all halls", "convention center"),
                "total exhibit area", ("combined exhibit area", "total area"), d.number(400000, 600000), "ft²",
                "across the four halls")
    noise = add("hallc.noise", *hall, "background noise limit", ("noise level", "background noise", "noise criterion"),
                d.number(38, 48), "dBA", "maximum", basis="required")
    live = add("hallc.liveload", *hall, "floor live load", ("live load", "design live load"), d.number(250, 400), "psf",
               "minimum", basis="required")
    snow = add("roof.snow", "Existing roof", ("existing roof", "roof", "the roof"), "snow load rating",
               ("rated snow load", "snow load", "snow rating"), d.number(25, 40), "psf", "maximum", basis="required")
    t_low = add("hallc.tmin", *hall, "minimum indoor design temperature", ("indoor temperature", "design temperature"),
                d.number(66, 70), "°F")
    t_high = add("hallc.tmax", *hall, "maximum indoor design temperature", ("indoor temperature", "design temperature"),
                 d.number(74, 78), "°F")
    ahu = ("AHU-3", ("air handling unit 3", "AHU 3", "air handler 3"))
    airflow = add("ahu3.airflow", *ahu, "supply airflow", ("airflow", "air flow", "supply air"), d.number(40000, 90000), "cfm")
    motor = add("ahu3.fanmotor", "AHU-3 supply fan motor", ("supply fan motor", "AHU-3 supply fan", "fan motor"),
                "motor power", ("power", "motor rating", "rating"), d.number(60, 200), "hp")
    beams = ("Option 1, chilled beams", ("Option 1", "chilled beams", "chilled beam option"))
    vav = ("Option 2, VAV baseline", ("Option 2", "VAV", "VAV baseline", "variable air volume"))
    beams_load = add("opt1.load", *beams, "peak cooling load", ("cooling load", "peak load"), d.number(700, 1000), "tons")
    vav_load = add("opt2.load", *vav, "peak cooling load", ("cooling load", "peak load"), d.number(1050, 1400), "tons")
    beams_cost = add("opt1.cost", *beams, "first cost", ("cost", "capital cost"), d.number(14.0, 22.0, 1), "$M")
    vav_cost = add("opt2.cost", *vav, "first cost", ("cost", "capital cost"), d.number(9.0, 13.5, 1), "$M")
    rooms = []
    for r in ("101", "102", "103", "104"):
        room = (f"Hall C meeting room {r}", (f"room {r}", f"meeting room {r}", r))
        rooms.append((r, add(f"room{r}.seats", *room, "seated capacity", ("capacity", "seats", "seating"),
                             d.number(60, 480), "persons", "Hall C"),  # under traps, named only in the caption
                      add(f"room{r}.area", *room, "floor area", ("area",), d.number(1500, 6000), "ft²", "Hall C")))
    texts = {  # (plain, trap)
        "intro": ("Hall C adds an exhibit floor area of {area} ft² to the convention center, with a clear ceiling height "
                  "of {height} ft and an occupant load of {occ} persons. The four halls together will offer {total} ft² "
                  "of exhibit space.",
                  "Hall C adds {area} ft² of exhibit floor under a {height} ft clear ceiling, for {occ} occupants. Across "
                  "the four halls, the total exhibit area becomes {total} ft²."),
        "criteria": ("Hall C's background noise limit is {noise} dBA. Its floor live load is at least {live} psf. The "
                     "existing roof's snow load rating is {snow} psf, and no higher. Hall C's indoor design temperature "
                     "ranges from {tmin} °F to {tmax} °F.",
                     "Background noise in Hall C shall not exceed {noise} dBA, and its floor shall carry a live load of "
                     "no less than {live} psf. The existing roof is not rated for snow loads above {snow} psf. Indoor "
                     "conditions are held between {tmin} and {tmax} °F."),
        "ahu": ("Air handling units (AHUs) serve the hall. AHU-3 supplies {airflow} cfm. The AHU-3 supply fan motor is "
                "rated {motor} hp.",
                "Air handling units (AHUs) serve the hall. {airflow} cfm comes from AHU-3, whose supply fan is driven by "
                "a {motor} hp motor."),
        "options": ("Option 1, chilled beams: peak cooling load {l1} tons, first cost ${c1}M. Option 2, a VAV baseline: "
                    "peak cooling load {l2} tons, first cost ${c2}M.",
                    "With chilled beams the peak cooling load drops to {l1} tons, against {l2} tons for the VAV baseline, "
                    "though their first cost of ${c1}M exceeds the baseline's ${c2}M."),
    }
    values = dict(area=area.value, height=height.value, occ=occupancy.value, total=total.value, noise=noise.value,
                  live=live.value, snow=snow.value, tmin=t_low.value, tmax=t_high.value, airflow=airflow.value,
                  motor=motor.value, l1=beams_load.value, l2=vav_load.value, c1=beams_cost.value, c2=vav_cost.value)
    room_rows = [[f"Room {r}", s.value, a.value] for r, s, a in rooms]
    sections = [
        ("1 Project Description", [("text", "intro"), ("p", LCC_PROSE["site"]), ("p", LCC_PROSE["program"])]),
        ("2 Design Criteria", [("text", "criteria"), ("p", LCC_PROSE["criteria"])]),
        ("3 Mechanical", [("p", LCC_PROSE["mechanical"]), ("text", "ahu"), ("p", LCC_PROSE["controls"])]),
        ("4 Cooling Options", [("p", LCC_PROSE["options"]), ("text", "options"), ("p", LCC_PROSE["choice"])]),
        ("5 Meeting Rooms", [("p", LCC_PROSE["rooms"]),
            ("rooms", ("Table 1. Meeting rooms in Hall C", "Table 1. Meeting rooms"),
             ["Room", "Seated capacity", "Area (ft²)"], room_rows)]),
        ("6 Construction Phasing", [("p", LCC_PROSE["phasing"])]),
    ]
    return Project(f"lcc-s{seed}", "Lakeshore Convention Center Expansion: Design Basis", F, sections, texts=texts,
                   values=values, kinds=PROSE_KNOBS)

# Number-free prose around the facts: it fills pages (so columns and running headers matter) without printing a
# number a reader could mistake for a fact.
LCC_PROSE = {
    "site": "The expansion occupies the former surface parking east of the existing building, between the lakefront "
            "promenade and the service road. Hall C connects to the existing concourse through a glazed link at the "
            "upper level, and its loading docks share the existing marshalling yard. The site slopes gently toward the "
            "lake, so the hall floor steps down from the concourse by a short ramp that meets accessibility guidance.",
    "program": "The program asks for column-free exhibit space that can be divided by operable walls, a block of "
               "flexible meeting rooms above the loading docks, and back-of-house corridors wide enough for forklifts. "
               "Food service is shared with the existing kitchens. Public circulation is kept on the lake side, where "
               "the façade is glazed and shaded by a deep roof overhang.",
    "criteria": "Criteria in this section govern the design of the new hall only. Where the existing building is "
                "affected, as at the roof of the glazed link, the existing documents govern unless this basis says "
                "otherwise. Acoustic criteria apply with the hall empty and all building systems running.",
    "mechanical": "The mechanical design favours few large air handling units on the roof, with ducts dropped through "
                  "the long-span trusses. Units are sized for a full hall on a design summer day, with outdoor air "
                  "set by occupancy sensors so that the units turn down when the hall is lightly used.",
    "controls": "All units report to the existing building automation system. Sequences are written so that one unit "
                "can be taken out of service for maintenance during move-in days without losing the hall.",
    "options": "Two cooling approaches were compared for the exhibit floor. Both use the existing central plant, "
               "extended with new chillers in the plant's spare bay.",
    "choice": "The design team recommends the chilled beam option for its lower plant load and quieter operation, "
              "subject to the owner's review of the first cost. A final choice is due at the end of schematic design.",
    "rooms": "The meeting rooms sit on a mezzanine above the loading docks, reached from the concourse by stairs and "
             "two passenger lifts. Rooms can be combined in pairs.",
    "phasing": "Construction proceeds while the existing halls stay open. The glazed link is built last, behind a "
               "temporary wall, so that events in the existing halls are not disturbed. Noisy work is scheduled "
               "outside show hours, and deliveries use the service road only.",
}

PROSE_PROJECTS = {"lcc": convention_center}

# --- charts (milestone 3a) -----------------------------------------------------------------------
# sc01 item 2: monthly use of two alternatives in a bar chart, and the text that summarises it. Knobs: the values
# printed above the bars (clean) or only readable against the axis; the chart as vector drawing or as an image;
# the legend in the chart or only in the caption; the whole page scanned (an image, no text layer).
CHART_KNOBS = ("clean", "axis", "raster", "legend-caption", "scan", "all")
SERIES_FILL = ((0.12, 0.23, 0.36), (0.55, 0.70, 0.86), (0.85, 0.55, 0.20))

@dataclass
class Chart:
    caption: str                 # "Figure 1. Monthly cooling energy"
    categories: list             # the labels under the axis
    series: list                 # [(name, [a Fact per category])]
    axis: str                    # the axis's title (its unit)
    step: float                  # the axis's labelled step; bars sit on multiples of half of it
    top: float
    legend_words: str = ""       # the series named in words, for a legend in the caption
    height: float = 210.0        # points
    kind: str = "grouped"        # grouped bars, stacked bars (each series a segment), or lines with markers

def energy_study(seed=1):
    """Hall C's cooling energy study: monthly energy of two options in a grouped bar chart, peak load by zone in
    another, and the text's totals."""
    d = Draw(f"lcc-energy-{seed}")
    F = []
    add = lambda *a, **k: F.append(Fact(*a, **k)) or F[-1]
    beams = ("Option 1, chilled beams", ("Option 1", "chilled beams", "chilled beam option", "chilled beam design"))
    vav = ("Option 2, VAV baseline", ("Option 2", "VAV", "VAV baseline", "variable air volume"))
    months = ("May", "June", "July", "August", "September", "October")
    season = (0.45, 0.75, 1.0, 0.95, 0.7, 0.4)
    series = []
    for (name, aliases), short, peak in ((beams, "opt1", d.rng.uniform(330, 420)), (vav, "opt2", d.rng.uniform(470, 560))):
        facts = [add(f"{short}.{m.lower()}", name, aliases, "cooling energy",
                     ("monthly cooling energy", "energy use", "cooling energy use", "energy", "monthly energy"),
                     d.slot(peak * k * d.rng.uniform(0.92, 1.08), 25), "MWh", m, drawn="chart")
                 for m, k in zip(months, season)]
        series.append((name, facts))
    zones = (("Exhibit floor", 150, 190), ("Meeting rooms", 60, 110), ("Concourse", 30, 70), ("Kitchens", 20, 50),
             ("Loading docks", 10, 30))
    zone_facts = [add(f"zone.{z.split()[0].lower()}", z, (z.lower(), f"{z.lower()} zone"), "peak cooling load",
                      ("cooling load", "peak load", "design cooling load"), d.slot(d.rng.uniform(lo, hi), 10), "tons",
                      "chilled beam design", drawn="chart") for z, lo, hi in zones]
    totals = []
    for (name, aliases), (_, facts), short in zip((beams, vav), series, ("opt1", "opt2")):
        text = f"{sum(f.number for f in facts):,.0f}"
        d.used.add(text)
        totals.append(add(f"{short}.season", name, aliases, "cooling season energy",
                          ("seasonal cooling energy", "total cooling energy", "season total", "cooling energy"),
                          text, "MWh", "cooling season"))  # not "May to October": no month's words
    demand = [add("opt1.demand", *beams, "peak electrical demand", ("peak demand", "electrical demand", "demand"),
                  d.number(900, 1250), "kW"),
              add("opt2.demand", *vav, "peak electrical demand", ("peak demand", "electrical demand", "demand"),
                  d.number(1300, 1700), "kW")]
    energy = Chart("Figure 1. Monthly cooling energy, May to October", list(months), series, "MWh", 50, 600,
                   "dark bars: Option 1, chilled beams; light bars: Option 2, VAV baseline")
    loads = Chart("Figure 2. Peak cooling load by zone, chilled beam design", [z for z, _, _ in zones],
                  [("Option 1, chilled beams", zone_facts)], "tons", 20, 200)
    plain = {
        "energy": "Figure 1 compares the two cooling options month by month over the cooling season, from May to "
                  "October. Over the season, chilled beams use {t1} MWh of cooling energy against {t2} MWh for the "
                  "VAV baseline.",
        "demand": "Peak electrical demand for cooling is {d1} kW with chilled beams and {d2} kW with the VAV baseline. "
                  "Figure 2 breaks the chilled beam design's peak cooling load down by zone.",
    }
    values = dict(t1=totals[0].value, t2=totals[1].value, d1=demand[0].value, d2=demand[1].value)
    sections = [
        ("1 Purpose", [("p", "This study estimates the cooling energy of the two options compared in the design "
                             "basis, to support the choice due at the end of schematic design. Both options were "
                             "modelled with the same weather file, schedules and internal gains.")]),
        ("2 Monthly Cooling Energy", [("text", "energy"), ("chart", energy),
                                      ("p", "The difference is largest in the peak months, when the VAV baseline moves "
                                            "the most air to meet the hall's sensible load.")]),
        ("3 Peak Loads", [("text", "demand"), ("chart", loads)]),
        ("4 Conclusions", [("p", "Chilled beams use less cooling energy in every month of the season. The saving "
                                 "should be weighed against their higher first cost, reported in the design basis.")]),
    ]
    return Project(f"lcc-energy-s{seed}", "Lakeshore Hall C: Cooling Energy Study", F, sections,
                   texts={k: (v, v) for k, v in plain.items()}, values=values, kinds=CHART_KNOBS)

def end_use_study(seed=1):
    """Hall C's energy by end use: monthly energy stacked by use (cooling, fans, lighting; sc01 item 2's stacked
    bars), the options' monthly peak loads as lines, and the season's totals in the text."""
    d = Draw(f"lcc-enduse-{seed}")
    F = []
    add = lambda *a, **k: F.append(Fact(*a, **k)) or F[-1]
    months = ("May", "June", "July", "August", "September", "October")
    season = (0.45, 0.75, 1.0, 0.95, 0.7, 0.4)
    uses = (("Cooling", (260, 340), ("cooling energy", "Hall C cooling", "space cooling")),
            ("Fans", (70, 100), ("fan energy", "Hall C fans", "fan")),
            ("Lighting", (40, 60), ("lighting energy", "Hall C lighting", "lights")))
    grid = lambda near, step: f"{max(step, round(near / step) * step):g}"  # bars read to half a step; may repeat
    stacked = []
    for use, (lo, hi), aliases in uses:
        peak = d.rng.uniform(lo, hi)
        stacked.append((use, [add(f"{use.lower()}.{m.lower()}", use, aliases, "energy use",
                                  ("energy", "monthly energy", "consumption", "energy consumption", "monthly use"),
                                  grid(peak * k * d.rng.uniform(0.9, 1.1), 25), "MWh", m, drawn="chart")
                              for m, k in zip(months, season)]))
    options = (("Option 1, chilled beams", ("Option 1", "chilled beams", "chilled beam option")),
               ("Option 2, VAV baseline", ("Option 2", "VAV", "VAV baseline", "variable air volume")))
    lines_ = []
    for (name, aliases), short, peak in zip(options, ("opt1", "opt2"), (d.rng.uniform(600, 700), d.rng.uniform(800, 900))):
        lines_.append((name, [add(f"{short}.{m.lower()}", name, aliases, "peak cooling load",
                                  ("cooling load", "peak load", "monthly peak load"),
                                  d.slot(peak * k * d.rng.uniform(0.94, 1.06), 50), "tons", m, drawn="chart")
                              for m, k in zip(months, season)]))
    totals = {}
    for use, facts in stacked:
        text = f"{sum(f.number for f in facts):,.0f}"
        d.used.add(text)
        totals[use] = add(f"{use.lower()}.season", use, dict((u, a) for u, _, a in uses)[use], "energy use",
                          ("energy", "season total", "seasonal energy", "total energy", "consumption"), text, "MWh",
                          "season")  # named as the months are, the season telling it apart ("cooling season" would
                                     # make every use's total a cooling one)
    use_chart = Chart("Figure 1. Hall C monthly energy by end use, May to October", list(months), stacked, "MWh", 50,
                      600, "dark: cooling; light: fans; orange: lighting", kind="stacked")
    load_chart = Chart("Figure 2. Monthly peak cooling load of the two options", list(months), lines_, "tons", 100,
                       1000, "circles: Option 1, chilled beams; squares: Option 2, VAV baseline", kind="line")
    plain = {"totals": "Over the cooling season, Hall C's cooling uses {c} MWh, its fans {f} MWh and its lighting {l} "
                       "MWh, as Figure 1 shows month by month. Figure 2 compares the two cooling options' peak loads."}
    values = dict(c=totals["Cooling"].value, f=totals["Fans"].value, l=totals["Lighting"].value)
    sections = [("1 Energy by End Use", [("text", "totals"), ("chart", use_chart)]),
                ("2 Peak Loads", [("p", "The two options' peak loads follow the season, rising to midsummer and "
                                        "falling after it."), ("chart", load_chart)])]  # true of any seed
    return Project(f"lcc-enduse-s{seed}", "Lakeshore Hall C: Energy by End Use", F, sections,
                   texts={k: (v, v) for k, v in plain.items()}, values=values, kinds=CHART_KNOBS)

CHART_PROJECTS = {"lcc-energy": energy_study, "lcc-enduse": end_use_study}

def charts(project):
    """The project's charts, in order (figure-1, figure-2, ...)."""
    return [block[1] for _, blocks in project.sections for block in blocks if block[0] == "chart"]

def draw_chart(page, rect, chart, values=True, legend=True, size=7.5):
    """Draw a bar chart into rect on a PyMuPDF page: an axis from 0 to its top, grouped bars, the categories under
    them, values printed above the bars (or not), a legend (or not). Returns [(fact, bar rect)] and the numbers
    drawn: [(text, facts, rect)]."""
    import pymupdf
    width = lambda t: pymupdf.get_text_length(t, fontname="helv", fontsize=size)
    text = lambda x, y, t: page.insert_text((x, y), t, fontname="helv", fontsize=size)
    ticks = [f"{k * chart.step:g}" for k in range(int(round(chart.top / chart.step)) + 1)]
    left = rect.x0 + max(width(t) for t in ticks) + 8
    plot = pymupdf.Rect(left, rect.y0 + 2.6 * size, rect.x1 - 4, rect.y1 - 2.2 * size)
    scale = plot.height / chart.top
    drawn, bars = [], []
    shape = page.new_shape()
    for t in ticks:
        y = plot.y1 - float(t) * scale
        shape.draw_line((plot.x0 - 3, y), (plot.x1, y))
    shape.finish(color=(0.78, 0.78, 0.78), width=0.5, closePath=False)
    shape.draw_line((plot.x0, plot.y0), (plot.x0, plot.y1))
    shape.draw_line((plot.x0, plot.y1), (plot.x1, plot.y1))
    shape.finish(color=(0, 0, 0), width=0.8, closePath=False)
    shape.commit()
    for t in ticks:
        x, y = plot.x0 - 5 - width(t), plot.y1 - float(t) * scale + size * 0.35
        text(x, y, t)
        drawn.append((t, [], pymupdf.Rect(x, y - size, x + width(t), y)))
    text(rect.x0, rect.y0 + size, chart.axis)  # the axis's title, above it
    group = plot.width / len(chart.categories)
    bar = group * 0.75 / len(chart.series)

    def label(fact, x, y, color=None):  # a value printed where it belongs, logged as drawn
        if color is None:
            text(x, y, fact.value)  # as grouped bars always were, so their pages draw byte for byte alike
        else:
            page.insert_text((x, y), fact.value, fontname="helv", fontsize=size, color=color)
        drawn.append((fact.value, [fact], pymupdf.Rect(x, y - size, x + width(fact.value), y)))

    if chart.kind == "line":  # each series a line through its points, marked; values beside the marks
        for s, (_, facts) in enumerate(chart.series):
            points = [(plot.x0 + (i + 0.5) * group, plot.y1 - f.number * scale) for i, f in enumerate(facts)]
            shape = page.new_shape()
            shape.draw_polyline(points)
            shape.finish(color=SERIES_FILL[s], width=1.4, closePath=False)
            for (x, y) in points:
                if s == 0:
                    shape.draw_circle((x, y), 2.6)
                else:
                    shape.draw_rect(pymupdf.Rect(x - 2.6, y - 2.6, x + 2.6, y + 2.6))
            shape.finish(color=SERIES_FILL[s], fill=SERIES_FILL[s], width=0.5)
            shape.commit()
            for i, (f, (x, y)) in enumerate(zip(facts, points)):
                bars.append((f, pymupdf.Rect(x - 3, y - 3, x + 3, y + 3)))
                if values:  # outside the lines: the higher point's value above it, the lower's below
                    others = [fs[i].number for _, fs in chart.series if fs[i] is not f]
                    above = all(f.number >= o for o in others)
                    label(f, x - width(f.value) / 2, y - 4 if above else y + size + 3)
    for i, category in enumerate(chart.categories):
        base = 0.0
        for s, (_, facts) in enumerate(chart.series):
            if chart.kind == "line":
                break
            fact = facts[i]
            if chart.kind == "stacked":  # one bar a category, each series a segment on the last
                x0 = plot.x0 + i * group + group * 0.25
                box = pymupdf.Rect(x0, plot.y1 - (base + fact.number) * scale, x0 + group * 0.5, plot.y1 - base * scale)
                base += fact.number
            else:
                x0 = plot.x0 + i * group + group * 0.125 + s * bar
                box = pymupdf.Rect(x0, plot.y1 - fact.number * scale, x0 + bar * 0.9, plot.y1)
            shape = page.new_shape()
            shape.draw_rect(box)
            if chart.kind == "stacked":  # segments parted by thin white lines
                shape.finish(color=(1, 1, 1), fill=SERIES_FILL[s], width=0.6)
            else:
                shape.finish(color=None, fill=SERIES_FILL[s], width=0)
            shape.commit()
            bars.append((fact, box))
            if values and chart.kind == "stacked":  # inside the segment, light on dark
                label(fact, box.x0 + box.width / 2 - width(fact.value) / 2, box.y0 + box.height / 2 + size / 3,
                      (1, 1, 1) if s == 0 else None)
            elif values:
                label(fact, box.x0 + box.width / 2 - width(fact.value) / 2, box.y0 - 2)
        text(plot.x0 + (i + 0.5) * group - width(category) / 2, plot.y1 + 1.5 * size, category)
    if legend and len(chart.series) > 1:
        x = plot.x1
        for s in reversed(range(len(chart.series))):
            name = chart.series[s][0]
            x -= width(name) + 2.2 * size
            shape = page.new_shape()
            shape.draw_rect(pymupdf.Rect(x, rect.y0 + 0.2 * size, x + size, rect.y0 + 1.2 * size))
            shape.finish(color=None, fill=SERIES_FILL[s], width=0)
            shape.commit()
            text(x + 1.4 * size, rect.y0 + 1.1 * size, name)
    return bars, drawn

def raster(page, rect, draw, dpi=150):
    """Draw onto a page of rect's size, and place the drawing on `page` as an image (a chart pasted as a picture)."""
    import pymupdf
    scratch = pymupdf.open()
    canvas = scratch.new_page(width=rect.width, height=rect.height)
    result = draw(canvas, pymupdf.Rect(0, 0, rect.width, rect.height))
    page.insert_image(rect, stream=canvas.get_pixmap(dpi=dpi, alpha=False).tobytes("png"))
    return result

def scanned(data, dpi=150):
    """The PDF as images only, one per page (a scan): no text layer."""
    import pymupdf
    src, out = pymupdf.open("pdf", data), pymupdf.open()
    for page in src:
        new = out.new_page(width=page.rect.width, height=page.rect.height)
        new.insert_image(new.rect, stream=page.get_pixmap(dpi=dpi, alpha=False).tobytes("png"))
    out.set_metadata({})
    return out.tobytes(garbage=3, deflate=True, no_new_id=True)
RUNNING_HEADER = "Lakeshore Convention Center · Doc LCC-HC-DB-004 · Rev C · 2026-03-14"

def corpus(seeds=(1,), knobs=False, revisions=False):
    """The clean corpus; with knobs, also each table project under every table knob, and each prose project under
    every prose knob (ids "<project>-<knob>"); with revisions, also each revision pair's generated side
    (revisions.py: the other side is a corpus document)."""
    out = [make(seed) for make in PROJECTS.values() for seed in seeds]
    if knobs:
        from .schematics import SCHEMATIC_KNOBS, SCHEMATIC_PROJECTS
        from .sheets import SHEET_KNOBS, SHEET_PROJECTS
        for makers, all_knobs in ((TABLE_PROJECTS, TABLE_KNOBS), (PROSE_PROJECTS, PROSE_KNOBS),
                                  (CHART_PROJECTS, CHART_KNOBS), (SCHEMATIC_PROJECTS, SCHEMATIC_KNOBS),
                                  (SHEET_PROJECTS, SHEET_KNOBS)):
            for make in makers.values():
                for seed in seeds:
                    for knob in all_knobs:
                        p = make(seed)
                        p.id, p.knob = f"{p.id}-{knob}", knob
                        out.append(p)
    if revisions:
        from .revisions import revised
        out += [project for seed in seeds for _, project in revised(seed)]
    return out

# --- rendering ---------------------------------------------------------------------------------

CSS = ("body {font-family: sans-serif; font-size: 10pt; line-height: 1.35} h1 {font-size: 16pt} h2 {font-size: 12pt} "
       "table {border-collapse: collapse; margin: 6pt 0} td, th {border: 1px solid #888; padding: 2px 6px} "
       "th {background-color: #1f3b5c; color: white} .caption {font-weight: bold; margin-top: 8pt}")

PAGE_BREAK = "<!--page-->"

def _esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def schedule_html(sched, knob, counter, breaks=()):
    """A schedule as HTML under a knob (see TABLE_KNOBS). counter numbers its tables across the document;
    breaks: the numbers of tables to start on a new page (so none is split but on purpose)."""
    on = lambda k: knob in (k, "all")
    merge = sched.merge if on("multivalue") else ()

    def cells(values):
        if merge:
            i, j, _ = merge
            values = values[:i] + [f"{_esc(values[i])}<br/>{_esc(values[j])}"] + values[j + 1:]
            return "".join(f"<td>{v}</td>" for v in values)
        return "".join(f"<td>{_esc(v)}</td>" for v in values)

    def labels(columns):
        names = [c.label for c in columns]
        if merge:
            i, j, label = merge
            names = names[:i] + [label] + names[j + 1:]
        return names

    def header(title, columns, first):
        names = labels(columns)
        if on("multilevel") and any(c.group for c in columns):
            groups, spans = [], []
            for c in columns if not merge else columns[:merge[0]] + [columns[merge[0]]] + columns[merge[1] + 1:]:
                if groups and groups[-1] == c.group:
                    spans[-1] += 1
                else:
                    groups.append(c.group)
                    spans.append(1)
            top = f"<tr><th rowspan='2'>{_esc(title)}</th>" + "".join(
                f"<th colspan='{n}'>{_esc(g)}</th>" for g, n in zip(groups, spans)) + "</tr>"
            return top + "<tr>" + "".join(f"<th>{_esc(n)}</th>" for n in names) + "</tr>"
        return f"<tr><th>{_esc(title)}</th>" + "".join(f"<th>{_esc(n)}</th>" for n in names) + "</tr>"

    def table(caption, parts):
        """parts: [(title, columns, rows)], drawn in one table, each under its own header row (stacked)."""
        number = next(counter)
        out = (PAGE_BREAK if number in breaks else "") + f"<p class='caption'>{_esc(caption)}</p><table id='schedule-{number}'>"
        for k, (title, columns, rows) in enumerate(parts):
            out += header(title, columns, k == 0)
            out += "".join(f"<tr{_last(number, k == len(parts) - 1 and r == len(rows) - 1)}><td>{_esc(tag)}</td>"
                           f"{cells(list(values))}</tr>" for r, (tag, values) in enumerate(rows))
        return out + "</table>"

    sections = [(title, columns, rows) for title, _, columns, rows in sched.sections]
    if len(sections) > 1:
        if on("stacked"):
            return table(sched.caption, sections)
        number, _, _ = sched.caption.partition(". ")  # clean: each section its own table, "Table 1a: Raw water pumps"
        return "".join(table(f"{number}{'abcdefgh'[k]}. {part[0]}", [part]) for k, part in enumerate(sections))
    title, columns, rows = sections[0]
    if sched.split and not (on("dense") or on("continued")):  # clean: small tables
        number, _, name = sched.caption.partition(". ")
        return "".join(table(f"{number}{'abcdefgh'[k]}. {name} ({k + 1} of {len(rows) // sched.split})",
                             [(title, columns, rows[i:i + sched.split])])
                       for k, i in enumerate(range(0, len(rows), sched.split)))
    if on("continued"):
        half = len(rows) // 2
        return (table(sched.caption, [(title, columns, rows[:half])]) + PAGE_BREAK +
                table(f"{sched.caption.split('.')[0]} (continued)", [(title, columns, rows[half:])]))
    return table(sched.caption, [(title, columns, rows)])

def _last(number, last):
    """A table's last row is marked, so layout sees where the table ends (Story notes a table only where it opens)."""
    return f" id='schedule-{number}-end'" if last else ""

def html(project, breaks=()):
    import itertools
    esc, counter, figures = _esc, itertools.count(1), itertools.count(1)
    out = [f"<h1>{esc(project.title)}</h1>"]
    for heading, blocks in project.sections:
        out.append(f"<h2>{esc(heading)}</h2>")
        for block in blocks:
            if block[0] == "p":
                out.append(f"<p>{esc(block[1])}</p>")
            elif block[0] == "schedule":
                out.append(schedule_html(block[1], project.knob, counter, breaks))
            elif block[0] == "text":
                plain, trap = project.texts[block[1]]
                text = (trap if project.has("traps") else plain).format(**project.values)
                out.append(f"<p>{esc(text)}</p>")
            elif block[0] == "intro":  # a schematic's description
                from .schematics import intro_html
                out.append(intro_html(block[1], esc))
            elif block[0] == "relations":  # a schematic's arrangement in words
                from .schematics import prose_html
                out.append(prose_html(project, block[1], esc))
            elif block[0] == "schematic":  # room for the figure, drawn after layout; its caption below
                from .schematics import figure_height, figure_style, has_figure
                if has_figure(project):
                    style = figure_style(project)
                    number = next(figures)
                    height = figure_height(block[1], 504, style["folded"], style["legend"])
                    out.append((PAGE_BREAK if f"figure-{number}" in breaks else "") +
                               f"<div id='figure-{number}' style='height:{height:g}pt'></div>"
                               f"<p class='caption'>{esc(block[1].caption)}</p>")
            elif block[0] == "chart":  # room for the chart, drawn after layout; its caption below
                chart = block[1]
                caption = chart.caption + (f" ({chart.legend_words})" if chart.legend_words and project.has("legend-caption")
                                           else "")
                number = next(figures)
                out.append((PAGE_BREAK if f"figure-{number}" in breaks else "") +
                           f"<div id='figure-{number}' style='height:{chart.height:g}pt'></div>"
                           f"<p class='caption'>{esc(caption)}</p>")
            elif block[0] == "rooms":  # the table's subject: in every row (clean), or only in the caption (traps)
                _, (caption_trap, caption_plain), header, rows = block
                trap = project.has("traps")
                caption = caption_trap if trap else caption_plain
                shown = rows if trap else [[f"Hall C {row[0].lower()}"] + row[1:] for row in rows]
                number = next(counter)
                out.append((PAGE_BREAK if number in breaks else "") +
                           f"<p class='caption'>{esc(caption)}</p><table id='schedule-{number}'><tr>" +
                           "".join(f"<th>{esc(h)}</th>" for h in header) + "</tr>" +
                           "".join(f"<tr{_last(number, r == len(shown) - 1)}>" + "".join(f"<td>{esc(c)}</td>" for c in row)
                                   + "</tr>" for r, row in enumerate(shown)) +
                           "</table>")
            else:
                _, caption, header, rows = block
                out.append(f"<p class='caption'>{esc(caption)}</p><table><tr>" +
                           "".join(f"<th>{esc(h)}</th>" for h in header) + "</tr>" +
                           "".join("<tr>" + "".join(f"<td>{esc(c)}</td>" for c in row) + "</tr>" for row in rows) +
                           "</table>")
    return "".join(out)

def render(project, page_size="letter"):
    """(pdf bytes, the printed numbers' log): the same project gives the same bytes."""
    import pymupdf
    if getattr(project, "sheet", None):  # a drawing sheet, drawn directly (sheets.py)
        from .sheets import render as render_sheet
        return render_sheet(project)
    rect = pymupdf.paper_rect(page_size)
    breaks = set()
    for _ in range(5):  # lay out; start any table Story split across pages on a new page; again
        buffer = io.BytesIO()
        writer = pymupdf.DocumentWriter(buffer)
        placed, pages = {}, {}  # page: schedule tables' boxes; table id: the (page, column)s it was drawn in
        figures = {}  # figure number: (page, the room left for it)
        spans = {}    # a sentence's links (by index): {page: its words' box}

        def note(position):
            ident = getattr(position, "id", "") or ""
            if ident.startswith("rel-"):
                at = spans.setdefault(ident, {})
                r = pymupdf.Rect(position.rect)
                at[position.page] = at[position.page] | r if position.page in at else r
            if ident.startswith("figure-") and position.open_close & 1:
                figures[int(ident.split("-")[1])] = (position.page, pymupdf.Rect(position.rect))
            if ident.startswith("schedule-"):
                pages.setdefault(ident.removesuffix("-end"), set()).add((position.page, position.column))
                if position.open_close & 1 and not ident.endswith("-end"):
                    placed.setdefault(position.page, []).append(tuple(position.rect))
        page = 0
        two = project.has("two-column")
        body = rect + (54, 54, -54, -72)
        columns = [pymupdf.Rect(body.x0, body.y0, body.x0 + body.width / 2 - 9, body.y1),
                   pymupdf.Rect(body.x0 + body.width / 2 + 9, body.y0, body.x1, body.y1)] if two else [body]
        for part in html(project, breaks).split(PAGE_BREAK):  # a page break starts the next part on a new page
            story = pymupdf.Story(html=part, user_css=CSS)
            more = True
            while more:
                page += 1
                device = writer.begin_page(rect)
                for c, column in enumerate(columns):  # one column, or two side by side
                    if not more:
                        break
                    more, _ = story.place(column)
                    story.element_positions(note, {"page": page, "column": c})
                    story.draw(device)
                writer.end_page()
        writer.close()
        split = {int(i.split("-")[1]) for i, p in pages.items() if len(p) > 1} - breaks
        # Story doesn't move a box of fixed height (a chart's room) to the next page: it overflows, and what
        # follows is lost. Such a box starts a page instead.
        split |= {f"figure-{n}" for n, (_, box) in figures.items() if box.y1 > body.y1 + 1} - breaks
        if not split:
            break
        breaks |= split
    else:
        raise ValueError(f"{project.id}: tables still split across pages after {len(breaks)} page breaks")
    doc = pymupdf.open("pdf", buffer.getvalue())
    for n, page in enumerate(doc, 1):  # page numbers: printed, so logged
        page.insert_text((rect.width / 2 - 20, rect.height - 36), f"Page {n} of {doc.page_count}", fontname="helv",
                         fontsize=8)
        if project.has("furniture"):  # a running header of numbers that aren't facts
            page.insert_text((54, 36), RUNNING_HEADER, fontname="helv", fontsize=8)
    drawn = draw_charts(project, doc, figures)
    project.chart_boxes = {n: (page_no, tuple(box)) for n, (page_no, box) in figures.items()  # for representations
                           if n <= len(charts(project))}
    if getattr(project, "schematic", None):
        drawn = draw_schematics(project, doc, figures, spans)
    doc.set_metadata({})
    data = doc.tobytes(garbage=3, deflate=True, no_new_id=True)
    log = locate(project, pymupdf.open("pdf", data), placed, drawn)
    return (scanned(data) if project.has("scan") else data), log

def draw_charts(project, doc, figures):
    """Draw each chart into the room left for it, as a drawing or a picture (raster), with or without its values
    (axis) and legend (legend-caption). Returns {page: [(chart box, [(fact, box)], [(number, facts, box)])]}: what
    was drawn where, since the drawer knows which number is a tick and which a value."""
    import pymupdf
    out = {}
    for number, chart in enumerate(charts(project), 1):
        page_no, box = figures[number]
        page = doc[page_no - 1]
        for _, facts in chart.series:
            for f in facts:
                f.tolerance = chart.step / 4 if project.has("axis") else 0.0
        draw = lambda pg, r, chart=chart: draw_chart(pg, r, chart, values=not project.has("axis"),
                                                      legend=not project.has("legend-caption"))
        if project.has("raster"):
            bars, numbers = raster(page, box, draw)
            shift = lambda r: pymupdf.Rect(r) + (box.x0, box.y0, box.x0, box.y0)
            bars, numbers = [(f, shift(b)) for f, b in bars], [(t, fs, shift(b)) for t, fs, b in numbers]
        else:
            bars, numbers = draw(page, box)
        out.setdefault(page_no, []).append((box, bars, numbers, "chart"))
    return out

def draw_schematics(project, doc, figures, spans):
    """Draw the schematic into its room, and place the facts stated in words where their sentences fell. Returns
    {page: [(figure box or None, [(fact, box)], [(number, facts, box)], form)]}, as draw_charts."""
    from .schematics import draw_system, figure_style, has_figure
    info = project.schematic
    system = info["system"]
    link_facts = [f for f in project.facts if f.relation]
    out = {}
    if has_figure(project):
        page_no, box = figures[1]
        placements, numbers = draw_system(doc[page_no - 1], box, system, link_facts, info["notes"],
                                          **figure_style(project))
        out.setdefault(page_no, []).append((box, placements, numbers, "figure"))
    for ident, pages in spans.items():
        links = [int(i) for i in ident.split("-")[1:]]
        for page_no, r in sorted(pages.items()):
            out.setdefault(page_no, []).append((None, [(link_facts[i], r) for i in links], [], "prose"))
    return out

def locate(project, doc, placed=None, drawn=None):
    """Find each fact's printed value on its pages (setting fact.forms), and log every number on the pages with
    its role: fact or distractor (by id), or structure (section, table and page numbers, anything else)."""
    by_value = {}
    for f in project.facts:
        if not f.relation:  # relations are placed by their drawer and their sentences, not found by number
            by_value.setdefault(printed_value(f.value), []).append(f)
        f.forms = []
    log = []
    for n, page in enumerate(doc, 1):
        table_boxes = [t.bbox for t in page.find_tables().tables] + list((placed or {}).get(n, []))
        chart_boxes = []
        for box, bars, numbers, form in (drawn or {}).get(n, []):  # figures: placed and logged as drawn
            if box is not None:
                chart_boxes.append(box)
            for fact, bar in bars:
                fact.forms.append({"form": form, "page": n, "box": [round(v, 1) for v in bar]})
            for text, facts, _ in numbers:
                log.append({"text": text, "page": n, "role": facts[0].role if facts else "structure",
                            "facts": [f.id for f in facts]})
        for w in page.get_text("words"):
            if any(b[0] - 1 <= w[0] and w[2] <= b[2] + 1 and b[1] - 1 <= w[1] and w[3] <= b[3] + 1 for b in chart_boxes):
                continue
            text = w[4].strip(",.;:()°")
            number = printed_value(text) if re.search(r"[0-9]", text) else None  # "ft²" is a unit, not a 2
            if number is None:
                continue
            facts = by_value.get(number, []) if re.match(r"[-+±$]?\d", text) else []  # "$15.2M" is printed money
            inside_table = any(b[0] - 1 <= w[0] and w[2] <= b[2] + 1 and b[1] - 1 <= w[1] and w[3] <= b[3] + 1
                               for b in table_boxes)
            for f in facts:
                f.forms.append({"form": f.drawn or ("table" if inside_table else "prose"), "page": n,
                                "box": [round(v, 1) for v in w[:4]]})
            log.append({"text": text, "page": n, "role": facts[0].role if facts else "structure",
                        "facts": [f.id for f in facts]})
    missing = [f.id for f in project.facts if not f.forms]
    if missing:
        raise ValueError(f"{project.id}: facts not found on the page: {missing}")
    return log

def key(project, log):
    """The answer key: facts with their forms, and the printed numbers with their roles."""
    optional = ("tolerance", "relation", "object_aliases", "accepts")  # left out when unused
    fields = lambda f: {k: v for k, v in asdict(f).items() if k not in optional or v}
    out = {"project": project.id, "title": project.title, "facts": [fields(f) for f in project.facts], "printed": log}
    if project.things:
        out["parts"] = [{"name": n, "aliases": list(a)} for n, a in project.things]
    if project.revision_of:
        out["revision_of"], out["edits"] = project.revision_of, project.edits
    return out

def write(project, folder):
    """Write <id>.pdf and <id>.key.json into folder; returns the PDF's path."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    data, log = render(project)
    pdf = folder / f"{project.id}.pdf"
    pdf.write_bytes(data)
    (folder / f"{project.id}.key.json").write_text(json.dumps(key(project, log), indent=1, ensure_ascii=False) + "\n",
                                                   encoding="utf-8")
    return pdf
