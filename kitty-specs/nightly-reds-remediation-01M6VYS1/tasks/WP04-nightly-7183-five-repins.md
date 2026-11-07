---
work_package_id: WP04
title: 'The six nodes of #7183 and the record (#7183)'
dependencies: []
requirement_refs:
- FR-007
- FR-008
- FR-009
- FR-010
- FR-011
- FR-012
- NFR-001
- NFR-002
- NFR-003
- NFR-004
- C-005
planning_base_branch: issue-7183-nightly-reds-remediation
merge_target_branch: issue-7183-nightly-reds-remediation
branch_strategy: Planning artifacts for this mission were generated on issue-7183-nightly-reds-remediation. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-7183-nightly-reds-remediation unless the human explicitly redirects the landing branch.
subtasks:
- T013
- T014
- T015
- T016
- T017
- T018
- T019
phase: Phase 2 - Re-pins
history:
- at: '2026-11-07T21:45:00+00:00'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/specify_cli/
create_intent:
- docs/changelog/unreleased/7340.internal.md
execution_mode: code_change
model: claude-sonnet-5-5
owned_files:
- tests/specify_cli/cli/commands/test_merge.py
- tests/specify_cli/cli/commands/test_tasks_status_default_mission.py
- tests/specify_cli/migration/test_residue_shared_walkers_6669.py
- tests/integration/test_pack_skill_lifecycle.py
- tests/integration/test_single_branch_write_checkout_e2e.py
- docs/changelog/unreleased/7340.internal.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP04 - The six nodes of #7183 and the record (#7183)

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

Check the `review_ref` field in the event log (`spec-kitty agent tasks status`). If this WP was returned from review, address every feedback item first.

---

## Markdown Formatting

Wrap HTML/XML tags in backticks. Use language identifiers in code blocks.

---

## Objectives & Success Criteria

- FR-007..FR-012, NFR-001..004. Six nodes pass, each at least as strong as before; an internal changelog fragment exists; the follow-up for the per-Mission git cost is drafted.
- Nodes: `tests/specify_cli/cli/commands/test_merge.py::test_mark_wp_merged_done_emits_done_when_lane_is_approved`; `tests/specify_cli/cli/commands/test_tasks_status_default_mission.py::test_bare_status_defaults_to_the_only_mission` and `::test_bare_status_skips_completed_missions`; `tests/specify_cli/migration/test_residue_shared_walkers_6669.py::test_cutover_repo_probes_git_once_per_walk`; `tests/integration/test_pack_skill_lifecycle.py::test_pack_skill_lifecycle_survives_every_retiring_path`; `tests/integration/test_single_branch_write_checkout_e2e.py::test_next_loop_claims_the_next_wp_after_residue_is_committed`.

## Context & Constraints

- Spec User Story 4; research.md rows #7183 n1..n5. Five different contract-change sources; none needs a `src/` change.

## Subtasks & Detailed Guidance

### Subtask T013 - merge done actor (n1, #6722 `3c0a8f3453`)

- `_mark_wp_merged_done` now emits `actor=build_system_actor(MERGE_ACTOR)` (`src/specify_cli/consolidation/done_bookkeeping.py`). In `test_merge.py` (about line 355) replace the plain-string pin with `assert emit_calls[0].actor == {"tool": "merge", "role": "system", "profile": None, "model": None}  # #6722`, the same dict-literal convention as `tests/consolidation/test_merge_done_recording.py::test_mark_wp_merged_done_emits_done_transition`. Keep the full 4-key dict (never `!= "merge"` or a subset). Leave the `actor="merge"` values at the seeded `StatusEvent` fixtures (about lines 111 and 537): they are inputs.

### Subtask T014 - tasks-status default fixture (n2, #5875 `7634075bd5`)

