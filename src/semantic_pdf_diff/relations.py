"""Relations between named things, and how claims that state them are scored (controlled documents, milestone
3b; docs/plans/controlled-documents-2026-10-01.md).

The owner, 2026-10-01: "We'll need to develop a fairly wide array of 'relations', e.g. component of, within,
attached to, etc. and a lot of control docs that present relations in different ways, with varying levels of
difficulty."

A relational fact is a subject, a relation and an object: "the cooling coil precedes the supply fan on the air
path", "the Lyot stop is located at a pupil plane". Readers state them in many shapes:

- "cooling coil | upstream of | supply fan", or from the other side, "supply fan | after | cooling coil"
- a path: "coronagraph | optical path | DM1 -> DM2 -> Focal plane mask -> Lyot stop"
- a list: "AHU-3 | components | mixing box, filter bank, cooling coil"
- options: "focal plane mask | options | HLC or VC"
- a place or a state: "Lyot stop | location | in pupil", "filter wheel | mobility | movable"

So a claim is read into triples: its names matched to the document's things (parts, and facts' literal objects
such as "pupil plane"), its relation found from the words left over (the attribute's first, then the value's),
paths split into adjacent pairs and lists into their members. Each triple is then classed:

- right: a fact, read from either side (an inverse phrasing is the same fact)
- implied: true, but not a stated fact (a part two steps upstream; a part of a part of the whole)
- reversed: the fact read backwards ("the fan precedes the coil")
- wrong: real things, a known relation, not so in the document
- invented: a subject or object the document doesn't name
- unscored: no relation recognised (a function described in words, say)
"""
import re
import unicodedata
from dataclasses import dataclass

@dataclass(frozen=True)
class Relation:
    name: str
    phrases: tuple            # how a claim may put it; matched as whole words, the longest match winning
    inverse: str = ""         # the same relation read from the object's side
    symmetric: bool = False
    literal: bool = False     # the object is a place or a state, not a part
    transitive: bool = False  # a chain implies its ends (upstream of upstream is upstream)
    forward: bool = True      # the direction facts are kept in; an inverse is turned round

