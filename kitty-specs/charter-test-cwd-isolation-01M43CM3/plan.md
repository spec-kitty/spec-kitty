# Implementation Plan: Charter CLI tests independent of invoking checkout

**Branch**: `issue-5317-charter-test-cwd-isolation` | **Date**: 2026-10-04 | **Spec**: [spec.md](spec.md)
**Input**: Mission specification from `kitty-specs/charter-test-cwd-isolation-01M43CM3/spec.md`

## Summary

Charter command tests direct a guarded write command at a test tmp project but leave the process working directory in the invoking checkout, so they are refused when pytest starts in a linked worktree. The plan is test-side only:

1. One shared opt-in fixture puts the process working directory and the project root in the same test tmp project. The three per-file copies are retired.
2. Every test that leaks adopts the fixture; the subprocess smoke test gets its own test-only remedy.
3. A runtime tripwire fails any test that reaches the guard from the invoking checkout, so the leak is caught in runs started from a repository root checkout too.

No file under `src/` changes.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: pytest (fixtures, `monkeypatch`, `pytest_plugins`), typer `CliRunner`, git (real linked worktrees built in tmp)
**Storage**: N/A
**Testing**: pytest; targeted files only (C-006). Red-first per ADR `2026-07-17-1`.
**Target Platform**: Linux, macOS, Windows (the fixture and tripwire use only `pathlib` and `monkeypatch`; the linked-worktree reproduction carries the `git_repo` marker like the existing guard tests)
**Project Type**: single project; changes confined to `tests/` plus one inventory-derivation script under `scripts/ci/`
**Performance Goals**: tripwire adds no measurable per-test cost (NFR-003); its own tests run in under 5 seconds (NFR-002)
**Constraints**: no `src/` change (C-001); the real guard always runs (C-002); fixture is opt-in (C-003); one definition (C-004)
**Scale/Scope**: 3 fixture copies retired; about 20 leaking tests in 7 files plus the smoke test; 3 guarded write commands watched

## Charter Check

| Gate | Status | Note |
|------|--------|------|
| Single canonical authority | Pass | Three copies of the isolation fixture become one; no second authority for the guard. |
| Architectural alignment | Pass | No product module touched; the guard's probe point stays as mission `charter-catalog-coherence-01M2XQQF` left it. |
| ATDD-first / red-first | Pass | IC-01 opens with a reproduction that shows the command's own refusal message from a real linked worktree. |
| Non-vacuous gate, empty allowlist (Standing Order 5) | Pass | The tripwire has no allowlist. Self-mutation tests plant offenders in a pytest subprocess (the repository does not enable `pytester`); a coverage test fails if a guarded command is not watched. |
| Canonical sources | Pass | Reuses the existing `tests/_support` plugin home and the linked-worktree fixture pattern of the guard's own tests. |
| No full heavy suites in mission work | Pass | Named files only; one bounded discovery run over the files that reference the charter command app (see research.md R-05). |
| Terminology canon | Pass | Mission, repository root checkout, linked worktree used as defined in the spec. |

No violations; Complexity Tracking is empty.

## Project Structure

### Documentation (this mission)

```
kitty-specs/charter-test-cwd-isolation-01M43CM3/
├── plan.md
├── research.md
├── quickstart.md
├── contracts/test-isolation-contract.md
├── traces/{tooling-friction,approach,design-decisions}.md
└── tasks.md            # created by /spec-kitty.tasks
```

No `data-model.md`: the mission has no data entities.

### Source Code (repository root)

```
tests/
├── conftest.py                                   # registers the two support plugins
├── _support/
│   ├── charter_cwd.py                            # NEW: shared opt-in fixture (single owner)
│   └── charter_cwd_tripwire.py                   # NEW: autouse runtime tripwire
├── specify_cli/cli/commands/charter/
│   ├── test_charter_cwd_isolation.py             # NEW: linked-worktree reproduction + with-helper refusal control
│   └── test_charter_cwd_tripwire.py              # NEW: self-mutation + coverage tests for the tripwire
├── specify_cli/cli/commands/test_charter_resynthesize.py     # copy retired
├── agent/cli/commands/test_charter_resynthesize_cli.py       # copy retired
├── cli/commands/test_charter_json_error_contract.py          # copy retired
├── agent/cli/commands/test_charter_cli.py                    # adopt
├── agent/cli/commands/test_charter_synthesize_cli.py         # adopt
├── agent/cli/commands/test_charter_status_cli.py             # adopt
├── charter/test_references_missing_failclosed.py             # adopt
├── charter/test_reject_not_drop_cli.py                       # adopt
├── charter/test_presence_gate_bundle_authority.py            # adopt
├── charter/test_phase3_integration.py                        # smoke-test remedy
├── consolidation/test_profile_charter_e2e.py                 # adopt (#5601)
└── release/pinning_rule_inventory.json                       # re-derived
scripts/ci/derive_pinning_inventory.py                        # only if a disposition entry must change
```

**Structure Decision**: Shared test support lives in `tests/_support/`, the existing home of pytest plugins loaded through `pytest_plugins` in `tests/conftest.py`. `tests/conftest.py` is 2,300 lines; adding to it would grow a god-file, so it gains only the two registration entries.

## Design

### Shared fixture (`tests/_support/charter_cwd.py`)

`charter_cwd_isolation` is an opt-in fixture returning a callable. Calling it with a project root changes the process working directory to that root and points the charter package's `find_repo_root` at the same root, so both come from one source. Called with no argument it uses `tmp_path`. Tests that already patch `find_repo_root` themselves may keep their patch and use the fixture only for the working directory; both end at the same root.

