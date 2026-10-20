"""Values as printed: numbers, dates, lengths in feet and inches, and units with their kinds (code review 2026-10-01:
number parsing written five ways, in five modules).

Two unit tables stay apart on purpose. The product's (UNITS: SI, deliberately small) enters comparison prompts
through compare.numeric_check, so a change to it changes requests and every recorded comparison answer would miss.
The scorer's (UNIT_KINDS) covers the controlled corpus's units and their spellings. Merging them is a decision for a
round, not a clean-up. The product's text folding (extract.FOLD, readings.QUOTES) stays with its users for the same
reason: it decides which quotes verify, which decides which tasks are refined.

A search's unit table (SEARCH_UNITS) is read from both and from units only it knows (SEARCH_EXTRA), changing
neither: it decides what a search finds, nothing a model is asked.
"""
import re
import unicodedata

# --- numbers and dates

def vulgar_fractions(text):
    """"9½" as "9 1/2": a fraction character written out, apart from a whole number before it (NFKC alone makes
    "9½" read 91/2; code review 2026-10-08, E19)."""
    return "".join(" " + unicodedata.normalize("NFKC", ch).replace("⁄", "/") + " "
                   if unicodedata.decomposition(ch).startswith("<fraction>") else ch for ch in str(text))

def parse_number(text):
    """The first number in a value as printed ("1,250" → 1250.0, "-0.8" → -0.8, "±0.05" → 0.05), or None."""
    text = unicodedata.normalize("NFKC", vulgar_fractions(text)).replace("−", "-").replace("–", "-")
    m = re.search(r"-?\d[\d,]*(?:\.\d+)?|-?\.\d+", text)
    if not m:
        return None
    try:
        return float(m.group(0).replace(",", ""))
    except ValueError:
        return None

DATE = re.compile(r"^\s*(\d{4})-(\d{2})-(\d{2})\s*$")

def same_number(a, b):
    return a is not None and b is not None and abs(a - b) <= 1e-9 * max(1.0, abs(a), abs(b))

# --- words

def singular(word):
    """A word's plural "s" dropped ("pumps" → "pump"), not a word's own ("glass", "gas")."""
    return word[:-1] if len(word) > 3 and word.endswith("s") and not word.endswith("ss") else word

# --- lengths in feet and inches

# Inches as a drafter writes them: 6, 6.5, 6 1/2 or 1/2 (a fraction, as on dimension strings).
INCH = r"(?:(\d+(?:\.\d+)?)(?:\s*-?\s*(\d+)\s*/\s*(\d+))?|(\d+)\s*/\s*(\d+))"
FEET_INCHES = re.compile(rf"^\s*(\d+)\s*'\s*-?\s*{INCH}?\s*(?:\"|'')?\s*$")

def ft_in(inches):
    """Inches as a drafter writes them: 702 -> 58'-6\"."""
    feet, rest = divmod(int(round(inches)), 12)
    return f"{feet}'-{rest}\""

def _inch(groups):
    """Inches from INCH's five groups (whole, numerator, denominator; or a bare fraction's two)."""
    whole, num, den, bare_num, bare_den = groups
    if bare_num:
        return int(bare_num) / int(bare_den) if int(bare_den) else None
    if num and not int(den):
        return None
    return float(whole or 0) + (int(num) / int(den) if num else 0.0)

