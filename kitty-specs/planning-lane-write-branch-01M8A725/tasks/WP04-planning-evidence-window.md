---
work_package_id: WP04
title: 'Planning evidence window: start, end, callers, in-flight guidance'
dependencies:
- WP01
requirement_refs:
- FR-003
- FR-004
- FR-007
- FR-010
- NFR-001
- C-002
- C-001
- SC-002
- SC-004
planning_base_branch: fix/7860-planning-evidence-window
merge_target_branch: fix/7860-planning-evidence-window
branch_strategy: Planning artifacts for this mission were generated on fix/7860-planning-evidence-window. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/7860-planning-evidence-window unless the human explicitly redirects the landing branch.
subtasks:
- T015
- T016
- T017
- T018
- T019
- T020
phase: Phase 2 - Evidence
history:
- at: '2026-11-25T21:20:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/consolidation/
create_intent:
- tests/consolidation/test_planning_evidence_window_7860.py
- tests/specify_cli/cli/commands/agent/test_move_task_planning_evidence_7860.py
execution_mode: code_change
owned_files:
- src/specify_cli/consolidation/wp_evidence.py
- src/specify_cli/cli/commands/agent/tasks_move_task.py
- tests/consolidation/test_planning_evidence_window_7860.py
- tests/specify_cli/cli/commands/agent/test_move_task_planning_evidence_7860.py
- docs/adr/4.x/2026-10-04-5-approval-stamp-bounds-the-approved-claim.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP04 – Planning evidence window: start, end, callers, in-flight guidance

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro` · **Role**: `implementer` · **Agent/tool**: `claude`

Then: `spec-kitty charter context --action implement --json`.

---

## ⚠️ IMPORTANT: Review Feedback

Check `review_ref` in the event log. Address every item and record it with `add-history`.

---

## Objectives & Success Criteria

For a default Mission that has not landed, each approved (or moving-into-review) planning WP is judged on its own window. The window starts at the commit on the Mission branch that introduced the WP's window-opening (claim) status event and ends at the Mission branch. Every caller of the evidence axis agrees. Refusals name the Mission branch. Work that exists only on the target is named with both remedies. All other shapes are unchanged.

Done when:
- `consolidation/wp_evidence.py`:
  - the planning lane of a default, not-landed Mission yields one window per WP, `(claim_event_commit, mission_branch)`;
  - code lanes, explicit topologies and landed Missions keep `(planning_commit_sha, target or lane branch)`, one diff per lane (NFR-001);
  - an unresolvable start or end refuses (`EVIDENCE_WINDOW_UNCOMPUTABLE` / `IMPLEMENTATION_UNREADABLE`), never passes (NFR-002).
- `_RECOVERY[IMPLEMENTATION_MISSING]`, `absent_lane_window_cause`, the module docstring (:32–33), `lane_evidence_window`'s docstring (:147–148) and the comments at :586 and :601 state the rule. A planning WP of a default not-landed Mission commits "on the Mission branch (the coordination branch)".
- `tasks_move_task._mt_require_lane_evidence` uses the same per-WP window for the planning lane. Its refusal (around :1327–1333) names the Mission branch.
- The in-flight probe (FR-007) works as follows:
  - runs only after `IMPLEMENTATION_MISSING` for a default not-landed planning WP;
  - range `merge-base(planning_commit_sha, target)..target`, limited to the WP's `owned_files`;
  - appends "found on the target branch only: `<sha …>`" and both remedies (cherry-pick onto the Mission branch; `--attest-no-implementation <WP> --attest-reason "..."`);
  - is never shown for a hollow WP.
- Per-caller tests: move-task, accept, consolidate claim, orchestrator API accept-mission and consolidate-mission. `--attest-no-implementation` still lifts only a real `IMPLEMENTATION_MISSING`.
- ADR 2026-10-04-5 carries a **Proposed** amendment.

Requirements: FR-003, FR-004, FR-006, FR-007, FR-010, NFR-001, NFR-002, FR-008 (ADR 2026-10-04-5 part).

## Context & Constraints

- Plan IC-04. Data model: PlanningEvidenceWindow, TargetOnlyEvidence. Contract C2. Research R-02 (window start ruling).
- **Window start (operator ruling)**: use `status/wp_window_selector.window_opener_events(events, wp_id, cycle=True)` to pick the opener, then `mission_runtime/claim_commit.py::commit_introducing_status_event(surface, wp_id, event_id, rev=<mission branch>)` for its commit.
  - That is the derivation `review/wp_range.py` uses for this shape (`_derived_bases`, `EVENT_COMMIT`). Read those modules; do **not** edit them (C-001).
  - The status surface for a coordination Mission is the coordination branch. Get it through the status read door (`status/read_surface.py::resolve_status_read`) and pass a `StatusRef` or path as `wp_range._Context.event_surface` does.
  - `ClaimCommitUnresolved` → refuse (fail closed).
- **Window end**: `planning_write_ref(...)` from WP01. Do not re-derive it.
- `lane_evidence_window(lanes_manifest, lane)` cannot see `meta.json`; its signature must change (add `repo_root`), or add a planning-specific function that `_scan_lane` and move-task both call. Keep exactly one place that decides the planning window (FR-005); WP05 pins it with a test.
- Today's callers:
  - `evaluate_evidence` ← `reconciliation_claim.py:354`, `no_implementation_attestation.py:161`, `mission_evidence_report` (← `accept.py:~1405`, `orchestrator_api/consolidation.py:~644`);
  - `lane_evidence_window` ← `_scan_lane` (:819), `tasks_move_task.py:~1295`;
  - `widened_lane_paths` (:793): dependency widening applies to lanes with `depends_on_lanes`. The planning lane has none, but check.

  If the external callers need no edit (the signature change is internal to `wp_evidence`), they stay outside `owned_files`. If one needs an edit, make it with a rationale in `add-history`.
- `tasks_move_task.py:~1525` reads `resolution_kind == "repo_root"` (WP02's audit). Handle that reader here, in the same way WP02 classified the others; check WP02's `add-history` for its classification table.
- The `single_branch` path (`_single_branch_scan`, `lanes/single_branch_landing.single_branch_evidence_window`) is unchanged.

## Branch Strategy

- **Planning base branch**: `fix/7860-planning-evidence-window` · **Merge target branch**: `fix/7860-planning-evidence-window`
- Use the workspace `spec-kitty agent action implement WP04 --agent claude --mission planning-lane-write-branch-01M8A725` prints.

## Subtasks & Detailed Guidance

### Subtask T015 – Red tests for the planning evidence window

- **File**: `tests/consolidation/test_planning_evidence_window_7860.py` (new), real git. Build a default `lanes_with_coord`-shaped Mission by hand (a `meta.json` with `topology_source: default`, `mission_branch`, `coordination_branch`; a `lanes.json` with `lane-planning` and one code lane; `status.events.jsonl` on the Mission branch with a `claimed` event for the planning WP committed in its own commit), or reuse helpers from `tests/consolidation/test_evidence_*`.
- **Cases**:
  1. owned file committed on the Mission branch after the claim → no refusal (FR-003);
  2. hollow (nothing after the claim) → `IMPLEMENTATION_MISSING`, whose window text ends at the Mission branch (FR-004);
  3. hollow, but the owned file was created on the Mission branch **before** the claim (for example `research/notes.md` written during planning) → still `IMPLEMENTATION_MISSING` (FR-010);
  4. explicit topology, owned change on the target after the pin → passes; landed default Mission with the landing recorded (use the real landing record, not a cleared `mission_branch`) → window ends at the target (FR-006);
  5. claim event not committed on the Mission branch (`ClaimCommitUnresolved`) → refusal, not a pass (NFR-002);
  6. two planning WPs on the lane, one real and one hollow → only the hollow one refused (per-WP windows);
  7. a code lane next to the planning lane → its window is unchanged and diffed once.

### Subtask T016 – Per-WP planning window in `wp_evidence`

- **Steps**:
  1. Add a function such as `planning_evidence_window(repo_root, feature_dir, lanes_manifest, wp_id) -> tuple[str, str] | None` that:
     - returns `None` when the Mission is not default or not landed (the caller keeps `lane_evidence_window`);
     - otherwise resolves the start (the opener's commit) and the end (`planning_write_ref`);
     - raises a typed error when the start cannot be proven.
  2. In `_scan_lane`, branch for the planning lane of such a Mission: loop over the approved WPs and take one diff per WP. Keep the rest of `_scan_lane` intact. Extract a helper to stay ≤ 15 complexity.
  3. `_landed_window` / `landed_commit` (#6780): a PR-landed Mission has no local landing record, so it keeps today's route. Document it in a comment; do not extend it.
  4. Update the docstrings and comments listed above.

### Subtask T017 – Move-task leg, refusal and remedy texts

- `tasks_move_task._mt_require_lane_evidence` (around :1290–1333): call the same planning-window function for the planning WP of a default not-landed Mission. The refusal reads: `IMPLEMENTATION_MISSING: WP02 cannot move into review: no change to its owned_files in its evidence window <start>..<mission branch> (lane-planning). Commit the work package's implementation to its owned_files on the Mission branch <branch> (the coordination branch, checked out in <coord worktree>), then retry (...)`.
- `_RECOVERY[IMPLEMENTATION_MISSING]` (wp_evidence.py:~493): change "on the target branch for a planning-artifact work package" to "on the branch its planning lane writes to: the Mission branch before a default Mission lands, else the target branch".
- `absent_lane_window_cause` (:596): the planning lane's window ends at the Mission branch before the landing.
- Test the move-task leg in `tests/specify_cli/cli/commands/agent/test_move_task_planning_evidence_7860.py`. Follow the monkeypatch style of `test_move_task_evidence_gate.py` for unit cases, plus one real-git case.

