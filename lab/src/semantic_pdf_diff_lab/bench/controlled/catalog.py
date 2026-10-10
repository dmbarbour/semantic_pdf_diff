"""The controlled corpus as generated: every project and seed, with knobs and revision pairs if asked. Above corpus.py
and revisions.py, which builds on the corpus's documents (code review 2026-10-08, E8).
"""
from .corpus import CHART_KNOBS, CHART_PROJECTS, PROJECTS, PROSE_KNOBS, PROSE_PROJECTS, TABLE_KNOBS, TABLE_PROJECTS

def corpus(seeds=(1,), knobs=False, revisions=False):
    """The clean corpus; with knobs, also each table project under every table knob, and each prose project under
    every prose knob (ids "<project>-<knob>"); with revisions, also each revision pair's generated side
    (revisions.py: the other side is a corpus document)."""
    out = [make(seed) for make in PROJECTS.values() for seed in seeds]
    if knobs:
        from .procedures import PROCEDURE_KNOBS, PROCEDURE_PROJECTS
        from .schematics import SCHEMATIC_KNOBS, SCHEMATIC_PROJECTS
        from .sheets import SHEET_KNOBS, SHEET_PROJECTS
        for makers, all_knobs in ((TABLE_PROJECTS, TABLE_KNOBS), (PROSE_PROJECTS, PROSE_KNOBS),
                                  (CHART_PROJECTS, CHART_KNOBS), (SCHEMATIC_PROJECTS, SCHEMATIC_KNOBS),
                                  (SHEET_PROJECTS, SHEET_KNOBS), (PROCEDURE_PROJECTS, PROCEDURE_KNOBS)):
            for make in makers.values():
                for seed in seeds:
                    for knob in all_knobs:
                        p = make(seed)
                        p.id, p.knob = f"{p.id}-{knob}", knob
                        out.append(p)
    if revisions:
        from .revisions import revised
        out += [project for seed in seeds for _, project in revised(seed)]
    return out
