# 0031. A commit needs a recorded pass of the tree it commits

- **Status:** Accepted (2026-10-17)
- **Source:** [recording tooling](../plans/README.md#retired), milestone 1

## Context

"Tests, then commit" was a rule kept by habit: commands chained `tests > log && commit`, and a pipe through `tail` once masked a failure. On 2026-10-17 a docs commit went in after a test command that named a module that doesn't exist. Partial commits (some changes staged, as when a fix is committed apart from the feature it was found in) were tested by hand in a temporary worktree, when they were tested at all.

The owner, 2026-10-17: "Perhaps adding a little CI for the fast tests to force a pass or a record of passing before commit." Of the options offered, the owner chose that a commit without a recorded pass runs the quick suite on its staged tree and is blocked on a failure.

## Decision

- **A pass is recorded for a tree:** `scripts/run_tests.py`, run over every module, records a pass for the working folder as git would commit it (untracked files included, ignored ones not). The tree is hashed before and after the run, and a tree edited during the run gets no pass. Passes are kept in the repository's git folder (`test-passes.jsonl`), shared by its worktrees.
- **The pre-commit hook** (`scripts/hooks/pre-commit`, enabled by `git config core.hooksPath scripts/hooks`):
  - lets a commit through when its staged tree has a recorded pass, quick or full;
  - otherwise checks the staged tree out into a temporary folder, with `samples/` linked in, and runs the quick suite there (`QUICK=1`, about 3 minutes);
  - records that pass, or blocks the commit on a failure.
- **The staged tree is what's tested:** a partial commit is tested as committed, not as the working folder stands.
- **Not pushed anywhere:** nothing runs on a server; the gate is local.

## Consequences

- A commit after a full suite run on the same tree goes through at once; any other commit takes about 3 minutes.
- The gate's own runs set `GATE_NO_RECORD`, not a flag, since a staged tree's suite may predate the gate: its first run passed a flag an older `run_tests.py` didn't know.
- A hung test module fails after `run_tests.py`'s timeout (15 minutes by default) instead of stalling the gate: its first hang, a lost result in the fork pool, waited until stopped by hand.
- `git commit --no-verify` skips the hook; nothing here uses it.
- `python scripts/gate.py status` says whether the working and staged trees have passes.
