# Behavioural Contracts: charter preflight fresh-checkout heal

This mission adds no network/API interfaces; the contracts below are behavioural seams on existing
in-process functions. Each is pinned by a test in the blast-radius suites.

## C-HEAL-1 — `run_charter_preflight(..., allow_heal: bool)` default-on safe-heal

- **Given** a repo where `synthesized_drg` is `stale` solely because `manifest.bundle_content_hash`
  lags `compute_bundle_content_hash(repo)` AND `manifest.verify(repo)` passes, **and** `allow_heal=True`,
- **When** `run_charter_preflight` runs,
- **Then** it re-stamps `bundle_content_hash` (via `finalize_manifest`, single authority), the
  `synthesized_drg` check resolves to a PASS state, and `result.passed is True` — **without** running
  the `generate→synthesize→validate` subprocess chain and **regardless** of `preflight.auto_refresh`.
- **Non-vacuity control**: same fixture, but the manifest artifacts are made inconsistent (an artifact
  body changed so `verify()` raises) ⇒ `result.passed is False` with an actionable `blocked_reason`;
  nothing is re-stamped.

## C-HEAL-2 — read-only query never mutates

- **Given** the same stale-but-consistent repo, **When** `run_preflight_warn_only` runs (`allow_heal=False`),
- **Then** the manifest on disk is **unchanged** (no re-stamp), and the caller continues (warn-only).

## C-HEAL-3 — advancing consumer unblocks

- **Given** the same repo, **When** `run_preflight_or_abort(consumer="next")` runs (`allow_heal=True`),
- **Then** it does not raise `typer.Exit(1)`; `spec-kitty next` proceeds (rc=0).

## C-WRITE-1 — every `charter.yaml` writer re-stamps

- **Given** a charter whose `charter.yaml` is recompiled by `charter activate`/`--cascade`,
- **When** the command completes, **Then** `compute_bundle_content_hash(repo)` equals the written
  `manifest.bundle_content_hash` (zero committed drift), computed through the single authority.
- **Scaffold parity**: `_fresh_project_layer._synthesize_project_layer` continues to stamp
  `bundle_content_hash=compute_bundle_content_hash(repo)` (regression-pinned).

## C-DATA-1 — this repo's committed manifest has parity

- **Given** this repository after the mission, **When** `compute_bundle_content_hash(repo)` is recomputed,
- **Then** it equals the committed `.kittify/charter/synthesis-manifest.yaml` `bundle_content_hash`, and
  `compute_freshness(repo).synthesized_drg.state` is a PASS state.

## C-TWIN-1 — per-PR regression twin (red-first)

- A deterministic `tests/charter_runtime/` test constructs a fresh/cloned owned checkout whose manifest
  stamp lags but artifacts are consistent and asserts `next`/preflight passes at rc=0. It is RED against
  the pre-fix product behaviour and GREEN after. A same-fixture positive control asserts a
  genuinely-inconsistent derived state still blocks (ties to C-HEAL-1 non-vacuity).

## Concurrency contract (NFR-003)

- The re-stamp is idempotent and atomic; concurrent `next` invocations against one owned root converge
  to the same stamp with no torn manifest.
