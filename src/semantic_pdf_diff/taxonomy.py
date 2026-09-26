"""What reviewers judge: verdicts, error flags, clarity and confidence, per item type.

Design (see benchmarks/README.md for sources): a coarse verdict first, then any number
of specific flags. Coarse verdicts agree far better between reviewers than error
categories do, and flags keep the detail. Every flag has a one-line definition and an
engineering example, which both people and panel models see. Names are stable: labels
store them, so rename only with a migration.
"""

def _f(group, name, label, help):
    return {"group": group, "name": name, "label": label, "help": help}

CLAIM_FLAGS = [
    # What is claimed: binding the value to the right thing, at the right level.
    _f("What is claimed", "entity_misbound", "Value bound to the wrong component or thing",
       "e.g. Pump B's 45 kW recorded as Pump A's"),
    _f("What is claimed", "scope_level_error", "Wrong level: per-unit vs total, component vs system",
       "e.g. a 2 kW per-module rating claimed as the whole array's power"),
    _f("What is claimed", "attribute_misassigned", "Right thing, wrong or overstated property",
       "e.g. peak power recorded as continuous rating; 'composition: glass' when glass is one of several materials"),
    _f("What is claimed", "relation_direction_reversed", "Directed relationship reversed",
       "e.g. 'HX-1 feeds P-2' when P-2 feeds HX-1"),
    _f("What is claimed", "referent_ambiguous", "Entity too vague to identify",
       "e.g. entity 'the unit' or 'system' with no way to tell which"),
    _f("What is claimed", "aggregation_unsupported", "Computed, summed or inferred value presented as stated",
       "e.g. 'total 120 MW' when the source only lists 3 x 40 MW"),
    # Value and unit.
    _f("Value and unit", "value_misread", "Wrong digits, sign or decimal point", "e.g. 0.35 read as 3.5"),
    _f("Value and unit", "unit_wrong_or_missing", "Unit wrong, missing or mis-converted", "e.g. psi recorded as kPa"),
    _f("Value and unit", "scale_factor_missed", "A multiplier in a header or caption ignored",
       "e.g. a 'Cost ($k)' column recorded as dollars; % vs fraction"),
    _f("Value and unit", "bound_or_range_collapsed", "A limit, range or tolerance reduced to one number",
       "e.g. '<= 85 dBA' recorded as 85 dBA; '10 +/- 0.5' as 10"),
    _f("Value and unit", "approximation_misflagged", "Approximate or estimated reading marked exact (or vice versa)",
       "e.g. '~12 t', or a value read off a chart, marked exact"),
    _f("Value and unit", "value_fabricated", "Value not in the source at all", "e.g. a typical steel density filled in"),
    # Qualifiers: the conditions under which the value holds.
    _f("Conditions and basis", "condition_dropped", "An operating condition or scope left out",
       "e.g. efficiency without 'at 50% load'"),
    _f("Conditions and basis", "condition_misattached", "A condition belonging to something else",
       "e.g. the hot-day condition attached to the ISO rating"),
    _f("Conditions and basis", "basis_wrong", "Requirement, target, estimate and measurement confused",
       "e.g. a 'shall be >= 95%' requirement recorded as a measured result"),
    _f("Conditions and basis", "time_or_version_wrong", "Wrong year, phase, revision or life stage",
       "e.g. end-of-life capacity reported as beginning-of-life"),
    _f("Conditions and basis", "scenario_confused", "Baseline, option or case values swapped",
       "e.g. option B's mass attributed to the baseline"),
    _f("Conditions and basis", "polarity_or_negation_error", "Negation or limit direction lost",
       "e.g. 'shall not exceed 60 C' recorded as 'is 60 C'"),
    # Where it came from.
    _f("Provenance", "quote_not_verbatim", "Quote paraphrased or stitched together", "e.g. a quote joining two cells"),
    _f("Provenance", "quote_not_supporting", "Quote exists but doesn't support this value or entity",
       "e.g. the quote names Pump A; the value is Pump B's"),
    _f("Provenance", "region_wrong", "The highlighted region doesn't contain the claim", ""),
    _f("Provenance", "extrinsic_knowledge", "From general knowledge, not this document",
       "e.g. a standard material property inserted"),
    _f("Provenance", "confidence_miscalibrated", "Model confidence clearly too high or too low",
       "e.g. 0.95 on a value misread from a log axis"),
    # Reading tables, charts, diagrams and drawings.
    _f("Tables, charts and drawings", "table_header_misaligned", "Wrong row or column header (incl. multi-level)",
       "e.g. value taken from the 'Max' column instead of 'Nominal'"),
    _f("Tables, charts and drawings", "table_note_lost", "Merged cell, footnote or note qualifier lost",
       "e.g. footnote 'a) at 20 C' ignored"),
    _f("Tables, charts and drawings", "chart_axis_misread", "Axis misread: interpolation, log scale, second axis",
       "e.g. 300 on a log axis read as 30"),
    _f("Tables, charts and drawings", "chart_series_swapped", "Legend or series mixed up",
       "e.g. the design A curve read as design B"),
    _f("Tables, charts and drawings", "chart_trend_wrong", "Direction or size of a change wrong",
       "e.g. 'rises sharply' for a flat line"),
    _f("Tables, charts and drawings", "diagram_edge_invented", "Connection that isn't in the diagram",
       "e.g. a valve linked to a nearby but unconnected tank"),
    _f("Tables, charts and drawings", "diagram_edge_direction_reversed", "Arrow or flow direction reversed", ""),
    _f("Tables, charts and drawings", "drawing_callout_misbound", "Dimension, tolerance or note on the wrong feature",
       "e.g. +/-0.05 applied to the wrong bore"),
    # Form: is it a good claim at all.
    _f("Form", "not_atomic", "Several facts fused into one claim", "e.g. 'mass 12 t and height 90 m' as one value"),
    _f("Form", "trivial_or_boilerplate", "True but useless for comparison",
       "e.g. a page number, drawing scale or revision date"),
    _f("Form", "kind_wrong", "Claim kind wrong (text, table, chart, diagram)", ""),
    _f("Form", "nearby_claims_missed", "Clearly important facts next to it were not extracted",
       "a coverage signal: say what was missed in the note"),
]