It never touches `resolve_charter_write_root`. The real guard runs against the test tmp project: a plain directory degrades to "not a linked worktree", and a tmp git repository resolves to its own toplevel.

Its docstring must not mention the `make test-fast` target: that literal is what made the retired copy a pinned rule in the release inventory (research.md R-04).

### Runtime tripwire (`tests/_support/charter_cwd_tripwire.py`)

An autouse fixture wraps the guard function where the three guarded write commands look it up (`generate`, `synthesize`, `resynthesize` modules). The wrapper always calls through to the real guard and returns or raises exactly what it does (C-002). Before calling through it records a violation when the probed path lies inside the invoking checkout, meaning the checkout that contains the running `tests/` tree. At teardown, a recorded violation fails the test with one message naming the test and `charter_cwd_isolation` (NFR-004).

Why runtime and not a static census: the leaking tests patch and invoke in at least five spellings, 21 files patch the seam, and some files mix leaking and isolated tests. A static check is per file and evadable; the runtime check is per test and indifferent to spelling. Its blind spot is a command started as a separate process, which only the smoke test does (FR-007).

Recording at teardown, not raising inside the wrapper, matters: `CliRunner` swallows exceptions into the result, which would turn the tripwire into a confusing exit-code failure.

There is no exemption mechanism. The few tests that deliberately run a guarded command from a real linked worktree build that worktree in tmp, which is outside the invoking checkout, so they do not trip it.

Coverage test: scans the charter commands package for modules that call the guard with the process working directory and asserts each one is wrapped. A new guarded command that is not watched turns this test red.

### Reproduction and controls (`test_charter_cwd_isolation.py`)

On one fixture (a tmp repository with a linked worktree, plus a separate test tmp project):

1. Unisolated arm: process in the linked worktree, `find_repo_root` patched to the tmp project, `charter generate` through `CliRunner` → exit non-zero and the literal refusal message in the output. This arm is the red-first witness and stays as a permanent assertion. It opts out of nothing: the linked worktree is in tmp, so the tripwire does not fire.
2. Isolated arm: same start, then `charter_cwd_isolation(project)` → exit 0 and the charter written under the tmp project.
3. With-helper refusal control (FR-008): helper active, then change into the linked worktree and invoke → still refused. A helper that stubbed the guard would fail this.

Red-first order inside IC-01: commit the reproduction with arm 1 passing and arm 2 written against plain `monkeypatch` state that shows the refusal (an honest red through `runner.invoke`), then add the fixture and turn arm 2 green.

### Smoke test remedy (`test_phase3_integration.py`)

The subprocess keeps its `PYTHONPATH` pointing at the invoking checkout's `src/` but runs with its working directory in a seeded tmp Python project (a few source files and a `conftest.py`, so the code-signal collector still reports signals). Both existing assertions stay. No skip, xfail or checkout-kind branch. If the dry-run path turns out to need something only a real checkout has, stop and record the deferral per FR-007.

## Complexity Tracking

None.

## Implementation Concern Map

### IC-01 — One owner for the isolation

- **Purpose**: Witness the defect honestly, introduce the single shared fixture, and remove the three copies.
- **Relevant requirements**: FR-001, FR-002, FR-003, FR-008, FR-010, C-002, C-003, C-004
- **Affected surfaces**: `tests/_support/charter_cwd.py`, `tests/conftest.py` (registration), `tests/specify_cli/cli/commands/charter/test_charter_cwd_isolation.py`, the three files holding copies, `tests/release/pinning_rule_inventory.json`, `scripts/ci/derive_pinning_inventory.py`
- **Sequencing/depends-on**: none
- **Risks**: The retired copy is a pinned rule; `tests/release/test_pinning_inventory_fresh.py` requires the inventory to re-derive byte for byte. The copies are requested by name in their files, so each request site changes too.

### IC-02 — Adoption

- **Purpose**: Make every leaking test independent of the invoking checkout, including the subprocess smoke test.
- **Relevant requirements**: FR-004, FR-007, NFR-001, C-005
- **Affected surfaces**: the six adopting files under `tests/agent/cli/commands/` and `tests/charter/`, `tests/consolidation/test_profile_charter_e2e.py`, `tests/charter/test_phase3_integration.py`
- **Sequencing/depends-on**: IC-01
- **Risks**: Two reported failures are read-command tests that fail in a preparatory write step. Some tests assert on paths relative to the working directory; changing it can change their output. `tests/charter/conftest.py` initialises `tmp_path` as a git repository, so nested project directories resolve to that toplevel.

### IC-03 — Recurrence tripwire

- **Purpose**: Fail any test that reaches the guard from the invoking checkout, in every kind of checkout, with no exemptions.
- **Relevant requirements**: FR-005, FR-006, NFR-002, NFR-003, NFR-004
- **Affected surfaces**: `tests/_support/charter_cwd_tripwire.py`, `tests/conftest.py` (registration), `tests/specify_cli/cli/commands/charter/test_charter_cwd_tripwire.py`
- **Sequencing/depends-on**: IC-02 (switching it on earlier turns every unadopted test red, in every checkout)
- **Risks**: Stragglers the worktree run did not reveal (tests that reach the guard from the invoking checkout but were listed in neither issue) surface here and must adopt the fixture in the same step. The plugin must not import `specify_cli` at module top level: plugin modules load before `pytest_configure` sets the isolated HOME, and the command modules cost about 0.38 s to import. Wrap what is already imported and catch later imports during the test.