R = Relation
RELATIONS = {r.name: r for r in (
    R("precedes", ("precedes", "upstream of", "before", "feeds into", "flows to", "flows into", "passes to",
                   "leads to", "discharges to", "sends to", "then", "next", "to", "into", "outlet to", "path",
                   "sequence", "order", "flow path", "light path", "air path", "optical path", "beam path",
                   "process flow", "followed by", "downstream component", "next component", "reflects to",
                   "directs to", "relays to", "flow sequence", "optical path sequence", "path order", "train",
                   "optical train", "air path order", "destination", "airflow destination", "air flow destination",
                   "flow destination", "flow target", "airflow target", "air flow target", "outlet", "next element",
                   "downstream element", "light destination", "beam destination", "sends light to", "sends air to",
                   "input sequence", "output beam path", "input beam path"), inverse="follows", transitive=True),
    R("follows", ("follows", "downstream of", "after", "receives from", "comes from", "from",
                  "preceded by", "inlet from", "upstream component", "previous component", "receives light from",
                  "receives air from", "input source", "input from", "upstream element", "source element",
                  "receives input from"), inverse="precedes", transitive=True, forward=False),
    R("part of", ("part of", "component of", "belongs to", "element of", "subassembly of", "member of", "parent",
                  "parent assembly", "assembly", "system membership", "membership", "member", "belongs",
                  "part of system", "subsystem of"), inverse="has part", transitive=True),
    R("has part", ("has part", "has parts", "component", "components", "comprises", "includes", "consists of",
                   "parts", "elements", "equipped with", "has", "contains components", "subcomponents",
                   "made up of"), inverse="part of", transitive=True, forward=False),
    R("within", ("within", "inside", "housed in", "located in", "enclosed in", "contained in", "in",
                 "located inside", "housing", "enclosure"), inverse="contains", transitive=True),
    R("contains", ("contains", "houses", "encloses", "holds"), inverse="within", transitive=True, forward=False),
    R("mounted on", ("mounted on", "attached to", "fixed to", "bolted to", "fastened to", "sits on", "installed on",
                     "mounted to", "on", "mounting"), inverse="carries"),
    R("carries", ("carries", "supports", "holds up", "bears", "mounting for"), inverse="mounted on", forward=False),
    R("drives", ("drives", "turns", "rotates", "actuates", "drive target", "driven equipment", "driven load"),
      inverse="driven by"),
    R("driven by", ("driven by", "turned by", "actuated by", "motor", "driver", "drive", "drive motor"),
      inverse="drives", forward=False),
    R("powers", ("powers", "supplies power to", "energizes", "feeds power to", "power to", "power target",
                 "powered equipment", "powered load"), inverse="powered from"),
    R("powered from", ("powered from", "powered by", "power source", "power supply", "electrical feed",
                       "fed power from", "power", "electrical supply", "circuit", "fed from panel"),
      inverse="powers", forward=False),
    R("controls", ("controls", "regulates", "modulates", "operates", "commands", "control", "controlled devices",
                   "control of", "control target", "controlled device", "controlled equipment"),
      inverse="controlled by"),
    R("controlled by", ("controlled by", "regulated by", "modulated by", "operated by", "controller",
                        "control source", "controlling device"), inverse="controls", forward=False),
    R("measures", ("measures", "senses", "monitors", "reads", "detects", "measurement", "measurement point",
                   "measurement target", "measured medium"), inverse="measured by"),
    R("measured by", ("measured by", "sensed by", "monitored by", "sensor", "instrument", "monitoring",
                      "monitoring device"), inverse="measures", forward=False),
    R("signals", ("signals", "reports to", "sends signal to", "wired to", "communicates with", "signal to", "signal",
                  "signal connection"), symmetric=True),
    R("serves", ("serves", "conditions", "supplies air to", "served zone", "serves zone", "zone served",
                 "supply to", "target area", "area served", "serves area", "served area"), inverse="served by"),
    R("served by", ("served by", "conditioned by", "air source", "served from", "source"),
      inverse="serves", forward=False),
    # a link whose kind isn't said: undirected ("connected to") or directed ("feeds", "directed connection"). The
    # kind may be named beside it ("control signal", "drive shaft", "air or light"); otherwise a true link is
    # implied, not the fact it stands for.
    R("linked", ("connected to", "connection", "connects to", "linked to", "joined to", "associated with",
                 "associated components", "associated", "connections", "link"), symmetric=True),
    R("leads to", ("directed connection", "directed to", "connection to", "points to", "arrow to", "output connection",
                   "output", "goes to", "leads into", "feeds", "supplies", "delivers to", "fed to", "supplies to"),
      inverse="led from"),
    R("led from", ("fed from", "supplied from", "supplied by", "input", "fed by", "receives"), inverse="leads to",
      forward=False),
    R("has option", ("option", "options", "can be", "either", "alternatives", "choice", "choices", "may be",
                     "configurations", "mask options", "selectable", "types"), inverse="option for"),
    R("option for", ("option for", "alternative for", "used as", "can serve as"), inverse="has option",
      forward=False),
    R("alternative to", ("alternative to", "instead of", "or", "alternative", "backup to", "backup for"),
      symmetric=True),
    R("located at", ("located at", "location", "positioned at", "placed at", "position", "plane", "at", "in",
                     "placed in", "conjugate to", "located in"), literal=True),
    R("state", ("movable", "mobility", "motion", "mechanism", "moves", "can move", "state", "adjustable",
                "insertable", "retractable", "deployable", "removable", "mounting type", "selectability",
                "capability", "mechanical property", "property", "feature"), literal=True),
)}
del R

# The kind of a generic link, named beside it (in its conditions, or the legend's words a reader copied).
KINDS = (("drive shaft", "drives"), ("shaft", "drives"), ("drive", "drives"), ("power", "powers"),
         ("electrical", "powers"), ("control signal", "controls"), ("control", "controls"), ("signal", "signals"),
         ("air or light", "precedes"), ("airflow", "precedes"), ("air flow", "precedes"), ("air", "precedes"),
         ("light", "precedes"), ("beam", "precedes"), ("flow", "precedes"))
DIRECTED = ("precedes", "drives", "powers", "controls", "signals", "serves")
# Words that say what kind of thing or link a value is, not which: "connection | power", "input | beam"
GENERIC = {w for word, _ in KINDS for w in word.split()} | {"or", "beam", "present", "shared", "yes", "no", "none",
                                                            "with", "via", "the", "a", "an", "input", "output"}

