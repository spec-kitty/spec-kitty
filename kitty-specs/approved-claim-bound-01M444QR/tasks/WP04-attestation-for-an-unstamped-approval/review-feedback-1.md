# WP04 review feedback, cycle 1 (reviewer: reviewer)

Verdict: **changes requested**. Lane `kitty/mission-approved-claim-bound-01M444QR-lane-d`, commits `89c69213ec`, `50aa1daf2a`, `7087a11b92`.

What is good and should stay: red-first commit holds only the test and imports only existing symbols; validation happens before anything is recorded; the stamped-approval refusal records nothing; `--dry-run` records nothing; the snapshot `review` / `review_result` slots are not overwritten by the attestation; ruff, format, C901 clean; mypy has only the pre-existing `untyped-decorator` on `consolidate`.

## 1. [BLOCKER] A re-attestation lifts `LANE_MOVED_AFTER_APPROVAL` (FR-007, contract)

`src/specify_cli/consolidation/approved_attestation.py:71-81` accepts any work package whose newest approval is an earlier attestation, whatever the lane holds now.

Reproduced through the real CLI (lanes topology):

1. strip WP01's stamps, record an attestation (bound = tip A);
2. add an unreviewed content commit on lane-a (tip B);
3. `consolidate` refuses with `LANE_MOVED_AFTER_APPROVAL` (correct);
4. `consolidate --attest-approved-reviewed WP01 --attest-reason "checked"` exits 0 and `src/alpha/late.py` is on the target.

This contradicts FR-007 ("a commit made after an attestation still refused, so that review stays the only way to approve content"), the contract table (`LANE_MOVED_AFTER_APPROVAL`: attestation lifts it: no), plan D-5 ("it has no approval stamp. A stamped work package is refused"), and three texts this work package ships: the module docstring (`approved_attestation.py:7-9`, "no code path leads from the flag to them"), the flag help ("Does not lift a refusal for commits made after a recorded approval") and `docs/api/cli-commands.md` ("Not overridable: `--attest-approved-reviewed` never lifts it"). The same path lifts `APPROVAL_STAMP_NOT_ON_LANE` after a lane rewrite.

Required: keep the repeatability the prompt asks for, and only that. Accept a work package whose newest approval is an attestation only while the lane holds nothing beyond that attestation's bound (the earlier attestation's `lane_head` is still the lane tip, or `approved_bound.check_lane` reports no refusal for it); otherwise refuse with a text that sends the work package back for review, and record nothing. Add one e2e test: attest, add a commit, repeat the attest command, assert refusal, log unchanged, target unchanged.

## 2. [BLOCKER] The attestation silences the hollow-review merge gate

The record is a forced `approved -> approved` event whose actor is the operator. `consolidation/preflight.py::_independent_reviewer_confirmed` reads the latest actor of a transition into `approved`, so after the attestation it sees the operator as an independent reviewer.

Reproduced through the real CLI: WP01 force-moved back and force-approved by its own implementer (`force_count=2`).

- stamped, no attestation: `MERGE WARNING: Hollow reviews detected ... WP01: force_count=2`;
- stamps stripped, `--attest-approved-reviewed WP01`: no warning at all, exit 0.

The module's own docstring says an attestation is not a review approval. It must not answer a gate that asks whether an independent review happened.

Required: the hollow-review check must not count an `approved_reviewed` attestation as the approving transition (skip events carrying `policy_metadata.attestation` in `_latest_actor_for_transition`, or an equivalent that keeps the change small). `preflight.py` is outside the owned files: make it a recorded out-of-map edit, or ask the orchestrator to route it. Add one test that pins the warning still appears after an attestation.

## 3. [MAJOR] Regression in an existing test

`tests/consolidation/test_consolidate_options.py::test_fields_mirror_the_typer_command_parameters` fails on the lane (`At index 18 diff: 'attest_reason' != 'attest_approved_reviewed'`). `ConsolidateOptions.attest_approved_reviewed` (`cli/commands/consolidate.py:852`) is declared after `attest_reason`, the typer parameter (`:936`) before it. Put them in the same order. This file is in `tests/consolidation`, which the prompt's test list did not name; run that directory before handing back.

## 4. [MINOR] `docs/api/cli-commands.md` code table order

`APPROVAL_STAMP_NOT_ON_LANE` and `LANE_MOVED_AFTER_APPROVAL` were inserted after `COORD_MOVED_AFTER_LANDING`; the table is otherwise alphabetical.

## 5. [NOTE] Changed existing text

`--attest-reason has no effect without --attest-canceled-superseded.` gained ` or --attest-approved-reviewed`, and the `--attest-reason` help changed. Both were asked for by T017; no test pins the old sentence. Accepted, say so in the hand-back.

## Not yours (reported to the orchestrator)

- `tests/terminus/canceled_dependency_support.py::strip_lane_head_stamps` (behind the frozen `strip_approval_stamps`) writes `"\n"` into an empty log copy, so a second call fails with `JSONDecodeError`. Your local `_strip_stamps` is an acceptable workaround until WP07.
- `test_no_dead_symbols.py` still flags only `approved_bound_refusal` and `lane_tips_moved_refusal` (other lanes).
