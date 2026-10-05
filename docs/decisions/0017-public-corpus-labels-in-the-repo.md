# 0017. Public-corpus labels committed as annotation files

- **Status:** Superseded by [0015](0015-repository-contents.md) (2026-10-03)
- **Source:** [evaluation benchmarks plan: decisions 2026-09-24](../plans/evaluation-benchmarks-2026-09-23.md#decisions-2026-09-24) and [Keeping it](../plans/evaluation-benchmarks-2026-09-23.md#keeping-it)

## Context

Benchmarks need answer keys that survive between runs: expected claims, adjudications, pair and relation labels. Labels on real documents can't leave the sandbox; labels on the public corpus can.

## Decision

- **Public-corpus labels were to live in the repo** as annotation export files, editable by hand, and rerun as a regression check whenever extraction, retrieval or comparison changed.
- **Real-document labels stay in the sandbox.** This part is still in force, through [0019](0019-offline-review-pages.md).

## Consequences

- Review batches, with their labels, were committed under `benchmarks/batches/` until 2026-10-03.
- Superseded when the repository was trimmed to code, docs and the answers tests replay ([0015](0015-repository-contents.md)). Batches and their labels are now local, and what they showed is written up in docs. The answer keys that are committed are the controlled corpus's, generated with their documents (`benchmarks/controlled/`).
