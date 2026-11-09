# Semantic PDF Diff

A Python CLI for evidence-first comparison of competing engineering proposals or revisions of one design. It extracts atomic claims from text, tables, charts and diagrams with a small vision model behind an OpenAI-compatible endpoint, pairs related claims, and reports differences with provenance back to the page and region each claim came from. It never ranks proposals, and it never treats a missing counterpart as proof of absence.

## Status

**v0.49.0** (2026-11-08; [changelog](CHANGELOG.md)). Versions are raised at each checkpoint and tagged ([decision 0040](docs/decisions/0040-versions-raised-at-checkpoints.md)). The first tag, v0.2.0, compared two PDFs. Since then the tool has gained:

- **Sources** as files, folders and zip archives, declared in a persistent, resumable store
- **Replay fixtures:** recorded model answers, so runs replay offline
- **Levers:** how documents are read, composed as mixins (`levers.py`)
- **The lab** (`lab/`, its own distribution): improvement rounds judged by model panels and people, controlled documents with known facts, eye and page tests
- **Plain text, Markdown, Word, PowerPoint, Excel, CSV and images** (`.png`, `.jpg`, `.tif` and others; read by vision, as a scanned page is) read as well as PDF: sections from headings (a slide's title, a sheet's name), paragraphs, tables, charts from their data, pictures and speaker notes, claims located by line, paragraph, slide or sheet and cells (Office formats need `pip install 'semantic-pdf-diff[office]'`). Each table in Excel, CSV, Word, PowerPoint or PDF is read as a model, asked once per table, says it should be: by rules applied to every row, row by row, or as a summary (a series, a log, a list) computed from all of them
- **Revisions aligned before they're judged:** items matched across revisions by their values, equal values settled without a model, and the report showing how it grouped them
- **One source on its own** (`analyze`): a file or a folder of documents read and reported, its claims browsed and searched without comparing. Each subject's claims are also read together, then each kind's items (`second_pass`, on by default; a request a subject or kind): what's restated, refined or contradicted (pairs of values code finds differ asked about too), likely misreads, likely gaps, and what a kind's items give together, noted beside the claims and in an Inconsistencies view, never changing them; the claims it doubts are read again from their place, and the gaps it finds looked for where they'd be
- **Indexes beside every report:** subjects and their kinds, properties, claims, figures and tables, a glossary, and what a source doesn't give (a sibling's missing property, a table's cell left blank, a reference not found, a placeholder), as index.md, an index workbook, CSV and the page's views; a comparison's merged, each subject once with each source's values
- **RAG export** (`export`): a report as Markdown chunks, by section, by subject (with what it doesn't give), by kind (a table of its items), by table (a document's own, as read), by topic and, for a comparison, by finding, each saying where it came from, the second pass's notes under the claims they're about, with chunks for finding things and an index
- **Differences explained:** in revisions, each difference named by kind (a value or its conditions changed, renamed, restated, misread, not the same item), value changes listed first
- **An endpoint checked before it's used:** each model checked and calibrated on first use (how small it reads among the checks), and asked a small request every run, so a run left overnight fails at once where an endpoint is down; a run names its models and says which features are off for want of one (`none` goes without); `config models` lists what the endpoint serves (chat, embedding, rerank; context, price), `config test --model NAME` tries a candidate before it's set (`--rerank`, `--embed`: a reranker, an embedding model), and `config checks` shows what was checked and measured

**Status:**
- Extraction has been measured with one real model (gemma-4-31B, through DeepInfra) on public sample documents and the controlled corpus.
- It isn't a validated engineering sign-off tool; see [limitations](docs/limitations.md).
- **Still planned:** criteria-first comparison of two or more sources, the second pass in comparisons, and subjects matched across documents. See [docs/plans/](docs/plans/README.md).

## Quick start

