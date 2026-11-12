---
work_package_id: WP02
title: Commit-to-target single_branch records window points (characterize first, then stamp)
dependencies: []
requirement_refs:
- FR-002
- C-008
- C-009
- SC-004
planning_base_branch: feat/7578-review-context
merge_target_branch: feat/7578-review-context
branch_strategy: Planning artifacts for this mission were generated on feat/7578-review-context. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into feat/7578-review-context unless the human explicitly redirects the landing branch.
subtasks:
- T006
- T007
- T008
- T009
- T010
history: []
agent_profile: python-pedro
authoritative_surface: src/specify_cli/status/
create_intent:
- tests/consolidation/test_commit_to_target_stamp_characterization.py
- tests/status/test_lane_head_commit_to_target.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/status/lane_head.py
- tests/consolidation/test_commit_to_target_stamp_characterization.py
- tests/status/test_lane_head_commit_to_target.py
- docs/adr/4.x/2026-11-08-2-work-package-windows-are-recorded-at-the-opening-transition.md
- tests/status/test_lane_head_single_branch.py
- tests/integration/test_single_branch_approval_windows.py
role: implementer
tags: []
tracker_refs: []
---

# WP02: Commit-to-target single_branch records window points (characterize first, then stamp)

> NOTE (orchestrator, 2026-11-12): `tests/integration/test_single_branch_approval_windows.py::test_commit_to_target_unbounded_residual` asserts `rc == 1` with `LANE_MOVED_AFTER_APPROVAL` on a commit-to-target Mission although its docstring says it is NOT refused. So some bound DOES reach commit-to-target today, contrary to the plan's premise. In T006, trace which code path refuses it (cite file:line) and pin it as a characterization cell; fix the stale docstring (this file is in owned_files). Record the finding in the ADR amendment and report it in your completion note (the orchestrator records it in `tracer-design-decisions.md`; lanes never edit tracer files). Both `tests/status/test_lane_head_single_branch.py` and this file are owned by WP02.

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

Implementation command:

```bash
spec-kitty agent action implement WP02 --agent claude --mission review-context-wp-diff-01M774QF
```

## Objective

Make a commit-to-target `single_branch` Mission record its window points: `wp_window.open_sha` on the
opening move (`claimed` / `in_progress`) and `lane_head` on every lifecycle move (notably `for_review`),
both taken at the head of the write branch, which for commit-to-target is the target branch itself.
Pin today's consolidation and accept verdicts **first**, measure what the stamp changes, and record the
change in an amendment to ADR `2026-11-08-2`.

## Context

- **Why (FR-002, ruling Q3).** The review range (IC-03, a later WP) must be *recorded*, not guessed, on
  every topology. Today a commit-to-target `single_branch` Mission records nothing:
  `status/lane_head.py::_read_lane_head` finds no minted write branch
  (`single_branch_landing.minted_write_branch` returns `None` when write branch == target), falls through
  to `lanes.json`, finds the WP on `lane-planning`, and returns `LaneHeadReading.not_applicable()`
  (`research/code-grounding.md` §3). `transition_pipeline._wp_window_value` then writes no `wp_window`
  because the reading is not applicable. The operator ruled (decision `DM-01M774W8SW9GE4VN8QAR59MJ9S`, Q3):
  stamp at the write checkout head and accept the resulting consolidation-verdict change, with an ADR
  amendment.
- **What changes in consolidation, and what does not (research R3, R8, post-plan P11/P12).**
  - **Unchanged (verified in planning):** `reconciliation_bound._bound_write_branch` returns `None` for
    commit-to-target (it calls `minted_mission_branch`), so `write_branch_bound.check_write_branch_windows`
    is never reached; `approved_bound._approval_is_bounded` excludes these Missions;
    `cutover_eligibility` treats the keys as provenance. The Q3 ruling text names
    `check_write_branch_windows` as the mechanism; that is wrong, and the ADR amendment corrects it (P12).
  - **Newly fed (must be measured):**
    1. `reconciliation_canceled._mixed_lanes` (line ~55) includes planning lanes, and the canceled-content
       attribution uses `lacks_lane_head_stamps` (line ~439). A mixed approved+canceled planning lane now
       has stamps, so the attribution gets real inputs.
    2. `reconciliation_closed_world._recorded_lane_heads` (line ~246), read by the `--dependency-ref`
       refusal ("names Mission work": any WP `lane_head` stamp).
    3. `approved_attestation._has_review_approval_stamp` (line ~103), which decides whether
       `--attest-approved-reviewed` is accepted.
