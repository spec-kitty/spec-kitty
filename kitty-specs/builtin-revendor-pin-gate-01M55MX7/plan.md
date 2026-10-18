# Implementation Plan: Built-in re-vendor — pin lockfile + vendor command + drift gate

**Branch**: `feat/builtin-revendor-pin-gate` | **Date**: 2026-10-17 | **Spec**: `kitty-specs/builtin-revendor-pin-gate-01M55MX7/spec.md`
**Input**: Mission specification from `kitty-specs/builtin-revendor-pin-gate-01M55MX7/spec.md`

## Summary

Implement ADR `2026-08-16-2` (amended 2026-10-11) **Option B** for #3504: anchor the committed `packs/built-in/` tree to its `spec-kitty-open-packs` provenance with a committed **pin lockfile** (repo URL + commit **SHA** + clean-tree digest + `requires_core`), a **`spec-kitty charter pack vendor [--check]`** command that resolves the pinned ref and copies/verifies the built-in subtree, a **per-PR + release drift gate** that fails when `packs/built-in/` ≠ pin, and **release re-verification** so the shipped wheel is provably the pinned bytes. The tree **stays committed and read-only** (a verified build cache). Build on the primitives #6046/#6048 (`c3fc8aa349`) already landed — `core_compat.check_requires_core`, `pack_clean_digest.clean_tree_digest`, `charter pack regenerate-graph --pack-root` — and the existing git-ref fetch machinery in `src/specify_cli/charter_packs/sources/`.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: typer/click (CLI), ruamel.yaml (lockfile I/O), the landed `charter.offering.packs` primitives (`pack_clean_digest.clean_tree_digest`, `core_compat.check_requires_core`, `pack_layout.resolve_pack_layout`), and `specify_cli.charter_packs.sources` (git ref clone/pin — already clones + pins a git ref; reuse, do not re-author)
**Storage**: one committed YAML pin lockfile in core (proposed `packs/built-in.source.yaml`, sibling of `packs/built-in/`, so it is NOT part of the digested tree); records the open-packs repo URL, the vendored commit SHA, the clean-tree digest, and the `requires_core` range
**Testing**: pytest, ATDD/red-first (ADR `2026-07-17-1`). Homes: `tests/charter_offering/` (lockfile model + vendor command + digest round-trip), `tests/cross_cutting/packaging/` (release/wheel parity re-verify), and a CI lane invocation in `.github/workflows/packs.yml`. The drift gate's acceptance drives the **same `vendor --check` command CI invokes**, never a YAML-text assertion
**Target Platform**: Linux CI runners + contributor dev checkouts
**Project Type**: single
**Performance Goals**: `vendor --check` is fast (seconds), **offline** (digest comparison of the committed tree vs the committed lockfile — no network), and deterministic (reuses the reproducible clean-tree digest)
**Constraints**: Option B only (filesystem sibling + wheel force-include; no runtime fetch — that is #3022); reuse landed primitives (no re-authoring digest/compat); no change to either packaging invariant (wheel force-includes byte-identical built-in; `packs/internal/` never ships); `packs/internal/`, tree removal/materialization, and the authoring flip are out of scope (C-001..C-005)
**Scale/Scope**: one new CLI command (+ `--check` mode), one lockfile schema, one CI gate wiring, one release re-verify hook, docs/CHANGELOG. ~5 concerns.

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Single canonical authority (DIRECTIVE_044)**: the pin lockfile becomes the single in-core authority for "which open-packs SHA built-in was vendored from"; the digest is the single integrity check. ✅ (does not add a second "where is built-in" authority — the architect lens flagged ≥8 existing encoders; this mission adds a pin, not another location authority, and reuses `kernel.pack_tiers`/`pack_layout`).
- **Architectural integrity (DIRECTIVE_001)**: reuses the landed digest/compat/layout primitives rather than re-implementing. ✅
- **Shared Package Boundary / Modularity SSOT**: no layer-rule or `pyproject.toml` package-set change; `packs/built-in/` wheel force-include unchanged. ✅
- **Packaging invariants**: `tests/cross_cutting/packaging/test_packaging_safety.py` unchanged; `packs/internal/` stays excluded. ✅
- **Decision documentation (DIRECTIVE_003)**: no new ADR required — this implements ADR `2026-08-16-2` amended decisions 1–4; cite it. A fresh ADR is filed only if the lockfile schema or gate placement introduces a decision the amendment does not cover (a spec/tasks-phase call). ✅
- **ATDD-first**: each of FR-005/006/007/008 lands a red-first repro through the real CLI entry point before the fix. ✅

No violations → Complexity Tracking left empty.

## Project Structure

### Documentation (this mission)

```
kitty-specs/builtin-revendor-pin-gate-01M55MX7/
├── plan.md              # This file
├── research.md          # Phase 0 decisions (lockfile location/schema, digest choice, fetch reuse)
├── spec.md              # Mission spec
├── trace/               # decisions/surprises/narrative tracer files
└── tasks.md             # Phase 2 output (/spec-kitty.tasks)
```

### Source Code (repository root)

```
packs/
├── built-in/                     # UNCHANGED committed tree (read-only; verified build cache)
└── built-in.source.yaml          # NEW pin lockfile (open-packs url + SHA + digest + requires_core)

src/specify_cli/cli/commands/charter/
├── pack_tooling.py               # existing (regenerate-graph --pack-root); vendor command added here or a sibling pack_vendor.py
└── ...

src/charter/offering/packs/
├── pack_clean_digest.py          # REUSE clean_tree_digest (digest primitive)
├── core_compat.py                # REUSE check_requires_core
├── pack_layout.py                # REUSE resolve_pack_layout
└── built_in_pin.py               # NEW: lockfile model (load/verify/write) — thin, pure

src/specify_cli/charter_packs/sources/
└── git_source.py                 # REUSE: clone + pin an open-packs git ref by SHA

.github/workflows/packs.yml       # built-in lane gains the `vendor --check` drift gate
.github/workflows/release.yml     # pre-build pin re-verify
RELEASE_CHECKLIST.md              # manual pre-tag build gains the same verify step

tests/
├── charter_offering/             # lockfile model, vendor command, digest round-trip, subtree-scoping
└── cross_cutting/packaging/      # release/wheel parity re-verify
```

**Structure Decision**: single project. The command lives with the other `charter pack` subcommands (`src/specify_cli/cli/commands/charter/`); the pure lockfile model + verify logic lives in `src/charter/offering/packs/` beside the primitives it reuses, so the CLI layer stays thin and the logic is unit-testable without the CLI.

## Implementation Concern Map

### IC-01 — Pin lockfile model

- **Purpose**: a committed, loadable record of the open-packs built-in provenance (repo URL + commit SHA + clean-tree digest + `requires_core`) and a pure verify function (tree digest == lockfile digest).
- **Relevant requirements**: FR-001, FR-002, NFR-001, NFR-002, C-006.
- **Affected surfaces**: new `packs/built-in.source.yaml`; new `src/charter/offering/packs/built_in_pin.py` (load/verify/write); reuses `pack_clean_digest.clean_tree_digest`.
- **Sequencing/depends-on**: none (foundational).
- **Risks**: naming/direction confusion with open-packs' own `built-in.source.yaml` (opposite provenance direction) — document clearly; ensure the lockfile sits OUTSIDE the digested tree.

### IC-02 — `charter pack vendor` command (+ `--check`)

- **Purpose**: resolve the pinned open-packs ref by SHA, copy its `built-in` subtree into `packs/built-in/`, and verify digest + `requires_core`; `--check` verifies only (no mutation).
- **Relevant requirements**: FR-003, FR-004, FR-005, FR-006, FR-007, FR-010.
- **Affected surfaces**: new command in `src/specify_cli/cli/commands/charter/`; reuses `specify_cli.charter_packs.sources.git_source`, `core_compat.check_requires_core`, `built_in_pin` (IC-01), `pack_layout`.
- **Sequencing/depends-on**: IC-01.
- **Risks**: fail-closed on unreachable ref (FR-006); must target only the open-packs `built-in` subtree (C-006); must resolve a tag input to a SHA and never persist the tag (FR-002).

### IC-03 — Per-PR drift gate

- **Purpose**: CI fails any PR whose committed `packs/built-in/` ≠ the pin, with a remedy message.
- **Relevant requirements**: FR-008, FR-010, SC-001.
- **Affected surfaces**: `.github/workflows/packs.yml` built-in lane runs `spec-kitty charter pack vendor --check`; an arch/packaging test drives the SAME command on a drifting-tree fixture (red-first).
- **Sequencing/depends-on**: IC-02 (`--check`).
- **Risks**: the test must drive the real command, not assert on workflow YAML text (non-vacuity); the gate must be offline (NFR-004).

### IC-04 — Release re-verification

- **Purpose**: the release build re-verifies the pin before `python -m build` and asserts the built wheel's `packs/built-in/` equals the pin.
- **Relevant requirements**: FR-009, SC-003, NFR-003.
- **Affected surfaces**: `.github/workflows/release.yml`, `RELEASE_CHECKLIST.md`, a wheel-parity assertion in `tests/cross_cutting/packaging/` (reuse the `test_packaging_parity.py` pattern).
- **Sequencing/depends-on**: IC-02.
- **Risks**: must not change the force-include or the `packs/internal/` exclusion; post-build assertion reuses existing build fixtures.

### IC-05 — Docs / CHANGELOG / ADR citation

- **Purpose**: a `[Unreleased]` CHANGELOG entry (impact-first, `#3504`), cite ADR `2026-08-16-2`; clear the stale `status:blocked` note on #3504; no ADR amendment.
- **Relevant requirements**: traceability for SC-001..SC-004.
- **Affected surfaces**: `docs/changelog/CHANGELOG.md`; mission trace files. A confined `planning_artifact` WP (all `owned_files` under `kitty-specs/`/`docs/`).
- **Sequencing/depends-on**: IC-01..IC-04 (documents what they deliver).
- **Risks**: changelog-style length limit (<1200 chars) and US-spelling docs-lint; keep the entry tight.
