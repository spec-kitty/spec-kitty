# Implementation Plan: Audit collisions only between selectable Missions

**Branch**: `kitty/mission-audit-collision-selectable-missions-only-01M66YHT` | **Date**: 2026-10-30 | **Spec**: [spec.md](./spec.md)
**Input**: Mission specification from `kitty-specs/audit-collision-selectable-missions-only-01M66YHT/spec.md`
(GitHub issue spec-kitty/spec-kitty#6757)

**Note**: This plan was authored from the mission spec and the discovery record
in [research.md](./research.md). Design decisions D-1…D-6 there are binding on
the task decomposition below.

## Summary

`specify_cli.audit.engine.run_audit()` (the engine behind `spec-kitty doctor
mission-state --audit`) builds *one* Mission population — the default,
non-residue-aware `audit_repo()` walk — and feeds it to three repo-level
reports. Two of those are collision reports (`DUPLICATE_PREFIX`,
`AMBIGUOUS_SELECTOR`) and must be judged on the population Mission selection can
actually reach. The fix is a two-population split inside `run_audit()`: keep the
default walk for the per-folder `IDENTITY_MISSING`/identity findings and for
`DUPLICATE_MISSION_ID`, and derive a second, residue-aware population
(`audit_repo(repo_root, residue_aware=True)` +
`find_duplicate_prefixes(repo_root, residue_aware=True)`) for the two collision
reports only. No new predicate: the read-side rule from #5875 is reused verbatim,
and the existing engine pin test is updated to the corrected contract with both
directions pinned.

## Technical Context

**Language/Version**: Python 3.11 (project floor; CI also runs 3.12–3.14)
**Primary Dependencies**: stdlib only for this change (`pathlib`, `collections`);
`specify_cli.status.identity_audit`, `specify_cli.context.mission_resolver`
(existing in-repo modules), pytest for the tests
**Storage**: filesystem only — `kitty-specs/<mission>/meta.json` and the paths
`git ls-files` reports; the engine writes nothing
**Testing**: pytest; the mission's red-first test lives in `tests/audit/` and
drives the public `run_audit(AuditOptions(...))` entry point against real
git-backed fixtures (`@pytest.mark.git_repo`), matching
`tests/audit/test_engine_keeps_its_mission_rule.py` and
`tests/audit/test_residue_directory_finding.py`
**Target Platform**: the `spec-kitty` CLI on Linux/macOS developer workstations
and CI
**Project Type**: single project (Python package under `src/specify_cli/`)
**Performance Goals**: no measurable regression; measured on a 210-mission
scratch repository (half without a `mission_id`) the full engine run is ~0.07 s
and the residue-aware collision pair ~0.04 s, both far inside the standing
NFR-002 budget of < 3 s for a 200-Mission audit
**Constraints**: a constant, small number of additional batch `git ls-files`
probes per audit (two, one per residue-aware walk; they cannot share a memo
without a public-signature change), never a per-Mission git call; report output
stays deterministic (missions sorted by slug, findings by
`(artifact_path, code)`); the engine stays read-only and keeps raising
`GitCommandError` on a broken git index rather than degrading
**Scale/Scope**: one module (`src/specify_cli/audit/engine.py`), one engine pin
test, one changelog entry; ~14 lines of production change plus tests

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Single canonical authority** — PASS. The collision population comes from the
  one read-side Mission rule (`is_selectable_mission_dir`, exercised through
  `audit_repo(..., residue_aware=True)`); no second predicate, no copied rule.
- **ATDD-first / test-first-bug-fixing (DIRECTIVE_034)** — PASS by construction:
  the failing test through `run_audit()` lands before the engine change, and
  fails on current `main` (reproduced during discovery).
- **Locality of change (DIRECTIVE_024) / smallest viable diff** — PASS. One
  function's data flow plus its pin test; no signature changes to public
  helpers, no new module.
- **Terminology Canon (Mission vs Feature)** — PASS. The change speaks only of
  Missions and residue folders; no `feature*` vocabulary is introduced.
- **Pre-existing Failure Reporting Rule** — PASS. Any gate failing for an
  unrelated reason is classified against the merge base and reported, never
  skipped.
- **NO_FULL_HEAVY_SUITES_IN_MISSION** — PASS. Test selection is the audit
  suite, the two identity/selection suites the change implicates, and the
  colliding-mission integration test; no whole-repo run.

No violations; the Complexity Tracking table stays empty.

## Project Structure

### Documentation (this mission)

```
kitty-specs/audit-collision-selectable-missions-only-01M66YHT/
├── plan.md              # This file
├── research.md          # Discovery + Phase 0 decisions (D-1…D-6)
├── spec.md              # Mission specification (FR/NFR/C, SC)
├── tasks.md             # /spec-kitty.tasks output
└── traces/              # approach.md, design-decisions.md, tooling-friction.md
```

### Source Code (repository root)

```
src/specify_cli/
├── audit/
│   └── engine.py            # run_audit(), _compute_repo_findings_by_slug()  ← changed
├── status/
│   └── identity_audit.py    # audit_repo / find_duplicate_prefixes / find_ambiguous_selectors
│                            # (behaviour used as-is; four docstrings corrected)
└── context/
    └── mission_resolver.py  # is_selectable_mission_dir (used as-is)

tests/
├── audit/
│   └── test_engine_keeps_its_mission_rule.py   ← contract updated + new pin tests
├── doctor/
│   └── test_identity_audit.py                  # unchanged; run as the doctor-identity control
├── context/
│   └── test_is_mission_dir.py                  # unchanged; run as the predicate control
└── integration/
    └── test_colliding_mission_flow.py          # unchanged; run as the real-collision control

docs/changelog/CHANGELOG.md                     ← [Unreleased] entry (#6757)
docs/api/cli-commands.md                        # only if its audit description states the collision rule
```

**Structure Decision**: Single project. The defect is a data-flow choice inside
`src/specify_cli/audit/engine.py`; no new modules, packages or layers.

## Implementation Concern Map

### IC-01 — Collision population split in the audit engine

- **Purpose**: Make the two collision reports consume the selectable-Missions
  population while every other engine finding keeps its current population, so a
  residue folder can neither fake nor silence a collision.
- **Relevant requirements**: FR-001, FR-002, FR-003, FR-006, NFR-001, NFR-002,
  NFR-003, C-001, C-002
- **Affected surfaces**: `src/specify_cli/audit/engine.py` —
  `run_audit()` (add the residue-aware walk and correct its inline `#5875 /
  FR-008` comment, which currently says both collision codes "must stay"),
  `_compute_repo_findings_by_slug()` (accept the collision population; call
  `find_duplicate_prefixes(repo_root, residue_aware=True)` and
  `find_ambiguous_selectors(selectable_states)`; leave the
  `DUPLICATE_MISSION_ID` grouping on the engine population), and the module
  docstring's step list. `src/specify_cli/status/identity_audit.py` — docstrings
  only (module, `audit_repo`, `find_duplicate_prefixes`,
  `find_ambiguous_selectors`): each currently states that the audit engine's
  collision findings are unchanged, which this Mission makes false. Consumers
  unaffected: `_merge_checkout_disagreements`, `_build_report`,
  `identity_adapter`, and every `status` function's behaviour.
- **Sequencing/depends-on**: none
- **Risks**: the group must be *rebuilt* over the selectable population, never
  post-filtered (a residue folder in a three-member prefix group would otherwise
  silence the two real Missions); `DUPLICATE_MISSION_ID` must not move, since
  residue rows never carry a `mission_id` and moving it would be an unnecessary
  contract change.

### IC-02 — Both directions pinned in the engine suite

- **Purpose**: Turn the corrected contract into executable, non-vacuous tests,
  replacing the #5875 pin that asserts the old (wrong) collision behaviour while
  keeping its `IDENTITY_MISSING` half.
- **Relevant requirements**: FR-004, FR-002, FR-003, SC-001, SC-002, SC-003
- **Affected surfaces**: `tests/audit/test_engine_keeps_its_mission_rule.py`
  (rewritten around one shared fixture family), plus the CLI-level assertion
  that `doctor mission-state --audit --fail-on error` still exits 1 on the
  residue folder.
- **Sequencing/depends-on**: IC-01 for the green state; the red-first test lands
  before IC-01's change.
- **Risks**: an absence-only assertion (`001-real` has no collisions) is vacuous
  without a same-fixture positive control — the real-collision fixture must be
  built from the same helper and assert the findings are present. Half-by-half:
  reverting the `find_ambiguous_selectors` half must leave the duplicate-prefix
  assertion red, and vice versa.

## Phase 0 — Research (already complete)

See [research.md](./research.md). It records the reproduction on
`main@512567ee`, the supersession check, the operator ruling of 2026-10-27 from
#5875, the D-1…D-6 decisions, and the non-goal (the `IDENTITY_MISSING`
`backfill-identity` remedy on a `meta.json`-less folder, which this Mission
deliberately leaves alone).

## Phase 1 — Design

No `data-model.md`, `contracts/` or `quickstart.md`: the change adds no entity,
no public signature and no operator-facing workflow. The design is the
two-population data flow described in IC-01 and proven in IC-02.

## Complexity Tracking

*(No charter violations — table intentionally empty.)*
