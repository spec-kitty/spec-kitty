---
work_package_id: WP09
title: 'Cutover: untrack packs/built-in and packs/internal'
dependencies:
- WP03
- WP04
- WP05
- WP06
- WP07
- WP08
requirement_refs:
- FR-001
- SC-001
planning_base_branch: feat/6451-built-in-from-open-packs
merge_target_branch: feat/6451-built-in-from-open-packs
branch_strategy: Planning artifacts for this mission were generated on feat/6451-built-in-from-open-packs. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into feat/6451-built-in-from-open-packs unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-built-in-pack-from-open-packs-01M59V4T
base_commit: 74b110c98086354bb6da06b14e70bd35ba17bf38
created_at: '2026-10-19T14:04:49.137880+00:00'
subtasks:
- T039
- T040
- T041
- T042
history:
- timestamp: '2026-10-19T11:36:32Z'
  agent: planner-priti
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: packs/built-in/**
create_intent: []
execution_mode: code_change
model: sonnet
owned_files:
- packs/built-in/**
- packs/internal/**
role: implementer
tags: []
tracker_refs: []
---

# Work Package Prompt: WP09 – Cutover: untrack packs/built-in and packs/internal

## ⚡ Do This First: Load Agent Profile

Run `/spk-charter-profile-load python-pedro` and read `.kittify/charter/charter.md` before touching code. Load action context with `spec-kitty charter context --action implement`.

## Objective

Remove both committed trees from git (`git rm -r --cached`), so open-packs is the only source, and prove a fresh sync reaches green.

Requirements: FR-001, SC-001.

## Context

- Lands last; every earlier WP must be approved.
- `git rm -r --cached packs/built-in packs/internal` keeps the working copies (now gitignored by WP03) so the lane keeps working.
- Allowed single out-of-map edit: remove the `xfail(strict=True)` marker in `tests/architectural/test_pack_trees_untracked.py` (owned by WP07), in the SAME commit as `git rm -r --cached`. No other edit outside the owned trees.
- Prerequisite: #6420/#6436 content must be landed upstream in open-packs before any new pin is minted; otherwise keep the current pin.
- Pack-manifest regen gate: editing pack paths trips it; run `spec-kitty charter pack regenerate-graph --check` against the synced tree.
- Before cutover, confirm the synced tree's digest equals the committed tree's digest for built-in (R-1) so no content changes for consumers.

Dependencies: Depends on WP03, WP04, WP05, WP06, WP07, WP08.

## Subtasks

### T039: Digest parity check

- **Purpose**: Digest parity check.
- **Steps**: Sync into a scratch dir and compare `clean_tree_digest` with the committed built-in tree; for internal compare with the pin (it intentionally differs from the old core copy, R-2).
- **Edge cases / notes**: Stop if built-in differs.
- **Validation**: the tests named under Test strategy pass, file-scoped.

### T040: Untrack the trees

- **Purpose**: Untrack the trees.
- **Steps**: `git rm -r --cached packs/built-in packs/internal`; confirm `git status` shows deletions and the files remain on disk.
- **Edge cases / notes**: Do not delete the pins.
- **Validation**: the tests named under Test strategy pass, file-scoped.

### T041: Flip the absence gate

- **Purpose**: Flip the absence gate.
- **Steps**: Remove the strict xfail; run the gate green.
- **Edge cases / notes**: See ownership note above.
- **Validation**: the tests named under Test strategy pass, file-scoped.

### T042: Fresh-clone verification

- **Purpose**: Fresh-clone verification.
- **Steps**: In a standalone clone (not a linked worktree), run `make dev-setup` then `make test-fast` and the targeted files; record counts.
- **Edge cases / notes**: Per memory notes, use a standalone clone for verification.
- **Validation**: the tests named under Test strategy pass, file-scoped.

## Owned files

- `packs/built-in/**`
- `packs/internal/**`

Do not edit files outside this list. If you need to, stop and raise it with the orchestrator.

## Branch Strategy

Planning base and merge target: `feat/6451-built-in-from-open-packs`. Mission topology is `coord`; the lane for this WP is assigned in `lanes.json` by `spec-kitty agent mission finalize-tasks`. Work in the workspace that `spec-kitty implement` resolves; never reconstruct the path.

## Test strategy

ATDD red-first: write or update the failing test, show it red, then implement. Run narrow, file-scoped pytest only (never a whole directory):

```bash
uv run --no-sync pytest tests/architectural/test_pack_trees_untracked.py -q
uv run --no-sync pytest tests/charter_offering/test_built_in_pin.py -q
```

Also run `ruff check` and `ruff format --check --force-exclude` on changed files, and `mypy` on changed source modules. Record commands and pass/fail counts in the WP notes.

## Definition of Done

- All subtasks done; tests above green; ruff, format and mypy clean with no new suppressions.
- Complexity ≤ 15 per function; repeated literals hoisted.
- Only owned files changed.
- In a fresh standalone git clone with `XDG_CACHE_HOME` set to a tmp dir: `make dev-setup`, `make test-fast`, then the test files for `pack_fetch`, `sync_packs`, packaging, `test_pack_trees_untracked` and kernel remote; the exact pass/fail counts are recorded in the WP notes and there are zero skips in those files.
- The xfail marker removal and `git rm -r --cached` happen in one commit (the single allowed out-of-map edit).
- Requirements FR-001, SC-001 demonstrably covered by a test or gate.

## Risks

Large deletion diff; any job missing the sync step goes red here (WP04 guard mitigates).

## Reviewer guidance

Confirm only deletions under the two trees plus the xfail flip, and that a fresh clone reaches green. Reviewer profile: reviewer-renata.

## Implement command

```bash
spec-kitty agent action implement WP09 --agent claude --mission built-in-pack-from-open-packs-01M59V4T
```
