# Implementation Plan: Owned single-branch lifecycle authority

**Branch**: `kitty/mission-owned-single-branch-lifecycle-authority-01M4J70Y` | **Date**: 2026-10-10 | **Spec**: [spec.md](./spec.md)
**Input**: Mission specification from `kitty-specs/owned-single-branch-lifecycle-authority-01M4J70Y/spec.md`

## Summary

Seven issues share one root: an owned-checkout `single_branch` lifecycle command folds the invocation root to `get_main_repo_root` (or `locate_project_root`/`get_status_read_root`) instead of consuming the already-validated `OwnedCheckout`. The approach is the seam already honoured by `review/cycle.py`, `accept.py`, `next_cmd.py`, `workspace/context.py`, and `git/protection_policy.py`: mint the fact once with `resolve_owned_mission` (or adopt via `adopt_owned_checkout`), thread it as an `owned=` kwarg through discovery → path/material selection → preflight → commit routing, and resolve every path through `placement_seam(repo_root, slug, owned=owned)` / `ProtectionPolicy.resolve_for_owned`. No second ownership resolver is introduced and `core/paths.py` is not changed (grounding confirmed every fix routes *around* that shared seam). Non-owned primary/coordination behaviour and all ownership refusals are preserved.

## Technical Context

**Language/Version**: Python 3.11+ (repo runs 3.11–3.13; mypy --strict)
**Primary Dependencies**: typer, rich, ruamel.yaml (existing CLI stack); `mission_runtime.OwnedCheckout` seam
**Storage**: Git (mission artifacts under `kitty-specs/<slug>/`); append-only `status.events.jsonl`
**Testing**: pytest; `make test-fast` baseline + targeted blast radius (`tests/specify_cli/**`, `tests/integration/test_owned_*`, finalize/decision/tasks/record-analysis modules). NO heavy suites in-mission (`NO_FULL_HEAVY_SUITES_IN_MISSION`); CI owns the full matrix at the draft PR.
**Target Platform**: Linux/macOS/Windows CLI
**Project Type**: single project (`src/specify_cli/`, `src/mission_runtime/`)
**Performance Goals**: no new O(tree) scans; one ownership-claim resolution per command; CLI < 2s typical
**Constraints**: single canonical authority; `core/paths.py` unchanged; ATDD red-first; terminology canon
**Scale/Scope**: exactly the 7 issues; ~8 command/surface modules + their targeted tests

## Charter Check

*GATE: passes before and after design.*

- **Single canonical authority** — thread the one `OwnedCheckout`; no second ownership resolver; `core/paths.py` unchanged (C-001). ✅
- **Architectural alignment** — consume `mission_runtime.OwnedCheckout` only via the package root and the `owned=` placement/protection seam; no new module seams. ✅
- **DDD + tiered rigour** — core judgment (branch/placement/commit routing) gets the heaviest coverage; glue/output gets proportionate tests. ✅
- **ATDD-first (C-011)** — each WP lands a failing-first reproduction test (RED on `planning_base_branch`, GREEN on final commit) as its first commit (C-003). ✅
- **Terminology canon** — Mission (not feature); run `tests/architectural/test_no_legacy_terminology.py` when touching charter/offering prose (C-004). ✅
- **No full heavy suites in mission** — targeted files + named gate files only. ✅
- **Smallest viable diff + locality (DIRECTIVE_024/025)** — per-surface edits mirror the sibling owned arms; no opportunistic widening beyond the 7-issue fence (C-002). ✅

No violations → Complexity Tracking omitted.

## Project Structure

### Documentation (this mission)

```
kitty-specs/owned-single-branch-lifecycle-authority-01M4J70Y/
├── spec.md              # substantive requirements (committed)
├── plan.md              # this file
├── research.md          # grounding + adopted-vs-rewrote provenance (DIRECTIVE_003)
├── decisions/           # specify Decision Moment ledger (committed)
├── checklists/          # requirements quality checklist (committed)
└── tasks/               # WP prompts (/spec-kitty.tasks output)
```

### Source Code (repository root)

```
src/specify_cli/
├── cli/commands/
│   ├── decision.py                         # IC-01 (#5874 host)
│   └── agent/
│       ├── mission_check_prerequisites.py  # IC-02 (#5877)
│       ├── tasks.py                         # IC-03 (#5878 CLI surface)
│       ├── tasks_map_requirements.py        # IC-03 (#5878)
│       ├── mission_finalize.py              # IC-04 (#5880)
│       ├── mission_finalize_lanes.py        # IC-04 (#5880)
│       ├── mission_finalize_planning_pin.py # IC-04 (#5880)
│       ├── mission_finalize_bootstrap.py    # IC-04 (#5892)
│       └── mission_record_analysis.py       # IC-05 (#5893)
├── decisions/{service.py,emit.py}          # IC-01 (#5874)
├── orchestrator_api/decision_verbs.py      # IC-01 (#5874 — operator D2 extension)
├── status/emit.py                          # IC-03 (#5878 owned guard on emit_inner_state_changed)
├── git/report_transaction.py               # IC-05 (#5893 recording)
├── analysis_inputs.py (missions/)          # IC-05 (#5893 authority half — operator D3)
├── charter/generate.py                     # IC-05 (#5893 authority half — operator D3)
└── review/cycle.py                         # IC-06 (#5947 defensive hardening)

tests/
├── integration/test_owned_*.py             # per-surface owned reproductions
└── specify_cli/test_owned_history_support.py  # IC-06 (#5947 invariant)
```

**Structure Decision**: single-project CLI; edits are localized per command surface, each mirroring the sibling owned arms. No new packages or module seams.

