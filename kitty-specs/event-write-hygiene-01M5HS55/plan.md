# Implementation Plan: Event write hygiene: retire dead write doors and private events imports

**Branch**: `feat/event-write-hygiene` (lands as `issue-6614-6607-event-write-hygiene` → `main`) | **Date**: 2026-10-22 | **Spec**: [spec.md](spec.md)
**Input**: Mission specification from `kitty-specs/event-write-hygiene-01M5HS55/spec.md`

## Summary

The mission deletes dead code paths, without behaviour change. Each deletion has a gate that keeps it from coming back, and every one of those gates **already exists and is extended**; no new scanner is written. It removes:
- the non-atomic `store.append_event`, its two verified wrappers, and the `coordination.status_service.append_event_log` wrapper;
- the duplicate `invocations_cmd.append_to_index`;
- the dead hosted lifecycle builder (`build_saas_lifecycle_queue_event`, `_canonical_lifecycle_payload_for_saas`, `_validate_lifecycle_payload`, `repo_root_for_lifecycle_log`), which takes core's only private `spec_kitty_events` import with it.

About 195 test files move their status-log seeding onto a `tests/_support` helper over the atomic primitive. The produce seam and its residue (`adapters.py`, `emit._saas_fan_out*`, the lifecycle `*_hosted` fan-out, the `conftest_saas_sink` test plugin) get transport-neutral names with no aliases. The timeout variable becomes `SPEC_KITTY_STATUS_FANOUT_TIMEOUT`.

## Engineering Alignment (confirmed by operator rulings and the post-spec squad)

- **Gates extend the existing owners** (charter: single canonical authority):
  - The store door set: `tests/architectural/test_status_unsafe_allowlist.py` (`STORE_APPEND_PRIMITIVES`, `COORD_WRAPPER_DOORS`, `_unsafe.__all__` rationale entries).
  - The no-plain-append-in-store pin: `tests/architectural/test_status_events_writes_gate.py::test_store_writes_are_found`, re-pinned to `{("os.replace","replace")}`.
  - Re-adding a dead door: `tests/architectural/test_no_dead_symbols.py`, once the `dead_symbol_allowlist.yaml` entries are removed. The `_baselines.yaml` counts are lowered.
  - Private imports: `tests/architectural/test_events_tracker_public_imports.py`, widened from `src/specify_cli` + `._internal` to every production root, and to any `_`-prefixed module segment or imported `alias.name`. It has no allowlist.
  - The invocation index: a single-writer check alongside the writes gate. It reuses the gate's scanner, parameterised on the target filename, or falls back to a narrow AST census in the same file if the scanner's path resolution cannot express `ops-index.jsonl`. Allowed writer: `specify_cli.invocation.writer`.
- **Test reach-ins into `spec_kitty_events.diary` privates are out of scope.** There are four files, two of them deliberate library-sync gates. Adding them to an allowlist would be priced debt. An upstream issue asking for public equivalents is proposed in the PR.
- **Seeding helper semantics.**
  - `seed_status_events(feature_dir, events)` and `seed_status_event(feature_dir, event)` take a list or a single event and delegate to `store.append_events_atomic` (unverified, same-package primitive). Tests keep using `status.store` directly, as `test_status_unsafe_allowlist` already permits for tests.
  - Row bytes are identical to the old door (`serialize_event_line`), with two documented differences: a newline is added when the file lacks one, and a symlinked log is refused.
  - Tests that relied on those two behaviours are rewritten to state them explicitly (the census lists them).
- **No dependency change.** `uv.lock` and the events/tracker ranges are untouched.

## Technical Context

**Language/Version**: Python 3.11+ (repo `.venv`, 3.13 runtime)
**Primary Dependencies**: `spec-kitty-events` 11.0.0 (locked, range `>=11.0.0,<12`, unchanged), `spec-kitty-tracker` 0.5.x, pytest, ruff, mypy
**Storage**: Append-only JSONL files (`status.events.jsonl`, `kitty-ops/ops-index.jsonl`). Write semantics are unchanged.
**Testing**: pytest. Red-first per gate (C-005). The blast radius is `tests/status`, `tests/specify_cli` (invocation, coordination, status), `tests/runtime` (raci), every codemodded test file, the named architectural gate files, and `make test-fast`.
**Target Platform**: The CLI (Linux, macOS, Windows). The seam timeout thread semantics are unchanged.
**Project Type**: single
**Performance Goals**: Test-suite wall time for codemodded files does not regress by more than 5%. The helper batches, so a multi-row seed is one atomic rewrite.
**Constraints**: Behaviour-preserving. Complexity ≤ 15. No new suppressions. `ruff format --check --force-exclude` on changed files. Diff coverage ≥ 90%.
**Scale/Scope**: About 200 test files (mechanical codemod), about 12 `src/` modules, 5 architectural gate files, and docs (ADR amendment notes, the architecture gap table, the env-var reference, the changelog).

