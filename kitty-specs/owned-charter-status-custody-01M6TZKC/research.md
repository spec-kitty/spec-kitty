# Research: Owned Mission coordination status charter custody

## Current-state verification

- Fetched `origin/main` at `f47114a75f3d85b1ebc7f1fb7c534aab4133a23c` on 2026-11-07.
- Re-read the completed investigation and the #6788 note under `research_notes/Main Red Issue Causes/`.
- Inspected every open PR file list through the GitHub pulls-files API. None touches `owned_charter.py`, the owned prompt/runtime integration files, or the owned-worktree e2e; no equivalent fix exists. PRs #7273/#7287 retain their own scopes.
- Current `origin/main` still has the resolved-path equality refusal in `charter_scope_for_owned`; `runtime_bridge` still selects canonical `STATUS_STATE.read_dir` when materialized.

## Decision

Use the existing placement facade only on the unequal-path arm. Admit `feature_dir` exactly when it resolves to the same owned Mission's canonical `STATUS_STATE.read_dir`, then resolve charter scope from the validated owned root and primary Mission directory as before.

## Rationale

The defect is too-narrow custody validation, not incorrect runtime status placement. `mission_context_for` is the canonical authority for artifact identity and supports declared-but-unmaterialized coordination without weakening EMPTY/NONE/DELETED refusals. Restricting the new lookup to inequality preserves the old fast path.

## Alternatives considered

- **Thread both directories from `runtime_bridge`**: rejected as unnecessary signature widening for one guard.
- **Hardcode or string-match coordination worktree paths**: rejected because it duplicates placement authority and is platform/topology fragile.
- **Drop the feature-directory guard or substitute `owned.mission_dir` unconditionally**: rejected because it hides genuine cross-Mission context conflicts.
- **Re-pin the installed-CLI e2e to accept refusal**: rejected because the reproduction is a valid user workflow.

## Focused planning lens

`architect-alphonso` profile resolved through the CLI. The boundary review found no new architectural authority, dependency, contract, storage migration, or gate requirement. Planner `planner-priti` scoped one WP with test-first sequencing and no unrelated campsite work.

## Remaining verification gap

Local focused success cannot prove nightly recovery. All 20 installed-CLI parameters and the unrelated startup-budget row remain for the relevant merged-commit nightly; #6788 stays referenced, not claimed closed by this slice.
