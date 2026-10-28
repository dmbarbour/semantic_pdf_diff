# The report: the text a claim came from, and views kept in the address

- **Status:** Planned (2026-10-28); [milestone 2](#2-every-view-kept-in-the-address) done the same day (the owner: "Please proceed with report bookmarks"). Milestone 1's [design questions](#design-questions) open.
- **The owner, 2026-10-28, from trials:**
  - "when a claim comes from text or the PDF text layer, we should include the relevant snippet of text in the report even when the image is dropped due to lower priority."
  - "bookmarking of views in the report, e.g. with `#anchor` but a javascript-driven anchor?"
- **Builds on:** [portable reports](portable-reports-2026-10-19.md) ([0033](../decisions/0033-self-contained-reports-and-their-search.md)).

## Why

### The text a claim came from

- **Every card shows the claim's quote,** with or without a crop (`report.py`, `Cards.card`).
  - The quote is the model's: at most 400 characters, checked against the file's text or the PDF's text layer (`quote_verified`).
  - The words around it aren't shown.
- **Claims read from text never have a crop.** Text tasks send no image (`tasks.text_task`), so their quote is all a card shows.
- **Claims read from images lose their crops to the budget.** These are claims from tiles, figures, overviews and tables read by rules.
  - A card whose crop was left out says only "Crop left out for the report's size budget (task): see Crops left out."
  - Nothing takes its place, even where the region has a text layer.
- **The store keeps no source text for a claim.**
  - A locator is coordinates only: a PDF box, a text file's lines, Word's paragraphs, a sheet's cells.
  - The text a task was sent (a text group's segments, an image region's text layer) is held in memory while it's read.
  - That text reaches the store only in the query log, which is for diagnosis and is never used to find answers.

### Views in the address

The page keeps two things in its address already: the view and the search (`#claims&q=...`, written by `history.replaceState`, read again on `hashchange`; `report.js`).

- **Not kept:**
  - the Findings view's relation, explanation kind and folding of equal wording
  - the Claims view's side, status, claim kind and counterparts
  - the pair of files, the topic and the search order
  - how far the list was paged
- **No card can be linked:** cards have no ids, and nothing scrolls to a claim or a finding.
- **Back doesn't step back:** nothing is pushed onto the history, so Back leaves the page.

## Milestones

### 1. A snippet of the source's text on each card

- **Taken at extraction, mechanically, from the text the task was sent.**
  - **A text claim:** the sentence or block holding its quote, about 600 characters at most.
  - **An image claim where the page has a text layer:** the text layer's lines under its mark, or the lines holding its quote where it has no mark.
  - **A table claim:** its row's cells as text, with the header.
- **Stored on the claim** and written again from cached answers when a store is read again, with no model calls.
- **Shown on every card that has one,** below the quote with the quote's words marked. Where a crop is left out, the snippet takes its place, and the note about the budget stays.
- **Counted in the page's size** before crops are chosen, since crops fill what's left.
  - Measured on TS 38.300's real pair (10.1 MB today) and the slices: the page's size with snippets, and the crops they push out.
- **Searched or not:** see [design question 2](#design-questions).
- **Tested:** the snippet of each kind of claim, on the replay fixtures. A card with its crop left out shows its snippet, checked in the headless browser as the page's other tests are.

### 2. Every view kept in the address

- **Every control's state in the address,** defaults left out so addresses stay short: `#claims&q=pump&side=1&topic=Hydraulics`.
- **A card's link:** `#claim=ID` or `#finding=ID` opens the view holding it, pages to it, scrolls to it and marks it.
  - Each card gets a link button that puts its address in the bar.
  - Claim ids are stable: the same store gives the same ids in every report written from it.
- **History:**
  - Filtering and typing replace the address, as now.
  - Changing view, following a card's link and "Claims like this" each add a step, so Back returns to the view before.
- **Split reports** (`--split`): a link names its part file, and the index's links carry the address on.
- **Tested** in the headless browser: an address opens its view and filters; a card's link scrolls to its card past the first hundred; Back returns.
- **Done 2026-10-28:**
  - **The address keeps,** defaults left out, in this order:
    - the view (`claims`)
    - each control: `relation`, `kind`, `side`, `status`, `read`, `file`, `order`
    - the boxes unticked (`fold=off`, `counterparts=off`)
    - the topic and the search
    - a linked item: `claim=ID` or `finding=A~B`, by the claims' ids
  - **Opening an address** sets every control from it; a value the report hasn't is left at its default.
  - **A linked item** is paged to, scrolled to and outlined. Where the address's filters leave it out, they and the search are cleared, and equal findings unfolded.
  - **A Link button** on each finding and on each claim in the Claims view, not on each card inside a finding: a finding's link holds both its claims.
  - **Steps Back returns from:** changing view, a Link, *Claims like this* and a coverage table's topic. Filters, topics and typing replace the address and drop a linked item.
  - **Split reports:** the index's links carry its address on to the part opened, and a part's link back to the index carries its own, without its linked item.
  - **Tested** in headless Chromium (`AddressInABrowser`): an address with a side, a kind and a search opens them; an edited address pages to the 150th claim; a Link gives `#finding=A-0~B-0`; Back twice returns through the findings view to the claim.

## Design questions

1. **Where the snippet comes from:**
   - **At extraction, stored with the claim** (proposed). The report needs only the store, as now.
   - **At report time, from the files on disk.** No store change, but it fails when a file has moved, and a report written elsewhere has none.
2. **Is the snippet searched?** Searching it finds a claim by words its quote left out, but it changes what the 17 real queries return.
   - **I'd leave it out of search at first,** and add it as a measured change against those queries.
3. **Shown on every card, or only in place of a crop left out?** Your words ask for it at least where the image is dropped.
   - **I'd show it on every card that has one,** folded to two lines on cards whose crop is shown.
