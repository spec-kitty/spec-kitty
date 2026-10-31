# Discovery — protected `--target` override (#6464)

Baseline: `origin/main` @ `35318ef51c` (2026-10-31). Issue: spec-kitty/spec-kitty#6464.

## Facts established (reproduction)

1. `spec-kitty merge` is a hidden migration stub (`cli/commands/consolidate.py::merge_removed_stub`);
   it prints the rename and exits 1, so the live surface is `spec-kitty consolidate`.
2. **The defect reproduces on current `main`.** Fixture: a real LANES Mission recorded for `develop`
   in a repo whose protected set includes `main` (`.kittify/config.yaml` has no `protection:` block,
   so the resolved set is `{main, master} ∪ origin/HEAD`). Checkout on `main`,
   `spec-kitty consolidate --mission <slug> --target main --yes` printed
   `✓ kitty/mission-… → main  Commit: 576d879` — the branch-integration squash landed **on `main`**
   with no protection check. The run only unwound because the next phase (done bookkeeping) tripped
   `SafeCommitHeadMismatch` against the recorded target `develop` and the #5385 rollback door
   restored the refs.
3. Root cause: `integration`'s commit is a raw `git commit` in an ephemeral worktree
   (`src/specify_cli/lanes/consolidation.py::_merge_branch_into` → `conclude_in_progress_op`), so the
   `WorkflowMutationPolicy` / `ProtectionPolicy` chokepoint every status commit goes through never
   sees it. The only protection preflight in the pipeline,
   `consolidation/preflight.py::refuse_protected_status_target` (#5385), probes the **recorded** target,
   and ADR `docs/adr/3.x/2026-09-19-1-terminus-safety-invariant.md` (follow-up 2026-09-30) states it
   "reads the recorded meta target, not `--target`" — the documented residual this issue hits.
4. The effective target is produced by `_load_lanes_manifest` (`consolidation/executor.py`), which
   mutates `manifest.target_branch = target_override` after `resolve_merge_target_branch`
   (precedence: `--target` > persisted `ConsolidationState.target_branch` > `meta.json` > default).
   The recorded target is the same resolver called with no override.

## Prior art / adjacent work (do not duplicate)

- #5385 (ADR 2026-09-19-1 follow-up) — the recorded-target refusal, its `--dry-run` parity, its
  orchestrator-api parity and its pinned controls. Kept exactly as-is.
- #5100 — the mission-scoped `commit_to_target` hatch folded into `ProtectionPolicy`.
- #3132 — the broader "PR-required delivery policy"; this Mission does not implement it.
- #3080 — `merge` → `consolidate` rename (why the issue's command name no longer exists).

## Decisions

- **D1 — Scope the guard to the override.** A blanket "effective target is protected → refuse" would
  contradict pinned, deliberate behaviour (`tests/terminus/test_protected_target_preflight.py` allows a
  coordination-topology Mission on `main`, an all-done Mission and a `commit_to_target` Mission). The
  new guard therefore fires only when the effective target differs from the recorded target **and** the
  protection policy says that branch is protected. #5385 owns the recorded-target decision.
- **D2 — One authority.** Ask `ProtectionPolicy.resolve_for_mission(...).is_protected_target(...)`
  (folds the operator hatch, the configured set, the repo primary and the mission-scoped bypass). No
  second list, no name comparison.
- **D3 — No new error code.** Reuse `PROTECTED_BRANCH_REFUSED`; the status-write protocol's code
  allowlist is a public contract.
- **D4 — Refuse before mutation, on all three entries** (real run, `--dry-run --json`,
  `orchestrator-api consolidate-mission`), matching the #5385 pattern so preview and API cannot be
  more permissive than the real run.
- **D5 — Order after #5385's probe** so the pinned refusal text for the recorded-target case (code,
  remedy, footer) is byte-identical.

## Open questions (resolved or deferred)

- *Should an override onto an unprotected, non-recorded branch also refuse?* Deferred: it is a
  coherence defect (the run cannot finish its bookkeeping), not a protection bypass, and it is out of
  this Mission's scope (spec C-002). Today it lands, then fails and rolls back.
- *Does the record-only `--target <recorded>` need a guard?* No — it is a restatement, covered by the
  in-bounds control.
