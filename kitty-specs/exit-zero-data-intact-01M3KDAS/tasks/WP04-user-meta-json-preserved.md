---
work_package_id: WP04
title: User meta.json edits survive consolidation (#4933)
dependencies: []
requirement_refs:
- FR-008
- FR-009
- FR-010
- NFR-001
- NFR-002
- NFR-003
planning_base_branch: claude/milestone-11-research-0rnnr4
merge_target_branch: claude/milestone-11-research-0rnnr4
branch_strategy: Planning artifacts for this mission were generated on claude/milestone-11-research-0rnnr4. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into claude/milestone-11-research-0rnnr4 unless the human explicitly redirects the landing branch.
subtasks:
- T019
- T020
- T021
- T022
phase: Phase 2 - Silent-loss fixes
history:
- at: '2026-09-28T09:40:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/coordination/coherence.py
create_intent:
- tests/consolidation/test_user_meta_json_dirty_4933.py
execution_mode: code_change
model: claude-sonnet-5
owned_files:
- src/specify_cli/coordination/coherence.py
- tests/specify_cli/git/test_destructive_guard.py
- tests/specify_cli/cli/commands/test_issue_2795_claim_blocker.py
- tests/mission_runtime/test_self_bookkeeping_allowlist.py
- tests/consolidation/test_user_meta_json_dirty_4933.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP04 – User meta.json edits survive consolidation (#4933)

## ⚡ Do This First: Load Agent Profile

Load `python-pedro` via `/ad-hoc-profile-load` (role `implementer`, agent `claude`); then `spec-kitty charter context --action implement --json`.

---

## ⚠️ IMPORTANT: Review Feedback

Check `review_ref` in the event log. Feedback items are your TODO list.

---

## Objectives & Success Criteria

Issue #4933: `coordination/coherence.py::is_self_bookkeeping_churn` (~:122-125) exempts **any** path whose basename is `meta.json` (`PurePosixPath(normalized).name == "meta.json"`). Every dirty-tree safety gate that consults it (directly or via `is_toolchain_generated_churn`) therefore ignores a user's own dirty `src/app/meta.json`, and `spec-kitty consolidate` then `reset --hard`s the repository root checkout or `worktree remove --force`s a lane worktree — destroying the edit — and exits 0.

Done means (FR-008–FR-010):
- FR-008: dirty tracked `src/app/meta.json` in the repository root checkout → `spec-kitty consolidate` exits 1 with `MERGE_UNSAFE_PRIMARY_DIRTY` (gate: `consolidation/executor.py:~3088-3090` `assert_worktree_clean(..., error_code=MERGE_UNSAFE_PRIMARY_DIRTY)`; codes defined in `git/destructive_guard.py:~41-42`), names the file, prints the commit-or-stash remedy, and the edit survives.
- FR-009: same edit inside a lane worktree that consolidation would remove → exits 1 with `MERGE_UNSAFE_WORKTREE_DIRTY` (lane gate `executor.py:~3106`, coord gate `~:3115`; the default code of `assert_worktree_clean`), names worktree + file, edit survives. FR-009 is a separate fixture through the worktree-removal gate (both locations share the one predicate, so it is not independently red from FR-008 — it proves the second gate honours it).
- FR-010 (ratchet): a dirty Spec Kitty-owned `kitty-specs/<mission>/meta.json` — including in a monorepo subdirectory (`sub/kitty-specs/<m>/meta.json`) — stays exempt; `kitty-specs/<m>/research/meta.json` is NOT exempt; the legacy `.kittify/meta.json` stays exempt.
- Several dirty user files are all listed in one refusal (verify the gates already aggregate; if they do, just test it).

## Context & Constraints

- Plan design decision **D4**; research **R3** (full caller census — destructive gates, refusal gates, filters).
- Anchor: `(?:^|/)kitty-specs/[^/]+/meta\.json$` (depth-exact) plus `(?:^|/)\.kittify/meta\.json$`. Apply to `normalized` (the function's posix-normalized, rstripped path), not the raw path. Git porcelain paths are git-root-relative, which is why the `(?:^|/)` prefix is needed for monorepos (adjudicated in the post-spec squad).
- Keep the literals **inside the function** (the C9 comment and `tests/architectural/test_exemption_registry_ratchet.py` pin that no new per-gate exemption list appears). Add a one-line comment that `.kittify/meta.json` is legacy (read only by `tracker.py` and an old migration).
- Do NOT add `meta.json` to `mission_runtime._MISSION_FILE_KIND_BY_BASENAME` (would widen `bookkeeping_projection.py:472` and the reconciliation class guard).
- `git/ref_advance.py` receives the classifier as a parameter; no change there. `ref_advance.py:353` lock-field-only skip is accepted as-is.
- This WP edits only `coherence.py`; the executor gates (owned by WP03's lane) are exercised by tests, not edited.

## Branch Strategy

- **Strategy**: lanes · **Planning base**: `claude/milestone-11-research-0rnnr4` · **Merge target**: `claude/milestone-11-research-0rnnr4`. `spec-kitty implement WP04`.

## Subtasks & Detailed Guidance

### Subtask T019 – Red-first CLI repros (`tests/consolidation/test_user_meta_json_dirty_4933.py`)

Mark `@pytest.mark.regression`; confirm FAIL on unmodified code; record in the Activity Log. Build a scratch repo with a lanes-topology mission ready to consolidate (reuse fixtures from existing consolidate integration tests — `grep -rl "MERGE_UNSAFE_PRIMARY_DIRTY\|MERGE_UNSAFE_WORKTREE_DIRTY" tests/`).

1. Root checkout: commit `src/app/meta.json`, then modify it without committing; run `spec-kitty consolidate --mission <m>` (CLI). Assert exit 1, the file named in output, the remedy text (commit/stash) present (NFR-003), file content still the modified text.
2. Lane worktree: same edit inside the lane worktree `.worktrees/<slug>-lane-<id>/src/app/meta.json` (the file must be tracked there); consolidate → exit 1, worktree still present, edit intact.
3. Aggregation: two dirty user files (`src/app/meta.json`, `README.md`) → one refusal listing both.
4. Controls (must pass before and after): dirty `kitty-specs/<m>/meta.json` only → consolidation proceeds as today.

### Subtask T020 – Depth-exact anchor

- Replace `if PurePosixPath(normalized).name == "meta.json": return True` with two compiled regexes (function-local, alongside the existing `kitty_ops_op_record` / `mission_state_audit` ones) and `if owned_meta.search(normalized) or legacy_kittify_meta.search(normalized): return True`. Update the docstring (it currently explains the basename rule) with the new rule and #4933.
- Remove the now-unused `PurePosixPath` import if nothing else uses it.

### Subtask T021 – Unit cases + caller-class tests

- `tests/mission_runtime/test_self_bookkeeping_allowlist.py` (~:94 pins the positive case): add parametrised negatives — `src/app/meta.json`, `kitty-specs/m/research/meta.json`, `my-kitty-specs/m/meta.json`, `meta.json` (repo root) — and positives — `kitty-specs/m/meta.json`, `sub/kitty-specs/m/meta.json`, `.kittify/meta.json`, a backslash path `kitty-specs\\m\\meta.json` if `to_posix` normalizes it.
- One test per caller class through the public predicate the gates use (`is_toolchain_generated_churn` if that is the facade) proving a user `meta.json` is now treated as dirty.

### Subtask T022 – Convert and gate

```bash
uv run --frozen pytest tests/consolidation/test_user_meta_json_dirty_4933.py tests/mission_runtime/test_self_bookkeeping_allowlist.py -q
uv run --frozen pytest $(grep -rl "is_self_bookkeeping_churn\|is_toolchain_generated_churn" tests --include=*.py | sort -u) -q
uv run --frozen pytest tests/architectural/test_exemption_registry_ratchet.py tests/architectural/test_destructive_op_routing.py tests/architectural/test_layer_rules.py -q
uv run --frozen ruff check src/specify_cli/coordination/coherence.py <tests> && uv run --frozen ruff format --check src/specify_cli/coordination/coherence.py <tests>
uv run --frozen mypy --strict src/specify_cli/coordination/coherence.py
make test-fast
```

Remove regression markers after green.

## Risks & Mitigations

- Known candidates now owned for re-pinning if they relied on the basename exemption: `tests/specify_cli/git/test_destructive_guard.py`, `tests/specify_cli/cli/commands/test_issue_2795_claim_blocker.py`. Any other re-pin outside owned_files: record a one-line rationale in the Activity Log.
- Some existing test fixtures may rely on an arbitrary dirty `meta.json` being exempt (e.g. `tests/audit/fixtures/*/repo/kitty-specs/*/meta.json` match the anchor and stay exempt; others may not). Judge each red: a fixture that relied on the bug gets its fixture fixed with a comment citing #4933; never weaken the anchor.

## Review Guidance

- Anchor is depth-exact and monorepo-safe; literals inside the function.
- Both arms (root checkout, lane worktree) proven red-first and green; edit survives.
- Ratchet controls pass unchanged.

## Activity Log

- 2026-09-28T09:40:00Z – system – Prompt created.
