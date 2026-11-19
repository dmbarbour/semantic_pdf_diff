"""Tables of statements (docs/plans/requirements-and-textual-claims-2026-11-18.md, milestone 0; the owner, 2026-11-18:
"I have a LOT of claims in the form of requirements tables that aren't numerical in nature in my actual corpus"): one
system's requirements, whose statements are sentences, drawn in several shapes (STATEMENT_KNOBS), none of them
canonical (the owner: "Don't count on that one table example as being canonical. It's just one example.").

- **cells:** a statement in one cell beside an identifier, a name, a rationale, a verification method and a status
  left blank, as a requirements table copied from a modelling tool.
- **split:** a statement split over condition, subject, verb and content cells, with a note discussing the wording,
  as a requirements table from elsewhere.
- **prose:** numbered paragraphs, each a statement with its rationale and verification after it.

The same facts in every shape: each statement whole and each rationale (text facts, drawn "statement": placed by the
words they print, scored by words: score.classify_statement), and the numbers a statement states (numeric facts,
placed and scored as any). A statement's modality is its fact's basis (shall: required; should: recommended; may:
permitted; will: intended), for later milestones to score.
"""
from .model import Draw, Fact, Project

STATEMENT_KNOBS = ("cells", "split", "prose")

# a statement's force, as its key says it (the owner, 2026-11-18: "I'd count 'will' as a claim or intention")
BASIS = {"shall": "required", "should": "recommended", "may": "permitted", "will": "intended"}

# (name, condition, subject, verb, content with {lo} and {hi} numbers, [(number name, attribute, synonyms, unit, low,
# high, decimals)], rationale, verification method, note discussing the wording)
REQUIREMENTS = [
    ("Survival Temperature", "", "The buoy hull", "shall",
     "withstand ambient temperatures from {lo} °C to +{hi} °C without damage",
     [("lo", "minimum survival temperature", ("lowest ambient temperature", "survival temperature (minimum)"), "°C",
       -45, -25, 0),
      ("hi", "maximum survival temperature", ("highest ambient temperature", "survival temperature (maximum)"), "°C",
       45, 60, 0)],
     "The buoy winters in an unheated yard and is deployed through the summer.", "Test",
     "Align the range with the mooring specification once it is issued."),
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
     "Consider a shorter interval during storms."),
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
                     "content": said, "rationale": rationale, "method": method, "note": note})
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
    if project.knob == "split":
        project.facts = [f for f in project.all_facts if f.attribute != "rationale"]
    else:
        project.facts = list(project.all_facts)
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

STATEMENT_PROJECTS = {"hmb": buoy_requirements}
