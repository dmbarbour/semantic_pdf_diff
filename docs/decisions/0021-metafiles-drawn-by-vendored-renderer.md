# 0021. Word and PowerPoint metafiles are drawn by a vendored renderer

- **Status:** Accepted (2026-10-03)
- **Source:** [multi-format adapters](../plans/multi-format-adapters-2026-09-23.md), "Pictures in Word documents, in detail"

## Context

Engineering Word documents carry many figures as Windows metafiles (EMF, WMF), which PyMuPDF and the Python imaging libraries can't draw, and no external program is assumed ([0020](0020-formats-share-one-task-core.md)).

## Decision

- **Route 1, a vendored copy of metafile-render,** draws metafiles to images for the vision tasks. The owner (2026-10-03): "Let's go with 1 for now, but hold 2/3 as fallback options if we struggle with fixes or quality."
- **The fallbacks, kept:** a port of Apache POI's renderer (the best quality, a much larger job), or a renderer of our own from the specifications for the record types our figures use.

## Consequences

- Fixes to the renderer are ours to carry; its record coverage is measured on the samples' figures.
- A picture the renderer can't draw is recorded as skipped, with the renderer's error, and the run goes on.
