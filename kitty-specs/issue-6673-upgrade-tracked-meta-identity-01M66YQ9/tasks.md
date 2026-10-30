# Tasks: Upgrade never re-mints a Mission identity that git already holds

**Mission**: `issue-6673-upgrade-tracked-meta-identity-01M66YQ9` · **Issue**: #6673 (refs #6669, #6627)
**Spec**: [spec.md](spec.md) · **Plan**: [plan.md](plan.md)

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Add the read of the tracked `meta.json` (`TrackedMeta`, `read_tracked_meta`) | WP01 | |
| T002 | Seed `build_baseline_feature_meta` from the tracked copy, and give a present copy its lost id back | WP01 | |
| T003 | Unit tests: HEAD copy, index-only copy, corrupt copy, unborn HEAD, nothing tracked | WP01 | |
| T004 | Red-first reproduction of the defect through the real `upgrade --yes` CLI | WP02 | |
| T005 | One notice authority; refuse an unreadable tracked `meta.json` in the 2.0.6 successor | WP02 | |
| T006 | Replace the weak "meta.json missing; mission skipped" notice in the 3.2.0a4 normalization | WP02 | |
| T007 | Make `backfill_mission` skip instead of minting, with its own test (`migrate backfill-identity`) | WP02 | |
| T008 | Stop the runtime-state cutover writing a stub `meta.json` for such a Mission | WP02 | |
| T009 | Green the reproduction, add the healthy/idempotent cases, prove the fix half by half | WP02 | |
| T010 | CHANGELOG `[Unreleased]` entry for #6673 | WP03 | [P] |
| T011 | Document the tracked-`meta.json` behaviour on the upgrade pages | WP03 | [P] |
| T012 | Run the docs freshness, index and terminology gates | WP03 | |

## Phase 1 — The owned read of the tracked `meta.json`

### WP01 — One reader answers what git holds for a Mission's `meta.json` (P1)

**Goal**: `mission_metadata.read_tracked_meta(feature_dir)` returns the metadata git holds for a Mission whose working-tree `meta.json` is gone, distinguishes "git holds nothing" from "git knows the path but cannot give it back" (and from "the only copy is staged"), and `build_baseline_feature_meta` seeds itself from it so the 2.0.6 sweep can no longer rebuild a nameless baseline over a real identity.
**Independent test**: `tests/specify_cli/upgrade/test_read_tracked_meta_6673.py` (new) exercises every branch against scratch git repositories, and baseline-builder tests prove the identity survives the sweep helper — including a working-tree copy that lost its `mission_id`.
**Prompt**: [tasks/WP01-read-tracked-meta.md](tasks/WP01-read-tracked-meta.md)

T001 Add the read of the tracked `meta.json` (WP01)
T002 Seed `build_baseline_feature_meta` from the tracked copy, and give a present copy its lost id back (WP01)
T003 Unit tests: HEAD copy, index-only copy, corrupt copy, unborn HEAD, nothing tracked (WP01)

Dependencies: none. Risks: an unborn `HEAD` must read as "nothing tracked" rather than an error; the `--show-prefix` newline must be stripped or the blob lookup silently misses; a nested project must read its own path; a git timeout must be re-raised, not degraded; the corrupt-copy branch must not silently fall back to the fabricating path.

## Phase 2 — The upgrade seams stop fabricating identity

### WP02 — Every upgrade seam restores or refuses, and none mints (P1)

**Goal**: through the real `spec-kitty upgrade --yes`, a Mission whose tracked `meta.json` is missing from the working tree keeps the identity git holds (a deleted file comes back with the tracked `mission_id`), an unreadable tracked copy is refused with `git checkout -- <path>` and no write at all from **any** migration in the run, and a pre-identity Mission is still repaired. `backfill_mission` never mints over a tracked-but-absent `meta.json`.
**Independent test**: `tests/integration/migration/test_upgrade_tracked_meta_identity_6673.py` (new) is red on `main` and green after this WP; `tests/specify_cli/upgrade/test_runtime_state_cutover_skips_absent_meta_6673.py` proves the phase flip never stubs a `meta.json`.
**Prompt**: [tasks/WP02-seams-restore-or-refuse.md](tasks/WP02-seams-restore-or-refuse.md)

T004 Red-first reproduction of the defect through the real `upgrade --yes` CLI (WP02)
T005 One notice authority; refuse an unreadable tracked `meta.json` in the 2.0.6 successor (WP02)
T006 Replace the weak "meta.json missing; mission skipped" notice in the 3.2.0a4 normalization (WP02)
T007 Make `backfill_mission` skip instead of minting, with its own test (WP02)
T008 Stop the runtime-state cutover writing a stub `meta.json` for such a Mission (WP02)
T009 Green the reproduction, add the healthy/idempotent cases, prove the fix half by half (WP02)

Dependencies: WP01 (the reader and the baseline seeding). Risks: the refusal must skip the whole folder, so no later step writes state for a Mission we could not identify; the runtime-state cutover is a third writer in the same run and must be guarded before `_cutover_corpus`, not after; residue behaviour (#6627/#6669) must stay identical; the frozen `m_2_0_6_consistency_sweep.py` must not be edited.

## Phase 3 — Communication

### WP03 — Changelog and upgrade documentation (P2)

**Goal**: an operator reading the changelog or the upgrade pages learns that a tracked `meta.json` missing from the working tree is rebuilt from git rather than re-identified, and what to do when it cannot be read.
**Independent test**: the docs freshness, index and terminology gates are clean, and the changelog entry follows the house style with the issue reference.
**Prompt**: [tasks/WP03-changelog-and-docs.md](tasks/WP03-changelog-and-docs.md)

T010 CHANGELOG `[Unreleased]` entry for #6673 (WP03)
T011 Document the tracked-`meta.json` behaviour on the upgrade pages (WP03)
T012 Run the docs freshness, index and terminology gates (WP03)

Dependencies: WP02 (the message text and the behaviour it documents). Risks: the docs index records section anchors, so a new heading needs the index regenerated and the index file owned; the changelog is a shared surface — rebase with both sides kept.
