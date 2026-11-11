"""Proposal pairs (docs/plans/tentative-matches-2026-11-07.md, milestone 5): a corpus document and another design of
the same kind of thing, its items named its own way, so a comparison in proposals mode is scored by what each item
is, not what it's called.

A proposal is its corpus project drawn from another seed (its values its own), its items renamed (a facts' ids kept:
an id is the item's role in the template, so the two designs' "P-101A.capacity" and "IP-1"'s capacity are one role),
some roles kept alike (the filters), one role gone (the UV option), a decoy (a backwash pump: a pump, not an intake
pump), a property dropped from a role both keep (the clarifiers' surface loading rate) and one added (the flash
mixer's volume): gaps another source fills.

Three designs (milestone 5, extended 2026-11-08; the owner: "please proceed with milestone 4 and the answer-key
improvement for milestone 5", after asking whether the sample sufficed to judge asking both ways): Pine Ridge's and
Cedar Falls' design bases against Harrow Creek's, and the Cyclone roller coaster against Ridgeback. Each names its items
its own way, some by what they do rather than how they're spelled (clarifiers, a coagulation tank), so the model's
other names miss some; keeps others alike; drops a role; adds a decoy of a role it keeps; and drops one property and
adds another of items both keep.

A held-out template (HELDOUT_PAIRS; tentative matches, milestone 6, 2026-11-09: the weights passed their held-out rule
on new seeds of the templates they were fitted on, then made 9 plausible links of the turbine pair by names alone):
the Harbor Telemetry Link against the Lakeshore one, a protocol whose items are named alike by nature ("Session ID
Length field", "Session ID field"), renamed by role, with decoys named like its other items. Never in development's
corpus: `controlled.py heldout` makes and reads it.

Scored by comparison.score_proposals: matching by role (each subject's claims bound to the keys' facts, a fact's role
its id's), and the gaps another source fills.
"""
import re
from dataclasses import dataclass, replace

from .corpus import PROJECTS
from .model import Draw, Fact
from .revisions import PUMPS, add_row, add_sentence, convert, drawer, drop_row, rewrite

@dataclass
class Pair:
    id: str          # the pair
    earlier: str     # the documents' ids: the corpus's design first, the other second (no order between proposals)
    later: str

# Pine Ridge's names for Harrow Creek's items (the printed words, then each role's entity and aliases)
WORDS = (("Harrow Creek", "Pine Ridge"), ("The rapid mix basin provides", "The flash mixer provides"),
         ("sedimentation basins, each", "clarifiers, each"), ("Raw water pumps", "Intake pumps"),
         ("P-101A", "IP-1"), ("P-101B", "IP-2"), ("P-101C", "IP-3"),
         ("Alum is dosed at", "Ferric sulfate is dosed at"),
         ("Two options were compared for primary disinfection.", "One option was considered for primary "
                                                                   "disinfection."),
         ("Option B: chlorine contact", "Chlorine contact tank"))
ITEMS = {"Harrow Creek Water Treatment Plant": ("Pine Ridge Water Treatment Plant", ("Pine Ridge WTP", "the plant")),
         "Rapid mix basin": ("Flash mixer", ("flash mixer", "mixer")),
         "Sedimentation basins": ("Clarifiers", ("clarifier", "clarifiers")),
         "Raw water pump P-101A": ("Intake pump IP-1", ("IP-1", "intake pump IP-1")),
         "Raw water pump P-101B": ("Intake pump IP-2", ("IP-2", "intake pump IP-2")),
         "Raw water pump P-101C": ("Intake pump IP-3", ("IP-3", "intake pump IP-3")),
         "Alum feed": ("Ferric sulfate feed", ("ferric sulfate", "coagulant feed")),
         "Option B, chlorine contact basin": ("Chlorine contact tank", ("chlorine contact tank", "contact tank"))}
LOADING = re.compile(r"; the surface loading rate is [\d.,]+ gpm/ft² at design flow")

def _edit(project, edit, titles=False):
    """Every printed string edited: paragraphs, tables' captions, headers and cells; with titles, the sections'."""
    if titles:
        project.sections[:] = [(edit(title), blocks) for title, blocks in project.sections]
    for _, blocks in project.sections:
        for i, block in enumerate(blocks):
            if block[0] == "p":
                blocks[i] = ("p", edit(block[1]))
            elif block[0] == "table":
                blocks[i] = (block[0], edit(block[1]), [edit(c) for c in block[2]],
                             [[edit(c) for c in row] for row in block[3]], *block[4:])

