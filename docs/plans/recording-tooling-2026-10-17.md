# Recording tooling: a commit gate, answer archives, parallel re-records and variants

- **Status:** Completed (2026-10-17)
- **The owner (2026-10-17):** "Let's do some tooling work. Faster re-records. Working with a few variants without losing information. Perhaps extraction and export of a refined replay cache instead of relying on in-place pruning. Perhaps adding a little CI for the fast tests to force a pass or a record of passing before commit. I think a little work here will improve things moving forward."
- **Takes over** *Testing and recording infrastructure*'s continuous integration item (plans index, Tentative), as a local gate: nothing is pushed.

## Why

- **Re-records are slow and hand-made.** Making `read_holders` and `hedge_rule` defaults (2026-10-17) re-recorded the controlled corpus in six processes started by scratch scripts, each on its own copy of the fixture, merged by hand: about 3 hours. One `controlled.py run` process would have taken many more. The old run stores refuse a prompt change, so they were moved aside by hand first.
- **Variants lose answers.** Each lever arm recorded into a fixture copy in scratch (b1 to b65), with its own runs folders, launcher scripts and, in a worktree, its own ledger to fold back. Answers paid for live only in those copies.
- **Pruning in place is fragile.** An answer's only use mark is the time it was last served, so "unused since T" needs one process, no restart after a code change, and the right responder (an unguarded prune once emptied a fixture). The slices' re-record of 2026-10-17 pruned a copy of the packed zip; the answers never reached the slices' working fixture (`tests/fixtures/slices.sqlite`), nor the ledger ($1.09, summed afterwards from the answers' usage).
- **Commits are gated by habit.** "Tests, then commit" is a rule, not a check: on 2026-10-17 a docs commit went in after a test command that named a module that doesn't exist.

## Design

The owner's answers (2026-10-17, choosing among the options offered): the gate "Run tests, then block"; "One archive per corpus"; variants "Yes, include variants".

- **A commit gate.**
  - `scripts/run_tests.py`, run over every module, records a pass for the exact tree it tested (its content hashed as git would commit it, untracked files included, before and after the run: a tree edited mid-run isn't recorded).
  - A pre-commit hook (`scripts/hooks/pre-commit`, enabled by `git config core.hooksPath scripts/hooks`) lets a commit through when its staged tree has a recorded pass. Otherwise it checks the staged tree out into a temporary folder, runs the quick suite there (`QUICK=1`, about 3 minutes), records the pass, and blocks the commit on a failure. A partial commit (some changes staged) is tested as committed.
- **One answer archive per corpus, and exports instead of pruning.**
  - The working fixtures (the controlled corpus's `fixture.sqlite`, the slices' `slices.sqlite`, the probes', the real pairs') are archives: every answer ever recorded, every variant's, kept. Several processes may record into one at once (SQLite's write-ahead log, waiting on locks).
  - A committed zip is exported: the runs it serves replay from the archive, read-only, and every answer served is copied into a new fixture, which is packed. Nothing is pruned, and no use time decides anything. `controlled.py pack` and the slices' recording export this way.
  - The answers scattered in scratch copies (the arms', the slices' copy) are merged into their archives.
- **Parallel re-records.**
  - `controlled.py run --jobs N`: documents read alone first, then the revision pairs (which replay the documents' extraction), each phase spread over N processes sharing the archive. A cost cap is checked before each run starts, so N runs may overshoot it together.
  - `--reset` passes the stores' reset through: a store bound to other settings clears what changed and reads it again (answers from the archive), instead of refusing.
  - One command for the corpus's whole refresh (record, row by row, export, replay, score, context measures), whose exit status is 1 only for a run that failed, not for incomplete coverage (2).
  - `record_runs.py --jobs N` likewise for the slices, with the ledger written by default.
- **Named variants.**
  - `controlled.py run --variant FILE.json`: a settings overlay over the corpus's settings, with optional document and format filters ("every PDF, and the views documents in every format"). Its runs go under `benchmarks/runs/controlled/variants/<name>/` (and the pairs' likewise), its answers into the shared archive. `paired.py` names variants as well as folders.
  - Run from a frozen worktree (to pin the code), the archive and the ledger default to the main checkout's, so nothing needs folding back.

## Milestones

1. **The commit gate:** pass records, the hook, tests; enabled in this checkout.
2. **Archives and exports:** the write-ahead log and lock waits; export on replay; `pack` and the slices exporting; scratch answers merged into the archives; [samples and testing](../samples-and-testing.md) and [decision 0006](../decisions/0006-replay-fixtures.md) amended.
3. **Parallel re-records:** `--jobs`, `--reset`, the refresh command, the slices' recorder; proved by exporting the committed zips again unchanged.
4. **Variants:** overlays, filters, folders, worktree defaults, `paired.py`; proved by re-running a measured arm's comparison (b62's `hedge_rule` against its null) from the archive at no cost.

## Results (2026-10-17)

- **The commit gate** (7b6308a; [decision 0031](../decisions/0031-commits-need-a-recorded-pass.md)): every commit since went through it. Its first run blocked a commit, rightly: the staged tree's own suite predated the gate's flag.
- **Archives and exports** (3dab76b; [decision 0006](../decisions/0006-replay-fixtures.md), amended): the scratch copies' answers merged into the archives (controlled 25,395 → 58,424 answers, slices 12,187 → 38,567, real pairs 7,488 → 11,749). Both committed zips are exported again with every answer as before and fewer recipe rows; an export matches the committed zip's bytes once exported.
  - Merging an archive with its arms' copies first let 28 arm answers replace committed ones: a committed zip now merges into its archive with `--prefer`.
  - 6,170 transient failures recorded under "gemma-4" (a run without its credentials) stayed in the controlled archive: deleting them was refused by the session's safety check, so it was left to the owner. A replay's responder guard counts only responders with answers, so nothing read them. Cleared 2026-10-19 (the owner: "You can clear the old "gemma-4" stuff."), with the 3,179 descriptions and 4,585 recipes of queries only they had; the archive still holds every answer of the committed zip.
- **Parallel re-records** (7cf7cc7): `--jobs` in `controlled.py` and `record_runs.py`, `--reset`, and `controlled.py refresh`. An open transaction for recipe notes held each fixture's write lock for a whole run, so six processes were no faster than one. Now the corpus exports in 1m54s with six processes (4m43s alone; 1m28s after the pool's fix below), and the slices in 41s with eight (2m15s). `refresh --jobs 6` over the current corpus took 8 minutes at $0 and changed nothing.
- **Found by the gate after the milestones:** the fork pool lost a result now and then (a queue's background thread across forks), and the gate's quick suite waited forever on it. Workers now send results down pipes of their own (5eec0be; the corpus's export 1m28s with six processes), and a test module that takes over 15 minutes fails instead of stalling (run_tests.py's `--timeout`).
- **Variants** (779d34a): b62's comparison replayed as three variants at $0, its verdict and numbers as recorded. The null arm is one document short of 145: 21 answers its arm recorded weren't kept.
- **Left for later** (the *Testing and recording infrastructure* row): collection rounds, the in-house recording kit, fixture summaries beside each zip, and a test replaying with the side tables dropped.
