---
work_package_id: WP01
title: Evidence is judged against the verified landing when the lane branch is gone
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- FR-005
- FR-006
- NFR-001
- NFR-002
- NFR-003
- NFR-004
- C-001
- C-002
- C-003
- SC-001
- SC-002
- SC-003
- SC-005
planning_base_branch: issue-6780-pruned-lane-evidence-window
merge_target_branch: issue-6780-pruned-lane-evidence-window
branch_strategy: Planning artifacts for this mission were generated on issue-6780-pruned-lane-evidence-window. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6780-pruned-lane-evidence-window unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-pruned-lane-evidence-window-01M67HX3
base_commit: 72f513446781d5eaa742358703a0c7ca93ce74ec
created_at: '2026-10-30T23:26:24.321202+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
- T007
phase: Phase 1 - The landed window
history:
- at: '2026-10-30T00:00:00+00:00'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/consolidation/
create_intent:
- tests/specify_cli/cli/commands/test_accept_merge_commit.py
execution_mode: code_change
owned_files:
- src/specify_cli/consolidation/wp_evidence.py
- src/specify_cli/consolidation/no_implementation_attestation.py
- src/specify_cli/cli/commands/accept.py
- tests/specify_cli/cli/commands/test_accept_merge_commit.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Evidence is judged against the verified landing when the lane branch is gone

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `pi`

---