def _drop_column(project, caption_word, column):
    """A table's column dropped (the table whose caption holds caption_word)."""
    for _, blocks in project.sections:
        for i, block in enumerate(blocks):
            if block[0] == "table" and caption_word in block[1]:
                blocks[i] = (block[0], block[1], block[2][:column] + block[2][column + 1:],
                             [row[:column] + row[column + 1:] for row in block[3]], *block[4:])
                return
    raise ValueError(f"{project.id}: no table of {caption_word}")

def _renamed(p, words, items, pattern=None, titles=False):
    """Every printed string's words replaced (words: [(old, new)]; pattern: a regex to strike; titles: the sections'
    too), and each role's entity and aliases (items: {old entity: (new entity, aliases)})."""
    def edit(text):
        for old, new in words:
            text = text.replace(old, new)
        return pattern.sub("", text) if pattern else text
    _edit(p, edit, titles)
    p.facts[:] = [f if f.entity not in items else replace(f, entity=items[f.entity][0], aliases=items[f.entity][1])
                  for f in p.facts]

def pine_ridge(seed):
    """Pine Ridge's design basis: Harrow Creek's template drawn from another seed, its items named its own way."""
    p = PROJECTS["wtp"](seed + 1)
    p.id, p.title = f"wtp-s{seed}-proposal", "Pine Ridge Water Treatment Plant"
    p.edits = []
    # the UV option isn't one of Pine Ridge's (a role gone); the clarifiers' loading rate not given (a gap)
    _drop_column(p, "Disinfection options", 1)
    gone = {f.id for f in p.facts if f.id.startswith("optA.")} | {"sed.loading"}

    def edit(text):
        for old, new in WORDS:
            text = text.replace(old, new)
        return LOADING.sub("", text)
    _edit(p, edit)
    p.facts[:] = [f if f.entity not in ITEMS else replace(f, entity=ITEMS[f.entity][0], aliases=ITEMS[f.entity][1])
                  for f in p.facts if f.id not in gone]
    p.edits.append({"kind": "removed", "facts": sorted(gone)})
    d = Draw(f"{p.id}-proposal")
    d.used |= {f.value for f in p.facts}
    mixer = p.fact("mix.g")
    # the flash mixer's volume, which Harrow Creek doesn't give (a gap); a backwash pump (a decoy for the intake pumps)
    add_sentence(p, "mix.g", "Its volume is {v} gal.",
                 Fact("mix.volume", mixer.entity, mixer.aliases, "volume", ("basin volume",), d.number(8000, 20000),
                      "gal"))
    add_sentence(p, "filters.rate", "A backwash pump delivers {v} gpm to the filters.",
                 Fact("bw.capacity", "Backwash pump", ("backwash pump", "the backwash pump"), "capacity",
                      ("flow", "rated flow"), d.number(3000, 6000), "gpm"))
    return p

def pine_ridge_metric(seed):
    """Pine Ridge's design basis in metric units (tentative matches, milestone 15's knob; the gotchas review, item 3:
    "150 psi and 1,034 kPa never meet"): the same design, its values the same quantities, its flows in m³/h, its
    basins in metres and its pumps in L/s, metres and kW; against Harrow Creek's, the Pine Ridge pair in imperial units
    is its control."""
    p = pine_ridge(seed)
    p.id = f"wtp-s{seed}-metric"
    convert(p, [(("plant.design_flow", "plant.peak_flow"), "m³/h", 694.444 / 4.40287, 0),
                (("sed.length", "sed.width", "sed.depth"), "m", 0.3048, 1),
                (tuple(f"{t}.capacity" for t in PUMPS) + ("bw.capacity",), "L/s", 1 / 15.8503, 1),
                (tuple(f"{t}.head" for t in PUMPS), "m", 0.3048, 1),
                (tuple(f"{t}.motor" for t in PUMPS), "kW", 0.7457, 0)],
            headers=(("Capacity (gpm)", "Capacity (L/s)"), ("TDH (ft)", "TDH (m)"), ("Motor (hp)", "Motor (kW)")))
    return p

