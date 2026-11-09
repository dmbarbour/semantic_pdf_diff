# Knowing when two parts talk about the same thing: a methodology review

- **Status:** Reviewed (2026-11-09): Claude's account, corrected where Fable's second opinion found it wrong, then [Fable's second opinion](#fables-second-opinion), for the owner's review.
- **The owner, 2026-11-09:** "consider how to improve `link_gaps`. We might need a review of our methodology and how we're integrating context (not just properties of a thing, but also of how it's used), with second opinions from Fable. Knowing when two sections or documents are talking about the same thing, with softer confidence levels, is the foundation of most of our analysis and comparisons. We'll start filling tables when we have stronger confidence in our relations."
- **Builds on:** [tentative matches](../plans/tentative-matches-2026-11-07.md) (links, their levels and measurement), [claim context](../plans/claim-context-2026-10-14.md) (subject, scope, frame, provenance, stance), [single-document analysis](../plans/single-document-analysis-2026-10-28.md) (subjects, dossiers, gaps), [indexes and glossaries](../plans/indexes-and-glossaries-2026-10-29.md) (subjects, kinds, other names), [0038](../decisions/0038-revisions-aligned-then-differences-explained.md) (revisions aligned items-first).

## Where "the same thing" is decided today

Each layer decides on its own evidence, mostly by names and the properties' names.

| Layer | Decided by | Its evidence | Confidence |
|---|---|---|---|
| A claim's subject | the reader | the entity as read; context records it references (subject, scope, frame, stance) | none |
| Claims into subjects, one source | code (`align.Side`, `indexes.renamed`) | a tag, else the entity's words; positional joins by shared values; glossary terms and the model's other names (`search_names`) | none: one or apart |
| Subjects into kinds | code (`indexes.kinds`), the model where `confirm_kinds` | a tag's letters, a name without its number | none |
| Subjects across revisions | alignment (`align.Alignment`) | values in common (rarity weighted), names, attributes; a floor and a margin | in-between states kept as groupings, now as links |
| Subjects across proposals | `indexes.matched`, then `crossmatch.py`, then `links.py` | keyed alike, other names; the model's match; links by names (words, spelling, meaning), properties in common (distinct from siblings'), the judge's verdicts, the model's read against a decoy | firm, plausible, possible |
| Properties across sources | `indexes.joined` | the same name (exact, case folded), the findings pairing their claims, other names (`aliases`, `kin`): nothing fuzzy | none: one or apart |
| Claims across sources | retrieval (TF-IDF), the reranker, the judge; alignment between revisions | the claims' words and values; context records shown where `judge_context` (measured worse), the second pass's notes where `judge_notes` (little change) | the judge's relation and confidence |
| Sections and documents across sources | nothing directly | topics (shared words); situating's "abouts" are per document | none |
| A subject's claims together | the second pass (`dossiers.py`) | its dossier: claims, quotes, records, abouts, siblings | relations as entries |

## What the measurements say

