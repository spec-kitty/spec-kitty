# Implementation Plan: Bound reconciliation windows at the Mission base (#7560)

**Branch**: `kitty/mission-mission-base-window-bound-01M78XB4` → lands on `fix/7560-dependency-ref-spine-base` | **Date**: 2026-11-12 | **Spec**: [spec.md](spec.md)
**Input**: Mission specification from `kitty-specs/mission-base-window-bound-01M78XB4/spec.md`; research in [research.md](research.md) and [research/](research/).

## Summary

On a fork, the target's pre-run tip (the *window base*) need not reach the commit the Mission branch was cut from (the *Mission base*). Every reconciliation window is `window_base..ref`, so on such a fork pre-Mission history is judged as Mission work. The fix has three parts:

1. Record the Mission base when the Mission branch is created, and resolve it for older Missions by deriving it from the scaffold commit.
2. Name the pre-Mission history: `rev-list <window_base>..<mission_base>`. It is empty whenever the target already reaches the base, which is the non-fork case.
3. Treat that history the way #6771 treats a verified declared dependency. Its commits drop out of the Mission-spine and recorded-tip guard walks. Its commits, final blobs and deletions are exempt on the closed-world, squash blob/deletion and patch-id axes.

Every verdict is byte-identical when the range is empty.

## Technical Context

**Language/Version**: Python 3.11+ (repo standard)
**Primary Dependencies**: git CLI (through `consolidation/git_probes.py`), typer/rich for the note line
**Storage**: `kitty-specs/<mission>/meta.json`, a new key `mission_base_sha`; no new `ConsolidationState` field
**Testing**: pytest. Red-first acceptance tests through `spec-kitty consolidate [--dry-run] [--strategy merge --dependency-ref]` on the terminus harness (`tests/terminus/conftest.py`), plus unit tests per module
**Target Platform**: Linux, macOS, Windows (git ≥ 2.38 already assumed by consolidation)
**Project Type**: single project, the CLI
**Performance Goals**: at most 3 extra git invocations per consolidate run (NFR-002); the pre-Mission walk is bounded by `window_base..mission_base`
**Constraints**: no refusal, exit-code or severity changes (C-001); one rollback authority (C-002); A2 surfaces untouched (C-003); facade compatibility (C-005)
**Scale/Scope**: about 6 source modules, about 5 test modules, 1 ADR amendment

## Charter Check

- **Single canonical authority**: one resolver, `consolidation/mission_base.py::resolve_mission_base`, owns the Mission base. The pre-Mission sets are computed with the existing `_final_authored_walk`, never a second walk. **Pass.**
- **Red-first (SO-4)**: WP01 lands both report shapes as strict-xfail tests through the pre-existing entry point, together with green soundness ratchets. **Pass.**
- **Tidy-first (SO-2)**: the resolver and its recording point are a separate enabler before any verdict changes. **Pass.**
- **Gate discipline (SO-5)**: no new gate in this plan. The #7593 gate is folded by ruling but blocked on PR #7596 (see below). **Pass.**
- **ADR governance**: verdict change under ADR `2026-09-29-1`, so an amendment is part of the Mission (FR-008). **Pass.**
- **Scope note (recorded decision)**: the operator's "all window axes" ruling named the closed-world, squash blob/deletion and patch-id windows. The approved-bound claim base and the canceled-content axes stay unchanged, per the dispatch non-goal "no change to the approved bound or canceled-content axes". They need no change: approval stamps descend from the base, so pre-base commits never enter `check_lane`. FR-004 is narrowed to match.

## Project Structure

### Documentation (this mission)

```
kitty-specs/mission-base-window-bound-01M78XB4/
├── spec.md  plan.md  research.md  data-model.md  quickstart.md
├── research/ (code-grounding.md, foldable-issues.md)
└── traces/   (tooling-friction.md, approach.md, design-decisions.md)
```

### Source Code (repository root)