ABOUT_FLAGS = [
    _f("Content", "about_out_of_context", "States something not shown or not in the section",
       "e.g. 'shows cost savings' for a mass chart"),
    _f("Content", "about_wrong_subject", "Wrong subject, variable or scope",
       "e.g. says the whole system when it covers one subsystem"),
    _f("Content", "about_misses_main_point", "Misses what the figure or section is mainly about", ""),
    _f("Content", "about_too_generic", "True but uninformative", "e.g. 'a chart of performance'"),
    _f("Content", "about_states_values", "States specific values or design decisions", "e.g. 'shows the 126 m rotor'"),
    _f("Context", "role_wrong", "The figure's stated purpose is wrong or invented", ""),
    _f("Context", "type_or_density_wrong", "Section type or density is wrong", "e.g. a data table called narrative"),
    _f("Context", "keywords_poor", "Keywords miss the main components or topics", ""),
]

PAIR_FLAGS = [
    _f("Pairing", "pairing_irrelevant", "The two claims aren't about the same thing at all",
       "retrieval shouldn't have paired them"),
    _f("Pairing", "upstream_claim_error", "One of the claims is itself wrong, so the judgment can't be right", ""),
    _f("Relation", "false_equivalent", "Called equivalent despite different conditions, scope or basis",
       "e.g. hot-day vs ISO rating"),
    _f("Relation", "false_different", "Called different over units, rounding or wording",
       "e.g. 1.2 MW vs 1200 kW"),
    _f("Relation", "should_be_equivalent", "Should be: equivalent", ""),
    _f("Relation", "should_be_different", "Should be: different", ""),
    _f("Relation", "should_be_complementary", "Should be: complementary (compatible, different aspects)", ""),
    _f("Relation", "should_be_unrelated", "Should be: unrelated", ""),
    _f("Relation", "should_be_uncertain", "Should be: uncertain (not enough to tell)", ""),
    _f("Relation", "rationale_wrong", "Right relation for the wrong reason", ""),
    _f("Relation", "would_relate_if_same_subject", "Would relate (e.g. complementary) if about the same subject, "
       "but they aren't, or it's unclear", "e.g. two turbines' pitch settings"),
]

