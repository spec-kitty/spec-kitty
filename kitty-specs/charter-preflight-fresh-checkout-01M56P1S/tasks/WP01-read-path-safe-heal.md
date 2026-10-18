---
work_package_id: WP01
title: Read-path default-on safe-heal on next (+ red-first twin)
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-007
- NFR-001
- NFR-002
- NFR-003
planning_base_branch: fix/charter-preflight-fresh-checkout
merge_target_branch: fix/charter-preflight-fresh-checkout
branch_strategy: Planning artifacts for this mission were generated on fix/charter-preflight-fresh-checkout. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/charter-preflight-fresh-checkout unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
- T007
phase: Phase 1 - Release-unblocking core
history:
- timestamp: '2026-10-18T05:10:00Z'
  lane: planned
  agent: system
  shell_pid: ''
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/charter_runtime/preflight/
create_intent:
- tests/specify_cli/charter_runtime/test_fresh_checkout_preflight_heal.py
execution_mode: code_change
mission_id: 01M56P1SC40TNTJ070H1SB430S
model: sonnet
owned_files:
- src/specify_cli/charter_runtime/preflight/runner.py
- src/specify_cli/charter_runtime/preflight/hook.py
- src/specify_cli/charter_runtime/preflight/references_refresh.py
- tests/specify_cli/charter_runtime/test_fresh_checkout_preflight_heal.py
role: implementer
tags: []
tracker_refs: []
wp_code: WP01
---

# Work Package Prompt: WP01 – Read-path default-on safe-heal on `next`

## ⚡ Do This First: Load Agent Profile

Before reading anything else, load your assigned agent profile via the `/spk-charter-profile-load`
skill with profile id **`python-pedro`**. Adopt its identity, governance scope, and boundaries for
the whole work package. Then read `kitty-specs/charter-preflight-fresh-checkout-01M56P1S/plan.md`,
`research.md`, `data-model.md`, and `contracts/behavioral-contracts.md`.

## Objective

Make `spec-kitty next` on a freshly-cloned owned checkout exit `rc=0` when its `synthesized_drg` is
stale **only** because the committed synthesis manifest's `bundle_content_hash` lags a clean recompute
of `charter.yaml` and the derived artifacts are consistent — by adding a **lightweight, default-on,
in-process re-stamp heal** in the preflight layer. A genuine derived inconsistency must still block
(never greenwashed), read-only query mode must never mutate, and the warm path must gain **no**
subprocess. This is the release-blocking core of #6366.

## Context & Constraints

- **Root cause** (see `research.md`): `preflight.auto_refresh` defaults `False`, so
  `run_preflight_or_abort` calls `run_charter_preflight(auto_refresh=False)` and a committed-drifted
  `synthesized_drg: stale` becomes a terminal `CHARTER_PREFLIGHT_FAILED`. The existing heavy heal
  (`generate→synthesize→validate`) is opt-in and must stay untouched.
- **Safe-heal predicate** = `charter.activation.synthesizer.manifest.verify(manifest, repo)` passes AND
  `manifest.bundle_content_hash` is non-None AND `compute_bundle_content_hash(repo)` is non-None AND the
  two differ. See `data-model.md` for the exact predicate.
- **Layer direction**: the heal lives in `specify_cli.charter_runtime.preflight` and *consumes*
  `charter.*` authorities (`charter.bundle.compute_bundle_content_hash`,
  `charter.activation.synthesizer.manifest.{verify,finalize_manifest,load_yaml}`). Do **not** invert
  `charter <- specify_cli`. Do **not** put side effects in `freshness/computer.py` (it is a
  side-effect-free observer).
- **Single hash authority** (C-002): re-stamp via `compute_bundle_content_hash` only — no second recipe.
- Do NOT run `make test-full`; do NOT regenerate `.github/ci-shard-timings.json`.
- Run only file-scoped / dir-scoped tests (see Test Strategy) — not whole-repo sweeps.

## Subtasks & Detailed Guidance

### Subtask T001 – Red-first per-PR twin (RED now)

**Purpose**: Give the regression a cheap, deterministic per-PR home (the nightly e2e is why #6366 hid).

- Create `tests/specify_cli/charter_runtime/test_fresh_checkout_preflight_heal.py`.
- Build a fixture repo on disk (tmp_path) that mirrors the real failure: a `.kittify/charter/`
  containing a `charter.yaml`, a project `graph.yaml`, provenance sidecars, and a
  `synthesis-manifest.yaml` with `built_in_only: false` whose per-artifact `content_hash` entries MATCH
  the on-disk artifacts (so `manifest.verify(repo)` passes) but whose `bundle_content_hash` is a stale
  value ≠ `compute_bundle_content_hash(repo)`. Prefer deriving this from the committed repo fixtures
  under `tests/specify_cli/charter_runtime/` / `tests/specify_cli/charter_preflight/` (reuse an existing
  seed helper if one exists — check `tests/specify_cli/charter_preflight/_fixtures.py`), NOT by shelling
  out to `charter synthesize`.
- Assert (RED against current product): `run_preflight_or_abort(repo, consumer="next")` does **not**
  raise `typer.Exit`, and `compute_freshness(repo).synthesized_drg.state` is a PASS state afterward.
- Keep it deterministic: no wheel build, no subprocess, no concurrency saturation (that stays in the
  nightly e2e, untouched).

### Subtask T002 – Positive control on the same fixture (non-vacuity)

**Purpose**: Prove the probe can observe a genuine block (FR-003 / NFR-002).

- From the **same** shared fixture builder, derive a variant where an artifact body is mutated so its
  on-disk hash no longer matches the manifest entry (so `manifest.verify(repo)` raises
  `ManifestIntegrityError`).
- Assert `run_preflight_or_abort(repo, consumer="next")` **does** raise `typer.Exit(1)` with an
  actionable `blocked_reason`, and the manifest's `bundle_content_hash` is **unchanged** (no heal, no
  greenwash).
