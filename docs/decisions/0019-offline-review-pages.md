# 0019. Labels are collected on offline review pages, questions judged blind first

- **Status:** Accepted (2026-09-25)
- **Source:** [evaluation benchmarks plan: decisions 2026-09-25](../plans/evaluation-benchmarks-2026-09-23.md#decisions-2026-09-25); [evaluation s01 review](../reviews/evaluation-s01-2026-09-25.md); [benchmarks README: reviewing a batch](../../benchmarks/README.md#reviewing-a-batch-for-people)

## Context

People label in short sessions and sometimes on documents that can't leave a sandbox. A labelling tool needing a server or network would exclude those documents. Judging an answer alongside its question also blurs two faults: a bad question (chunking, headings, crops, context), and a bad answer.

## Decision

- **A review page is a local, self-contained HTML file:**
  - it works offline, so it works inside the sandbox on real documents
  - one item per screen, progress saved in the browser
  - labels downloaded as a file and imported with `pdf-semantic-diff review import`
- **Batches are small:** about 15–20 items, 10–20 minutes a session.
- **Two pages per batch, in order:**
  - `questions.html` first, blind: is what the model was asked answerable?
  - `review.html` second: the answer, judged against that input
- **Labels on real documents never leave the sandbox.** Only public-corpus labels are shared.
- **Evidence-web relations** (component of, input to, contradicts…) get their own item type when that work starts.

## Consequences

- Sampling, review, import and agreement are lab commands (`pdf-semantic-diff review sample | import | agreement`), installed with `semantic-pdf-diff[lab]` ([0014](0014-lab-as-its-own-distribution.md)).
- Labels and batches are local working data ([0015](0015-repository-contents.md)). What a batch showed goes into a review document.
