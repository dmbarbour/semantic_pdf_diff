# Progress in stacked bars of fixed size

- **Status:** Active (2026-10-20)
- **The owner (2026-10-20):** "Progress bars: it's very awkward to have say 97/100 items followed by 98/115. I spend 90% of my time at 90% done, like a metaphor for software development. I'd prefer to have multiple stacked progress bars that are each stable size."
- **On testing (2026-10-20):** "How are you testing progress bar rendering in any case? Seems difficult, though IIUC libghostty has some support for headless terminal testing."

## Why

- **Each stage has one tqdm bar of requests,** and its total grows to the end:
  - Extraction asks a page at a time, as room is made (twice the workers pending at most), so the requests of pages not yet reached aren't counted.
  - Answers then add more: a partial tile refined in halves, an answer continued, a table's question asked again or reviewed.
- **Rendering isn't tested.** One test checks the bar's counters and that the stage's name reaches standard error. Nothing checks what a terminal shows.

## Design

- **A bar counts what's known when it appears,** and its total never changes:

  | Stage | Bars |
  |---|---|
  | extract | each file being read, in pages; each source of more than one file, in files |
  | situate | each PDF, in figures and sections |
  | compare | claims reranked, pairs judged, findings explained, names grouped, topics, claims embedded |

- **A page is done when every request for it is answered,** follow-ups included:
  - A request belongs to the page being read when it's asked.
  - A follow-up belongs to its parent's page: the dispatcher hands each answer's handler the page it was asked for.
  - A page is done once its handlers have run and none of its requests is waiting. Its bar never counts back.
  - A file's job finishing marks every page of it done, so a request counted wrongly can't leave a bar short.
- **The display:**
  - Bars are stacked, one line each, with a status line below: requests answered, waiting and failed; tokens a minute; cost; time left.
  - A finished file's bar leaves the screen; its source's bar stays.
  - Log lines print above the bars, which are drawn again below them.
  - Lines are cut to the terminal's width, so none wraps.
  - Without a terminal, heartbeat lines give the same numbers.
- **Drawn by the product itself,** in about a hundred lines, replacing tqdm, its only use. Bars come and go in any order, and log lines from worker threads print above them.
- **Tested in an emulated terminal:**
  - pyte, a terminal emulator written in Python and installed for tests only, reads what was written and gives the screen as rows of text.
  - Tests assert what a user would see: bars after log lines, after bars finish out of order, and at 40 columns.
  - One test runs the command on a pseudo-terminal, so it draws as it would for a user.
  - libghostty's terminal library (libghostty-vt) offers the same from C or Zig. pyte is a pip install, which suits a Python test suite.

## Milestones

1. **The renderer and its tests:** a block of bars and a status line, log lines above it, tested in pyte. tqdm is dropped.
2. **Extraction's bars:** pages per file, files per source, with requests attributed to pages.
3. **Situating's and comparing's bars.**
4. **Heartbeat lines** from the same numbers, for runs without a terminal.
