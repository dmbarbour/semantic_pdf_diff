"""What `semantic-pdf-diff config` says about each setting (decision 0032): the
group it's listed in, a line on what it does, more for `config help`, and an example where one helps. The owner,
2026-10-20: "Definitely will need navigation of settings and adequate help for each." tests/test_configuration.py
checks every setting has its entry.

Groups, as `config show GROUP` names them: endpoint, budget, sources, reading, comparing, report, and levers (the
lever settings, which `config show --all` adds). `basic` marks the settings `config show` lists without a group.
"""
from dataclasses import dataclass

@dataclass(frozen=True)
class Help:
    group: str
    about: str
    more: str = ""
    example: str = ""
    basic: bool = False

GROUPS = {"endpoint": "the model and how requests travel to it",
          "budget": "when a run stops asking",
          "sources": "what is scanned, and the archives' safety limits",
          "reading": "how documents are read into claims",
          "comparing": "how two sources' claims are paired and judged",
          "report": "what report.html holds",
          "levers": "the query levers: each a way of asking, measured before it became a default or not"}

_L = "levers"  # every lever setting's group

HELP = {
    # --- endpoint
    "model": Help("endpoint", "the vision model's name at the endpoint ($OPENAI_BASE_URL); none by default",
                  "A run needs one: `config models vision` lists the endpoint's models reading images. Every answer "
                  "depends on it: a store read with one model reads again with another.",
                  "google/gemma-4-31B-it", basic=True),
    "base_url": Help("endpoint", "the OpenAI-compatible endpoint, with /v1 where it needs it",
                     "Set by $OPENAI_BASE_URL, else the user's settings (`config set --user base_url URL`); "
                     "--base-url beats both for one run. Never kept in a store: the endpoint is the user's.",
                     "https://api.deepinfra.com/v1/openai"),
    "context_tokens": Help("endpoint", "the model's context window, in tokens: requests are sized to fit",
                           "Measured on first use where the endpoint lists the model's (`config show` marks it "
                           "measured); otherwise set it to the model's: 262144 for gemma-4.", "262144", basic=True),
    "output_tokens": Help("endpoint", "tokens reserved for each answer",
                          "About 150 a claim: raise it with claims_per_request."),
    "image_tokens": Help("endpoint", "an image's cost in tokens, an upper bound for sizing requests",
                         "Measured on first use, an image image_side square, a tenth added; a value set below the "
                         "measure is warned of. Provider-specific: gemma-4 at DeepInfra spends 258 an image."),
    "safety_tokens": Help("endpoint", "tokens kept spare in every request, against estimates running short"),
    "max_token_field": Help("endpoint", "the request field naming the answer's length",
                            "max_completion_tokens for providers that refuse max_tokens."),
    "response_format": Help("endpoint", "ask for JSON by the endpoint's response_format, or not",
                            "none: the prompt asks for JSON; json_object or json_schema where the endpoint supports "
                            "them."),
    "seed": Help("endpoint", "a sampling seed sent with each request, where the endpoint honours one"),
    "stream": Help("endpoint", "receive answers as they're written",
                   "Streamed, the timeout counts between chunks, so a long answer isn't cut off."),
    "retries": Help("endpoint", "attempts after a failed request (0 to 5)"),
    "stop_after_failures": Help("endpoint", "requests failing in a row at one URL before a run stops sending",
                                "Failing: no answer came back (an HTTP error, a lost connection, a timeout); an answer "
                                "cut short or not the JSON asked doesn't count. The run pauses, as the cost cap pauses "
                                "it, and exits 5: the model's name, the key or the endpoint is likely wrong (`config "
                                "test` checks them). Running again resumes.",
                                "25"),
    "timeout": Help("endpoint", "seconds without data before a request gives up",
                    "Between chunks when streaming: a slow answer isn't cut off whole, and still billed.", "300",
                    basic=True),
    "concurrency": Help("endpoint", "requests in flight at most (adaptive below it)",
                        "A slow model needs many at once: 32 for gemma-4 at DeepInfra. A run's own: two runs at once "
                        "send twice as many. The status shows those in flight, and those queued behind them.", "32",
                        basic=True),
    "rate_limits": Help("endpoint", "throughput ceilings by day and hour",
                        "A JSON list of rules: days, hours, tokens_per_minute, requests_per_minute; the first that "
                        "matches applies.", '[{"hours": "08:00-18:00", "tokens_per_minute": 200000}]'),
    "heartbeat_seconds": Help("endpoint", "seconds between progress lines when the output isn't a terminal"),
    # --- budget
    "max_cost": Help("budget", "stop asking once the provider-reported cost reaches this many dollars",
                     "The run pauses: running it again resumes. A response without a reported cost counts nothing.",
                     "2", basic=True),
    "max_calls": Help("budget", "the most requests a run sends, retries not counted",
                      "A safety stop against runaway runs, not a budget.", basic=True),
    # --- sources
    "rescan": Help("sources", "rescan a source's folders on every run (auto), or only on `source update` (manual)"),
    "max_zip_depth": Help("sources", "archives within archives followed, at most"),
    "max_source_bytes": Help("sources", "a source's size at most, in bytes; anything past it is reported"),
    "zip_ratio_limit": Help("sources", "an archive member's compression ratio at most (a zip bomb's sign)"),
    "zip_ratio_min_bytes": Help("sources", "the size past which zip_ratio_limit applies"),
    # --- reading
    "vision": Help("reading", "read pictures of pages, tables, charts and drawings",
                   "off: text only, the report saying what went unread.", basic=True),
    "situate": Help("reading", "write each figure's and section's \"about\" statements, which place claims",
                    basic=True),
    "claims_per_request": Help("reading", "claims asked for in one extraction request",
                               "Raise with output_tokens; a task at the limit is asked for the rest."),
    "text_bytes": Help("reading", "a text task's text, in bytes at most"),
    "image_side": Help("reading", "an image's longer side, in pixels, as it's sent"),
    "tile_points": Help("reading", "a page tile's side, in points"),
    "refinement_depth": Help("reading", "how many times a tile answered incomplete is read again in parts (0-3)"),
    "least_half": Help("reading", "a refined tile's half holds at least this share of what the tile holds"),
    "section_depth": Help("reading", "sections come from a PDF's outline down to this depth"),
    "section_pages": Help("reading", "a section's pages without an outline"),
    # --- comparing
    "mode": Help("comparing", "proposals: two designs side by side; revisions: an earlier and a later version",
                 "In revisions mode the first source is the earlier one, and differences are named as changes.",
                 "revisions", basic=True),
    "top_k": Help("comparing", "candidates of the other source each claim is compared with", basic=True),
    "min_score": Help("comparing", "the least word-overlap score a candidate pair needs"),
    "max_pairs": Help("comparing", "candidate pairs the judge takes at most, best first",
                      "The report says how many it left unjudged.", "5000", basic=True),
    "aliases": Help("comparing", "names taken as one for pairing claims, as a JSON object",
                    "Each alias read as its canonical name when claims are paired.", '{"CHW": "chilled water"}'),
    "rerank_model": Help("comparing", "proposals mode: a reranker scoring candidate pairs before the judge",
                         "Off unless named. Pairs below rerank_threshold aren't judged; the rest are, best first. It's "
                         "asked at the chat endpoint's /rerank unless rerank_api or rerank_url says otherwise.",
                         "Qwen/Qwen3-Reranker-8B", basic=True),
    "rerank_api": Help("comparing", "the reranker's API: rerank, deepinfra or tei",
                       "rerank: the /rerank most servers take (vLLM, llama.cpp, Infinity, LiteLLM; Cohere's and "
                       "Jina's), told the task where the server passes it on (vLLM, to Qwen3-Reranker). deepinfra: "
                       "DeepInfra's inference API, told the task (DeepInfra serves no /rerank). tei: Hugging Face's "
                       "text-embeddings-inference, told nothing.", "deepinfra"),
    "rerank_url": Help("comparing", "where the reranker is asked ({model} filled in)",
                       "Unset: beside the chat endpoint, on its host: its /rerank, or with rerank_api deepinfra "
                       "DeepInfra's inference API (.../v1/inference/MODEL). A reranker served elsewhere is sent "
                       "OPENAI_API_KEY too.", "http://localhost:8080/rerank"),
    "rerank_threshold": Help("comparing", "the least reranker score a pair is judged with, in hundredths (1-10)",
                             "3 is 0.03. Measured at 2, 5 and 10: no related finding lost.", "5", basic=True),
    "search_names": Help("comparing", "the model groups the names the documents give one thing, so a search for one "
                         "finds the others' claims too", "In a request after the comparison (a topic's, for a large "
                         "one): \"rated output\" finds \"nominal power\". About $0.004 a comparison of 1,400 to "
                         "3,100 claims; measured in docs/plans/search-2026-10-20.md.", basic=True),
    "embed_model": Help("comparing", "an embedding model the claims are embedded with after the comparison, for a "
                        "search by meaning (none: not embedded)",
                        "near:ID finds the claims most like a claim in meaning, and like:ID blends meaning in (the "
                        "page and the command line); meaning:\"...\" from the command line. Each distinct claim "
                        "sentence once, 64 to a request, on the chat endpoint's /embeddings unless embed_url says "
                        "otherwise. Measured best: Qwen3-Embedding-8B, with embed_dimensions 256.",
                        "Qwen/Qwen3-Embedding-8B"),
    "embed_url": Help("endpoint", "where the embedding model is asked ({model} filled in); none: the chat endpoint's "
                      "/embeddings", "A model served elsewhere is sent OPENAI_API_KEY too."),
    "embed_dimensions": Help("comparing", "each claim's vector's size, asked of the embedding model and kept in the "
                             "report (unset: none asked, the model's own)", "A model trained to be cut "
                             "(Qwen3-Embedding) answers any; most can't be, and some servers refuse the size for them "
                             "(a LiteLLM proxy; then it's asked again without it). A byte a dimension a claim in the "
                             "report.", "256"),
    "glossary": Help("comparing", "each source's abbreviations, defined terms, symbols and conventions, read for the "
                     "index and the search", "From the parts headed Abbreviations, Definitions, Symbols, Legend and "
                     "the like (the model, a request a part of about 100 lines; a text file's tables as they are), "
                     "and from prose (\"net positive suction head (NPSH)\"). off: none read.", basic=True),
    "second_pass": Help(_L, "analyses: each subject's claims read together, a request a subject; context added, "
                            "relations, suspicions and likely gaps noted beside the claims, never changing them"),
    "topic_glossary": Help(_L, "with glossary: the topics count a meaning written out as its term, one word"),
    "topic_names": Help("comparing", "the model chooses the report's topics and names them, in one request",
                        "off: topics named by their words.", basic=True),
    # --- report
    "answers_cache": Help("endpoint", "where this store's answers are kept: an answers cache's folder (or its .sqlite "
                          "file); a relative path is the store's folder's",
                          "Set by the store's first run to the cache it used ($SEMANTIC_PDF_DIFF_CACHE's, else the "
                          "user's). Later runs use it whatever the environment says, and refuse when "
                          "SEMANTIC_PDF_DIFF_CACHE names another, so a project's answers stay in its cache. A path "
                          "given here is taken from the current folder. A store's only: the user's cache is "
                          "$SEMANTIC_PDF_DIFF_CACHE's, else ~/.cache/semantic-pdf-diff.", "../answers", basic=True),
    "report_budget": Help("report", "report.html's size at most: its crops embedded in order of value until then",
                          "A size: 20MB, 500KB; 0 embeds no crop. `report --dry-run` says what a budget leaves out.",
                          "40MB", basic=True),
    "split": Help("report", "a report file a pair of files, and an index, for comparisons too large for one file",
                  basic=True),
    # --- levers: instructions
    "extract_prompt": Help(_L, "replaces the extraction instructions with this text"),
    "extract_rules": Help(_L, "rules appended to the extraction instructions, as a JSON list",
                          example='["Read values with their units."]'),
    "visual_rules": Help(_L, "rules appended for image tasks only (tiles, figures, overviews), as a JSON list"),
    "split_conditions": Help(_L, "the reader keeps a claim's scope (conditions) apart from how its value is read "
                                 "(frame)"),
    "read_holders": Help(_L, "the reader names who holds a claim the source reports as another's, and their attitude"),
    "hedge_rule": Help(_L, "the reader is told a hedge on a value is its uncertainty"),
    "worked_examples": Help(_L, "worked examples after the extraction instructions"),
    "column_conditions": Help(_L, "table rules are told a condition some columns have isn't every column's"),
    "conditions_by_column": Help(_L, "table rules' templates give conditions (and frames) column by column"),
    "images_first": Help(_L, "a request's images before its text, as Google's guidance for gemma-4 has them"),
    "complete_by_image": Help(_L, "an image task's completeness is the image's, not its text layer's"),
    # --- levers: context
    "context_before": Help(_L, "characters of the text before a text task's, sent as context"),
    "context_after": Help(_L, "characters of the text after a text task's, sent as context"),
    "leave_furniture": Help(_L, "running headers, footers and page numbers left out of context and text layers"),
    "table_context": Help(_L, "characters of text above a table (lead-in, caption) sent with it"),
    "stem_context": Help(_L, "text and table tasks are told the numbered items and headings they're under"),
    "references": Help(_L, "abbreviations defined elsewhere, and cited figures' captions, sent as context"),
    "reader_glossary": Help(_L, "with glossary: each request reading claims is shown the terms its words use, as its "
                                "document defines them"),
    "tile_locator": Help(_L, "with each tile, a page thumbnail outlining where it sits"),
    "visual_text_layer": Help(_L, "characters of a region's PDF text sent with its image"),
    "table_cuts": Help(_L, "an image region cutting a table is sent the table's header and the rows it touches"),
    "text_cuts": Help(_L, "where a long text is cut: where the bytes run out, or at a sentence's end"),
    "text_spans": Help(_L, "a text task's blocks: a page's up to the byte budget, or one section's"),
    "repeated_text": Help(_L, "a page's text tasks leave out a block repeated in the same place on earlier pages"),
    "lone_rows": Help(_L, "a one-row table's row sent once, not also as its header"),
    "leave_text": Help(_L, "a page's text tasks leave out the text other readers read: tables, and figures too"),
    "dedupe_repeated": Help(_L, "a table row repeated exactly on three pages or more is read once"),
    # --- levers: segmentation and inclusion
    "decoration": Help(_L, "decoration (rules, margin bars, frames) set aside when a tile's graphics are counted"),
    "tiling": Help(_L, "how a report page is cut: full-width bands at whitespace, or a grid"),
    "band_width": Help(_L, "pages up to this many tiles wide get bands"),
    "tile_cut": Help(_L, "how a page not cut into bands is cut: grid, snapped grid, or XY-cut blocks"),
    "tile_choice": Help(_L, "which cut a page gets: off (the default cut), measured, or the model's choice"),
    "grow_tiles": Help(_L, "grid tiles grow to include every text line they cut"),
    "sheet_details": Help(_L, "drawing sheets cut into their details, titled from the sheet"),
    "skip_empty": Help(_L, "tiles with no text, drawing or image aren't sent"),
    "skip_text_only": Help(_L, "tiles holding text and no graphic aren't sent (the text tasks read them): everywhere "
                                   "(true), but on drawing sheets (except_sheets), or only on pages too wide for "
                                   "bands, sent after all where the page's text gives no claim (wide_pages)"),
    "region_labels": Help(_L, "the model labels a page's tiles; text, decoration and blank ones aren't sent"),
    "another_tiling": Help(_L, "a partial tile is read again under the page's next cut, rather than in halves"),
    "refine_figures": Help(_L, "a partial tile mostly one figure is looked at again whole, rather than in halves"),
    "halve_parts": Help(_L, "a refined tile's halves are cut around the figures it holds"),
    "render_area": Help(_L, "a long region rendered to a square's pixel area, not its longer side to image_side"),
    "figure_tasks": Help(_L, "each detected figure is read whole, besides the tiles"),
    "table_filter": Help(_L, "detected tables that are charts, frames or paragraphs are dropped"),
    "skip_sheet_tables": Help(_L, "a drawing sheet isn't searched for tables"),
    "continuations": Help(_L, "times an image task at the claim limit is asked for the rest"),
    # --- levers: tables
    "table_rules": Help(_L, "tables of more body rows than this are read by rules the model writes (0: every "
                            "table; none: row by row)"),
    "table_review": Help(_L, "times a table's rules, applied, are shown to the model for review (0: never)"),
    "table_structure": Help(_L, "a PDF table with suspect lines is asked how its lines group into rows"),
    # --- levers: after the answers
    "quote_match": Help(_L, "how quotes are checked against the text: exact, fragments, or excerpts"),
    "positions": Help(_L, "a numbered item's label is its claim's position, not part of its conditions"),
    "records": Help(_L, "lists, notes and legends kept once as context records claims reference"),
    "sheet_records": Help(_L, "a drawing sheet's title block kept as a record its claims reference"),
    "table_holders": Help(_L, "a table's holder column (Company, Source) holds every claim from its row"),
    "carried_holders": Help(_L, "a holder column's blank cell takes the name above it"),
    "view_attitudes": Help(_L, "a holder's yes or no is their view of the proposition"),
    "view_rows": Help(_L, "a holder's yes or no in a table is read without the model"),
    "hedges_apart": Help(_L, "a hedge read into a claim's conditions is moved to its uncertainty"),
    "reconcile": Help(_L, "readings of one fact by different tasks are merged into one claim"),
    # --- levers: comparing
    "align": Help(_L, "revisions: items are matched across the revisions before any value is judged"),
    "align_printed": Help(_L, "with align: a claim's name as printed weighed beside its attribute"),
    "align_hedges": Help(_L, "with align: a value differing only by a hedge or a status is reported without a model"),
    "align_glossary": Help(_L, "with align and glossary: a meaning written out weighed as its term"),
    "retrieve_glossary": Help(_L, "with glossary: retrieval takes a meaning written out as its term, so one source's "
                                  "abbreviation meets the other's words among the candidate pairs"),
    "verify_visuals": Help(_L, "a claim's crop is sent with it when it's judged"),
    "explain_differences": Help(_L, "revisions: each different or uncertain finding is explained by kind"),
    "explain_context": Help(_L, "the explainer is shown each claim's list position and name as printed"),
    "explain_glossary": Help(_L, "with glossary: the explainer is shown the terms each claim uses, as its document "
                                 "defines them"),
    "editorial": Help(_L, "a claim equivalent at another place in its list is reported as renumbered"),
    "record_changes": Help(_L, "a context record restated between revisions is reported once, with the claims it "
                               "reaches"),
    "judge_context": Help(_L, "the judge is shown each claim's context records, and rules on subject, scope and frame"),
    "judge_glossary": Help(_L, "with glossary: the judge is shown the terms each claim uses, as its document defines "
                               "them"),
}
