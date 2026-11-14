# Implementation Plan: One checkout verdict for the planning commands

**Branch**: `kitty/mission-checkout-verdict-agreement-01M7B1GG` | **Date**: 2026-11-13 | **Spec**: [spec.md](spec.md)
**Input**: Mission specification from `kitty-specs/checkout-verdict-agreement-01M7B1GG/spec.md`; grounding in [research.md](research.md).

## Summary

`setup-plan` and `check-prerequisites` each compute the planning checkout verdict from
their own operands, so they disagree for a default Mission before and after topology
settlement (#7594). Slice 1 adds one shared helper in `mission_branch_context.py` that
returns `(current_branch, target_branch, expected_checkout_branch)`:

- the current branch comes from the invoking checkout;
- the landing target comes from `meta.json`;
- the expected checkout is `placement_seam(repo_root, slug).write_target(PRIMARY_METADATA).ref`.

Both commands feed that verdict into the existing `_inject_branch_contract`. Owned runs
keep their fact-derived values. Slice 2 (#7633) is deferred to the operator ruling Q8.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: typer, `mission_runtime.placement_seam`, `specify_cli.core.checkout_identity`
**Storage**: `meta.json` (read only)
**Testing**: pytest integration tests on real git repositories with the real create core and the real `finalize-tasks` (`test_planning_checkout_verdict.py`), plus the existing pins
**Target Platform**: Linux, macOS, Windows (CLI)
**Project Type**: single
**Performance Goals**: at most one seam resolution per command (NFR-001)
**Constraints**: no seam change and no commit-destination change (C-001, C-002)
**Scale/Scope**: 3 source files, 1 new test module, 1 changelog fragment

## Charter Check

- **Single canonical authority:** the verdict consumes the placement seam; no second resolver. Pass.
- **Red-first:** the acceptance test is committed red before the fix. Pass.
- **Smallest viable diff / locality:** only the verdict pair and the setup-plan display target. Siblings are filed and linked (research.md). Pass.
- **Gates:** no allowlist growth, and the gates are named in research.md. Pass.
- **Terminology:** Mission, not feature. Pass.

## Project Structure

### Documentation (this mission)

```
kitty-specs/checkout-verdict-agreement-01M7B1GG/
├── spec.md
├── plan.md
├── research.md
└── tasks.md / tasks/
```

### Source Code (repository root)

```
src/specify_cli/cli/commands/agent/
├── mission_branch_context.py       # new: PlanningCheckoutVerdict + resolve_planning_checkout_verdict
├── mission_setup_plan.py           # consume the verdict (drop _resolve_branch_match_operands)
└── mission_check_prerequisites.py  # consume the verdict
tests/specify_cli/cli/commands/agent/
└── test_planning_checkout_verdict.py
docs/changelog/unreleased/<id>.fixed.md
```

## Design

```python
@dataclass(frozen=True)
class PlanningCheckoutVerdict:
    current_branch: str            # invoking checkout HEAD (owned: owned.write_branch)
    target_branch: str             # meta.target_branch (landing target)
    expected_checkout_branch: str  # seam planning write ref (owned: owned.write_branch)

def resolve_planning_checkout_verdict(repo_root, mission_slug, *, invoking_root, owned, fallback_branch) -> PlanningCheckoutVerdict
```

- **Non-owned:**
  - `current = get_current_branch(invoking_root) or fallback`
  - `target = read_target_branch_from_meta(<seam PRIMARY_METADATA read dir>) or fallback`
  - `expected = placement_seam(...).write_target(PRIMARY_METADATA).ref`
  - If the seam cannot resolve (unreadable meta, unknown Mission), `expected = current`
    (silent match, #3124).
- **Owned:** all three come from the fact, unchanged.
- **setup-plan:** feeds `target_branch=verdict.target_branch` only into the branch
  contract. Its `target_branch` argument to the commit helpers is unchanged (C-002).
- **check-prerequisites:** resolves the invocation identity once at the entry point
  (#3786), as setup-plan does.
- `read_minted_mission_branch` and `_resolve_branch_match_operands` lose their callers and
  are deleted (dead-symbol gate).

## Complexity Tracking

None.

## Implementation Concern Map

### IC-01 — Shared planning checkout verdict

- **Purpose**: one helper decides the planning checkout verdict for both commands.
- **Relevant requirements**: FR-001, FR-002, FR-003, NFR-001, NFR-002, C-001, C-002
- **Affected surfaces**: `mission_branch_context.py`, `mission_setup_plan.py`, `mission_check_prerequisites.py`, and the tests patching `_resolve_branch_match_operands`
- **Sequencing/depends-on**: none
- **Risks**:
  - Existing pins that hand-seed a legacy meta (`mission_branch` without a stored
    `single_branch` topology) may have expected the minted branch. The seam does not honour
    such a field. If a pin asserts it, surface it to the operator: it is an
    expectation edit.
  - check-prerequisites now reads the invoking checkout, so a lane-worktree run reports
    its own branch (FR-006 parity).

### IC-02 — Coordination-less status commit through the seam (slice 2, deferred)

- **Purpose**: #7633. Waits for the operator ruling Q8.
- **Relevant requirements**: none declared yet (spec § Deferred scope)
- **Affected surfaces**: `coordination/transaction.py`, `git/commit_helpers.py:213`
  (docstring), and the `test_no_write_side_rederivation.py` #2453 entry
- **Sequencing/depends-on**: IC-01; the Q8 ruling
- **Risks**: shape (b) needs a seam change.