def inches(value, unit=""):
    """A length in inches, from 58'-6\", 2'-9 1/2\", 58 ft 6 in, 58.5 ft, 702 in, 9 1/2" or 58.5 with unit ft; None
    if it isn't one. (Fractions were read as their whole part, or not at all: code review 2026-10-01, item 10.)"""
    text = " ".join(vulgar_fractions(value).split()).replace("′", "'").replace("″", '"').replace("’", "'") \
        .replace("”", '"').replace(' "', '"')
    m = FEET_INCHES.match(text)
    if m:
        rest = _inch(m.groups()[1:])
        return None if rest is None else int(m.group(1)) * 12 + rest
    m = re.match(rf"^\s*(\d+(?:\.\d+)?)\s*(?:ft|feet|foot)\.?\s*(?:{INCH}\s*(?:in|inch|inches)\.?)?\s*$", text, re.I)
    if m:
        rest = _inch(m.groups()[1:])
        return None if rest is None else float(m.group(1)) * 12 + rest
    m = re.match(rf"^\s*{INCH}\s*(?:in|inch|inches|\")\.?\s*$", text, re.I)
    if m:
        return _inch(m.groups())
    m = re.match(r"^\s*(\d+(?:\.\d+)?)\s*$", text)
    if m and str(unit).strip().lower() in ("ft", "feet", "foot", "'"):
        return float(m.group(1)) * 12
    if m and str(unit).strip().lower() in ("in", "inch", "inches", '"'):
        return float(m.group(1))
    return None

def printed_value(text):
    """A printed number, for finding values on the page: lengths in feet and inches as inches (38'-6" is 462, not
    38), dates as dates (2026-01-10, not 2026), anything else as parse_number reads it."""
    if DATE.match(str(text)):
        return ("date", str(text).strip())
    if "'" in str(text):
        length = inches(text)
        if length is not None:
            return ("in", length)
    return parse_number(text)

# --- units: the product's

# Deliberately small, explicit dimensional conversions. Unknown units abstain.
# No currency, affine temperature, ambiguous "ton", ranges or inequalities.
# Keys are case-sensitive: SI prefixes differ by case (mW/MW, mPa/MPa) and so do
# some symbols (s second vs S siemens, m metre vs M molar).
UNITS = {
    "mW": ("power", ".001"), "W": ("power", "1"), "kW": ("power", "1000"), "MW": ("power", "1000000"),
    "mPa": ("pressure", ".001"), "Pa": ("pressure", "1"), "kPa": ("pressure", "1000"), "MPa": ("pressure", "1000000"),
    "bar": ("pressure", "100000"), "m": ("length", "1"), "mm": ("length", ".001"),
    "cm": ("length", ".01"), "km": ("length", "1000"), "kg": ("mass", "1"), "g": ("mass", ".001"),
    "s": ("time", "1"), "min": ("time", "60"), "h": ("time", "3600"),
    "L/s": ("flow", ".001"), "m3/s": ("flow", "1"), "m³/s": ("flow", "1"),
    "L/min": ("flow", ".00001666666666666666666666666667"),
    "%": ("percent", "1"), "Hz": ("frequency", "1"), "kHz": ("frequency", "1000"), "MHz": ("frequency", "1000000"),
}
# Case variants accepted only where no other unit folds to the same spelling.
FOLDED = {k.casefold(): k for k in ("kW", "kPa", "bar", "km", "kg", "min", "L/s", "L/min", "m3/s", "m³/s", "Hz", "kHz")}

def unit(text):
    text = text.strip()
    return UNITS.get(text) or UNITS.get(FOLDED.get(text.casefold(), ""))

# --- units: the scorer's