- `_make_mission` in `test_tasks_status_default_mission.py` writes a `meta.json` with no `mission_id` and untracked files, so the Mission is read-side residue (not selectable) and the sole-active default finds zero candidates. Add a distinct deterministic `mission_id` derived from the slug to the meta dict (ULID-shaped, e.g. `"01J8" + slug.replace("-", "").upper()[:16].ljust(16, "0")[:22]`; only non-empty is required but keep ids distinct so the several-active-missions test stays discriminating). Do not add git tracking instead. All five tests in the file must pass: the three error-path tests (`several_active_missions`, `no_active_mission`, `explicit_mission_still_wins`) must still produce their `mission_required` or success outcomes for the right reason.

### Subtask T015 - cutover git-call budget (n3, #6673 `d8829074b7`)

- The walk now makes 2 batch residue-probe calls (#6669) plus 4 guard calls per non-residue Mission whose `meta.json` is absent on disk (rev-parse prefix, rev-parse HEAD, ls-tree, ls-files --error-unmatch). In `test_cutover_repo_probes_git_once_per_walk` (about lines 184-191): split results into `residue` and `real`, assert `len(residue) == 32` and `len(real) == 1`, and replace `<= 2` with `assert git_count.calls <= 2 + 4 * len(real)` with a comment citing #6673/`d8829074b7`; optionally keep a lower bound `2 <=` pinning that the batch probe still ran. Update the docstring ("one batch residue probe (#6669) plus the #6673 guard per real Mission, never per residue folder"). The residue-independence intent stays explicit: 32 residue folders must cost no calls.
- Do not change production. The per-Mission cost goes to the drafted follow-up (T018).

### Subtask T016 - pack-skill lifecycle snapshot (n4, #6719 `d4be7a1940`)

- `charter activate/deactivate` hold the synthesis lock; in the non-git fixture it lives at `.kittify/runtime/locks/charter-synthesis.lock` and persists (filelock). Add `".kittify/runtime/locks"` to the snapshot ignore tuple in BOTH `_snapshot` calls (about lines 116 and 160), following `tests/specify_cli/cli/commands/charter/test_activation_json_6525.py` (`_RUNTIME_LOCKS`). Add `assert (project / ".kittify/runtime/locks/charter-synthesis.lock").is_file()` after the deactivate so the ignore is not vacuous, with a comment citing #6453/#6719. Leave `_without_empty_runtime` as is.
- If this node goes red once right after a venv rebuild, re-run to confirm and REPORT it; do not retry silently.

### Subtask T017 - single-branch residue (n5, #7003 `8f3149ae5b`)

- Lifecycle records are now one new file per record (`kitty-ops/lifecycle/<ulid>.json`), so a post-commit `next` produces no tracked-and-modified `kitty-ops/` path. In `test_single_branch_write_checkout_e2e.py` (about lines 351-354) replace the dead `kitty-ops/` clause: keep `modified = _git(repo, "status", "--porcelain", "--untracked-files=no")` (do NOT include untracked in this query), assert `f"kitty-specs/{slug}/mission-events.jsonl" in modified, modified`, then `full = _git(repo, "status", "--porcelain")` and `assert "?? kitty-ops/lifecycle/" in full, full`, then the existing `implement WP02` acceptance. Update the module docstring bookkeeping line to name the new shape. The sibling tests' `_assert_next_bookkeeping_dirty` is unaffected.

### Subtask T018 - changelog fragment and drafted follow-up

- Create `docs/changelog/unreleased/7340.internal.md` (read `docs/changelog/unreleased/README.md` first): one entry in the changelog's style, US spelling, no heading, e.g. `- **Nightly reds #7177, #7178, #7111, #7181, #7182, #7183 cleared** ...` stating that stale out-of-matrix pins were re-pinned and the upgrade tracked-meta notice now renders its restore remedy through the git-remedies home. Run `uv run --frozen python -m scripts.docs.check_changelog_style` and `uv run --frozen python -m scripts.docs.check_spelling --pass unreleased`.
- Append to `kitty-specs/nightly-reds-remediation-01M6VYS1/traces/tooling-friction.md` a dated draft of the follow-up issue: the tracked-meta guard costs 4 git subprocess calls per real Mission per cutover walk (2 + 4N for N Missions); proposal: pass the walk's already-computed `tracked` set into the guard to short-circuit call 6. Also note the process finding: out-of-matrix tests drift because per-PR CI never runs them (near-duplicate pairs like n1). Do NOT file the issue; report it for the operator.

### Subtask T019 - Evidence and neighbour guards

- RED on all six nodes first, then GREEN plus whole-file runs: `tests/specify_cli/cli/commands/test_merge.py`, `tests/consolidation/test_merge_done_recording.py`, `tests/specify_cli/cli/commands/test_tasks_status_default_mission.py`, `tests/specify_cli/migration/test_residue_shared_walkers_6669.py`, `tests/specify_cli/upgrade/test_runtime_state_cutover_skips_absent_meta_6673.py`, `tests/integration/test_pack_skill_lifecycle.py`, `tests/integration/test_single_branch_write_checkout_e2e.py`.
- `make format-check-files FILES="<the five test files>"` (or `ruff format --check --force-exclude`), `ruff check` on them.
- Strength spot-check (not committed): confirm at least the actor pin and the budget fail when the guarded behaviour changes.
- Commit: `test(nightly): re-pin the six stale nightly nodes of #7183 and add the changelog fragment`.

## Risks & Mitigations

- Unreproduced one-off flake on n4 after a venv rebuild: report, never retry to green silently.
- Do not widen the n5 `modified` query to include untracked files (would weaken the discrimination).

## Review Guidance

- Full 4-key actor dict; distinct mission ids; budget derived from `real`; lock existence asserted; tracked-only query kept; fragment passes both docs checks; follow-up drafted, not filed.

## Branch Strategy

- **Strategy**: `single_branch` (no lanes; WPs run one after the other in the write checkout)
- **Planning base branch**: `issue-7183-nightly-reds-remediation`
- **Merge target branch**: `issue-7183-nightly-reds-remediation`

> Populated by `spec-kitty agent mission finalize-tasks`. Do not change by hand.

## Rules that bind every WP (charter and spec)

- **Never weaken a test to green it.** A re-pin keeps every original behavioural assertion and adds the new contract. If you cannot re-pin without loosening an assertion or deleting a pin without a stronger home, STOP and report an operator decision.
- Cite the contract-change commit in a comment on the re-pinned lines or in the commit message.
- RED first: run each exact node id on the current tree before editing and keep the failure output (summary line). After the edit run the same ids, then the owning files and named gates. Record the exact commands and passed/failed counts in the WP's `add-history` note and the commit message.
- Run tests as `PWHEADLESS=1 .venv/bin/python -m pytest <ids> -q` (not a bare `uv run`). No full suites, no `make test-fast` over the repo (NO_FULL_HEAVY_SUITES_IN_MISSION); the targeted nodes, owning files and named gates are the verification.
- `uv run --frozen ruff check <files>` and `uv run --frozen ruff format --check --force-exclude <files>` must report 0 issues. No `noqa`, no `type: ignore`, no allowlist additions.
- Touch only this WP's owned files. A tiny justified out-of-map edit needs a one-line rationale in the history note.
- Commit per WP, ending the message with `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`. Do NOT push, open a PR, review, approve, accept or consolidate; the stop point is `for_review`.

## Progress & Status

Progress lives in the status event log, never in this file.

- Progress note: `spec-kitty agent tasks add-history <WPID> --note "<what you did>"`
- Subtask done: `spec-kitty agent tasks mark-status T00x --status done`
- Move: `spec-kitty agent tasks move-task <WPID> --to for_review`
- View: `spec-kitty agent tasks status`

Implementation command: `spec-kitty agent action implement <WPID> --agent claude --mission nightly-reds-remediation-01M6VYS1`
