"""Probe batteries: does the model use the context it's given? (docs/plans/claim-context-2026-10-14.md, milestone 2;
Measurement, layer 4.)

Each probe varies one kind of context and nothing else, so its right answer is known, and tests one property:
sensitivity (the reading changes when the context is there), specificity (context that doesn't reach a claim leaves
it alone), precedence (a local exception beats a general note) or abstention (with no context to name a thing by,
it isn't given a conventional name).

- **Reader probes** are tiny Markdown documents read by the product's extraction, as it reads any document (each
  compared with itself, so nothing is judged). A check reads the claims for its values.
- **Judge probes** are pairs of claims put to the product's judge as a revisions comparison puts them
  (compare.pair_request, then compare.vetoes), each in both orders. A probe passes when the relation is one it allows.

A battery is tens of requests: cents per model. Answers are recorded into a fixture and replayed after, so a battery
qualifies a model or backend, and checks a prompt change, at no further cost.
"""
import re
from dataclasses import dataclass, field
from pathlib import Path

PROPERTIES = ("sensitivity", "specificity", "precedence", "abstention", "control")

@dataclass
class ReaderProbe:
    id: str
    kind: str          # the context kind it varies: scope, frame, subject, stance
    property: str      # PROPERTIES
    text: str          # the Markdown document
    checks: list       # [(value, what it must say, a check of the value's claims: claims -> bool)]

@dataclass
class JudgeProbe:
    id: str
    kind: str
    property: str
    a: dict            # the earlier claim's fields (entity, attribute, value, unit, conditions, quote)
    b: dict
    allowed: tuple     # relations that pass
    mode: str = "revisions"

def _said(claims, fields, *patterns):
    """Whether every claim says one of the patterns in one of its fields (any claim at all: none read fails)."""
    return bool(claims) and all(any(re.search(p, str(c.get(f, "")), re.I) for f in fields for p in patterns)
                                for c in claims)

def _silent(claims, fields, *patterns):
    """Whether no claim says any of the patterns (and some claim was read)."""
    return bool(claims) and not any(re.search(p, str(c.get(f, "")), re.I) for c in claims for f in fields
                                    for p in patterns)

WHERE = ("entity", "attribute", "conditions")
CONVENTION = r"\b(?:width|wide|depth|deep|length|long)\b"

READER = [
    ReaderProbe("scope-lead-in", "scope", "sensitivity",
                "# Link Specification\n\n## 5 Timers\n\nWhen the link is idle, the following values apply.\n\n"
                "- Retransmission timer: 709 ms\n- Keep-alive interval: 1,250 ms\n",
                [("709", "idle, from the lead-in", lambda cs: _said(cs, ("conditions",), r"\bidle\b")),
                 ("1,250", "idle, from the lead-in", lambda cs: _said(cs, ("conditions",), r"\bidle\b"))]),
    ReaderProbe("scope-other-section", "scope", "specificity",
                "# Link Specification\n\n## 4 Idle link\n\nWhen the link is idle, the retransmission timer is "
                "709 ms.\n\n## 5 Congested link\n\nThe retransmission timer is 856 ms.\n",
                [("856", "not idle (another section's scope)", lambda cs: _silent(cs, WHERE, r"\bidle\b")),
                 ("856", "congested, from its heading", lambda cs: _said(cs, WHERE, r"congest"))]),
    ReaderProbe("frame-units-note", "frame", "sensitivity",
                "# Flange Data\n\nAll dimensions are in millimetres.\n\nThe flange outer diameter is 340 and the "
                "bolt circle diameter is 290.\n",
                [("340", "unit mm, from the note", lambda cs: _said(cs, ("unit",), r"^mm$|millimet")),
                 ("290", "unit mm, from the note", lambda cs: _said(cs, ("unit",), r"^mm$|millimet"))]),
    ReaderProbe("frame-exception", "frame", "precedence",
                "# Floor Plan Notes\n\nGeneral note: all dimensions are to face of finish unless noted otherwise."
                "\n\nRoom 101 is 12'-6\" wide. The corridor is 6'-0\" wide, measured to the centreline of its "
                "walls.\n",
                [("12'-6\"", "to face of finish (the general note)",
                  lambda cs: _said(cs, WHERE, r"face of finish")),
                 ("6'-0\"", "to centreline, not face of finish (the exception)",
                  lambda cs: _said(cs, WHERE, r"cent(?:er|re) ?line") and _silent(cs, WHERE, r"face of finish"))]),
    ReaderProbe("stance-holders", "stance", "sensitivity",
                "# Contributions\n\nCompany A proposes a retransmission timer of 709 ms. Company B proposes a "
                "retransmission timer of 856 ms.\n",
                [("709", "held by Company A", lambda cs: _said(cs, WHERE, r"company a\b")),
                 ("856", "held by Company B", lambda cs: _said(cs, WHERE, r"company b\b"))]),
    ReaderProbe("stance-negation", "stance", "sensitivity",
                "# Contributions\n\nCompany C does not support a retransmission timer below 500 ms.\n",
                [("500", "Company C's, as a limit it holds (not supported below; a minimum)",
                  lambda cs: _said(cs, WHERE, r"company c\b")
                  and _said(cs, WHERE, r"\bnot\b|oppose|reject|minimum|at least|lower limit"))]),
    ReaderProbe("name-abstention", "subject", "abstention",
                "# Room Data\n\nRoom 214 measures 12'-6\" by 14'-0\" on plan.\n",
                [("12'-6\"", "no conventional name the page doesn't give",
                  lambda cs: _silent(cs, ("attribute",), CONVENTION)),
                 ("14'-0\"", "no conventional name the page doesn't give",
                  lambda cs: _silent(cs, ("attribute",), CONVENTION))]),
]

