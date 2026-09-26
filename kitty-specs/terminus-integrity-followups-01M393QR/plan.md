# Implementation Plan: Terminus Integrity Follow-ups

**Branch**: `fix/terminus-integrity-followups` | **Date**: 2026-09-24 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `kitty-specs/terminus-integrity-followups-01M393QR/spec.md`

## Summary

Close the last three open Epic #5001 workstreams left after PR #5012 landed the reconciliation-gate spine, by extending — not re-architecting — that spine:

- **WS1 (#5013, P1):** make the DEFAULT squash merge enforce the excluded/closed-world content guarantee via a **squash-sound blob-attribution axis** (attribute the squashed diff's content paths against approved lanes' first-parent authored blobs — content, never SHAs/patch-ids). Replaces the squash PASS early-return in `MergeOutcomeVerifier.verify`.
- **WS2 (#4982 #4997 #4985 #4991, P2):** make `merge --resume` **honor the persisted strategy** (today `MergeState.strategy` is a dead field) and **preserve pre-interrupt lane-tip commits** (today the reconciliation claim's coordination base is a live resume-start checkpoint, asymmetric with the already-persisted target window base).
- **WS3 (#4970, P3):** make the coordination write gate **refuse a stale-local-head self-materialization** that already carries committed matrix content, and route `issue-verdict` writes through the **fail-closed write resolver**.

Grounding: three read-only research lenses (`work/epic-5001-research/followup-{architect,debbie,paula}.md`), each re-verified against this base (`fix/terminus-merge-integrity` HEAD, the #5012 spine).

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: typer (CLI), rich (console), subprocess-driven git (no GitPython); pytest for tests
**Storage**: git refs / trees / blobs (the authority the gate verifies); `MergeState` JSON at `.kittify/merge-state.json`; `status.events.jsonl`; issue-matrix under `kitty-specs/<slug>/`
**Testing**: pytest — the mock-free real-CLI `tests/terminus/` harness (red-first repros), plus `tests/merge/`, `tests/git/`, `tests/coordination/`, `tests/mission_runtime/` unit coverage
**Target Platform**: cross-platform CLI (Linux / macOS / Windows 10+)
**Project Type**: single (CLI library under `src/`)
**Performance Goals**: CLI operations < 2s typical; new git probes add a bounded number of `git` invocations per merge (no O(commits²) scans)
**Constraints**: fail-closed on any ambiguity/probe-error (NFR-001); no new `mission_runtime → specify_cli` first-level subpackage import edge and no `_baselines.yaml` cap growth (C-002); every new function ≤ McCabe 15 (NFR-004); no new suppressions
**Scale/Scope**: repository-internal terminus/merge machinery in `src/specify_cli/{merge,coordination,git}` + `src/mission_runtime/`; ~6 production files, ~5 test files; no dependency changes (so the Supply-Chain planning section does not apply — no add/upgrade/remove of any package)

## Constitution Check (Charter)

*GATE: Must pass before Phase 0. Re-checked after Phase 1 design (below).*

- **ATDD-first (C-011):** every WP lands its failing test first. The `tests/terminus/` repros are `xfail(strict)` today; markers come off only on genuine green. ✅ planned.
- **Architectural gate discipline / non-vacuity (DIRECTIVE_043, SO#5):** the fixes close defect classes fail-closed (REFUSE on ambiguity), with positive+negative test arms; no vacuous PASS. ✅ planned (NFR-001, NFR-003).
- **Red-main / no green-washing (SO#9, SO#4):** honest xfail residuals; the 3-way merge-resolution content residual stays a tracked follow-up (C-003). ✅.
- **Canonical sources (SO#6):** extend the existing verifier/state/resolver seams; no improvised parallel authority. ✅.
- **Boundary integrity (C-002, layer rules):** no new layer edge; WS3 helper homes inside the already-ledgered `coordination` subpackage. ✅ (re-verify post-design).
- **Change-scope reconciliation:** smallest-viable-diff picks the file set; boy-scout cleanup stays inside touched files; no scope creep beyond the three workstreams. ✅.
- **Terminology canon:** Mission, not Feature; no `--feature` flags introduced. ✅.
- **Git/workflow (DIRECTIVE_045):** PR-bound; operator merges; consolidated linear history at closeout. ✅.

No violations → Complexity Tracking empty.

## Project Structure

### Documentation (this mission)

```
kitty-specs/terminus-integrity-followups-01M393QR/
├── plan.md              # This file
├── research.md          # Phase 0 — consolidated squad design
├── data-model.md        # Phase 1 — data-structure changes
├── quickstart.md        # Phase 1 — how to validate each workstream
├── contracts/           # Phase 1 — behavioral invariant contracts
└── tasks.md             # Phase 2 (/spec-kitty.tasks — NOT created here)
```

### Source Code (repository root)

```
src/specify_cli/
├── merge/
│   ├── reconciliation.py     # WS1: authored_blobs (FINAL blob per (lane,path)) + _unattributable_content_squash (diff --name-status A/M, REFUSE on "") + reorder None-base/empty-authored REFUSE above squash early-return
│   ├── git_probes.py         # WS1: blob_id_at(); changed_paths_in_range(--no-renames); first_parent_commits_in_range propagates GitProbeError — all raise → REFUSE
│   ├── executor.py           # WS1 honest pass-message (MUST NOT strip enforce_closed_world in the verify_reachability=False replace); WS2 strategy reseed + pre_mutation_coord persist (read-persisted-first) + resume anchoring  (SINGLE OWNER)
│   └── state.py              # WS2: additive fields only — strategy, pre_mutation_coord_sha/_ref, pre_interrupt_lane_tips
├── cli/commands/
│   ├── merge.py              # WS2: resume strategy precedence (explicit > persisted > config > SQUASH); REFUSE on strategy-flip (H1)
│   └── agent/issue_verdict.py# WS3: do_issue_verdict routes through resolve_for_write
├── coordination/
│   └── surface_resolver.py   # WS3: committed-matrix-content probe (placement-authority path / ls-tree subtree; path-drift ≠ absent) beside _coord_branch_is_local_head
└── ...
src/mission_runtime/
└── write_target_degrade.py   # WS3: assert_coord_write_materialized refuses stale-local-head-with-committed-content

tests/
├── terminus/                 # red-first repros (WP01 owns; markers removed at integration WP06 WITH captured before/after)
│   ├── conftest.py           #   blob_present_at helper + plant_canceled_commit returns the planted path
│   ├── test_repro_{4945,4977,4981}.py  # + DEFAULT-squash variants (blob/tree-presence observable, pin FAIL cause)
│   ├── test_repro_{4970,4982,4985,4991,4997}.py  # xfail → green
│   └── test_terminus_reconciliation_property.py   # [squash] param xfail → green + new clean-squash param
├── merge/
│   ├── test_git_probes_seam.py   # blob-probe unit tests (WP03, canonical seam home)
│   ├── test_reconciliation.py    # squash content-axis unit tests incl. FINAL-blob / second-parent exclusion (WP03)
│   └── test_merge_state_*.py      # strategy precedence + H1 flip; lane-tip CAS H3 (ancestor OK) + absent-base H4 (WP04)
├── coordination/ | mission_runtime/  # write-gate + issue-verdict-reroute unit tests, path-drift REFUSE (WP02)
```

**Structure Decision**: single-project CLI library. The load-bearing conflict-avoidance rule (learned from the #5012 mission retrospective): **`executor.py` has exactly one owning WP (WP05).** WS1's honest pass-message and WS2's strategy-reseed + resume-anchoring both live in `executor.py`. Per the post-plan architect finding, the strategy persist is homed as a **WP05 executor reseed** (mirroring the landed C-1 target reseed at `executor.py:2735`), so `resolve.py` is NOT touched and the WP04↔WP05 contract stays pure-additive `MergeState` fields — no required-kwarg change across WPs. WS1 needs **no** executor `authored_blobs` change: `_reconciliation_claim_for_gate`'s `replace(captured, verify_reachability=False)` already preserves `enforce_closed_world`/`authored_blobs` (WP05 must not strip them). Every other production file is single-owned. `tests/terminus/` is owned by WP01 (which ADDS red tests but never removes a marker); xfail-marker removal happens at integration as an **orchestrator-at-consolidation** step (NOT a WP — WP06 owns docs only; a WP owning the same repro files WP01 owns would be a static ownership overlap), serially, with captured per-repro before/after evidence, reviewed by the mandatory pre-merge squad. This is the established #5012 pattern.

## Parallel Work Analysis

### Dependency Graph

```
Parallel fan (no deps, disjoint files):
  WP01 test-harness (tests/terminus)          ─┐
  WP02 WS3 surface-write                       ─┤
  WP03 WS1 content-axis (git_probes+reconcil.) ─┤
  WP04 WS2 resume state+cli                     ─┤
                                                 │
Serial integration (shared executor.py):         │
  WP05 executor integration  (deps WP03, WP04) ──┘→ WP05
                                                        │
Integration + close:                                    ▼
  WP06 markers+docs+final-green (deps WP01..05) ───────→ WP06

Critical path: {WP03 | WP04} → WP05 → WP06  (depth 3)
```

### Work Distribution

- **Sequential work**: `executor.py` edits are all in WP05 (depends on WP03's reconciliation API + WP04's `MergeState` fields). Integration/marker-removal/docs in WP06.
- **Parallel streams**: WP01 (tests/terminus harness), WP02 (WS3 files), WP03 (git_probes+reconciliation), WP04 (state+resolve+cli merge.py) run concurrently — file-disjoint.
- **Agent assignments** (no file overlap is the real guard):
  - WP01 → debugger-debbie — `tests/terminus/` (harness + red-first repros incl. blob/tree-presence default-squash variants that pin the FAIL cause + the hard-coupled clean-squash positive)
  - WP02 → python-pedro — `write_target_degrade.py`, `surface_resolver.py`, `issue_verdict.py` + `tests/coordination|mission_runtime/` unit tests (incl. path-drift REFUSE, first-write success, flat/no-coord no-false-refuse); **must run + record the F11 blast-radius** (tests/coordination+status+cli+issue_matrix) and choose file-existence vs row-level accordingly
  - WP03 → python-pedro — `merge/git_probes.py`, `merge/reconciliation.py` + `tests/merge/test_git_probes_seam.py`, `tests/merge/test_reconciliation.py` (incl. FINAL-blob / second-parent-exclusion + per-REFUSE-branch error-injection)
  - WP04 → python-pedro — `merge/state.py` (additive fields), `cli/commands/merge.py` (strategy precedence + H1 flip-REFUSE) + `tests/merge/test_merge_state_*.py` (precedence table, H1, lane-tip CAS H3 ancestor-OK, absent-base H4)
  - WP05 → python-pedro — `merge/executor.py` only (honest pass-message without stripping `enforce_closed_world`; strategy reseed = persist attempt-1's executed value; `_resolve_pre_mutation_coord_sha` read-persisted-first; per-lane tip persist + resume anchoring at the consumption site)
  - WP06 → curator-carla / implementer-ivan (NOT the reviewer) — marker removal WITH captured before/after per repro, CHANGELOG + docs, final aggregate green

### Coordination Points

- **Integration**: WP05 consumes WP03's `reconciliation` API (authored_blobs + squash axis) and WP04's `MergeState` fields; both are additive so WP05 can develop against the declared signatures.
- **Marker removal at integration (orchestrator, at consolidation — NOT WP06)**: as each fix lands, its `tests/terminus/` `xfail(strict)` marker is removed and the repro must XPASS→green, with captured before/after. Additionally, after WP04's strategy fix lands but BEFORE WP05, verify #4982/#4997 STILL xfail (proves WP05's lane-tip work is load-bearing, not dead code — post-tasks renata). Any child that cannot fully close stays `xfail(strict)` with an honest reason (SO#9).
- **Integration tests**: blast-radius suites (`tests/merge`, `tests/coordination`, `tests/git`, `tests/lanes`, `tests/terminus`) + `make test-fast`; each WP declares its targeted surface.

## Complexity Tracking

*No Charter violations — table intentionally empty.*
