---
work_package_id: WP19
title: implement receipts name the branch that holds each commit
dependencies:
- WP02
requirement_refs:
- FR-013
planning_base_branch: issue-5440-coord-artifact-single-home
merge_target_branch: issue-5440-coord-artifact-single-home
branch_strategy: Planning artifacts for this mission were generated on issue-5440-coord-artifact-single-home. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5440-coord-artifact-single-home unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-coord-artifact-single-home-01M3V4BE
base_commit: c833721eb3c4ac284f1c32443a292e81969d99ae
created_at: '2026-10-01T11:11:10.255245+00:00'
subtasks:
- T103
- T104
- T105
phase: Phase 2 - Commit router and create
assignee: ''
agent: claude
shell_pid: ''
history:
- at: '2026-10-01T08:36:27Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/agent/workflow.py
create_intent: []
execution_mode: code_change
model: claude-sonnet-5
owned_files:
- src/specify_cli/cli/commands/agent/workflow.py
- tests/specify_cli/cli/commands/agent/test_workflow.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP19 – implement receipts name the branch that holds each commit

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status` or the Activity Log below).
- **You must address all feedback** before your work is complete. Feedback items are your implementation TODO list.
- **Report progress**: As you address each feedback item, update the Activity Log explaining what you changed.

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the Activity Log below or in the status event log.]*

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``, `` `<script>` ``
Use language identifiers in code blocks: ````python`,````bash`

---

## Objectives & Success Criteria

After `spec-kitty agent action implement`, the CLI prints which commits it made on which branch. Today, on a coordination-routed Mission, the claim's status transition is committed on the **coordination branch** by the transactional emit. The legacy follow-up then finds nothing left to commit and records a receipt against the **target branch** with `sha=None`. That misleading receipt was the evidence behind #5440's "implement leaks status" claim (spec Assumptions). When this WP is done:

- **FR-013 / US6.1.** Every receipt line carries a commit id, and the branch it names actually contains that commit: `git branch --contains <sha>` includes `destination_ref`.
- **US6.2 (positive control).** When implement does commit on the target branch (work-package metadata through the PRIMARY-group transaction), that receipt still names the target branch. A naive "always print the coordination branch" fix fails this control.
- The human summary prints the short commit id per line; the JSON `{"commits": [...]}` carries a non-null `sha` on every entry (additive).
- **C-008.** `lanes`/`single_branch` receipts are unchanged in meaning, and every entry still has a sha.

This is a small WP on one file (plus its test file). It depends on WP02 (shared fixture factory) and shares a lane with WP08, which runs after it. It is not a parallel root (analyze I4).

## Context & Constraints

- **Spec**: US6 (scenarios 1–2); FR-013; Assumptions ("#5440's 'implement leaks status' evidence is the misleading receipt covered by FR-013; no status record is committed to the target branch by `implement` today").
- **Plan**: IC-14.
- **Research**: D17 (receipt decision); red-first R18.
- **Contract**: `contracts/commit-outcome.md` §"JSON shape changes", "implement receipts": every entry carries a non-null `sha`.
- **Code facts at `ecb5dd914a`** (`src/specify_cli/cli/commands/agent/workflow.py`):
  - `_record_receipt(destination_ref, message, outcome, *, sha=None, wp_id=None)` (≈L233-249) appends `{"destination_ref", "message", "outcome", "sha", "wp_id"}` to `_WORKFLOW_COMMIT_RECEIPTS`.
  - PRIMARY-group transaction receipt: `_record_receipt(primary_ref, message, "committed", sha=receipt.commit_sha, ...)` (≈L487). It is correct and is the positive control.
  - Coordination transaction receipt: `destination_ref=coord_branch` (≈L545), via `BookkeepingTransaction.commit_idempotent`.
  - `_commit_via_legacy_safe_commit` (L768) runs the porcelain pre-check in `_resolve_legacy_porcelain_root(...)` (L716, which may be the coordination worktree). In the "State already present at HEAD" arm (L806-813) it records `_record_receipt(target_branch, message, "committed", sha=None, ...)`. **This is the defect.**
  - `_print_commit_summary` (L837; loop ≈L856-860) prints `- <destination_ref>  <message>  [ok]` with no commit id.
  - Caller: `workflow_executor.py:372` (`w._commit_via_legacy_safe_commit(...)`). It is not owned and must not need changes. `commit_workflow_change` (`workflow_executor.py:209`, C901 10) is untouched.
- **Charter**: read `.kittify/charter/charter.md` and run `spec-kitty charter context --action implement`. ATDD-first (C-011): R18 is committed before the fix.
- **Model discipline**: implement = sonnet (`claude-sonnet-5`); review = opus.
- **Terminology**: Mission, never feature. Say "target branch" and "coordination branch"; never a bare "primary".
- **C-006**: no heavy suites.
- **Brownfield scout (binding read)**: before coding, read `## WP19` in `kitty-specs/coord-artifact-single-home-01M3V4BE/research/brownfield-scout-wp12-22.md` (plus its "Cross-cutting" section where present). Its corrections are folded into the "Binding corrections" section below, which overrides conflicting text above.

