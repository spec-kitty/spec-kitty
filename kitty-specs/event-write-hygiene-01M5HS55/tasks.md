# Tasks: Event write hygiene (event-write-hygiene-01M5HS55)

**Input**: `spec.md`, `plan.md`, `research.md`, `research-census.md`, `occurrence_map.yaml`
**Topology**: `single_branch`: work packages run sequentially in the write checkout on `feat/event-write-hygiene`.
**Issues**: #6614 (dead write doors), #6607 (private events import + seam names). Epic context: see #6608.

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Seeding helper `tests/_support/status_seed.py` + its tests | WP01 | |
| T002 | Codemod module-level imports of `store.append_event` in tests | WP01 | |
| T003 | Codemod function-local imports; delete the identity spy | WP01 | |
| T004 | Batch multi-row seeds; run the codemodded blast radius | WP01 | |
| T005 | Red-first: re-pin the door gates (unsafe allowlist, writes gate, index single writer) | WP02 | |
| T006 | Delete the store doors; shrink `_unsafe`; fix docstrings; drop the door's own tests | WP02 | |
| T007 | Delete `append_event_log`; retarget its tests onto `append_event_stream_log` | WP02 | |
| T008 | Delete `append_to_index`; retarget invocation tests | WP02 | |
| T009 | Shrink the dead-symbol allowlist and `_baselines.yaml`; run the blast radius | WP02 | |
| T010 | Red-first: widen the public-imports gate (all roots, any private name) | WP03 | |
| T011 | Delete the hosted lifecycle builder family + `repo_root_for_lifecycle_log` + facade exports | WP03 | |
| T012 | Retarget/delete the builder's tests; run the blast radius | WP03 | |
| T013 | Red-first: stub-handler contract test + extended timeout test (new env name) | WP04 | |
| T014 | Rename `status/adapters.py` to transport-neutral names, no aliases | WP04 | |
| T015 | Rename `emit._saas_fan_out*`, the lifecycle `*_hosted` fan-out and every `src/` caller | WP04 | |
| T016 | Rename the test sink plugin (fail-loud), test files and path-keyed ledgers | WP04 | |
| T017 | Retarget test references (patch strings, caplog text); run the blast radius | WP04 | |
| T018 | Update the G-11/G-16/G-18 gap-table rows | WP05 | [P] |
| T019 | ADR amendment notes (2026-10-13-2, 2026-10-14-1, 2026-04-25-1) + stale seam doc mentions | WP05 | [P] |
| T020 | Env-var reference + `[Unreleased]` changelog entry (breaking) | WP05 | [P] |
| T021 | Docs freshness + terminology gates | WP05 | |

## WP01 — Test seeding helper and codemod (tidy-first)

**Goal**: Every test that seeds `status.events.jsonl` through `specify_cli.status.store.append_event` moves onto a test-only helper over the atomic primitive. No production change.
**Priority**: P1 (it blocks WP02). **Prompt**: `tasks/WP01-test-seeding-helper-and-codemod.md`
**Independent test**: after the codemod, the old name appears in no test outside the door's own tests (`tests/status/test_store.py`, `test_store_sanitized.py`), and every codemodded file passes.

T001 Seeding helper `tests/_support/status_seed.py` + its tests (WP01)
T002 Codemod module-level imports of `store.append_event` in tests (WP01)
T003 Codemod function-local imports; delete the identity spy (WP01)
T004 Batch multi-row seeds; run the codemodded blast radius (WP01)

**Dependencies**: none. **Risks**: the durability-matrix worker blocks on `os.replace` (census), and the file mode becomes 0600. Neither is asserted by any test.

## WP02 — Delete the dead write doors (#6614)

