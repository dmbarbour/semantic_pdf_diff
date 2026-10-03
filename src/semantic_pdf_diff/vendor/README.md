# Vendored code

Code kept here is someone else's, copied in so that it can be fixed for our documents and so that what renders
them doesn't change under us. Each package keeps its license file; changes made here are listed below, newest last.

## metafile_render

- **What:** renders Windows metafiles (WMF, EMF, EMF+) by playing their records back into drawing commands.
- **Source:** [metafile-render](https://github.com/myhloli/metafile-render) 0.3.0, the PyPI wheel
  `metafile_render-0.3.0-py3-none-any.whl` (sha256 `94144d7e6195711d…`, uploaded 2026-09-05), every file checked
  against the wheel's RECORD when copied (2026-10-03).
- **License:** MIT, © 2026 Xiaomeng Zhao (myhloli); `metafile_render/LICENSE`.
- **Why:** pictures in Word documents (docs/plans/multi-format-adapters-2026-09-23.md, "Pictures in Word
  documents"); the owner chose it over porting Apache POI or writing a renderer of our own (2026-10-03), which stay
  fallbacks.
- **Dependencies:** Pillow and pyclipper (the `office` extra).

**Changes here** (each marked `semantic_pdf_diff:` in the code), found on 3GPP TS 38.300's 163 figures (Visio
previews as EMF+ dual files, Msc-generator charts as placeable WMF), 2026-10-03:
1. **Dual EMF files play their EMF+ stream** (`parser.py`), as GDI+ does. The EMF records are played only when the
   EMF+ stream holds no drawing, or can't be read. Visio's fallback records draw gradients by XOR tricks that
   came out as black boxes over the labels.
2. **A GetDC window's EMF records draw in GDI's own coordinates and clip** (`gdi/bridge.py`), not through EMF+'s
   world and page transforms. Visio places every label so; under EMF+'s page scale of 2 they landed twice as far out,
   many off the picture.
3. **A placeable WMF starts with its window and viewport set to its bounding box** (`gdi/playback.py`), as its
   players set them. Msc-generator's charts set a window but no viewport and were drawn into a 1-by-1 corner.
4. **EMF+ regions (object type 4) are read** (`emfplus/objects.py`, `emfplus/playback.py`): the node tree computed
   with pyclipper into one path of polygons, and SetClipRegion clips to it. It used to stop the playback ("complex
   region clipping is unsupported"), losing the rest of the figure.
5. **A text record's rectangle is its background only with ETO_OPAQUE** (`gdi/text.py`). With ETO_CLIPPED alone it
   only clips; an opaque background mode fills the text's cell. A single space's clip rectangle had painted white
   over a whole logo.
6. **The clip-operation limit is 100,000, not 64** (`limits.py`). Msc-generator's charts exclude a rectangle per
   label.
