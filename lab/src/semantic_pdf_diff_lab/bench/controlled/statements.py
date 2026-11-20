"""Tables of statements (docs/plans/requirements-and-textual-claims-2026-11-18.md, milestone 0; the owner, 2026-11-18:
"I have a LOT of claims in the form of requirements tables that aren't numerical in nature in my actual corpus"): one
system's requirements, whose statements are sentences, drawn in several shapes (STATEMENT_KNOBS), none of them
canonical (the owner: "Don't count on that one table example as being canonical. It's just one example.").

- **cells:** a statement in one cell beside an identifier, a name, a rationale, a verification method and a status
  left blank, as a requirements table copied from a modelling tool.
- **split:** a statement split over condition, subject, verb and content cells, with a note discussing the wording,
  as a requirements table from elsewhere; two of its notes claim something of the system (a limit the hull can't
  meet, another interval wanted), their numbers facts the note holds (NOTE_HOLDER), not the statement.
- **prose:** numbered paragraphs, each a statement with its rationale and verification after it.

The same facts in every shape: each statement whole and each rationale (text facts, drawn "statement": placed by the
words they print, scored by words: score.classify_statement), and the numbers a statement states (numeric facts,
placed and scored as any). A statement's modality is its fact's basis (shall: required; should: recommended; may:
permitted; will: intended), for later milestones to score.
"""
from .model import Draw, Fact, Project

STATEMENT_KNOBS = ("cells", "split", "prose")
NOTE_HOLDER = "the requirements note"  # who holds a note's claim: not the statement's

# a statement's force, as its key says it (the owner, 2026-11-18: "I'd count 'will' as a claim or intention")
BASIS = {"shall": "required", "should": "recommended", "may": "permitted", "will": "intended"}

# (name, condition, subject, verb, content with {lo} and {hi} numbers, [(number name, attribute, synonyms, unit, low,
# high, decimals)], rationale, verification method, note: discussing the wording, or (claiming something of the system
# with {alt}, its numbers as the content's))
REQUIREMENTS = [
    ("Survival Temperature", "", "The buoy hull", "shall",
     "withstand ambient temperatures from {lo} °C to +{hi} °C without damage",
     [("lo", "minimum survival temperature", ("lowest ambient temperature", "survival temperature (minimum)"), "°C",
       -45, -25, 0),
      ("hi", "maximum survival temperature", ("highest ambient temperature", "survival temperature (maximum)"), "°C",
       45, 60, 0)],
     "The buoy winters in an unheated yard and is deployed through the summer.", "Test",
     ("The hull supplier rates the hull to +{alt} °C only; expect the upper limit to be lowered.",
      [("alt", "maximum survival temperature", ("highest ambient temperature", "hull rating"), "°C", 35, 44, 0)])),
    ("Data Retention", "In the event of a loss of main power", "the data logger", "shall",
     "retain every logged record for at least {lo} hours",
     [("lo", "data retention time", ("record retention on power loss", "retention period"), "h", 48, 96, 0)],
     "Field crews may take several days to reach a buoy after an outage.", "Test, Analysis",
     "Confirm whether the hold-up battery or the flash memory carries this."),
    ("Hull Colour", "", "The buoy hull above the waterline", "shall",
     "be painted international orange", [],
     "Mariners must see the buoy by day against open water.", "Inspection",
     "The harbour authority may prefer yellow; ask before the paint is ordered."),
    ("Record Format", "", "The data logger", "should",
     "store its records in a documented, non-proprietary file format", [],
     "Records outlive the software that wrote them.", "Inspection",
     "Wording to be agreed with the data management group."),
    ("Remote Update", "", "The logger firmware", "may",
     "be updated over the satellite link", [],
     "Visits to the buoy cost a boat day each.", "Demonstration",
     "Security review pending."),
    ("Mooring Inspection", "", "The operator", "will",
     "inspect the mooring chain every {lo} months", [("lo", "mooring inspection interval",
                                                     ("inspection interval", "mooring inspection period"), "months",
                                                     9, 15, 0)],
     "Chain wear is the leading cause of lost buoys.", "Inspection",
     "Interval to be confirmed against the chain supplier's guidance."),
    ("Transmit Interval", "While the buoy is moored", "the telemetry unit", "shall",
     "report its position and water temperature at intervals of no more than {lo} minutes",
     [("lo", "maximum reporting interval", ("reporting interval", "transmit interval"), "min", 20, 40, 0)],
     "The harbour office plots positions in near real time.", "Demonstration",
     ("During storms the harbour office wants reports every {alt} minutes instead.",
      [("alt", "storm reporting interval", ("reporting interval in storms", "storm interval"), "min", 5, 15, 0)])),
    ("Lamp Visibility", "", "The navigation lamp", "shall",
     "be visible at a range of at least {lo} nautical miles on a clear night",
     [("lo", "minimum lamp range", ("visibility range", "lamp range"), "nmi", 2, 5, 1)],
     "The buoy marks a channel used at night.", "Analysis",
     "Range assumes the standard atmospheric transmissivity."),
]