# Phrases naming a whole path: the things listed are its steps, in order.
SEQUENCE = {"path", "sequence", "order", "flow path", "light path", "air path", "optical path", "beam path",
            "process flow", "flow sequence", "optical path sequence", "air path order", "path order", "train",
            "optical train"}
ARROWS = re.compile(r"\s*(?:->|→|=>|⟶|>)\s*")
AFFIRMATIVE = {"yes", "true", "y"}

def norm(text):
    """Folded for matching: NFKC, casefolded, hyphens and slashes as spaces, other punctuation dropped."""
    text = unicodedata.normalize("NFKC", str(text)).casefold()
    text = re.sub(r"[-‐‑‒–—_/]", " ", text)
    text = re.sub(r"[^\w\s]", " ", text)
    return " ".join(text.split())

def _spans(text, phrase):
    return [(m.start(), m.end()) for m in re.finditer(rf"(?<!\w){re.escape(phrase)}(?!\w)", text)]

@dataclass(frozen=True)
class Thing:
    """A named thing in a document: a part (a component, a zone, a system), or a fact's literal object."""
    name: str
    aliases: tuple = ()
    literal: bool = False

    def names(self):
        return {n for n in (norm(x) for x in (self.name,) + tuple(self.aliases)) if n}

def find_things(text, things):
    """The things a text names, in order: [(start, end, thing)], longest names first, none overlapping."""
    text = norm(text)
    spans = sorted(((s, e, t) for t in things for n in t.names() for s, e in _spans(text, n)),
                   key=lambda x: (-(x[1] - x[0]), x[0]))
    found = []
    for s, e, t in spans:
        if not any(s < fe and fs < e for fs, fe, _ in found):
            found.append((s, e, t))
    return sorted(found, key=lambda x: x[0])

def strip_things(text, found):
    text = norm(text)
    for s, e, _ in sorted(found, key=lambda x: -x[0]):
        text = text[:s] + " " + text[e:]
    return " ".join(text.split())

def relation_of(*texts):
    """(relation, phrase) the words name, by the longest phrase found: the attribute's words before the value's.
    (None, "") when two relations tie, or none is named."""
    for text in texts:
        text, best, length = norm(text), {}, 0
        for relation in RELATIONS.values():
            for phrase in relation.phrases:
                if _spans(text, phrase):
                    if len(phrase) > length:
                        best, length = {relation.name: phrase}, len(phrase)
                    elif len(phrase) == length:
                        best[relation.name] = phrase
        if len(best) == 1:
            return next(iter(best.items()))
        if best:
            return None, ""
    return None, ""

def canonical(subject, relation, obj):
    """A triple in the direction facts are kept: an inverse turned round ("the fan follows the coil" is "the coil
    precedes the fan"), a symmetric relation's ends in name order."""
    r = RELATIONS[relation]
    s, o = (x.name if isinstance(x, Thing) else x for x in (subject, obj))
    if r.symmetric:
        a, b = sorted((s, o))
        return (a, relation, b)
    if not r.forward:
        return (o, r.inverse, s)
    return (s, relation, o)

def _specific(found, ancestors):
    """Of the things an entity names, the one inside the others ("supply fan of AHU-3": the supply fan)."""
    names = {t.name for _, _, t in found}
    inner = [t for _, _, t in found if ancestors.get(t.name, set()) & names]
    return (inner or [t for _, _, t in found])[-1]

