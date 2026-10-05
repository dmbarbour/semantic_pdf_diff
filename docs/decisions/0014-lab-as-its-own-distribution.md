# 0014. The lab is its own distribution, installed as `semantic-pdf-diff[lab]`

- **Status:** Accepted (2026-10-02)
- **Source:** [code review 2026-10-01: decisions](../reviews/code-review-2026-10-01.md#decisions-2026-10-02) item 3; [architecture clean-up](../plans/architecture-cleanup-2026-10-02.md): [decisions](../plans/architecture-cleanup-2026-10-02.md#decisions-2026-10-02), [design](../plans/architecture-cleanup-2026-10-02.md#packaging-the-lab-as-an-extra), [progress](../plans/architecture-cleanup-2026-10-02.md#progress) milestone 8

## Context

The tooling that measures and improves the product (rounds, judges, rubrics, review panels, spot checks, controlled documents, eye and page tests) lived in the product's package and kept growing it. An extra installs only optional dependencies: every module in a distribution is installed either way, so an extra alone hides no code or commands.

## Decision

- **The owner (2026-10-02):** "IIUC, Python supports installing `package[extra-features]` in some way ... this might offer a way to make meta-evaluation and bench tooling available via CLI without making it the default."
- **The lab is a second distribution in this repository:** `semantic-pdf-diff-lab` in `lab/`, package `semantic_pdf_diff_lab`, with `eval/` and `bench/`.
- **The core declares it as the extra `lab`** (`pyproject.toml`).
- **The lab registers commands** through the entry-point group `semantic_pdf_diff.commands` (today `review` and `queries`). The core CLI runs whatever is installed (`cli.lab_commands()`).
- **The product imports nothing from the lab.** `tests/test_boundaries.py` checks every product module's imports, lazy ones included, and that evaluation doesn't reach into the benches.
- **Development installs both:** `pip install -e '.[dev]' -e lab`.

## Consequences

- A plain install is the diff tool alone.
- The rounds, spot checks and benches run as scripts (`scripts/run_round.py`, `scripts/spotcheck.py`, `scripts/controlled.py` and others), which need the lab installed.
- The two distributions pin each other's version (`0.2.0`), so they're released together.
- Types used only by evaluation live in the lab (`eval/models.py`: `RoundSpec`, `Criteria` and others), not in the product's `models.py`.
- Code both sides need belongs in the product (as `printed_value` moved to `values.py`).
