---
work_package_id: WP02
title: No-implementation attestation
dependencies:
- WP01
requirement_refs:
- FR-006
- C-002
- SC-003
planning_base_branch: issue-6715-lane-evidence-independence
merge_target_branch: issue-6715-lane-evidence-independence
branch_strategy: Planning artifacts for this mission were generated on issue-6715-lane-evidence-independence. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6715-lane-evidence-independence unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-lane-evidence-independence-01M5YHXF
base_commit: 06765b3738efd7735290a40bc77cca9ab4ede281
created_at: '2026-10-27T19:07:34.365165+00:00'
subtasks:
- T006
- T007
- T008
- T009
phase: Phase 2 - Operator override
history:
- at: '2026-10-27T12:10:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: implementer-ivan
authoritative_surface: src/specify_cli/consolidation/no_implementation_attestation.py
create_intent:
- src/specify_cli/consolidation/no_implementation_attestation.py
- tests/consolidation/test_no_implementation_attestation.py
- tests/integration/test_6715_no_implementation_attestation.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/consolidation/no_implementation_attestation.py
- src/specify_cli/consolidation/preflight.py
- src/specify_cli/consolidation/executor.py
- src/specify_cli/cli/commands/consolidate.py
- tests/consolidation/test_no_implementation_attestation.py
- tests/integration/test_6715_no_implementation_attestation.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – No-implementation attestation

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `implementer-ivan`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

- Check `review_ref` via `spec-kitty agent tasks status`; address every item; report with
  `spec-kitty agent tasks add-history WP02 --note "..."`.

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the status event log.]*

---

## Objectives & Success Criteria

- `spec-kitty consolidate --attest-no-implementation <WP> --attest-reason "<why>"` records, before
  the claim is captured, a forced operator self-transition for each named WP with
  `policy_metadata.attestation = "no_implementation"` (the value WP01 reads), and the run then
  lifts `IMPLEMENTATION_MISSING` for exactly those WPs.
- Consolidate output names each WP whose `IMPLEMENTATION_MISSING` was lifted by an attestation
  (also when it was recorded earlier, e.g. by `accept`).
- The attestation never lifts `REVIEW_NOT_INDEPENDENT`, `IMPLEMENTATION_UNREADABLE` or
  `EVIDENCE_WINDOW_UNCOMPUTABLE`, and is never read as the approving actor, an approval, an
  approval stamp, or a review.
- A request without a non-blank `--attest-reason`, or for a WP not in the approved claim, refuses
  and records nothing (exit 2 for the missing reason at the CLI boundary, exit 1 for an invalid
  WP), like `--attest-approved-reviewed`.

## Context & Constraints

- Model: `src/specify_cli/consolidation/approved_attestation.py` and
  `canceled_attestation.py`; `executor._record_operator_attestations` and its helpers;
  `cli/commands/consolidate.py` flag plumbing for `--attest-approved-reviewed` (~L824, L999,
  L1087, L1193, L1378, L1403–1430).
- Record through `coordination.status_transition.emit_status_transition_transactional` with
  `force=True`, `reason_source=OPERATOR_REASON_SOURCE`, reason prefix
  `operator attests no implementation is owed: `, evidence
  `{"review": {"reviewer": actor, "verdict": "approved", "reference": "operator-attestation:<WP>"}}`
  (the events contract needs evidence into approved/done), `to_lane` = the WP's current lane.
- Verified in research: `approved_bound._is_approval` does not treat a forced `approved ->
  approved` move outside `in_review` as an approval, so the approval bound needs no change. Pin
  it with a test anyway.
- `preflight._latest_actor_for_transition` (~L514) must skip this attestation like it skips
  `approved_reviewed` (else the operator becomes "the approver"). `_review_force_counts` should
  discount it so it does not feed the hollow-review force-count warning.
- `--attest-reason` is shared with the other attestation flags (one reason per run).
- Consolidate's `--dry-run` path: print the same "would record" notice shape as the other flags
  (`dry_run_attestation_notice`).

## Branch Strategy

- **Planning base branch**: issue-6715-lane-evidence-independence
- **Merge target branch**: issue-6715-lane-evidence-independence

Run `spec-kitty agent action implement WP02 --agent claude --mission lane-evidence-independence-01M5YHXF`.