```
src/specify_cli/meta_keys.py                         # MISSION_BASE_SHA_KEY
src/specify_cli/mission_metadata.py                  # TypedDict field
src/specify_cli/core/mission_creation_protected_mint.py  # record at topic/protected mint
src/specify_cli/missions/_create.py                  # record at coordination-branch create
src/specify_cli/consolidation/mission_base.py        # NEW: MissionBase + resolve_mission_base + pre_mission_history
src/specify_cli/consolidation/claim_inputs.py        # carry mission_base into the claim build
src/specify_cli/consolidation/reconciliation_closed_world.py  # guard walks exclude pre-Mission commits
src/specify_cli/consolidation/reconciliation_claim.py / _claim_types.py  # pre_mission_* claim fields
src/specify_cli/consolidation/reconciliation_verifier.py  # exemptions on closed-world / squash / patch-id
src/specify_cli/consolidation/phase_claim.py, forecast.py  # provenance note line
docs/adr/4.x/2026-09-29-1-*.md                       # amendment
docs/changelog/unreleased/7560.fixed.md
tests/consolidation/test_mission_base*.py, tests/consolidation/test_dependency_ref_mission_base_7560.py
```

## Implementation Concern Map

### IC-01 — Acceptance reproduction

- **Purpose**: pin both reported shapes red through `spec-kitty consolidate`, and pin that genuine post-base work still refuses.
- **Relevant requirements**: FR-003, FR-004, FR-005, SC-001..SC-003
- **Affected surfaces**: `tests/consolidation/test_dependency_ref_mission_base_7560.py` (new), terminus harness helpers if needed
- **Sequencing/depends-on**: none
- **Risks**: the harness commits planning on the target, so the fork shape must be planted as history the target lacks: cut the Mission branch from an "upstream" line, and reset the target behind it.

### IC-02 — Mission base authority

- **Purpose**: record the base at create and mint; resolve it with provenance (`recorded` → `derived` → `unavailable`); compute the pre-Mission history.
- **Relevant requirements**: FR-001, FR-002, NFR-002, NFR-003
- **Affected surfaces**: `meta_keys.py`, `mission_metadata.py`, `core/mission_creation_protected_mint.py`, `missions/_create.py`, new `consolidation/mission_base.py`
- **Sequencing/depends-on**: none
- **Risks**: the derivation must be fail-closed. A probe error or a non-ancestor gives `unavailable`; a target-reachable base gives an empty range.

### IC-03 — Guard and claim

- **Purpose**: pass the Mission base through `ClaimInputs` and remove the pre-Mission commits from the #6771 spine and recorded-tip walks. The declared-ref window stays `target..ref`. Attach the pre-Mission shas, blobs and deletions to the claim, and print the provenance note on the run and the forecast.
- **Relevant requirements**: FR-003, FR-006, FR-007
- **Affected surfaces**: `claim_inputs.py`, `reconciliation_closed_world.py`, `reconciliation_claim.py`, `reconciliation_claim_types.py`, `phase_claim.py`, `forecast.py`
- **Sequencing/depends-on**: IC-02
- **Risks**: overlap with PR #7596 (`reconciliation_closed_world.py`), so keep the diff local; the facade (`reconciliation.py`) must re-export any new name.

### IC-04 — Verifier axes

- **Purpose**: exempt pre-Mission history in `_unattributable_patch_id` (closed world, also the forecast scan), `_unattributable_content_squash`, `_window_has_non_bookkeeping_change` and `_reachable_excluded`'s patch-id window.
- **Relevant requirements**: FR-004, FR-005, NFR-001
- **Affected surfaces**: `reconciliation_verifier.py`
- **Sequencing/depends-on**: IC-03
- **Risks**: complexity ceiling 15 on the squash loop; the exemption must use the same set semantics as `external_dependency_*`.

### IC-05 — Governance and docs

- **Purpose**: ADR `2026-09-29-1` amendment, changelog fragment, and the CLAUDE.md "Declared dependency ref" paragraph.
- **Relevant requirements**: FR-008
- **Affected surfaces**: `docs/adr/4.x/`, `docs/changelog/unreleased/`, `CLAUDE.md`
- **Sequencing/depends-on**: IC-03, IC-04

### Deferred fold — #7593 (FR-009)

Operator ruling `01M78XC76BMN026BTEH4T1ADFM` folds #7593. Its gate needs `consolidation_events`, which only PR #7596 introduces, and that PR is open and unmerged (checked 2026-11-12). The fold is re-checked at closeout. If #7596 has merged by then, the gate is added post-consolidation on the branch; otherwise it is reported as blocked and #7593 stays `Refs`.