def statement(condition, subject, verb, content):
    """The sentence a statement makes, whatever shape prints it."""
    said = f"{subject} {verb} {content}."
    return f"{condition}, {said[0].lower()}{said[1:]}" if condition else said

def requirements(seed=1):
    """The buoy's requirements: their facts, and the rows each shape prints them from."""
    d = Draw(seed)
    count = len(REQUIREMENTS)  # numbers printed as structure: section and table numbers, identifiers' digits
    numbered = range(1, count + 1)
    d.used.update({"1", "2", "3", "0.1", *(f"3.{n}" for n in numbered), *(str(100 + n) for n in numbered),
                   *(f"{n:03d}" for n in numbered)})
    facts, rows = [], []
    for n, (name, condition, subject, verb, content, numbers, rationale, method, note) in enumerate(REQUIREMENTS, 1):
        values = {}
        ident = (f"HMB-REQ-{100 + n}", f"HMBv0.1-{n:03d}", f"3.{n}")
        aliases = (*ident, name.lower(), subject.removeprefix("The ").removeprefix("the "))
        for key, attribute, synonyms, unit, lo, hi, decimals in numbers:
            values[key] = d.number(lo, hi, decimals)
            facts.append(Fact(f"req{n}.{key}", name, aliases, attribute, synonyms, values[key], unit,
                              basis=BASIS[verb]))
        said = content.format(**values)
        facts.append(Fact(f"req{n}.statement", name, aliases, "statement",
                          ("requirement", "requirement text", "text", "content", "shall statement"),
                          statement(condition, subject, verb, said), basis=BASIS[verb], drawn="statement",
                          printed_as=tuple(p for p in (condition, subject, verb, said) if p)))
        facts.append(Fact(f"req{n}.rationale", name, aliases, "rationale", ("justification", "reason"), rationale,
                          drawn="statement", printed_as=(rationale,)))
        rows.append({"ids": ident, "name": name, "condition": condition, "subject": subject, "verb": verb,
                     "content": said, "rationale": rationale, "method": method, "note": note, "aliases": aliases})
    for n, row in enumerate(rows, 1):  # notes claiming something of the system (the owner, 2026-11-18: "a "well,
        if isinstance(row["note"], tuple):  # actually" in the comment"), drawn after the statements so theirs stay
            template, claimed = row["note"]
            alt = {}
            for key, attribute, synonyms, unit, lo, hi, decimals in claimed:
                alt[key] = d.number(lo, hi, decimals)
                facts.append(Fact(f"req{n}.note.{key}", row["name"], row["aliases"], attribute, synonyms, alt[key],
                                  unit, basis="intended", holder=NOTE_HOLDER))
            row["note"] = template.format(**alt)
    return facts, rows

def buoy_requirements(seed=1):
    """The harbour monitoring buoy's requirements, drawn as its knob's shape says (STATEMENT_KNOBS; "cells" unless
    set: corpus.catalog sets each)."""
    facts, rows = requirements(seed)
    project = Project(f"hmb-s{seed}", "Harbour Monitoring Buoy: System Requirements", facts, [], knob="cells",
                      kinds=STATEMENT_KNOBS)
    project.statements, project.all_facts = rows, facts
    return shaped(project)

