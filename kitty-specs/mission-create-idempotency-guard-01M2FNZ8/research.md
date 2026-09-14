# Research: mission-create idempotency guard

## Decision 1 — Duplicate key = same mission_slug AND mission_type (operator-decided)
Refuse only when a prior non-abandoned mission shares BOTH the slug and the type. A
`research` and a `software-dev` mission named alike are different work. Rationale: matches
the #4033 symptom (re-running the same command) with minimal false refusals.

## Decision 2 — Abandonment-aware auto-allow (operator-decided)
A prior same-key mission that is abandoned does NOT trigger the guard. "Abandoned" =
canceled, OR genesis / no lifecycle progress (no `status.events.jsonl` beyond scaffold /
spec never committed). Source of truth = the status event log (reduced), consistent with
the append-only status model. Rationale: the common "gave up and re-ran" path must not need
a flag. Fail closed (C-002): if abandonment can't be read, treat as live and refuse.

## Decision 3 — Escape hatch = explicit allow_duplicate (operator-decided)
`create_mission_core(allow_duplicate=False)` new param (mirrors existing opt-in flags);
`--allow-duplicate` on `agent mission create` and `/spec-kitty.specify`; factory passes it.
Not a blind same-slug refusal (the factory creates at volume) — the flag + abandonment
awareness together cover the legitimate cases.

## Seam grounding
`_create_mission_core_impl` (mission_creation.py) already funnels all callers and hosts the
early guards (git-repo, unborn-HEAD, detached-HEAD) before scaffold write — the guard slots
there. `_list_mission_scaffolds()` is the detection primitive.

## Supply-chain
No dependency added/removed.