SPRUCE_WORDS = (("Harrow Creek", "Spruce Lake"), ("Filtration uses", "Granular filtration uses"),
                ("dual-media filters", "granular media beds"), ("With one filter out of service",
                                                                "With one bed out of service"))
SPRUCE_ITEMS = {"Harrow Creek Water Treatment Plant": ("Spruce Lake Water Treatment Plant", ("Spruce Lake WTP",
                                                                                              "the plant")),
                "Filters": ("Granular media beds", ("granular media beds", "media beds", "filter beds"))}
# Harrow Creek's sections as Spruce Lake titles and orders them, a building services section among them
SPRUCE_SECTIONS = (("Design Basis", "Basis of Design"), (None, "Building Services"),
                   ("Chemical Feed", "Chemical Systems"), ("Treatment Process", "Process Units"),
                   ("Disinfection Options", "Disinfection"))

def spruce_lake(seed):
    """Spruce Lake's design basis (tentative matches, milestone 9: test material for place and use): Harrow Creek's
    template from a seed further on, its sections renamed and reordered (Harrow Creek's "2 Treatment Process" its "4
    Process Units"), its filters named granular media beds, and in a building services section ahead of them the air
    handling units' filters, a schedule's column named as Harrow Creek names its own and given by the same three
    properties (a decoy only where it is, and what it serves, can tell apart; written as a sentence, the reader named
    it "administration building air handling unit filter", 2026-11-11)."""
    p = PROJECTS["wtp"](seed + 4)
    p.id, p.title = f"wtp-s{seed}-spruce", "Spruce Lake Water Treatment Plant"
    p.edits = []
    _renamed(p, SPRUCE_WORDS, SPRUCE_ITEMS)
    d = Draw(f"{p.id}-proposal")
    d.used |= {f.value for f in p.facts}
    # the key names the decoy apart (the scorer's items are its entities); the page names it as a schedule would
    aliases = ("filters", "air filters", "building filters")
    count, area, rate = d.number(18, 40), d.number(3, 8, 1), d.number(250, 500)
    decoy = [Fact("air.count", "Building filters", aliases, "number of filters", ("count", "filter count"), count, ""),
             Fact("air.area", "Building filters", aliases, "area per filter", ("filter area", "area"), area, "ft²"),
             Fact("air.rate", "Building filters", aliases, "filtration rate", ("loading rate",), rate, "cfm/ft²")]
    services = [("p", "The administration building's air handling units are served as follows."),
                ("table", "Table 3. Filters", ["", "Filters"],
                 [["Number of filters", count], ["Area per filter (ft²)", area], ["Filtration rate (cfm/ft²)", rate]])]
    by = {title.split(" ", 1)[1]: blocks for title, blocks in p.sections}
    layout = [(new, by[old] if old else services) for old, new in SPRUCE_SECTIONS]
    p.sections[:] = [(f"{k} {title}", blocks) for k, (title, blocks) in enumerate(layout, 1)]
    p.facts.extend(decoy)
    p.edits.append({"kind": "added", "facts": [f.id for f in decoy]})
    return p

CEDAR_WORDS = (("Harrow Creek", "Cedar Falls"), ("The rapid mix basin provides", "The coagulation tank provides"),
               ("Flocculation follows in", "Slow mixing follows in"),
               ("sedimentation basins, each", "settling basins, each"), ("Raw water pumps", "Low-lift pumps"),
               ("P-101A", "LL-1"), ("P-101B", "LL-2"), ("P-101C", "LL-3"),
               ("Chlorine is fed at", "Sodium hypochlorite is fed at"),
               ("Two options were compared for primary disinfection.", "One option was considered for primary "
                                                                         "disinfection."),
               ("Option A: UV", "Ultraviolet reactors"))
