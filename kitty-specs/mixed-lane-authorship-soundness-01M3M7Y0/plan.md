# Implementation Plan: Mixed-lane authorship soundness

**Branch**: `issue-5046-mixed-lane-authorship` (planning base = merge target; `branch_matches_target: true`) | **Date**: 2026-09-28 | **Spec**: [spec.md](spec.md)
**Input**: Mission specification from `kitty-specs/mixed-lane-authorship-soundness-01M3M7Y0/spec.md`

## Summary

The terminus reconciliation gate trusts an approved lane's whole first-parent spine as approved authorship, so a WP that committed to a shared (mixed) lane and was then canceled ships its content at exit 0 under every strategy (#5046). This mission (1) records **WP commit attribution** — the lane branch head stamped into the free-form `StatusEvent.policy_metadata` sidecar on every lifecycle transition of a lane-mapped WP, through the one pure seam every transition passes (`status/transition_pipeline.prepare_transition`); (2) adds **one strategy-independent canceled-content axis** to the gate: at claim-build time the canceled WP's unsuperseded final per-path state is derived from its attributed windows on the lane spine, and the verifier FAILs when the target carries that state; missing/contradictory attribution for an implemented canceled WP in a mixed lane becomes a claim **refusal**; the existing lane-level `authored_*` sets are left untouched so the issue 5018 availability fix cannot regress; and (3) builds the squash-capable mixed-lane fixture the red-first reproductions need (#5047).

## Technical Context

**Language/Version**: Python 3.11+ (repo floor; CI on 3.11/3.12)
**Primary Dependencies**: existing only — `typer`, `rich`, `ruamel.yaml`, git CLI via `specify_cli.consolidation.git_probes` / kernel git helpers; `spec_kitty_events` consumed unchanged (C-001). No new dependency (supply-chain section not applicable).
**Storage**: the mission's append-only `status.events.jsonl` (existing `policy_metadata` dict field; new inner key `lane_head`); no new file.
**Testing**: pytest — unit tests beside each touched module (`tests/status/`, `tests/consolidation/`), real-CLI reproductions in `tests/terminus/` (red-first, `@pytest.mark.regression` then converted per ADR 2026-07-17-1), named architectural gates only (C-005).
**Target Platform**: Linux/macOS/Windows CLI (cross-platform git plumbing only).
**Project Type**: single Python project (`src/specify_cli`, `tests/`).
**Performance Goals**: NFR-001 — ≤ 1 s added gate time on a 5-WP / 50-commit mixed lane; the capture probe is one `git rev-parse` per transition.
**Constraints**: C-001 (no events-schema change), C-002 (single authority: the status event log), C-003 (strategy-independent), C-004 (no `tests/integration/**`, consolidation start ordering, `--dry-run`, resume markers), C-005 (targeted tests), C-006 (red-first), NFR-002 (fail-closed reader).
**Scale/Scope**: ~150–250 src LOC capture (+ cutover-eligibility campsite) + ~450–600 src LOC gate (`wp_attribution.py` + claim + verifier + rendering); ~1,300–1,700 test LOC including a ~150–250 LOC conftest extraction and the real-CLI repros.

## Charter Check

| Charter rule | Status |
|---|---|
| Single canonical authority (DIRECTIVE_044) | PASS — attribution lives in the existing status event log; the gate reads it via the `specify_cli.status` facade; no sidecar file. |
| Architectural alignment / shared-package boundary | PASS — `policy_metadata` is CLI-local and already `dict[str, Any]` in `spec_kitty_events.diary`; the `extra='forbid'` `StatusTransitionPayload` never carries it (Zeitgeist bridge drops it). |
| ATDD-first / red-first (DIRECTIVE_034/041, C-011) | PASS — red-first real-CLI repros are a distinct WP committed before the gate change. |
| Close defect class by construction (DIRECTIVE_043) | PASS — the stamp is added in the one seam every transition passes (enforced funnel: `test_no_legacy_status_emit_callers.py`), not by each caller. |
| Campsite (DIRECTIVE_025) | PASS — tidy-first extraction of the duplicated terminus builder scaffolding precedes the fixture; `reconciliation.py` is already complexity-clean (every function under 10; the ceiling is 15, `pyproject.toml` mccabe). |
| Terminology canon | PASS — Mission, WP, execution lane; "provenance" avoided (existing meaning). |
| NO_FULL_HEAVY_SUITES_IN_MISSION | PASS — named gate files listed under Validation. |

## Project Structure

### Documentation (this mission)

```
kitty-specs/mixed-lane-authorship-soundness-01M3M7Y0/
├── spec.md / reasons-canvas.md / checklists/
├── plan.md              # this file
├── research.md          # decisions R-1…R-8
├── data-model.md        # attribution stamp, windows, canceled-content claim
├── quickstart.md        # how to reproduce / verify
├── contracts/attribution-and-verdicts.md
├── traces/              # tooling-friction, approach, design-decisions
└── tasks.md + tasks/    # /spec-kitty.tasks
```

### Source Code (repository root)

```
src/specify_cli/status/
├── lane_head.py                 # NEW: best-effort lane-head probe (lanes.json → lane branch → rev-parse)
└── transition_pipeline.py       # prepare_transition: injected lane_head_probe, stamps policy_metadata["lane_head"]
src/specify_cli/consolidation/
├── wp_attribution.py            # NEW: pure window reconstruction + canceled-commit resolution (reads events via specify_cli.status facade)
└── reconciliation.py            # claim: canceled_content + mixed-lane refusal; verifier: canceled-content axis; Divergence.canceled_content
tests/status/test_lane_head.py, tests/status/test_transition_pipeline.py (extend)
tests/consolidation/test_wp_attribution.py (NEW), tests/consolidation/test_reconciliation.py (extend)
tests/terminus/conftest.py       # shared scaffold extraction + squash-capable mixed-lane builder
tests/terminus/test_repro_5046*.py  # NEW red-first real-CLI repros (FAIL / PASS / REFUSE / production path)
```

**Structure Decision**: single project; two new small modules keep the pure logic testable and out of the 1,400-line `reconciliation.py` (deep-module design): `status/lane_head.py` (IO adapter, injected) and `consolidation/wp_attribution.py` (pure window/commit math over already-read events and first-parent spines).

## Design

Post-plan squad (paula-patterns brownfield, debugger-debbie residual hunt, debugger-debbie fixture probe) folded 2026-09-28; residual IDs R1–R8 and brownfield IDs B1–B9 refer to `research.md` R-9/R-10.

### D-1 Capture (FR-001)

- `prepare_transition(..., lane_head_probe: LaneHeadProbe | None = None)`: `None` means **no stamp** — the pipeline stays pure ("zero writes, zero locks, zero git", `status/transition_pipeline.py:26-28`) (B1). The two shells inject the real probe at all four call sites (`status/emit.py:944,1051`, `coordination/status_transition.py:1528,1836`); a named test pins that all four pass it.
- `status/lane_head.py::probe_lane_head(repo_root, mission_slug, wp_id) -> str | None`: lanes.json from the PRIMARY partition via the placement seam (`lanes/for_review_gate.py:82 _resolve_lane` pattern), `manifest.lane_for_wp`, skip the planning lane, `lane_created_branch`, `git rev-parse --verify refs/heads/<branch>` from the canonical root (`resolve_canonical_root` when `request.repo_root` is `None`; never `feature_dir`, which is the coord worktree under coord topology). Any absence/corruption/git error → `None` (best-effort; never blocks a transition). One rev-parse inside the status lock.
- Stamped on every persisted transition of a lane-mapped WP: `{**(request.policy_metadata or {}), "lane_head": sha}`.
- Campsite (B5): `status/cutover_eligibility.py:133-137,156` treats any non-empty `policy_metadata` as runtime-state evidence; re-key it on the claim keys (`shell_pid`/`agent`) and fix its docstring, with a focused test.

### D-2 Windows (FR-001/FR-005) — pure, in `consolidation/wp_attribution.py`

- Events come from `specify_cli.status.read_events(feature_dir)` in append (causal) order; `StoreError` → unattributable (NFR-002).
- **Implementation windows**: intervals in `{claimed, in_progress, blocked}` (R6: blocked counts as work); open stamp = the stamp on the entering transition, close stamp = the stamp on the leaving transition. An entered-implementation WP with no stamp, or a still-open window, is unattributable.
- **Review windows** (`for_review`/`in_review`): a commit inside the canceled WP's review window is attributed to it only if no other WP of the lane holds an implementation **or** review window over that commit (R5); otherwise contested → REFUSE.
- **Stamp validity** (R8): a stamp is valid iff it is an ancestor-or-equal of the lane tip (`merge-base --is-ancestor`); never test membership of the `coord_base..lane` range (the first WP's open stamp is the fork point, outside that range). Invalid → unattributable (history rewritten; cf. issue 5080 / issue 5151 as causes).
- A window's commits = first-parent commits in `(open, close]` intersected with the lane's first-parent spine `coord_base..lane`; **non-merge only** — merge commits (e.g. lane sync with the coord branch, `lanes/lifecycle_sync.py`; coord auto-rebase merges `workflow_executor.py:887,1764`) never attribute to a WP (B4/R3).
- Overlapping implementation windows of two WPs claiming the same commit → contested → REFUSE with an actionable "lane WPs ran concurrently" message (R7).

### D-3 Claim (FR-002/FR-003/FR-004/FR-005)

In `build_approved_wp_set`:
1. **Mixed lane** = `_lane_is_approved(lane)` **and** `any(wp in excluded_canceled_wp_ids)` — reusing the single merge-side authority `acceptably_canceled_wp_ids` (B2; `consolidation/done_bookkeeping.py:42`).
2. For each such canceled WP that **entered implementation** (event history has a transition into `claimed`/`in_progress`): resolve its commit set C (D-2). Any unattributable outcome → `_refusal_claim(...)` naming lane, WP, reason and recovery.
3. Walk the lane's first-parent spine with `first_parent_commits_in_range` **directly**, mapping `GitProbeError` → refusal (B3; never the tolerant `_lane_first_parent_spine`, whose `[]` would vacuously PASS). In the same newest→oldest walk record, per non-bookkeeping path (`_is_bookkeeping_path` semantics, R3): the newest **non-merge** commit touching it, and for paths touched by C, the canceled WP's final state and its **pre-state** = the path's content at the parent of the canceled WP's oldest commit touching it (R1). Reuse `changed_paths_of` / `blob_id_at` (`consolidation/git_probes.py`).
4. A path P is **canceled content** iff the newest non-merge commit touching P is in C and the canceled final state ≠ pre-state. Entry: `(wp_id, lane_id, path, canceled_state, pre_state)` where a state is a blob sha or `None` (absent).
5. `approved`, `authored_*`, `excluded_*`, `multi_lane_paths` stay byte-identical (no issue 5018-class regression surface).

### D-4 Verifier (FR-003/FR-005, C-003)

A new `_canceled_content_divergence(target_ref, claim)` step in `verify()`, after the claim-integrity refusals and before the strategy branch, for every strategy. For each entry, read the target state T and the window-base state W (`excluded_window_base`):
- T == canceled_state and W ≠ canceled_state → **FAIL** entry (introduced by this consolidation).
- T == canceled_state and W == canceled_state: **FAIL** if `pre_state_by_survivor` (a surviving lane commit's approved change was undone — SC-007 / R1), else no finding (R4: the target already carried it).
  (Post-tasks squad BLOCKER: without `pre_state_by_survivor` the R4 exemption swallowed both SC-007 shapes.)
- T == pre_state, or T == W → no finding (the canceled change did not land).
- otherwise (T is a merge of the canceled change with an independent change) → **REFUSE** "canceled change merged with an independent change" (R2).
A `GitProbeError` → REFUSE. REFUSE findings take precedence over FAIL; FAIL findings merge with the strategy axes' divergences into one `VerifyResult.failed`.
- `Divergence.canceled_content` + `describe()`: `file '<path>' carries canceled <WP>'s change (lane <lane>) on the target — canceled work would ship; revert <WP>'s change to '<path>' on the lane through a surviving WP's governed work, then re-run spec-kitty consolidate`; deletions/undo analogously. Residual R4b (another approved lane authored the identical state) FAILs — safe direction — and is documented.
- `verify()` stays ≤ complexity 15 by delegating to the new method; `_collect_excluded` docstring corrected (B6).

### D-4b REFUSE restores the target (FR-010)

- Post-tasks code-truth finding: `_phase_reconcile_before_teardown` (`consolidation/executor.py:2330-2343`) rolls back only on `VerifyStatus.FAIL`; the claim is captured pre-mutation (`_capture_reconciliation_claim`, `:3278`) but its `refusal` is only acted on by `verify()` after the mission→target advance, so every REFUSE exits 1 with the target advanced. Operator decision `01M3MAB8FTDKKVVTXPREK75AEP`: apply the same CAS rollback (`_rollback_target_after_failed_reconciliation`) to every REFUSE; no new pre-mutation exit (keeps off the sibling slice's start-ordering seam); correct the misleading comment.

### D-5 Fixture (FR-007/FR-008)

- Tidy-first (behaviour-preserving): extract the repo-init / coord-cut / lane-cut scaffolding shared by `build_coord_mission`, `build_coord_mission_mixed_lane`, `build_coord_mission_shared_file` (`tests/terminus/conftest.py:314-670`); add a `.gitignore` for `.worktrees/` in the fixture's init commit and use explicit-path `git add` (the `git add .` hazard captured the coord worktree as a gitlink and tripped the dirty-target guard, `git/ref_advance.py:144`).
- `_event(..., policy_metadata=None)` optional parameter.
- New builder `build_coord_mission_mixed_lane_canceled(...)` based on the working prototype (`scratchpad/fixture-probe/test_probe_d.py::build_mixed_lane_squash`, re-authored in-repo): survivor WP01 + canceled WP02 (canceled from `in_progress`) on one lane; plants WP02 add/modify/delete commits, optional survivor-superseding/undo commits, optional lane-sync merge; stamps (or omits) `lane_head` on the planted events; resolves the coord workspace last.
- FR-008: a test showing a post-build `update-ref` still consolidates, and that removing the coord worktree dir yields the unmaterialized abort; the builder docstring records this (retracting the #5047 claims).

## Complexity Tracking

No charter violations. New verifier step kept as its own method to hold `verify()` under complexity 15.

## Implementation Concern Map

### IC-01 — Terminus fixture scaffolding (tidy-first) and squash-capable mixed-lane builder

- **Purpose**: make mixed-lane canceled-content repros buildable under the default strategy without post-build mutation.
- **Relevant requirements**: FR-007, FR-008, SC-005.
- **Affected surfaces**: `tests/terminus/conftest.py`.
- **Sequencing/depends-on**: none.
- **Risks**: FR-008 root cause may sit in consolidation start (sibling slice) — time-box and file, don't fix.

### IC-02 — Red-first real-CLI reproductions

- **Purpose**: pin SC-001/SC-003 red through `spec-kitty consolidate` before the gate change; add SC-002/SC-004 positive controls.
- **Relevant requirements**: FR-003, FR-004, FR-005, FR-006, C-006.
- **Affected surfaces**: `tests/terminus/test_repro_5046*.py`.
- **Sequencing/depends-on**: IC-01.
- **Risks**: repro must assert the FAIL verdict text, not merely non-zero exit (post-spec BLOCKER 1).

### IC-03 — WP commit attribution capture

- **Purpose**: stamp the lane head on every lifecycle transition of a lane-mapped WP.
- **Relevant requirements**: FR-001, C-001, C-002, NFR-002.
- **Affected surfaces**: `src/specify_cli/status/transition_pipeline.py`, new `src/specify_cli/status/lane_head.py`, `tests/status/`.
- **Sequencing/depends-on**: none (parallel with IC-01).
- **Risks**: purity pins on the pipeline; cold-import boundary; git call inside the status lock (one rev-parse).

### IC-04 — Gate: per-WP canceled-content axis and mixed-lane refusal

- **Purpose**: FAIL unsuperseded canceled content, PASS superseded, REFUSE missing/contradictory attribution, strategy-independent.
- **Relevant requirements**: FR-002, FR-003, FR-004, FR-005, FR-006, NFR-001, NFR-003.
- **Affected surfaces**: new `src/specify_cli/consolidation/wp_attribution.py`, `src/specify_cli/consolidation/reconciliation.py`, `tests/consolidation/`.
- **Sequencing/depends-on**: IC-02 (red first), IC-03 (stamp format).
- **Risks**: issue 5018 false-FAIL regression (mitigated: `authored_*` untouched); review-window attribution rule; legacy in-flight missions now REFUSE (accepted).

### IC-05 — Production-path proof (time-boxed)

- **Purpose**: SC-006 real-CLI transition-driven twin (implement → commit → for_review → rework → cancel with no hand-written stamps) plus the half-by-half revert proof.
- **Relevant requirements**: FR-001, SC-006.
- **Affected surfaces**: `tests/terminus/` (or `tests/status/` if the CLI-driven fixture fits there better).
- **Sequencing/depends-on**: IC-03, IC-04.
- **Risks**: highest-risk item — driving real transitions needs the mission scaffold the CLI expects; time-box it and, if blocked, record the gap and fall back to driving `emit_status_transition` through the shells (still the production capture path).

### IC-06 — Residual pins and docs

- **Purpose**: FR-009 strict xfail (hunk-level), R4b / post-cancel-commit / never-claimed-commit (issue 5069) residuals documented, NFR-001 benchmark, gate docs, CHANGELOG, follow-up issues (dry-run surfacing, hunk-level supersession, for_review gate counting a sibling's commits).
- **Relevant requirements**: FR-009, NFR-001, C-007.
- **Affected surfaces**: `tests/consolidation/`, `docs/`, `CHANGELOG.md`, tracker.
- **Sequencing/depends-on**: IC-04.
- **Risks**: none beyond wording.

### IC-07 — REFUSE rollback

- **Purpose**: make every REFUSE restore the target like FAIL.
- **Relevant requirements**: FR-010, FR-005.
- **Affected surfaces**: `src/specify_cli/consolidation/executor.py` (gate verdict handling only), new focused tests.
- **Sequencing/depends-on**: none (parallel).
- **Risks**: resume flows that expect a refused target to stay advanced — grep tests asserting on target SHA after a refusal.

## Validation (targeted, C-005)

- `tests/status/test_transition_pipeline.py`, `tests/status/test_lane_head.py`, `tests/status/test_emit*.py`, `tests/specify_cli/coordination/test_status_transition.py`
- `tests/consolidation/test_reconciliation.py`, `tests/consolidation/test_wp_attribution.py`, `tests/terminus/` (file by file)
- `tests/status/test_cutover_eligibility*.py`, `tests/consolidation/test_done_bookkeeping*.py`, the executor tests that call `build_approved_wp_set`
- Named gates: `tests/architectural/test_no_legacy_status_emit_callers.py`, `test_status_module_boundary.py`, `test_cold_import_status_boundary.py`, `test_layer_rules.py`, `test_status_events_writes_gate.py`, `test_status_unsafe_allowlist.py`, `test_2093_authority_invariant.py`, `test_execution_context_parity.py`, `test_no_dead_symbols.py`, `test_merge_pipeline_ratchets.py`, `test_no_read_side_bypass.py`, `test_no_legacy_terminology.py`
- `make test-fast`, `ruff check .`, `ruff format --check .`, `mypy` on touched modules.