## ⚠️ IMPORTANT: Review Feedback

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status`).
- **You must address all feedback** before your work is complete.
- **Report progress**: `spec-kitty agent tasks add-history WP01 --note "..."`.

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the status event log.]*

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``. Use language identifiers in code blocks.

---

## Objectives & Success Criteria

Deliver the mission's whole behavioural change in the evidence axis:

1. **The reproduction passes.** A lanes Mission whose lane branch was merged into the
   mission branch, landed on the target through a verified PR-shaped merge commit, and
   then pruned, accepts through `accept(mode="pr", merge_commit=…, attest_first_landing=True)`.
   Each approved/done work package is judged on
   `planning_commit_sha..<verified landing commit>`.
2. **The lane branch stays the first choice.** When the window tip resolves to a commit,
   the lane window is used exactly as today and no fallback text appears.
3. **The gate keeps its teeth.** A work package with no change to its `owned_files`
   between the planning commit and the landing commit still refuses
   `IMPLEMENTATION_MISSING`; `--attest-no-implementation` is still the only lift and is
   still refused for a genuinely unreadable window.
4. **The refusal is honest.** With no verified landing commit, `IMPLEMENTATION_UNREADABLE`
   names the absent lane branch and both remedies (restore/fetch, or
   `accept --mode pr --merge-commit`), on both output lanes.
5. **Nothing else changes.** No skip, xfail, marker or silencing flag; no new CLI flag,
   config key or env var; every other caller of `evaluate_evidence` (consolidate,
   orchestrator-api, `move-task`, single_branch) is byte-identical.

Success criteria from `spec.md`: SC-001, SC-002, SC-003, SC-005.

## Context & Constraints

- Issue: spec-kitty/spec-kitty#6780, follow-up of #6715. Reproduced on `main` at
  `512567eee7`; the reproduction transcript is in
  `kitty-specs/pruned-lane-evidence-window-01M67HX3/research.md`.
- Read first: the mission's `plan.md` (IC-01 … IC-04), `research.md` (D-1 … D-8),
  `spec.md`.
- The one window authority is
  `src/specify_cli/consolidation/wp_evidence.py::lane_evidence_window` /
  `_scan_lane`. The one verified landing value is
  `src/specify_cli/consolidation/baseline.py::verify_pr_merge_evidence`, already called
  by `accept()` **before** the evidence gate (`_verify_merge_commit` →
  `_refuse_unevidenced_work`).
- **Charter constraints**: single canonical authority (use `lanes._git.ref_exists`,
  `git_probes.changed_paths_in_range` / `sha_reachable_from`,
  `core.vcs.git.git_merge_base` — never a hand-rolled git call); locality of change (the
  window choice stays in `wp_evidence.py`); fail-closed on every git error; no gate
  weakening; terminology canon (Mission, work package, lane branch, target branch,
  landing commit).
- Do **not** touch `cli/commands/agent/tasks_move_task.py` (the pre-review gate) or the
  single_branch leg.
- Keep the diff boring: no refactors of neighbouring helpers, no new module.

## Branch Strategy

- **Strategy**: Feature-branch mission with lanes (`topology: lanes`); all work merges
  into the mission's target branch and a PR carries it to `main`.
- **Planning base branch**: `issue-6780-pruned-lane-evidence-window`
- **Merge target branch**: `issue-6780-pruned-lane-evidence-window`

> Populated by `specify_cli` finalize-tasks. Do not change by hand.

## Subtasks & Detailed Guidance

### Subtask T001 – Survey before editing

- **Purpose**: Confirm the exact call chain so the change lands once, in the module that
  owns the window.
- **Steps**:
  1. Read `wp_evidence.py` end to end, especially `lane_evidence_window`,
     `_scan_lane`, `_dependency_evidence_windows`, `widened_lane_paths`, `_RECOVERY`,
     `evaluate_evidence`, `mission_evidence_report`.
  2. Read `accept.py::_refuse_unevidenced_work`, `_evidence_lanes_manifest`,
     `_record_no_implementation_attestations` and the `accept()` body ordering of
     `_verify_merge_commit` vs the gate.
  3. Read `no_implementation_attestation.py::plan_no_implementation_attestations` and
     `_refuse_unliftable`.
  4. Confirm every other caller of `evaluate_evidence` / `mission_evidence_report`
     (`consolidation/reconciliation.py`, `orchestrator_api/consolidation.py`,
     `tasks_move_task.py`) keeps working with the new keyword absent.
- **Files**: read-only.
- **Notes**: record the call chain in `spec-kitty agent tasks add-history WP01 --note` so
  the reviewer can see what was checked.

### Subtask T002 – The failing reproduction (RED first)

- **Purpose**: prove the bug through the production entry point before the fix.
- **Steps**:
  1. Extend `tests/specify_cli/cli/commands/test_accept_merge_commit.py`. Add a fixture
     variant (or a parameter on `_create_pr_merged_feature`) that, after
     `commit_lane_implementation`, merges the lane branch into the mission branch
     (`git merge --no-ff <lane branch>`), then lands the mission branch on `main` with the
     existing PR-shaped merge, then deletes the lane branch
     (`git branch -D <lane branch>`), and finally checks the mission branch back out.
  2. Assert the pre-fix behaviour first: `accept(...)` raises `typer.Exit(1)` with
     `IMPLEMENTATION_UNREADABLE` in the output and `baseline_merge_commit` absent from
     `meta.json`. Run it RED and paste the failure into the WP history.
  3. Then flip the test to the expected post-fix behaviour: the accept completes, records
     `baseline_merge_commit` (the landing commit's first parent) and `pr_merge_commit`,
     and leaves a clean tree (`git status --porcelain` empty).
- **Files**: `tests/specify_cli/cli/commands/test_accept_merge_commit.py`.
- **Notes**: use the module's existing `_git` helper; do not mock git. Keep the fixture
  shape realistic: the lane's content must be on the target (that is what makes the
  post-fix assertion meaningful).

### Subtask T003 – The control arms

- **Purpose**: prove the fix did not spread and the gate still refuses.
- **Steps**:
  1. **Hollow arm**: same fixture, a second approved work package (`WP02`, owned
     `docs/**`) that was never implemented and whose lane branch was pruned; assert the
     accept refuses with `IMPLEMENTATION_MISSING` naming `WP02` and writes nothing.
  2. **Intact-lane control**: run the accept with the lane branch still present; assert it
     passes and that the refusal text (if any other arm) never names the landing stand-in.
  3. **No-landing arm**: same pruned fixture, `accept` without `--merge-commit`; assert
     `IMPLEMENTATION_UNREADABLE` and that the text names the missing lane branch and the
     `--merge-commit` remedy (both human and `--json` lanes if cheap).
- **Files**: same test module.
- **Notes**: build the arms on one shared fixture builder so the positive and negative
  cases cannot drift (tactic `acceptance-criteria-non-vacuity`).

### Subtask T004 – The landed-window stand-in

- **Purpose**: make the evidence window survive the deletion of the lane branch ref.
- **Steps**:
  1. Add a keyword-only `landed_commit: str | None = None` to `evaluate_evidence` and
     `mission_evidence_report`, documented as "a commit the caller has already verified as
     this Mission's PR landing commit".
  2. Add one helper that resolves the window actually judged per lane: return the window
     unchanged when its tip resolves through `lanes._git.ref_exists`; otherwise, when
     `landed_commit` is supplied, require `git_probes.sha_reachable_from(repo_root, base,
     landed_commit)` and return `(base, landed_commit)` — and when the ancestor probe
     fails, raise `GitProbeError` with an explicit reason instead of diffing.
  3. Thread the effective tip into `_dependency_evidence_windows` (keyword, default
     `None` → today's `lane_created_branch(...)`) so a pruned lane branch does not make
     the widening probe raise; keep `widened_lane_paths`'s public signature backward
     compatible.
  4. When the stand-in was used, the `IMPLEMENTATION_MISSING` line must name the landing
     window (`<base>..<landing sha>`) and say the lane branch `<branch>` was pruned so the
     verified landing commit stands in; the submachine's `_CANNOT_VERIFY` wording is not
     used for a readable stand-in.
  5. Rewrite `_RECOVERY[IMPLEMENTATION_UNREADABLE]` so it names both remedies: restore or
     fetch the lane branch **or** re-run `spec-kitty accept --mode pr --merge-commit <sha>`
     with the verified PR landing commit.
  6. In `_scan_lane`, when the tip does not resolve and no `landed_commit` is supplied,
     emit the honest line: name the missing ref and say the window cannot be read because
     the branch no longer exists (rather than a bare `could not be diffed`), keeping the
     `IMPLEMENTATION_UNREADABLE` code.
- **Files**: `src/specify_cli/consolidation/wp_evidence.py`.
- **Notes**: keep `_SINGLE_BRANCH_ALIASES`, `_NEUTRAL_CODES`, the verdicts and the
  `EvidenceReport` shape untouched (`tests/consolidation/test_evidence_code_literals.py`
  pins them). Prefer a small dataclass or a `(window, stand_in_note)` tuple over
  threading two parallel values through the call chain.

### Subtask T005 – Thread the verified landing commit through accept

- **Purpose**: only the caller that verified the landing may widen the window.
- **Steps**:
  1. In `accept.py`, pass the verified commit into `_refuse_unevidenced_work`
     (`landed_commit=pr_merge.merge_commit if pr_merge is not None else None`) and from
     there into `mission_evidence_report`.
  2. Do the same for `_record_no_implementation_attestations` →
     `plan_no_implementation_attestations` (new keyword-only `landed_commit`), so the
     attestation planner and the gate read one window.
  3. Keep `_verify_merge_commit` where it is; do not re-verify or re-derive the SHA.
  4. Update the module/function docstrings that describe the window (they are the
     operator's map).
- **Files**: `src/specify_cli/cli/commands/accept.py`,
  `src/specify_cli/consolidation/no_implementation_attestation.py`.
- **Notes**: `accept --mode local` and `--mode pr` without `--merge-commit` pass `None`
  and must behave byte-identically to today.

### Subtask T006 – Targeted test run

- **Purpose**: prove the fix and no regression in the evidence axis.
- **Steps**: from the repo root run (module-scoped, never a full sweep):
  - `uv run pytest tests/specify_cli/cli/commands/test_accept_merge_commit.py tests/specify_cli/cli/commands/test_accept_evidence_preflight.py -q`
  - `uv run pytest tests/consolidation/test_evidence_code_literals.py tests/consolidation/test_single_branch_evidence_axis.py -q`
  - `uv run pytest tests/integration/test_6715_squad_identity_and_evidence.py -q`
  Record the counts in the WP history.
- **Files**: none.
- **Notes**: if a module is red for a reason outside this diff, classify it (reproduce on
  a pristine `origin/main` worktree) and report it — never skip or xfail it.

### Subtask T007 – Lint and type checks

- **Steps**: `uv run ruff check src/specify_cli/consolidation/wp_evidence.py src/specify_cli/consolidation/no_implementation_attestation.py src/specify_cli/cli/commands/accept.py tests/specify_cli/cli/commands/test_accept_merge_commit.py`
  and `uv run mypy src/specify_cli/consolidation/wp_evidence.py src/specify_cli/cli/commands/accept.py`.
- **Notes**: match the repository's configured rules (`ruff.toml`, `pyproject.toml`);
  do not add noqa suppressions to silence a real finding.

## Test Strategy

- Red-first through the production entry point: the reproduction calls the real
  `accept(...)` (not a helper) on a real git repository.
- Same-fixture controls: hollow work package (still refuses), intact lane branch (lane
  window), no landing commit (honest refusal).
- Existing #6715/#5939 modules unmodified and green.

## Risks & Mitigations

- **Broadening the gate**: the stand-in changes only the tip, the base and owned-glob
  match stay; the hollow arm pins that a missing deliverable still refuses.
- **Dependency-widening regression**: thread the effective tip; assert a lane with a
  dependency does not raise on a pruned ref (add the assertion to the fixture if cheap).
- **Over-eager fallback**: only when the caller verified a landing commit; every other
  call site passes `None`.

## Review Guidance

- Confirm the fallback cannot fire for consolidate, orchestrator-api or `move-task`
  (they pass no landing commit).
- Confirm the lane branch is preferred whenever it resolves.
- Confirm the ancestor guard refuses a planning commit that is not an ancestor of the
  landing commit rather than diffing it.
- Confirm no test was weakened, skipped or xfailed and no gate was silenced.
- Confirm the new refusal text is actionable and names the two remedies.

## Progress & Status

Progress, history, and status live in the status event log (`status.events.jsonl`).

- **Record a progress note**: `spec-kitty agent tasks add-history WP01 --note "<what you did>"`
- **Change WP status**: `spec-kitty agent tasks move-task WP01 --to <status>`
- **View history and status**: `spec-kitty agent tasks status`