def _claim(entity, attribute, value, unit="", conditions="", quote=None):
    return {"entity": entity, "attribute": attribute, "value": value, "unit": unit, "conditions": conditions,
            "quote": quote or f"{attribute} {value} {unit}".strip()}

NOT_SAME = ("complementary", "uncertain", "unrelated")
JUDGE = [
    JudgeProbe("frame-differs", "frame", "sensitivity",
               _claim("Room 101", "width", "12'-6\"", "ft-in", "to face of finish"),
               _claim("Room 101", "width", "12'-6\"", "ft-in", "to centreline of walls"),
               ("complementary", "uncertain")),
    JudgeProbe("holder-differs", "stance", "sensitivity",
               _claim("link", "retransmission timer", "709", "ms", "proposed by Company A"),
               _claim("link", "retransmission timer", "709", "ms", "proposed by Company B"), NOT_SAME),
    JudgeProbe("position-renumbered", "provenance", "specificity",
               _claim("link failure", "acknowledgement timeout", "856", "ms", "",
                      "Condition 2: no acknowledgement is received within 856 ms."),
               _claim("link failure", "acknowledgement timeout", "856", "ms", "",
                      "Condition 3: no acknowledgement is received within 856 ms."), ("equivalent",)),
    JudgeProbe("scope-differs", "scope", "sensitivity",
               _claim("link", "retransmission timer", "709", "ms", "link idle"),
               _claim("link", "retransmission timer", "856", "ms", "link congested"), NOT_SAME),
    JudgeProbe("scope-unknown", "scope", "abstention",
               _claim("link", "retransmission timer", "709", "ms", "link idle"),
               _claim("link", "retransmission timer", "709", "ms", ""), ("equivalent", "uncertain")),
    JudgeProbe("irrelevant-context", "scope", "specificity",
               _claim("link", "retransmission timer", "709", "ms", "link idle",
                      "When the link is idle, the retransmission timer is 709 ms."),
               _claim("link", "retransmission timer", "709", "ms", "link idle",
                      "When the link is idle (see Annex B for the history of this value), the retransmission timer "
                      "is 709 ms."), ("equivalent",)),
    JudgeProbe("value-changed", "scope", "control",
               _claim("link", "retransmission timer", "709", "ms", "link idle"),
               _claim("link", "retransmission timer", "720", "ms", "link idle"), ("different",)),
    JudgeProbe("units-converted", "frame", "control",
               _claim("flange", "outer diameter", "340", "mm"), _claim("flange", "outer diameter", "34", "cm"),
               ("equivalent",)),
]

@dataclass
class Outcome:
    probe: str
    kind: str
    property: str
    check: str
    passed: bool
    read: list = field(default_factory=list)  # what was read (reader) or answered (judge)
    model_passed: bool | None = None  # a judge probe: the model's own answer passes, before the product's vetoes

