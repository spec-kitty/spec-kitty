# Implementation Plan: Provision the move-task git-validation fixture's charter (#7073)

**Branch**: `issue-7073-move-task-fixture-charter-provisioning` | **Date**: 2026-11-03 | **Spec**: `kitty-specs/move-task-fixture-charter-provisioning-01M6GA71/spec.md`
**Input**: Mission specification from `kitty-specs/move-task-fixture-charter-provisioning-01M6GA71/spec.md`

## Summary

`tests/tasks/test_move_task_git_validation_unit.py` builds its project through `git_repo_with_worktree`, which
writes `.kittify/config.yaml` with only `# Config\n` and never provisions a charter. Mission-type activation is
read from the activation ledger (`PackContext.from_config` → `load_activation_ledger`), which for that fixture is
absent, so `existing_mission_types()` is `[]` (correct, total, no backfill) and
`resolve_mission_type_context(repo, "software-dev")` raises `UnknownMissionTypeError`. The review-ward guard the
module exercises reaches that resolver through `charter.activation.api.code_producing_for`, which catches the
exception, logs it with `exc_info=True` and returns the built-in fallback — so all 15 nodes read a *fallback*
capability instead of the project's resolved `software-dev` profile.

The fix is test-side and minimal: provision the fixture through the production provisioner
(`tests/_factories.provision_test_charter` → `specify_cli.provisioning.default_charter.provision_default_mission_type_activations`,
the same call `spec-kitty init` makes), then pin the property red-first with two tests that resolve the
fixture's mission type and assert the capability read records no fallback warning. No `src/` file changes, no
assertion is loosened, and no node is skipped, xfailed, deselected or forced.

## Technical Context

**Language/Version**: Python 3.11 (repo pin, `pyproject.toml`)
**Primary Dependencies**: `pytest` (+ `pytest-randomly`, `pytest-xdist`), `typer.testing.CliRunner`; in-tree
`charter.*` and `specify_cli.*` packages via `uv run --frozen`
**Storage**: files — a temporary git repository per test (`tmp_path`), YAML activation ledger
**Testing**: `pytest`; the module is `tests/tasks/**`, an `out_of_matrix` directory
(`.github/ci-module-registry.yml`), so no per-PR shard runs it — local runs are the evidence and the nightly owns
the automated backstop
**Target Platform**: Linux (this host), Python 3.11
**Project Type**: single project (CLI + libraries)
**Performance Goals**: the module stays under 180 s for 15 nodes on this host (base measured 115–137 s)
**Constraints**: test-side only; must not collide with #7057/PR #7100 in the same helper; provisioning must be
the production one, not a second seeder
**Scale/Scope**: one test module (`tests/tasks/test_move_task_git_validation_unit.py`), one changelog fragment

## Charter Check

*GATE: passed before Phase 0 research; re-checked after Phase 1 design.*