CEDAR_ITEMS = {"Harrow Creek Water Treatment Plant": ("Cedar Falls Water Treatment Plant", ("Cedar Falls WTP",
                                                                                            "the plant")),
               "Rapid mix basin": ("Coagulation tank", ("coagulation tank",)),
               "Flocculation basins": ("Slow mixing tanks", ("slow mixing", "slow mixers")),
               "Sedimentation basins": ("Settling basins", ("settling basin", "settling basins")),
               "Raw water pump P-101A": ("Low-lift pump LL-1", ("LL-1", "low-lift pump LL-1")),
               "Raw water pump P-101B": ("Low-lift pump LL-2", ("LL-2", "low-lift pump LL-2")),
               "Raw water pump P-101C": ("Low-lift pump LL-3", ("LL-3", "low-lift pump LL-3")),
               "Chlorine feed": ("Sodium hypochlorite feed", ("sodium hypochlorite", "hypochlorite feed")),
               "Option A, UV disinfection": ("Ultraviolet reactors", ("UV reactors", "ultraviolet"))}
FINISHED = re.compile(r" ?Finished water turbidity shall not exceed [\d.,]+ NTU in 95% of monthly samples\.")

def cedar_falls(seed):
    """Cedar Falls' design basis: Harrow Creek's template from a seed further on, named its own way again; the
    chlorine contact option gone, a sludge pump (a decoy for the low-lift pumps), the finished water's turbidity
    limit not given and the filters' backwash rate given (2 gaps)."""
    p = PROJECTS["wtp"](seed + 2)
    p.id, p.title = f"wtp-s{seed}-cedar", "Cedar Falls Water Treatment Plant"
    p.edits = []
    _drop_column(p, "Disinfection options", 2)
    gone = {f.id for f in p.facts if f.id.startswith("optB.")} | {"plant.finished_turbidity"}
    _renamed(p, CEDAR_WORDS, CEDAR_ITEMS, FINISHED)
    p.facts[:] = [f for f in p.facts if f.id not in gone]
    p.edits.append({"kind": "removed", "facts": sorted(gone)})
    d = Draw(f"{p.id}-proposal")
    d.used |= {f.value for f in p.facts}
    filters = p.fact("filters.rate")
    add_sentence(p, "filters.rate", "The filters are backwashed at {v} gpm/ft².",
                 Fact("filters.backwash", filters.entity, filters.aliases, "backwash rate", ("backwash",),
                      d.number(15, 22, 1), "gpm/ft²"))
    add_sentence(p, "mix.g", "A sludge pump moves {v} gpm from the basins.",
                 Fact("sludge.capacity", "Sludge pump", ("sludge pump", "the sludge pump"), "capacity",
                      ("flow", "rated flow"), d.number(150, 600), "gpm"))
    return p

CYCLONE_WORDS = (("Ridgeback", "Cyclone"), ("The lift hill rises", "The chain lift rises"),
                 ("First drop", "Main drop"), ("first drop", "main drop"), ("Zero-g roll", "Heartline roll"),
                 ("Camelback", "Airtime hill"), ("support columns", "steel bents"))
CYCLONE_ITEMS = {"Lift hill": ("Chain lift", ("chain lift", "lift")), "First drop": ("Main drop", ("main drop",
                                                                                                  "drop")),
                 "Ridgeback roller coaster": ("Cyclone roller coaster", ("Cyclone", "the ride", "the coaster")),
                 "Zero-g roll": ("Heartline roll", ("heartline roll",)),
                 "Camelback": ("Airtime hill", ("airtime hill",)),
                 "Support structure": ("Steel structure", ("steel bents", "structure"))}
G_MAX = re.compile(r", and the maximum vertical acceleration is [\d.]+ g")

def cyclone(seed):
    """The Cyclone roller coaster: Ridgeback's template from the next seed, named its own way (a chain lift, a main
    drop, a heartline roll, an airtime hill, steel bents), its helix gone, a bunny hop (a decoy for the airtime hill),
    its maximum vertical acceleration not given and its trains' length given (2 gaps)."""
    p = PROJECTS["coaster"](seed + 1)
    p.id, p.title = f"coaster-s{seed}-proposal", "Cyclone roller coaster"
    p.edits = []
    old, lift = p.fact("ride.lift_old"), p.fact("ride.lift")
    rewrite(p, f"In revision B the lift hill was raised from {old.value} ft to {lift.value} ft.",
            f"The lift hill rises {lift.value} ft.")  # a design, not a revision: no superseded height
    p.facts.remove(old)
    d = drawer(p)
    add_row(p, "Camelback", "Bunny hop", d)
    drop_row(p, "Helix")
    _renamed(p, CYCLONE_WORDS, CYCLONE_ITEMS, G_MAX)
    p.facts[:] = [f for f in p.facts if f.id != "ride.g_max"]
    p.edits.append({"kind": "removed", "facts": ["ride.g_max"]})
    trains = p.fact("trains.mass")
    add_sentence(p, "trains.mass", "Each train is {v} ft long.",
                 Fact("trains.length", trains.entity, trains.aliases, "train length", ("length",),
                      d.number(52, 78), "ft"))
    return p

