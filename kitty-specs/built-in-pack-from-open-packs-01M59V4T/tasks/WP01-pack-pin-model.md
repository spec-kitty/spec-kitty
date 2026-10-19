---
work_package_id: WP01
title: PackPin model with subtree and digest level, internal pin
dependencies: []
requirement_refs:
- C-005
- FR-002
- FR-011
planning_base_branch: feat/6451-built-in-from-open-packs
merge_target_branch: feat/6451-built-in-from-open-packs
branch_strategy: Planning artifacts for this mission were generated on feat/6451-built-in-from-open-packs. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into feat/6451-built-in-from-open-packs unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-built-in-pack-from-open-packs-01M59V4T
base_commit: eed3806ff59d0b9a062b23be9a8ef47b69e4da73
created_at: '2026-10-19T12:14:39.357157+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
- T050
history:
- timestamp: '2026-10-19T11:36:32Z'
  agent: planner-priti
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/charter/offering/packs/pack_pin.py
create_intent:
- src/charter/offering/packs/pack_pin.py
- packs/internal.source.yaml
- tests/charter_offering/test_pack_pin.py
execution_mode: code_change
model: sonnet
owned_files:
- src/charter/offering/packs/pack_pin.py
- src/charter/offering/packs/built_in_pin.py
- src/charter/packs.py
- tests/charter_offering/test_pack_pin.py
- tests/charter_offering/test_built_in_pin.py
- tests/architectural/test_charter_facades_reexport_offering.py
role: implementer
tags: []
tracker_refs: []
---

# Work Package Prompt: WP01 – PackPin model with subtree and digest level, internal pin

## ⚡ Do This First: Load Agent Profile

Run `/spk-charter-profile-load python-pedro` and read `.kittify/charter/charter.md` before touching code. Load action context with `spec-kitty charter context --action implement`.

## Objective

> **Out-of-map edit (recorded):** this WP also edits `packs/built-in.source.yaml` and creates `packs/internal.source.yaml`. They are left out of `owned_files` because finalize-tasks' lane planner treats `packs/built-in.source.yaml` and WP09's `packs/built-in/**` as the same scope (string-prefix match), which produced a false lane cycle.

Generalise the built-in pin into one `PackPin` model that every pack uses. Add the `subtree` field and a `tree_digest.level` field, keep `BuiltInPin` as an alias (removal-target note: the alias module `built_in_pin.py` is transitional and carries a docstring note naming WP06/WP07 callers as the removal trigger), and mint the internal pin `packs/internal.source.yaml`.

Requirements: FR-002, FR-011, C-005.

## Context

- `src/charter/offering/packs/built_in_pin.py:51-130` holds `BuiltInPinError`, `TreeDigest` (algorithm, value), `BuiltInPin` (repository, commit, tree_digest, requires_core), `load_built_in_pin`, `verify_built_in_pin` (calls `clean_tree_digest(pack_root, level=BUILT_IN)` at L119) and `write_built_in_pin`.
- `src/charter/offering/packs/pack_clean_digest.py:104` `clean_tree_digest(pack_root, *, level: PackTier, kinds=None)` accepts only `built-in|org|project` (research R-3). Internal is an org pack, so its pin records `level: org`.
- Re-exports: `src/charter/packs.py:28-34,105` facade, and `tests/architectural/test_charter_facades_reexport_offering.py` pins the facade surface.
- Current pin `packs/built-in.source.yaml`: commit `7f063aec...`, no `subtree`. Research R-1: keep that commit, add `subtree: built-in`.
- Data model: `data-model.md` (PackPin table).

**Prerequisite (orchestrator task, not core code):** the internal pin needs an open-packs commit whose `packs/internal/pack.yaml` restores `pack_level: org`, `active_charter` and `pack_drg` (and keeps `pack_version: 1.0.0`), per DM 01M59YNJWKKHG6KJVBGF56K0PQ. The orchestrator opens that PR on `spec-kitty/spec-kitty-open-packs`. Until it merges, mint the internal pin with a commit placeholder only if the digest you compute matches; otherwise stop and ask for the merged SHA.

**B5 internal pin rule:** the internal pin MUST reference an open-packs SHA whose `packs/internal/pack.yaml` contains `pack_level: org` and `pack_version: 1.0.0` (pending open-packs PR branch `fix/internal-descriptor-4x-core`, head `b5484f3`, not yet pushed; the orchestrator supplies the merged SHA). Until supplied, implement the model and the built-in pin and leave the internal pin with a clearly marked `TODO` that FAILS a test (`test_internal_pin_has_real_sha`), never silently passing. Do not loosen the core schema to work around it.

Dependencies: none (can start immediately).

## Subtasks

### T001: Write failing tests for `PackPin`

- **Purpose**: Write failing tests for `PackPin`.
- **Steps**: Create `tests/charter_offering/test_pack_pin.py`: load a pin with and without `subtree`/`tree_digest.level`; reject `..`, absolute and backslash subtrees; reject a non-40-hex commit; reject an unknown level; round-trip `write`→`load` keeps field order and comments header. Run red first.
- **Edge cases / notes**: Absent `level` defaults to `built-in` (backward compatible). Absent `subtree` on the built-in pin: refuse with an actionable `PackPinError` naming the field, because FR-011 needs the path explicit.
- **Validation**: the tests named under Test strategy pass, file-scoped.

### T002: Introduce `pack_pin.py` with `PackPin`, `PackPinError`, `TreeDigest.level`