TAXONOMY = {
    "claim": {"verdicts": [
        {"name": "correct", "label": "Correct", "help": "A faithful reading of the source (usefulness is judged by flags)"},
        {"name": "flawed", "label": "Usable but flawed",
         "help": "The core fact is right, but a qualifier, quote, scope or form is off, or part of the truth is stated as the whole"},
        {"name": "wrong", "label": "Wrong", "help": "The fact is misread, misbound or not supported"},
        {"name": "not_a_claim", "label": "Not a claim", "help": "Commentary, a heading or a fragment, not a fact"}],
        "flags": CLAIM_FLAGS},
    "about": {"verdicts": [
        {"name": "good", "label": "Good", "help": "Correct and tells a reader what to expect"},
        {"name": "acceptable", "label": "Acceptable", "help": "Correct but vague or incomplete"},
        {"name": "wrong", "label": "Wrong", "help": "Misleading or incorrect"}],
        "flags": ABOUT_FLAGS},
    "pair": {"verdicts": [
        {"name": "right", "label": "Relation right",
         "help": "Relations: equivalent = same engineering meaning; different = incompatible values under the same conditions; "
                 "complementary = distinct compatible information about a corresponding subject; unrelated = different "
                 "subject or property; uncertain = correspondence can't be established"},
        {"name": "wrong", "label": "Relation wrong", "help": "Flag what it should be"}],
        "flags": PAIR_FLAGS},
}

# The coarse question agreement is best measured on: is the result usable?
USABLE = {"claim": {"correct", "flawed"}, "about": {"good", "acceptable"}, "pair": {"right"}}

# Quick per-field answers shown next to each part of an item: the fastest way to say what's wrong.
FIELD_ANSWERS = [
    {"name": "ok", "label": "\u2713", "help": "Right"},
    {"name": "wrong", "label": "\u2717", "help": "Wrong (or missing when it should be there)"},
    {"name": "unsure", "label": "?", "help": "Can't tell, or contested"},
]

def _field(name, label, help=""):
    return {"name": name, "label": label, "help": help}

FIELDS = {
    "claim": [_field("entity", "Entity", "The thing the value belongs to, at the right level"),
              _field("attribute", "Attribute", "The property, stated specifically enough"),
              _field("value", "Value", "Digits, bounds and ranges"),
              _field("unit", "Unit", "Including scale factors; wrong if missing"),
              _field("conditions", "Conditions", "Load case, scenario, scope; wrong if a needed one is missing"),
              _field("basis", "Basis", "Requirement, target, measured, calculated... 'unknown' is right only "
                     "when the source doesn't say; it is wrong for a 'shall' or 'must' (required) or a reported measurement"),
              _field("approximate", "Approximate", "Readings off charts should be approximate"),
              _field("quote", "Quote", "Verbatim, and supports the claim"),
              _field("section", "Section", "The section it was attributed to")],
    "about": [_field("about", "About", "What it depicts or covers, without values"),
              _field("role", "Role", "Why the document includes it"),
              _field("keywords", "Keywords"),
              _field("type", "Type and density", "Sections only")],
    "pair": [_field("a", "Claim A is read correctly"),
             _field("b", "Claim B is read correctly"),
             _field("same_subject", "Same subject, or counterparts in two designs"),
             _field("relation", "The judged relation is right")],
}

# Suggested verdict from field answers (the reviewer can always choose another).
CORE_FIELDS = {"claim": {"entity", "attribute", "value"}, "about": {"about"}, "pair": {"relation"}}

# --- judging questions (the model's input, before seeing its answer) ---------------------

ADEQUACY = [
    {"name": "enough", "label": "Enough", "help": "Everything needed to answer fully is in the input"},
    {"name": "partly", "label": "Partly", "help": "Something useful is missing, but a partial answer is possible"},
    {"name": "not_enough", "label": "Not enough", "help": "A good answer isn't possible from this input"},
]