# Typed values (code review 2026-10-01, item 10: "5,151 ft" held a flow in gpm). A unit's kind and its size in the
# kind's base: values of two kinds never hold each other's facts, and one kind compares by magnitude ("10,000 W" is
# "10 kW"). A unit not listed, or none, abstains: the number decides, as before. The corpus's units and their
# common spellings; compare.UNITS is the product's own (its numeric check enters comparison prompts), and the
# clean-up's values module (milestone 6) is to hold both.
UNIT_KINDS = {kind: units for kind, units in (
    ("length", {"in": 1, "inch": 1, "inches": 1, '"': 1, "ft": 12, "feet": 12, "foot": 12, "'": 12, "m": 39.3701,
                "mm": 0.0393701, "cm": 0.393701}),
    ("area", {"ft²": 1, "ft2": 1, "sf": 1, "sq ft": 1, "sq. ft": 1, "square feet": 1, "m²": 10.7639, "m2": 10.7639}),
    ("speed", {"mph": 1, "mi/h": 1, "m/s": 2.23694, "km/h": 0.621371, "kph": 0.621371, "ft/s": 0.681818,
               "fps": 0.681818}),
    ("pressure", {"psi": 1, "psig": 1, "psia": 1, "psf": 1 / 144, "ksi": 1000, "kPa": 0.145038, "Pa": 0.000145038,
                  "bar": 14.5038, "MPa": 145.038}),
    ("force", {"kips": 1, "kip": 1, "lb": 0.001, "lbs": 0.001, "lbf": 0.001, "kN": 0.224809}),
    ("tonnage", {"tons": 1, "ton": 1}),
    ("energy", {"MWh": 1, "kWh": 0.001, "GWh": 1000, "Wh": 0.000001}),
    ("energy a year", {"MWh/yr": 1, "MWh/year": 1, "kWh/yr": 0.001, "kWh/year": 0.001}),
    ("power", {"kW": 1, "W": 0.001, "MW": 1000, "hp": 0.7457, "bhp": 0.7457}),
    ("flow", {"gpm": 1, "gal/min": 1, "MGD": 694.444, "L/s": 15.8503, "cfs": 448.831, "cfm": 7.48052,
              "scfm": 7.48052, "acfm": 7.48052, "m3/h": 4.40287, "m³/h": 4.40287}),
    ("loading rate", {"gpm/ft²": 1, "gpm/ft2": 1, "gpm/sf": 1, "gpm/sq ft": 1}),
    ("rotation", {"rpm": 1, "r/min": 1}),
    ("time", {"s": 1, "sec": 1, "second": 1, "seconds": 1, "min": 60, "mins": 60, "minute": 60, "minutes": 60,
              "h": 3600, "hr": 3600, "hrs": 3600, "hour": 3600, "hours": 3600}),
    ("acceleration", {"g": 1, "G": 1, "m/s²": 0.101972, "m/s2": 0.101972}),
    ("people", {"persons": 1, "person": 1, "people": 1, "occupants": 1, "riders": 1, "seats": 1}),
    ("people an hour", {"riders/h": 1, "riders/hr": 1, "riders per hour": 1, "persons/h": 1, "pph": 1}),
    ("money", {"$M": 1, "M$": 1, "$K": 0.001, "$": 0.000001}),
    ("degrees F", {"°F": 1, "F": 1, "deg F": 1, "degF": 1}),
    ("degrees C", {"°C": 1, "C": 1, "deg C": 1, "degC": 1}),
    ("sound", {"dBA": 1, "dB(A)": 1, "dB": 1}),
    ("concentration", {"mg/L": 1, "ppm": 1}),
    ("turbidity", {"NTU": 1}),
    ("angle", {"°": 1, "deg": 1, "degrees": 1}),
    ("rate", {"1/s": 1, "s−1": 1, "s-1": 1, "/s": 1}),  # NFKC: s⁻¹ is s−1
    ("percent", {"%": 1, "percent": 1}),
)}
_EXACT = {u: (kind, size) for kind, units in UNIT_KINDS.items() for u, size in units.items()}
# Case matters only where a letter's case changes the unit (m metre, M mega; g, G; s, S); longer spellings fold.
_FOLDED = {u.casefold(): ks for u, ks in _EXACT.items() if len(u) > 1 and u.casefold() not in
           {v.casefold() for v in _EXACT if v != u}}

def unit_kind(text):
    """(kind, size in the kind's base) of a unit as written, or None when it isn't listed."""
    text = " ".join(unicodedata.normalize("NFKC", str(text)).split()).rstrip(".")  # NFKC: ft² is ft2
    text = re.sub(r"^(?:per|in)\s+", "", text)
    return _EXACT.get(text) or _FOLDED.get(text.casefold())

