---
work_package_id: WP04
title: Attestation for an unstamped approval
dependencies:
- WP02
requirement_refs:
- FR-006
- FR-007
planning_base_branch: issue-5668-approved-claim-bound
merge_target_branch: issue-5668-approved-claim-bound
branch_strategy: Planning artifacts for this mission were generated on issue-5668-approved-claim-bound. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5668-approved-claim-bound unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-approved-claim-bound-01M444QR
base_commit: 1571015860025be91d106c4f550b3c6b6b1a6246
created_at: '2026-10-04T21:47:08.286452+00:00'
subtasks:
- T016
- T017
- T018
- T019
- T020
phase: Phase 3 - Completing the fix
history:
- at: '2026-10-04T19:45:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/consolidation/
create_intent:
- src/specify_cli/consolidation/approved_attestation.py
- tests/consolidation/test_approved_attestation.py
- tests/terminus/test_unstamped_approval_attestation.py
execution_mode: code_change
owned_files:
- src/specify_cli/consolidation/approved_attestation.py
- src/specify_cli/consolidation/executor.py
- src/specify_cli/cli/commands/consolidate.py
- docs/api/cli-commands.md
- tests/specify_cli/cli/commands/test_merge_cli_golden.py
- tests/consolidation/test_approved_attestation.py
- tests/terminus/test_unstamped_approval_attestation.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---
# Work Package Prompt: WP04 – Attestation for an unstamped approval

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt. If the skill is not available, run `.venv/bin/spec-kitty agent profile show python-pedro` and apply the resolved profile.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task.** Check the `review_ref` field in the event log (`.venv/bin/spec-kitty agent tasks status --mission approved-claim-bound-01M444QR`). If this work package was returned from review, every feedback item is part of your work.

---

## Objectives & Success Criteria

An operator can land a mission whose approval carries no stamp, and only that.

- `consolidate --attest-approved-reviewed <WP> --attest-reason "<why>"` records an operator attestation in the status log; the lane head at that moment becomes the work package's bound; the mission consolidates.
- A commit added after the attestation refuses with `LANE_MOVED_AFTER_APPROVAL`.
- An attestation for a work package that already has an approval stamp, or that is not in the approved claim, is refused and nothing is recorded.
- The CLI reference documents the flag.

Implementation command: `.venv/bin/spec-kitty agent action implement WP04 --agent claude --mission approved-claim-bound-01M444QR`

## What WP02 delivered (read before the subtasks)

WP02 is approved. These exist on your lane's base; call them, do not redefine or edit them:

- `consolidation/approved_bound.py`: `APPROVED_REVIEWED`, `ATTEST_APPROVED_FLAG`, `BoundRefusalCode`, `BoundRefusal.render()`, `approval_stamp(events, wp_id)`, `check_lane(...)`, `commits_beyond`, `content_commits`. The printed recovery command is `spec-kitty agent tasks move-task <WP> --to in_progress --mission <mission>`.
- `consolidation/reconciliation.py`: `approved_bound_refusal(repo_root, feature_dir, lanes_manifest, *, coord_base_ref, excluded_canceled_wp_ids=(), excluded_window_base=None, event_log=None) -> str | None` and `lane_tips_moved_refusal(repo_root, lanes_manifest, *, validated_tips, anchor_shas, planning_prefix, approved_wp_ids=None) -> str | None`. The claim carries `ApprovedWpCommitSet.bound_lane_tips`.
- Run state (`run_state.py`, set in `phase_claim._capture_reconciliation_claim`): `validated_lane_tips: dict[str, str]`, `bound_anchor_shas: tuple[str, ...]`.
- `tests/terminus/post_approval_support.py` (frozen: import it, do not edit it): `build_post_approval_mission(tmp_path, "lanes" | "coord")` returning a two-lane `CoordMission`, `add_post_approval_commit(mission, lane=...)`, `strip_approval_stamps(mission, wp_id)`, `rework_and_reapprove(mission, wp_id)`, `lane_worktree`. Test helpers that re-record approvals at the current lane tips: `restamp_approvals_at_lane_tips` (`tests/terminus/conftest.py`), `tests/consolidation/approval_stamps.py`.
- `tests/architectural/test_no_dead_symbols.py` is red on the base for five names that have no `src/` caller yet: `APPROVED_REVIEWED`, `ATTEST_APPROVED_FLAG`, `approval_stamp` (WP04 imports them), `lane_tips_moved_refusal` (WP03), `approved_bound_refusal` (WP05). Your work package clears its own names; the others stay red on your lane until the lanes are consolidated. Do not add an allowlist entry.
- Running mypy on one file alone reports a spurious `no-any-return` because of the repository's `follow_imports = "skip"` override; run `.venv/bin/mypy --strict src/specify_cli/consolidation` (the package) instead.