## Implementation Concern Map

> Concerns are NOT work packages. `/spec-kitty.tasks` turns these into WPs — here the mapping is 1:1 and sequential because every concern converges on the shared `OwnedCheckout` + placement seam; sequential execution avoids repeated collisions and dogfoods the owned single-branch path.

### IC-01 — Decision Moment owned authority (#5874)

- **Purpose**: Resolve an owned single_branch mission at the Decision Moment entry points and thread the fact through the decision service/emit placement, host CLI **and** `orchestrator-api` verbs.
- **Relevant requirements**: FR-001, FR-008.
- **Affected surfaces**: `cli/commands/decision.py`, `decisions/service.py`, `decisions/emit.py`, `orchestrator_api/decision_verbs.py`.
- **Provenance**: adopt-with-rebase `codex/5874-owned-decisions` (`28e526d73`; one import-line merge) **and EXTEND** to `decision_verbs.py` (branch omitted it; operator decision D2).
- **Sequencing/depends-on**: none (first — it is the specify entry point).
- **Risks**: must keep `resolve_owned_or_adopt` (returns `None` for non-owned) so default/coord missions still work; `verify()` skips coord fork-detection only when owned.

### IC-02 — Owned prerequisite branch contract (#5877)

- **Purpose**: Carry `owned.write_branch` as the prerequisite capsule's `expected_checkout_branch` so the branch match is correct for a protected-mint owned mission.
- **Relevant requirements**: FR-002, FR-008.
- **Affected surfaces**: `cli/commands/agent/mission_check_prerequisites.py`.
- **Provenance**: adopt-as-is `codex/5877-owned-prerequisites` (`96252a666`).
- **Sequencing/depends-on**: none.
- **Risks**: non-owned callers must pass `None` → byte-identical legacy contract; `commit_to_target` control stays green.

### IC-03 — Owned requirement mapping (#5878)

- **Purpose**: Add `--owned-checkout` to `map-requirements`, thread the fact through mission selection, spec/WP reads, protection checks and commit routing; refuse a foreign mission in `emit_inner_state_changed`.
- **Relevant requirements**: FR-003, FR-008.
- **Affected surfaces**: `cli/commands/agent/tasks.py`, `tasks_map_requirements.py`, `status/emit.py`. **No `core/paths.py` change.**
- **Provenance**: adopt-as-is `codex/5878-owned-requirement-mapping` (`885833015`); confirm composition with the `mission_write_lock` already on main.
- **Sequencing/depends-on**: none.
- **Risks**: lock keys on the owned-resolved primary dir — verify the reworked integration suite after.

### IC-04 — Owned finalize-tasks family (#5880 + #5892)

- **Purpose**: Consume the owned write branch in finalize branch setup (skip the legacy protected-target recovery triad when owned), and compute the validate-only lane preview with the stored `single_branch` topology + mission branch.
- **Relevant requirements**: FR-004, FR-005, FR-008.
- **Affected surfaces**: `mission_finalize.py`, `mission_finalize_lanes.py`, `mission_finalize_planning_pin.py` (#5880); `mission_finalize_bootstrap.py` (#5892).
- **Provenance**: adopt-with-rebase `codex/5880-owned-task-finalization` (`4c0f5130c`) + `28a262f00` (#5892). Kept together (operator instruction); the two edits are disjoint files.
- **Sequencing/depends-on**: none.
- **Risks**: base drifted in unrelated write-ledger regions → rebase the small edits onto current files; preserve the legacy refusal for non-owned missions.

### IC-05 — Owned analysis recording + material/charter authority (#5893)

- **Purpose**: Resolve the owned mission in `record-analysis`, read material/charter inputs from the owned checkout, commit the wrapped report on the owned write branch; **and** (operator D3) admit a package-identical GLOBAL template mirror with a `template-selection:<kind>` freshness identity and thread owned through `charter generate` destinations.
- **Relevant requirements**: FR-006, FR-006a, FR-008.
- **Affected surfaces**: `cli/commands/agent/mission_record_analysis.py`, `git/report_transaction.py` (recording); `missions/analysis_inputs.py`, `charter/generate.py` (authority half).
- **Provenance**: adopt-as-is `2084975b9` (recording); adopt-with-rebase `9dafc88d3` (authority — `DoctrineService`→`ActiveCharterService`, `CharterPackConfigError`→`ActiveCharterConfigError`, `_declared_paths(source=)`). Keep the guard relaxation EXACTLY as reviewed (byte-identical mirror only). Run the terminology guard.
- **Sequencing/depends-on**: none.
- **Risks**: must not weaken external-authority guards beyond the reviewed package-identical mirror; the deeper #5253/#5380 classes stay out of scope.

### IC-06 — Review/cycle owned resolver invariant (#5947)

- **Purpose**: Pin by construction that a validated owned single_branch `review/cycle` arm never consults `get_main_repo_root`, and tidy the one latent smell (`ProtectionPolicy.resolve(main_repo_root)` → `resolve_for_owned(owned, slug)` guarded by owned-is-None fallback). Verify-green on the scoped file; no fabricated red, no test-expectation edits.
- **Relevant requirements**: FR-007, FR-008.
- **Affected surfaces**: `review/cycle.py`, `tests/specify_cli/test_owned_history_support.py`.
- **Provenance**: no repair branch (new work; operator decision D4). The two named nightly tests are empirically GREEN on current `main`; the red nightly ran on an older commit.
- **Sequencing/depends-on**: none (last).
- **Risks**: cannot witness the nightly red locally (out-of-matrix sweep forbidden in-mission); the defensive invariant test + tidy harden the mechanism by construction and the next green nightly self-closes #5947.
