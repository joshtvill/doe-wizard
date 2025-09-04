"""Utilities Constants (MVP)
- Centralized thresholds and defaults used by tests and services.
"""

# Artifacts
ARTIFACTS_DIR = "artifacts"  # relative to repo root

# Profiling
PROF_SAMPLE_CAP = 50000  # rows
HIGH_CARD_FRAC = 0.50    # >50% unique => high cardinality
EXAMPLE_VALUES = 3       # show up to 3 unique examples

# Performance budgets (not enforced in tests; informational)
BUDGET_JOIN_PROFILE_SEC = 8
