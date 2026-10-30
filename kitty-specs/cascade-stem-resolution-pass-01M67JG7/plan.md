# Implementation Plan: Cascade activation resolves stems in one pass (#6777)

**Branch**: `issue-6777-cascade-stem-resolution-pass` | **Date**: 2026-10-30 | **Spec**: [spec.md](./spec.md)
**Input**: Mission specification from `kitty-specs/cascade-stem-resolution-pass-01M67JG7/spec.md`

## Summary

The `[cascade]` writer of `tests/charter/activation/test_stored_spelling_6527.py` is red on
`main` because it drives a real `charter activate <directive> <id> --cascade all`, and that
operator command resolves each of its 114 cascade targets' config stems with its **own**
fresh `ResolutionPass` — re-walking and re-parsing the whole doctrine catalog once per
target — before the render-only pass #5526 added at `activate.py:525` ever runs.

The fix threads **one** `ResolutionPass` through the whole target batch and resolves every
target's config stem **before** the first `ActiveCharterManager.activate()` write, so the
lookup cost becomes independent of the target count. Measured effect: 80.3 s → 49.8 s for
the writer on this host (single-run experiment, load ~18), pure read deduplication, no
behaviour change. Then the interim 600 s per-test timeout crutch (#6776) is removed, the
case is marked with the repo's documented `slow` tier, and both decisions are pinned by
deterministic (non-wall-clock) tests.

## Technical Context

**Language/Version**: Python 3.11
**Primary Dependencies**: typer/click, ruamel.yaml, rich (CLI), pytest + pytest-timeout
**Storage**: files — `.kittify/config.yaml`, the activation ledger, doctrine pack files
**Testing**: pytest (explicit `pytest.ini` 240 s per-test backstop, `slow` marker for >30 s)
**Target Platform**: Linux CI (module-tests charter shards) + local POSIX
**Project Type**: single project (`src/specify_cli` CLI + `src/charter` domain)
**Performance Goals**: cascade writer ≤60 s on this host vs a 70.9–80.3 s baseline; one
`ResolutionPass` per cascade run regardless of target count
**Constraints**: no gate weakened, no `specify_cli` import added to the charter layer, no
wall-clock assertion in the new guard
**Scale/Scope**: 114 cascade targets / 6 kinds for `directive:DIRECTIVE_001 --cascade all`

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Single canonical authority** — reuse `ResolutionPass` and `drg_urn_to_config_id`; do not
  add a second memo seam. PASS.
- **Locality of change (DIRECTIVE_024)** — the edit is confined to
  `_activate_cascade_targets` and its caller in `specify_cli/cli/commands/charter/activate.py`,
  plus the test module under change. PASS.
- **Smallest viable diff (`change-apply-smallest-viable-diff`)** — one helper extraction and
  one marker removal; the batch-activation seam is explicitly deferred. PASS.
- **ATDD-first / test-first-bug-fixing (DIRECTIVE_034)** — the defect is a measured quadratic
  redundancy; the red test asserts one shared pass and one pre-write resolution batch, and it
  fails on unmodified `main`. PASS.
- **Architectural gate discipline / C-001 layering** — `activate.py` already imports the
  charter-layer `ResolutionPass` sibling symbols; no new cross-layer import. PASS.
- **No gate weakened** — the change deletes a timeout override and adds markers that the
  module shards still select (`-m "not performance and not stress"`). PASS.

## Project Structure

### Documentation (this mission)

```
kitty-specs/cascade-stem-resolution-pass-01M67JG7/
├── spec.md
├── plan.md              # This file
├── tasks.md             # /spec-kitty.tasks output
└── traces/              # approach.md, design-decisions.md, tooling-friction.md
```

### Source Code (repository root)

```
src/specify_cli/cli/commands/charter/activate.py   # _activate_cascade_targets + caller
src/charter/activation/kind_vocabulary.py          # ResolutionPass (reused, unchanged)
src/charter/activation/_cascade_shared.py          # drg_urn_to_config_id (reused, unchanged)
tests/charter/activation/test_stored_spelling_6527.py         # [cascade] case, tier, markers
tests/charter/activation/test_cascade_stem_resolution_6777.py # new deterministic guard
docs/changelog/CHANGELOG.md                                   # [Unreleased] entry (#6777)
```

## Implementation Concern Map

| IC | Concern | Where | Verification |
|----|---------|-------|--------------|
| IC-01 | One read-only stem-resolution batch before the first write | `activate.py::_activate_cascade_targets` | new unit test: one `ResolutionPass`, all lookups before first `activate()` |
| IC-02 | Retire the interim 600 s override, mark the slow tier | `test_stored_spelling_6527.py` | collected-mark test: no `timeout` mark, `slow` present |
| IC-03 | Measured improvement retained and recorded | both files, `docs/changelog` | `pytest -k cascade` under the default timeout, timed twice |

## Phase 0 — Research (evidence)

`research.md` records the measurement protocol and the profiler output that decided the
root cause, so the diagnosis is auditable rather than asserted.

## Phase 1 — Design

`data-model.md` (the batch value the loop resolves once), `quickstart.md` (how to reproduce
the measurement), `contracts/` (the ordering/marker contracts the guards pin).

## Phase 2 — Tasks

See `tasks.md`.
