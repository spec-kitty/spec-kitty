# Tracer: design-decisions

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-10-31 · planner-priti · D2: the lane-local meta.json source is consulted ONLY when no repository-root-derived policy matches that path, because _classify_worktree_state treats >1 candidate as UNKNOWN — a duplicate would flip a correct verdict.

2026-10-31 · planner-priti · D1/D6: reuse the same _policy_from_meta gate for the lane-local source (no second pattern grammar, no widened escape), and let the doctor surface follow the corrected is_blocking instead of adding remediation logic.

2026-10-31 · implementer-ivan · Kept the no-policy default (LEGACY_USER) instead of forcing UNKNOWN for a lane with no meta.json anywhere: UNKNOWN is the classifier's 'a policy matched but a check failed' verdict, and reusing it for 'no policy found' would blur two different states. Fail-closed is asserted as is_blocking + not-MANAGED_LANE.
