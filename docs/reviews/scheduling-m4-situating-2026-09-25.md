# Review: situating stage (scheduling milestone 4) and next steps

- **Date:** 2026-09-25
- **Plan:** [scheduling-and-triage](../plans/scheduling-and-triage-2026-09-23.md), milestone 4
- **Commits:** `34ac923` (figures, captions and citing prose), `0988581` (figure and section requests), and the quality checks and report section (this review's commit)
- **Tests:** 135 passing on Python 3.10; 135 passing with 4 skipped on the minimum-version environment

## Delivered

- **Mechanical figures and references** (`situate.py`):
  - figures are image blocks and dense vector-drawing clusters, paired with captions ("Figure 3:", "Table 2", "Sheet M-101")
  - citing sentences are found by regex and linked to the figure they cite; claims inside a figure's region are attached to it
  - list-of-figures entries are skipped
- **Figure requests:**
  - one per *labelled* figure: caption, citing sentences, its claims, and a crop when it has a region
  - returns "about", role and keywords
  - uncaptioned regions don't get a request; their claims feed their section's request instead
- **Section requests:**
  - one per section, after all figures: heading path, text (trimmed to the context budget), claims, and its figures' "abouts"
  - diagram-heavy sections also get up to 3 page overviews
  - returns type, density, keywords and "about"
- **Storage (schema v7):**
  - a `situation` row per content holds its figures, unresolved references and request issues
  - sections gain `about`, `section_type`, `density` and `keywords`
  - complete results are reused; failed requests are retried on the next run
- **Binding:**
  - the new `triage` role is bound to the store
  - a changed triage interpreter needs `--reset`, which clears only situating results and cached triage responses
  - an extraction reset also clears situating, since situating reads the evidence
  - both roles are checked before either is cleared, so a rejected run changes nothing
- **Quality checks:**
  - they run on every run, loaded results included, and are reported but never applied
  - checks: share of references that resolve, labelled figures never cited, values in "abouts", "about" terms missing from their material, lengths, and sections with claims but no "about"
- **Report:** a "Situating" section per content with sections, figures, their flags, unresolved references and failed requests.
- **CLI:**
  - `--no-situate` (setting `situate`) skips the stage
  - `--plan` counts situating tasks
  - `evidence.json` and `report.json` carry `sections` and `situation`

## Drift from the plan (with evidence)

- **One row per content, not a figure table.** Figures are always read and replaced together, and the reference graph lives with them.
- ~~**Figure "abouts" only for labelled figures.**~~ Reversed the same day; see *Revision* below.
- **The diagram-heavy rule uses the ratio of vector paths to text characters.** The first rule (under 800 characters per page) sent overviews for only 2 of 143 drawing sheets, because sheets carry dimensions and notes. Paths per character separate the samples cleanly:

  | Document | Median paths per character |
  |---|---|
  | `dc_cd.pdf`, `calg_cd.pdf` (drawing sets) | 2.3–4.3 |
  | NREL report, 2013 rules | about 0.01 |

  The rule is now 500 or more paths per page and at least one path per two characters, or images with almost no text (scans). Result: 131 of 143 sheets get overviews; the reports are unchanged.
- **Human-review sample of "abouts" moves to milestone 8,** where reviewer feedback is captured.

## Evidence (stub model, real documents)

| Document | Pages | Requests | Images | Largest request | References resolved | Mechanical time |
|---|---|---|---|---|---|---|
| NREL 5 MW | 75 | 52 | 23 | 40 KB | 63 of 71 (89%) | 1.6 s |
| 2013 rules | 68 | 58 | 20 | 25 KB | 22 of 22 (100%) | 2.0 s |
| `dc_cd.pdf` | 143 | 145 | 133 | 13 KB | 4 of 58 (7%) | 42 s |

- **Cost:** `--plan` on the NREL and IEA 15 MW pair counts 122 situating requests out of 1,265, about 10%.
- **Time:** on drawing sets, the mechanical time is mostly drawing-cluster detection over thousands of paths per sheet.
- **Nothing measures "about" quality yet.** All of this ran against stub models; the checks can flag values and ungrounded terms, not correctness.

## Revision after feedback (2026-09-25)

The owner's feedback: unlabelled figures can't be excluded. Location in the document situates a figure, citing sentences belong to paragraphs that situate them, and some labels must be read from the figures themselves. The first version's context was thin. Changes:

- **Every figure gets a request.** The fragment problem that motivated skipping unlabelled ones is solved at the source instead: a drawing sheet is now one figure.
- **Drawing sheets:**
  - a page with a title block, or with at least 500 paths and one path per two text characters, becomes one figure, unless it has captions
  - it is labelled from the title block: the largest sheet-number-like text at twice the median font size, and the mid-sized text beside it as the title
  - fake-bold duplicate spans are dropped
- **Context per figure:**
  - location: page N of M, position on the page, section path
  - label with its source (caption, title block or model), caption and title
  - text before and after it on the page, up to 1,500 characters each; for a sheet, its own text up to 3,000
  - whole citing paragraphs with their page and section
  - its claims and an image
  - material is cut in steps until it fits the context budget, and trimming is reported
- **Labels from figures:**
  - the model also returns a label and title printed in the figure
  - new labels resolve outstanding references
  - figures that gain citations get one more request, with the citing paragraphs
- **Reference fixes found on the way:**
  - list-of-figures entries no longer count as citations
  - a paragraph citing the same figure twice counts once
  - "Figure 1 shows…" at the start of a paragraph is no longer a caption
  - labels match regardless of hyphens (`M201` cites `M-201`)
  - a panel (`Figure 2-4A`) cites its figure when it has no figure of its own
- **Sections:** overviews now go only to scanned pages; sheets are shown by their own figure requests.

### Evidence after the revision (stub model)

| Document | Figures | Labelled (source) | References resolved | Situating requests | Before |
|---|---|---|---|---|---|
| NREL 5 MW | 62 | 28 (captions) | 35 of 39 (90%) | 86 | 52 |
| IEA 15 MW | 62 | 52 (captions) | 92 of 92 (100%) | 80 | 70 |
| 2013 rules | 82 | 18 (captions) | 22 of 22 (100%) | 120 | 58 |
| `dc_cd.pdf` | 147 (143 sheets) | 143 (141 title blocks, 2 captions) | 57 of 60 (95%) | 290 | 145 |
| `calg_cd.pdf` | 92 (92 sheets) | 92 (title blocks) | 0 of 8 | 184 | — |

- **Earlier counts were inflated.** NREL's earlier "63 resolved" counted list-of-figures entries and repeats.
- **`calg_cd.pdf`'s unresolved references cite other documents** (building-code tables such as "Table 26.9-1"). Telling external references apart is future work.
- **Speed:** skipping region detection on sheets cut `dc_cd.pdf`'s mechanical time from 42 s to 31 s.
- **Possible saving, not taken:** on drawing sets each sheet is also its own section, so figure and section requests pair up. A one-sheet section could reuse its sheet's "about", saving about half the requests there, at the cost of a section request that also judges type and density. Worth measuring once real answers exist.

## Next

### Real-model check (when the gemma-4 endpoint is ready)

"Abouts" need judging on real output before more prompt work builds on them. The record/replay plan's first rounds (Claude as a reference, gemma-4) come next, starting with situating on a small slice of the samples.

### Milestone 5: epistemic status

Prompts ask for basis, uncertainty, context and role; add skeptical instructions and the basis veto in comparison. This is a deliberate extraction prompt-version change, which invalidates cached extraction for existing stores; nobody uses the tool yet, so that's free.

### Supporting-evidence webs

Recorded as a tentative plan in the index. Situating's figure–prose links and milestone 7's claim quality signals are its first threads. Webs feed confidence (corroboration) and derivations (values computed from others, which need units and normalization), so the plan fits after milestone 7 and units, and before criteria-first comparison uses confidence.