| Governance rule | How this plan honours it |
| --- | --- |
| Single canonical authority (`DIRECTIVE_044`) | Provisioning goes through the one production provisioner; no second seeder, no hand-written YAML activation key. |
| ATDD-first / test-first bug fixing (`DIRECTIVE_034`, `DIRECTIVE_041`) | The defect gets a failing test through the pre-existing entry point (`resolve_mission_type_context` / `code_producing_for`) before the fixture changes. |
| Locality of change (`DIRECTIVE_024`) | One helper, one module, one new test class, one fragment. No `src/` edit. |
| Smallest viable diff | Two fixture lines plus the regression tests; nothing else in the module is touched. |
| Adversarial review | One independent reviewer round (small fix); reviewer and implementer are distinct roles. |
| Changelog fragments (#6988) | `docs/changelog/unreleased/<pr>.internal.md` — internal, test-only. |

## Project Structure

### Documentation (this mission)

```
kitty-specs/move-task-fixture-charter-provisioning-01M6GA71/
├── plan.md              # this file
├── research.md          # Phase 0: how mission-type activation is read, and which layer to fix
├── spec.md              # the mission specification
├── tasks.md             # Phase 2 output (/spec-kitty.tasks)
└── traces/              # approach / design-decisions / tooling-friction tracers
```

### Source Code (repository root)

```
tests/
├── _factories/
│   └── __init__.py                       # provision_test_charter (production-delegating, reused as-is)
└── tasks/
    └── test_move_task_git_validation_unit.py   # the only code file this mission edits
docs/
└── changelog/
    └── unreleased/
        └── <pr>.internal.md              # per-PR fragment
```

**Structure Decision**: the existing single-project layout. The mission edits one existing test module and adds
one changelog fragment; it adds no source tree, package or module.

## Research (summary; details in `research.md`)

- `existing_mission_types(repo_root)` → `PackContext.activated_mission_types` → `load_activation_ledger`; absent
  key → `frozenset()`, deliberately total (#2657).
- `resolve_mission_type_context` hard-fails (FR-006 activation gate) when the type is not in that set.
- The module's guard path is `_validate_ready_for_review` → `_is_code_producing` →
  `charter.activation.api.code_producing_for` → `resolve_mission_type_context(...).code_producing`, with a
  caught-exception fallback that logs `exc_info=True`.
- `spec-kitty init` provisions through `provision_default_mission_type_activations`, which for a fresh project
  writes `.kittify/charter/activation.yaml` (activation ledger, ADR `2026-10-19-1`); on the fixture it writes
  `software-dev, documentation, research, plan` and makes resolution succeed (`provenance: built-in`,
  5-step curated action sequence).
- Verified with a scratch probe: before provisioning `code_producing_for` returns `True` *via the fallback* with
  a logged traceback; after provisioning it returns `True` from the resolved profile with no log record. So the
  pin must assert the absence of the fallback record, not the boolean (which is identical either way).

## Implementation Concern Map

### IC-01 — Fixture charter provisioning plus its red-first pin

- **Purpose**: make the shared fixture a provisioned project and keep it that way, so the guard under test reads
  a resolved capability instead of a swallowed resolution failure.
- **Relevant requirements**: FR-001, FR-002, FR-003, FR-004, NFR-001, NFR-002, C-001, C-002, C-003
- **Affected surfaces**: `tests/tasks/test_move_task_git_validation_unit.py` (the `git_repo_with_worktree`
  fixture's `config.yaml` write region and a new test class); `docs/changelog/unreleased/<pr>.internal.md`
- **Sequencing/depends-on**: none
- **Risks**:
  - *Collision with PR #7100.* Both edit `git_repo_with_worktree`. #7100 touches the WP01 frontmatter
    (`owned_files`), the lane worktree's `Add implementation` commit and one node's `--agent`. This mission
    touches the `.kittify/config.yaml` write (adds one provisioning call) and appends a new test class at the
    end of the module. Keep those regions disjoint; if #7100 lands first, rebase is trivial because no hunk
    overlaps.
  - *Commit shape.* Existing nodes assert the lane branch's head subject and the repository's commit history.
    Provisioning must run **before** the fixture's `git add .` / `Initial commit`, so the ledger file lands
    inside that first commit and the commit count is unchanged.
  - *Vacuous pin.* `code_producing_for` returns `True` both before and after the fix, so a boolean-only assertion
    would be no-op passable. The pin asserts the resolved bundle (`mission_type`, non-empty `action_sequence`)
    and the absence of the fallback log record.

## Verification approach (red-first, recorded per command)

1. **Red (base `d18c4f1d58`).** New test 1 fails with `charter.activation.mission_type_profiles.UnknownMissionTypeError:
   Unknown mission type 'software-dev'. No registered mission types are available.`; new test 2 fails because
   `charter.activation.mission_type_profiles` logged `code_producing resolution failed for mission type
   'software-dev'; using the built-in default`.
2. **Green (fixture provisioned).** Both new tests pass; the module's 15 pre-existing nodes keep their ids,
   decorators and assertions and their fail/pass set.
3. **Non-vacuity.** Delete the provisioning call and both new tests fail again (revert proof). With PR #7100's
   fixture re-pin applied locally, the module is 15/15; without it, the same 8 nodes fail with the same
   `IMPLEMENTATION_MISSING` message that #7057 owns — proving this mission neither fixes nor masks #7057.
4. **No production change.** `git diff origin/main..HEAD -- src/` empty; `ruff check` / `ruff format --check`
   clean on the edited module; `check_changelog_style` and `check_spelling --pass unreleased` clean on the new
   fragment.

## Complexity Tracking

No charter violations; no complexity to justify.