def shaped(project):
    """The project drawn in its knob's shape: its sections, and the facts that shape prints (the split shape prints
    no rationale). The catalog sets the knob after making it, so it shapes the project again (catalog.corpus)."""
    project.sections = sections(project)
    if project.knob == "split":  # notes, no rationales
        project.facts = [f for f in project.all_facts if f.attribute != "rationale"]
    else:  # rationales, no notes
        project.facts = [f for f in project.all_facts if f.holder != NOTE_HOLDER]
    return project

def sections(project):
    """The sections the project's shape prints."""
    rows, knob = project.statements, project.knob
    intro = ("p", "This document states the requirements for the harbour monitoring buoy. Each requirement is "
                  "identified, stated and verified as below.")
    if knob == "split":
        header = ["Temporary UID", "Condition", "Subject", "Verb", "Clause(s)/Content", "REQUIREMENTS NOTE"]
        body = [[r["ids"][1], r["condition"], r["subject"], r["verb"].upper(), r["content"] + ".", r["note"]]
                for r in rows]
        return [("1 Scope", [intro]), ("2 Requirements", [("table", "Table 1. Buoy requirements", header, body)])]
    if knob == "prose":
        said = lambda r: statement(r["condition"], r["subject"], r["verb"], r["content"])  # noqa: E731
        paragraphs = [("p", f"{r['ids'][2]} {r['name']}. {said(r)} Rationale: {r['rationale']} "
                            f"Verification: {r['method']}.") for r in rows]
        return [("1 Scope", [intro]), ("3 Requirements", paragraphs)]
    header = ["ID", "Name", "Text", "Rationale", "Verification Method", "Requirement Status"]
    body = [[r["ids"][0], r["name"], statement(r["condition"], r["subject"], r["verb"], r["content"]), r["rationale"],
             r["method"], ""] for r in rows]
    return [("1 Scope", [intro]), ("2 Requirements", [("table", "Table 1. Buoy requirements", header, body)])]

# A risk register: another table of statements, not requirements (Risk ID, Risk, Likelihood, Consequence,
# Mitigation, Owner): (risk, likelihood, consequence, mitigation with {n}, [its numbers], owner)
RISKS = [
    ("If the mooring chain wears through, the buoy may drift into the shipping channel.", "Medium",
     "A hazard to navigation until the buoy is recovered.",
     "Replace any chain link worn by more than {n} percent of its diameter.",
     [("n", "chain wear limit", ("allowed link wear", "wear limit"), "%", 12, 25, 0)], "Operator"),
    ("If the satellite service is withdrawn, positions stop reaching the harbour office.", "Low",
     "The buoy's position is unknown between visits.", "Keep a second telemetry provider under contract.", [],
     "Harbour office"),
    ("If seabirds foul the solar panel, the battery may not recharge in winter.", "High",
     "Data gaps through the darkest months.", "Fit bird spikes around the panel frame.", [], "Operator"),
    ("If the lamp fails at night, the channel is unmarked.", "Low", "Vessels may stray from the channel.",
     "Broadcast a notice to mariners within {n} hours of a reported failure.",
     [("n", "notice to mariners time", ("notice deadline", "time to broadcast a notice"), "h", 2, 8, 0)],
     "Harbour office"),
]

