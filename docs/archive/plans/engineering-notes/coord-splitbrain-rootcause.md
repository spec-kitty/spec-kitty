---
title: 'Coord-branch bookkeeping: read/write split-brain root-cause'
description: 'Root-cause analysis of the coordination-branch drift (#2841) as an unenforced write-placement split-brain, and the single placement-port seam that prevents it.'
doc_status: deprecated
updated: '2026-07-22'
related:
- docs/adr/3.x/2026-06-27-1-common-docs-reconciliation.md
- docs/plans/engineering-notes/index.md
---

# Coord-branch bookkeeping: read/write split-brain root-cause

> **Retired (deprecated).** Design shipped/superseded via merged mission `coord-write-placement-closure-01KYCF83` (#2841; `kitty-specs/coord-write-placement-closure-01KYCF83/`). Preserved as a historical record.

**Scope:** ground a PREVENTION-first re-scope of #2841 (coord-branch drift). READ-ONLY analysis; no product code changed.
**Thesis under test:** coord drift is a read/write split-brain — coord bookkeeping is a *second, independently-writable copy* of a truth whose authority lives elsewhere. Confirmed, with one precise refinement (below).

---

## 0. The one-paragraph answer

The partition **contract** is already correct and symmetric. `artifact_home_for(kind, ...)`
(`src/mission_runtime/artifacts.py:194-232`) returns `read_surface == write_surface` for
*every* kind, keyed on the single disjoint-and-total partition
(`_PRIMARY_ARTIFACT_KINDS` `artifacts.py:110-126`, `_PLACEMENT_ARTIFACT_KINDS` (=COORD)
`artifacts.py:132-139`, guarded exhaustive by `assert_partition_invariant` `artifacts.py:235-263`).
The canonical **write** seam `resolve_placement_only(kind=...)` (`src/mission_runtime/resolution.py:1219`)
and the canonical **read** seam `resolve_planning_read_dir(kind=...)`
(`src/specify_cli/missions/_read_path_resolver.py:1349`) both key on that *same* partition via
`is_primary_artifact_kind` (`artifacts.py:294-304`).

The split-brain is **not** in the contract. It is that **there is no enforced invariant that a
mission artifact is physically written to its `artifact_home_for(kind).write_surface`.** Individual
writers pick their own directory — some through a kind-*blind* resolver, some hard-anchored to the
wrong partition, some by writing to primary and then *copying* to coord. Wherever a writer bypasses
the kind-keyed placement seam, the on-disk/committed copy forks from the partition every reader
resolves. That is the recurring boundary leak.

---

## 1. Artifact-by-artifact table

Partition legend: **COORD** = `_PLACEMENT_ARTIFACT_KINDS` (lives on the coordination branch under
coord topology); **PRIMARY** = `_PRIMARY_ARTIFACT_KINDS` (lives on `target_branch` for every topology).

| Artifact | Authored / Derived | Write site(s) | Read site(s) | Authority partition | Where it forks (split-brain risk) | Prevention shape |
|---|---|---|---|---|---|---|
| **status.events.jsonl** | **Authored** — the sole append-only authority | `emit_status_transition` → `append_event`; physical dir via `canonicalize_feature_dir` (`root_resolver.py:83`), committed to coord only via `BookkeepingTransaction` (`status_transition.py:900,943`) | coord-anchored: `resolve_status_surface`/`read_event_log(coordination_branch_ref)` (`agent_utils/status.py:125`, `done_bookkeeping.py:581`) | COORD (`STATUS_STATE`, `artifacts.py:136`) | **Write-authority fork:** `_transaction_topology_available` False (`status_transition.py:924`) falls back to a bare **primary-checkout, uncommitted** write; the copy-stager *deliberately skips* status files (`commit_router.py:687-688`, `COORD_OWNED_STATUS_FILES` `status/__init__.py:222`). Reader always reads coord → stale. | single-write-authority + partition-discipline (force the coord-worktree commit path; no primary-uncommitted arm) |
| **status.json** | **Derived** — pure `reduce()`/`materialize()` output | written only as the reduction output inside the emit/save transaction (`aggregate.py:820-824`); never independently authored | `MissionStatus.load` / views | COORD (`STATUS_STATE`) | **None** — this is the reference pattern (authoritative log → derived view). It cannot drift because it is never authored. | already make-derived (the model to copy) |
| **review-cycle-N.md** | **Authored** (reviewer verdict + prose) **AND the verdict is *also* event-sourced** as a `review_ref` pointer → **dual authority** | `create_rejected_review_cycle` `cycle.py:272,299` → `artifacts.py:199,214`, dir via kind-**blind** `candidate_feature_dir_for_mission` (→ **COORD** husk for coord topology) | dry-run: **PRIMARY** (`forecast.py:175`, `resolve_planning_read_dir(WORK_PACKAGE_TASK)`); real-merge: **COORD** (`executor.py:1327` → `preflight.py:369` → `review_artifact_consistency.py:128-174`); done: event slot only (`done_bookkeeping.py:109-121`) | **PRIMARY** (inherited: `tasks/` → `WORK_PACKAGE_TASK`, `artifacts.py:157,118`) | **Two forks.** (a) Written to COORD but declared PRIMARY. (b) Same gate reads *different partitions per entry point* — a rejected cycle on COORD is invisible to `merge --dry-run` (false-green) yet blocks real merge. (c) Verdict duplicated: authored markdown vs event-log `review` override — the very existence of `find_rejected_review_artifact_conflicts` (a cross-store reconciliation, `review_artifact_consistency.py:77-94,148`) is the fingerprint of split-brain. | single-write-authority (route write + *all* reads through `resolve_planning_read_dir(WORK_PACKAGE_TASK)`); longer term collapse the *verdict* into the event log (make-derived), keep prose authored |
| **issue-matrix.md** | **Authored** verdicts; rows derivable from `spec.md` issue refs | scaffold at finalize onto **PRIMARY** `planning_dir` (`mission_finalize.py:361`, `issue_matrix.py:124`), then **copied primary→coord** (`commit_router.py:701`); per-issue verdicts updated during review/move-task | doctor (`status/doctor.py:342,368`), accept, review report | COORD (`ISSUE_MATRIX`, `artifacts.py:135`) | Authored on **two** partitions (primary scaffold + coord lifecycle updates); stale **primary residue** drifts (#2841), papered over by `is_coordination_artifact_residue_path` declaring the primary copy non-dirt (`artifacts.py:266-291`) | single-write-authority + partition-discipline (write directly into the coord home; rows may be derived from `spec.md`, verdicts stay authored) |
| **acceptance-matrix.json** | **Authored** `pass_fail`/`evidence`/`verified_by`; only `overall_verdict` derived (`matrix.py:120-137`) | `write_acceptance_matrix(feature_dir)` (`matrix.py:182`) — caller-supplied dir (PRIMARY at finalize `mission_finalize.py:1246`, accept-time re-persist `gates_core.py:258`); `commit_for_mission(kind=ACCEPTANCE_MATRIX)` copies to coord (`accept.py:218-224`) | coord via `placement_seam.read_dir` (`accept.py:97`) + `read_acceptance_matrix(feature_dir)` | COORD (`ACCEPTANCE_MATRIX`, `artifacts.py:134`) | Historical write(primary)/read(coord) fork **reconciled for accept** (#2404: `_commit_coord_residuals` + dual-worktree dirty scan `accept.py:117-232`); residual **write-then-copy** residue shape remains (same class as issue-matrix) | single-write-authority + partition-discipline (write directly into coord home; drop the copy) |
| **analysis-report.md** | **Authored** (analysis prose + `analysis-findings/v1` carrier) | writer anchors **PRIMARY** (`mission_record_analysis.py:307`, `resolve_planning_read_dir(kind=spec)`); coord copy under `contextlib.suppress(Exception)` (`:324-342`) | implement freshness gate reads **PRIMARY** (`workflow.py:850`, `check_analysis_report_current`); COORD placement authority also declared | COORD (`ANALYSIS_REPORT`, `artifacts.py:137`) | **LIVE split-brain.** Writer *and* freshness gate both anchor PRIMARY; the coord commit is best-effort/swallowed. SSOT says COORD (residue predicate calls the primary copy disposable, `artifacts.py:266`), the gate says the primary copy is *required* — mutually contradictory. | single-write-authority + partition-discipline: pick ONE home and make writer+gate+SSOT agree (write directly to coord + move gate read to coord, OR reclassify the kind to PRIMARY) |
| **notes** (status snapshot slot) | **Derived** — reduced per-WP slot (`reducer.py:50,188-191`) | source `note` events via emit (`tasks.py:944`, `tasks_move_task.py:1670`, `tasks_transition_core.py:598`) → coord log | materialized snapshot / views | COORD (`STATUS_STATE`) | **None** — pure reduction of the event log, one authority | already derived |
| **traces/\*.md** | **Authored** (agent tracer prose) | no Python writer; agent-authored, cross-branch reconciled by the **union merge driver** (`merge_driver.py:180-215`, registered `init.py:60`, `lanes/merge.py:74-77`) | retrospective home = **PRIMARY** (`retrospective_terminus.py:79-81`, `generator.py:224-242`) | **Unclassified in SSOT** (doctrine/glossary label it COORD — `docs/context/orchestration.md:506`) | **Partition GAP** — `traces/` is absent from `_COORD_RESIDUE_DIRS` (`artifacts.py:156-159`), so `_artifact_kind_for_path` returns `None` and a primary `traces/*.md` is "real dirt," not residue. Code sites it PRIMARY/lane + union-merge; doctrine says coord. Doc-vs-SSOT mismatch. | classify it (add a `TRACE` kind + residue-dir entry, OR correct the glossary to PRIMARY/lane); union-merge already prevents lane drift |

> **Resolved (2026-08-05, mission `review-cycle-verdict-seam-rebuild-01KZ2W7W`, ADR
> [`2026-08-03-1`](/docs/adr/3.x/2026-08-03-1-review-cycle-artifacts-are-coord-partition.md)) — the
> `review-cycle-N.md` row above.** This note marks the row as historical without rewriting it: it
> was an accurate diagnosis of the pre-ADR split. The dual authority / "written to COORD but
> declared PRIMARY" shape it describes is what that mission's ADR and WP04/WP07/WP13 resolve —
> `review-cycle-N.md` is reclassified as its own `REVIEW_CYCLE` kind (not inherited from
> `WORK_PACKAGE_TASK`), filename-anchored (`review-cycle-*.md`, not directory-anchored), and its
> read/write seam is unified through `_artifact_dirs_for_wp`/`_review_cycle_wp_dir`. This closes
> forks (a) and (b) the row names (wrong-declared-partition, and dry-run/real-merge reading
> different partitions). Fork (c) — the verdict duplicated across authored markdown and the
> event-log `review` slot — is re-framed, not eliminated, by this mission's FR-001: the event is now
> authoritative for *which* verdict and *where*, the markdown artifact for *what the reviewer said*
> — a deliberate two-representation design (index + payload), not the accidental drift this row
> describes. The two cited line-pinned call sites (`cycle.py:272,299` → `artifacts.py:199,214`,
> and the kind-**blind** `candidate_feature_dir_for_mission` resolver) no longer describe live code
> at those exact lines after this mission's rewrite; the current source of truth for the writer/
> resolver/reader shape is `tests/architectural/verdict_seam_census.yaml`, checked against the live
> AST on every run, not a line-pinned table entry.

---

## 2. The single load-bearing seam

**There is no enforced write-placement invariant.** Concretely: nothing forces a writer to physically
land an artifact in `artifact_home_for(kind_for_mission_file(path)).write_surface`. The pieces to enforce
it already exist and are *unused by the drifting writers*:

- `kind_for_mission_file(path)` — the single public file→kind classifier (`artifacts.py:307-326`).
- `resolve_placement_only(kind=...)` — the single kind-keyed write-placement projection (`resolution.py:1219`);
  byte-identical topology classification to the full resolver (`resolution.py:1238-1258`).
- `safe_commit` — already **structurally asserts** the write-root's HEAD equals `destination_ref`
  before staging (`git/commit_helpers.py:867-868`, `SafeCommitHeadMismatch`) — the #2868/#2612 guard.

The drift is entirely upstream of that guard, at the point a writer *chooses its directory*:

- `cycle.py:272` and `cycle.py:193` use kind-**blind** `candidate_feature_dir_for_mission` (topology-aware → COORD husk) for a PRIMARY-partition kind.
- `mission_record_analysis.py:307` hard-anchors PRIMARY for a COORD kind; coord copy swallowed.
- `commit_router._stage_artifacts_in_coord_worktree` (`commit_router.py:666-724`) `shutil.copy2` (`:701`) the matrices/report **from primary into coord** — this copy *is the residue factory*: it manufactures the second, independently-writable primary copy that #2841 observes drifting.
- `emit`/`canonicalize_feature_dir` (`root_resolver.py:104-142`) rewrites the status write to PRIMARY unless a *registered* coord worktree is present, and the coord-commit only happens on the `_transaction_topology_available` True arm (`status_transition.py:924`).

**One seam collapses shapes 2, 3, and 4:** route *every* mission-artifact write through a single
placement port keyed on `kind_for_mission_file(path) → resolve_placement_only(kind).ref`, and **stage the
bytes directly in that ref's worktree** (never write-to-primary-then-copy). The `safe_commit`
worktree/HEAD guard then makes a wrong-partition write *unrepresentable at commit time* rather than a
silent divergence discovered at merge.

---

## 3. What prevention makes structurally impossible vs. the residual fail-loud net

**Made structurally impossible by "one kind-keyed placement port + write-in-home + safe_commit guard":**

1. **Wrong-partition authorship (shape 2).** A `WORK_PACKAGE_TASK` review-cycle can only land PRIMARY; an
   `ANALYSIS_REPORT` can only land COORD. `cycle.py:272` / `mission_record_analysis.py:307` can no longer
   choose a divergent dir.
2. **Second-copy / residue drift (shape 3).** Writing in-place removes the `shutil.copy2` primary→coord
   stager (`commit_router.py:701`) that manufactures the drifting primary residue for issue-matrix /
   acceptance-matrix / analysis-report. No second writable copy ⇒ nothing to reconcile ⇒
   `is_coordination_artifact_residue_path` (`artifacts.py:266`) becomes vestigial rather than load-bearing.
3. **Status primary-uncommitted fork (shape 4).** Removing the `_transaction_topology_available` False
   fallback (or making emit target the coord worktree unconditionally for coord topology) means a status
   event cannot land primary-uncommitted while readers read coord.
4. **Per-entry-point read disagreement.** If write and *all* reads share the one kind-keyed resolver,
   `merge --dry-run` (PRIMARY) and real merge (COORD) can no longer see different review-cycle truth.

**Genuinely irreducible — the minimized residual that still needs a fail-LOUD net:**

- **Bootstrap staleness (#2841 Gap 1).** The coordination branch is a one-time snapshot of `target_branch`
  at `mission create`; `target_branch` moves afterward. This is **not** a coord-bookkeeping split-brain at
  all — it is a *base-ref freshness* problem. No single-authority derivation touches it. It needs a
  detect-and-resync (surfaced at plan/tasks or an explicit `doctor coordination --check-staleness`). This
  is the *only* place a reconciliation/cure command legitimately survives.
- **Dual authority of the review *verdict*.** Until the verdict is collapsed into the event log, the
  authored `verdict:` frontmatter and the event-sourced `review` override remain two stores. The
  existing cross-store gate (`review_artifact_consistency.py`) should stay as a **fail-loud** check, not
  be deleted — it is the safety net for the one artifact whose authored/derived halves genuinely coexist
  during the transition.
- The existing narrow cure `doctor coordination --fix` (`_coordination_doctor.py:80-120,579-601`) — today
  keyed to the `pending_coord_reconcile` marker for stranded-`done` reverts + stale-worktree
  fast-forward — is the correct *shrunken* residual: keep it fail-loud, do **not** grow it into the
  general "repair arbitrary drifted content" command the field report proposed. Prevention removes the
  need for that generalization.

---

## 4. Blunt verdict

**"Prevent via single-authority derivation" is achievable for the derived subset and is already the
model** — `status.json` and `notes` are pure `reduce()` outputs of `status.events.jsonl` and cannot
drift. Nothing else should be a second authored copy of state that the log already owns.

**But most coord bookkeeping genuinely cannot be made derived, and it does not need to be.**
review-cycle prose, issue-matrix verdicts, acceptance-matrix evidence/`verified_by`, analysis-report
findings, and traces all carry human/agent judgement no reduction can reconstruct from the event log or
tracker. Trying to "derive" them is a category error.

The load-bearing insight for the re-scope: **the drift is not caused by these artifacts being authored —
it is caused by them being authored to the *wrong partition* and/or *copied to a second partition*.** The
right prevention for the authored set is therefore **single-WRITE-authority + partition discipline**, not
derivation: one kind-keyed placement port, write-in-home, `safe_commit`-guarded — so wrong-partition
authorship and second-copy residue become structurally impossible. That subsumes the "staleness" and
"reconciliation" symptoms for every artifact *except* the #2841 Gap-1 bootstrap-snapshot freshness
problem, which is a base-ref sync concern and is the sole surviving home for a minimized, fail-loud
detect/resync — never a broad "repair the drift after the fact" cure.

### Composition notes

- **Builds ON PR#2868/#2612** (`safe_commit` sub-worktree-root + HEAD==destination_ref assertion,
  `commit_helpers.py:867-868`): that is the *enforcement primitive*. This prevention feeds it a
  correct write-root by construction; it does not redo the write-path mechanics.
- **#2160 (unify coord artifact authority):** the single kind-keyed placement port *is* the "one
  authority" — route all writers through it.
- **#2400 (metadata single canonical source):** same shape applied to `meta.json`/profile — a
  partition already correct (`PRIMARY_METADATA`), the discipline is identical.
- **#2173 (infra-as-ports):** express the placement port as an injected port so writers depend on the
  resolver, not on ad-hoc `candidate_feature_dir_for_mission` / hard-coded primary anchors.

### Branch caveat (verify before scoping mechanical fixes)

On this branch (`doctrine/drg-completeness-2843`), `find_rejected_review_artifact_conflicts`
(`review_artifact_consistency.py:128-174`) still takes a single `feature_dir` and serves *both* the
`materialize()` STATUS_STATE read (`:133`) and the `tasks/` WORK_PACKAGE_TASK read (`:143`, `:57-58`)
from it — the exact pre-#2834 shape. Confirm the #2834 split has actually landed here before assuming
the review-cycle read is kind-correct; the write side (`cycle.py:272`) is *not* kind-routed regardless.
