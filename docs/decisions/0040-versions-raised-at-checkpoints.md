# 0040. Versions are raised at each checkpoint, changelogged and tagged

- **Status:** Accepted (2026-10-28)
- **Source:** the owner, 2026-10-28: "It's about time to be systematically updating version numbers. We've been on 0.2.0 for a while now."
- **Builds on:** [0001](0001-v0-2-0-stable-baseline.md) (the stable baseline, no users yet), [0014](0014-lab-as-its-own-distribution.md) (the lab pinned to the product's version)

## Context

- The version stayed 0.2.0 for about 630 commits after the tag (2026-09-24 to 2026-10-28), so it didn't say which build made a store or a report.
- The owner runs trials on documents that can't be shared. A report of a problem needs to name the build that showed it.
- The package's own version was part of each store's binding ([0004](0004-store-bound-to-its-interpreters.md)), so raising it would have read every store again.
  - Nothing would have been paid for: unchanged queries replay from the answers cache. But every store would have been read again, for no change.
  - It never caught a change: 630 commits shipped as 0.2.0. What a change asks differently is bound by the prompts, the settings and each reader's version ([0016](0016-content-reread-when-its-reader-changes.md)).

## Decision

- **Versions are `0.MINOR.PATCH`** while the tool has no users ([0001](0001-v0-2-0-stable-baseline.md)'s period).
- **Raised at each checkpoint that changes the product,** in a commit of its own after the checkpoint's commits:
  - **MINOR** where the checkpoint changes what the product does: a feature, a new default, a changed format or output.
  - **PATCH** where it only fixes bugs or changes nothing a user sees.
  - **No change** for commits touching only the lab, the docs or the tests.
- **A checkpoint** is a batch of work reported to the owner. One version per batch, however many commits it holds; the report names the version.
- **The lab shares the product's version,** and each pins the other's ([0014](0014-lab-as-its-own-distribution.md)).
- **Each version gets:**
  - an entry in `CHANGELOG.md`, saying what a user would notice
  - an annotated tag, `vX.Y.Z`, made locally (the owner pushes)
- **The version records; it doesn't bind.**
  - It's in `--version`, and in each interpreter a store and its reports record.
  - A store binds quietly to a new version of the package (`binding.OWN_VERSION`). A library's version (PyMuPDF, pydantic) still reads the store again.

## Consequences

- A store or report names the build that last read it, and trial reports can quote it.
- Raising the version costs no rereading.
- `README.md`'s status names the current version and links the changelog. Docs no longer carry a version in their titles: they describe the build they ship with.
- Compatibility (migrations, release branches) still waits for users, as [0001](0001-v0-2-0-stable-baseline.md) says.
