# Tasks: Built-in pack sourced from open-packs

Mission: `built-in-pack-from-open-packs-01M59V4T` · Branch: `feat/6451-built-in-from-open-packs` · Spec: [spec.md](spec.md) · Plan: [plan.md](plan.md)

## Subtask Index

| ID | Description | WP | Parallel |
|---|---|---|---|
| T001 | Write failing tests for `PackPin` | WP01 | [P] |
| T002 | Introduce `pack_pin.py` with `PackPin`, `PackPinError`, `TreeDigest.level` | WP01 | [P] |
| T003 | Turn `built_in_pin.py` into a thin alias module | WP01 | [P] |
| T004 | Add `subtree: built-in` to the built-in pin | WP01 | [P] |
| T005 | Mint `packs/internal.source.yaml` | WP01 | [P] |
| T050 | C-005 subtree-layout test and HTTPS pin assertion | WP01 |  |
| T006 | Local bare-repo fixture | WP02 |  |
| T007 | Red tests for every outcome | WP02 |  |
| T008 | Implement `fetch_to_cache(pin, *, offline, cache_root)` | WP02 |  |
| T009 | Implement `place_pack(cached, dest)` and `check_pack(pin, dest)` | WP02 |  |
| T010 | `PackSyncError` with stable codes | WP02 |  |
| T043 | Kernel primitive `fetch_commit_subtree` in `src/kernel/git/remote.py` | WP02 |  |
| T044 | Integrity, symlink and swap hardening | WP02 |  |
| T011 | Red tests for the script | WP03 |  |
| T012 | Write `scripts/sync_packs.py` | WP03 |  |
| T013 | Make targets | WP03 |  |
| T014 | `BuiltInPackMissing` | WP03 |  |
| T015 | gitignore entries | WP03 |  |
| T045 | `tests/charter_offering/conftest.py` session-start guard | WP03 |  |
| T016 | Red guard test | WP04 |  |
| T017 | Warmup action + module matrix | WP04 |  |
| T018 | packs.yml | WP04 |  |
| T019 | Remaining workflows | WP04 |  |
| T020 | Cache step | WP04 |  |
| T046 | Router filters and remaining workflow files | WP04 |  |
| T021 | Red packaging tests | WP05 | [P] |
| T022 | Write `hatch_build.py` | WP05 | [P] |
| T023 | pyproject wiring | WP05 | [P] |
| T024 | Clean-install digest check | WP05 | [P] |
| T025 | Verify layout unchanged | WP05 | [P] |
| T047 | Editable-install and sdist-member cases | WP05 | [P] |
| T026 | Red tests | WP06 | [P] |
| T027 | Rewire to `pack_fetch` | WP06 | [P] |
| T028 | `--pack` and `--subtree` options | WP06 | [P] |
| T029 | Remove tree copying | WP06 | [P] |
| T048 | Real-fetch bump test and `requires_core` enforcement | WP06 | [P] |
| T030 | Tracked-tree absence gate | WP07 |  |
| T031 | Retire the drift gate | WP07 |  |
| T032 | Update release parity | WP07 |  |
| T033 | Relax internal identity | WP07 |  |
| T049 | No `skipif` keyed on pack presence (grep gate) | WP07 |  |
| T034 | ADR 2026-08-16-2 amendment | WP08 |  |
| T035 | ADR 2026-08-16-3 cross-reference | WP08 |  |
| T036 | CLAUDE.md | WP08 |  |
| T037 | packs/README.md and how-to | WP08 |  |
| T038 | .gitattributes | WP08 |  |
| T039 | Digest parity check | WP09 |  |
| T040 | Untrack the trees | WP09 |  |
| T041 | Flip the absence gate | WP09 |  |
| T042 | Fresh-clone verification | WP09 |  |

Sequencing: WP01 → WP02 → {WP03, WP05, WP06 in parallel} → WP04 (after WP03), WP07 (after WP01, WP06), WP08 (after WP03, WP06) → WP09 cutover last.

