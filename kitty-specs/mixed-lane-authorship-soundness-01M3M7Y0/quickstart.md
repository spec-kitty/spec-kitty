# Quickstart — verifying mixed-lane authorship soundness

1. Build a mixed-lane mission with the new terminus builder (canceled WP02 adds `b.py`, approved WP01 owns `a.py`).
2. `spec-kitty consolidate --mission <slug>` (default squash) → expect exit ≠ 0 and `Reconciliation FAILED: file 'b.py' carries canceled WP02 content …`; target at its pre-consolidation SHA.
3. Same with `--strategy merge` → same verdict.
4. Supersede: WP01 rework rewrites `b.py` → consolidate exits 0.
5. Strip `lane_head` stamps from WP02's events → `Reconciliation refused (fail-closed): … WP02 … no commit attribution …`.
6. Inspect a stamp: `grep lane_head kitty-specs/<slug>/status.events.jsonl`.
