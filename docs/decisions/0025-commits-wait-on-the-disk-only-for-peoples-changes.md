# 0025. Commits wait on the disk only for the changes people make

- **Status:** Accepted (2026-10-09)
- **Source:** the [code review of 2026-10-08](../reviews/code-review-2026-10-08.md), C2 and C3, and the owner's answer there; refines [0003](0003-sqlite-evidence-store.md)

## Context

The store committed every write waiting on the disk (WAL, `synchronous` FULL), about 3 ms each, and most of a replay's 3,300 commits were diagnostics: a query's recipe and text in the store's query log, and the same recipe in the fixture, each its own transaction. A replay of the drawing-sheet slice spent 9.5 of 57 seconds on them. A zipped fixture's temporary copy was written to as well, and removed on close.

The owner, 2026-10-09: "I think it's safe to reduce durability of commits. This system is designed to resume from what is known to be committed, IIRC. The main exceptions should be the things humans manipulate manually, e.g. adding/removing items to project, updating configurations, etc."

## Decision

- **The store commits at `synchronous` NORMAL** (WAL). A power cut, not a crash, may lose the last transactions: a task's row and claims commit together (`Store.record_task`), so a lost one is a task asked again, its answer usually still in the fixture.
- **The changes people make commit at FULL** (`Store._durable`): sources added, updated, rescanned or removed; binding and resets; the reconcile setting; `gc`. Configuration joins them once it's in the store.
- **The query log isn't committed alone:** its rows ride in the next transaction, and the store's close commits what's left.
- **The fixture keeps its rollback journal at FULL:** a recorded answer is paid for, and the fixture is what makes a lost store task free to ask again. Only its recipe notes are batched, committed with the next answer or on close. (The plan had proposed WAL with NORMAL for the fixture too; a read-only connection to a WAL file leaves `-wal` and `-shm` files beside it, and recording's one commit per answer costs little next to the model's answer.)
- **A zipped fixture is replayed from a read-only copy:** nothing is marked in a copy removed on close.
- **A test guards it:** a replay commits fewer times than half the answers it serves (65 for 182 when decided; 429 before).

## Consequences

- The eight development runs of the slices replay in 98 s instead of 127 s, reports identical.
- A crash loses nothing committed; a power cut may lose a run's last tasks and query-log rows, never a source, binding or reset.
- A diagnostic row written just before a failed transaction is rolled back with it.