Prerequisite (orchestrator): open a PR on `spec-kitty/spec-kitty-open-packs` restoring `pack_level: org`, `active_charter` and `pack_drg` in `packs/internal/pack.yaml` (keep `pack_version`). Its merged SHA is needed by WP01 (internal pin) and WP07 (internal identity test).

## WP01: PackPin model with subtree and digest level, internal pin

Goal: Generalise the built-in pin into one `PackPin` model that every pack uses. Add the `subtree` field and a `tree_digest.level` field, keep `BuiltInPin` as an alias, and mint the internal pin `packs/internal.source.yaml`.

Priority: P1 · Requirements: FR-002, FR-011, C-005 · Prompt: [tasks/WP01-pack-pin-model.md](tasks/WP01-pack-pin-model.md)

No dependencies.

- T001 Write failing tests for `PackPin` (WP01)
- T002 Introduce `pack_pin.py` with `PackPin`, `PackPinError`, `TreeDigest.level` (WP01)
- T003 Turn `built_in_pin.py` into a thin alias module (WP01)
- T004 Add `subtree: built-in` to the built-in pin (WP01)
- T005 Mint `packs/internal.source.yaml` (WP01)
- T050 C-005 subtree-layout test (WP01)

## WP02: pack_fetch core: sparse fetch at SHA, cache, digest verify, atomic place

Goal: Build the one fetch/cache/verify core that the sync script, the hatch hook and the pin-bump helper all call.

Priority: P1 · Requirements: FR-003, FR-004, NFR-001, NFR-002, NFR-004 · Prompt: [tasks/WP02-pack-fetch-core.md](tasks/WP02-pack-fetch-core.md)

Depends on WP01.

- T006 Local bare-repo fixture (WP02)
- T007 Red tests for every outcome (WP02)
- T008 Implement `fetch_to_cache(pin, *, offline, cache_root)` (WP02)
- T009 Implement `place_pack(cached, dest)` and `check_pack(pin, dest)` (WP02)
- T010 `PackSyncError` with stable codes (WP02)
- T043 Kernel primitive `fetch_commit_subtree` (WP02)
- T044 Integrity, symlink and swap hardening (WP02)

## WP03: sync_packs script, make sync-packs, BuiltInPackMissing, gitignore

Goal: Give developers and CI one entry point that syncs both packs, make `dev-setup` run it, and make a missing built-in tree fail with an error that names the fix.

Priority: P1 · Requirements: FR-001, FR-003, FR-005, FR-006 · Prompt: [tasks/WP03-sync-entry-and-missing-pack.md](tasks/WP03-sync-entry-and-missing-pack.md)

Depends on WP02.

- T011 Red tests for the script (WP03)
- T012 Write `scripts/sync_packs.py` (WP03)
- T013 Make targets (WP03)
- T014 `BuiltInPackMissing` (WP03)
- T015 gitignore entries (WP03)
- T045 `conftest.py` session-start guard (WP03)

## WP04: CI: sync packs before tests, pin gate, regen/DRG against fetched trees

Goal: Every CI job that reads a pack syncs it first, a pin gate fails when a pin is unresolvable or its digest does not match, and the regeneration and DRG `--check` gates run against the fetched tree.

Priority: P2 · Requirements: FR-006, FR-012, NFR-004 · Prompt: [tasks/WP04-ci-sync-wiring.md](tasks/WP04-ci-sync-wiring.md)

Depends on WP03.

- T016 Red guard test (WP04)
- T017 Warmup action + module matrix (WP04)
- T018 packs.yml (WP04)
- T019 Remaining workflows (WP04)
- T020 Cache step (WP04)
- T046 Router filters and remaining workflow files (WP04)

## WP05: Hatch build hook, pyproject wiring, packaging and clean-install digest tests

Goal: Wheels and sdists ship the pinned built-in tree at `packs/built-in` after a digest check, never ship `packs/internal`, and a wheel builds from the sdist with no network.