BIRCH_WORDS = (("Harrow Creek", "Birch Hollow"), ("P-101A", "P-201A"), ("P-101B", "P-201B"), ("P-101C", "P-201C"))
BIRCH_ITEMS = {"Harrow Creek Water Treatment Plant": ("Birch Hollow Water Treatment Plant", ("Birch Hollow WTP",
                                                                                              "the plant")),
               "Raw water pump P-101A": ("Raw water pump P-201A", ("P-201A", "pump P-201A", "raw water pump P-201A")),
               "Raw water pump P-101B": ("Raw water pump P-201B", ("P-201B", "pump P-201B", "raw water pump P-201B")),
               "Raw water pump P-101C": ("Raw water pump P-201C", ("P-201C", "pump P-201C", "raw water pump P-201C"))}
# Harrow Creek's raw water pump tags on Birch Hollow's other pumps: (tag, the pump, its role's id, the fact its sentence
# follows, what it does)
BIRCH_TAGGED = (("P-101A", "Backwash pump", "bw", "filters.rate", "delivers {v} gpm to the filters"),
                ("P-101B", "Sludge pump", "sludge", "sed.depth", "moves {v} gpm of sludge from the basins"),
                ("P-101C", "Washwater recycle pump", "recycle", "plant.design_flow",
                 "returns {v} gpm of washwater to the head of the plant"))

def birch_hollow(seed):
    """Birch Hollow's design basis (tentative matches, milestone 14's knob; the gotchas review, item 2: "P-101 in two
    designs is a numbering habit, not identity"): Harrow Creek's template from a seed further on, its items named as
    Harrow Creek names them but its raw water pumps tagged P-201A to C, and Harrow Creek's tags P-101A to C on its
    backwash, sludge and washwater recycle pumps, each a capacity and a head as the raw water pumps have: a tag in
    both designs, another role in each."""
    p = PROJECTS["wtp"](seed + 3)
    p.id, p.title = f"wtp-s{seed}-birch", "Birch Hollow Water Treatment Plant"
    p.edits = []
    _renamed(p, BIRCH_WORDS, BIRCH_ITEMS)
    d = Draw(f"{p.id}-proposal")
    d.used |= {f.value for f in p.facts}
    for tag, pump, role, after, does in BIRCH_TAGGED:
        name = f"{pump} {tag}"
        aliases = (tag, f"pump {tag}", f"{pump.lower()} {tag}")
        add_sentence(p, after, f"{name} {does}.",
                     Fact(f"{role}.capacity", name, aliases, "capacity", ("flow", "rated flow"), d.number(300, 6000),
                          "gpm"))
        add_sentence(p, f"{role}.capacity", f"{name} has a total dynamic head of {{v}} ft.",
                     Fact(f"{role}.head", name, aliases, "total dynamic head", ("TDH", "head"), d.number(20, 120, 1),
                          "ft"))
    return p

HARBOR_WORDS = (("Lakeshore Telemetry Link", "Harbor Telemetry Link"),
                ("Status Report Formats", "Buffer Report Formats"),
                ("extended short status report", "extended compact buffer report"),
                ("short status report", "compact buffer report"), ("long status report", "full buffer report"),
                ("Session ID Length", "Connection ID Length"), ("Session ID", "Connection ID"),
                ("Packet Number Length", "Sequence Number Length"), ("Packet Number", "Sequence Number"),
                ("Measurement Report", "Radio Report"), ("measurement report", "radio report"),
                ("Link Failure Detection", "Link Loss Detection"), ("A link failure is declared",
                                                                     "A link loss is declared"),
                ("retransmission timer", "resend timer"), ("send window", "transmit window"))