## Charter Check

| Charter rule | Status |
|---|---|
| Single canonical authority | PASS. The mission extends the existing gates and adds no parallel scanner. |
| Shared Package Boundary (public imports only) | PASS. Core's only private import goes, and the gate makes "public symbols only" explicit. ADR 2026-04-25-1 gets an amendment note. |
| Architectural gate discipline (non-vacuity, red-first, no unpriced allowlist) | PASS. Every extended gate keeps or gains a floor and a planted-fault self-test. No allowlist is added. |
| ATDD / red-first | PASS. Each WP opens with the gate change committed red. |
| Campsite cleaning | PASS. Stale docstrings are folded into the WPs (`_unsafe` :18/:83, `status/__init__` :75, `invocations_cmd` docstring, `drain_posture` text). |
| Locality of Change | PASS, with a recorded extension: the rename widens from `adapters.py` to the seam's residue, because a rename confined to one file would satisfy SC-003 on paper only. "Saas" or "hosted" names unrelated to the seam are out of scope and listed as a follow-up. |
| No full heavy suites | PASS. Only targeted gate files are run. |
| Team Kitty (no hosted surfaces, "sync"/"saas" are residue vocabulary) | PASS. This mission removes residue and adds nothing hosted. |
| Packs untouched | PASS |

## Project Structure

### Documentation (this mission)

```
kitty-specs/event-write-hygiene-01M5HS55/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── occurrence_map.yaml
├── traces/
└── tasks.md          (/spec-kitty.tasks)
```

`contracts/` is waived (`"contracts": "none"` in `meta.json`). The mission adds no interface. The seam's renamed registration API is pinned by the stub-handler contract test.

### Source Code (repository root)

```
src/specify_cli/status/store.py               # delete append_event + two verified wrappers
src/specify_cli/status/_unsafe.py             # shrink __all__, docstring
src/specify_cli/status/__init__.py            # drop dead exports/comments; renamed seam exports
src/specify_cli/status/adapters.py            # transport-neutral names, env var
src/specify_cli/status/emit.py                # _saas_fan_out* -> neutral names
src/specify_cli/status/lifecycle_events.py    # delete hosted builder + repo_root_for_lifecycle_log; rename *_hosted fan-out
src/specify_cli/coordination/status_service.py   # delete append_event_log
src/specify_cli/coordination/outbound.py         # seam rename callers
src/specify_cli/coordination/status_transition.py # emit fan-out caller
src/specify_cli/decisions/emit.py               # lifecycle seam caller
src/specify_cli/cli/commands/invocations_cmd.py # delete append_to_index
tests/_support/status_seed.py                   # NEW seeding helper (+ its tests)
tests/architectural/test_status_unsafe_allowlist.py, test_status_events_writes_gate.py,
  test_events_tracker_public_imports.py, dead_symbol_allowlist.yaml, _baselines.yaml
tests/conftest_saas_sink.py -> tests/conftest_fanout_sink.py (+ pytest_plugins users)
~195 tests/**: import codemod
docs/architecture/event-ledger-writers-and-readers.md (G-11/G-16/G-18), docs/api/environment-variables.md,
docs/adr/{3.x/2026-04-25-1, 4.x/2026-10-13-2, 4.x/2026-10-14-1} amendment notes, docs/changelog/CHANGELOG.md
```

**Structure Decision**: single-project CLI. All edits are to existing modules, plus one test-support module.

## Complexity Tracking

No charter violations.

## Implementation Concern Map

### IC-01 — Test seeding helper and codemod

- **Purpose**: Move every test seeding through the deleted door onto a helper over the atomic primitive, before the door is deleted.
- **Relevant requirements**: FR-004, NFR-001, SC-004
- **Affected surfaces**: `tests/_support/status_seed.py` (new), about 195 test files, and the monkeypatch tests in `tests/status/test_store.py`.
- **Sequencing/depends-on**: none. This is a tidy-first step.
- **Risks**: Tests that depend on the plain-append quirks (no trailing newline, symlink, inode). The census lists them, and each is rewritten explicitly. Seeding through many single-row calls in performance-tier tests is fixed by batching.

