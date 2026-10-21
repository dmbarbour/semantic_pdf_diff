# Reading formats beyond PDF

- **Date:** 2026-10-03 to 2026-10-07
- **Asked by:** the owner, 2026-10-02: "When we do add the alternative readers, we'll implicitly get a new form of control tests: same facts across two or more representations"; and on Word's pictures, 2026-10-03: "Perhaps do a bit more research."
- **From:** the multi-format adapters plan, retired 2026-10-21 (the [plans index](../plans/README.md#retired) says how to read it). Its decisions are [0020](../decisions/0020-formats-share-one-task-core.md) to [0023](../decisions/0023-tables-read-by-rules-a-model-writes.md); its table and reading levers are in the [lever index](../reviews/levers.md).
- **Method:** the controlled corpus written in each reader's format (`bench/controlled/`: `representations.py`, `word.py`, `slides.py`, `workbooks.py`) and scored by the same keys; the public samples (3GPP's Word documents and decks, the IEA and RAN1 workbooks) read and checked by eye. gemma-4-31B on DeepInfra.

## The same facts in other formats

| Representation | Against the PDFs |
|---|---|
| Markdown (17 documents, 2026-10-03) | Recall 1.000 in both. Misbound claims 0, where the PDFs had 6 (`wtp-tables-s1-clean`), 18 (`coaster-tables-s1-clean`) and 5–9 (the energy studies). Its 9 revision pairs: every change, addition and removal, no false change, 0–6 pairs judged each (the PDF pairs 4–24). $0.066 |
| Word (17, 2026-10-03) | Full recall, no misbinding, its nine pairs as Markdown's. $0.058 |
| Word, charts as pictures (2026-10-03) | Energy study 21 of 21, misbound 0 (the PDF 7); end-use study 33 of 33, misbound 0 (the PDF 5) |
| Word, charts as chart XML (2026-10-04) | Every value right, kept to its month, read once: the end-use study 33 claims, 51 as a picture (its overview and tiles read the values twice). $0.014 |
| Decks (26, 2026-10-04) | Facts as Word's, fact for fact; the specification slightly better (13 against 10 on the renumbered revision); 15 pairs as Word's. $0.059 |
| Workbooks (26, 2026-10-04) | Facts as the decks' in 19 of 26 runs; the specification one fact fewer ("per channel group" put in the attribute rather than the conditions). $0.045 |
| Dense charts (`lcc-metered`, 51 facts) | Word, charts as pictures: 51 right, none loose or misbound. The PDF's clean drawing: 24 loose (its image reader named the peak demand line's values "power", the axis being in kW; in Word, with the caption beside the picture, "peak demand") and 14 misbound (its text reader) |
| The procedure diagram (`attach`, 26 facts) | Word, a WMF picture: 26 right, none hallucinated; the PDF 2 hallucinated, its raster drawing 5 |

- **The PDF schedules' misbinding came from layout** (the text layer's column shifts, the image reader's row names), not from the tables' content.

## Metafiles in Word documents (2026-10-03)

**The figures** (TS 38.300 v19.3's 143 metafiles; [decision 0021](../decisions/0021-metafiles-drawn-by-vendored-renderer.md)):
- 103 EMF, every one EMF+ "dual" (an EMF+ stream with a plain GDI fallback). 101 preview Visio objects: 65 binary `.vsd`, 36 `.vsdx`.
- 40 WMF, 37 of them previews of Msc-generator charts, whose OLE object holds the chart's source as text.
- Labels are text records: EMF+ DrawDriverString in 53 EMFs, GDI ExtTextOutW in 49, WMF ExtTextOut. A few store glyph indices instead of characters (4 seen).
- Visio's gradient boxes are drawn in the GDI fallback by an XOR trick: pattern blits (PATINVERT) over DIB pattern brushes.
- Across the samples: TS 38.300's three versions hold 270 EMF, 115 WMF and 19 PNG, almost all previews of embedded Visio drawings (176 `.vsd`, 92 `.vsdx`, 109 OLE `.bin` beside them); the five RAN1 contributions and summaries 13 PNG and 2 JPEG (plots and tables as pictures); the Rel-19 decks PNG, JPEG, TIFF and one embedded workbook.

**Renderers tried** on v19.3's 143 metafiles (renders in the scratchpad only):

| Route | License | On our figures |
|---|---|---|
| **metafile-render** 0.3.0 (Python; Pillow, pyclipper; ~7,100 lines; first released 2026-09, one author) | MIT | Every EMF renders. Sequence diagrams and stacks are good, and its SVG, drawn by PyMuPDF, keeps labels as text. Visio's gradient boxes become black stripes over their labels. 36 of 103 SVGs are a raster wrapped in SVG. 38 of 40 WMFs fail or render blank (Msc-generator's clipping). |
| Apache POI HEMF/HWMF (Java, ~16,000 lines of logic) | Apache-2.0 | All 143 render, the best seen: gradients, boxes and labels right. A port needs Java2D's clipping areas, transforms and raster operations rebuilt. |
| wmf2svg (Java, ~28,000 lines) | Apache-2.0 | All convert. Draws both streams of dual files (labels doubled); misplaced labels. |
| metafile-rs, emf-rs, emfsdk (Rust) | Apache-2.0 / MIT | A native build to maintain. metafile-rs drops all EMF+ text. |
| pyemf, pyemf3; libwmf | LGPL | Write or parse only; none renders what we need |
| libUEMF, libemf2svg, pymfvu, UniConvertor, libvisio-ng | GPL or AGPL | Ruled out for an MIT project |
| Pillow's WMF plugin | MIT-CMU | Renders only on Windows |

