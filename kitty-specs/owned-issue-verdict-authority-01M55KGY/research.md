# Research: Owned issue-verdict authority (#6320)

This mission's discovery was performed by a grounding squad against current `main` before
specification. Findings are recorded here; all are code-grounded (file:line verified).

## Decision 1 — Reach the gate, not just placement

- **Decision**: The load-bearing blocker is the fail-closed `resolve_for_write` gate, not
  placement. `do_issue_verdict` calls `resolve_for_write(root, slug, ISSUE_MATRIX)` →
  `mission_runtime.resolve_write_target_or_degrade` **before** any write dir is computed;
  `_mission_meta_exists` reads `read_primary_meta(repo_root, …)` at the repository root,
  returns `False` for an owned-only mission, and with `terminus_write=True` raises fail-closed.
- **Rationale**: `acceptance-verdict` (fixed by #6023) has **no** equivalent gate — it never
  calls `resolve_for_write`. So this fix is strictly wider than #6023 and must make the shared
  `write_target_degrade` helper owned-aware.
- **Alternatives considered**: Only fixing the command's own `_resolve_write_dir` (rejected —
  the gate refuses first, before that code runs).

## Decision 2 — Downstream surfaces are already owned-ready

- **Decision**: Reuse them rather than re-plumb. `resolve_placement_only(..., owned=None)`
  (`mission_runtime/resolution.py`) and `write_issue_matrix(..., owned=None)`
  (`specify_cli/tasks/issue_matrix.py`) already accept the fact. The command and the gate chain
  simply drop it before it reaches them.
- **Rationale**: Minimizes new surface; the fix is a thread-through, not a redesign.
- **Alternatives considered**: New owned-aware write path (rejected — redundant, violates C-001).

## Decision 3 — Mirror the merged #6023 carrier pattern

- **Decision**: Reuse `_owned_checkout.OwnedCheckoutOption` / `resolve_owned_or_refuse` /
  `success_false_envelope` and `LIFECYCLE_OWNED_TOPOLOGIES` (`specify_cli.core.owned_mission`).
  Resolve ownership once in the command, derive `mission_slug`/`feature_dir` from the owned fact
  when present, else fall back to `resolve_mission_handle`.
- **Rationale**: #6023's `acceptance_verdict.py` is the proven template (commits `a6f8add16f`,
  `dccf199f7a`, red-first `c85d75e064`, docs `b82b6a9649`). Fixtures reuse:
  `tests/integration/test_owned_acceptance_authority_6023.py`,
  `test_p0_repro_6023_owned_acceptance_verdict.py`, the owned R/P/S checkout fixtures in
  `test_explicit_checkout_commands.py` / `test_owned_pr_bound_finalization.py`.
- **Alternatives considered**: Bespoke owned resolution (rejected — C-001).

## Decision 4 — Scope includes the coord-owned read path

- **Decision**: Thread owned through `coord_read_dir_for` / `_resolve_read_dir` /
  `_migrate_if_needed` as well as the write path (operator scope decision
  `include-coord-owned-read`, DM-01M55KHFFMTF0N8FE1TWG3BEZ5).
- **Rationale**: #6320's headline case is `single_branch` (where `coord_read_dir_for` returns
  `None` and the owned write dir is what matters), but an owned coord mission must not silently
  read the repository root. The `single_branch` fallback to `feature_dir` must not regress.
- **Alternatives considered**: Write-only (mirror #6023 exactly) — declined by operator.

## Decision 5 — Shared-helper backward-compat is a hard invariant

- **Decision**: `assert_coord_write_materialized` has three other callers
  (`decision_log._resolve_default_target`, `bookkeeping_commit._resolve_bookkeeping_commit_target`,
  `status_transition._resolve_write_target`). The new `owned` param defaults `None` and those
  callers stay byte-identical (FR-005), with a unit test proving it.
- **Rationale**: Prevents collateral change to decision-log / bookkeeping / status-transition
  write targeting.

## Supply-chain / dependencies

No dependency added, upgraded, or removed. `DIRECTIVE_051` / `supply-chain-install-safety`
controls are **not applicable** to this mission (no install surface touched). Recorded here to
satisfy the plan's supply-chain disclosure: silence would be a gap; this is an explicit N/A.

## Adversarial evidence

No security-impacting dependency decision. The grounding squad's findings were re-verified
against HEAD before specification; no contested finding was dropped.
