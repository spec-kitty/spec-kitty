---
work_package_id: WP05
title: Hatch build hook, pyproject wiring, packaging and clean-install digest tests
dependencies:
- WP02
requirement_refs:
- C-001
- C-002
- C-003
- C-004
- FR-007
- FR-008
- FR-009
- FR-015
- NFR-003
planning_base_branch: feat/6451-built-in-from-open-packs
merge_target_branch: feat/6451-built-in-from-open-packs
branch_strategy: Planning artifacts for this mission were generated on feat/6451-built-in-from-open-packs. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into feat/6451-built-in-from-open-packs unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-built-in-pack-from-open-packs-01M59V4T
base_commit: 429375f9a9477ff8f3664fd95be7f7249054c6b1
created_at: '2026-10-19T12:40:03.298674+00:00'
subtasks:
- T021
- T022
- T023
- T024
- T025
- T047
history:
- timestamp: '2026-10-19T11:36:32Z'
  agent: planner-priti
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: hatch_build.py
create_intent:
- hatch_build.py
- tests/cross_cutting/packaging/test_sdist_offline_wheel.py
- tests/cross_cutting/packaging/test_installed_built_in_digest.py
execution_mode: code_change
model: sonnet
owned_files:
- hatch_build.py
- pyproject.toml
- tests/cross_cutting/packaging/test_packaging_safety.py
- tests/cross_cutting/packaging/test_sdist_offline_wheel.py
- tests/cross_cutting/packaging/test_installed_built_in_digest.py
role: implementer
tags: []
tracker_refs: []
---

# Work Package Prompt: WP05 – Hatch build hook, pyproject wiring, packaging and clean-install digest tests

## ⚡ Do This First: Load Agent Profile

Run `/spk-charter-profile-load python-pedro` and read `.kittify/charter/charter.md` before touching code. Load action context with `spec-kitty charter context --action implement`.

## Objective

Wheels and sdists ship the pinned built-in tree at `packs/built-in` after a digest check, never ship `packs/internal`, and a wheel builds from the sdist with no network.

Requirements: FR-007, FR-008, FR-009, FR-015, NFR-003, C-001, C-002, C-003, C-004.

## Context

- `pyproject.toml` ~L160-215: wheel `artifacts`, `force-include = { "packs/built-in" = "packs/built-in" }` (scoped on purpose, comment at L196-208), sdist `include` lists `packs/built-in/**`.
- Research R-4: hatch drops VCS-ignored files unless they are artifacts or force-included. Once the tree is gitignored (WP03), the static `force-include` may still work, but the hook must sync/verify first. Move the force-include into the hook's `build_data["force_include"]` so it only applies after verification; add `packs/built-in/**` to sdist `artifacts`.
- Hook: `[tool.hatch.build.hooks.custom]` → `hatch_build.py` (`BuildHookInterface.initialize(version, build_data)`). In a git checkout: fetch if missing (uses `pack_fetch`), verify digest. In an unpacked sdist (no `.git`, tree present): verify only, never fetch (C-003, FR-008). Mismatch → fail the build.
- The hook runs in an isolated build env where `charter` is not importable: load `pack_fetch` by file path (`importlib.util.spec_from_file_location`) or keep the hook self-contained and import only the digest + fetch modules. Make sure those modules import nothing outside the stdlib + `ruamel.yaml`/`yaml`; add the needed library to `[build-system].requires` if so.
- The hook inserts `<root>/src` on `sys.path` during the build to import `kernel`/`charter`; the sdist therefore carries `src/kernel` and `src/charter`. From an sdist the hook does NO fetch: it only re-verifies the shipped `packs/built-in` digest against the pin.
- Internal never ships (C-002): `test_packaging_safety.py:62,105` already guard package sets; add an explicit assertion that no `packs/internal` path is in wheel or sdist.
- Clean-install check (FR-015): install the built wheel into a fresh venv, locate `packs/built-in` through `charter.offering.pack_paths.built_in_root()`, compare `clean_tree_digest` with the pin.

Dependencies: Depends on WP02.

## Subtasks

### T021: Red packaging tests

- **Purpose**: Red packaging tests.
- **Steps**: Extend `test_packaging_safety.py`: wheel and sdist contain `packs/built-in/` files, contain nothing under `packs/internal/`. New `test_sdist_offline_wheel.py`: build sdist, unpack to tmp, build a wheel with network disabled (`GIT_*` unset, no `.git`, `SPEC_KITTY_PACK_OFFLINE=1`), assert success and digest match.
- **Edge cases / notes**: Mark these with the existing packaging markers; they are slow, run them file-scoped.
- **Validation**: the tests named under Test strategy pass, file-scoped.

### T022: Write `hatch_build.py`