- **Purpose**: Introduce `pack_pin.py` with `PackPin`, `PackPinError`, `TreeDigest.level`.
- **Steps**: Move the model into `src/charter/offering/packs/pack_pin.py`: `load_pack_pin(path)`, `verify_pack_pin(pin, root)` (uses `pin.tree_digest.level`), `write_pack_pin(pin, path)`. Keep `requires_core` optional. Validate subtree as a relative POSIX path (`PurePosixPath`, no `..` parts, not absolute).
- **Edge cases / notes**: Reuse `_require_str`/`_optional_str` patterns from `built_in_pin.py:78-90`. Keep complexity ≤ 15.
- **Validation**: the tests named under Test strategy pass, file-scoped.

### T003: Turn `built_in_pin.py` into a thin alias module

- **Purpose**: Turn `built_in_pin.py` into a thin alias module.
- **Steps**: `BuiltInPin = PackPin`, `BuiltInPinError = PackPinError`, `load_built_in_pin`/`verify_built_in_pin`/`write_built_in_pin` delegate. Update `src/charter/packs.py` facade to also export the new names, and update `test_charter_facades_reexport_offering.py` expectations.
- **Edge cases / notes**: Existing callers (`pack_vendor.py`, `test_built_in_release_parity.py`) must keep working unchanged in this WP.
- **Validation**: the tests named under Test strategy pass, file-scoped.

### T004: Add `subtree: built-in` to the built-in pin

- **Purpose**: Add `subtree: built-in` to the built-in pin.
- **Steps**: Edit `packs/built-in.source.yaml`: add `subtree: built-in` and `tree_digest.level: built-in`, change `repository` to the HTTPS URL `https://github.com/spec-kitty/spec-kitty-open-packs.git` (no SSH; CI has no credentials), keep commit/digest/requires_core. Update the header comment to say the tree is fetched, not vendored.
- **Edge cases / notes**: `tests/charter_offering/test_built_in_pin.py` keeps passing against the still-committed tree.
- **Validation**: the tests named under Test strategy pass, file-scoped.

### T005: Mint `packs/internal.source.yaml`

- **Purpose**: Mint `packs/internal.source.yaml`.
- **Steps**: repository = open-packs URL, commit = the open-packs commit carrying the restored internal `pack.yaml` (prerequisite above), `subtree: packs/internal`, `tree_digest.level: org`, value = `clean_tree_digest(<that subtree>, level="org")`. No `requires_core`.
- **Edge cases / notes**: Compute the digest from a fetched copy of the open-packs subtree, never from core's committed `packs/internal` (that copy differs, R-2).
- **Validation**: the tests named under Test strategy pass, file-scoped.

### T050: C-005 subtree-layout test

- **Purpose**: Prove the pin subtree works for both open-packs layouts.
- **Steps**: In `test_pack_pin.py` (fixture repo with each layout, or the WP02 fixture once available) assert `subtree: built-in` and `subtree: packs/built-in` both validate and resolve to the same relative-path semantics; assert the built-in pin URL starts with `https://`.
- **Edge cases / notes**: Layouts are `built-in/` and `packs/built-in/` (C-005).
- **Validation**: the tests named under Test strategy pass, file-scoped.

## Owned files

- `src/charter/offering/packs/pack_pin.py`
- `src/charter/offering/packs/built_in_pin.py`
- `src/charter/packs.py`
- `packs/built-in.source.yaml`
- `packs/internal.source.yaml`
- `tests/charter_offering/test_pack_pin.py`
- `tests/charter_offering/test_built_in_pin.py`
- `tests/architectural/test_charter_facades_reexport_offering.py`

Do not edit files outside this list. If you need to, stop and raise it with the orchestrator.

## Branch Strategy

Planning base and merge target: `feat/6451-built-in-from-open-packs`. Mission topology is `coord`; the lane for this WP is assigned in `lanes.json` by `spec-kitty agent mission finalize-tasks`. Work in the workspace that `spec-kitty implement` resolves; never reconstruct the path.

## Test strategy

ATDD red-first: write or update the failing test, show it red, then implement. Run narrow, file-scoped pytest only (never a whole directory):

```bash
uv run --no-sync pytest tests/charter_offering/test_pack_pin.py -q
uv run --no-sync pytest tests/charter_offering/test_built_in_pin.py -q
uv run --no-sync pytest tests/architectural/test_charter_facades_reexport_offering.py -q
```

Also run `ruff check` and `ruff format --check --force-exclude` on changed files, and `mypy` on changed source modules. Record commands and pass/fail counts in the WP notes.

## Definition of Done

- All subtasks done; tests above green; ruff, format and mypy clean with no new suppressions.
- Complexity ≤ 15 per function; repeated literals hoisted.
- Only owned files changed.
- C-005 asserted: pin subtree works for both `built-in/` and `packs/built-in/` layouts (fixture repo with each layout).
- Built-in pin repository is `https://github.com/spec-kitty/spec-kitty-open-packs.git`; a test asserts HTTPS.
- Internal pin references an open-packs SHA containing `pack_level: org` and `pack_version: 1.0.0`; until the orchestrator supplies it, a marked TODO fails `test_internal_pin_has_real_sha` (never silent).
- Requirements FR-002, FR-011, C-005 demonstrably covered by a test or gate.

## Risks

Facade re-export gate breaks if names are dropped. The internal pin cannot be finalised before the open-packs PR merges.

## Reviewer guidance

Check the alias keeps every old name importable, the subtree validation rejects traversal, and the internal pin's digest level is `org`. Reviewer profile: reviewer-renata.

## Implement command

```bash
spec-kitty agent action implement WP01 --agent claude --mission built-in-pack-from-open-packs-01M59V4T
```