- Build both the heal-case and this control from one shared fixture so they cannot silently drift.

### Subtask T003 – Safe-heal predicate helper

**Purpose**: Encode the "authoring-only stamp lag vs genuine inconsistency" decision once.

- In `references_refresh.py`, add a pure helper (e.g. `bundle_hash_restamp_is_safe(repo_root) -> bool`
  or returning a small result object) implementing the predicate in `data-model.md`: load the manifest
  via the chokepoint, require `built_in_only is False`, require a project graph exists, require
  `manifest.bundle_content_hash` and `compute_bundle_content_hash(repo)` both non-None and unequal, and
  require `manifest.verify(repo)` to not raise. Any exception from `verify`/probes ⇒ return `False`
  (fail-closed, never heal on uncertainty).
- Keep imports of `charter.*` lazy (match the NFR-003 deferred-import pattern already in these modules).

### Subtask T004 – Lightweight in-process re-stamp

**Purpose**: Re-stamp `bundle_content_hash` without the heavy subprocess chain.

- Add a function that, given the predicate holds, loads the manifest, produces
  `finalize_manifest(manifest.model_copy(update={"bundle_content_hash": compute_bundle_content_hash(repo)}))`,
  and writes it back through the manifest chokepoint **atomically** (temp + rename, matching the existing
  manifest writer's path discipline). Change ONLY `bundle_content_hash` (and the derived `manifest_hash`
  that `finalize_manifest` recomputes); never rewrite authored content or artifact entries (NFR-002).
- Make it idempotent: if the stamp already matches, do nothing. Ensure two concurrent `next` runs on one
  owned root converge (NFR-003) — rely on atomic rename; confirm the writer the chokepoint uses is
  atomic (it is via `path_guard`), and add a brief note if additional locking is needed.

### Subtask T005 – Wire the heal into `run_charter_preflight` (default-on)

**Purpose**: Fire the heal on the advancing path regardless of `preflight.auto_refresh`.

- Add an `allow_heal: bool = False` parameter to `run_charter_preflight`. When `allow_heal` is True and
  the computed `synthesized_drg` is `stale`, run the predicate (T003); if safe, perform the re-stamp
  (T004) and **recompute freshness** (or mark that layer fresh) so the result `passed` is True. The heal
  is independent of `auto_refresh` — do not touch the existing `auto_refresh` heavy-refresh branch.
- Keep it off the warm path: the predicate/heal only runs when `synthesized_drg` is already stale, so a
  fresh repo pays nothing (NFR-001). No subprocess is spawned.

### Subtask T006 – Thread `allow_heal` through `hook.py`

**Purpose**: Mutate only in advancing mode; keep query read-only.

- `run_preflight_or_abort` (advancing `next` / `implement`): pass `allow_heal=True`.
- `run_preflight_warn_only` (read-only query `next`): pass `allow_heal=False` → no mutation; it already
  continues warn-only. Confirm `next_cmd._run_charter_preflight_for_next` advancing vs query routing is
  preserved (advancing calls `run_preflight_or_abort`; query calls `run_preflight_warn_only`).

### Subtask T007 – Validate

- `mark-status` T001–T006 done as you complete them.
- Run the blast-radius tests (see Test Strategy). Confirm the twin (T001) is green and the positive
  control (T002) still blocks. Confirm no mutation in query mode.
- Sanity-check on THIS repo: after the change, `spec-kitty next --mission <any> ...` advancing no longer
  returns `CHARTER_PREFLIGHT_FAILED` for the synthesized_drg stamp-lag (this repo's committed drift).

## Branch Strategy

- Planning/base branch: `fix/charter-preflight-fresh-checkout`; final merge target: `fix/charter-preflight-fresh-checkout` (PR to `main`, operator merges).
- Execution worktrees are allocated per computed lane from `lanes.json` by `finalize-tasks` — do not pick a base branch manually.

## Test Strategy (red-first)

```bash
PYTHONPATH="$PWD/src:$PWD" .venv/bin/python -m pytest tests/specify_cli/charter_runtime/test_fresh_checkout_preflight_heal.py -q
PYTHONPATH="$PWD/src:$PWD" .venv/bin/python -m pytest tests/specify_cli/charter_runtime/ tests/specify_cli/charter_preflight/ tests/specify_cli/charter_freshness/ -q
```
Record exact commands + passed/failed counts in the PR. Do NOT run `make test-full`.

## Definition of Done

- Twin (T001) RED before the fix, GREEN after; positive control (T002) blocks; query mode does not mutate.
- Heal is default-on (independent of `auto_refresh`), lightweight (no subprocess), idempotent, atomic.
- `ruff` + `mypy` clean on changed files; layer direction intact (`tests/architectural/test_layer_rules.py` green).
- No change to `freshness/computer.py` behaviour beyond read; no change to the heavy `auto_refresh` path.

## Risks & Reviewer Guidance

- **Greenwash risk**: the predicate MUST fail-closed — any `verify`/probe error ⇒ no heal. Reviewer:
  confirm the positive control proves a genuine inconsistency still blocks.
- **Query-mode mutation**: reviewer confirm `allow_heal=False` on the warn-only path and that the
  manifest is untouched in query mode.
- **Warm-path budget**: reviewer confirm the heal branch is reached only when `synthesized_drg` is
  already stale, and no subprocess is spawned.
- **Concurrency**: reviewer confirm atomic write; the nightly e2e runs 4 concurrent `next` on 2 owned roots.