MISSING = [
    _field("heading", "Section heading or title", "e.g. which contest, component or subsystem this is about"),
    _field("surrounding_text", "Surrounding text", "the sentence or paragraph before or after the chunk"),
    _field("legend_or_key", "Legend, key or axis labels", "cut off, or elsewhere on the page"),
    _field("caption", "Caption or figure title", ""),
    _field("table_header", "Table header or row labels", ""),
    _field("resolution", "Resolution", "small labels or dimensions can't be read"),
    _field("other_page", "Something on another page", "e.g. a table continued, a definition, a referenced figure"),
    _field("domain_knowledge", "Domain knowledge", "how to read this kind of chart or drawing"),
    _field("instructions", "Clearer instructions", "the request itself is ambiguous for this input"),
]

WORTH = [
    {"name": "worth", "label": "Worth asking", "help": "The input holds facts worth extracting"},
    {"name": "little", "label": "Little value", "help": "Mostly boilerplate, labels or fragments"},
    {"name": "none", "label": "Nothing to extract", "help": "e.g. an empty region or only decoration"},
]

# Usefulness of a claim as final evidence, with the context attached to it after extraction.
USEFULNESS = [
    {"name": "usable", "label": "Usable as is", "help": "Clear enough to compare with other sources"},
    {"name": "with_context", "label": "Usable with its context", "help": "Only with its section or linked figure"},
    {"name": "not_useful", "label": "Not useful", "help": "Trivial, vague or unanchored even in context"},
]

# One line per kind of request, so reviewers learn to recognise the (folded) instructions.
REQUEST_SUMMARIES = {
    ("extract", "text"): "Extract up to N atomic engineering claims (entity, attribute, value, unit, conditions, quote) from a text chunk.",
    ("extract", "table"): "Extract claims from one table row, given the table's header.",
    ("extract", "tile"): "Extract claims from an image of part of a page (a tile), checked against the page's text where possible.",
    ("extract", "figure"): "Extract claims from an image of one detected figure, with its caption.",
    ("extract", "overview"): "Extract claims from a low-resolution image of the whole page.",
    ("triage", "figure"): "Say what a figure depicts and why it's there, from its location, caption, surrounding text and citing paragraphs.",
    ("triage", "section"): "Say what a section covers (type, density, keywords, about) from its heading, text, claims and figures.",
    ("compare", "proposals"): "Relate two claims from competing designs: equivalent, different, complementary, unrelated or uncertain.",
    ("compare", "revisions"): "Relate two claims from two revisions of one document: equivalent, different, complementary, unrelated or uncertain.",
}

CLARITY = [
    {"name": "clear", "label": "Clear", "help": "I could judge this item"},
    {"name": "context_insufficient", "label": "Context insufficient",
     "help": "I'd need more of the document than shown to judge"},
    {"name": "source_illegible", "label": "Source illegible", "help": "The image or text can't be read well enough"},
    {"name": "reading_unclear", "label": "Not sure how to read the source",
     "help": "e.g. a chart or drawing convention I don't know; a domain expert might"},
    {"name": "item_ambiguous", "label": "Item or question ambiguous",
     "help": "The item could be read several ways, or the categories don't fit it"},
]

CONFIDENCE = [
    {"name": "high", "label": "High", "help": "I'd stake a review comment on it"},
    {"name": "medium", "label": "Medium", "help": "Probably right"},
    {"name": "low", "label": "Low", "help": "A guess, or outside what I know"},
]

def field_names(kind):
    return {f["name"] for f in FIELDS[kind]}

def suggested_verdict(kind, fields):
    """A verdict implied by per-field answers, or None when nothing is answered."""
    if not fields:
        return None
    wrong = {f for f, answer in fields.items() if answer == "wrong"}
    if kind == "claim":
        return "wrong" if wrong & CORE_FIELDS["claim"] else "flawed" if wrong else "correct"
    if kind == "about":
        return "wrong" if wrong & CORE_FIELDS["about"] else "acceptable" if wrong else "good"
    return "wrong" if "relation" in wrong else "right"

def flag_names(kind):
    return {f["name"] for f in TAXONOMY[kind]["flags"]}