# --- units: a search's (docs/plans/search-2026-10-20.md, milestone 3)

# Units only a search knows, in SI: those engineering documents use that the product's table leaves out (it enters
# comparison prompts, so it stays as it is). "°" and "rpm" bridge the scorer's angles and rotations into SI.
_TAU = 6.283185307179586
SEARCH_EXTRA = {
    "N": ("force", 1), "kN": ("force", 1e3), "MN": ("force", 1e6),
    "N.m": ("moment", 1), "Nm": ("moment", 1), "kN.m": ("moment", 1e3), "kNm": ("moment", 1e3),
    "MN.m": ("moment", 1e6), "MNm": ("moment", 1e6),
    "N.m2": ("bending stiffness", 1), "kN.m2": ("bending stiffness", 1e3), "MN.m2": ("bending stiffness", 1e6),
    "N/m": ("force per length", 1), "kN/m": ("force per length", 1e3),
    "N/m2": ("pressure", 1), "N/mm2": ("pressure", 1e6), "GPa": ("pressure", 1e9),
    "t": ("mass", 1000), "tonne": ("mass", 1000), "tonnes": ("mass", 1000), "gram": ("mass", .001),
    "grams": ("mass", .001), "kilogram": ("mass", 1), "kilograms": ("mass", 1),
    "kg/m": ("mass per length", 1), "kg/m3": ("density", 1), "g/cm3": ("density", 1000), "t/m3": ("density", 1000),
    "kg.m": ("mass moment", 1), "kg.m2": ("moment of inertia", 1), "t.m2": ("moment of inertia", 1000),
    "A": ("current", 1), "kA": ("current", 1e3), "mA": ("current", .001),
    "V": ("voltage", 1), "kV": ("voltage", 1e3), "mV": ("voltage", .001),
    "rad": ("angle", 1), "°": ("angle", _TAU / 360),
    "rad/s": ("rotation", 1), "rpm": ("rotation", _TAU / 60),
    "day": ("time", 86400), "days": ("time", 86400), "year": ("time", 31557600), "years": ("time", 31557600),
    "yr": ("time", 31557600),
}

def _search_units():
    """The units a search compares values in: {spelling: (kind, size in the kind's base)}, the product's table, the
    search's own and the scorer's together, none changed. A kind the SI tables hold is put in their base through a
    spelling both hold (the scorer's inches become metres through "m"); a spelling the product's table holds keeps
    its meaning there ("g" is a gram, not g-force)."""
    out = {u: (kind, float(size)) for u, (kind, size) in UNITS.items()}
    for u, (kind, size) in SEARCH_EXTRA.items():
        out.setdefault(u, (kind, float(size)))
    for kind, units in UNIT_KINDS.items():
        bridge = next((u for u in units if out.get(u, ("",))[0] == kind), None)
        scale = out[bridge][1] / units[bridge] if bridge else 1.0
        for u, size in units.items():
            out.setdefault(u, (kind, size * scale))
    return out

SEARCH_UNITS = _search_units()
# a spelling lowercased, where every unit lowercasing to it means the same ("rpm" for "RPM"; "mw" is mW or MW: none)
SEARCH_FOLDED = {}
for _u, _ks in SEARCH_UNITS.items():
    if len(_u) > 1:
        SEARCH_FOLDED.setdefault(_u.lower(), set()).add(_ks)
SEARCH_FOLDED = {u: next(iter(ks)) for u, ks in SEARCH_FOLDED.items() if len(ks) == 1}

def spelled(text):
    """A unit as a search looks it up: "º" a degree (NFKC would make it "o"), NFKC (m² is m2), a product's dot
    however written (N·m, N•m, N*m, kN-m are N.m), no "^" (m^3 is m3), spaces collapsed, a final period dropped.
    search.js spells it alike."""
    text = unicodedata.normalize("NFKC", str(text).replace("º", "°"))
    text = re.sub(r"(?<=[A-Za-zµμ])-(?=[A-Za-z])", ".", re.sub("[·•⋅*×]", ".", text)).replace("^", "")
    return " ".join(text.split()).rstrip(".")