## Subtasks & Detailed Guidance

### Subtask T006 – Red-first tests

- `tests/consolidation/test_no_implementation_attestation.py` (unit, on a status log built
  through the transactional seam in a temp repo, or the existing helpers under
  `tests/consolidation/`):
  - validate: blank reason refuses; WP not approved/done refuses; nothing recorded on refusal.
  - record: event has `force`, operator `reason_source`, `policy_metadata.attestation ==
    "no_implementation"`, `to_lane == from_lane`.
  - `_independent_reviewer_confirmed` result is unchanged by an attestation recorded after the
    approval (independent stays independent; self stays self).
  - `approved_bound.approval_stamp` returns the review approval's stamp, not the attestation's.
- `tests/integration/test_6715_no_implementation_attestation.py` (CLI, coord): hollow WP approved
  by a different reviewer with `--force` ⇒ consolidate refuses; with
  `--attest-no-implementation WP02 --attest-reason "docs-only"` ⇒ rc 0, WP02 `done`, output names
  WP02; self-approved hollow WP + attestation ⇒ still refuses `REVIEW_NOT_INDEPENDENT`;
  attestation without reason ⇒ exit 2, nothing recorded.
- Commit the tests first.

### Subtask T007 – `no_implementation_attestation.py`

- `validate_no_implementation_request(wp_ids, reason, *, claim_lanes) -> tuple[str, ...]`
  (raises `AttestationError`), `plan_no_implementation_attestations(feature_dir, lanes_manifest,
  wp_ids, reason, *, excluded_canceled_wp_ids) -> dict[str, str]` (WP -> current lane; reuse
  `approved_attestation.approved_claim_lanes`), `record_no_implementation_attestation(...)`.
- Import the constant `NO_IMPLEMENTATION` and flag name from `wp_evidence` (WP01) so the reader
  and writer share one value. Define `ATTEST_NO_IMPLEMENTATION_FLAG =
  "--attest-no-implementation"` in `wp_evidence` too if WP01 did not (out-of-map one-liner with
  rationale), so accept (WP03) and consolidate import one name.

### Subtask T008 – Exclusions

- `preflight._latest_actor_for_transition`: skip events whose
  `policy_metadata[ATTESTATION_KEY] == NO_IMPLEMENTATION`.
- `preflight._review_force_counts`: discount them.
- Docstrings updated; keep complexity ≤ 15.

### Subtask T009 – Consolidate wiring and output

- Add `--attest-no-implementation` (repeatable, `list[str] | None`) to `consolidate`, thread it
  like `attest_approved_reviewed` into `_run_lane_based_consolidation_locked` and
  `_record_operator_attestations` (validate all requests first, then record; refusal records
  nothing).
- CLI boundary: without non-blank `--attest-reason` ⇒ exit 2 with
  `--attest-no-implementation requires --attest-reason "<why no implementation is owed>"`.
- Output: after the claim is built (or at record time and for pre-existing attestations),
  print `⚠️  <WP>: IMPLEMENTATION_MISSING lifted by operator attestation (<reason>)` for every
  attested WP whose evidence was actually missing. Simplest correct place: the claim builder
  (WP01) exposes the lifted WP ids on `ApprovedWpCommitSet` or a helper in `wp_evidence`
  returns them; render in the executor. Coordinate with WP01's API; if a field must be added in
  `reconciliation.py`, record the out-of-map edit with a rationale.

## Test Strategy

- `uv run --frozen pytest tests/consolidation tests/integration/test_6715_no_implementation_attestation.py tests/specify_cli/cli/commands -k "consolidate or attest" -q`
  plus `tests/consolidation/test_single_rollback_authority.py`.
- ruff, ruff format `--force-exclude`, mypy on touched files.

## Risks & Mitigations

- Adding a forced transition can surface the hollow-review warning; T008 discounts it.
- `consolidate.py` is large; keep new helpers small and tested.

## Review Guidance

- The attestation can only ever lift `IMPLEMENTATION_MISSING`; grep that no other code path reads it.
- No change in `approved_bound.py`.

## Progress & Status

- `spec-kitty agent tasks add-history WP02 --note "<what you did>"`
- `spec-kitty agent tasks move-task WP02 --to <status>`