## Branch Strategy

- **Strategy**: Planning artifacts were generated on issue-5440-coord-artifact-single-home; completed changes must merge back into issue-5440-coord-artifact-single-home.
- **Planning base branch**: issue-5440-coord-artifact-single-home
- **Merge target branch**: issue-5440-coord-artifact-single-home
- `finalize-tasks` allocates execution worktrees per computed lane, from `lanes.json`. Start with `spec-kitty agent action implement WP19 --agent claude`. Use the workspace path it resolves; never reconstruct it.
- **Lane (updated by the post-tasks squad)**: this WP depends on WP02 (fixture factory, P-m6). It shares `cli/commands/agent/workflow.py` with WP08, which depends on this WP (R-M3), so WP19 runs first in that shared lane. Keep your `workflow.py` edits confined to the receipt functions so WP08's reader fixes rebase cleanly.

## Subtasks & Detailed Guidance

### Subtask T103 – Red-first R18 and the target-branch positive control

- **Purpose**: Pin the observable receipt contract through the real CLI entry point before changing code.
- **Steps**:
  1. Build a coordination-routed Mission ready for `implement WP01`. If WP02's factory (`tests._factories.coord_mission`) is available on your lane base, use it; otherwise build the fixture directly:
     - a temporary repository on a topic branch;
     - `create_mission_core(..., topology=MissionTopology.COORD)` (or `LANES_WITH_COORD`);
     - minimal `spec.md`, `plan.md`, `tasks.md` and one `tasks/WP01-*.md`;
     - `spec-kitty agent mission finalize-tasks --mission <slug> --json` so `lanes.json` exists;
     - commit the planning artifacts;
     - satisfy the analysis-report gate if `implement` requires it (`analysis-report.md`). Look at existing implement CLI tests for a ready-made fixture: `grep -rl "action implement\|agent action implement" tests/ --include="test_*.py"`, e.g. `tests/agent/test_implement_command.py`.
     - Follow the "Comment on existing fixtures" note below.
  2. Add `test_implement_receipts_name_branch_containing_sha` to `tests/specify_cli/cli/commands/agent/test_workflow.py`:
     - run `spec-kitty agent action implement WP01 --agent claude --json` (via `typer.testing.CliRunner` on the app, or a subprocess against the installed CLI; match the module's existing style);
     - parse the trailing `{"commits": [...]}` line;
     - for every entry, assert `sha` is non-null and `git branch --contains <sha> --format=%(refname:short)` includes `destination_ref`.
     - It is red at base: the "already present" receipt has `sha: null` and names the target branch, while the status commit lives on the coordination branch.
  3. Add the positive control `test_implement_target_branch_receipt_names_target`: in the same run (or a fixture where implement commits work-package metadata on the target branch), the receipt for the PRIMARY-group commit names the **target branch**, and its sha is contained in the target branch. Make the assertion specific enough that hard-coding the coordination branch for every receipt fails.
  4. Add a C-008 control `test_implement_receipts_lanes_mission_unchanged`: a `lanes` Mission's receipts keep their destination refs, and every entry has a sha.
  5. Commit the three tests alone. Confirm R18 is red on the lane base and record the failing assertion in the Activity Log. The control tests may be green at base; that is expected.
- **Files**: `tests/specify_cli/cli/commands/agent/test_workflow.py` (extend near `class TestWorkflowCommitReceipts`, L401).
- **Comment on existing fixtures**: if wiring a full implement run is too heavy for a fast unit file, put the CLI-level receipts test in the same file but mark it with the repo's `git_repo` / integration marker conventions. It must still go through the real `implement` command path (C-005: the pre-existing entry point). Keep the pure `_record_receipt` unit tests as they are.
- **Edge cases**:
  - the JSON summary line may follow other output, so parse the **last** JSON line;
  - Windows newline handling;
  - `implement` may auto-claim, so make sure the WP is in `planned` and its dependencies are satisfied.
- **Shared fixture (post-tasks squad P-m6)**: this WP now depends on WP02. Build the coordination-routed Mission with `tests._factories.coord_mission` (`materialized=True` gives a deterministic MATERIALIZED surface at this lane's base), never a hand-rolled fixture.

### Subtask T104 – The "already present" arm names the ref and commit that hold the status record

- **Purpose**: Research D17. The receipt must point at where the record actually is: the ref returned by `write_target(STATUS_STATE)` and the latest commit on that ref touching the Mission's status log.
- **Steps**:
  1. In `_commit_via_legacy_safe_commit` (L768), replace the early-return arm (L806-813). When `mission_slug` is known:
     - resolve `ref = placement_seam(repo_root, mission_slug).write_target(MissionArtifactKind.STATUS_STATE).ref`. Use the existing import style in this module; `placement_seam` comes from `mission_runtime`. Check how `_resolve_legacy_porcelain_root` resolves the coordination worktree and reuse the same canonical authority; do not recompose branch names.
     - resolve the status log path relative to the repository: `kitty-specs/<mission dir>/status.events.jsonl`. Derive the dir name the way the module already does; `mid8` is passed in.
     - `sha = git log -1 --format=%H <ref> -- <path>`, run in `repo_root` (refs are shared across worktrees);
     - `_record_receipt(ref, message, "committed", sha=sha, wp_id=wp_id)`.
  2. When the probe yields no sha (an unexpected state, e.g. the ref is missing), fall back to `git rev-parse <ref>` (the tip, which by construction contains the already-present state) and log a debug line. Never record `sha=None` for a `committed` receipt.
  3. When `mission_slug` is `None` (truly legacy, no Mission identity), keep `target_branch` as the destination but record `git rev-parse HEAD` of the porcelain root as the sha, so the receipt is still contained in its ref. Verify that the porcelain root's HEAD is on `target_branch`; if not, use `git log -1 --format=%H <target_branch> -- <paths>`.
  4. Leave the normal `safe_commit` arm (≈L815-834), which already records `sha=getattr(result, "sha", None)`, unchanged. Make sure `result.sha` is populated; if `safe_commit` can return without a sha, apply the same rev-parse fallback.
  5. Keep the function's C901 ≤ 15 by extracting `_already_present_receipt(...) -> tuple[str, str]` as a small helper, with its own focused test.
- **Files**: `src/specify_cli/cli/commands/agent/workflow.py`.
- **Validation**: R18 is green; the positive control stays green (the PRIMARY-group receipt at ≈L487 is untouched); a unit test for the extracted helper covers the `mission_slug=None` and the ref-has-no-matching-commit fallbacks.
- **Edge cases**:
  - **Owned checkout.** If the module builds the seam with `owned=...` elsewhere, mirror it.
  - **`lanes` Missions.** `write_target(STATUS_STATE).ref` is the PRIMARY-partition target ref, so the receipt names the same branch as before and adds a sha (C-008 meaning preserved).
  - Do not call `write_dir` here. A receipt is a read of an already-persisted state, and must never materialize or seed.

### Subtask T105 – Print the short id; every JSON receipt carries `sha`

- **Purpose**: Operators and investigators can resolve every printed line to a commit (FR-013).
- **Steps**:
  1. In `_print_commit_summary` (L837; loop ≈L856-860), print `  - <destination_ref>  <short sha>  <message>  [ok]`. Use the first 7–10 characters, matching the repo's convention; grep `[:7]`/`--short`. When a receipt is `refused` (no commit), print `-------` or omit the id, and keep the `[refused]` glyph.
  2. JSON: `{"commits": [...]}` keeps every existing key. `sha` is already a key; the change is that it is now non-null for every `committed` entry. Optionally add `short_sha` (additive). If you add it, test it.
  3. Update the function docstring's human-format example.
  4. Audit every `_record_receipt(..., "committed", ...)` call in the module (`grep -n '_record_receipt(' workflow.py`): each must pass a sha. Add a guard in `_record_receipt`: when `outcome == "committed"` and `sha` is falsy, log a warning (do not raise; keep runtime robust). Cover it with a test.
- **Files**: `src/specify_cli/cli/commands/agent/workflow.py`, `tests/specify_cli/cli/commands/agent/test_workflow.py`.
- **Validation**: unit tests for `_print_commit_summary` (capsys) in human and JSON modes, plus the committed-without-sha warning test. The existing `TestWorkflowCommitReceipts` tests stay green.
- **Edge cases**: receipts accumulated across multiple operations in one invocation (`_reset_workflow_receipts`); unchanged JSON key order is not required but keep it stable.

## Binding corrections — analyze + brownfield scout (round 3)

> These corrections are binding and **override any conflicting text earlier in this prompt**. Source: `analysis-report.md` and the brownfield scout notes (pointer in Context & Constraints). Operator decisions are quoted where they apply.

- **Red premise (operator decision)**: on a coordination-routed Mission with a complete identity triple, `workflow_executor.commit_workflow_change` (L292) uses `_commit_via_coordination_transaction`, whose receipts carry non-null shas. R18 as written may therefore be **GREEN at the base**.
  1. **First** reproduce through the CLI on a coordination Mission. The grounding repro saw `chore: Start WP01 implementation [ok]` against the target branch. If it reproduces, fix that path.
  2. If it does **not** reproduce, fix the lanes/single_branch `sha=None` receipt path that does reproduce. That is `_commit_via_legacy_safe_commit` L806-813, reached for coordination-less Missions (`workflow_executor.py` ≈L366-372).
  3. Re-target R18 accordingly, with the coordination run as the control, and **report the finding** to the orchestrator (activity log plus a `tooling-friction` tracer entry). Never fake a red.
- **Keep the allowlisted line verbatim**: `safe_commit(target=CommitTarget(ref=target_branch))` stays inside `_commit_via_legacy_safe_commit`. It is allowlisted in `test_no_write_side_rederivation.py:780-790`, and its liveness twin is `test_checkout_grammar_allow_list_entries_are_still_live` (L973). Add no new non-seam `CommitTarget(ref=…)`.
- **Use the choke point**: call `_resolve_workflow_placement(...)` (`workflow.py:680`, the single choke point for `write_target`) and take `.ref`. Do not add a raw `placement_seam(...)`.
- `tests/git/test_guard_capability_regression.py:252-261` calls `_commit_via_legacy_safe_commit` directly, so keep the kw signature. `test_coord_commit_integrity_e2e.py` references it too.
- **Stale text**: this WP has **dependencies** (WP02), and it shares a lane with WP08 (WP19 first). It is not a parallel root (analyze I4).
- **I9 (round 4)**: record the reproduction result explicitly against FR-013 / US6, and against the spec Assumption "#5440's 'implement leaks status' evidence is the misleading receipt", in the activity log and in a `design-decisions` tracer entry. Record whether the coordination-Mission receipt defect reproduced.
  - If only the `lanes`/`single_branch` fallback reproduces, the fix there is **output-only and additive**: a commit id on every receipt entry, and no change to any existing field, branch name or commit. That is the spec's sanctioned C-008 note (Edge Cases, "Implement receipts on non-coordination topologies"). Add a `lanes` control asserting that every pre-existing receipt field is unchanged.
  - FR-013 still needs its coordination-Mission green (US6.1/6.2). If that run is green at the base, say so honestly; do not fabricate a red.

## Targeted test surface

```bash
uv run --frozen pytest tests/specify_cli/cli/commands/agent/test_workflow.py -q
uv run --frozen pytest $(grep -rl "_commit_via_legacy_safe_commit\|_print_commit_summary\|_record_receipt" tests --include="test_*.py") -q
uv run --frozen pytest tests/agent/test_implement_command.py -q
uv run --frozen pytest tests/specify_cli/cli/commands/agent/ -q        # owning module directory
make test-fast
```

- Never run the bare `tests/architectural/`, any e2e or integration directory, performance or stress suites, or `make test-full` (NO_FULL_HEAVY_SUITES_IN_MISSION, C-006).
- Record commands and pass/fail counts in the Activity Log for the PR's *Tests run* section.
- Classify unrelated reds per CLAUDE.md's baseline-red gotcha (pre-existing P0, CI environment, stale install, stale venv). In particular, a CLI subprocess against a stale `spec-kitty` install gives false reds; reinstall editable in the lane first.

## Quality gates

- C901 ≤ 15 for `_commit_via_legacy_safe_commit`, `_print_commit_summary`, `_record_receipt` and any new helper (NFR-004).
- `ruff check`, `ruff format --check` and `mypy --strict` on changed files; no new suppressions (NFR-005).
- ≥ 90% coverage of new and changed lines, with a focused test per new helper and branch (NFR-003).
- **Mission tracer files (analyze C4; charter Standing Order 3)**: at every decision point and every friction, append a dated entry through the canonical CLI, e.g. `spec-kitty agent tracer-append --mission coord-artifact-single-home-01M3V4BE --category design-decisions|approach|tooling-friction --entry "<YYYY-MM-DD WPxx: …>" --actor <you>`. The files are `traces/tooling-friction.md`, `traces/approach.md` and `traces/design-decisions.md`.
- **Pre-existing Failure Reporting Rule (analyze C4; charter)**: a red you did not cause and that is red on your base MUST be reported. Record the test id, the exact command and the evidence (output, base SHA) in the activity log and notify the orchestrator, who files the GitHub issue. Never fix it silently, never green-wash it, never xfail it.

## Issues

Issues: #5440

## Definition of Done

- R18 is green, and was red on the lane base (failure recorded).
- The target-branch positive control and the `lanes` control are green.
- No `committed` receipt carries `sha=None`; the human summary prints the short id; the JSON stays additive.
- The "already present" receipt names `write_target(STATUS_STATE).ref` and a commit on that ref touching the status log.
- Gates are green; Activity Log updated.

## Risks & Mitigations

- **Fixture weight.** A full implement run needs finalize-tasks and gate artifacts. Reuse an existing implement-CLI fixture rather than inventing one; keep the test count small.
- **Seam usage in a CLI module.** Use `write_target` (pure, ref-only) rather than `write_dir` (side-effecting).
- **Detached or odd HEAD in the coordination worktree.** The `git log -1 <ref> -- <path>` probe uses the ref, not the worktree HEAD, so it is robust to a worktree state.

## Review Guidance

- The reviewer (opus, distinct from the implementer) verifies red→green: R18 RED on the WP's lane base before the fix commit, GREEN on the final commit.
- Confirm the positive control would fail an "always coordination branch" implementation, by reading the assertion.
- Confirm every receipt's sha is contained in its named branch in the test (`git branch --contains`), not merely non-null.
- Confirm no `write_dir` call was introduced, and the `lanes` meaning is unchanged.

## Activity Log

> **CRITICAL**: Activity log entries MUST be in chronological order (oldest first, newest last).

### How to Add Activity Log Entries

**When adding an entry**:

1. Scroll to the bottom of this Activity Log section
2. **APPEND the new entry at the END** (do NOT prepend or insert in middle)
3. Use exact format: `- YYYY-MM-DDTHH:MM:SSZ – agent_id – <action>`
4. Timestamp MUST be current time in UTC (check with `date -u "+%Y-%m-%dT%H:%M:%SZ"`)
5. Agent ID should identify who made the change (claude-sonnet-4-5, codex, etc.)

**Format**:

```
- YYYY-MM-DDTHH:MM:SSZ – <agent_id> – <brief action description>
```

**Common mistakes (DO NOT DO THIS)**:

- Adding new entry at the top (breaks chronological order)
- Using future timestamps (causes acceptance validation to fail)
- Inserting in middle instead of appending to end

**Initial entry**:

- 2026-10-01T08:36:27Z – system – Prompt created.

---

### Updating Status

Status is managed via `status.events.jsonl`. Use `spec-kitty agent tasks move-task <WPID> --to <status>` to change WP status.
- 2026-10-01T12:00:05Z – claude – Cycle 1 review REJECTED (reviewer-renata). B1 (blocking): _already_present_receipt_sha's branch-tip fallback could name a commit that does NOT contain the change (reproduced: an ignored/never-committed path, and porcelain_root HEAD diverging from target_branch). Fixed: anchor on git log -1 HEAD -- <paths> at porcelain_root, accept only if the candidate both tracks every path (git cat-file -e) and is an ancestor of target_branch (git merge-base --is-ancestor); otherwise return None so _record_receipt's warning fires -- no unverified fallback. N1: corrected the reproduction record -- R18 reproduces only via a direct call to _commit_via_legacy_safe_commit with already-clean paths; through implement, neither topology reaches the already-present arm (coord receipts come from the transaction; lanes goes through safe_commit with a real sha). The grounding repro's target-branch [ok] line was the correct PRIMARY-group receipt shown without an id -- the missing id was the misleading part of #5440's evidence, fixed by T105. N2: corrected fixture attribution -- tests use tests.characterization.test_trio_json_envelope._build_mission_repo (not WP02's make_coord_mission, which mints identity/coord-worktree shape only and cannot pass implement's preflight gates); recorded as tooling-friction. N3: fixed the _record_receipt docstring reference to _already_present_receipt_sha. N4: added the message-unchanged assertion to the C-008 lanes control. Replaced the tip-fallback test with an ignored-path test and a HEAD-mismatch test, both asserting None + exactly one warning.
- 2026-10-01T12:22:59Z – claude – Cycle 2 review REJECTED on B2 (blocking, tests-only): diff coverage of workflow.py additions was 83% (25/30), below the 90% gate -- the uncovered lines were the new verification branches in _paths_tracked_at_commit and _already_present_receipt_sha's tracked-rejection arm. Added test_already_present_receipt_partially_untracked_path_set_is_none_with_warning (a tracked path plus an untracked path in the same set -> git log finds a commit but the tracked-at-commit check rejects it -> None + one warning) and TestPathsTrackedAtCommit (direct unit tests: outside-root -> False, untracked-inside-root -> False, tracked -> True, relative-path-anchors-on-porcelain_root per N6). Verified: removing the _paths_tracked_at_commit(...) call turns exactly the new test red, nothing else. Diff coverage now 100% (29/29) measured with diff-cover against lane base 4f2ddb7939 over test_workflow.py + test_guard_capability_regression.py + test_coord_commit_integrity_e2e.py. Applied N6 (anchor relative paths on porcelain_root, not process cwd).