### Subtask T018 – In-flight target-only probe and refusal addendum

- After a planning WP of a default not-landed Mission is refused `IMPLEMENTATION_MISSING`:
  - compute `base = git merge-base <planning_commit_sha> <target>`;
  - list `git log --format=%H <base>..<target> -- <owned pathspecs>`;
  - use the shared owned-files → pathspec conversion if one exists (`grep -rn "def _owned_pathspecs\|owned_pathspec" src`). The review range has one; do not copy it if a public helper exists. Otherwise add a small local one and note it.
- Non-empty → append the addendum (contract C2). Empty → no addendum.
- A git error in the probe must not hide the refusal: keep the refusal, and append "could not check the target branch: <reason>".
- **Tests**:
  - owned commit on the target only → the addendum names its SHA and both remedies;
  - an unrelated later commit on the target touching another path → its SHA is absent;
  - hollow → no addendum (negative control).

### Subtask T019 – Per-caller coverage

- In `tests/consolidation/test_planning_evidence_window_7860.py` (or a second new file you add to `owned_files` via a history note), drive each caller on the same fixture:
  - `mission_evidence_report` (accept and orchestrator accept-mission);
  - `evaluate_evidence` through `reconciliation_claim.build_approved_wp_set` (consolidate claim), or call `evaluate_evidence` as the claim does;
  - `no_implementation_attestation` planning (`--attest-no-implementation` on a hollow planning WP lifts it; on a real one it is refused or a no-op, as today);
  - move-task (T017).