def triples(claim, things, path_nodes=(), ancestors=None):
    """The triples a claim states, as (subject, relation, object) Things, or (None, reason) when it names no
    relation, or names what the document doesn't. A path gives its adjacent pairs; a list or an "or" gives one
    triple per member."""
    ancestors = ancestors or {}
    entity, attribute, value = (str(claim.get(k, "") or "") for k in ("entity", "attribute", "value"))
    subjects = find_things(entity, things)
    subject = _specific(subjects, ancestors) if subjects else None

    def path(steps):
        nodes = list(steps)
        if subject is not None and subject.name in path_nodes and nodes and nodes[0] is not subject:
            nodes = [subject] + nodes  # "OA damper | downstream path | mixing box -> filter bank": it starts the path
        return [(a, "precedes", b) for a, b in zip(nodes, nodes[1:])] or [(None, "unscored")]

    raw_value = unicodedata.normalize("NFKC", value)
    if ARROWS.search(raw_value):  # a path written with arrows
        steps = [find_things(part, things) for part in ARROWS.split(raw_value) if part.strip()]
        if any(not s for s in steps):
            return [(None, "invented")]
        return path([s[0][2] for s in steps])
    objects = find_things(value, things)
    attribute_left, value_left = strip_things(attribute, find_things(attribute, things)), strip_things(value, objects)
    if subject is not None and len(objects) == 2 and re.search(r"\bbetween\b", value_left):
        a, b = objects[0][2], objects[1][2]  # "between the filter bank and the supply fan": a step on the path
        return [(a, "precedes", subject), (subject, "precedes", b)]
    # the attribute read whole and with its names taken out ("input source": "input" is also a part's name);
    # the longer phrase wins, then the value's words
    whole, left = relation_of(attribute), relation_of(attribute_left)
    relation, phrase = max((whole, left), key=lambda x: len(x[1]))
    if relation is None:
        relation, phrase = relation_of(value_left)
    if relation is None and len(objects) >= 2 and re.search(r"\bor\b|/", value):  # "type | wide stop / narrow stop"
        relation, phrase = "has option", "options"
    if relation is None and len(objects) == 1:  # "UV channel | detector | EMCCD": a part named, as what it is
        obj = objects[0][2]
        named = find_things(attribute, things)
        words = set(norm(attribute).split())
        if (named and named[-1][2] is obj) or (words and any(words <= set(n.split()) for n in obj.names())):
            relation, phrase = "has part", "component"
    if relation in ("linked", "leads to", "led from"):  # the kind, when named: "connects to | ... | drive shaft"
        context = " ".join(norm(str(claim.get(k, "") or "")) for k in ("conditions", "attribute"))
        context += " " + value_left
        kind = next((r for word, r in KINDS if re.search(rf"\b{word}\b", context)), None)
        if kind:
            relation = kind if relation != "led from" else (RELATIONS[kind].inverse or kind)
    if relation and RELATIONS[relation].literal and objects and not any(t.literal for _, _, t in objects):
        better, better_phrase = relation_of(value_left)  # "position | after the cooling coil": the value says how
        if better:
            relation, phrase = better, better_phrase
    if relation is None:
        return [(None, "unscored")]
    r = RELATIONS[relation]
    if not objects and r.literal and norm(value) in AFFIRMATIVE | {""}:  # "filter wheel | movable | yes"
        named = [t for _, _, t in find_things(attribute, things) if t.literal]
        objects = [(0, 0, named[-1])] if named else []
    if subject is None:
        return [(None, "invented")] if objects else [(None, "unscored")]
    if not objects:  # a name the document doesn't have, or a description: only a short value counts as a name
        words = set(norm(value).split()) - GENERIC
        return [(None, "invented")] if 0 < len(words) and len(norm(value).split()) <= 3 else [(None, "unscored")]
    items = [t for _, _, t in objects if t is not subject]
    if relation in ("precedes", "follows") and phrase in SEQUENCE and len(items) >= 2:
        return path(items)  # "air path order | mixing box, filter bank, cooling coil"
    # a list's members that name nothing in the document ("..., humidifier") are invented
    unknown = [chunk for chunk in re.split(r"\s*(?:[,;]|\band\b|\bor\b)\s*", value)
               if chunk.strip() and not find_things(chunk, things) and 0 < len(norm(chunk).split()) <= 3]
    out = [(None, "invented")] * (len(unknown) if len(objects) > 0 and re.search(r"[,;]|\band\b|\bor\b", value) else 0)
    for obj in items:
        if r.literal != obj.literal:
            if relation in ("within", "located at"):
                out.append((subject, "located at" if obj.literal else "within", obj))  # "in AHU-3": a part as a place
            else:
                out.append((None, "unscored"))
            continue
        out.append((subject, relation, obj))
    return out or [(None, "unscored")]