- **Also tried:** LibreOffice (`soffice --headless --convert-to`) renders EMF and WMF faithfully, about 1.5 s for five pictures in one call; converted to PDF, a drawing stays vector and its labels stay text. No external program is assumed ([decision 0020](../decisions/0020-formats-share-one-task-core.md)). PyMuPDF opens PNG, JPEG and TIFF but not EMF.
- **The specifications** ([MS-EMF], [MS-EMFPLUS], [MS-WMF]) allow copying them "in order to develop implementations". Microsoft's patent map lists no patents for any of them. An implementation of our own, or our own fixes, may follow them.
- **Text without rendering:** the metafiles' own text records (a record walker of about 300 lines); `.vsdx` shape text (the `vsdx` package, BSD-3; text found in 35 of 36); Msc-generator chart sources (`olefile`, BSD; 35 of 37 read). Binary `.vsd` would need a port of POI's HDGF (text only, ~1,700 lines).

**The vendored copy, with our fixes** (`src/semantic_pdf_diff/vendor/README.md`):

| TS 38.300, three versions | Before the fixes (v19.3) | After (all three) |
|---|---|---|
| Distinct metafiles drawn | 106 of 143 (37 WMF over the clip limit) | 163 of 163 |
| With text, words in all | 104, 3,939 | 155, 6,256 |
| Compared by eye with Apache POI's renders (v19.3's 143) | Visio's gradient boxes black over their labels; GetDC labels scattered; Msc-generator charts blank | close throughout |

- **Known differences:** EMF+ gradients drawn as one representative colour (the vendored brush approximation); translucent fills drawn opaque in a few figures; the 3GPP cover logo's EMF+ image not decoded (its fallback bitmap is drawn, cropped); 2 characters the built-in fonts can't show (counted); one path drawn with an AND operation skipped.
- **Read** (v19.2 → v19.3, $0.142 for both versions' pictures and the comparisons they added): claims from pictures 2,706 of 13,355; quotes found in the picture's own text layer 2,428 (90%); picture tasks 354 of 358 complete (4 long procedure diagrams hit the claim limit, before continued reading).
- **The label check** (`pictures.Reading.labels`) on 267 pictures (two versions): median 100%, 16 under 80%, none under half. The uncovered words are mostly axis titles and sentences in figures.

## Word documents on the real samples (2026-10-03 to 04)

What the first readers did, each mended (`docxdocs.py` says how):
- **A nested table was read three times:** squashed into its cell, added as extra columns, and read as rows of the outer table under its header ("Flow | 450 gpm" asked as Pump = Flow, Duty = 450 gpm).
- **A cell merged down** left the rows below it without their subject; **a cell merged across** shifted the cells after it under the wrong headers; **a table of one row** (a boxed note or proposal) was taken for a header with no rows and never read.
- **A modern text box was read twice,** once from its shape and once from the VML copy Word keeps for older readers (`mc:Fallback`), both glued into the sentence anchoring it. A Qualcomm RAN1 contribution draws its figures with Word shapes: read once each, on their own lines, its unread objects fell from 166 to 64, the rest shapes without text.
- **Equations (Office Math) were dropped:** TS 38.300's inline symbols vanished ("K_offset and K_mac:" read " and :"), along with values (Δf=15∙10^3 Hz).
- **Cells were skipped** when Python reused an lxml element's id; each `w:tc` is one cell.
- **The first layout-table rule misfired:** long cells or a pasted heading made 3GPP's tables of companies' comments (a "Company | Comments" header, then long views) into layout, half the tables of two RAN1 feature-lead summaries. A short, filled first row now keeps a table data.
- **TS 38.300's change history:** a title row merged across all its columns ("Change history") had been read as the header. The model mostly declines that table either way ("a change history log rather than engineering specifications"): 39 claims from its 1,187 rows before, 10 after.
- **TS 38.300 v19.2.0 and v19.3.0,** about 800 KB of text each, read for $0.52: 10,649 claims, 1,283 table rows.

## Workbooks on the real samples (2026-10-05)

- **The IEA 15 MW workbook's two published versions** (v1.0 and the current) as a revision pair: the blade shell layup sheet stacks 12 tables of one shape, each headed by label-and-value pairs ("Airfoil: circular", "Pct Span: 0.0"). Its claims carried no station until those pairs were read as the table's title: "different" findings 676 → 148, pairings of different items 649 → 52, changes found 26 → 93. A real change: the polars' angle in radians in v1.0, degrees now.
- **Its PDF report (54 pages) against each version:**

  | | Against the current workbook | Against v1.0 |
  |---|---|---|
  | Equivalent | 149 | 132 |
  | Different | 43 | 11 |
  | Overview: equivalent, different | 112, 31 | 86, 6 |

  - Against the current workbook, the differences are the turbine's later revision: rotor diameter 240 m against 241.35 m, rated wind speed 10.59 against 10.66 m/s, blade mass 65 against 67.92 t.
  - Against v1.0, the version the report was written from, most look like true discrepancies between the report and its own workbook (rated wind speed 10.59 against 10.88 m/s, the report also saying 10.8 elsewhere; hub overhang 11.35 against −11.014 m, a sign convention). One is a wrong pairing (rotor-nacelle assembly mass against nacelle mass).
  - Both runs hit `max_pairs` (1,000).
- **Read as stored:** the polars' header says "alpha [rad]" over values from −180 to 180 (degrees); claims carry the header's unit, as written. Cells hold 15 significant digits in General format ("3.78071922309736 m"), where Excel would show fewer in a narrow column.
- **The RAN1 #116 document list:** one table, A1:AJ1931, read in about 12 s.