Priority: P1 · Requirements: FR-007, FR-008, FR-009, FR-015, NFR-003, C-001, C-002, C-003, C-004 · Prompt: [tasks/WP05-hatch-hook-packaging.md](tasks/WP05-hatch-hook-packaging.md)

Depends on WP02.

- T021 Red packaging tests (WP05)
- T022 Write `hatch_build.py` (WP05)
- T023 pyproject wiring (WP05)
- T024 Clean-install digest check (WP05)
- T025 Verify layout unchanged (WP05)
- T047 Editable-install and sdist-member cases (WP05)

## WP06: charter pack vendor becomes a pin-bump helper

Goal: `spec-kitty charter pack vendor [--pack <name>] [--ref <ref>] [--subtree <path>]` rewrites a pin (commit, subtree, digest) and copies no tree.

Priority: P2 · Requirements: FR-010, FR-011 · Prompt: [tasks/WP06-vendor-pin-bump-helper.md](tasks/WP06-vendor-pin-bump-helper.md)

Depends on WP02.

- T026 Red tests (WP06)
- T027 Rewire to `pack_fetch` (WP06)
- T028 `--pack` and `--subtree` options (WP06)
- T029 Remove tree copying (WP06)
- T048 Real-fetch bump test and `requires_core` enforcement (WP06)

## WP07: Tracked-tree absence gate, retire drift gate, update parity and internal identity tests

Goal: Add the gate that fails if `packs/built-in` or `packs/internal` is tracked, retire the drift gate (#6421 and the drift-gate part of #6364), and align the parity and internal identity tests with the fetched trees.

Priority: P2 · Requirements: FR-001, FR-012, FR-013 · Prompt: [tasks/WP07-gates-retire-drift.md](tasks/WP07-gates-retire-drift.md)

Depends on WP01, WP06.

- T030 Tracked-tree absence gate (WP07)
- T031 Retire the drift gate (WP07)
- T032 Update release parity (WP07)
- T033 Relax internal identity (WP07)
- T049 No `skipif` keyed on pack presence (WP07)

## WP08: ADR amendment, CLAUDE.md, packs/README, .gitattributes, how-to

Goal: Governance text says to edit pack content in open-packs and then bump the pin; the ADR is amended and the internal ADR cross-referenced.

Priority: P2 · Requirements: FR-014, FR-011, C-006 · Prompt: [tasks/WP08-governance-docs.md](tasks/WP08-governance-docs.md)

Depends on WP03, WP06.

- T034 ADR 2026-08-16-2 amendment (WP08)
- T035 ADR 2026-08-16-3 cross-reference (WP08)
- T036 CLAUDE.md (WP08)
- T037 packs/README.md and how-to (WP08)
- T038 .gitattributes (WP08)

## WP09: Cutover: untrack packs/built-in and packs/internal

Goal: Remove both committed trees from git (`git rm -r --cached`), so open-packs is the only source, and prove a fresh sync reaches green.

Priority: P1 · Requirements: FR-001, SC-001 · Prompt: [tasks/WP09-cutover-untrack-trees.md](tasks/WP09-cutover-untrack-trees.md)

Depends on WP03, WP04, WP05, WP06, WP07, WP08.

- T039 Digest parity check (WP09)
- T040 Untrack the trees (WP09)
- T041 Flip the absence gate (WP09)
- T042 Fresh-clone verification (WP09)

## Issue matrix

- #6421: closed by WP07 (drift gate retired).
- #6364: drift-gate part closed by WP07; `requires_core` decision (kept, enforced in pin-bump) closed by WP06.
- #6166: closed by WP04 (FOLD-POST: router path filters).
- #6451: closed by WP09 (cutover).
- #3504: related (open-packs vendoring direction).
- Context only: see #3022, see #6395, see #6420, see #6436, see #4822. Follow-up: #6420/#6436 content must land upstream before any new pin is minted.
