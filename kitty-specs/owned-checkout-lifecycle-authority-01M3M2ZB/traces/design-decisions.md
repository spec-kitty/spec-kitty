# Tracer: design-decisions

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-09-28 · claude-code/orchestrator · Seed (operator-locked 2026-09-28): Architecture B typed carrier over kwarg threading (A) and ambient resolvers (C, violates ADR 2026-08-12-1); create-time charter/template reads from owned checkout, authoring stays primary-only; stale primary copy -> owned wins + warning (DM 01M3M2ZXH4CGY20X1PZEC18F54); fold #4867; --owned-checkout on tasks status/setup-plan/context resolve; typed refusal for implement/action review (#5100 owns support); atomic finalize-tasks; amend ADR 2026-09-03-1.

2026-09-28 · claude-code/orchestrator · Post-spec squad (renata+paula) folded. Operator: keep owned coordination-topology next + harden (DM 01M3M4GM), validated flagless adoption with lane/coord worktrees excluded (DM 01M3M4GT), owned implement/review via next + move-task and typed OWNED_ACTION_UNSUPPORTED on action implement/review (DM 01M3M4GZ). Found existing OwnedMission carrier in core/owned_mission.py - seed for the validated fact.

2026-09-28 · claude-code/orchestrator · Plan decisions (operator): convert ALL 92 bare effective_root: Path params to OwnedCheckout in-mission, gate with EMPTY allowlist, no shrink-only ledger - rationale: half-implemented work and ratchets have been hurting us for weeks; pay it now. Carrier renamed to mission_runtime.OwnedCheckout (OwnedMission deleted, no alias) -> bulk_edit with occurrence map.

2026-09-28 · claude-code/orchestrator · Operator (2026-09-28 ~18:00): keep single PR; reviewer model tiering - opus reviews high-risk WPs (WP01,02,04-13,18,19), sonnet reviews the mechanical conversion sweep WP14-WP17 (implement stays sonnet). Rationale: throughput; ~12-20h projected wall clock at uniform opus review.

2026-09-28 · claude-code/orchestrator · WP02 approved with follow-ups assigned to WP08: (a) commit a test for the explicit-path WORKTREE_REGISTRY_UNAVAILABLE typed refusal (CLI level); (b) WORKTREE_REGISTRY_UNAVAILABLE is a pre-existing wire code outside OwnedRefusalCode - emit_owned_refusal must accept it (single named constant, like FEATURE_CONTEXT_UNRESOLVED/MISSION_CONTEXT_CONFLICT).
