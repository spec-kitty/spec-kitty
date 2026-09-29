# Design decisions — implement-rework-resume

- 2026-09-29 — DM `resume_scope`: only the implementer of record resumes; the allowance lives in the shared lifecycle authority so `agent action implement`, `implement`, and orchestrator-api start-implementation inherit one rule (single canonical authority).
- 2026-09-29 — Reuse `status.review_roles.latest_implementer_actor`; do not add a fourth "who implemented" projection (unification stays with #5340).
- 2026-09-29 — Fail closed: a failure to read the implementer of record grants no allowance (mirrors move-task's R-03 behaviour).
- 2026-09-29 — `_ownership_role_allowance` keeps its own None/generic guard (it also protects `_reviewer_arm`, which needs "latest is usable" independent of the requester); only `_implementer_arm` uses `is_latest_implementer`. The rule itself (key equality + generic/None exclusion) now has one owner.