class Index:
    """The facts' triples, kept one way round, and what their chains imply."""
    def __init__(self, facts):
        self.facts = {}
        for f in facts:
            for relation in (f["relation"],) + tuple(f.get("accepts") or ()):
                self.facts[canonical(f["entity"], relation, f["value"])] = f["id"]
        self.edges = {}
        for (s, r, o) in self.facts:
            if RELATIONS[r].transitive:
                self.edges.setdefault(r, {}).setdefault(s, set()).add(o)
        self.path_nodes = {x for (s, r, o) in self.facts if r == "precedes" for x in (s, o)}
        self.ancestors = {}
        for r in ("part of", "within"):
            for a in self.edges.get(r, {}):
                self.ancestors.setdefault(a, set()).update(self.closure(r, a))

    def closure(self, relation, a):
        seen, todo = set(), [a]
        graph = self.edges.get(relation, {})
        while todo:
            for y in graph.get(todo.pop(), ()):
                if y not in seen:
                    seen.add(y)
                    todo.append(y)
        return seen

    def related(self, a, b):
        return any({x, y} == {a, b} for (x, _, y) in self.facts)

    def directed(self, a, b):
        return next((fid for (x, r, y), fid in self.facts.items() if x == a and y == b and r in DIRECTED), None)

    def targets(self, a, relation):
        return {y for (x, r, y) in self.facts if x == a and r == relation}

    def options_of(self, name):
        return {s for (s, r, o) in self.facts if r == "has option" and o == name}

    def classify(self, subject, relation, obj):
        """(outcome, fact id or None) for one triple."""
        key = canonical(subject, relation, obj)
        if key in self.facts:
            return "right", self.facts[key]
        s, r, o = key
        rel = RELATIONS[r]
        if not rel.symmetric and not rel.literal and (o, r, s) in self.facts:
            return "reversed", self.facts[(o, r, s)]
        if rel.transitive and o in self.closure(r, s):
            return "implied", None
        if r == "within" and o in self.closure("part of", s) or r == "part of" and o in self.closure("within", s):
            return "implied", None  # a part drawn inside its whole, or a thing inside what it's part of
        if r == "alternative to" and self.options_of(s) & self.options_of(o):
            return "implied", None  # two options of one thing
        upstream = lambda a, b: b in self.closure("precedes", a) or any(
            b in self.ancestors.get(x, ()) for x in self.closure("precedes", a))  # to b, or to a part of b
        if r == "linked":  # a link of unsaid kind: true, but not the fact it stands for
            near = self.related(s, o) or upstream(s, o) or upstream(o, s)
            return ("implied", None) if near else ("wrong", None)
        if r == "leads to":  # an arrow read, its kind not said: the fact it follows, if any
            fid = self.directed(s, o)
            if fid:
                return "right", fid
            if upstream(s, o):
                return "implied", None  # two steps on, or into a whole
            return ("reversed", self.directed(o, s)) if self.directed(o, s) or upstream(o, s) else ("wrong", None)
        if r == "precedes" and upstream(s, o):
            return "implied", None  # into a whole: "the input beam feeds the UV channel"
        if r in DIRECTED and r != "precedes" and any(o in self.ancestors.get(x, ()) for x in self.targets(s, r)):
            return "implied", None  # "the motor drives AHU-3": it drives a part of AHU-3
        if r == "serves" and o in self.closure("precedes", s) or r == "precedes" and (s, "serves", o) in self.facts:
            return "implied", None  # what's upstream serves what's downstream
        if r in ("has part", "contains") or r in ("part of", "within"):
            whole, part = (s, o) if r in ("has part", "contains") else (o, s)
            if any(whole in self.ancestors.get(x, ()) or (x, "part of", whole) in self.facts for x in self.options_of(part)):
                return "implied", None  # an option of one of its parts
        if rel.transitive and not rel.symmetric and s in self.closure(r, o):
            return "reversed", None
        return "wrong", None

def classify_claim(claim, things, index):
    """[(outcome, fact id or None, triple or None)] for one claim: one entry per triple it states."""
    out = []
    for t in triples(claim, things, index.path_nodes, index.ancestors):
        if t[0] is None:
            out.append((t[1], None, None))
        else:
            outcome, fid = index.classify(*t)
            out.append((outcome, fid, canonical(*t)))
    return out