### IC-02 — Delete the status write doors and the coordination wrapper

- **Purpose**: Remove `store.append_event`, `append_event_verified`, `append_primary_checkout_event_verified` and `status_service.append_event_log` together. They must land together: `status_service` imports the verified wrapper.
- **Relevant requirements**: FR-001, FR-002, FR-005, SC-001
- **Affected surfaces**: `status/store.py`, `status/_unsafe.py`, `status/__init__.py`, `coordination/status_service.py`, `test_status_unsafe_allowlist.py`, `test_status_events_writes_gate.py`, `dead_symbol_allowlist.yaml`, `_baselines.yaml`, 18 tests that use `append_event_log` (moved to `append_event_stream_log`).
- **Sequencing/depends-on**: IC-01
- **Risks**: The contract-validation tests for `append_event_log` must move to `append_event_stream_log`, which shares `_validate_write_contract`, so validation coverage is not lost.

### IC-03 — Single invocation-index writer

- **Purpose**: Delete `invocations_cmd.append_to_index`, retarget its tests onto `InvocationWriter`, and gate `ops-index.jsonl` writes to `invocation/writer.py`.
- **Relevant requirements**: FR-003, FR-005
- **Affected surfaces**: `cli/commands/invocations_cmd.py`, `tests/specify_cli/invocation/cli/test_invocations.py`, the writes-gate file, and `dead_symbol_allowlist.yaml`. The forbidden-name sets in the two contract tests stay as reintroduction bans.
- **Sequencing/depends-on**: none
- **Risks**: Scanner path resolution for `kitty-ops/ops-index.jsonl`. Fallback: a narrow census in the same gate file.

### IC-04 — Delete the dead hosted lifecycle builder; public-imports gate

- **Purpose**: Remove the builder family and `repo_root_for_lifecycle_log` with their facade exports and tests, then widen the public-imports gate to every production root and any private name.
- **Relevant requirements**: FR-006, FR-007, SC-002
- **Affected surfaces**: `status/lifecycle_events.py`, `status/__init__.py`, `tests/status/test_lifecycle_events.py`, `tests/architectural/test_status_module_boundary.py`, `tests/architectural/test_events_tracker_public_imports.py`.
- **Sequencing/depends-on**: none
- **Risks**: Public imports aliased to private local names (`glossary/events.py:41`, `tasks_transition_core.py:263`). The gate checks `alias.name`, not `asname`.

### IC-05 — Transport-neutral produce seam

- **Purpose**: Rename the seam and its residue with no aliases, and pin behaviour with a stub-handler contract test.
- **Relevant requirements**: FR-008, FR-009, SC-003
- **Affected surfaces**: `status/adapters.py`, `status/emit.py`, `status/__init__.py`, `status/lifecycle_events.py`, `coordination/outbound.py`, `coordination/status_transition.py`, `decisions/emit.py`, about 25 tests, `tests/conftest_saas_sink.py`, path-keyed ledgers (`test_timing_coverage_invariant.py`, `tests/release/coverage_breadth_baseline.json`, `pyproject.toml`), and `docs/api/environment-variables.md`.
- **Sequencing/depends-on**: IC-04, which shares `lifecycle_events.py` and `status/__init__.py`.
- **Risks**: Exact-text log assertions (caplog). A test that still sets the old env var silently falls back to the 10 s default, so the extended timeout test asserts the old name has no effect.

### IC-06 — Docs, ADR amendment notes, gap table, changelog

- **Purpose**: Keep the documentation truthful.
- **Relevant requirements**: FR-010
- **Affected surfaces**:
  - The G-11/G-16/G-18 rows in `docs/architecture/event-ledger-writers-and-readers.md` (G-11's alias proposal is superseded, and G-18 points at the real gate).
  - Amendment notes on ADR 2026-10-13-2 (rename debt discharged), ADR 2026-10-14-1 (stale hosted-drain text, door list) and ADR 2026-04-25-1 (public symbols only; the gate reference).
  - `docs/changelog/CHANGELOG.md` `[Unreleased]`: a breaking entry for the env var and the seam API.
- **Sequencing/depends-on**: IC-02..IC-05
- **Risks**: Docs freshness and terminology gates. Run `scripts/docs/check_docs_freshness.py --ci` and `test_no_legacy_terminology.py`.
