"""Controlled documents: PDFs for fictional projects, generated from a fact sheet and a seed, with every fact's
form and place known, so extraction is scored exactly (docs/plans/controlled-documents-2026-10-01.md).

    corpus      projects, knobs, rendering, keys
    score       claims scored against a key
    relations   relations between named things, and how claims stating them are scored
    schematics  system drawings: parts, links and enclosures, laid out
    procedures  procedures drawn as message sequence charts, in PDF and as WMF for Word
    sheets      drawing sheets: a floor plan with dimensions, tags and a door schedule
    revisions   revision pairs: a corpus document and a revision of it with known changes
    comparison  a comparison in revisions mode scored against the key's changes

This façade keeps `controlled.X` working for corpus and score (architecture clean-up, milestone 8).
"""
from .corpus import (  # noqa: F401
    CHART_KNOBS, CHART_PROJECTS, CSS, Chart, Column, Draw,
    Fact, LCC_PROSE, PAGE_BREAK, PROJECTS, PROSE_KNOBS, PROSE_PROJECTS,
    Project, RUNNING_HEADER, SERIES_FILL, Schedule, TABLE_KNOBS, TABLE_PROJECTS,
    _esc, _last, _phrase, _schedule_facts, charts, convention_center,
    corpus, draw_chart, draw_charts, draw_schematics, end_use_study, energy_study,
    equipment_schedules, html, key, locate, metered_study, parse_number, printed_value,
    raster, render, roller_coaster, scanned, schedule_html, track_schedules,
    water_treatment, write)
from .score import (  # noqa: F401
    BOUNDS, DATE, FIT_WEIGHTS, INEXACT_STEPS, NUMBER, NUMERIC_VALUE,
    RANGE, REFERENCE, SAME, SIGNS, STOP, UNIT_AFTER,
    bounds, claimed_unit, classify, distinctive, fit, holds,
    holds_as, parse_number, printed_value, ranges, rarity, same_number,
    score, tokens, unit_kind, vocabulary)