- **For this work package**: `approval_stamp` returns only the stamp. To tell a real approval from an earlier attestation (T016), add the small `approval_source` function to `approved_bound.py` as the prompt says (out-of-map, recorded). WP02's reviewer noted that a work package with an **unstamped** canceled attestation on a mixed lane now gets no covered point; that is the canceled flow and not yours to change.

## Context & Constraints

Read first, in this order:

1. `.kittify/charter/charter.md` (binding) and `spec-kitty charter context --action implement --json`.
2. `kitty-specs/approved-claim-bound-01M444QR/spec.md`, `plan.md` (sections D-1 to D-6), `research.md`, `data-model.md`, `contracts/consolidate-refusals.md`.
3. `kitty-specs/approved-claim-bound-01M444QR/research/code-grounding.md` for file and line references. Line numbers were taken at `9adc68803f`; re-locate by symbol name (`codegraph explore "<symbol>"`).

Rules that bind every work package of this mission:

- **CLI binary**: always `.venv/bin/spec-kitty` and `.venv/bin/python -m pytest`. The bare `spec-kitty` on PATH is a stale install. Never `uv run`.
- **No heavy suites**: never `make test-full`, never a bare `tests/architectural/` run. Run the files named in this prompt.
- **Test economy**: each new test must pin one distinct behaviour. No test per helper, no duplicate of an existing pin. Prefer extending a parametrized test over adding a sibling.
- **Quality**: `ruff check` and `mypy --strict` clean on changed files, complexity <= 15, no new `# noqa` or `# type: ignore`. Format check: `uv run --frozen ruff format --check --force-exclude <changed files>`.
- **Status imports**: import status symbols only through the `specify_cli.status` facade. Git reads go through `consolidation/git_probes.py`; do not shell out to git directly from new consolidation code.
- **Byte-identity**: no existing refusal code or text changes. New texts are additions.
- **No fail-open**: an absent approval stamp is never replaced by the lane tip, in product code or by a test switch (spec C-003).
- **Terminology**: Mission and work package; `--mission`, never `--feature`.
- **Commits**: conventional messages; every commit ends with the trailer `Co-Authored-By: Stijn Dejongh <stijn.dejongh@sddevelopment.be>`. No AI model or tool identifiers in commit messages.
- **Tracers**: do not edit `kitty-specs/approved-claim-bound-01M444QR/tracers/*.md` in a lane worktree (parallel lanes would conflict). Put tooling friction and unplanned design decisions in this prompt's Activity Log and in your hand-back report; the orchestrator records them.

## Branch Strategy