def search_unit(text):
    """(kind, size in its base) of a unit as a search reads it, or None: as spelled, else lowercased where that's
    unambiguous."""
    text = spelled(text)
    return SEARCH_UNITS.get(text) or SEARCH_FOLDED.get(text.lower())

_NUMBER = r"[+-]?(?:\d[\d,]*(?:\.\d+)?|\.\d+)(?:[eE][+-]?\d+)?"
_ABOUT = r"(?:(?:~|≈|approx\.?|approximately|about|ca\.?|nominal(?:ly)?)\s*)?"
_BELOW = {"≤": True, "<=": True, "<": False, "up to": True, "max": True, "max.": True, "maximum": True,
          "under": False, "below": False}
_ABOVE = {"≥": True, ">=": True, ">": False, "at least": True, "min": True, "min.": True, "minimum": True,
          "over": False, "above": False}
_SINGLE = re.compile(rf"^{_ABOUT}({_NUMBER})$", re.I)
_RANGE = re.compile(rf"^{_ABOUT}({_NUMBER})\s*(?:–|—|-|to)\s*({_NUMBER})$", re.I)
_BOUND = re.compile(rf"^({'|'.join(re.escape(k) for k in sorted({**_BELOW, **_ABOVE}, key=len, reverse=True))})"
                    rf"\s*({_NUMBER})$", re.I)

def _float(text):
    return float(text.replace(",", ""))

def value_range(value, unit_text=""):
    """A claim's value as a search compares it: (low, high, unit) as written, None for an open end ("≤ 39" has no
    low), or None when it isn't a number, a range or a bound. A unit written in the value ("75 kW") is taken when
    the claim's unit is empty."""
    text = unicodedata.normalize("NFKC", str(value)).replace("−", "-").strip()
    unit_text = str(unit_text or "").strip()
    if not unit_text:
        split = re.match(r"^(.*?\d)\s*([^\d\s,.].*)$", text)
        if split and search_unit(split.group(2)):
            text, unit_text = split.group(1).strip(), split.group(2)
    try:
        if m := _SINGLE.match(text):
            return _float(m.group(1)), _float(m.group(1)), unit_text
        if m := _RANGE.match(text):
            low, high = sorted((_float(m.group(1)), _float(m.group(2))))
            return low, high, unit_text
        if m := _BOUND.match(text):
            word, number = m.group(1).lower(), _float(m.group(2))
            return (None, number, unit_text) if word in _BELOW else (number, None, unit_text)
    except ValueError:
        return None
    return None

# a kind as a search's page and search.py name it: its index
KINDS = sorted({kind for kind, _ in SEARCH_UNITS.values()})
KIND = {kind: i for i, kind in enumerate(KINDS)}

def unit_of(text):
    """A unit as the search reads it: (its kind's index, its size in the kind's base), or None."""
    known = search_unit(text)
    return (KIND[known[0]], known[1]) if known else None

def claim_value(e):
    """A claim's value as a search compares it: [its kind's index or None, its unit's size, low, high] (an open end is
    None; without a known unit the size is 1 and the numbers are as written), or None when it isn't a number."""
    found = value_range(e.get("value", ""), e.get("unit", ""))
    if found is None:
        return None
    low, high, unit_text = found
    known = unit_of(unit_text) if unit_text else None
    return [known[0], known[1], low, high] if known else [None, 1, low, high]

def unit_tables():
    """The units the page's search reads ({spelling: [kind, size]}, and lowercased where that's unambiguous), and the
    kinds' names."""
    exact = {u: [KIND[k], size] for u, (k, size) in SEARCH_UNITS.items()}
    return exact, {u: [KIND[k], size] for u, (k, size) in SEARCH_FOLDED.items()}, KINDS
