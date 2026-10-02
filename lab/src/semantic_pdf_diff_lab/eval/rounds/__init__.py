"""Query-improvement rounds: compare a variant's answers with the baseline's on the same inputs.

The unit of comparison is a page region of one kind (text, table, or visual: tiles, figures
and overviews) in one document. Each variant's claims for a unit come from its own replay
store, so variants that change chunking or tiling still compare page for page. Panel models
judge each unit twice, with the two claim sets in both orders (cancelling position bias).
A unit scores 1 when the variant wins, 0.5 for a tie, 0 when the baseline wins; results
get intervals (clustered by page region), overall and per stratum, and acceptance rules decide the round.
See docs/plans/query-improvement-2026-09-26.md.

Split by job (architecture clean-up, milestone 8): units, judging, spotcheck, decisions, measures. This
façade keeps `rounds.X` working for every caller.
"""

from .units import (  # noqa: F401
    BANDS, LEAD, MAX_BANDS, MAX_CLAIMS, PAGE_TEXT, UNIT_CLAIMS,
    _lead, _reader, _unit_of, add_context, band_region, build_batch,
    collect, lever_scope, pair_units, private_slices, rotations, shown,
    split_units)
from .judging import (  # noqa: F401
    _claim_marks, _claims_text, _grouped, _ident, _set_note, _whole_view,
    judge_pairs, pair_requests, pair_verdict)
from .spotcheck import (  # noqa: F401
    BETTER, SPOTCHECK_FORMAT, SURE, _judge_claim_marks, anchor, claim_shares,
    import_spotcheck, write_spotcheck)
from .decisions import (  # noqa: F401
    _t_quantile, decide, decide_scores, interval, lock_criteria, region,
    unit_scores, unsettled)
from .measures import (  # noqa: F401
    gains, mechanical, report)
# Names callers reach through rounds, though they live elsewhere.
from semantic_pdf_diff.regions import FAMILY, region_of  # noqa: F401
from ..rubrics import (CLAIM_MARKS, CLAIM_PROBLEMS, PAIR_PROBLEMS, PAIRWISE, RUBRICS, V1_OUTPUT,  # noqa: F401
                       pairwise_prompt, rubric as rubric_of)
