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
- **Figure "abouts" only for labelled figures.** On the drawing set `dc_cd.pdf`, 688 of 690 detected regions are uncaptioned drawing fragments; a request for each would cost more than the sections themselves.
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

## Next: one proposal, then milestone 5

### Drawing sheets as figures, labelled from title blocks

Sheet references on drawing sets mostly stay unresolved (7% resolve on `dc_cd.pdf`). The sheet number lives in the title block, not in a caption. The proposal:

- On diagram-heavy pages, read the sheet number from the title block mechanically: the text near the page's bottom-right corner that matches a sheet pattern such as `A-101` or `M2.01`.
- Treat the whole sheet as one labelled figure.
- References such as "see M-101" then resolve, and each sheet gets a figure "about".

It's small, and the quality check already measures it. **Recommended before milestone 5.**

### Milestone 5: epistemic status

Prompts ask for basis, uncertainty, context and role; add skeptical instructions and the basis veto in comparison. This is a deliberate extraction prompt-version change, which invalidates cached extraction for existing stores; nobody uses the tool yet, so that's free.

### Worth considering: a real-model check

The record/replay plan (a weak local VLM, and Claude as a reference) would let "abouts" be judged on real output before more prompt work stacks up on them.
