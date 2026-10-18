# Tasks: Fix charter preflight blocking `next` on a fresh checkout

**Mission**: charter-preflight-fresh-checkout-01M56P1S (#6366)
**Branch**: `fix/charter-preflight-fresh-checkout` → PR to `main` (operator merges)
**Spec**: [spec.md](./spec.md) · **Plan**: [plan.md](./plan.md)

Tests-included mission (red-first discipline). Two work packages, write-scope-separable (parallel lanes).

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Red-first per-PR twin: fresh checkout, stamp-lags-but-consistent → `next`/preflight rc=0 (RED now) | WP01 | |
| T002 | Positive control (same fixture): genuinely-inconsistent manifest still blocks | WP01 | |
| T003 | Safe-heal predicate helper (`verify()` passes + bundle-hash mismatch) | WP01 | |
| T004 | Lightweight in-process re-stamp (`finalize_manifest`, atomic, idempotent) | WP01 | |
| T005 | Wire default-on heal into `run_charter_preflight` + `allow_heal` param | WP01 | |
| T006 | Thread `allow_heal` through `hook.py` (abort=True, warn-only=False) | WP01 | |
| T007 | Validate WP01: twin green, concurrency idempotency, warm-path no-subprocess | WP01 | |
| T008 | Red-first: after `charter activate --cascade` recompile, recompute==stamp (RED now) | WP02 | [P] |
| T009 | Re-stamp `bundle_content_hash` at the activate/cascade `charter.yaml` recompile site | WP02 | [P] |
| T010 | Scaffold-parity regression test pinning `_fresh_project_layer` re-stamp | WP02 | [P] |
| T011 | Committed-data fix: re-stamp this repo's `synthesis-manifest.yaml` to match `charter.yaml` | WP02 | [P] |
| T012 | Validate WP02: tests/charter + tests/charter_offering green; no #3504 surface touched | WP02 | [P] |

---

## WP01 — Read-path default-on safe-heal on `next` (+ red-first twin)

**Goal**: A fresh/cloned owned checkout whose `synthesized_drg` is stale *only* because the manifest's
`bundle_content_hash` lags a clean recompute (derived artifacts consistent) runs `spec-kitty next` at
`rc=0` via a lightweight, default-on in-process re-stamp — while a genuine derived inconsistency still
blocks, and read-only query mode never mutates. This is the release-unblocking core.

**Priority**: P1 (MVP) · **Dependencies**: none · **Prompt**: [tasks/WP01-read-path-safe-heal.md](./tasks/WP01-read-path-safe-heal.md)

**Independent test**: Construct a repo whose manifest stamp lags `charter.yaml` but whose artifacts pass
`manifest.verify(repo)`; assert `run_preflight_or_abort(consumer="next")` does not raise and the manifest
is re-stamped. Positive control: break an artifact so `verify()` raises → still blocks; query mode →
no mutation.

Included subtasks: T001, T002, T003, T004, T005, T006, T007

---

## WP02 — Write-side re-stamp gap + committed-data parity

**Goal**: Close the write-side gap so `charter activate`/`--cascade` (and the fresh-project scaffold, by
regression pin) re-stamp `bundle_content_hash` at the single `compute_bundle_content_hash` authority, and
correct this repository's committed drifted manifest so a clean clone has parity today.

**Priority**: P2 · **Dependencies**: none (independent write scope; shared hash authority) · **Prompt**: [tasks/WP02-write-side-restamp.md](./tasks/WP02-write-side-restamp.md)

**Independent test**: After a `charter activate --cascade` recompile on a fixture,
`compute_bundle_content_hash(repo) == manifest.bundle_content_hash`. Scaffold parity pinned. This repo's
`compute_freshness(repo).synthesized_drg.state` is a PASS state after the data fix.

Included subtasks: T008, T009, T010, T011, T012

---

## Sequencing & MVP

- **MVP = WP01** (unblocks the release-blocking `next` failure). WP02 hardens the write side and fixes
  the committed data so the regression cannot recur and clones are clean.
- WP01 and WP02 have disjoint write scopes (`src/specify_cli/charter_runtime/preflight` +
  `tests/specify_cli/charter_runtime` vs `src/charter/activation` + `tests/charter` +
  `tests/charter_offering` + `.kittify/charter`) → separate lanes, runnable in parallel.

## Guardrails (both WPs)

- Single hash authority (`charter.bundle.compute_bundle_content_hash`); no second recipe.
- Layer direction `charter <- specify_cli` holds: heal in `specify_cli.charter_runtime`, re-stamp in `charter.activation`.
- Never greenwash a genuine inconsistency; heal is concurrency-safe/idempotent; no subprocess on the warm path.
- No fixture-faking / no test-side `charter synthesize` to pass the e2e. Orthogonal to #3504. Do not conflate #5419/#6074.
- Do NOT run `make test-full`; do NOT regenerate `.github/ci-shard-timings.json` (CI-owned).
- #6366 is the owning gating issue (issue-matrix verdict row required before WP approval); #4885/#4017/#3343/#5419/#6074 are context-only.