Python 3.10+:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
export OPENAI_API_KEY='your-serving-provider-key'
export OPENAI_BASE_URL='https://your-provider.example/v1'
semantic-pdf-diff config models vision           # the endpoint's models reading images
semantic-pdf-diff config test --model MODEL-ID    # a candidate tried before it's set, for a fraction of a cent
semantic-pdf-diff config set --user model MODEL-ID
semantic-pdf-diff config test                     # the endpoint, the key and the model checked
semantic-pdf-diff compare team-a.pdf team-b.pdf --store result
```

The model, like the endpoint's other settings (context, concurrency, timeout), is the user's: kept once for every store. A store keeps its own settings: `semantic-pdf-diff config show --store result` lists them by group, `config set NAME VALUE` sets one for every run in the store, and `config help NAME` says what it does and what changing it redoes. `semantic-pdf-diff --help` lists every command, the environment it needs and examples; `semantic-pdf-diff COMMAND --help` (or `semantic-pdf-diff help COMMAND`) gives a command's options, and `semantic-pdf-diff settings` prints every setting a run would use (with `--changed`, those differing from the defaults: a starting `--config` file).

Open `result/report.html`: it's one file, which can be moved or sent on its own. Its crops are embedded in order of value (the findings to check, and claims read from charts, diagrams and tables, first) until the file reaches `--report-budget` (20 MB by default); `semantic-pdf-diff report --store result --dry-run` says what a budget leaves out. Each claim's card shows the source's text around its quote (a table row under its header), in full where its crop was left out. For comparisons too large for one file, `--split` writes a file per pair of files and an index, in a folder to zip and send. The page shows the findings, or every claim of both sources, by topic, file and relation; its search takes words in any order, `"phrases"`, `-exclusions`, `a OR b` and a claim's parts (`entity:pump`, `page:10-20`), finds the most relevant first, compares values across units (`>50kW` finds 0.075 MW), and keeps what's shown in the page's address (the view, every filter, the topic and the search), to bookmark or send. Each finding's and claim's *Link* puts its own address in the bar (`#claims&claim=ID`), and Back steps through the views. Each card's *Claims like this* finds the other source's claims most like it (by meaning too, with an embedding model configured: `config set embed_model Qwen/Qwen3-Embedding-8B`); in the claims view, a search also shows the found claims' counterparts and the claims under the documents' other names for what was searched (the model groups them once a comparison: `search_names`), and offers the other source's names. Machine-readable results are in `report.json`; the extracted evidence, its provenance and coverage are in `evidence.json`.

