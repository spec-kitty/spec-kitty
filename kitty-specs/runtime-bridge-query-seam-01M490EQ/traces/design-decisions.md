# Design decisions — runtime-bridge-query-seam-01M490EQ

Decisions already made in the spec (Decision Moments, resolved from the operator brief):
- Scope: query + answer + the shared mapping helpers only; #2562 stays out.
- Public names stay plain re-exports (same objects); no delegates.
- False-green policy: drop unused bridge imports, review remaining shared-name patches by call path, repoint with proof the fake ran.

- 2026-10-06 · claude · Identity seam is a leaf (imports nothing in `runtime.next`) and the io seam imports it, so `_wrap_with_decision_git_log` (which calls `_io_seam.resolve_commit_target`) cannot move into identity without an io ↔ identity cycle. Placement is decided in plan.md (D-2).
- 2026-10-06 · claude · New modules are NOT added to the pyproject mypy `ignore_errors` list that covers `runtime.next.runtime_bridge` (debt; CLAUDE.md requires new code to pass mypy). The verbatim move therefore tightens bare `dict` annotations to `dict[str, Any]` in the mapping module. This is annotation-only, with no runtime effect.
- 2026-10-06 · claude · io's deferred `DecisionGitLogUnavailable` import is repointed at the decision-log module rather than moving `resolve_commit_target` (squad A-3; io owns it and `test_bridge_io.py` pins it).
- 2026-10-06 · claude · Test repoint rule applied in WP02: a patch moves to the mapping module when the code under test reads the name there. `_dn_*` tests that patch `_state_to_action` / `_build_prompt_or_error` / `get_mission_type` on the bridge stay, because the bridge's own phases read them. Each repointed shared-name patch got an `assert_called()`.