- **C-009.** Planning-artifact WPs on `lanes` / `lanes_with_coord` topologies keep recording nothing.
  Only the stored-`single_branch` commit-to-target case changes.
- **SC-004 / User Story 5.** Verdicts are unchanged, or differ only as recorded. Any previously PASSING
  cell that now REFUSES is an operator decision, not yours.
- **Discipline and commit order (C-010, per work package: the lane's first commit is a failing test).**
  1. First lane commit: T007's red unit test, alone.
  2. Second commit: T006's characterization, alone (green on the base: it pins today's verdicts).
  3. Then T008 (`src/`), T009, T010.
  Both test commits land before any `src/` change. Write the subtasks in this order even though T006 is
  described first below.
- **Dependents.** IC-03's review-range resolver (later WP) reads these stamps when present. This WP has no
  dependencies and can run in parallel with WP01.
- **Do not edit** `tests/integration/test_single_branch_write_checkout_e2e.py` (PR #7562 overlap).

### Subtask T006: Characterization of today's verdicts (FIRST, separate commit)

- **Purpose**: pin the current consolidation and accept verdicts of a commit-to-target `single_branch`
  Mission before the stamp exists, so the verdict change is measured, not assumed (R8, IC-06a).
- **Steps**:
  1. Create `tests/consolidation/test_commit_to_target_stamp_characterization.py`.
  2. Reuse `tests/integration/single_branch_window_support.py`: `build_template(base, commit_to_target=True)`
     once per module (a `tmp_path_factory` fixture, as `test_single_branch_approval_windows.py:328` does),
     then copy/checkout per cell. Use its `claim`, `implement`, `submit`, `approve`, `build_and_approve`,
     `move`, `emit`, `commit_file`, `consolidate`, `tip` helpers. Do not hand-roll git or CLI plumbing the
     module already provides. If a helper you need (for example a cancel or accept call) is missing, call
     the CLI through the module's `_invoke` / `_sk` pattern inside your own test file; do not edit the
     support module (not owned).
  3. Use `monkeypatch.delenv` for harness leaks (`SPEC_KITTY_NO_NAG`, `SPEC_KITTY_NO_UPGRADE_CHECK`,
     `SPEC_KITTY_NON_INTERACTIVE`) where a cell depends on them being unset.
  4. Write four cells, each asserting the exit code AND the exact refusal code / message fragment (or the
     success banner) as it is today:
     - **(a) approved-only**: two WPs built and approved (`build_and_approve`), then `consolidate` and
       `accept`. Pin both verdicts.
     - **(b) mixed approved + canceled on the planning lane**: WP01 approved, WP02 implemented then moved
       to `canceled` (with its commit on the target). Pin the `consolidate` verdict and code. This exercises
       `_mixed_lanes` and `lacks_lane_head_stamps`.
     - **(c) `consolidate --dependency-ref <ref>`**: create an external branch off the target, declare it.
       Pin whether it is accepted or refused (and the code, e.g. the "names Mission work" refusal). This
       exercises `_recorded_lane_heads`.
     - **(d) `consolidate --attest-approved-reviewed <WP> --attest-reason "..."`**: on an approved WP. Pin
       whether the attestation is accepted or refused and the resulting consolidate verdict. This exercises
       `_has_review_approval_stamp`.
  5. Each cell carries a short docstring naming the reader it pins.
  6. **Reachability, so "0 differences" cannot pass as a no-op.** A cell whose reader is never reached
     would show no verdict change whether or not the stamp exists. Each cell must therefore prove, in the
     AFTER state (once T008 lands), that its reader actually ran on stamped inputs:
     - **Inputs carry the stamps.** Read the Mission's status events (through
       `specify_cli.status.resolve_status_read` + `read_status_events`, not a hand-parsed file) and assert
       that the cell's WPs carry `policy_metadata["lane_head"]` on their lifecycle moves and
       `policy_metadata["wp_window"]` with an `open_sha` on their opening move. Write this assertion now,
       parametrised on a module constant `STAMPED = False` (T006: assert the keys are ABSENT, today's
       state); T009 flips it to `True` and the same assertion then requires them PRESENT.
     - **The reader ran.** Wrap the targeted reader with a `monkeypatch.setattr` spy that records each call
       and delegates to the original (the pattern `characterization_support.run_in_process` uses for
       `MergeOutcomeVerifier.verify`):
       - cell (b): `reconciliation_canceled._mixed_lanes` (and the attribution entry that calls
         `lacks_lane_head_stamps`);
       - cell (c): `reconciliation_closed_world._recorded_lane_heads`;
       - cell (d): `approved_attestation._has_review_approval_stamp`;
       - cell (a): `MergeOutcomeVerifier.verify` (the approved-only gate).
       Assert the spy recorded at least one call, and for (b)-(d) record what it returned (for example the
       stamp set `_recorded_lane_heads` produced), so T009's AFTER expectation can show the reader saw a
       non-empty stamp input. Patch the attribute where the caller looks it up (the module that calls it),
       not only where it is defined.
     - **In-process, so the spy can see it.** `single_branch_window_support.consolidate` runs the CLI as a
       subprocess, which a `monkeypatch` spy cannot observe. Drive `consolidate` / `accept` in-process for
       these cells with `CliRunner().invoke(specify_cli.app, [...])` inside the same environment the module
       sets up (`cli_env`, `chdir` to the repo), as `characterization_support.run_in_process` does. Use the
       support module's subprocess `consolidate` only for a cross-check cell, never as the only driver.
  7. Mark the tests with the markers the neighbouring integration-style consolidation tests use (check
     `tests/integration/test_single_branch_approval_windows.py` for the marker set).
  8. Run them: all pass on the unmodified code (with `STAMPED = False`). Commit **alone**, right after the
     T007 red commit (see "Discipline and commit order"):
     `test(consolidation): characterize commit-to-target single_branch verdicts before window stamp (#7578)`.