**Indexes** are written beside every report (`analyze`'s and `compare`'s), built from what was read with no model requests: `index.md` (subjects A to Z, each with its properties and every value with where it's said; then properties, and figures and tables), `index.xlsx` (a sheet per index; Subjects an outline, a subject's row with its values beneath it, collapsing to the subjects), `index/*.csv` (subjects, properties, claims, figures), and `report.json`'s `index`. Kinds of items (P-101, P-102, P-103 as "pump (P)"; "Room 104", "Room 105" as Room) each a table of its items by property, "—" where an item gives none its siblings do. **What it doesn't give**, found by code and labelled weak: in a comparison, a property one source gives an item the other describes and doesn't give (looked for where it'd be, the `look_gaps` setting, on by default: given under another name, not given, no place for it, or not shown); a property most of an item's siblings give that it doesn't, a figure, table or sheet cited and not found, a value given as a placeholder ("TBD"). The page shows them as its Subjects, Kinds and Figures views, each value linked to its claim, the search box showing the rows it finds: by their own words, and by their claims for the rest of its language (`file:`, `page:`, a value compared, …), a figure's and a glossary term's own file and page too. **Glossaries** too (the `glossary` setting, on by default): each source's abbreviations, defined terms, symbols and conventions, read from the parts headed Abbreviations, Definitions, Symbols, Legend and the like (by the model, each term kept only where the text holds it and its meaning; a table or tabbed list as it is) and from prose ("net positive suction head (NPSH)"), in index.md, `index/glossary.csv`, the workbook and a Glossary view; a search for a term finds its meaning's claims too, wherever their words are, and offers the glossary's other names. Comparing revisions, the `align_glossary` setting (on by default) lets alignment take a meaning written out as its term, so a revision that abbreviates ("an SWD of") still pairs its values with the other's "side water depth"; comparing proposals, `retrieve_glossary` (on by default) does the same for the pairs judged. The topics count a meaning written out as its term too (`topic_glossary`, on by default), so one source's "SWD" and the other's "side water depth" make one topic. In a comparison the sources' subjects are matched and listed once, each source's values beside the other's: comparing revisions, where the findings pair their claims, else by name; comparing proposals, by name or other names (a judge's verdicts compare values, not items), and with the `match_subjects` setting the model matches what's left (the same item, the corresponding element such as each design's tower, or a state of it, kept apart). Subjects possibly one by weaker evidence are linked, never merged: "possibly the counterpart of …" with its level (plausible, two signals; possible, one) and its signals (names, properties or values in common, the judge's pairings, alignment's groupings, the model's answers), found by a search for either, a plausible link's claims sharing a topic. Tested by code (`link_tests`, on by default: properties siblings share don't set a pair apart; two designs' values that don't fit leave a link possible) and, comparing proposals, read by the model against a decoy (`link_read`, on by default: a request a link), each passing a held-out check first.

**How well each page was read**, in the report's Reading view: what the run recorded of its own reading, counted by file and page, each kind apart and with what it's counted of: requests that failed, weren't sent or came back incomplete; claims dropped because their quote isn't in their text; a picture's claims whose quote isn't in the text layer; image tiles that said their text was cut; tables read without their rules; claims the second pass doubted or read again otherwise. No score is made of them: they say where to look first. Each page's claims are a link away, and a run ends with one line of the totals.

**Summaries, each sentence citing its claims** (`summaries`; in analyses, sections', files' and the source's by default): a section's (a drawing set's sheets, page by page), a file's, a folder's, a subject's or a topic's, written by the model from the claims alone, each sentence citing the claims it rests on and checked against them by code: one stating a number its claims don't give is marked, never corrected. In a Summaries view, each citation a link to its claim, and in `export`, labelled as written by the model.

**Tensions** (`tensions`, off; analyses): a subject's claims hard to hold together on engineering grounds (low-alloy steel said to resist corrosion), at a level of suspicion (can't both hold, needs a reason, worth a look), with what would reconcile them looked for in the document: in a Suspects view, those not reconciled first. `reviewer_concerns` adds a reviewer's own things to watch for.

**One source on its own**, a file or a folder or zip of documents, is read and reported without comparing: `semantic-pdf-diff analyze spec/ --store spec` writes `spec/report.html`, every claim with where it was read, by topic and file, searched as a comparison's report is (its other names and vectors too). It takes `compare`'s options but those of comparing, and the same store, settings and answers cache: a source analyzed and then compared isn't asked of the model twice.

Either source can also be a folder or a zip archive. For revisions, supply the old version first:

```bash
semantic-pdf-diff compare old.pdf new.pdf --mode revisions --store revision-diff
semantic-pdf-diff compare team-a/ team-b.zip --store team-diff
```

For repeated work, declare **sources** in a store, each with a name, provenance metadata and one or more roots, and compare them by name (`compare` takes names and paths alike, a declared name first). Sources are rescanned on every run, so edited, added or deleted files are picked up:

```bash
semantic-pdf-diff source add team-a --store work --path team-a/ --path addendum.pdf --meta organization="Team A" --meta revision=C
semantic-pdf-diff source add team-b --store work --path team-b.zip
semantic-pdf-diff compare --store work team-a team-b
semantic-pdf-diff source export team-a --store work --output team-a.source.json --with-hashes
```

Model requests run in parallel (`concurrency`, default 4, adapting down when the server throttles) within optional time-of-day rate limits, e.g. in a `--config` file:

```json
{"concurrency": 6, "rate_limits": [{"days": "mon-fri", "hours": "08:00-18:00", "tokens_per_minute": 300000},
                                   {"tokens_per_minute": 500000}]}
```

Runs show progress bars on a terminal and heartbeat lines otherwise; `-q`, `-v`, `-vv` and `--log-file` control the detail.

Inspect and maintain a store with `show` (views as Markdown, CSV or JSON Lines), `report` (regenerate a report without model calls) and `gc` (delete content no source references any more); the answers cache with `cache` (show it; copy, remove or prune a project's answers by naming its stores):

```bash
semantic-pdf-diff show evidence_occurrences --store work --format csv
semantic-pdf-diff report --store work --out reports/latest
semantic-pdf-diff gc --store work --dry-run
semantic-pdf-diff cache copy ~/.cache/semantic-pdf-diff --store work   # this project's answers, from another cache
semantic-pdf-diff search 'hub height -tower' --store work               # the store's claims, as the report's search
semantic-pdf-diff export --store work                                   # its report as Markdown chunks for a RAG ingest
semantic-pdf-diff export --store work --since work/export --json        # only what changed since; chunks.json too
```

A revision is just another source (e.g. `team-a-rev1` vs `team-a-rev2`). Manifests (`source export` / `source import`, or `compare --manifest FILE` for a live link) carry source definitions between stores and users. Files of the types listed under Status are read; others are listed as skipped (`source show` says which, and why).

When requests fail, `semantic-pdf-diff debug --store work` says how often and why, in a few lines to read off a screen: the endpoint and models the last comparison used, the requests the store's runs asked by step (answered, failed, never answered), and the errors recorded, the most frequent first. It asks no model and prints nothing of the documents but what a server's error quotes.

Exit codes: `0` complete (uncertainty may remain); `2` incomplete coverage or processing failures; `3` paused for the budget, or for a rate limit until the time it says: run it again to resume; `1` fatal input or configuration error, a mistyped command or option included; `5` the endpoint failed: a check of `semantic-pdf-diff config test`, or 25 requests in a row (`stop_after_failures`), which pauses the run until it's run again; `130` interrupted by Ctrl+C: run it again to resume.

The `--store` folder (`diff-output` unless named) is an evidence **store** (`store.sqlite` plus rendered crops): rerunning into it reuses extracted evidence, and an interrupted run resumes where it stopped. Model answers are cached for every store (`$SEMANTIC_PDF_DIFF_CACHE`, else the user's: `$SEMANTIC_PDF_DIFF_USER/cache`, else `~/.cache/semantic-pdf-diff`), so what was asked once isn't paid for again. `$SEMANTIC_PDF_DIFF_USER` names a folder for what's the user's, in place of the home folder's (their settings and answers cache), for a machine that starts fresh each day. A store is bound to the model and extraction settings it was built with. A run with different ones reads again what they change, saying what differs and at most how much is asked again (preview with `--dry-run`); unchanged queries are answered from the cache. `--reset` starts a store over.

## Documentation

| Document | Contents |
| --- | --- |
| [How it works](docs/how-it-works.md) | Claims, the extraction and comparison pipeline, modes, code map |
| [Configuration](docs/configuration.md) | Endpoint, environment variables, settings, context budget, caching, exit codes |
| [Samples and testing](docs/samples-and-testing.md) | Running tests, the public sample corpus, recorded answers (replay fixtures), synthetic samples, local embedding server |
| [Limitations](docs/limitations.md) | What the current release can't do, and what to review before relying on it |
| [Validation](docs/VALIDATION.md) | What has and hasn't been verified |
| [Plans](docs/plans/README.md) | Design plans for the generalized tool, with status |
| [Decisions](docs/decisions/README.md) | Architecture decisions in force, each with its reasons and consequences |

## Tests

The tests cover the lab too: the evaluation and bench tooling, its own distribution in `lab/` (`semantic-pdf-diff[lab]` once published), which adds the `review` and `queries` commands.

```bash
pip install -e '.[dev]' -e lab
python -m unittest discover -s tests -v
```
