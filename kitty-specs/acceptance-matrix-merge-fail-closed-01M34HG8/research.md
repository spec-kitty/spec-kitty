# Research: Fail-closed acceptance-matrix merge driver (#4880)

Phase 0 for `acceptance-matrix-merge-fail-closed-01M34HG8`. The bulk of this
"research" is a completed 3-lens investigation (code grounding, architectural
alignment, related tickets) run 2026-09-22 against `skupstream/main @ 793e555224`.

## Decision: fail closed at the shared `_merge_field` mechanism

- **Decision**: On a genuine both-sides-diverged keyed-row field, the matrix
  merge driver raises `RowMatrixMergeError` (→ `typer.Exit(1)` → git leaves the
  conflict → `_merge_branch_into` aborts) instead of returning a
  `_field_conflict_marker(...)` string. `_field_conflict_marker` is deleted.
- **Rationale**: The fail-closed spine already exists in the module
  (`RowMatrixMergeError → Exit(1)`, used for malformed JSON and the intra-side
  duplicate-key guard); the field-conflict path is the one deviation. Raising in
  the shared mechanism closes the class **by construction** (DIRECTIVE_043) for
  both the acceptance and issue matrix drivers, and covers the "lesser variant"
  (prose-only divergence still embedded markers today).

### Alternatives considered

- **Guard only the verdict field (`pass_fail`/`result`) in
  `reconcile_acceptance_matrix_documents`.** Rejected: smaller diff but leaves
  the lesser variant (markers embedded in `description`/`notes`) silently
  committed — the architecture review flagged this as whack-a-field.
- **Read-side rejection only (`from_dict`).** Rejected as the *primary* fix: it
  fires downstream of the corrupting write and today `from_dict` succeeds on a
  marker string (a valid `str`), silently recomputing to `fail`. Kept as
  **defense-in-depth** (FR-004), not the load-bearing fix.
- **Widen `overall_verdict` recompute to raise on unknown tokens.** Deferred:
  wider blast radius; belongs behind the ADR as a follow-up, not this hotfix.

## Recorded-decision reversal (load-bearing)

Fail-closed reverses decisions that are currently contract- and test-pinned;
all amendments land in this mission:

- **ADR `docs/adr/3.x/2026-07-23-2-post-consolidation-deferral-and-external-enforcement.md`** —
  qualify its "no consolidation abort" rule to exclude **gate/verdict**
  artifacts (authoritative → fail closed; non-authoritative prose, e.g.
  review-cycle `.md`, → best-effort embed).
- **Contract `kitty-specs/write-side-seam-matrix-tracer-01KYP3MH/contracts/merge-driver-algorithm.md:29`** —
  the line that calls marker-embed "fail-closed (no consolidation abort)".
- **Completed mission `gate-artifact-merge-driver-unit-gate-01KZPG7V`, FR-004
  negative control** — asserts the `pass_fail`-conflict→`fail` flip is *correct*;
  amend to expect refusal.
- **Test pins**: `tests/merge/test_gate_artifact_merge_drivers_2804.py` (lesser
  variant) and `tests/specify_cli/cli/commands/test_row_aware_merge_driver.py`
  (pass_fail marker embed). Keep `test_a4` (authored out-of-domain value → `fail`
  is a *different, correct* behavior).

Symmetric precedent: the review-cycle driver was deliberately *downgraded* to
non-aborting because it became non-authoritative prose; the identical reasoning
justifies *upgrading* the verdict-bearing acceptance fields to fail-closed.

## History note

**#1424** recorded the opposite historical default (unknown token → fail-*open*
to `pass`); the recompute has since inverted to `fail` (`matrix.py:311-335`).
Not changed here, but noted so the direction is understood.

## Supply-chain security

**N/A** — this mission adds, upgrades, and removes **no** dependencies in any
ecosystem. No registry-authenticity / lifecycle-script / LTS decision to record.

## Adversarial evidence

The three review lenses (python-pedro code grounding, paula-patterns arch
alignment, planner-priti related tickets) served as the pre-plan adversarial
pass. Contested-finding dispositions:

- *Altitude (verdict-field-only vs mechanism)* — **changed** to mechanism-level
  per the whack-a-field argument (operator-confirmed).
- *Direction reverses recorded decisions* — **accepted**; amendments folded into
  scope (FR-006).
- *Issue-matrix also fails closed under the shared mechanism* — **accepted** as
  the coherent rule (operator-confirmed).
- *Closed-mission mutation guard (#4880 fix #2)* — **deferred_with_rationale**:
  distinct vector, own follow-up issue, must consume canonical mission-state.