def buoy_risks(seed=1):
    """The harbour monitoring buoy's risk register (RISK_KNOBS): each risk and its mitigation text facts, the
    numbers a mitigation states numeric facts."""
    d = Draw(seed + 100)
    d.used.update({"1", "2", *(f"R-{n:02d}" for n in range(1, len(RISKS) + 1))})
    facts, rows = [], []
    for n, (risk, likelihood, consequence, mitigation, numbers, owner) in enumerate(RISKS, 1):
        ident, values = f"R-{n:02d}", {}
        aliases = (ident, f"risk {n}")
        for key, attribute, synonyms, unit, lo, hi, decimals in numbers:
            values[key] = d.number(lo, hi, decimals)
            facts.append(Fact(f"risk{n}.{key}", f"Risk {ident}", aliases, attribute, synonyms, values[key], unit))
        said = mitigation.format(**values)
        facts.append(Fact(f"risk{n}.risk", f"Risk {ident}", aliases, "risk", ("risk statement", "hazard",
                                                                              "description"),
                          risk, drawn="statement", printed_as=(risk,)))
        facts.append(Fact(f"risk{n}.mitigation", f"Risk {ident}", aliases, "mitigation",
                          ("mitigation measure", "treatment", "control"), said, drawn="statement", printed_as=(said,)))
        rows.append([ident, risk, likelihood, consequence, said, owner])
    header = ["Risk ID", "Risk", "Likelihood", "Consequence", "Mitigation", "Owner"]
    sections = [("1 Purpose", [("p", "This register lists the risks to the harbour monitoring buoy's service and how "
                                     "each is treated.")]),
                ("2 Risks", [("table", "Table 1. Risk register", header, rows)])]
    project = Project(f"hmbr-s{seed}", "Harbour Monitoring Buoy: Risk Register", facts, sections, knob="register",
                      kinds=RISK_KNOBS)
    project.statements = rows  # a table of statements: written in every representation (representations.corpus)
    return project

RISK_KNOBS = ("register",)

STATEMENT_PROJECTS = {"hmb": buoy_requirements}
RISK_PROJECTS = {"hmbr": buoy_risks}

# --- held out (statement_tables' held-out rule, docs/reviews/levers.md): never in the development corpus ------------
# An irrigation controller's requirements, in two shapes of their own, other columns named and ordered otherwise; and a
# table of values beside them (zone valves), which must read as before. Generated only by `controlled.py
# statements-heldout`, into benchmarks/controlled/heldout/statements (git-ignored).
HELDOUT_KNOBS = ("listed", "clauses")

CONTROLLER = [  # (title, trigger, actor, modal, action with {lo}, [its numbers], justification, verification, priority)
    ("Frost Shutdown", "When the air temperature falls below {lo} °C", "the controller", "shall",
     "close every zone valve and hold them closed until it rises again",
     [("lo", "frost shutdown temperature", ("shutdown temperature", "frost threshold"), "°C", 1, 4, 1)],
     "Water left in the laterals freezes and splits them.", "Test", "Essential"),
    ("Manual Override", "", "An operator", "shall",
     "be able to open or close any zone from the cabinet keypad", [],
     "Crews must water by hand when the schedule is wrong.", "Demonstration", "Essential"),
    ("Schedule Storage", "", "The controller", "shall",
     "keep at least {lo} watering programs in non-volatile memory",
     [("lo", "stored programs", ("program capacity", "number of programs"), "", 12, 24, 0)],
     "Each season needs its own programs.", "Inspection", "High"),
    ("Rain Delay", "After rainfall of more than {lo} mm in a day", "the controller", "should",
     "postpone the next watering by one day",
     [("lo", "rain delay threshold", ("rainfall threshold", "rain delay rainfall"), "mm", 5, 12, 0)],
     "Watering after heavy rain wastes water and leaches fertilizer.", "Analysis", "Medium"),
    ("Remote Reporting", "", "The controller", "may",
     "send a daily water use summary to the parks office", [],
     "The office budgets water by park.", "Demonstration", "Low"),
    ("Cabinet Enclosure", "", "The cabinet", "shall",
     "be lockable and rated for outdoor installation", [],
     "Cabinets stand in public parks.", "Inspection", "Essential"),
    ("Flow Alarm", "If a zone draws more than {lo} percent above its learned flow", "the controller", "shall",
     "close that zone and raise an alarm",
     [("lo", "flow alarm margin", ("excess flow alarm", "high flow threshold"), "%", 20, 45, 0)],
     "A broken head floods the turf and wastes water.", "Test", "High"),
    ("Valve Replacement", "", "The parks crew", "will",
     "replace zone valves on failure, keeping two spares per park", [],
     "Spares avoid a week without water.", "Inspection", "Medium"),
]

