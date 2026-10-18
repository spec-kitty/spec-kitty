---
work_package_id: WP02
title: Write-side re-stamp gap + committed-data parity
dependencies: []
requirement_refs:
- FR-004
- FR-005
- FR-006
planning_base_branch: fix/charter-preflight-fresh-checkout
merge_target_branch: fix/charter-preflight-fresh-checkout
branch_strategy: Planning artifacts for this mission were generated on fix/charter-preflight-fresh-checkout. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/charter-preflight-fresh-checkout unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-charter-preflight-fresh-checkout-01M56P1S
base_commit: e222350f3d7c09e41ed9f12114cda979a29c72e6
created_at: '2026-10-18T05:20:24.289033+00:00'
subtasks:
- T008
- T009
- T010
- T011
- T012
phase: Phase 2 - Write-side hardening
history:
- timestamp: '2026-10-18T05:10:00Z'
  lane: planned
  agent: system
  shell_pid: ''
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/charter/activation/
create_intent:
- tests/charter/test_activate_restamps_bundle_hash.py
- tests/charter_offering/test_fresh_seed_restamp_parity.py
execution_mode: code_change
mission_id: 01M56P1SC40TNTJ070H1SB430S
model: sonnet
owned_files:
- src/charter/activation/**
- tests/charter/test_activate_restamps_bundle_hash.py
- tests/charter_offering/test_fresh_seed_restamp_parity.py
- .kittify/charter/synthesis-manifest.yaml
role: implementer
tags: []
tracker_refs: []
wp_code: WP02
---

# Work Package Prompt: WP02 – Write-side re-stamp gap + committed-data parity

## ⚡ Do This First: Load Agent Profile

Before reading anything else, load your assigned agent profile via the `/spk-charter-profile-load`
skill with profile id **`python-pedro`**. Adopt its identity, governance scope, and boundaries for
the whole work package. Then read `kitty-specs/charter-preflight-fresh-checkout-01M56P1S/plan.md`,
`research.md`, and `contracts/behavioral-contracts.md`.

## Objective

Close the write-side re-stamp gap: when `spec-kitty charter activate`/`--cascade` recompiles
`charter.yaml` (regenerating catalog/activation + graph/provenance), the synthesis manifest's
`bundle_content_hash` must be re-stamped in the same operation at the single
`charter.bundle.compute_bundle_content_hash` authority, so no committed drift is produced for clones to
inherit. Pin the fresh-project scaffold's existing re-stamp against regression, and correct this
repository's already-committed drifted `synthesis-manifest.yaml` so a clean clone has parity today.

## Context & Constraints

- **Root cause** (see `research.md`, R1/R7): commit `712aee06a9` was a `charter activate --cascade all`
  that edited `charter.yaml` + regenerated graph/provenance but left `bundle_content_hash` stale.
  `activation_engine.commit_plan` only writes `config.yaml`; the gap is in the **`charter.yaml`
  recompile** path that activate/cascade triggers.
- **Single hash authority** (C-002/FR-005): re-stamp via `compute_bundle_content_hash` only. The
  fresh-project scaffold (`src/specify_cli/cli/commands/charter/_fresh_project_layer.py`) already does
  this correctly — your job is to bring the activate/cascade recompile to the same guarantee and to pin
  the scaffold behaviour with a test (do not rewrite the scaffold).
- **Orthogonal to #3504** (C-003): do NOT touch `packs/built-in.source.yaml`,
  `src/charter/offering/packs/built_in_pin.py`, `src/charter/packs.py`, or `pack_vendor.py`.
- Do NOT run `make test-full`; do NOT regenerate `.github/ci-shard-timings.json`.
- Narrow `owned_files` during implementation to the exact recompile file(s) you touch; the `**` glob is
  the authoritative surface, not a license to sprawl.

## Subtasks & Detailed Guidance

### Subtask T008 – Red-first: activate/cascade recompile must re-stamp (RED now)

- Create `tests/charter/test_activate_restamps_bundle_hash.py`.
- Build a fixture project with a synthesized project charter (manifest `built_in_only: false`, stamp ==
  recompute initially). Run the activate/cascade path that recompiles `charter.yaml` (prefer the
  in-process engine API over a CLI subprocess; mirror how `tests/charter/test_activation_engine_charter_yaml.py`
  drives it).
- Assert (RED against current product): after the recompile,
  `compute_bundle_content_hash(repo) == load_yaml(manifest).bundle_content_hash`.

### Subtask T009 – Re-stamp at the activate/cascade `charter.yaml` recompile site

- Pin the exact persistence function that writes `charter.yaml` for activate/cascade (trace from
  `pack_manager.activate` / the cascade command through the `charter.yaml` compile/write; candidates
  include the compiler write path `charter.activation.compiler.write_compiled_charter` and/or a manifest
  refresh in the activation flow). Re-stamp `bundle_content_hash` there via
  `finalize_manifest(manifest.model_copy(update={"bundle_content_hash": compute_bundle_content_hash(repo)}))`,
  written through the manifest chokepoint.
- Preserve authored-content round-trip (never rewrite `charter.md`; keep ruamel comments). Only the
  derived `bundle_content_hash`/`manifest_hash` change.
- Make T008 green.

### Subtask T010 – Scaffold-parity regression test

- Create `tests/charter_offering/test_fresh_seed_restamp_parity.py` pinning that
  `_fresh_project_layer._synthesize_project_layer` stamps
  `bundle_content_hash == compute_bundle_content_hash(repo)` for a fresh-seed project. This guards the
  already-correct scaffold behaviour against future regressions.

### Subtask T011 – Committed-data parity fix (this repo)

- Re-stamp this repository's committed `.kittify/charter/synthesis-manifest.yaml` so its
  `bundle_content_hash` equals a recompute of the committed `charter.yaml`. Produce it via the corrected
  write path where practical (or an explicit `spec-kitty charter synthesize` on this branch), NOT a raw
  hand-edit that could drift again. Current drift: stamped `sha256:6a188326…` vs recompute
  `sha256:649ee217…`.
- Assert in a test (or via quickstart check) that `compute_freshness(repo).synthesized_drg.state` is a
  PASS state afterward. Do not alter authored charter content.

### Subtask T012 – Validate

- `mark-status` T008–T011 as completed.
- Run the blast-radius tests (see Test Strategy). Confirm no #3504 surface is touched (`git diff --stat`
  must not list vendor/pin files).

## Branch Strategy

- Planning/base branch: `fix/charter-preflight-fresh-checkout`; final merge target: `fix/charter-preflight-fresh-checkout` (PR to `main`, operator merges).
- Execution worktrees are allocated per computed lane from `lanes.json` by `finalize-tasks` — do not pick a base branch manually.

## Test Strategy (red-first)

```bash
PYTHONPATH="$PWD/src:$PWD" .venv/bin/python -m pytest tests/charter/test_activate_restamps_bundle_hash.py tests/charter_offering/test_fresh_seed_restamp_parity.py -q
PYTHONPATH="$PWD/src:$PWD" .venv/bin/python -m pytest tests/charter/ tests/charter_offering/ -q
```
Record exact commands + passed/failed counts in the PR. Do NOT run `make test-full`.

## Definition of Done

- T008 RED before the fix, GREEN after; activate/cascade recompile re-stamps at the single authority.
- Scaffold-parity test (T010) green; committed manifest (T011) re-stamped, `synthesized_drg` PASS on this repo.
- `ruff` + `mypy` clean on changed files; no #3504 surface touched; authored charter content byte-preserved.

## Risks & Reviewer Guidance

- **Finding the exact recompile site**: trace carefully; `commit_plan` is a decoy (it only writes
  config.yaml). Reviewer: confirm the re-stamp fires on the `charter.yaml` write, not just config.
- **Authored-content preservation**: reviewer confirm only `bundle_content_hash`/`manifest_hash` changed
  and `charter.md` is untouched.
- **Data fix provenance**: reviewer confirm the committed manifest was re-stamped via the corrected
  path / `charter synthesize`, matching the current `charter.yaml` exactly.
