"""Values as printed: numbers, dates, lengths in feet and inches, and units with their kinds (code review 2026-10-01:
number parsing written five ways, in five modules).

Two unit tables stay apart on purpose. The product's (UNITS: SI, deliberately small) enters comparison prompts
through compare.numeric_check, so a change to it changes requests and every recorded comparison answer would miss.
The scorer's (UNIT_KINDS) covers the controlled corpus's units and their spellings. Merging them is a decision for a
round, not a clean-up. The product's text folding (extract.FOLD, readings.QUOTES) stays with its users for the same
reason: it decides which quotes verify, which decides which tasks are refined.
"""
import re
import unicodedata

# --- numbers and dates

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

DATE = re.compile(r"^\s*(\d{4})-(\d{2})-(\d{2})\s*$")

def same_number(a, b):
    return a is not None and b is not None and abs(a - b) <= 1e-9 * max(1.0, abs(a), abs(b))

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
    text = str(value).strip().replace("′", "'").replace("″", '"').replace("’", "'").replace("”", '"')
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
