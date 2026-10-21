# 0021. Word and PowerPoint metafiles are drawn by a vendored renderer

- **Status:** Accepted (2026-10-03)
- **Source:** [multi-format adapters](../plans/README.md#retired), "Pictures in Word documents, in detail"; the renderers tried in [formats beyond PDF](../research/formats-beyond-pdf-2026-10-07.md)

## Context

Engineering Word documents carry many figures as Windows metafiles (EMF, WMF), which PyMuPDF and the Python imaging libraries can't draw, and no external program is assumed ([0020](0020-formats-share-one-task-core.md)). The owner (2026-10-03), on LibreOffice as the converter: "I wouldn't count on LibreOffice being available in most environments, among them my intended usage environment. It's also outside our control and difficult to make reproducible. My intuition is that it isn't the right move. Perhaps do a bit more research. If there is an un-maintained python lib with a suitable license, consider grabbing a copy and extracting what is needed?"

## Decision

- **Route 1, a vendored copy of metafile-render,** draws metafiles to images for the vision tasks. The owner (2026-10-03): "Let's go with 1 for now, but hold 2/3 as fallback options if we struggle with fixes or quality."
- **Pictures are read within their document** (the owner, 2026-10-03: "Yes, we'll want similar context as what PDF pics get."): each picture a page at its displayed size, read by a PDF figure's image tasks, its caption as source text, its own text as a text layer, its claims located at its paragraph.
- **Every picture is read** (the owner: "Every pic."), captioned or not, with no size floor.
- **The fallbacks, kept:** a port of Apache POI's renderer (the best quality, a much larger job), or a renderer of our own from the specifications for the record types our figures use.

## Consequences

- Fixes to the renderer are ours to carry; its record coverage is measured on the samples' figures.
- A picture the renderer can't draw is recorded as skipped, with the renderer's error, and the run goes on.
- The renderer's own safety limits are still constants (`vendor/metafile_render/limits.py`; the clip-operation limit raised from 64 to 100,000 for Msc-generator's charts), not settings (*More formats* in the [plans index](../plans/README.md#tentative)).
