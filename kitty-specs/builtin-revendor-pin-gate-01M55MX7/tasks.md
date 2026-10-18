# Tasks: Built-in re-vendor — pin lockfile + vendor command + drift gate

**Mission**: builtin-revendor-pin-gate-01M55MX7
**Branch**: `feat/builtin-revendor-pin-gate` → PR to `main`
**Spec**: [spec.md](./spec.md) · **Plan**: [plan.md](./plan.md) · **Research**: [research.md](./research.md)

Five implementation concerns (IC-01..IC-05) → five work packages, one per IC. Tests ship in
the same WP that delivers the behaviour. Topology is `single_branch`: WPs run sequentially in
the write checkout; there is no lane worktree and no dependency merge.

Build on the landed primitives (#6046/#6048, `c3fc8aa349`), never re-author them:
`charter.offering.packs.pack_clean_digest.clean_tree_digest`,
`charter.offering.packs.core_compat.check_requires_core`,
`specify_cli.charter_packs.sources.git_source.GitSource`.

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Round-trip test: committed `packs/built-in/` clean-tree digest == recorded pin (RED before model/lockfile) | WP01 | |
| T002 | `BuiltInPin` model: load/verify/write the `packs/built-in.source.yaml` schema | WP01 | |
| T003 | Seed the lockfile with the real open-packs `v0.1.0` pin (SHA + digest + `requires_core`) | WP01 | |
| T004 | Subtree-scoping + tag-resolves-to-SHA + direction-doc coverage (FR-002, C-006) | WP01 | |
| T015 | SC-004 resolver probe: `clean_tree_digest(resolve_pack_root("built-in"))` == pin, + mutated-tree positive control | WP01 | |
| T005 | Red-first `vendor`/`vendor --check` repros through the real CLI (in-sync=0, edited-byte=non-0, stale-pin rewrites) | WP02 | |
| T006 | `pack_vendor` command: resolve pinned ref by SHA, copy built-in subtree, verify digest + `requires_core`; `--check` verify-only | WP02 | |
| T007 | Register `vendor` on `charter_pack_app` (small out-of-map edit in the shared `_app.py`) | WP02 | |
| T008 | Fail-closed controls: unreachable ref, digest mismatch, incompatible `requires_core` (tree unchanged, non-zero) | WP02 | |
| T009 | Red-first drift-gate test driving the SAME `vendor --check` command on a drifting-tree fixture (non-vacuity) | WP03 | |
| T010 | Wire the built-in drift gate into `.github/workflows/packs.yml` (offline, `vendor --check`) + `packs-gate.needs` | WP03 | |
| T011 | Red-first wheel-parity test: built wheel's `packs/built-in/` digest == pin (positive control included) | WP04 | |
| T012 | Release pre-build verify in `release.yml` + `RELEASE_CHECKLIST.md`; force-include / `packs/internal/` untouched | WP04 | |
| T013 | `[Unreleased]` CHANGELOG entry (impact-first, `(#3504)`, <1200 chars, US spelling, cite ADR `2026-08-16-2`) | WP05 | |
| T014 | Append the closing mission narrative | WP05 | |

## Work Packages

### WP01 — Pin lockfile model (IC-01)

- **Goal**: A committed, loadable record of built-in provenance (`packs/built-in.source.yaml`:
  open-packs repo URL + commit SHA + clean-tree digest + `requires_core`) and a pure verify
  function (tree digest == lockfile digest), seeded with the real `v0.1.0` pin.
- **Independent test**: the committed lockfile names a real open-packs SHA + a `tree_digest`; a
  digest helper recomputes the committed `packs/built-in/` clean-tree digest and it equals the
  recorded value (FR-001, US1-S2, SC-002 foundation).
- **Prompt**: [tasks/WP01-pin-lockfile-model.md](./tasks/WP01-pin-lockfile-model.md)
- **execution_mode**: code_change
- **agent_profile**: python-pedro
- **owned_files**: `src/charter/offering/packs/built_in_pin.py`, `packs/built-in.source.yaml`, `tests/charter_offering/test_built_in_pin.py`
- **authoritative_surface**: `src/charter/offering/packs/`
- **Dependencies**: none
- **Requirement refs**: FR-001, FR-002, NFR-001, NFR-002, C-006, SC-002

### WP02 — `charter pack vendor` command (+ `--check`) (IC-02)

- **Goal**: Resolve the pinned open-packs ref by SHA, copy its `built-in` subtree into
  `packs/built-in/`, verify digest + `requires_core`, and fail closed on mismatch/unreachable;
  `--check` verifies only (no mutation).
- **Independent test**: `vendor` from the recorded pin on a clean tree is a no-op exiting 0;
  a deliberately stale pin rewrites the tree and refreshes the lockfile digest; an incompatible
  `requires_core` / unreachable ref / digest mismatch refuses non-zero with the tree unchanged
  (FR-003..FR-007, FR-010).
- **Prompt**: [tasks/WP02-charter-pack-vendor.md](./tasks/WP02-charter-pack-vendor.md)
- **execution_mode**: code_change
- **agent_profile**: python-pedro
- **owned_files**: `src/specify_cli/cli/commands/charter/pack_vendor.py`, `src/specify_cli/cli/commands/charter/_app.py`, `tests/charter_offering/test_pack_vendor.py`
- **authoritative_surface**: `src/specify_cli/cli/commands/charter/`
- **Dependencies**: WP01
- **Requirement refs**: FR-003, FR-004, FR-005, FR-006, FR-007, FR-010, SC-002

### WP03 — Per-PR drift gate (IC-03)

- **Goal**: CI fails any PR whose committed `packs/built-in/` ≠ the pin, with the FR-010 remedy
  message, offline, by running the same `vendor --check` command.
- **Independent test**: a test drives the SAME `spec-kitty charter pack vendor --check` command
  on a drifting-tree fixture (not a YAML-text assertion) and asserts non-zero + the remedy
  message; in-sync exits 0 (FR-008, FR-010, SC-001).
- **Prompt**: [tasks/WP03-per-pr-drift-gate.md](./tasks/WP03-per-pr-drift-gate.md)
- **execution_mode**: code_change
- **agent_profile**: implementer-ivan
- **owned_files**: `.github/workflows/packs.yml`, `tests/architectural/test_built_in_drift_gate.py`
- **authoritative_surface**: `.github/workflows/`
- **Dependencies**: WP02
- **Requirement refs**: FR-008, FR-010, SC-001

### WP04 — Release re-verification (IC-04)

- **Goal**: the release build re-verifies the pin before `python -m build` and asserts the built
  wheel's `packs/built-in/` digest equals the pin; force-include and the `packs/internal/`
  exclusion unchanged.
- **Independent test**: the wheel-parity test builds the wheel and asserts its `packs/built-in/`
  clean-tree digest equals the committed pin; a positive control pointing at a mutated tree reds
  (FR-009, SC-003, NFR-003).
- **Prompt**: [tasks/WP04-release-reverification.md](./tasks/WP04-release-reverification.md)
- **execution_mode**: code_change
- **agent_profile**: implementer-ivan
- **owned_files**: `.github/workflows/release.yml`, `RELEASE_CHECKLIST.md`, `tests/cross_cutting/packaging/test_built_in_release_parity.py`
- **authoritative_surface**: `tests/cross_cutting/packaging/`
- **Dependencies**: WP02
- **Requirement refs**: FR-009, SC-003, NFR-003

### WP05 — Docs / CHANGELOG / ADR citation (IC-05)

- **Goal**: a `[Unreleased]` CHANGELOG entry (impact-first, `(#3504)`, <1200 chars, US spelling),
  citing ADR `2026-08-16-2`; append the closing mission narrative. No ADR amendment.
- **Independent test**: the CHANGELOG entry references `#3504`, the `vendor` remedy, and ADR
  `2026-08-16-2`; `scripts.docs.check_spelling` passes on the touched changelog
  (traceability for SC-001..SC-004).
- **Prompt**: [tasks/WP05-docs-changelog.md](./tasks/WP05-docs-changelog.md)
- **execution_mode**: planning_artifact
- **agent_profile**: comms-cleo
- **owned_files**: `docs/changelog/CHANGELOG.md`, `kitty-specs/builtin-revendor-pin-gate-01M55MX7/trace/narrative.md`
- **authoritative_surface**: `docs/changelog/`
- **Dependencies**: WP01, WP02, WP03, WP04
- **Requirement refs**: SC-001, SC-003

## Sequencing

```
WP01 ──> WP02 ──┬──> WP03
                └──> WP04
WP01, WP02, WP03, WP04 ──> WP05
```

WP01 is foundational (the pin everything verifies against). WP02 builds the command on it. WP03
and WP04 both consume `vendor --check` and are independent of each other. WP05 documents all four
and closes last.

## Ownership (no overlap)

Every WP owns a disjoint file set. The only shared-file touch is `_app.py` (WP02), a small
out-of-map-justified registration edit (three-line sibling of the existing `regenerate-graph`
registration). No `code_change` WP owns a `kitty-specs/` path; WP05 (the only `planning_artifact`
WP) owns only `docs/` + `kitty-specs/`.
