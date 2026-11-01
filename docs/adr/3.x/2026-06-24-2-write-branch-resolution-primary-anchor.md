---
title: 'ADR: Write-Branch Resolution Anchors `meta.json` on the PRIMARY Surface (Write-Surface
  Twin)'
description: 'Write-branch resolvers read `meta.json` from the repository-root checkout under every topology, so commits land on the mission Target Ref, not the protected Primary Branch.'
status: Accepted
doc_status: active
kind: ADR
date: '2026-06-24'
---

## Context

A coordination-topology mission keeps two on-disk copies of its feature directory:
the **repository-root checkout** (the `primary` **Sense C** surface — `kitty-specs/<slug>/`)
and the **coordination worktree** (`.worktrees/<slug>-<mid8>-coord/kitty-specs/<slug>/`).
(The four `primary` senses — PRIMARY partition / Primary Branch / repository-root
checkout / Target Ref — are catalogued in `docs/context/orchestration.md`; each use
below is qualified to exactly one.)

The predecessor ADR ([2026-06-24-1]) made artifact **placement** kind-aware: planning +
identity kinds (`spec.md`, `plan.md`, `tasks.md`, `tasks/WP*.md`, `data-model.md`,
`research.md`, `lanes.json`, `meta.json`) are PRIMARY-partition kinds that author, read,
and commit on the primary `target_branch` for **every** topology; status/verification
kinds stay on the coordination branch under coordination topology. The read side adopted
the per-kind seam `resolve_planning_read_dir(repo_root, slug, *, kind)`.

Two residual seams survived that re-partition, both on the **write** path, and both share
one root failure mode. A write-branch resolver that needs a mission's `target_branch`
reads it from `meta.json`. `meta.json` is `PRIMARY_METADATA` — it **only** ever lives on
the primary checkout. The pre-fix resolvers anchored that `meta.json` read on the
**topology-aware candidate** dir (`candidate_feature_dir_for_mission`):

1. **The write-branch resolvers** — `get_feature_target_branch` (`core/paths.py`),
   `resolve_target_branch` (`core/git_ops.py`), and the `finalize-tasks` commit-branch
   resolution (`mission.py`). Under coordination topology the candidate resolver returns
   the materialized `-coord` worktree, whose mission dir has **no** `meta.json`. The read
   found nothing and silently fell back to `resolve_primary_branch` = the protected
   repository's **Primary Branch** (`primary` **Sense B**, normally `main`). So the
   planning-artifact commit/branch resolved to that Primary Branch instead of the mission's
   **Target Ref** (`target_branch`, `primary` **Sense D**) — the implement-loop /
   `finalize-tasks` "refusal-to-main" defect. The root confusion is reading a
   PRIMARY-partition (`primary` **Sense A** — `meta.json` is a PRIMARY-partition kind)
   fact as a Primary-Branch (Sense B) instruction.