def controller_requirements(seed=1):
    """The held-out template's requirements and a zone valve schedule; shaped by its knob (HELDOUT_KNOBS)."""
    d = Draw(seed + 200)
    count = len(CONTROLLER)
    d.used.update({"1", "2", *(f"IRC-{n:04d}" for n in range(1, count + 1)), *(f"{n:04d}" for n in range(1, count + 1)),
                   *(str(n) for n in range(1, count + 1))})
    facts, rows = [], []
    for n, (title, trigger, actor, modal, action, numbers, why, method, priority) in enumerate(CONTROLLER, 1):
        values = {}
        ident = (f"IRC-{n:04d}", f"REQ {n}")
        aliases = (*ident, title.lower(), actor.removeprefix("The ").removeprefix("An ").removeprefix("the "))
        for key, attribute, synonyms, unit, lo, hi, decimals in numbers:
            values[key] = d.number(lo, hi, decimals)
            facts.append(Fact(f"irc{n}.{key}", title, aliases, attribute, synonyms, values[key], unit,
                              basis=BASIS[modal]))
        when, said = trigger.format(**values), action.format(**values)
        facts.append(Fact(f"irc{n}.statement", title, aliases, "statement",
                          ("requirement", "requirement text", "text", "content", "shall statement"),
                          statement(when, actor, modal, said), basis=BASIS[modal], drawn="statement",
                          printed_as=tuple(p for p in (when, actor, modal, said) if p)))
        facts.append(Fact(f"irc{n}.justification", title, aliases, "justification", ("rationale", "reason"), why,
                          drawn="statement", printed_as=(why,)))
        rows.append({"ids": ident, "title": title, "when": when, "actor": actor, "modal": modal, "said": said,
                     "why": why, "method": method, "priority": priority})
    zones = []
    for z in range(1, 5):  # a table of values beside the statements: its numbers must read as before
        flow, pressure = d.number(30, 90), d.number(250, 450)
        facts.append(Fact(f"zone{z}.flow", f"Zone {z}", (f"zone {z} valve",), "design flow", ("flow",), flow, "L/min"))
        facts.append(Fact(f"zone{z}.pressure", f"Zone {z}", (f"zone {z} valve",), "operating pressure",
                          ("pressure",), pressure, "kPa"))
        zones.append([f"Zone {z}", flow, pressure])
    project = Project(f"irc-s{seed}", "Park Irrigation Controller: Requirements", facts, [], knob="listed",
                      kinds=HELDOUT_KNOBS)
    project.statements, project.all_facts, project.zones = rows, facts, zones
    return shaped_heldout(project)

def shaped_heldout(project):
    """The held-out template in its knob's shape (the clauses shape prints no justification)."""
    rows, zones = project.statements, project.zones
    valves = ("table", "Table 2. Zone valves", ["Zone", "Design flow (L/min)", "Operating pressure (kPa)"], zones)
    if project.knob == "clauses":
        header = ["UID", "Trigger", "Actor", "Modal", "Action", "Phase"]
        body = [[r["ids"][1], r["when"], r["actor"], r["modal"].upper(), r["said"] + ".", "Construction"] for r in rows]
        project.facts = [f for f in project.all_facts if f.attribute != "justification"]
    else:
        header = ["Req No.", "Priority", "Title", "Requirement", "Verification", "Justification"]
        body = [[r["ids"][0], r["priority"], r["title"], statement(r["when"], r["actor"], r["modal"], r["said"]),
                 r["method"], r["why"]] for r in rows]
        project.facts = list(project.all_facts)
    project.sections = [("1 Introduction", [("p", "These are the requirements for the park irrigation controller and "
                                                  "the valves it drives.")]),
                        ("2 Requirements", [("table", "Table 1. Controller requirements", header, body)]),
                        ("3 Valves", [valves])]
    return project

HELDOUT_STATEMENTS = {"irc": controller_requirements}
