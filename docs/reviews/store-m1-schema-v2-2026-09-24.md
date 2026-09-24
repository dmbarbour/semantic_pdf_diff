# Review: store milestone 1 (schema v2) and next steps

- **Date:** 2026-09-24
- **Plan:** [sources-and-evidence-store](../plans/sources-and-evidence-store-2026-09-23.md), milestone 1
- **Commit:** `3560327`
- **Tests:** 50 passing on Python 3.12 (current dependencies); 46 passing and 4 skipped on Python 3.10 with minimum dependency versions

## Delivered

- **Model:** `Source`, `FileRef`, `PdfLocator` (the only locator shape so far, discriminated by `format`), `DerivationStep`, `Interpreter`. `Evidence` replaces the A/B `document`, `page`, `bbox` and `source` fields with `content`, `locator` and `derivation`.
- **Content identity** (`provenance.py`): `sha256:<hex><ext>` with the extension alias table; files without an extension are refused with an explanation.
- **Evidence IDs** derive from content, locator and claim, so they survive renames (tested).
- **Claim context fields** (`topic`, `basis`, `uncertainty`, `context`, `role`) exist in the schema with "not stated" defaults. Prompts don't ask for them yet; that belongs to the epistemic-status milestone in scheduling-and-triage.
- **Interpreters:** extraction and comparison descriptions (model, prompt hash, output-affecting settings, library versions) are written to `evidence.json` and `report.json`. Not yet enforced; binding comes with the store.
- **CLI, report and demo** work on sources and files: evidence cards show `source / path · page`, and coverage rows name files. Two positional PDFs remain the interface.

## Drift from the plan, with justification

| Drift | Justification |
|---|---|
| **Shared evidence is listed separately and never compared.** This is a sliver of milestone 5 (content-difference comparison). | Content-based IDs make the same PDF on both sides produce *identical* evidence. Without this, the comparison would pair every claim with itself (a test with the same PDF twice showed it). Listing shared evidence apart from findings also avoids flooding the report. |
| `evidence.json` replaces `evidence-A.json` / `evidence-B.json`. | Per-label files don't fit sources that share content. The store will replace both anyway. |
| The locator's pass field is named `region`, not `pass`. | `pass` is a Python keyword. |
| An unrecognized `basis` from the model becomes `unknown` instead of dropping the claim. | Consistent with the lenient salvage rule: a bad optional field shouldn't discard a claim. |
| `context_tokens` counts as an output-affecting setting. | It decides which requests are refused as too large, so it changes what gets extracted. |
| Rendered crops are named by a content-hash prefix instead of the A/B label. | Content-addressed like everything else; the same content reuses the same crops. |

## Next step: milestone 2 (SQLite store). Two findings to discuss before starting

### 1. Resume doesn't need a persistent task queue yet

The plan pairs the store with "a task queue with per-task transactions" for stopping and resuming. But extraction is deterministic given the model's responses, and the response cache already makes a rerun replay every answered request without calling the model. **Moving the response cache into SQLite gives resume almost for free**: rerun, and the pipeline fast-forwards through cached answers to where it stopped.

A persistent task queue earns its keep for *scheduling*: concurrency, fair share across sections and sources, priorities, and progress for preliminary reports. That's the scheduling plan's first two milestones, and doing it there avoids designing the queue twice.

**Proposal:** milestone 2 builds the store, moves the response cache into it, writes evidence and coverage per task in their own transactions, and implements resume by cache replay. The persistent queue moves to scheduling-and-triage milestone 2, where extraction gets restructured into discrete tasks anyway.

### 2. Cache keys: design them once, for both the store and record/replay

Today's cache keys hash the full request bytes (prompt text, image bytes, settings). The record/replay plan needs **semantic keys** (task kind, prompt version, content ID, locator, input-text hash, crop specification), because byte keys break on incidental changes like PyMuPDF rendering differences.

The store's interpreter binding makes semantic keys safe inside a store. Everything that could change a response for the same semantic key (model, prompts, output-affecting settings, library versions) is already part of the bound interpreter, and a change there is rejected or triggers a reset.

**Proposal:** the store's response cache uses semantic keys from the start. That covers the first milestone of the record/replay plan, and a replay fixture becomes literally a copy of a store's cache table. The risk: a semantic key that forgets some input would silently serve a wrong answer. Mitigation: tests that change each input and assert a miss, and an optional stored byte hash per entry, checked in a debug mode.

### Smaller decisions (no discussion needed unless you object)

- The CLI's `--out` folder *becomes* the store folder (`store.sqlite`, `assets/`, `reports/`), so the two-file shortcut needs no temporary store.
- Until sections exist (milestone 4), interpreter components are scoped by role only; per-extension scoping arrives with the second adapter.