- **Strategy**: see `branch_strategy` in the frontmatter (written by `finalize-tasks`)
- **Planning base branch**: issue-5668-approved-claim-bound
- **Merge target branch**: issue-5668-approved-claim-bound

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`. Execution worktrees are allocated per computed lane from `lanes.json`; use the workspace path `spec-kitty agent action implement` resolves, do not construct it.

## Subtasks & Detailed Guidance

**Order (red-first)**: write the first test of T018 (refuse, attest, consolidate) before T016 and T017 and commit it red: `test(consolidation): reproduce an unstamped approval with no attest path`. It fails at the attest step because the flag does not exist.

### Subtask T016 – `approved_attestation.py`

- **Purpose**: validate and record the attestation (plan D-5, `data-model.md`), parallel to `canceled_attestation.py`.
- **Steps**:
  1. Create `src/specify_cli/consolidation/approved_attestation.py`. Import `APPROVED_REVIEWED`, `ATTEST_APPROVED_FLAG` and `approval_stamp` from `approved_bound`; import `ATTEST_REASON_FLAG`, `AttestationError` and `ATTESTATION_KEY` from where `canceled_attestation.py` gets or defines them. One definition of each.
  2. `validate_approved_attestation_request(wp_ids, reason, *, events, claim_lanes: Mapping[str, str]) -> tuple[str, ...]` where `claim_lanes` maps each work package in the approved claim to its current lane (`approved` or `done`):
     - empty request returns `()`;
     - blank reason raises `AttestationError`: `--attest-approved-reviewed requires --attest-reason "<why the lane content is the reviewed content>".`;
     - a work package not in `claim_lanes` raises: `... applies only to an approved work package; not approved: <ids>. Nothing was recorded.`;
     - a work package whose latest approval source is a **real** `approved` event with a stamp raises: `... applies only to an approval with no recorded lane head; <ids> already has one. Move it back for review instead. Nothing was recorded.`
     - a work package whose latest approval source is an earlier `approved_reviewed` attestation is accepted and re-recorded, as the canceled attestation flow re-records on a re-run (`executor._record_operator_attestations`). A run that failed for an unrelated reason after attesting must be repeatable with the same command. Expose the distinction from `approved_bound` (for example `approval_source(events, wp_id) -> tuple[str | None, bool]` returning the stamp and whether it came from an attestation) instead of re-reading events here; adding that small function to `approved_bound.py` is an out-of-map edit in a dependency's file, record it.
  3. `record_approved_reviewed_attestation(*, repo_root, feature_dir, mission_slug, wp_id, current_lane, reason, actor) -> StatusEvent | None`: build a `TransitionRequest` like `record_canceled_superseded_attestation` does, with `to_lane=current_lane`, `force=True`, `reason=f"operator attests approved content reviewed: {reason.strip()}"`, `reason_source=OPERATOR_REASON_SOURCE`, `policy_metadata={ATTESTATION_KEY: APPROVED_REVIEWED}`, and the evidence the events contract requires for `approved` and `done` (`spec_kitty_events` rejects `to_lane in {approved, done}` with no evidence). Find how the consolidation's own `approved -> done` builds its evidence (`cli/commands/consolidate.py::_mark_wp_merged_done`) and how a review approval does, and pass a truthful value: the reviewer is the operator, the reference is the attestation. Emit through `emit_status_transition_transactional`.
  4. The pipeline stamps `lane_head` itself for a lane-mapped work package. If the stamp could not be taken, the next claim still refuses with `APPROVAL_STAMP_MISSING`; that is correct, do not paper over it.
  5. A dry-run notice function like `dry_run_attestation_notice`, or generalise the existing one to take the flag name (out-of-map edit in `canceled_attestation.py`; prefer generalising over copying).
- **Files**: `src/specify_cli/consolidation/approved_attestation.py`.

### Subtask T017 – CLI flag, recording, and the refusal sentence

- **Purpose**: wire the flag end to end.
- **Steps**:
  1. `src/specify_cli/cli/commands/consolidate.py`: add `--attest-approved-reviewed` (repeatable, `list[str]`) next to `--attest-canceled-superseded`, with help text: "Attest that an approved work package whose approval recorded no lane head was reviewed as it stands on its lane. Requires --attest-reason. Does not lift a refusal for commits made after a recorded approval." `--attest-reason` serves both flags: one reason applies to every attestation of the run. Update its help text to say so. `_validated_attestation_flags` prints messages that name only `--attest-canceled-superseded` (for example the "has no effect without" message): when only the old flag is involved those texts stay byte-identical; add the wording for the new flag as new branches or a parametrized message, and make "`--attest-reason` without either flag" name both.
  2. Thread the value the way the canceled attestation is threaded (validated early at the two sites that validate `--attest-canceled-superseded`, carried on the run state, recorded in `executor.py` where `_record_operator_attestations` records the canceled ones, before the claim is captured). Keep `_run_lane_based_consolidation` at complexity <= 15 (it was 12 at grounding time): extend the existing recording helper, do not add branches to the caller.
  3. `claim_lanes` comes from the Lamport snapshot the same way the claim's membership does (`_APPROVED_MEMBERSHIP_LANES`); reuse an existing reader, do not re-derive membership.
  4. `phase_claim._claim_refusal_change_sentence` and `_exit_on_claim_integrity_refusal` already report recorded attestations; make sure approved attestations recorded by this run are included in `run.recorded_attestations` so the sentence stays true. `phase_claim.py` belongs to WP02; you should not need to edit it.
  5. `--dry-run` with the flag prints the notice and records nothing.
- **Files**: `cli/commands/consolidate.py`, `consolidation/executor.py`, `consolidation/phase_claim.py`.

### Subtask T018 – End-to-end test

- **Purpose**: spec User Story 2, through `consolidate`.
- **Steps** (`tests/terminus/test_unstamped_approval_attestation.py`, markers `integration`, `git_repo`, `regression`):
  1. Build the WP02 mission, then strip the stamps with `canceled_dependency_support.strip_lane_head_stamps` (or the smallest variant that strips only the `approved` events' stamps).
  2. One test walks the story in order, asserting at each step: `consolidate` refuses with `APPROVAL_STAMP_MISSING`, names WP01 and both remedies, target unchanged; `consolidate --attest-approved-reviewed WP01` with no reason is refused; with a reason the attestation event is in the status log (`policy_metadata.attestation == "approved_reviewed"`, a `lane_head` equal to the lane tip, the reason) and the run exits 0 with the banner.
  3. A second test: after attesting (use `--dry-run`-free flow up to the attestation by letting the first consolidate be refused for another unstamped work package, or record the attestation through `record_approved_reviewed_attestation` directly), add a lane commit and assert `LANE_MOVED_AFTER_APPROVAL`.
  4. A third test: `--attest-approved-reviewed WP01` on a stamped mission with a post-approval commit is refused with the "already has one" text and the status log is unchanged.
  5. A fourth test (spec US2 scenario 5): a work package forced to `done` with no `approved` event refuses with `APPROVAL_STAMP_MISSING`.
  6. Re-run: on the two-lane mission strip both work packages' stamps, attest only WP01 (the run records the attestation and then refuses for WP02), then repeat the command attesting WP01 and WP02. It must be accepted: the earlier attestation of WP01 is re-recorded, not refused as "already has one".
  7. `--dry-run` with the flag prints the notice and the status log is unchanged (one assertion in the first test before the real run).
- **Files**: `tests/terminus/test_unstamped_approval_attestation.py`.

### Subtask T019 – Unit tests

- **Purpose**: the validation branches not reached by T018.
- **Cases** (`tests/consolidation/test_approved_attestation.py`): only what T018 does not reach: the `AttestationError` branch for a work package that is not in the approved claim; the recorded event's shape for a `done` work package (T018 covers `approved`). Do not repeat WP02's `approval_stamp` tests.
- **Files**: `tests/consolidation/test_approved_attestation.py`.

### Subtask T020 – CLI reference and flag inventory

- **Steps**:
  1. `docs/api/cli-commands.md`: document the flag under `consolidate`, next to `--attest-canceled-superseded`. If the file is generated, regenerate it with the repository's generator instead of hand-editing (look for the generator named in the file header or in `tests/architectural/test_docs_cli_reference_parity.py`).
  2. `tests/specify_cli/cli/commands/test_merge_cli_golden.py`: add the flag to the pinned inventory.
  3. Run `tests/architectural/test_docs_cli_reference_parity.py` and `tests/architectural/test_no_legacy_terminology.py`.
- **Files**: `docs/api/cli-commands.md`, `tests/specify_cli/cli/commands/test_merge_cli_golden.py`.

## Test Strategy

```bash
.venv/bin/python -m pytest tests/terminus/test_unstamped_approval_attestation.py tests/consolidation/test_approved_attestation.py tests/consolidation/test_canceled_attestation.py -q
.venv/bin/python -m pytest tests/specify_cli/cli/commands/test_merge_cli_golden.py tests/architectural/test_docs_cli_reference_parity.py tests/architectural/test_no_legacy_terminology.py -q
.venv/bin/python -m pytest tests/cli -q -k "consolidate or merge" -n auto --dist loadfile
.venv/bin/python -m pytest tests/terminus/test_mixed_lane_fail_recovery_and_attestation.py tests/consolidation/test_executor_phase_boundary.py -q
```

## Risks & Mitigations

- **Evidence contract.** A forced self-transition to `approved` or `done` without evidence is rejected by `spec_kitty_events`. Find the truthful evidence shape before writing the recorder.
- **Status-write guard.** The transactional shell refuses when the coordination worktree's log diverged (`COORD_STATUS_SURFACE_DIVERGED`); surface that error as it is, do not catch it.
- **Complexity** of the consolidate command function and the executor entry: extend helpers.
- **Parallel work packages.** WP03 and WP05 run beside you. Do not edit `reconciliation.py`, `phase_claim.py`, `run_state.py`, `phase_gate.py` or `tests/terminus/post_approval_support.py`.
- **Review slot.** Check that the attestation's evidence does not overwrite the review evidence the later `approved -> done` record is built from; if it does, say so in the hand-back.

## Review Guidance

- Attestation cannot lift `LANE_MOVED_AFTER_APPROVAL` or `APPROVAL_STAMP_NOT_ON_LANE`: there is no code path from the flag to those reasons.
- The attestation is a status event in the mission's log, written through the transactional shell, never a side file.
- `--attest-canceled-superseded` behaviour and texts are byte-identical.
- The flag is in the CLI reference and the golden inventory.
- Confirm the implementer ran `ruff check`, the format check and `mypy --strict` on the changed files and that all were clean.
- Reviewer and implementer are different agents. Judge each new test: does it pin a distinct behaviour, and would it fail if the behaviour were removed?

## Activity Log

> Entries are appended in chronological order (oldest first). Format: `- YYYY-MM-DDTHH:MM:SSZ – <agent_id> – <action>`.

- 2026-10-04T19:45:00Z – system – Prompt created.

### Updating Status

Status is managed via `status.events.jsonl`. Use `spec-kitty agent tasks move-task <WPID> --to <status> --mission approved-claim-bound-01M444QR` to change WP status, and `spec-kitty agent tasks mark-status <Txxx> --status done --mission approved-claim-bound-01M444QR` for subtasks.