def matching(claims, value):
    """The claims whose value is this one, as printed or as a number."""
    from semantic_pdf_diff.values import printed_value
    want = printed_value(value)
    return [c for c in claims if printed_value(str(c.get("value", ""))) == want or c.get("value") == value]

def read_probe(probe, claims):
    """A reader probe's outcomes from the claims read."""
    out = []
    for value, says, check in probe.checks:
        mine = matching(claims, value)
        out.append(Outcome(probe.id, probe.kind, probe.property, f"{value}: {says}", bool(check(mine)),
                           [" | ".join(str(c.get(k, "")) for k in ("entity", "attribute", "value", "unit",
                                                                    "conditions")) for c in mine]))
    return out

def evidence(fields, side):
    """A claim as the judge's evidence (provenance made up: the judge never sees it)."""
    from semantic_pdf_diff.schema import Evidence, TextLocator
    return Evidence(id=f"probe-{side}", content=f"sha256:{side * 64}.md", kind="text", confidence=0.95,
                    locator=TextLocator(page=1, lines=(1, 1), region="text", task="probe"), **fields)

def run_reader(folder, settings, options):
    """Every reader probe read: [Outcome]. Each document is written into folder/docs, its run into folder/runs."""
    from semantic_pdf_diff.pipeline import attempt, compare_paths
    from semantic_pdf_diff.store import Store
    out = []
    for probe in READER:
        doc = Path(folder) / "docs" / f"{probe.id}.md"
        doc.parent.mkdir(parents=True, exist_ok=True)
        doc.write_text(probe.text, encoding="utf-8")
        run = Path(folder) / "runs" / probe.id
        attempt(compare_paths, doc, doc, run, settings, options)
        with Store.open(run) as store:
            claims = list({e.id: e.model_dump() for f in store.files() for e in store.evidence(f.content)}.values())
        out += read_probe(probe, claims)
    return out

def run_judge(folder, settings, options):
    """Every judge probe asked in both orders: [Outcome] (check: "A, B" or "B, A")."""
    from semantic_pdf_diff.pipeline import make_client
    from semantic_pdf_diff.store import Store
    with Store(Path(folder) / "judge") as store:
        client = make_client(options, settings, store)
        try:
            return [judge(client, settings, probe, order) for probe in JUDGE for order in ("A, B", "B, A")]
        finally:
            client.close()  # the fixture notes which answers were used (pack keeps those)

def judge(client, settings, probe, order):
    """One judge probe asked in one order, judged as compare() judges a pair: the model's relation, then vetoes."""
    from semantic_pdf_diff.compare import pair_request, vetoes
    from semantic_pdf_diff.schema import Judgment
    x, y = (probe.a, probe.b) if order == "A, B" else (probe.b, probe.a)
    a, b = evidence(x, "a"), evidence(y, "b")
    prompt, images, _, calc = pair_request(settings, probe.mode, a, b)
    judgment = client.ask(prompt, Judgment, images, ("compare", probe.mode, "probe", probe.id, order))
    relation = "uncertain" if vetoes(judgment, a, b, calc) else judgment.relation
    return Outcome(probe.id, probe.kind, probe.property, order, relation in probe.allowed,
                   [f"{relation} (asked: {judgment.relation}; same conditions: {judgment.same_conditions}) "
                    f"{judgment.rationale}"], judgment.relation in probe.allowed)

def summary(outcomes):
    """Passed of asked, by kind and by property; and, for judge probes, the probes answered alike in both orders."""
    from collections import Counter
    def tally(key):
        asked, passed = Counter(), Counter()
        for o in outcomes:
            asked[key(o)] += 1
            passed[key(o)] += o.passed
        return {k: f"{passed[k]}/{asked[k]}" for k in sorted(asked)}
    judged = [o for o in outcomes if o.model_passed is not None]
    return {"passed": f"{sum(o.passed for o in outcomes)}/{len(outcomes)}", "by_kind": tally(lambda o: o.kind),
            "by_property": tally(lambda o: o.property),
            **({"judge_model_passed": f"{sum(o.model_passed for o in judged)}/{len(judged)}"} if judged else {})}

def consistency(outcomes):
    """Judge probes whose relation was the same in both orders, of those asked in both."""
    by = {}
    for o in outcomes:
        by.setdefault(o.probe, []).append(o.read[0].split(" ")[0])
    both = [v for v in by.values() if len(v) == 2]
    return f"{sum(1 for v in both if v[0] == v[1])}/{len(both)}"
