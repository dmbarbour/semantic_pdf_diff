"""What the lab's recording scripts share (code review 2026-10-08, E4: the scripts copied each other): the settings
every recording's queries are shaped with, and where the repository's spending ledger is.
"""

# The settings recordings share (scripts/record_runs.py, controlled.py, real_pairs.py): they shape the queries, so they
# decide what replays. One definition, so recordings can't drift apart.
BASE_SETTINGS = {"claims_per_request": 20, "output_tokens": 4000, "context_tokens": 262144, "image_tokens": 300}

LEDGER = "benchmarks/ledger.jsonl"  # the spending ledger, relative to the repository's root (ledger.spent: 0 without one)
