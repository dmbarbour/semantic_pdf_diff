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
  loose (the fact's value and attribute, a vague entity), misbound, misread (a non-fact number), hallucinated
  (a value printed nowhere), and facts missed.
"""
import io
import json
import random
import re
import unicodedata
from dataclasses import asdict, dataclass, field
from pathlib import Path

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

    @property
    def number(self):
        return parse_number(self.value)

def parse_number(text):
    """The first number in a value as printed ("1,250" → 1250.0, "-0.8" → -0.8, "±0.05" → 0.05), or None."""
    text = unicodedata.normalize("NFKC", str(text)).replace("−", "-").replace("–", "-")
    m = re.search(r"-?\d[\d,]*(?:\.\d+)?|-?\.\d+", text)
    if not m:
        return None
    try:
        return float(m.group(0).replace(",", ""))
    except ValueError:
        return None

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

# --- projects ----------------------------------------------------------------------------------

@dataclass
class Project:
    id: str
    title: str
    facts: list
    sections: list    # [(heading, [blocks])]; a block is ("p", text) or ("table", caption, header, rows)

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

PROJECTS = {"wtp": water_treatment, "coaster": roller_coaster}

def corpus(seeds=(1,)):
    return [make(seed) for make in PROJECTS.values() for seed in seeds]

# --- rendering ---------------------------------------------------------------------------------

CSS = ("body {font-family: sans-serif; font-size: 10pt; line-height: 1.35} h1 {font-size: 16pt} h2 {font-size: 12pt} "
       "table {border-collapse: collapse; margin: 6pt 0} td, th {border: 1px solid #888; padding: 2px 6px} "
       "th {background-color: #1f3b5c; color: white} .caption {font-weight: bold; margin-top: 8pt}")

def html(project):
    esc = lambda s: str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    out = [f"<h1>{esc(project.title)}</h1>"]
    for heading, blocks in project.sections:
        out.append(f"<h2>{esc(heading)}</h2>")
        for block in blocks:
            if block[0] == "p":
                out.append(f"<p>{esc(block[1])}</p>")
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
    buffer = io.BytesIO()
    story = pymupdf.Story(html=html(project), user_css=CSS)
    writer = pymupdf.DocumentWriter(buffer)
    rect = pymupdf.paper_rect(page_size)
    more = True
    while more:
        device = writer.begin_page(rect)
        more, _ = story.place(rect + (54, 54, -54, -72))
        story.draw(device)
        writer.end_page()
    writer.close()
    doc = pymupdf.open("pdf", buffer.getvalue())
    for n, page in enumerate(doc, 1):  # page numbers: printed, so logged
        page.insert_text((rect.width / 2 - 20, rect.height - 36), f"Page {n} of {doc.page_count}", fontname="helv",
                         fontsize=8)
    doc.set_metadata({})
    data = doc.tobytes(garbage=3, deflate=True, no_new_id=True)
    return data, locate(project, pymupdf.open("pdf", data))

def locate(project, doc):
    """Find each fact's printed value on its pages (setting fact.forms), and log every number on the pages with
    its role: fact or distractor (by id), or structure (section, table and page numbers, anything else)."""
    by_value = {}
    for f in project.facts:
        by_value.setdefault(f.value, []).append(f)
        f.forms = []
    log = []
    for n, page in enumerate(doc, 1):
        table_boxes = [t.bbox for t in page.find_tables().tables]
        for w in page.get_text("words"):
            text = w[4].strip(",.;:()°")
            if parse_number(text) is None:
                continue
            facts = by_value.get(text, [])
            inside_table = any(b[0] - 1 <= w[0] and w[2] <= b[2] + 1 and b[1] - 1 <= w[1] and w[3] <= b[3] + 1
                               for b in table_boxes)
            for f in facts:
                f.forms.append({"form": "table" if inside_table else "prose", "page": n,
                                "box": [round(v, 1) for v in w[:4]]})
            log.append({"text": text, "page": n, "role": facts[0].role if facts else "structure",
                        "facts": [f.id for f in facts]})
    missing = [f.id for f in project.facts if not f.forms]
    if missing:
        raise ValueError(f"{project.id}: facts not found on the page: {missing}")
    return log

def key(project, log):
    """The answer key: facts with their forms, and the printed numbers with their roles."""
    return {"project": project.id, "title": project.title, "facts": [asdict(f) for f in project.facts],
            "printed": log}

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

# --- scoring -----------------------------------------------------------------------------------

# Not "a": single letters name things (Option A, Module B, detail B4).
STOP = {"the", "an", "of", "for", "per", "each", "at", "in", "on", "to", "and", "with", "is", "value", "by", "its"}
# Words a reader may fairly use for one another (domain-neutral; a project's own synonyms are in its facts).
SAME = {"weight": "mass", "number": "count", "quantity": "count", "qty": "count", "velocity": "speed",
        "seating": "seat", "rider": "seat", "tonnage": "ton", "max": "maximum", "min": "minimum",
        "dia": "diameter", "temp": "temperature", "rated": "rating"}

def tokens(text):
    """A name's words: case-folded, hyphens split, stop words dropped, plurals and synonyms folded."""
    text = unicodedata.normalize("NFKC", str(text)).casefold().replace("-", " ")
    out = set()
    for t in re.findall(r"[a-z0-9]+", text):
        if t in STOP:
            continue
        if len(t) > 3 and t.endswith("s") and not t.endswith("ss"):
            t = t[:-1]
        out.add(SAME.get(t, t))
    return out

def vocabulary(fact):
    """Every word naming a fact: its entity and aliases, attribute and synonyms, and conditions."""
    return set().union(*(tokens(o) for o in (fact.entity, fact.attribute, fact.conditions) + tuple(fact.aliases)
                         + tuple(fact.synonyms)))

def fit(claim, fact, weights):
    """How well a claim's words (entity, attribute and conditions together, however it split them) describe a fact:
    the weighted share of them among the fact's words, rare words counting more (weights: see rarity)."""
    words = tokens(claim.get("entity", "")) | tokens(claim.get("attribute", "")) | tokens(claim.get("conditions", ""))
    total = sum(weights.get(w, weights[None]) for w in words)
    return sum(weights.get(w, weights[None]) for w in words & vocabulary(fact)) / total if total else 0.0

def rarity(facts):
    """{word: weight}: log(1 + facts / facts using the word); None for words no fact uses."""
    import math
    counts = {}
    for f in facts:
        for w in vocabulary(f):
            counts[w] = counts.get(w, 0) + 1
    n = len(facts)
    return {**{w: math.log(1 + n / c) for w, c in counts.items()}, None: math.log(1 + n)}

def same_number(a, b):
    return a is not None and b is not None and abs(a - b) <= 1e-9 * max(1.0, abs(a), abs(b))

def classify(claim, facts, printed):
    """(outcome, fact id or None) for one claim.

    A printed value names one fact (values are unique in a document), so the question is the binding: which fact
    the claim's names describe best. Right: the value's own fact fits best, alone. Loose: it ties for best (a bare
    "pump" among three pumps), or no name fits at all. Misbound: another fact fits better (the value filed under
    another entity or attribute). Distractor: a superseded or otherwise wrong value, bound to its own fact.
    Misread: a printed number that isn't a fact (a page or section number). Hallucinated: printed nowhere.
    Text: a value without a number, not scored yet."""
    number = parse_number(claim.get("value", ""))
    if number is None:
        return "text", None
    holders = [f for f in facts if same_number(f.number, number)]
    if holders:
        holder = holders[0]
        weights = rarity(facts)
        scores = {f.id: fit(claim, f, weights) for f in facts}
        best = max(scores.values())
        top = [i for i, v in scores.items() if v == best]
        by_id = {f.id: f for f in facts}
        if holder.id in top and all((by_id[i].entity, by_id[i].attribute) == (holder.entity, holder.attribute)
                                    for i in top):
            top = [holder.id]  # facts named alike (a superseded value and its successor): the value decides
        if best == 0 or (holder.id in top and len(top) > 1):
            return "loose", holder.id
        if top == [holder.id]:
            return ("right" if holder.role == "fact" else "distractor"), holder.id
        return "misbound", holder.id
    if any(same_number(parse_number(p["text"]), number) for p in printed):
        return "misread", None
    return "hallucinated", None

def score(key_data, claims):
    """Each claim classed, facts found and missed, and conditions kept, from a key and extracted claims (dicts
    with entity, attribute, value, unit, conditions)."""
    facts = [Fact(**{k: (tuple(v) if k in ("aliases", "synonyms") else v) for k, v in f.items()})
             for f in key_data["facts"]]
    by_id = {f.id: f for f in facts}
    outcomes, found, conditions = {}, {}, {}
    seen = set()
    for c in claims:
        ident = (str(c.get("entity", "")).casefold(), str(c.get("attribute", "")).casefold(), str(c.get("value", "")))
        if ident in seen:
            continue  # the same claim read twice (overlapping tiles) counts once
        seen.add(ident)
        outcome, fid = classify(c, facts, key_data["printed"])
        outcomes[outcome] = outcomes.get(outcome, 0) + 1
        if outcome in ("right", "loose") and fid:
            found.setdefault(fid, outcome)
            if outcome == "right":
                found[fid] = "right"
            want = by_id[fid].conditions
            if want and fid not in conditions or conditions.get(fid) is False:
                conditions[fid] = bool(tokens(want) & tokens(c.get("conditions", "")))
    real = [f for f in facts if f.role == "fact"]
    by_form = {}
    for f in real:
        for form in {x["form"] for x in f.forms}:
            got = by_form.setdefault(form, [0, 0])
            got[0] += f.id in found
            got[1] += 1
    return {"facts": len(real), "found": sum(1 for f in real if f.id in found),
            "recall": round(sum(1 for f in real if f.id in found) / len(real), 4),
            "found_right": sum(1 for v in found.values() if v == "right"),
            "missed": sorted(f.id for f in real if f.id not in found),
            "claims": sum(outcomes.values()), "outcomes": dict(sorted(outcomes.items())),
            "conditions_kept": f"{sum(conditions.values())}/{len(conditions)}",
            "recall_by_form": {k: round(v[0] / v[1], 4) for k, v in sorted(by_form.items())}}