**Goal**: Remove `store.append_event`, `append_event_verified`, `append_primary_checkout_event_verified`, `coordination.status_service.append_event_log` and `invocations_cmd.append_to_index`. The existing gates are re-pinned red-first so the doors cannot return. A single-writer check covers `ops-index.jsonl`.
**Priority**: P1. **Prompt**: `tasks/WP02-delete-dead-write-doors.md`
**Independent test**: `test_status_unsafe_allowlist.py`, `test_status_events_writes_gate.py` and `test_no_dead_symbols.py` fail on the pre-change tree and pass after.

T005 Red-first: re-pin the door gates (unsafe allowlist, writes gate, index single writer) (WP02)
T006 Delete the store doors; shrink `_unsafe`; fix docstrings; drop the door's own tests (WP02)
T007 Delete `append_event_log`; retarget its tests onto `append_event_stream_log` (WP02)
T008 Delete `append_to_index`; retarget invocation tests (WP02)
T009 Shrink the dead-symbol allowlist and `_baselines.yaml`; run the blast radius (WP02)

**Dependencies**: WP01. **Risks**: contract-validation coverage must move, not vanish.

## WP03 — Dead hosted lifecycle builder and public-imports gate (#6607, part 1)

**Goal**: Delete `build_saas_lifecycle_queue_event`, `_canonical_lifecycle_payload_for_saas`, `_validate_lifecycle_payload` and `repo_root_for_lifecycle_log`, which takes core's only private `spec_kitty_events` import with them. Widen `test_events_tracker_public_imports.py` to every production root and any private name.
**Priority**: P1. **Prompt**: `tasks/WP03-dead-hosted-builder-and-public-imports-gate.md`
**Independent test**: the widened gate is red on the pre-change tree (it reports `lifecycle_events.py:368`) and green after. Its planted-fault self-test stays red-capable.

T010 Red-first: widen the public-imports gate (all roots, any private name) (WP03)
T011 Delete the hosted lifecycle builder family + `repo_root_for_lifecycle_log` + facade exports (WP03)
T012 Retarget/delete the builder's tests; run the blast radius (WP03)

**Dependencies**: WP02 (sequential write checkout; no code coupling).

## WP04 — Transport-neutral produce seam (#6607, part 2)

**Goal**: The seam and its residue get transport-neutral names, with no aliases (operator ruling). Behaviour is pinned by a stub-handler contract test.
**Priority**: P2. **Prompt**: `tasks/WP04-transport-neutral-produce-seam.md`
**Independent test**: the contract test passes. `grep -ni saas src/specify_cli/status/adapters.py` is empty. The old env var has no effect.

T013 Red-first: stub-handler contract test + extended timeout test (new env name) (WP04)
T014 Rename `status/adapters.py` to transport-neutral names, no aliases (WP04)
T015 Rename `emit._saas_fan_out*`, the lifecycle `*_hosted` fan-out and every `src/` caller (WP04)
T016 Rename the test sink plugin (fail-loud), test files and path-keyed ledgers (WP04)
T017 Retarget test references (patch strings, caplog text); run the blast radius (WP04)

**Dependencies**: WP03 (shares `status/__init__.py` and `lifecycle_events.py`).

## WP05 — Docs, ADR amendment notes, changelog

**Goal**: The documentation reflects the closure of G-11, G-16 and G-18, the renamed env var and seam API (breaking), and the public-symbols-only boundary.
**Priority**: P3. **Prompt**: `tasks/WP05-docs-adr-notes-changelog.md`

T018 Update the G-11/G-16/G-18 gap-table rows (WP05)
T019 ADR amendment notes (2026-10-13-2, 2026-10-14-1, 2026-04-25-1) + stale seam doc mentions (WP05)
T020 Env-var reference + `[Unreleased]` changelog entry (breaking) (WP05)
T021 Docs freshness + terminology gates (WP05)

**Dependencies**: WP02, WP03, WP04.

## Parallelization

None: `single_branch` runs the work packages sequentially. Within WP05, T018–T020 are independent.

## MVP

WP01 + WP02 close #6614. WP03 + WP04 close #6607.
