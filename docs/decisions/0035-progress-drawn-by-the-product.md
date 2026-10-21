# 0035. Progress is drawn by the product, in bars of fixed total

- **Status:** Accepted (2026-10-21)
- **Source:** [progress in stacked bars of fixed size](../plans/progress-display-2026-10-20.md), milestones 1 to 7; the [trials review](../plans/README.md#retired), findings 3 and 4

## Context

Each stage had one tqdm bar of requests, and its total grew to the end. Extraction asks a page at a time, as room is made, so the requests of pages not yet reached weren't counted; answers then added more (a partial tile refined in halves, an answer continued, a table's question asked again or reviewed). One test checked the bar's counters; nothing checked what a terminal showed.

What the owner said, as the plan records it:
- **2026-10-08** (the trials review): "What we need is something closer to pinned progress bars at the bottom with a rolling log above or similar." And: "It would be better to develop some clear concept of what needs processing and base it on that, and use multiple progress bars for hierarchical subtasks that open into more tasks."
- **2026-10-20:** "Progress bars: it's very awkward to have say 97/100 items followed by 98/115. I spend 90% of my time at 90% done, like a metaphor for software development. I'd prefer to have multiple stacked progress bars that are each stable size." On testing: "How are you testing progress bar rendering in any case? Seems difficult, though IIUC libghostty has some support for headless terminal testing."
- **2026-10-21,** on the status: "it would be convenient if we also mention how many were answered from cache, e.g. 1234 answered (1179 from cache) or similar." On Ctrl+C: "ctrl+c just leaves a mess of exception info in the terminal. Please capture it and exit cleanly, with a short message about how to resume." On concurrency: "Is the `concurrency` setting ignored? I regularly seem to have `"7 waiting"` when I configure concurrency at 2, for example. My in-house setup has only a few servers for gemma-4, and I need to not be taking all of them."

## Decision

- **A bar counts what's known when it appears, and its total never changes:**
  - extract: each file's pages; each source of more than one file, in files;
  - situate: each PDF's figures, figures cited and sections, and the PDFs when there are several;
  - compare: claims reranked, pairs judged, findings explained, sentences embedded. Requests no bar counts (the other names') are counted in the status.
- **A page is done when every request for it is answered,** follow-ups included:
  - A request belongs to the page being read when it's asked; the dispatcher runs each answer's handler within the page it was asked for, so a follow-up belongs to its parent's page.
  - A bar never counts back. A file's job finishing marks every page of it done.
- **The display:**
  - Bars stacked, one line each, with a status line below; a finished file's bar leaves the screen, its source's stays.
  - Log lines print above the bars, and anything else written to standard output or error while they're drawn too. PyMuPDF's own messages go to the log.
  - Lines are cut to the terminal's width. Without a terminal, heartbeat lines (every `heartbeat_seconds`, 30) give the same numbers.
- **The status's counts:** "1,234 answered (1,179 from cache), 2 in flight, 5 queued", then failed, tokens a minute, cost and time left; on two lines where one doesn't fit, kept so for the stage.
  - **From cache:** the dispatcher says, as each answer's handler runs, whether the cache (a fixture's, in a replay) gave it. Not the client's count of hits at lookup, which ran ahead of the answers handled.
  - **In flight:** sent through the client's gate and not yet answered, never more than `concurrency`. **Queued:** asked and not yet sent; the dispatcher holds up to twice `concurrency` (at least 4). Until 2026-10-21 both were "waiting".
- **Drawn by the product's own renderer** (progress.py), replacing tqdm, its only use.
  - rich's live display and log handler, proposed by the trials review (finding 3), was declined: stacked lines need little of it, and the product keeps two dependencies (PyMuPDF and pydantic).
- **Tested in an emulated terminal:**
  - pyte, a terminal emulator written in Python (LGPL-3.0), is a dependency of the tests only (the `dev` extra). It gives the screen as rows of text, so tests assert what a user would see: bars after log lines, after bars finish out of order, at 40 columns.
  - One test runs the command on a pseudo-terminal, so it draws as it would for a user.
  - libghostty's terminal library offers the same from C or Zig; pyte is a pip install, which suits a Python test suite.
- **Ctrl+C ends a run at once:** the bars erased, "Interrupted: rerun the same command to resume; finished work is kept.", exit 130.
  - The command line's own process (the console script, `python -m`) catches KeyboardInterrupt once the answers cache and the store have closed, then ends without waiting for the worker threads.
  - Each answer is committed as it comes, so only the requests in flight are asked again. A second Ctrl+C ends the process where it is.
  - A caller of `cli.main` with its own arguments (tests, scripts) gets KeyboardInterrupt as Python raises it.

## Consequences

- **On the recorded slices** (turbines, drawings, rules), every page was counted by its own answers before its file's job ended, and each stage's requests asked and answered matched. With answers handled in a shuffled order (`SEMANTIC_PDF_DIFF_ANSWER_ORDER`), the turbines' 12-page files rose a page or so each tenth of the 149 requests.
- **The pseudo-terminal test found** PyMuPDF's notice ("Consider using the pymupdf_layout package…") printed while the bars were drawn, leaving their copy on the screen; hence everything written while they're drawn goes above them.
- **Ctrl+C before:** a traceback, the bars drawn again below it, and an exit waiting for the requests in flight (17 s against a stub answering in 20 s; up to the timeout, 600 s, against a model). Tested in its own process, on a pseudo-terminal and through a pipe, then resumed: the requests sent on resume matched those answered less those from the cache, and the claims matched a run never interrupted.
- **`concurrency` was never passed at the endpoint:** a stub counting its open requests saw at most 1, 2 and 4 at `concurrency` 1, 2 and 4, while "waiting" reached 1, 5 and 9.
- **`concurrency` is a run's own:** two runs at once send twice as many, and its help says so. Whether several runs should share one cap is an open question to the owner (the plan's closing).
- The topics' one request is counted in no bar and not in the status.
- If *Interactive views* (a tentative row in the [plans index](../plans/README.md)) brings Textual, rich comes with it, and the bars can move onto it.
