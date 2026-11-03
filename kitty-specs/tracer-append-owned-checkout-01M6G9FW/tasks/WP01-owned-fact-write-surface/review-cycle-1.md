# WP01 review — cycle 1 (reviewer-renata)

Reviewed: `d18c4f1d58..HEAD` for `src/specify_cli/cli/commands/agent/tracer_append.py`,
`src/specify_cli/retrospective/tracer_writer.py` and the new test module.

## Findings

| ID | Severity | Finding | Action |
| --- | --- | --- | --- |
| F1 | MEDIUM | `ProtectionPolicy.resolve_for_owned(owned, mission)` passed the CLI handle as the mission slug. `resolve_for_owned` only applies the mission scope when that slug equals `owned.mission_dir.name`, so a call spelled with a mid8 or a mission id would silently skip the Mission's own `commit_to_target` and keep its branch protected. The write's mission is always the fact's own mission, and the method defaults to it. | Fixed: call `resolve_for_owned(owned)` with no slug, with the reason recorded at the call site. |
| F2 | LOW | The new module pinned the repository-root refusal but not the "checkout does not own the Mission" refusal, which FR-004 lists separately. | Fixed: `test_foreign_checkout_claim_refuses_before_writing` pins `OWNERSHIP_FOREIGN` and asserts the writer is never reached and neither checkout gains a `traces/` file. |
| F3 | INFO | The primary owned-routing test asserted `ok` and the on-disk outcome but not the write branch the seam reports. | Fixed: also asserts `payload["commit_ref"] == BRANCH`. |
| F4 | INFO | Verified the owned refusal fires before `append_tracer_finding`: the writer spy raises if reached, and the case passes. Verified the non-owned path still passes `repo_root=R` and `owned=None`. | No change. |
| F5 | INFO | Verified the writer's existing fail-closed arms (`CoordinationWorktreeUnmaterialized`, non-UTF-8 traces file, blank actor) are untouched and their payload shapes are still covered by `tests/mission_runtime/test_coord_read_seam_callers.py` and the retrospective suite. | No change. |

## Verification after the fixes

```
uv run pytest tests/specify_cli/cli/commands/agent/test_tracer_append_owned_checkout_7081.py -q   # 6 passed
uv run pytest tests/specify_cli/cli/commands/agent/test_tracer_append_outcome.py \
              tests/retrospective tests/mission_runtime/test_coord_read_seam_callers.py -q       # 571 passed, 5 skipped
uv run pytest tests/architectural/test_owned_checkout_single_authority.py \
              tests/specify_cli/cli/commands/test_owned_refusal_format_unified.py -q              # 41 passed
uv run ruff check … / ruff format --check … / uv run mypy …                                        # clean
```

Gate status: single-authority allowlist still empty (no new caller of
`resolve_owned_mission` / `adopt_owned_checkout`). No gate was weakened, skipped or xfailed.

## Verdict

APPROVE.
