# Mission Review Report: coordination-doctor-branch-safety-01M35EN8

**Reviewer**: codex, using reviewer-renata doctrine
**Date**: 2026-09-22
**Mission**: `coordination-doctor-branch-safety-01M35EN8` — Coordination Doctor Branch Safety
**Baseline commit**: `6f82d1ec5a415fae113e188454a81a95313a25cf`
**HEAD at review**: `048c4527870ce491e42af2b12eb06e302b595fde`
**WPs reviewed**: WP01

## Gate Results

### Gate 1 — Contract tests

- Command: `SPEC_KITTY_ENABLE_SAAS_SYNC=1 uv run --frozen pytest tests/contract -v --tb=short`
- Exit code: 0
- Result: PASS
- Notes: 246 passed, 10 skipped, 1 warning in 217.02s.

### Gate 2 — Architectural tests

- Command: `uv run --frozen pytest tests/architectural -n auto --dist loadfile -q -p no:cacheprovider --tb=short`
- Exit code: 0
- Result: PASS
- Notes: 2,808 passed, 4 skipped, 2 xfailed, 2 warnings in 451.12s. The
  complete gate was rerun under xdist after a serial run proved impractically slow.

### Gate 3 — Cross-repo E2E

- Command: `SPEC_KITTY_ENABLE_SAAS_SYNC=1 SPEC_KITTY_REPO=<spec-kitty-checkout> SK_E2E_SPEC_KITTY_REPO=<spec-kitty-checkout> uv run --frozen pytest scenarios -v --tb=short`
- Exit code: 0
- Result: PASS
- Notes: 5 passed in 545.03s against the merged CLI checkout. The review skill still
  names retired `scenarios/saas_sync_enabled.py` as a mandatory floor, but E2E commit
  `e59564b` and E2E issue #4 document its intentional deletion with the removed sync
  transport. Doctrine drift is tracked in spec-kitty issue #4949.

### Gate 4 — Issue Matrix

- File: `kitty-specs/coordination-doctor-branch-safety-01M35EN8/issue-matrix.md`
- Rows: 1
- Empty / `unknown` verdicts: 0
- `in-mission` verdicts surviving mission `done`: 1 (`#4920`)
- Result: FAIL
- Notes: Line 5 still marks #4920 `in-mission` after WP01 reached `done`. The runtime
  accepted event-sourced verdicts for #4506 and #4873, but the legacy canonical
  failover artifact neither materializes those rows nor terminalizes #4920.

## FR Coverage Matrix

| FR ID | Description | WP Owner | Test evidence | Adequacy | Finding |
|-------|-------------|----------|---------------|----------|---------|
| FR-001 | Validate symbolic HEAD before mutation | WP01 | wrong-branch real-Git regression | ADEQUATE | — |
| FR-002 | Block mismatch/detached state with no mutation | WP01 | wrong-branch snapshots four refs; canonical helper maps detached HEAD to mismatch | ADEQUATE | Direct detached acceptance coverage is absent but the shared path is constrained. |
| FR-003 | Print success only after declared-ref postcondition | WP01 | `test_fix_one_staleness_requires_declared_ref_postcondition` | ADEQUATE | — |
| FR-004 | Preserve safe correct-branch fast-forward | WP01 | existing strict-ancestor real-Git control | ADEQUATE | — |

Deleting the new branch guard makes the wrong-branch test advance the unrelated ref;
deleting the postcondition makes its focused test print false success. Both tests
therefore constrain live production behavior rather than synthetic output shapes.

## Drift Findings

### DRIFT-1: Completed mission retains a non-terminal issue verdict

**Type**: GOVERNANCE ARTIFACT DRIFT
**Severity**: HIGH
**Spec reference**: Gate 4 issue-matrix contract
**Evidence**: `issue-matrix.md:5` records #4920 as `in-mission` while WP01 is `done`.

The matrix itself states that no `in-mission` row may survive close. This is a hard
mission-review failure even though the product implementation is correct. The matrix
must be materialized with terminal verdicts and the gate rerun before publication.

## Risk Findings

### RISK-1: Review independence is profile-based, not actor-independent

**Type**: REVIEW-INDEPENDENCE
**Severity**: LOW
**Location**: `status.events.jsonl` review transition at 2026-09-22T21:51:46Z

The same `codex` tool actor implemented WP01 and later approved it under the
`reviewer-renata` profile. The event contains a distinct reviewer role and complete
evidence, but no independent second actor. The full post-merge gates reduce product
risk; future high-risk ref-mutation work should obtain actor-independent review when
the operating environment permits it.

## Silent Failure Candidates

No new silent-default path was introduced. Existing `return None` branches remain
documented no-op conditions. The new mismatch and postcondition paths return structured
error findings with the existing stable machine code.

## Security Notes

No blocking security finding. The new Git invocation remains a list-form subprocess
with `shell=False` semantics. Branch identity is checked before mutation, and the
declared ref is re-read after mutation before success output. No credential, network,
path-construction, branch-switch, reset, or user-state-discarding behavior was added.

## Final Verdict

**FAIL**

### Verdict rationale

The merged code accurately realizes FR-001 through FR-004, the focused and owning
tests are adequate, and all executable contract, architecture, and current cross-repo
E2E gates pass. Publication is nevertheless blocked because Gate 4 is a hard gate and
the canonical legacy issue matrix retains #4920 as `in-mission` after completion.

### Open items

- Repair and revalidate the mission issue matrix: terminalize #4920 and materialize
  the already classified #4506 and #4873 follow-ups.
- Update stale Gate 3 doctrine under #4949 so it no longer requires the deliberately
  retired SaaS-sync scenario.
- Baseline-only linked-worktree fast-suite failures remain tracked in #4873.
- Baseline-only Ruff format ratchet debt remains tracked in #4506.

## Retrospective Reminder

The runtime terminus authored
`kitty-specs/coordination-doctor-branch-safety-01M35EN8/retrospective.yaml`.
After the blocking issue-matrix repair and review rerun, use
`spec-kitty retrospect summary` for cross-mission aggregation and
`spec-kitty agent retrospect synthesize --mission coordination-doctor-branch-safety-01M35EN8`
to inspect staged proposals; synthesis is dry-run by default.