2. **The `research` (Phase 0) command** (the [#2107](https://github.com/Priivacy-ai/spec-kitty/issues/2107)
   driver's read+write twin, found at closeout). It bound `feature_dir =
   resolve_feature_dir_for_slug` (coord-aware), then validated `coord/plan.md` (absent on
   the husk since the predecessor mission moved plan.md to primary) and **scaffolded**
   `research.md` / `data-model.md` / the research CSV stubs onto the coord husk —
   re-introducing the very primary↔coord split the placement ADR eliminated.

Both are instances of one shape: **a topology-routed `feature_dir` binding followed by a
planning-kind read/write.** The recurrence is the tell — the pre-plan squad found
`map-requirements`, the post-tasks squad found `finalize-tasks-commit`, the closeout
squad found `research`; each enumeration undersized the set by one. The missing boundary
is not a name to add but a *shape* to fence.

## Decision

The mission's write-branch / planning-write resolution anchors on the **primary** surface
for **all** topologies, and the boundary is enforced by a coverage-derived (default-deny)
ratchet so the recurring N+1 cannot return silently.

1. **Write-branch resolution reads `meta.json` from the repository-root-checkout anchor.**
   Every write-branch resolver (`get_feature_target_branch`, `resolve_target_branch`, the
   `finalize-tasks` commit-branch resolution) reads `target_branch` from `meta.json`
   under `primary_feature_dir_for_mission` (the topology-blind repository-root-checkout
   constructor — `primary` **Sense C**), mirroring the already-proven
   `resolve_merge_target_branch`. It is **never** anchored on
   `candidate_feature_dir_for_mission` (which selects coord, then falls back to the
   protected **Primary Branch** — `primary` **Sense B**, `main`). For ALL topologies the
   resolved commit/branch is the mission's **Target Ref** (`target_branch`, `primary`
   **Sense D**) (G-6).

2. **Planning reads and the scaffold writes resolve via the kind-aware seam.** A gate
   command that reads OR scaffolds a planning artifact resolves the dir through
   `resolve_planning_read_dir(..., kind=...)` (PRIMARY-partition → primary for all
   topologies). The `research` command's `plan.md` read uses
   `kind=FINALIZED_EXECUTION_PLAN` and its `research.md` / `data-model.md` / CSV scaffold
   writes use `kind=RESEARCH` / `DATA_MODEL` — all primary-partition kinds, so both legs
   converge on the primary `target_branch` dir. The STATUS-namespace dossier sync keeps
   its existing coord-aware `feature_dir` surface, untouched.

3. **Status destinations are unchanged.** The status/coord commit destinations
   (`status.events.jsonl`, `acceptance-matrix.json`, `analysis-report.md`) still route to
   the coordination branch under coordination topology. This decision touches ONLY the
   `target_branch` (`meta.json`) read and the planning scaffold surface — not where any
   status-class write lands (C-002 status leniency preserved).

4. **The boundary is a default-deny ratchet, not a manual denylist.** The FR-010
   architectural ratchet support (`tests/architectural/_gate_read_callshape.py`) keeps its
   pinned, contract-cited surface set AND adds a **coverage-derived** read arm that walks
   every function in the CLI command packages and flags ANY topology-routed
   planning-artifact join — so a NEW planning-lifecycle command that re-reads
   `coord/<artifact>.md` FAILS the gate even if nobody adds it to the pinned set. The
   topology-routed resolver set is broadened to include `resolve_feature_dir_for_slug` and
   `candidate_feature_dir_for_mission`. A runnable synthetic-AST self-test proves the
   default-deny arm flags an un-listed command in the exact `research` shape. The write
   arm is symmetric: it flags a `meta.json` read anchored on the candidate dir.

## Consequences

### Positive

- **The refusal-to-main / planning-write-to-coord defect class is closed at the root.**
  A coordination-topology mission whose `target_branch` is a feature branch resolves its
  planning commit/branch to that branch, and authors its Phase-0 artifacts on it — the
  command that authors and the command that validates agree on the surface.
- **The recurring N+1 is fenced at the shape, not the name.** The default-deny ratchet
  catches the next un-listed command automatically; a future author cannot silently
  re-introduce a `coord/<artifact>.md` read.
- **Behavior-neutral for flattened / single-branch missions** (NFR-001): with no
  coordination branch the candidate and primary anchors coincide, and the seam returns
  `target_branch` — identical to pre-mission behavior.

### Negative / risks

- **Forward-only.** A mission already split (planning scaffolded on coordination) is not
  reconciled; the flatten / manual-recovery flow remains the remedy for legacy splits.
- **The default-deny scan is scoped to the CLI command packages.** A planning-kind read
  introduced outside `src/specify_cli/cli/commands/` is not covered by the discovery arm
  (it would still need an enumerated pin). This is the deliberate precision/coverage
  trade-off — the command packages are the planning-lifecycle gate surface.

## Alternatives considered

- **Anchor write-branch resolution on the topology candidate (status quo).** Rejected:
  that *is* the bug — under coordination topology the candidate lacks `meta.json` and the
  read falls back to protected `main`.
- **Keep the manual denylist and just add `research`.** Rejected: the set undersized
  three times running. Fencing the shape (default-deny) is the only durable fix; the
  pinned set is retained for its contract citations, not as the sole coverage mechanism.
- **Transit the coordination worktree to find `meta.json`.** Rejected (mirrors the
  predecessor ADR's D-3): `meta.json` is a primary-only kind; the primary anchor is a
  cleaner guarantee with no special-case transit.

## References

- Driver: [#2107](https://github.com/Priivacy-ai/spec-kitty/issues/2107) (setup-plan + accept gate reads, and the research read/write twin, on protected-primary/coord topology)
- Bundled: [#2085](https://github.com/Priivacy-ai/spec-kitty/issues/2085), [#2102](https://github.com/Priivacy-ai/spec-kitty/issues/2102), [#2088](https://github.com/Priivacy-ai/spec-kitty/issues/2088), [#2091](https://github.com/Priivacy-ai/spec-kitty/issues/2091)
- Predecessor (write-placement): [ADR 2026-06-24-1 — Kind- and Topology-Aware Artifact Placement](2026-06-24-1-kind-and-topology-aware-artifact-placement.md) / mission `write-surface-coherence-01KVTVZS` ([#2106](https://github.com/Priivacy-ai/spec-kitty/pull/2106))
- Predecessor (topology SSOT): [ADR 2026-06-22-1 — MissionTopology SSOT](2026-06-22-1-mission-topology-ssot.md)
- Epics: [#1716](https://github.com/Priivacy-ai/spec-kitty/issues/1716) (single surface authority), [#1868](https://github.com/Priivacy-ai/spec-kitty/issues/1868), [#1878](https://github.com/Priivacy-ai/spec-kitty/issues/1878)
- Mission spec: `kitty-specs/gate-read-surface-completion-01KVW9B0/spec.md`
- Seam + ratchet contract: `kitty-specs/gate-read-surface-completion-01KVW9B0/contracts/gate-read-seam.md`
- Canonical seams: [`src/specify_cli/missions/_read_path_resolver.py`](../../../src/specify_cli/missions/_read_path_resolver.py) (`primary_feature_dir_for_mission`, `resolve_planning_read_dir`), [`src/specify_cli/core/paths.py`](../../../src/specify_cli/core/paths.py) (`get_feature_target_branch`, `resolve_merge_target_branch`), [`src/specify_cli/core/git_ops.py`](../../../src/specify_cli/core/git_ops.py) (`resolve_target_branch`)
- Ratchet support (default-deny enforcement): [`tests/architectural/_gate_read_callshape.py`](../../../tests/architectural/_gate_read_callshape.py)
