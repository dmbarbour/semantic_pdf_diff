"""Proposal pairs (docs/plans/tentative-matches-2026-11-07.md, milestone 5): a corpus document and another design of
the same kind of thing, its items named its own way, so a comparison in proposals mode is scored by what each item
is, not what it's called.

A proposal is its corpus project drawn from another seed (its values its own), its items renamed (a facts' ids kept:
an id is the item's role in the template, so the two designs' "P-101A.capacity" and "IP-1"'s capacity are one role),
some roles kept alike (the filters), one role gone (the UV option), a decoy (a backwash pump: a pump, not an intake
pump), a property dropped from a role both keep (the clarifiers' surface loading rate) and one added (the flash
mixer's volume): gaps another source fills.

Scored by comparison.score_proposals: matching by role (each subject's claims bound to the keys' facts, a fact's role
its id's), and the gaps another source fills.
"""
import re
from dataclasses import dataclass, replace

from .corpus import PROJECTS
from .model import Draw, Fact
from .revisions import add_sentence

@dataclass
class Pair:
    id: str          # the pair
    earlier: str     # the documents' ids: the corpus's design first, the other second (no order between proposals)
    later: str

# Pine Ridge's names for Harrow Creek's items (the printed words, then each role's entity and aliases)
WORDS = (("Harrow Creek", "Pine Ridge"), ("The rapid mix basin provides", "The flash mixer provides"),
         ("sedimentation basins, each", "clarifiers, each"), ("Raw water pumps", "Intake pumps"),
         ("P-101A", "IP-1"), ("P-101B", "IP-2"), ("P-101C", "IP-3"),
         ("Alum is dosed at", "Ferric sulfate is dosed at"),
         ("Two options were compared for primary disinfection.", "One option was considered for primary "
                                                                   "disinfection."),
         ("Option B: chlorine contact", "Chlorine contact tank"))
ITEMS = {"Harrow Creek Water Treatment Plant": ("Pine Ridge Water Treatment Plant", ("Pine Ridge WTP", "the plant")),
         "Rapid mix basin": ("Flash mixer", ("flash mixer", "mixer")),
         "Sedimentation basins": ("Clarifiers", ("clarifier", "clarifiers")),
         "Raw water pump P-101A": ("Intake pump IP-1", ("IP-1", "intake pump IP-1")),
         "Raw water pump P-101B": ("Intake pump IP-2", ("IP-2", "intake pump IP-2")),
         "Raw water pump P-101C": ("Intake pump IP-3", ("IP-3", "intake pump IP-3")),
         "Alum feed": ("Ferric sulfate feed", ("ferric sulfate", "coagulant feed")),
         "Option B, chlorine contact basin": ("Chlorine contact tank", ("chlorine contact tank", "contact tank"))}
LOADING = re.compile(r"; the surface loading rate is [\d.,]+ gpm/ft² at design flow")

def _edit(project, edit):
    """Every printed string edited: paragraphs, tables' captions, headers and cells."""
    for _, blocks in project.sections:
        for i, block in enumerate(blocks):
            if block[0] == "p":
                blocks[i] = ("p", edit(block[1]))
            elif block[0] == "table":
                blocks[i] = (block[0], edit(block[1]), [edit(c) for c in block[2]],
                             [[edit(c) for c in row] for row in block[3]], *block[4:])

def _drop_column(project, caption_word, column):
    """A table's column dropped (the table whose caption holds caption_word)."""
    for _, blocks in project.sections:
        for i, block in enumerate(blocks):
            if block[0] == "table" and caption_word in block[1]:
                blocks[i] = (block[0], block[1], block[2][:column] + block[2][column + 1:],
                             [row[:column] + row[column + 1:] for row in block[3]], *block[4:])
                return
    raise ValueError(f"{project.id}: no table of {caption_word}")

def pine_ridge(seed):
    """Pine Ridge's design basis: Harrow Creek's template drawn from another seed, its items named its own way."""
    p = PROJECTS["wtp"](seed + 1)
    p.id, p.title = f"wtp-s{seed}-proposal", "Pine Ridge Water Treatment Plant"
    p.edits = []
    # the UV option isn't one of Pine Ridge's (a role gone); the clarifiers' loading rate not given (a gap)
    _drop_column(p, "Disinfection options", 1)
    gone = {f.id for f in p.facts if f.id.startswith("optA.")} | {"sed.loading"}

    def edit(text):
        for old, new in WORDS:
            text = text.replace(old, new)
        return LOADING.sub("", text)
    _edit(p, edit)
    p.facts[:] = [f if f.entity not in ITEMS else replace(f, entity=ITEMS[f.entity][0], aliases=ITEMS[f.entity][1])
                  for f in p.facts if f.id not in gone]
    p.edits.append({"kind": "removed", "facts": sorted(gone)})
    d = Draw(f"{p.id}-proposal")
    d.used |= {f.value for f in p.facts}
    mixer = p.fact("mix.g")
    # the flash mixer's volume, which Harrow Creek doesn't give (a gap); a backwash pump (a decoy for the intake pumps)
    add_sentence(p, "mix.g", "Its volume is {v} gal.",
                 Fact("mix.volume", mixer.entity, mixer.aliases, "volume", ("basin volume",), d.number(8000, 20000),
                      "gal"))
    add_sentence(p, "filters.rate", "A backwash pump delivers {v} gpm to the filters.",
                 Fact("bw.capacity", "Backwash pump", ("backwash pump", "the backwash pump"), "capacity",
                      ("flow", "rated flow"), d.number(3000, 6000), "gpm"))
    return p

# (the pair's corpus project maker and seed's id pattern, the other design's maker, the pair's name)
PAIRS = (("wtp-s{seed}", pine_ridge, "proposals"),)

def pairs(seed=1):
    """Each pair's documents, by id (nothing generated)."""
    return [Pair(f"{base.format(seed=seed)}-{name}", base.format(seed=seed), f"wtp-s{seed}-proposal")
            for base, _, name in PAIRS]

def check(project):
    """A proposal's key is honest: its facts all placed (render raises otherwise), each value naming one fact."""
    from .corpus import render
    render(project)
    values = [f.value for f in project.facts if not f.relation]
    if len(values) != len(set(values)):
        raise ValueError(f"{project.id}: a value names two facts")

def proposed(seed=1):
    """[(Pair, the generated design)], checked."""
    out = []
    for (base, make, _), pair in zip(PAIRS, pairs(seed)):
        project = make(seed)
        check(project)
        out.append((pair, project))
    return out