- Assert identical windows across callers (the same start..end string in each refusal).

### Subtask T020 – Proposed amendment to ADR 2026-10-04-5

- **File**: `docs/adr/4.x/2026-10-04-5-approval-stamp-bounds-the-approved-claim.md`. Append `## Amendment 2026-11-25 (Proposed): a default Mission's planning evidence window runs on its Mission branch (#7860)`, using the heading form of ADR 2026-11-06-3's 2026-11-22 amendment. The italic line reads: *Proposed. The operator accepts or amends it on the pull request.*
  - **Gap**: Amendment 2026-10-29 (around :204) fixed the planning window at `planning_commit_sha..<target branch>`.
  - **Decision**: before a default Mission lands, a planning WP's window is `<commit introducing its window-opening event>..<Mission branch>`, one per WP (operator ruling 2026-11-25). Its start is durable and readable across clones, and the same derivation as the review range (ADR 2026-11-08-2, Q10/Q12). Everything else is unchanged.
  - **In-flight**: guidance only. Target-only owned commits are named with the two remedies.
  - **Residuals**:
    - a PR-landed Mission without a local landing record keeps the `--merge-commit` route;
    - NFR-001 is relaxed to one diff per approved planning WP for this lane only.
- Update the `**Status:**` line.

## Test Strategy

```bash
PWHEADLESS=1 .venv/bin/python -m pytest tests/consolidation tests/specify_cli/cli/commands/agent/test_move_task_evidence_gate.py tests/specify_cli/cli/commands/agent/test_move_task_planning_evidence_7860.py -q -p no:cacheprovider
PWHEADLESS=1 .venv/bin/python -m pytest tests/specify_cli/cli/commands/test_accept_evidence_preflight.py tests/integration/test_6715_consolidate_lane_evidence.py -q -p no:cacheprovider
make test-fast
```

`tests/specify_cli/cli/commands` is an out-of-matrix directory (nightly). Run the files you touch locally anyway. Plus ruff, format and mypy.

## Risks & Mitigations

- **Vacuous windows**: test case 3 (owned file present before the claim) is the guard. Do not drop it.
- **Event-commit lookup cost**: one `git log` per approved planning WP. Planning lanes are small; note it in NFR-001.
- **Divergence from the review range**: same primitives, read-only (C-001). WP05 adds the ratchet.

## Standing rules

Signed commits; no model names; zero ruff/format/mypy findings, no suppressions, complexity ≤ 15; no `test-full`; attribute every red.

## Review Guidance

- Exactly one function decides the planning window. move-task and `_scan_lane` both call it.
- Case 3 exists and fails without the window-start change.
- The probe is bounded to the owned files, names only owned commits, and never appears on a hollow WP.
- The ADR amendment is Proposed and lists its residuals.

## Progress & Status

- `spec-kitty agent tasks add-history WP04 --note "..."` · `mark-status T015 … --status done` · `move-task WP04 --to for_review`
