# Implementation Plan: Post-merge partition integrity (#3942 + #4090)

**Branch**: `issue-3942-merge-surface-authority` | **Date**: 2026-09-14 | **Spec**: `./spec.md`
**Input**: Feature specification from `kitty-specs/post-merge-partition-integrity-01M2FQ80/spec.md`

## Summary

Two-track fix on the shared post-merge partition surface, verified live red-first by a 3-lens pre-spec squad on HEAD `ecbf036328`.

- **Track A (#3942, write half)**: squash consolidation clobbers target-newer `kitty-specs/` planning files with older lane copies. Real seam: `lanes/merge.py::integrate_mission_into_target(SQUASH)` → `_merge_branch_into` → `git merge --squash -X theirs` (`lanes/merge.py:635`), with `_MERGE_DRIVERS` (`lanes/merge.py:59-121`) reconciling only an allowlist of 6 artifact classes. Everything else (planning docs) falls to blanket `-X theirs` = lane wins. No recency/kind guard.
- **Track B (#4090 + folded #4091, read half)**: retrospect and doctor now share `resolve_status_surface`, but the primary-wins guard for a surviving diverged coord husk (`surface_resolver.py:745` `_primary_mission_is_completed` → `is_mission_merged` → `_last_merge_marker_at` → `meta.get("merged_at")`) gates on `meta["merged_at"]`, whose production writer was deleted in #2258 (`6f46cf6bb6`) and never re-added. The guard is dormant; divergence resurfaces.

**Shared root-cause hypothesis (FR-009):** both are "what content/state is authoritative post-merge, and on which surface." Track A = which *bytes* win per artifact; Track B = which *surface* a reader trusts. The classifier `mission_runtime.kind_for_mission_file` / `is_primary_artifact_kind` (the single-authority seam extended by the #3867/#2181 work) is the candidate shared spine: planning artifacts are PRIMARY-partition-authoritative, so lanes must neither overwrite them (A) nor be read as their post-merge home (B).

## Technical Context

**Language/Version**: Python 3.11
**Primary Dependencies**: internal — `specify_cli.lanes.merge`, `specify_cli.merge.executor`, `specify_cli.coordination.surface_resolver`, `mission_runtime` kind classifier, `specify_cli.status` reducer
**Storage**: git (merge worktrees), `kitty-specs/**` files, `status.events.jsonl`, `meta.json`
**Testing**: pytest — targeted only (`PYTHONPATH=$(pwd)/src .venv/bin/python -m pytest <targeted> -q -p no:cacheprovider`), never full suite, never `uv run`
**Target Platform**: Linux dev/CI
**Project Type**: single (CLI toolkit)
**Constraints**: complexity ≤15; single canonical authority (extend, don't add); name overloaded `primary`/`merge` senses; mission minted `single_branch` (no coord dogfooding); ATDD red-first per track
**Scale/Scope**: two disjoint code seams, ~4-6 WPs, both P1

## Constitution Check

*GATE: passes.* C-001 single canonical authority — Track A extends the merge-driver/restore + `kind_for_mission_file` authority; Track B re-activates the existing `_primary_mission_is_completed` guard rather than adding a second reader. C-002 terminology — plan names write/read halves and primary/coord senses explicitly. ATDD-first — each track's WP01-equivalent is a red-first repro that must fail on HEAD before a fix lands. No new authority introduced.

## Locked design decisions (post-brownfield-squad, 3-lens convergent)

Validated by a 3-lens post-plan brownfield squad (architect-alphonso seam, paula-patterns reuse, python-pedro feasibility). All three converged; two decisions were RE-LOCKED from the proposals. Citations verified against HEAD `ecbf036328`.

### Track A — #3942 (write authority)

- **D-A1 (LOCKED):** Resolve `kitty-specs/` conflicts during squash by artifact *kind*. Files where `is_primary_artifact_kind(kind_for_mission_file(path))` is true resolve **target-authoritative when the target copy is newer**, with the divergence **reported** (FR-002); driver-covered classes keep their existing reconcilers (FR-003). pedro *ran* the classifier: spec.md→SPEC, plan.md→FINALIZED_EXECUTION_PLAN, tasks/WP*.md→WORK_PACKAGE_TASK, research/data-model → all `is_primary_artifact_kind=True`; driver-covered artifacts False. The predicate (`src/mission_runtime/artifacts.py:158/402/415`) is the pre-built single authority — advances #2907 by driving resolution off it.
- **D-A2 (LOCKED = (a); (b) REJECTED as infeasible):** Extend the post-squash restore `_restore_regressed_gate_artifacts` (`merge/executor.py:206`, #2804 pattern). Option (b) — a `_MERGE_DRIVERS` planning-file driver — is **structurally incapable** of the required decision: a git merge driver receives only three blobs (`%O %A %B`) with **no ref/history access**, so it cannot compute recency; it could only refuse-on-collision (over-fires on every legitimate lane-carries-finalized-state merge). Recency lives in the executor, which has full git access.
- **D-A3 (RE-LOCKED → three-way divergence):** "Newer" is a **three-way base/target/lane** comparison: target wins iff **target diverged from the merge-base while the lane copy is base-or-ancestor** (target evolved, lane is stale). Committer-date is a tiebreak only; **never mtime**. This mirrors the #2709 meta-field driver and is topology-safe by construction — on `single_branch`/`LANES` (lane≠base, target=base) the lane correctly wins with no special-case. Reuse the merge-base + per-side-diff shape at `lanes/stale_check.py:39-67`; no ready-made helper exists, so WP02 builds a small pure one.
- **D-A4 (new):** Amend the `lanes/merge.py:631-633` "mission branch is authoritative" comment — its premise is false for PRIMARY-partition planning kinds (authored on primary, not the lane).

### Track B — #4090 + #4091 (read authority)

- **D-B1 (RE-LOCKED → restore writer AND make guard reopen-aware; one coupled change):** Restore a production writer for `meta["merged_at"]` (datetime; + `merged_commit` for provenance) as a **sibling of `record_baseline_merge_commit`** in the executor's `_phase_capture_and_baseline` (`executor.py:951`, meta-write authority `merge/baseline.py`) — **not** `done_bookkeeping.py` (which writes nothing to meta.json; a meta write there is a boundary leak). The driver's `_TARGET_AUTHORITATIVE_META_FIELDS` (`merge_driver.py:84-95`) already declares `merged_at` as the marker, so this is the canonical reuse, not a new authority. **Do NOT re-point** the guard to `baseline_merge_commit` (modern-mission-only; not cleared on reopen; a SHA not a datetime) or `mission_number` (permanent identity; never cleared on reopen) — both would make a reopened mission read as merged forever. **Mandatory addendum:** because nothing today actually clears `merged_at` on reopen and `is_mission_merged` (`lifecycle.py:302`) is presence-only, restoring the writer would make a *reopened* mission wrongly read as merged across three consumers (`surface_resolver.py:745`, `runtime_bridge.py:1600`, `is_mission_completed`). So WP04 must **also make `is_mission_merged` reopen-aware** via the adjacent `_last_reopen_at` machinery (merged iff `merged_at` present AND no later `MissionReopened`) — event-sourced, no meta-clearer. Writer + reopen-awareness are ONE WP.
- **D-B2 (LOCKED = separable; #4091 contingent):** #4090 is fixed by the marker alone. #4091 is a **distinct measure mismatch**: `event_count = len(unique transition events)` by definition < raw `status.events.jsonl` line count (annotations, lifecycle, decision events are not transitions). `_project_status_bookkeeping_to_target` (`bookkeeping_projection.py:282`) already unions + re-reduces, and its union branch runs only under a coord husk (`:315` `is_under_worktrees_segment`) — this `single_branch` mission never hits it. So **WP05 is CONTINGENT**: it must first stand up a red-first repro on a **coord fixture**; if `event_count` is already correct on HEAD, #4091 is **verify-and-close** (building a fix-test first = green-regression trap).
- **D-B3 (LOCKED):** Keep `resolve_status_surface` as the single read resolver; the fix only makes the merged-state signal it consumes actually written + reopen-correct — it does not fork the reader.

### Do-not-touch / hazards (all three lenses)

- `merge/conflict_resolver.py` (`ConflictType`/`classify_conflict`/`resolve_owned_conflicts`) is **DEAD** (only `merge/__init__.py` re-exports it; the live auto-rebase classifier is the different module `merge/conflict_classifier.py`). WP02 must not wire the fix into it. Boy-scout: file a dead-code ticket advancing #2907.
- Keep green (FR-003 / SC-004): the #2709/#2804 suites — `test_squash_target_newer_provenance_regression_2709.py`, `test_squash_reconcilers_2709.py`, `test_gate_artifact_merge_drivers_2804.py`, `test_issue_2804_merge_resets_gate_artifacts.py`, `test_issue_2709_projection_union.py`.
- `_restore_regressed_gate_artifacts` is ~complexity 4 today; WP02 must **extract** the recency decision into its own helper to hold ≤15 (NFR-003).
- WP03 must drive the **real `doctor mission-state`** read leg (it passes through `enforce_primary_write_ownership`, `_mission_state_doctor.py:429`), not infer agreement from the retrospect side alone.
- Epic notes for WP06 synthesis: D-A1 advances #2907 (classifier-driven taxonomy); D-B1 chooses "override the husk on primary" over "freshen the husk" — a #2160 coord-authority decision to record for the epic owner.

## Project Structure

### Documentation (this mission)

```
kitty-specs/post-merge-partition-integrity-01M2FQ80/
├── spec.md              # committed
├── plan.md              # this file
├── analysis-report.md   # /analyze output (later)
├── synthesis.md         # FR-009 cross-track root-cause synthesis (WP06)
└── tasks/               # WP prompt files (/tasks output)
```

### Source Code (repository root) — seams by track

```
Track A (write):
  src/specify_cli/lanes/merge.py            # integrate_mission_into_target, _merge_branch_into, _MERGE_DRIVERS
  src/specify_cli/merge/executor.py         # _phase_mission_to_target, _restore_regressed_gate_artifacts
  src/mission_runtime/ (kind_for_mission_file / is_primary_artifact_kind)  # classifier authority (read/extend)
  tests/integration/  tests/lanes/          # red-first + regression

Track B (read):
  src/specify_cli/coordination/surface_resolver.py   # _primary_mission_is_completed, is_mission_merged (guard)
  src/specify_cli/merge/done_bookkeeping.py           # merge completion — write merged_at
  src/specify_cli/status/ (lifecycle.py, reducer)     # merged_at read; event_count (#4091)
  src/specify_cli/cli/commands/agent_retrospect.py    # reader (verify, likely untouched)
  tests/  (retrospect + doctor + status)              # red-first + regression
```

**Structure Decision**: single project; two disjoint seam clusters kept in separate WP tracks for reviewability but synthesized in WP06.

## Parallel Work Analysis

### Dependency Graph

```
Track A:  WP01 (red-first clobber repro) ──▶ WP02 (three-way-recency restore + kind guard + report + comment amend)
Track B:  WP03 (red-first retro/doctor disagreement) ──▶ WP04 (restore merged_at writer + reopen-aware is_mission_merged)
                                                            ──▶ WP05 (#4091 CONTINGENT: coord-fixture repro → reconcile-or-verify-close)
Both:                                    WP02, WP04, WP05 ──▶ WP06 (cross-track synthesis + NFR census + green consolidation)
```

Tracks A and B are file-disjoint and run in parallel. WP06 is the only cross-track join.

### Work Distribution

- **Sequential within track**: red-first repro must land (and be RED on HEAD) before its fix WP.
- **Parallel streams**: Track A (`merge/executor.py` + new recency helper) and Track B (`merge/baseline.py`/executor writer + `status/lifecycle.py`) touch disjoint files — safe to parallelize.
- **Ownership**:
  - **WP01** owns `tests/merge/` (or `tests/lanes/`) Track-A red-first (real `integrate_mission_into_target(SQUASH)` harness, from `repro_3942.py`).
  - **WP02** owns `merge/executor.py` (`_capture_pre_target_planning_artifacts`, extended restore) + a **net-new pure three-way recency helper** + the `lanes/merge.py:631-633` comment amendment; consumes the `mission_runtime` classifier read-only. Must NOT touch `merge/conflict_resolver.py` (dead) or the `_MERGE_DRIVERS` registry.
  - **WP03** owns the Track-B red-first test driving the **real retrospect AND real doctor** readers to disagreement (constructed post-merge state; NO live coord merge — C-003).
  - **WP04** owns the `merged_at` writer beside `merge/baseline.py`'s pattern (call site `executor.py:951`) **and** the reopen-aware change in `status/lifecycle.py::is_mission_merged` — one coupled change; re-arms `surface_resolver.py:745` + `runtime_bridge.py:1600` by data.
  - **WP05** owns the #4091 coord-fixture repro in `merge/bookkeeping_projection.py` / status reducer — existence gated on the repro being RED on HEAD.
  - No `owned_files` overlap; `mission_metadata._MERGE_FIELDS` stays untouched.

### Coordination Points

- **Integration**: WP06 runs the combined regression (both red-first tests green) + the preserved #2709/#2804/#3981 suites, writes the FR-009 synthesis (record the #2709→#3942 target-newer lineage, the dead-`conflict_resolver.py` disposition for #2907, and the D-B1 husk-override authority note for #2160), and runs the NFR-003 complexity census.
- **Post-plan brownfield squad**: DONE — 3-lens convergent; decisions above are the re-locked result.
