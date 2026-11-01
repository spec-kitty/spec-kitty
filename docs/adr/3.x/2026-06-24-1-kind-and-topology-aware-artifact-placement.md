---
title: 'ADR: Kind- and Topology-Aware Artifact Placement — One Partition, Read/Write
  Symmetry'
description: 'Artifact placement becomes a frozenset partition over `MissionArtifactKind`: planning and identity kinds sit in the PRIMARY partition, status kinds on the coordination branch.'
status: Accepted
doc_status: active
kind: ADR
date: '2026-06-24'
---

## Context

A coordination-topology mission keeps two on-disk copies of its feature directory:
the **primary checkout** (`kitty-specs/<slug>/`) and the **coordination worktree**
(`.worktrees/<slug>-<mid8>-coord/kitty-specs/<slug>/`). Where each mission artifact
*lives* — which surface authors and reads it, and which branch its commit lands on —
is the central correctness question of the planning lifecycle.

The merged read-side mission `single-authority-topology-cleanup` (PR #2099) introduced
the canonical answer for **reads**: `MissionArtifactKind` in
[`src/mission_runtime/artifacts.py`](../../../src/mission_runtime/artifacts.py). Every
mission artifact has a kind; `artifact_home_for(kind, placement_ref)` resolves its
read/write/commit home; `is_coordination_artifact_residue_path` classifies a stale
primary copy as residue-or-dirt by kind. That model already routed reads by **kind**.

The **write/authoring** path, however, was **kind-blind**. `resolve_placement_only`
(`mission_runtime/resolution.py`) and `commit_for_mission`
(`specify_cli/coordination/commit_router.py`) routed *purely by topology*: under
coordination topology, **every** planning artifact was written to the coordination
branch. So the read model said `spec.md`/`tasks.md`/`tasks/WP*.md` belong on primary,
while the write path committed them to coordination. That asymmetry **is** the
[#2101](https://github.com/Priivacy-ai/spec-kitty/issues/2101) deadlock: for a
protected-main / `pr_bound` / `topology: coord` mission, `map-requirements` wrote WP
files to the coordination worktree while `finalize-tasks` globbed `tasks/*.md` on the
main checkout and found nothing — `requirement_refs_parsed: {}`, every functional
requirement reported unmapped. No single location satisfied both commands, and the
`/tasks` phase could not complete without a manual file-copy workaround.

The predecessor ADR named and stored the mission *shape* (`MissionTopology`) so the
shape is resolved once. This mission addresses the orthogonal question the shape alone
cannot answer: **two artifacts of the same mission can legitimately want different
surfaces.** Topology says *whether a coordination branch exists*; it must not be the
sole decider of *which* artifacts go there.

## Decision

Make the write side **kind-aware** by consulting the same `MissionArtifactKind` model
the read side already uses, and decide placement by a **single frozenset partition**.

1. **Placement is a partition, not a topology switch.** The PRIMARY-vs-coordination
   decision is the membership test `kind in _PRIMARY_ARTIFACT_KINDS`
   ([`artifacts.py`](../../../src/mission_runtime/artifacts.py)). Planning + identity
   kinds — `SPEC`, `DATA_MODEL`, `RESEARCH`, `CHECKLIST`, `FINALIZED_EXECUTION_PLAN`,
   `TASKS_INDEX`, `WORK_PACKAGE_TASK`, `LANE_STATE`, `PRIMARY_METADATA` — author, read,
   and commit on the primary `target_branch` **for every topology shape**. The
   status/bookkeeping/verification kinds — `STATUS_STATE`, `ISSUE_MATRIX`,
   `ACCEPTANCE_MATRIX`, `ANALYSIS_REPORT` (`_PLACEMENT_ARTIFACT_KINDS`), plus
   `decisions/index.json` — stay on the **coordination branch** under coordination
   topology (`SINGLE_BRANCH`/`LANES` collapse to primary). The two frozensets are the
   **single swappable locus**: flipping where a kind lands is moving it between the
   sets — one line, no caller change, no signature or returned-shape change (NFR-004).

2. **The write projection consults the partition.** `resolve_placement_only`
   ([`resolution.py:1017`](../../../src/mission_runtime/resolution.py)) now takes a
   **required** `kind: MissionArtifactKind` keyword (no default — an un-threaded call
   site fails at the type level rather than silently flipping coord→primary). A
   `_PRIMARY_ARTIFACT_KINDS` member returns `CommitTarget(ref=target_branch)`; every
   other kind keeps the topology-routed `destination_ref` the full resolver already
   computes via `_assemble_core_fragments` — **one authority, two projections**, not a
   parallel resolver (C-006). `commit_for_mission` derives `use_coord` from that single
   kind-aware placement (`routes_through_coordination(topology) and placement.ref !=
   primary_target`), so a primary kind never materializes the coordination worktree
   even under coordination topology.

3. **Read/write symmetry (INV-5).** The read side (`artifact_home_for` /
   `is_coordination_artifact_residue_path`, #2099) and the write side
   (`resolve_placement_only` / `commit_for_mission`, plus the bypass writers and the
   second routing authority — see §4) now both consult the same partition. For a given
   kind they resolve the **same** surface. `meta.json` (`PRIMARY_METADATA`) is the
   capstone: it already *read* from primary, and now *writes* to primary too, closing
   the last read/write split. The #2101 class is structurally impossible once both
   legs agree: the command that writes WP files and the command that validates them
   resolve the identical `feature_dir`.

4. **Converge every write site — no "fixed N of M".** Kind-awareness is threaded
   through *all* planning-placement writers, not just `commit_for_mission`'s callers
   (`spec-commit`, `setup-plan`, `map-requirements`, finalize tail, `record-analysis`,
   analyze/tasks/accept): also the **bypass writers** (`safe-commit` and
   `append-history`, which hold a *path* and classify it via the new public
   `kind_for_mission_file` classifier) **and** the **second routing authority**
   `_planning_commit_worktree`
   ([`mission.py:792`](../../../src/specify_cli/cli/commands/agent/mission.py)), which
   maps each `artifact_type` to a `MissionArtifactKind` (`_ARTIFACT_TYPE_TO_KIND`) and
   delegates to `resolve_placement_only`. The planning-artifact→coordination *write*
   route is **removed**, not preserved as a fallback (C-005 — unification, not parity).

5. **Topology governs only the status destination.** After this mission,
   `MissionTopology` decides *where the status commit lands*, **not** where the planning
   commit lands. Planning is partition-decided (always primary); status is
   topology-routed (coordination under `COORD`/`LANES_WITH_COORD`). The two questions
   are finally separated.

### Binding invariant — protected primary (FR-008 / C-002)

Because planning artifacts now always land on the primary `target_branch`, a
coordination-topology mission whose `target_branch` is a **protected** branch
(`main`/`master`) is **refused** at the planning-commit boundary
([`commit_router.py:160`](../../../src/specify_cli/coordination/commit_router.py),
`no_op_wrong_surface`) with guidance to start a non-protected feature branch. The
protected-primary deadlock is avoided by this **feature-branch invariant** — not by
transiting the coordination worktree. Status commits are unaffected: they continue to
route to the (non-protected) coordination branch. This deliberately revises mission
`01KSPTVW` FR-005 (which originally placed planning-artifact commits on the coordination
branch); the revision is operator-confirmed unification, called out so it is not read
as a regression.

## Consequences

### Positive

- **The #2101 / #2062-#2064 desync class is closed at the root.** Read and write
  resolve the same surface per kind, so the command that authors a planning artifact
  and the command that validates it can never disagree about its `feature_dir`. A fresh
  coordination-topology mission completes specify → plan → tasks →
  `finalize-tasks --validate-only` with 100% of requirements mapped and **zero** manual
  coordination-worktree steps (SC-001).
- **Placement is one named, swappable partition.** Re-homing a kind is a one-line set
  move; callers and the returned `CommitTarget`/`MissionArtifactHome` shape are blind to
  the membership (NFR-004 / G-5). The decision lives in exactly one module.
- **Status semantics are preserved.** The append-only `status.events.jsonl`,
  `decisions/index.json`, `issue-matrix.md`, and WP transition commits still land on the
  coordination branch under coordination topology (C-001), keeping the atomic-event-log
  model from mission `01KSPTVW`.
- **Behavior-neutral for flattened / single-branch missions** (NFR-001): with no
  coordination branch, both partitions collapse to `target_branch` — identical to
  pre-mission behavior.

### Negative / risks

- **Forward-only (C-003).** A mission already *split* (planning on coordination, reads
  on primary) is not reconciled; the flatten / manual-recovery flow remains the
  documented remedy for legacy split missions.
- **A required `kind` keyword is a breaking internal-seam change.** Every
  `resolve_placement_only` / `commit_for_mission` call site must thread a
  `MissionArtifactKind`. This is intentional (fail at the type level, not silently),
  but any out-of-tree caller must be updated.
- **The coordination-worktree mechanism stays** (C-004). This mission stops routing
  planning artifacts through it; it does not remove the materialization used for
  status/sync. The `_planning_commit_worktree` / `_materialise_coord_worktree` staging,
  the `_try_advance_ref` ff-advance (#1878), and the `is_coordination_artifact_residue_path`
  dirty-filter remain, now governing only status-class coord writes (FR-005). A stale
  *primary* copy of a planning artifact is now **real dirt**, not residue.

## Alternatives considered

- **Keep routing purely by topology (status quo).** Rejected: that *is* the #2101 bug —
  it forces planning artifacts onto coordination while reads expect primary.
- **Build a second, write-only resolver that mirrors the read partition.** Rejected
  (C-006): `artifact_home_for` / the partition is already the single classification
  authority. `resolve_placement_only` *projects* the same `_assemble_core_fragments`
  builder; a parallel resolver re-reading `meta.json`/git would re-create the split-brain
  under repair — the same anti-pattern the predecessor topology-SSOT ADR rejected.
- **Move status to primary too (uniform primary placement).** Rejected (C-001): it
  would break the atomic coordination event-log model; status legitimately wants the
  coordination branch under coordination topology. The bifurcation is the point.
- **Solve protected-primary by transiting the coordination worktree for planning
  commits.** Rejected (FR-008 / D-3): the feature-branch invariant is a cleaner
  guarantee with no special-case transit; it removes the deadlock by construction rather
  than re-introducing the coord landing the read side just escaped.

## References

- Driver: [#2090](https://github.com/Priivacy-ai/spec-kitty/issues/2090) (kind- and topology-aware write-side placement)
- User-reported deadlock closed: [#2101](https://github.com/Priivacy-ai/spec-kitty/issues/2101) (coordination-worktree missions: planning/tasks resolve different `feature_dir`)
- Read-side predecessor: [#2099](https://github.com/Priivacy-ai/spec-kitty/pull/2099) / mission `single-authority-topology-cleanup` ([#147](https://github.com/Priivacy-ai/spec-kitty/issues/147)) — the `MissionArtifactKind` read model
- Desync class closed structurally by the read+write pair: [#2062](https://github.com/Priivacy-ai/spec-kitty/issues/2062), [#2063](https://github.com/Priivacy-ai/spec-kitty/issues/2063), [#2064](https://github.com/Priivacy-ai/spec-kitty/issues/2064)
- Epics: [#1716](https://github.com/Priivacy-ai/spec-kitty/issues/1716) (single surface authority), [#2007](https://github.com/Priivacy-ai/spec-kitty/issues/2007), [#1619](https://github.com/Priivacy-ai/spec-kitty/issues/1619) (execution-context)
- Mission spec: `kitty-specs/write-surface-coherence-01KVTVZS/spec.md`
- Placement contract: `kitty-specs/write-surface-coherence-01KVTVZS/contracts/placement-bifurcation.md`
- Data model (INV-5 read/write symmetry, the swappable locus): `kitty-specs/write-surface-coherence-01KVTVZS/data-model.md`
- Phase-0 decisions (D-1..D-8): `kitty-specs/write-surface-coherence-01KVTVZS/research.md`
- Canonical seams: [`src/mission_runtime/artifacts.py`](../../../src/mission_runtime/artifacts.py) (partition + `artifact_home_for` + `kind_for_mission_file`), [`src/mission_runtime/resolution.py`](../../../src/mission_runtime/resolution.py) (`resolve_placement_only`, kind-aware), [`src/specify_cli/coordination/commit_router.py`](../../../src/specify_cli/coordination/commit_router.py) (`commit_for_mission`, FR-008 protected-primary refusal), [`src/specify_cli/cli/commands/agent/mission.py`](../../../src/specify_cli/cli/commands/agent/mission.py) (`_planning_commit_worktree`, second routing authority)
