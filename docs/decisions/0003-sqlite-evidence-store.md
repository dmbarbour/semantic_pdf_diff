# 0003. A resumable SQLite evidence store in a local folder

- **Status:** Accepted (2026-09-23)
- **Source:** [evidence store plan](../plans/sources-and-evidence-store-2026-09-23.md): [layout](../plans/sources-and-evidence-store-2026-09-23.md#layout), [why SQLite](../plans/sources-and-evidence-store-2026-09-23.md#why-sqlite), [decisions](../plans/sources-and-evidence-store-2026-09-23.md#decisions-2026-09-23), [milestones](../plans/sources-and-evidence-store-2026-09-23.md#milestones) 2 and 7; [store milestone 2 review](../reviews/store-m2-sqlite-store-2026-09-24.md); [architecture clean-up: progress](../plans/architecture-cleanup-2026-10-02.md#progress), milestone 6c (read-only `Store.open`)

## Context

0.1 extracted, compared and reported in one run, with a folder of cached responses. Long runs over many files must survive interruption, several sources must share work, and many views (evidence with provenance, coverage, differences, exports) should come from one body of evidence.

## Decision

- **A store is a local folder:**
  - `store.sqlite`: sources, files, content, evidence, coverage, cached answers, the query log, comparisons
  - `assets/`: rendered crops
  - reports, generated from the database
- **SQLite:** in the standard library, so no new dependency. WAL mode, so readers work while extraction writes.
- **Each task's evidence and coverage commit in their own transaction.** A rerun resumes by replaying cached answers. How long a commit waits on the disk: [0025](0025-commits-wait-on-the-disk-only-for-peoples-changes.md).
- **One writer at a time:** an exclusive lock on the folder. A second writer gets "is in use by another process" (`store.StoreInUse`).
  - `Store.open` opens a store read-only, without the lock, so a reader neither waits on a run nor stops one.
- **Owner-only permissions:** folder `0700`, files `0600`. A store is as sensitive as its sources.
- **No migrations during development:** a store whose schema version differs from `store.SCHEMA_VERSION` refuses to open and asks for a new store ([0001](0001-v0-2-0-stable-baseline.md)).
- **Staged commands over a store:** `compare --store`, `source ...`, `show`, `report`, `gc`. The two-path command is a shortcut whose `--out` folder is a store.

## Consequences

- An interrupted run (`--max-calls`, a cost cap, a crash) loses nothing finished. Rerunning the same command resumes.
- Sharing a store folder shares its documents' content, crops and answers.
- Copying a store is fine. Using one live over a network filesystem isn't supported (SQLite's locking is unreliable there).
- On platforms without `fcntl`, the writer lock is absent.
- After a schema change, a new store re-pays its answers unless a fixture holds them (`--fixture`, [0006](0006-replay-fixtures.md)).
- `report` regenerates a report from a saved comparison without model calls.
- `gc` removes orphaned content with its evidence, crops and cached extraction answers. Saved comparisons are kept.
