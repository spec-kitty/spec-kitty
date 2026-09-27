# Contract — render-side feedback surfacing (WP02, #5024)

## 1. Visible fall-through warning (FR-006, SC-003)

`implement_try_render_fix_mode_prompt` (`workflow_executor.py:1084`), `except` at `:1161`:

- MUST surface the failure on the operator-visible surface the implementer reads (e.g.
  `console.print("[bold red]⚠️ …[/bold red]")`), naming the WP and the cause — NOT a log-only
  `logger.warning`.
- MAY still `return None` (the full prompt is a legitimate, now-announced fallback); MUST NOT silently
  substitute a feedback-less prompt with no visible signal.
- The `except` block retains concrete recovery logic (no effect-free handler — Sonar).

## 2. `build_implement_prompt_lines` test (FR-005 positive control)

`build_implement_prompt_lines` (`workflow_executor.py:1302`) currently has NO test. WP02 adds
`tests/agent/test_build_implement_prompt_lines.py` covering:
- feedback-present → feedback text appears in the produced lines;
- feedback-absent → no crash, no spurious feedback.

## 3. Event-log partition re-route (FR-007, SC-004 — F4 independent-red)

The event-log read behind the render/feedback resolution MUST resolve through the `STATUS_STATE` placement
seam, not the `WORK_PACKAGE_TASK` `feature_dir`:

- `implement_resolve_feedback_and_gate` (`workflow_executor.py:667`) currently passes a
  `read_dir(WORK_PACKAGE_TASK)` dir to `resolve_review_feedback_context`.
- The event-log-reading helpers `latest_review_feedback_reference` / `has_prior_rejection`
  (`workflow_cores.py:311,394`) MUST read events from `placement_seam(repo_root, mission_slug).read_dir(STATUS_STATE)`
  (mirroring the write-side `_resolve_verdict_read_feature_dir`, `tasks_verdict_persistence.py:694`).
- The review-cycle ARTIFACT read stays on `WORK_PACKAGE_TASK` (`_review_cycle_wp_dir`) — unchanged.
- Single-branch: PRIMARY == COORD == `repo_root`, so the re-route is a no-op (no single-branch regression).

## Consumed FROZEN dependencies (NFR-001 — do NOT modify)

- `is_review_rejection_edge` — see `is-review-rejection-edge.md`.
- Grammar in `review/cycle.py`: `is_non_resolvable_review_ref`, `is_synthetic_review_ref`,
  `SYNTHETIC_REVIEW_REF_PREFIXES`, `synthetic_review_ref`.
- `ReviewCycleArtifact` (`review/artifacts.py`) and `generate_fix_prompt` (`review/fix_prompt.py`).
