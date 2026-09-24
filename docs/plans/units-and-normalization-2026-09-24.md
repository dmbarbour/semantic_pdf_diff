# Units, quantities and normalization

- **Status:** Planned
- **Depends on:** nothing strictly; claim fields from schema v2 in [sources-and-evidence-store](sources-and-evidence-store-2026-09-23.md) (basis, uncertainty)
- **Used by:** claim-level comparison and `check`; normalization in [n-way-comparison](n-way-comparison-2026-09-23.md); spreadsheet summaries in [multi-format-adapters](multi-format-adapters-2026-09-23.md); claim matching in [evaluation-benchmarks](evaluation-benchmarks-2026-09-23.md)

## Problem

Today's numeric check parses a plain number and looks up one of about 25 simple units (case-sensitive since 0.2.0). It abstains on everything else: ranges, inequalities, tolerances, compound units, currencies. That was a sound conservative start. But criteria-first comparison promises **normalized** comparisons (per kW installed, per m², per year), mechanical statistics over values from many sources, and unit-aware claim matching. None of that works on the current table.

The goal stays the same: **mechanical arithmetic where it is unambiguous, explicit abstention where it isn't, and never a silent guess.**

## Design

### 1. Quantities, not just numbers

Parse a claim's value and unit into a structured **quantity**:

- **point value:** `10`, `1.5e3`, `12 000`
- **interval:** `10–12 kW`, `10 to 12`, `between 10 and 12`
- **bound:** `≥ 10`, `at least 10`, `< 5`, `up to 12`
- **tolerance:** `10 ± 0.5`, `10 (+0.5/−0.2)`, or a separate uncertainty field (schema v2)
- **approximate:** flagged by extraction (e.g. chart readings), carried through as a relative tolerance

Ambiguous number formats abstain: `1,000` vs `1.000,5` (thousands vs decimal separators) are parsed only when unambiguous, and otherwise marked "unparsed" with the reason.

Comparison uses the structure: two quantities are *consistent* if their intervals (after tolerances) overlap, *different* if they don't, and a bound is compared as a bound. The existing vetoes still apply: approximate readings and basis or condition mismatches never produce a confident judgment.

### 2. Units

A layer of our own rules sits on top of a unit library:

- **Case-sensitive prefixes** (`mW` ≠ `MW`), as since 0.2.0.
- **Compound and per-units:** `kWh`, `m³/s`, `m3/s`, `W/m²`, `kg/m³`, `L/min`, `rpm`, `%`, `ppm`, `per year`, `/yr`.
- **An alias table we maintain** for spellings found in engineering documents (`cu m/s`, `lps`, `kW(e)`…).
- **Explicit ambiguity rules:** refuse arithmetic, with a stated reason, for
  - `ton` / `tons` (metric, short, long, or refrigeration) unless qualified
  - apparent vs real power (`kVA` is not `kW`)
  - gauge vs absolute pressure (`barg`, `psig` vs `bara`), unless both sides say the same
  - absolute temperatures vs temperature differences (`°C` vs `K` vs `ΔT`); offset units convert only as absolute temperatures
  - logarithmic units (`dB`, `dBm`): like-for-like comparison only, no arithmetic
  - bare `$` when the currency isn't stated (see money below)
- **Dimension check before conversion:** a conversion across dimensions is always an abstention, never an error that stops the run.

### 3. Money

- Amounts are compared **only in the same currency and the same price basis** (year, and nominal or real where stated).
- Scale prefixes are fine (`k$`, `M€`, "thousand dollars").
- Otherwise amounts are shown side by side, with no arithmetic. **No exchange-rate or inflation conversion:** that would be a judgment the sources didn't make.

### 4. Normalization for criteria

A criterion can ask for normalized values (e.g. cost per kW installed). Normalizing needs a second quantity, the **normalizer**, which must come from the **same source and the same context** as the value. It is found by per-source synthesis, recorded in the derivation ("cost 2.6 M$ ÷ installed capacity 350 kW, both from Team B's Rev C cost plan"), and checked for dimension. If the source doesn't state a normalizer, the outcome is **"cannot normalize"**, shown as such, never estimated.

### 5. Statistics

Mechanical statistics for criterion descriptions (range, median, spread, counts) run on values converted to one common unit. They exclude abstentions (listed separately), keep different bases in separate groups (measured vs projected), and report the unit explicitly.

### 6. Recording

Every numeric comparison records the parsed quantities, the conversions applied, and any abstention with its reason, so reports can show *why* two values were or weren't compared.

## Tests

- **Table-driven unit tests** for every rule above, including the case pitfalls fixed in 0.2.0.
- **A corpus of real unit strings** collected from sample extractions (once replay tables exist), to measure how many parse, convert or abstain, and why.
- **Synthetic documents** from [evaluation-benchmarks](evaluation-benchmarks-2026-09-23.md) with known quantities in mixed units.

## Milestones

1. Quantity model and parser: points, intervals, bounds, tolerances, approximate values; ambiguity abstentions.
2. Unit layer on `pint`: alias table, ambiguity rules, dimension checks; check its parsing against the collected unit strings, and extend our alias layer wherever it falls short.
3. Claim-level numeric check rebuilt on quantities; recording of conversions and abstentions.
4. Money handling.
5. Normalization with same-source normalizers and "cannot normalize" outcomes; statistics in common units.

## Decisions (2026-09-24)

- **Money:** same currency and price basis only; otherwise side by side, no arithmetic; no exchange-rate or inflation conversion.
- **Ambiguity:** abstain with a stated reason, never guess.
- **Unit library:** adopt [`pint`](https://github.com/hgrecco/pint) (BSD-licensed) behind our own alias and ambiguity layer, which stays ours.

## Open questions

None currently.