- **Purpose**: Write `hatch_build.py`.
- **Steps**: Implement `initialize`: determine checkout vs sdist; ensure/verify tree; set `build_data['force_include']['packs/built-in'] = 'packs/built-in'` for wheel target only.
- **Edge cases / notes**: Fail with the WP02 error code text so release logs are actionable.
- **Validation**: the tests named under Test strategy pass, file-scoped.

### T023: pyproject wiring

- **Purpose**: pyproject wiring.
- **Steps**: Register the hook, remove the static wheel `force-include` (now in the hook), add sdist `artifacts` for `packs/built-in/**` and keep `packs/internal` excluded; update the comment block.
- **Edge cases / notes**: Run `test_pyproject_shape.py` after.
- **Validation**: the tests named under Test strategy pass, file-scoped.

### T024: Clean-install digest check

- **Purpose**: Clean-install digest check.
- **Steps**: `test_installed_built_in_digest.py`: install the wheel into a venv in tmp, run a one-liner computing the digest of `built_in_root()`, compare with the pin value.
- **Edge cases / notes**: This is the FR-015 ratchet; NFR-003 requires 0 differing files.
- **Validation**: the tests named under Test strategy pass, file-scoped.

### T025: Verify layout unchanged

- **Purpose**: Verify layout unchanged.
- **Steps**: Assert the wheel path is exactly `packs/built-in/...` at site-packages level as today (C-001).
- **Edge cases / notes**: Compare against the paths the kernel sibling walk expects.
- **Validation**: the tests named under Test strategy pass, file-scoped.

### T047: Editable-install and sdist-member cases

- **Purpose**: Close the editable-install and sdist-content gaps (A2, B2).
- **Steps**: Add an editable-install case to the clean-install check (`pip install -e` in a venv: `built_in_root()` resolves and digest equals the pin). Extend the packaging test to assert the sdist member list (includes `src/kernel`, `src/charter`, `packs/built-in/**`; zero `packs/internal/*`).
- **Edge cases / notes**: Use real `uv build`; no stubs.
- **Validation**: the tests named under Test strategy pass, file-scoped.

## Owned files

- `hatch_build.py`
- `pyproject.toml`
- `tests/cross_cutting/packaging/test_packaging_safety.py`
- `tests/cross_cutting/packaging/test_sdist_offline_wheel.py`
- `tests/cross_cutting/packaging/test_installed_built_in_digest.py`

Do not edit files outside this list. If you need to, stop and raise it with the orchestrator.

## Branch Strategy

Planning base and merge target: `feat/6451-built-in-from-open-packs`. Mission topology is `coord`; the lane for this WP is assigned in `lanes.json` by `spec-kitty agent mission finalize-tasks`. Work in the workspace that `spec-kitty implement` resolves; never reconstruct the path.

## Test strategy

ATDD red-first: write or update the failing test, show it red, then implement. Run narrow, file-scoped pytest only (never a whole directory):

```bash
uv run --no-sync pytest tests/cross_cutting/packaging/test_packaging_safety.py -q
uv run --no-sync pytest tests/cross_cutting/packaging/test_sdist_offline_wheel.py -q
uv run --no-sync pytest tests/cross_cutting/packaging/test_installed_built_in_digest.py -q
uv run --no-sync pytest tests/architectural/test_pyproject_shape.py -q
```

Also run `ruff check` and `ruff format --check --force-exclude` on changed files, and `mypy` on changed source modules. Record commands and pass/fail counts in the WP notes.

## Definition of Done

- All subtasks done; tests above green; ruff, format and mypy clean with no new suppressions.
- Complexity ≤ 15 per function; repeated literals hoisted.
- Only owned files changed.
- Offline sdist->wheel: build with `--no-isolation` from a local wheelhouse, with a PATH `git` shim that exits 1, `GIT_ALLOW_PROTOCOL=` and a dead `HTTPS_PROXY`; the test asserts the shim was never called.
- Real `uv build` of wheel and sdist: list members, zero `packs/internal/*` in either, and the extracted `clean_tree_digest` equals the pin.
- The editable-install case is part of the clean-install check; the packaging test also asserts the sdist member list.
- Requirements FR-007, FR-008, FR-009, FR-015, NFR-003, C-001, C-002, C-003 demonstrably covered by a test or gate.

## Risks

Isolated build env lacking imports; hatch silently dropping ignored files (prove with tests); accidental network fetch in sdist builds.

## Reviewer guidance

Build a wheel and an sdist locally and list their contents; confirm no `packs/internal` and the sdist path never fetches. Reviewer profile: reviewer-renata.

## Implement command

```bash
spec-kitty agent action implement WP05 --agent claude --mission built-in-pack-from-open-packs-01M59V4T
```
