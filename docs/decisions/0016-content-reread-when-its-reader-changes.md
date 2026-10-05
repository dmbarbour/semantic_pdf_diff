# 0016. Content is read again when its reader changes

- **Status:** Accepted (2026-10-04)
- **Source:** [multi-format adapters: merged and nested cells](../plans/multi-format-adapters-2026-09-23.md#progress) ("A gap met on the way"); the plans review of 2026-10-04 (the owner: "Go for the cheap wins!")

## Context

A store marks each content item extracted once its tasks are done, and a later run loads the item from the store rather than reading it again ([0003](0003-sqlite-evidence-store.md)). The binding ([0004](0004-store-bound-to-its-interpreters.md)) catches a changed model, prompt or setting, but not a changed reader: when the Word reader learned merged cells, a TS 38.300 store re-run kept the old reader's table tasks and asked nothing new. Content in a format with no reader yet (a `.docx` before the `office` extra was installed) was marked extracted too, so it was never read once a reader arrived.

## Decision

- **Each reader has a version** (`extract.READERS`: `pdf/1`, `text/1`, `docx/2`), raised whenever what it sends the model changes without a setting or prompt changing: its parsing, its blocks, its tasks.
- **The store records, per content item, the version that extracted it** (`content.extracted`), or `unsupported` where no reader could.
- **A run re-reads an item whose recorded version differs from its reader's current one,** an earlier or later one alike, and an item that has gained a reader. Its tasks are made again; `keep_tasks` drops those the new reading doesn't have.
- **Nothing is refused and no reset is needed:** a reader change touches only the content it reads, not the store's binding.

## Consequences

- Unchanged queries replay from the store's cache ([0009](0009-content-addressed-queries.md)); only the queries the new reader changed are paid for. A re-read costs time, not money, for content the reader change didn't affect.
- Stores made before versions were recorded hold `1`, which matches no version: every item is read once more, free.
- The discipline is by hand: a reader change that alters requests without raising its version leaves stores stale. The golden requests and the controlled corpus's committed keys (`tests/test_controlled.py`, the Corpus test) show when a change alters what a reader sends.
- Situating results for a PDF are kept unless the re-read dropped tasks.