HARBOR_ITEMS = {"Short status report": ("Compact buffer report", ("compact report", "compact buffer report")),
                "Extended short status report": ("Extended compact buffer report",
                                                 ("extended compact report", "extended compact buffer report")),
                "Long status report": ("Full buffer report", ("full report", "full buffer report")),
                "Session ID Length field": ("Connection ID Length field", ("Connection ID Length",)),
                "Session ID field": ("Connection ID field", ("Connection ID",)),
                "Packet Number Length field": ("Sequence Number Length field", ("Sequence Number Length",)),
                "Packet Number field": ("Sequence Number field", ("Sequence Number",)),
                "Measurement report": ("Radio report", ("radio report", "the report")),
                "Link failure detection": ("Link loss detection", ("link loss", "loss detection")),
                "Retransmission timer": ("Resend timer", ("resend timer",)),
                "Send window": ("Transmit window", ("transmit window", "window"))}
TIMING = re.compile(r"^– the timing advance, [\d,]+ bits\.?$")

def harbor(seed):
    """The Harbor Telemetry Link: the Lakeshore protocol's template from the next seed, its items renamed by role;
    its Version field gone; decoys named like the Lakeshore items (a status report period, a measurement interval);
    its measurement report's timing advance not given and its transmit window's growth step given (2 gaps)."""
    p = PROJECTS["spec"](seed + 1)
    p.id, p.title = f"spec-s{seed}-proposal", "Harbor Telemetry Link: Protocol Specification"
    p.edits = []
    drop_row(p, "Version")
    gone = {"meas.ta"}
    for _, blocks in p.sections:
        blocks[:] = [b for b in blocks if not (b[0] == "p" and TIMING.match(b[1]))]
    _renamed(p, HARBOR_WORDS, HARBOR_ITEMS, titles=True)
    p.facts[:] = [f for f in p.facts if f.id not in gone]
    p.edits.append({"kind": "removed", "facts": sorted(gone)})
    d = drawer(p)
    add_sentence(p, "short.field", "A status report period of {v} ms applies to every buffer report.",
                 Fact("status.period", "Status report period", ("status report period", "report period"), "period",
                      ("reporting period",), d.number(20, 200), "ms"))
    add_sentence(p, "timer.congested", "The measurement interval is {v} ms.",
                 Fact("meas.interval", "Measurement interval", ("measurement interval",), "interval",
                      ("measurement period",), d.number(250, 950), "ms"))
    window = p.fact("window.idle")
    add_sentence(p, "window.idle", "The transmit window grows by {v} packets per round trip.",
                 Fact("window.growth", window.entity, window.aliases, "growth step", ("increment",),
                      d.number(2, 12), "packets"))
    return p

# (the corpus project's key, the other design's maker and id's ending, the pair's id's ending)
PAIRS = (("wtp", pine_ridge, "proposal", "proposals"), ("wtp", cedar_falls, "cedar", "cedar-proposals"),
         ("coaster", cyclone, "proposal", "proposals"), ("wtp", birch_hollow, "birch", "birch-proposals"),
         ("wtp", pine_ridge_metric, "metric", "metric-proposals"), ("wtp", spruce_lake, "spruce", "spruce-proposals"))

# held out only: never in development's corpus (controlled.py heldout)
HELDOUT_PAIRS = (("spec", harbor, "proposal", "proposals"),)

def pairs(seed=1, heldout=False):
    """Each pair's documents, by id (nothing generated); with heldout, the held-out templates' too."""
    listed = PAIRS + (HELDOUT_PAIRS if heldout else ())
    return [Pair(f"{key}-s{seed}-{name}", f"{key}-s{seed}", f"{key}-s{seed}-{other}") for key, _, other, name in listed]

def check(project):
    """A proposal's key is honest: its facts all placed (render raises otherwise), each value naming one fact."""
    from .corpus import render
    render(project)
    values = [f.value for f in project.facts if not f.relation]
    if len(values) != len(set(values)):
        raise ValueError(f"{project.id}: a value names two facts")

def proposed(seed=1, heldout=False):
    """[(Pair, the generated design)], checked; with heldout, the held-out templates' too."""
    out = []
    for (_, make, _, _), pair in zip(PAIRS + (HELDOUT_PAIRS if heldout else ()), pairs(seed, heldout)):
        project = make(seed)
        check(project)
        out.append((pair, project))
    return out
