# Review: triage without the model (scheduling milestone 3)

- **Date:** 2026-09-24
- **Plan:** [scheduling-and-triage](../plans/scheduling-and-triage-2026-09-23.md), milestone 3, with section ordering deferred to milestone 6 (decided 2026-09-24)
- **Tests:** 123 passing on Python 3.12; 119 passing and 4 skipped on Python 3.10 with minimum dependency versions

## Delivered

- **Per-section signals:** numbers, units, requirement words (`shall`, `must`, …), tables, images, vector drawings and characters, summed over each section's pages and stored with the sections. Nothing uses them yet: ordering and model triage will. Vector drawings are counted with PyMuPDF's `get_cdrawings`, about 0.05 s per drawing sheet.
- **Repeated table rows follow their first occurrence.**
  - A row counts as repeated if its header and cells are exactly identical, in the same table position, and seen for at least the third time in the same content.
  - It then reuses the first occurrence's claims (as occurrences on its own page, in its own section), with a coverage row saying which task it is identical to.
  - If the first occurrence failed, followers are extracted normally.
  - Under concurrency, a follower queued before its first occurrence's answer arrives waits for it.
  - `dedupe_repeated` turns it off.

## Evidence, and the amendment it forced

The approved rule covered text blocks too, isolating repeated ones into their own tasks. Measured with a call-counting stub (text and tables, no vision):

| Document | No de-duplication | Table rows only | Table rows and text |
|---|---|---|---|
| `dc_cd.pdf` (143 drawing sheets) | 5,537 calls | **3,053 (−45%)** | 3,768 (−32%) |
| `2013_rules.pdf` (68 pages of text) | 533 | 533 (±0) | 609 (+14%) |
| `NREL-5MW` report (75 pages) | 376 | not measured | 399 (+6%) |

**Text isolation always added calls.** Text blocks are packed into requests of up to 1,800 bytes, so a repeated header rides along in a request that's made anyway and costs no extra call. Isolating it adds a call on its first page and can split the page's remaining text into more groups. Table rows are one call each, so following them saves real calls: 45% on the drawing set, where title blocks and legends repeat on every sheet.

**So de-duplication applies to table rows only.** Text grouping is unchanged from before, which also removes the footnote risk entirely: no text is ever skipped. The plan's decision is amended with this evidence.

## Tests

- **Text:** a synthetic 4-page PDF with a repeated header, per-page footnotes and page numbers. The text is sent on every page, and no text task is ever a follower.
- **Title-block rows:**
  - an identical row: sent on pages 1 and 2, followed on pages 3 and 4
  - a row whose sheet number changes: always sent
  - the identical row in another position: sent
  - with the setting off, everything is sent
  - followed rows carry every sighting as occurrences
- **Concurrency:** the same extraction through the real client against a random-latency stub gives identical evidence and coverage with 1 and 6 workers, with followers present.

## Next: model triage per section (milestone 4)

One request per section returns its type, estimated density, keywords and "about" statement. The deployment's 262,144-token context means whole sections fit. This is also the first input to retrieval-recall (embeddings of "about" statements) and to criteria recommendation.

**Before building it, a question about when it runs.** The triage request needs a whole section's text, and nothing in extraction depends on its result, since ordering is deferred. It could run inside extraction (one more request per section, fed alongside pages), or as a separate stage after extraction. A separate stage is simpler and lets `--plan` count it separately. I'll build it as a separate stage unless you prefer otherwise.
