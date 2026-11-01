---
affected_files: []
cycle_number: 1
mission_slug: scoped-leg-universe-prestep-01M6BV5D
reproduction_command:
reviewed_at: '2026-11-01T16:20:51Z'
reviewer_agent: reviewer-renata
wp_id: WP01
---

# WP01 review — changes requested

Reviewed by reviewer-renata (stronger tier) against the anti-pattern checklist and the WP prompt.

## F1 (low, correctness of the record) — the lazy import's stated reason is wrong

`scripts/ci/battery_partition_plugin.py:read_gates_file` claims the import is inside the function
"because battery_scope imports this module (lazily) for the partition, so a top-level import would
close the cycle". That is not true: `battery_scope` imports `battery_partition_plugin` only inside
`_part_files`, so a module-level `from scripts.ci.battery_scope import read_selected_gates` in the
plug-in creates no cycle (plug-in → battery_scope top level → nothing back).

A comment that states a false reason is worse than no comment: the next reader will preserve an
unnecessary lazy import (and its per-call import cost on every scoped leg) because the "cycle"
looks real.

**Fix**: import `read_selected_gates` at module top level and drop the cycle claim; if the lazy
import is kept for another reason, state that reason instead.

## Everything else: PASS

1. Dead code — PASS. `write_selected_gates` is called by `output_lines` (production); `read_selected_gates` is called by the plug-in's `read_gates_file` (production).
2. Synthetic-fixture test — PASS. The new tests call the real writer (`output_lines`) and the real readers; deleting either implementation reds them (verified: the round-trip test failed with `AttributeError` before T001 landed).
3. Silent empty return — PASS. No new `except …: return None/[]`.
4. FR coverage — PASS (FR-005: the round-trip and both-readers tests; C-001: the unchanged unset/missing cases still pass).
5. Frozen surface — PASS. No frozen file touched; the plug-in's documented `SK_BATTERY_GATES_FILE` contract is intact.
6. Locked decision — PASS. The collection is untouched (C-002); nothing narrowed.
7. Shared-file ownership — PASS. The diff is exactly this lane's `write_scope`.
8. Production fragility — PASS. The one new `raise` is the plug-in's pre-existing `pytest.UsageError` for a missing file, unchanged.