- **Revisions match well** (milestone 1's scorer): 482 of 483 scorable PDF matches right. Values carry identity between revisions.
- **Proposals don't, by names alone.** On the controlled proposals pairs, the model's other names took most renames; what's left is hard:
  - *Siblings:* P-101A, P-101B and P-101C against LL-1 to LL-3 share every property; nothing we read tells which corresponds (the keys say by row order).
  - *Names shared by unrelated items* in real documents (the turbine pair's dozens of "turbine" and "rotor" items): under the fitted weights, names alike made 9 plausible links, most wrong (NREL's baseline and IEA's reference turbines among them, right).
  - The model's other names took most of Pine Ridge's renames; of Cedar Falls', its PDF matched 5 of 10 roles.
- **`link_gaps` fails on properties, not items:** of the 136 gaps "if one item" on the controlled proposals pairs (seeds 1 to 5), 17 were right and 119 not: 116 in `comparison._gaps`' bucket "both give it" (properties both designs give under other names, "design flow (average day)" against "average day flow"), 3 another fact or unbound. The item was matched; its properties weren't.
- **Context shown to the judge didn't help:** `judge_context` was no better than its null arm, both worse than without; `judge_notes` within noise. That's context shown to a verdict-taker; context used to form or weigh candidates hasn't been tried.
- **Our keys are synthetic templates.** Held-out seeds share their templates; the one real check (the turbine pair, by eye) broke the weights. The real drawings pair gave non-match rates.

## What isn't used: how a thing is used

The owner's point: identity rests on more than a thing's properties. What we read but don't weigh:

- **Where it is:** its section's heading path and "about" (a pump in "Raw water intake" and one in "Filter backwash"), the figure or sheet it's drawn on.
- **What it does:** role words in its name or claims ("duty", "standby", "intake", "backwash", "primary disinfection"); the process stage it serves.
- **What it's connected to:** part-of and serves relations (the tower of the turbine; the pump feeding the clarifier). Relational facts exist in the keys; the reader is seldom asked for them.
- **When it applies:** its operating states and conditions (rated point, phase 2, congested link), already in claims' conditions and scope.
- **What's said about it together:** the second pass's dossier per subject (relations, inferences), never compared across sources.

## Directions, for discussion

1. **Properties matched across sources as their own layer, with levels,** as items now are: names (words, spelling, meaning), units and magnitudes that fit, value kinds, the judge's pairing of their claims, the glossary. It's what `link_gaps` needs most (116 of its 136 gaps), and the gaps from firm matches too.
2. **Sections matched across documents,** softly: headings, abouts, the subjects in them. Two items in corresponding sections (each design's "Disinfection") are likelier counterparts; items in unrelated sections less so.
3. **A subject's use as evidence:** a short description of each subject from its section, role words, relations and conditions (code, then the model where code can't), compared across candidates by words and meaning. Siblings may separate by role (duty and standby) or by where they're used.
4. **Correspondence propagated across layers:** documents, sections, subjects, properties, values reinforcing one another (matched wholes make their parts likelier; matched parts make their wholes likelier), so a level is earned from the structure, not from names alone.
5. **Measurement closer to use:**
   - controlled templates that vary use (the same item in two roles; two items sharing a name in different sections);
   - a labelled real sample, by model panels as raters ([0018](../decisions/0018-several-raters-none-ground-truth.md));
   - non-match rates from real pairs.
6. **`link_gaps`, meanwhile:** gaps only for properties not matched to any of the other's (direction 1); looked for where they'd be (a look's "given" settles a renamed property); in corresponding sections only (direction 2).

## Fable's second opinion

Fable (claude-fable-5-1), 2026-11-09, read-only, at the owner's request ("with second opinions from Fable"); summarized, its words where quoted.

- **Where the draft fell short:** it gave no mechanical cause for the false gaps, and "use" is an unfilled slot, not a new structure. `Claim.role` and `Claim.context` exist in the schema, asked by no prompt. `dossiers.PROMPT` asks for relations among a subject's claims, never its role or place. `crossmatch.described` shows names and property names only, though `dossiers.dossiers` already gathers heading paths and abouts per subject. And the synthetic templates share their section titles verbatim (only Harbor renames them), so section correspondence would score perfectly on today's keys "for the wrong reason".
- **The core problem:** "across designs, identity is a hypothesis about role in a structure. Names are the weakest proxy."
  - **A use profile per subject,** by code from what's stored: its claims' sections (heading path, about, keywords), figures' roles and abouts, its kind, role words in names and attributes (duty, standby, intake), conditions and scope words, and relational claims where read. Kept as a commentary entry.
  - **Sections matched across sources** as their own layer: alignment-style assignment with a floor and a margin over heading words, abouts' keywords, and the firm-matched subjects in both. A link's band `place`: correspond, don't, unknown.
  - **In the rubric:** a third family, place/use, beside names and a model's readings; new bands (`place`, `neighbour`) so `linkfit` can fit them.
  - **Joint inference, kept small:** one or two passes, firm matches to section correspondence to a link band, and links to property joins to gaps. Not similarity flooding or a factor graph: the graphs are small, and "a level must stay explainable in a 'why' line".
  - **The model:** keep the discriminating read; "enrich what it's shown (profiles), not what it's asked".
- **`link_gaps`, ranked:**
  1. **Join the pair's properties before counting** (code, no requests). The cause of the false gaps: a firm match's properties are joined over its merged claims (`indexes.joined`), so renamed properties collapse before gaps are counted. A link's two subjects stay apart, and `if_one_item` compares exact case-folded names. Worse, `links._properties` keys a property by its set of words while `if_one_item` uses the case-folded name, so a property counted as a link's shared evidence can still be emitted as its gap. Join over the pair's word-set keys, other names, and the findings pairing the two subjects' claims, with unit kind as a guard. Measured by the buckets of `comparison._gaps`: "both give it" should collapse while "right" holds.
  2. **Property links with levels** (the draft's direction 1): units, magnitudes within ten times, the judge's pairing, the glossary.
  3. **Look for link gaps where they'd be** (`dossiers.looks`): a "given" settles a renamed property, and doubles as the plan's unbuilt look as a link's test. The owner's call: it reverses "links and topics for now".
  4. **Gate by place:** a link gap only where the two sections correspond. Its knob first: section titles renamed and reordered in proposals.
  5. **Use in the match and the read:** heading path and about shown to `crossmatch`. Its knobs first: a role column among siblings (duty, standby); a decoy sharing a name in another section; a proposals pair from the schematics templates, where connections carry identity (`comparison._matching` ignores relational facts today).
- **Methodology risks:**
  - *The template trap, precisely:* held-out seeds vary values, not vocabulary, layout or structure. "Build the knobs before the lever, as `link_tests` did."
  - *Harbor:* keep it sealed until a candidate beats the rubric on validation; add one sealed template of another genre (schedules, drawings) rather than more seeds.
  - *Real documents without sharing them:*
    - non-match rates from real pairs (done for the drawings; extend);
    - EM on unlabelled pairs, which needs some 50 to 100 labelled pairs for its match rates;
    - a local `links review` command: a sample of links by level, marked right, wrong or unsure on the owner's machine, only counts leaving it;
    - a model panel on public pairs as a second rater, disagreements shown, not averaged.
  - *Not fitting our own keys:* rules written before looking; never decoys tuned to a fitted feature; fit on one corpus, promote on another; rotate templates.
- **Its sequence:**
  1. Join properties across a link before counting gaps, replayed on the recorded reports.
  2. The knobs: section titles renamed and reordered; a role column among siblings; a same-name decoy in another section; a second sealed template.
  3. Section correspondence by code, a `place` band and family, heading path and about shown to the match and the read, fitted, its held-out rule written first.
  4. Looks for link gaps, and the look as a link's test.
  5. A schematics proposals pair; a `neighbour` band.
  6. `links review`; EM on real pairs; a model panel on the turbine pair.

## Where Claude and Fable agree

- Properties, not items, are why `link_gaps` fails; joining a link's properties first is the cheapest, surest step.
- Use enters as evidence through where a subject sits (sections) and what it's said to do, compared by code first; the model is shown it, not asked for a number.
- Knobs before levers: the controlled templates must vary what use-based evidence reads (section titles, roles, same-named items elsewhere), or it scores perfectly for the wrong reason.

## Questions for the owner

- **A. Looks for link gaps,** reversing "links and topics for now" for gaps only?
- **B. A third family, place/use, in the rubric** (and the two-family rule required of any numbers)?
- **C. Harbor:** spent only on a candidate that beats the rubric, a second sealed template of another genre made first?
- **D. A local `links review` mode** as the real-document rater (only counts leave your machine), and a model panel on public pairs as a second rater toward promotion?
