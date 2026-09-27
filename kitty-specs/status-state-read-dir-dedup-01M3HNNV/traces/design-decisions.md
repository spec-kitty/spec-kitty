# Design Decisions

> Capture the rationale that would otherwise evaporate.

**Prompting questions**
- What decision was made?
- What alternatives were considered?
- What was the rationale — why this option over the others?

---

## Entries

<!-- YYYY-MM-DD — Decision: [what]. Alternatives: [what else]. Rationale: [why this one]. -->
2026-09-27 — Decision: the single public resolver lives in `specify_cli/missions/_read_path_resolver.py` as `resolve_partition_read_dir(feature_dir, kind)`. Alternatives: (a) keep it in `post_merge/review_artifact_consistency.py` and import the private name from the CLI layer — rejected, a render-path authority should not live in a post-merge gate module; (b) new `specify_cli/status/` submodule — rejected, SR-2 (`test_status_module_boundary.py`) bans external submodule imports and a facade export means an `__init__.py` edit + version bump; (c) `core/paths.py` — rejected, already 1.2k lines and not the read-path owner. `_read_path_resolver` already owns handed-dir → read-dir resolution and already imports `resolve_canonical_root` + `MissionArtifactKind`.
2026-09-27 — Decision: keep the two thin adapters that tests import by name (`_resolve_lane_state_read_dir`, `_resolve_verdict_read_feature_dir(wp_path)`) as one-line delegations; delete `workflow_cores._resolve_status_state_read_dir` (no external importer). Rationale: dedup the logic, not churn test imports.
2026-09-27 — Decision: keep `workflow_cores._resolve_status_state_read_dir` as a one-line adapter instead of deleting it (WP02 prompt said delete). Alternatives: inline lazy imports at both call sites. Rationale: the pure-core module keeps its lazy import surface in one place and the single-authority gate names a stable entry point; no logic is duplicated.
2026-09-27 — Decision: implement and review ran as orchestrator-implemented + opus reviewer subagents (reviewer-renata) rather than sonnet implementer subagents; the whole diff is ~150 lines and role separation holds (reviewer ≠ implementer).
2026-09-27 — Follow-ups noted, not folded (C-005, pre-PR squad): the same foreign-anchor phantom exposure exists for the review-cycle artifact dir (`_review_cycle_wp_dir` callers), the TASKS_INDEX gate dir and `migration/runtime_state_cutover.py`; the write side (`coordination/status_transition.py`) was not re-verified under a phantom anchor.