- **Files**: `tests/consolidation/test_commit_to_target_stamp_characterization.py` (new, ~200–300 lines).
- **Validation**: `uv run --frozen pytest tests/consolidation/test_commit_to_target_stamp_characterization.py -q`
  is green on the base; `git log` shows this commit before any `src/` change.

### Subtask T007: Red-first unit test for the stamp

- **Purpose**: specify the new reading and its limits before implementing it.
- **Steps**:
  1. Create `tests/status/test_lane_head_commit_to_target.py`. Borrow the fixture shape of
     `tests/status/test_lane_head_single_branch.py` (`_git`, `_write_mission`, `_commit`, `_TARGET`), by
     copying the minimal helpers into your file. That file is owned by this WP, but its only planned edit is
     the inversion of `test_commit_to_target_single_branch_stays_unstamped` in T008; do not move helpers
     out of it.
  2. Tests:
     - commit-to-target `single_branch` (`topology="single_branch"`, no `mission_branch`): `read_lane_head`
       returns the target branch head SHA (`reading.sha == git rev-parse <target>`), `applicable` True.
     - commit-to-target with the target branch ref absent (or a git read failure, monkeypatched): a failed
       reading (`LANE_BRANCH_MISSING` / `GIT_ERROR`), never an exception (C-1).
     - `lanes` topology, WP on the planning lane: still `not_applicable` (C-009).
     - minted `single_branch` (with `mission_branch`): unchanged, stamps the minted branch head.
     - a Mission with no stored topology / no `target_branch` in `meta.json`: unchanged behaviour.
     - pipeline level: for commit-to-target, moving a WP to `claimed` and `in_progress` writes
       `policy_metadata.wp_window` with `open_sha` == target head; moving to `for_review` writes
       `policy_metadata.lane_head` == target head. Drive it through `emit_status_transition` (or the CLI
       `agent status emit` / `move-task` path) the same way existing `tests/status/` pipeline tests do.
  3. Run: the commit-to-target cases are red, the C-009 / minted cases green. Commit red, as the lane's
     **first** commit (C-010):
     `test(status): red — commit-to-target single_branch stamps lane_head and wp_window (#7578)`.
- **Files**: `tests/status/test_lane_head_commit_to_target.py` (new, ~150–220 lines).
- **Validation**: the expected subset fails for the right reason (`sha is None` / missing `wp_window`).

### Subtask T008: Implement the commit-to-target reading in `_read_lane_head`

