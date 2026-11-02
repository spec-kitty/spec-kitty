# Implementation Plan: Make the migrate group-flag acceptance module own its git-discovery ceiling

**Branch**: `kitty/mission-migrate-group-flags-test-own-git-ceiling-01M6EKQH` | **Date**: 2026-11-02 | **Spec**: `kitty-specs/migrate-group-flags-test-own-git-ceiling-01M6EKQH/spec.md`
**Input**: Mission specification from `kitty-specs/migrate-group-flags-test-own-git-ceiling-01M6EKQH/spec.md`
**Issue**: spec-kitty/spec-kitty#6957

## Summary

`tests/cli/test_migrate_group_flags_4964.py` poisons `locate_project_root` but leaves the *root walk*
`specify_cli.core.paths.resolve_canonical_root` unisolated. On a host whose platform temp root sits
inside a git repository (this host: a stray `/tmp/.git`), the cutover's PRIMARY-home resolution ascends
into that repository, reports `<repo>/kitty-specs/<slug>`, and `_flip_phase` fails closed against the
fixture's real write target — the exact red in #6957. Today that is masked only by the process-wide
`GIT_CEILING_DIRECTORIES` that `tests/conftest.py` installs from the run basetemp (#7022/#5356); clear
that ambient value and the red returns verbatim.

The fix is tests-only: the module's autouse isolation fixture appends its own `tmp_path` to
`GIT_CEILING_DIRECTORIES` (via `monkeypatch`, so teardown restores it), so the module's discovery can
never climb above its own test root. Two red-first guards pin the property: a host-independent
standing-invariant assertion on `git_ceiling_dirs()` and a behavioural probe that runs the real CLI
positive control with the ambient ceiling cleared (skips, rather than passing vacuously, where the host
shape is absent).

## Technical Context

**Language/Version**: Python 3.11 (repository `requires-python` range; the venv here is 3.11)
**Primary Dependencies**: pytest, `typer`/`click` via `tests._click_universe`, `specify_cli.core.paths`,
`specify_cli.migration.runtime_state_cutover`, `tests.unit.migration._backfill_fixture`
**Storage**: filesystem only — `kitty-specs/<slug>/meta.json`, `status.events.jsonl` fixtures in `tmp_path`
**Testing**: pytest; the module carries `pytestmark = [pytest.mark.integration]`; run with
`uv run --frozen pytest tests/cli/test_migrate_group_flags_4964.py -q`
**Target Platform**: Linux/macOS dev hosts and CI runners; the defect only manifests where the platform
temp root is inside a git work tree, so the guard must be honest on both shapes
**Project Type**: single project (`src/specify_cli/…`, `tests/cli/…`, `tests/specify_cli/…`)
**Performance Goals**: the added guards cost < 15 s on this host (module baseline ≈ 33 s warm, ≈ 143 s cold)
**Constraints**: no production module changes; no deleted, skipped or weakened existing assertion; the
ceiling must be appended to, never replace, whatever the harness installed
**Scale/Scope**: one acceptance module (~76 existing tests) + two new guard tests + one changelog fragment

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Charter rule | Status | Note |
| --- | --- | --- |
| Single canonical authority | PASS | Reuses the repo's one ceiling idiom (`GIT_CEILING_DIRECTORIES` + `core.paths.git_ceiling_dirs`, `tests/_support/git_ceiling.py`); introduces no second mechanism. |
| ATDD-first (C-011) | PASS | Both guards are written and observed red before the fixture change (separate commit). |
| Test remediation & bug-fix discipline (DIRECTIVE_041/034) | PASS | Red-first through the pre-existing entry point (`_invoke`, the module's real CLI seam), not a helper. |
| Architectural gate discipline (DIRECTIVE_043) | PASS | The non-vacuity self-check is explicit: guard 1 fails on every host without the fix; guard 2 skips where its host shape is absent instead of passing vacuously. |
| Campsite cleaning (DIRECTIVE_025) | PASS (scoped) | The touched surface is a test module with no dead code or Sonar debt in the region being changed; no refactor is needed to land the fix. |
| Locality of change (DIRECTIVE_024) / smallest viable diff | PASS | Test-only, one module; no production or harness file changes. |
| Red-main & release discipline | PASS | The red is witnessed live (with and without the ambient ceiling) before the change; nothing is green-washed. |
| Test policy / `NO_FULL_HEAVY_SUITES_IN_MISSION` | PASS | Targeted module run plus the sibling placement test tree; no whole-repo suite. |
| Terminology canon | PASS | "PRIMARY home", "ceiling", "placement" used in their glossary senses (`docs/context/`). |

## Project Structure

### Documentation (this mission)

```
kitty-specs/migrate-group-flags-test-own-git-ceiling-01M6EKQH/
├── spec.md
├── plan.md              # this file
├── research.md          # discovery findings + grounding evidence
├── tasks/               # WP prompts (created by the tasks step)
└── (no data-model/quickstart — no data model, no user-facing quickstart)
```

### Source Code (repository root)

```
src/specify_cli/core/paths.py                                   # READ ONLY: git_ceiling_dirs, resolve_canonical_root
src/specify_cli/migration/runtime_state_cutover.py              # READ ONLY: _resolve_primary_home_or_degrade, _flip_phase
tests/cli/test_migrate_group_flags_4964.py                      # THE CHANGE: autouse isolation + 2 guard tests
tests/specify_cli/migration/test_runtime_state_cutover_placement.py  # reference idiom (reads `GIT_CEILING_DIRECTORIES`)
tests/_support/git_ceiling.py                                   # READ ONLY: harness ceiling contract
tests/unit/migration/_backfill_fixture.py                       # READ ONLY: build_mission fixture
docs/changelog/unreleased/<pr>.internal.md                      # changelog fragment (test-only → internal)
```

**Structure Decision**: single project. The only edited source file is the acceptance module; the rest
are read to confirm the contract the guard asserts.

## Design

### 1. Autouse isolation (the fix)

`_hard_repo_isolation` currently: asserts `tmp_path` is not inside the real checkout, chdirs into
`tmp_path/cwd`, and poisons `_LOCATE`. It gains one append:

```python
# The root walk the cutover uses (core.paths.resolve_canonical_root) is not
# patched above; pin it to this test's own root so an ambient repository
# enclosing the platform temp root (`/tmp/.git` — #6957, #7022) can never
# capture the PRIMARY-home resolution.
monkeypatch.setenv(
    "GIT_CEILING_DIRECTORIES",
    _append_ceiling(os.environ.get("GIT_CEILING_DIRECTORIES", ""), resolved_tmp),
)
```

where `_append_ceiling` keeps the existing value verbatim and appends `resolved_tmp` only when that
absolute entry is not already listed. Append-only is this helper's policy, not something git imposes:
it exists so the harness's value survives untouched (a leading empty entry is meaningful to git) while
the module's own root joins it. Dedupe is against absolute entries only, because
`git_ceiling_dirs` drops relative ones. `monkeypatch` restores the previous value at teardown
(NFR-002).

### 2. Guard A — standing invariant, host-independent (always runs)

```python
def test_module_pins_git_discovery_to_its_own_test_root(tmp_path: Path) -> None:
    assert tmp_path.resolve() in git_ceiling_dirs()
```

Red before the fixture change on every host, green after. This is the gate that cannot be vacuous, and
it mirrors `tests/_support/test_git_ceiling.py::test_this_session_has_its_basetemp_as_a_ceiling`.

### 3. Guard B — behavioural probe through the production entry point (host-shape dependent)

```python
def test_positive_control_survives_a_temp_root_inside_a_repository(tmp_path, monkeypatch) -> None:
    feature_dir = build_mission(tmp_path)                 # build the corpus first
    installed_value = os.environ["GIT_CEILING_DIRECTORIES"]  # what the fixture pinned
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", "")       # drop the ambient ceiling
    enclosing = resolve_canonical_root(feature_dir)        # the leak is real (or skip)
    assert installed_pin(installed_value, tmp_path)        # the fixture really pinned us
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", pin)     # restore ONLY that entry
    with pytest.raises(WorkspaceRootNotFound):             # the pin bounds the walk
        resolve_canonical_root(feature_dir)
    ...                                                    # then the real CLI control
```

Sequence inside the test: build the fixture corpus, capture the value the autouse fixture installed,
clear it, prove the unpinned walk escapes into the enclosing repository (or skip where that repository
is inside the test root, or none exists), assert the fixture really installed this test's root as an
absolute ceiling, then re-install **only that captured entry**, assert the walk now raises
`WorkspaceRootNotFound`, invoke the real CLI seam (`_invoke(["backfill-runtime-state", "--json"])` with
`_LOCATE` patched), and assert `exit_code == 0` with `flipped == 1`. The skip reasons name the absent
host shape, so the guard never reports a vacuous green; taking the pin from the fixture keeps the
half-by-half proof honest (removing the fixture wiring reds this test too).

### 4. Non-vacuity proof (recorded in the PR)

- Revert the fixture change → **both** guards red on this host (Guard B takes the pinned entry from the
  fixture's own environment and asserts the fixture installed one, so it fails too); Guard A red on CI
  as well, since it is host-independent.
- Restore → both green, plus the pre-existing 76 tests unchanged.
- Half-by-half: the fixture wiring is guarded uniquely by Guard A (invariant) and by Guard B's
  wiring assertion; the `_append_ceiling` mechanism is guarded by Guard B's production-path probe and
  by its own unit tests. Removing either part reds the guard that depends on it alone.
- Whole-module check: `git diff origin/main -- tests/ src/` shows additions only, no deleted
  assertion.

## Complexity Tracking

No charter violations; no complexity to justify.

## Implementation Concern Map

- **IC-01 — Autouse isolation append**: `tests/cli/test_migrate_group_flags_4964.py::_hard_repo_isolation`
  plus the `_append_ceiling` helper (append-only, idempotent, `monkeypatch`-restored).
- **IC-02 — Non-vacuity guards**: Guard A (invariant) and Guard B (behavioural probe with skip-not-pass
  semantics) in the same module, red-first.
- **IC-03 — Evidence trail**: changelog fragment, and the PR's *Tests run* section carrying the
  red-then-green commands, plus the tracer files for tooling friction.

## Risks

| Risk | Mitigation |
| --- | --- |
| Guard B is skipped on CI (no enclosing repo) and so proves little there | Guard A covers the invariant on every host; Guard B is the production-path, non-vacuity companion and states its skip reason explicitly. |
| Appending to `GIT_CEILING_DIRECTORIES` leaks into later tests in the same process | `monkeypatch` restores at teardown; the value is append-only and never replaced. |
| A future fixture inside `tmp_path` needs to discover an enclosing repo above it | Not a supported shape: the module's hard-isolation rule already forbids the real checkout and poisons `locate_project_root`; the ceiling makes that rule explicit. |
| Red-first evidence is disputed because the file is green on `main` | Grounding recorded in `research.md`: the red is reproducible in-process by clearing the ambient value, byte-for-byte matching the issue's error string; PR body cites it. |
