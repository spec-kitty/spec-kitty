---
work_package_id: WP06
title: charter pack vendor becomes a pin-bump helper
dependencies:
- WP02
requirement_refs:
- FR-010
- FR-011
planning_base_branch: feat/6451-built-in-from-open-packs
merge_target_branch: feat/6451-built-in-from-open-packs
branch_strategy: Planning artifacts for this mission were generated on feat/6451-built-in-from-open-packs. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into feat/6451-built-in-from-open-packs unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-built-in-pack-from-open-packs-01M59V4T
base_commit: 0ac1fc082220aee3429dcc3f7d7f854651bad91b
created_at: '2026-10-19T12:40:27.745330+00:00'
subtasks:
- T026
- T027
- T028
- T029
- T048
history:
- timestamp: '2026-10-19T11:36:32Z'
  agent: planner-priti
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/charter/pack_vendor.py
create_intent: []
execution_mode: code_change
model: sonnet
owned_files:
- src/specify_cli/cli/commands/charter/pack_vendor.py
- tests/charter_offering/test_pack_vendor.py
role: implementer
tags: []
tracker_refs: []
---

# Work Package Prompt: WP06 – charter pack vendor becomes a pin-bump helper

## ⚡ Do This First: Load Agent Profile

Run `/spk-charter-profile-load python-pedro` and read `.kittify/charter/charter.md` before touching code. Load action context with `spec-kitty charter context --action implement`.

## Objective

`spec-kitty charter pack vendor [--pack <name>] [--ref <ref>] [--subtree <path>]` rewrites a pin (commit, subtree, digest) and copies no tree.

Requirements: FR-010, FR-011.

## Context

- `pack_vendor.py`: `_pin_path` L54, `_load_pin` L58, `check_built_in_pin` L67, `_resolve_sha` L77, `_fetch_subtree` L86, `_copy_tree` L100, `_assert_core_compatible` L113, `_swap_in` L125, `_verified_pin` L137, `vendor_built_in` L162, command `pack_vendor` L187.
- After this WP the command resolves the ref to a SHA, fetches the subtree through `pack_fetch.fetch_to_cache` into the cache only, computes the digest at the pin's level, keeps `requires_core` compatibility checking for the built-in pack, and writes the pin with `write_pack_pin`. No tree under `packs/` is touched.
- `--check` becomes an alias for `sync_packs.py --check` behaviour (or is removed with a pointer); the drift gate test that drives it is retired in WP07.
- Delete `pack_vendor._fetch_subtree`, `_copy_tree`, `_swap_in` and the `OPEN_PACKS_SUBTREE` constant; reuse `pack_fetch` (one authority).
- Fold #6364 `requires_core`: keep `requires_core` and enforce it in the pin bump (refuse when the fetched pack's `requires_core` excludes the current core).

Dependencies: Depends on WP02.

## Subtasks

### T026: Red tests

- **Purpose**: Red tests.
- **Steps**: Update `tests/charter_offering/test_pack_vendor.py`: bumping writes the new commit/subtree/digest; `packs/built-in` mtime/contents unchanged; `--pack internal` writes `level: org`; `--subtree packs/built-in` works; an incompatible `requires_core` refuses.
- **Edge cases / notes**: Use the WP02 bare-repo fixture.
- **Validation**: the tests named under Test strategy pass, file-scoped.

### T027: Rewire to `pack_fetch`

- **Purpose**: Rewire to `pack_fetch`.
- **Steps**: Replace `_fetch_subtree` with the core; resolve `--ref` to a 40-hex SHA via `git ls-remote` or the fetched commit.
- **Edge cases / notes**: URL only from the existing pin.
- **Validation**: the tests named under Test strategy pass, file-scoped.

### T028: `--pack` and `--subtree` options

- **Purpose**: `--pack` and `--subtree` options.
- **Steps**: Select `packs/<pack>.source.yaml`; `--subtree` overrides the pin's subtree.
- **Edge cases / notes**: Default `--pack built-in`.
- **Validation**: the tests named under Test strategy pass, file-scoped.

### T029: Remove tree copying

- **Purpose**: Remove tree copying.
- **Steps**: Delete `_copy_tree`/`_swap_in`; update help text and docstring.
- **Edge cases / notes**: Keep complexity ≤ 15.
- **Validation**: the tests named under Test strategy pass, file-scoped.

### T048: Red-first real-fetch bump test and requires_core enforcement

- **Purpose**: Prove the helper bumps pins through the shared core only.
- **Steps**: Red test first: `vendor --ref X` rewrites `*.source.yaml` and copies no tree, using a real fetch from the bare-repo fixture (no `ls-remote` stubbing); assert the recomputed digest equals the written one. Add the `requires_core` refusal test.
- **Edge cases / notes**: Ref resolution goes through the kernel primitive, not a new git spawn.
- **Validation**: the tests named under Test strategy pass, file-scoped.

## Owned files

- `src/specify_cli/cli/commands/charter/pack_vendor.py`
- `tests/charter_offering/test_pack_vendor.py`

Do not edit files outside this list. If you need to, stop and raise it with the orchestrator.

## Branch Strategy

Planning base and merge target: `feat/6451-built-in-from-open-packs`. Mission topology is `coord`; the lane for this WP is assigned in `lanes.json` by `spec-kitty agent mission finalize-tasks`. Work in the workspace that `spec-kitty implement` resolves; never reconstruct the path.

## Test strategy

ATDD red-first: write or update the failing test, show it red, then implement. Run narrow, file-scoped pytest only (never a whole directory):

```bash
uv run --no-sync pytest tests/charter_offering/test_pack_vendor.py -q
```

Also run `ruff check` and `ruff format --check --force-exclude` on changed files, and `mypy` on changed source modules. Record commands and pass/fail counts in the WP notes.

## Definition of Done

- All subtasks done; tests above green; ruff, format and mypy clean with no new suppressions.
- Complexity ≤ 15 per function; repeated literals hoisted.
- Only owned files changed.
- `pack_vendor._fetch_subtree`/`_copy_tree`/`_swap_in` and `OPEN_PACKS_SUBTREE` are deleted; the helper reuses `pack_fetch` (one authority).
- Red test first: `vendor --ref X` rewrites `*.source.yaml` and copies no tree, via real fetch from the bare-repo fixture (no `ls-remote` stubbing); asserts the recomputed digest equals the written one.
- #6364 `requires_core` decision: kept and enforced in pin-bump (refused when the fetched pack's `requires_core` excludes the current core).
- Requirements FR-010, FR-011 (folds #6364 requires_core) demonstrably covered by a test or gate.

## Risks

Callers of `check_built_in_pin` (drift gate) break; coordinate with WP07, which retires that gate.

## Reviewer guidance

Confirm no write under `packs/<pack>/` happens and that the written pin round-trips through `load_pack_pin`. Reviewer profile: reviewer-renata.

## Implement command

```bash
spec-kitty agent action implement WP06 --agent claude --mission built-in-pack-from-open-packs-01M59V4T
```