- **Purpose**: return the target head for a stored-`single_branch` commit-to-target Mission.
- **Steps**:
  1. In `src/specify_cli/status/lane_head.py::_read_lane_head`, after the existing
     `minted_write_branch(...)` check and before the `lanes.json` read, resolve the commit-to-target case:
     read `meta.json` once through `single_branch_landing.stored_mission_meta(repo_root, mission_slug,
     owned=owned)`; when `is_single_branch_meta(meta)` and `target_branch` is a non-empty string and
     `write_branch_from_meta(meta, target) == target`, return
     `_write_branch_head(repo_root, mission_slug, wp_id, target)`.
  2. Prefer a small helper (for example `_commit_to_target_branch(repo_root, mission_slug, owned) -> str | None`,
     the mirror of `minted_write_branch`) so `_read_lane_head` stays at complexity ≤ 15 and the helper is
     directly testable. Consider reading `meta.json` once for both the minted and commit-to-target checks;
     do not change `single_branch_landing.py` (not owned).
  3. Keep best-effort semantics (C-1): `_write_branch_head` already maps a missing branch and a git error
     to failed readings and logs at WARNING. Confirm the WARNING wording (`_WRITE_BRANCH_LANE`, "Mission
     branch ... does not exist") still reads correctly when the branch is the target; adjust the `why`
     text if it would mislead (e.g. "write branch <target>").
  4. Update the module docstring paragraph "single_branch Missions (S8, #7283, FR-070)": it currently
     says a commit-to-target Mission "keeps the lane-map behaviour (unbounded residual, FR-078)". State
     that it now stamps the target head (#7578) and stays unbounded in consolidation; planning lanes of
     lane topologies stay unstamped.
  5. Invert `tests/status/test_lane_head_single_branch.py::test_commit_to_target_single_branch_stays_unstamped`
     (owned by this WP): it asserts `sha is None` and goes red by design. Re-pin it to the new reading
     (the target head), rename it to say so, and cite #7578 in its docstring and the commit message. Never
     delete it.
  6. Run T007: green. Run `ruff check`, `ruff format --check --force-exclude`, `mypy --strict` on the file.
- **Files**: `src/specify_cli/status/lane_head.py` (~20–40 changed lines).
- **Validation**: `tests/status/test_lane_head_commit_to_target.py`, `tests/status/test_lane_head.py`,
  `tests/status/test_lane_head_single_branch.py` (with the step 5 inversion).

### Subtask T009: Re-run the characterization and record the verdict change

- **Purpose**: measure what the stamp changed (SC-004, User Story 5).
- **Steps**:
  1. Flip `STAMPED = True` (T006 step 6) and re-run
     `tests/consolidation/test_commit_to_target_stamp_characterization.py`. Every cell must now show the
     stamps present on its inputs and its reader spy called with a non-empty stamp input. A cell whose spy
     never fires is not a characterization: fix the cell (drive the reader), never drop the assertion.
  2. For every cell whose verdict changed, update its pinned expectation **only** with an explicit
     comment block `# BEFORE (#7578 base): ... / AFTER: ... / reader: ...`. Never delete a cell.
  3. Put the before/after table in the ADR amendment (T010) and report it in your completion note. Do not
     edit `tracer-design-decisions.md` (or any `tracer-*.md`) from the lane: the orchestrator records the
     entry from your note.
  4. **STOP rule.** If any previously PASSING cell now REFUSES (or refuses with a new code), do not adjust
     the expectation. Stop and escalate to the orchestrator with the cell, the before/after output and the
     reader responsible. That is an operator decision.
  5. Re-run the existing commit-to-target consolidation tests:
     `tests/integration/test_single_branch_approval_windows.py` (incl.
     `test_commit_to_target_unbounded_residual`), `tests/consolidation/test_write_branch_bound.py`,
     `tests/consolidation/test_single_branch_evidence_axis.py`,
     `tests/consolidation/test_single_branch_stamp_warnings.py`. Any change there follows the same STOP rule.
- **Files**: the characterization test (expectation updates and the `STAMPED` flip).
- **Validation**: all green; every cell proves its reader ran on stamped inputs; every changed verdict has
  a BEFORE/AFTER comment, a row in the ADR table and an entry in the completion note.

### Subtask T010: ADR amendment

- **Purpose**: record the decision and its measured effect (C-008).
- **Steps**:
  1. Append a section `## Amendment 2026-11-12 (#7578)` to
     `docs/adr/4.x/2026-11-08-2-work-package-windows-are-recorded-at-the-opening-transition.md`, and bump
     the frontmatter `updated:` field.
  2. Say, in plain operator-readable prose:
     - A commit-to-target `single_branch` Mission now records `lane_head` and `wp_window` at the head of
       the write checkout's branch, which is the target. Planning lanes of lane topologies still record
       nothing.
     - Why: the review range (#7578) reads a recorded window on every topology (ruling Q3).
     - Consolidation keeps such Missions out of the approval-stamp and write-branch bounds:
       `_bound_write_branch` returns `None`; `_approval_is_bounded` excludes them.
     - The measured effect on the three readers (`_mixed_lanes` / canceled attribution, `_recorded_lane_heads`
       / `--dependency-ref`, `_has_review_approval_stamp` / `--attest-approved-reviewed`), as a before/after
       table from T009, plus approved-only consolidate and accept.
     - The correction: the Q3 ruling named `check_write_branch_windows` as the mechanism; it is never
       reached for commit-to-target. The substance of the ruling stands.
  3. Keep the ADR's existing structure untouched otherwise.
- **Files**: the ADR (~30–50 added lines).
- **Validation**: `uv run --frozen pytest tests/architectural/test_no_legacy_terminology.py -q`; read the
  section once as an operator would.

## Definition of Done

- C-010: T007's red unit test is the lane's first commit; T006's characterization is the second, alone,
  green on the base; both precede any `src/` change. T007 is green after T008.
- `_read_lane_head` stamps the target head for stored-`single_branch` commit-to-target Missions only;
  lanes planning lanes remain `not_applicable`; minted `single_branch` unchanged; never raises.
- Every characterization cell proves reachability in the AFTER state: its inputs carry `lane_head` /
  `wp_window` and its reader spy recorded a call on them, so "0 differences" is not no-op passable.
- Every changed verdict is recorded (BEFORE/AFTER comment + ADR table row + completion-note entry for the
  orchestrator's tracer); no previously passing cell silently refuses. No `tracer-*.md` edited from the lane.
- ADR amendment written with the measured table and the mechanism correction.
- NFR-006: `ruff check`, `ruff format --check --force-exclude`, `mypy --strict` clean on changed files, no
  new suppressions; function complexity ≤ 15.
- Tests run and passing (record commands + counts in the PR):
  - `tests/status/` (in particular `test_lane_head.py`, `test_lane_head_single_branch.py`,
    `test_lane_head_commit_to_target.py`)
  - `tests/consolidation/test_commit_to_target_stamp_characterization.py`, `test_write_branch_bound.py`,
    `test_single_branch_evidence_axis.py`, `test_single_branch_stamp_warnings.py`
  - `tests/integration/test_single_branch_approval_windows.py` and the other single_branch window
    integration files
  - `tests/architectural/test_dossier_sha_provenance.py`, `tests/architectural/test_execution_context_parity.py`
  - `make test-fast`. No `make test-full`, no whole `tests/architectural/`.
- Per-subtask completion recorded with `spec-kitty agent tasks mark-status T00x --status done`.

## Risks

- **An existing test pins the old behaviour.** `tests/status/test_lane_head_single_branch.py::test_commit_to_target_single_branch_stays_unstamped`
  asserts `sha is None`. It goes red by design; T008 step 5 inverts it (owned by this WP), citing #7578.
  Never delete it.
- **Verdict change on mixed planning lanes.** Canceled-content attribution now has stamps; a Mission that
  passed may refuse, or vice versa. Mitigation: T006/T009 measure it; STOP rule on any new refusal.
- **Foreign commits on the shared target.** The target head moves with other work, so `open_sha` and
  `lane_head` may span unrelated commits. That is a named residual for IC-03, not a defect here.
- **`open_sha` is `BRANCH_RELATIVE`.** Check `test_dossier_sha_provenance.py` still classifies the keys
  correctly for the new writer.
- **Complexity.** `_read_lane_head` is near its limit; extract the helper rather than adding branches.
- **Harness env leaks** can flip CLI-driven cells; use `monkeypatch.delenv`.

## Reviewer Guidance

- Confirm by `git log --stat` that the first lane commit is T007's red test alone, the second is the
  characterization alone, and both precede the `src/` change.
- Confirm the `lanes` planning-lane case is untouched (C-009) and that minted `single_branch` stamping is
  byte-for-byte unchanged.
- Confirm every changed verdict in the characterization has a BEFORE/AFTER comment and a recorded row, and
  that no passing cell was quietly turned into an expected refusal.
- Confirm reachability: each cell asserts the stamps on its inputs (`STAMPED = True` on the final tip) and a
  reader spy call; temporarily reverting T008 locally must make the stamp assertions fail.
- Confirm the ADR amendment corrects the `check_write_branch_windows` mechanism note and states that the
  approval-stamp and write-branch bounds still exclude these Missions.
- Confirm best-effort semantics: no new path can raise out of `read_lane_head`.
