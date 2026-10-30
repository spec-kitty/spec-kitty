# Implementation Plan: Prune unlinked runs and Op-scoped glossary logs

**Branch**: `issue-6739-prune-unlinked-runs-and-op-logs` | **Date**: 2026-10-30 | **Spec**: [spec.md](./spec.md)
**Input**: Mission specification from `kitty-specs/prune-unlinked-runs-and-op-logs-01M66YMR/spec.md`
**Issue**: spec-kitty/spec-kitty#6739 (follow-up to #6610, #5212)

## Summary

`spec-kitty doctor event-logs` keeps two local-tier families forever because its
verdict rule has one state for "no Mission resolved": it treats an item that names
**nothing** like an item that names a Mission this checkout cannot see. The fix
splits that state in the retention engine's link resolution:

- a run's own snapshot may name its Mission by slug — the only identity the
  production writer records (`inputs.mission_slug`) — so the run links to its
  Mission and follows the lifecycle rule an indexed run already follows;
- an Op-scoped glossary log (`profile-invocation-<id>.events.jsonl`) links to its
  Op, whose open/closed state is the record `kitty-ops/<id>.jsonl` plus the
  closure spine;
- an item that links to nothing at all is judged on age alone once it is outside
  the newest `keep_runs` of its kind;
- a *recorded* Mission identity this checkout does not know keeps its protection
  (`Mission not found`), per the 2026-10-23 operator ruling.

Everything else about the command — the limits, the locks, the preview/apply
parity, the never-removed list, the JSON envelope — is unchanged.

## Technical Context

**Language/Version**: Python 3.12+ (repository target; `mypy --strict`)
**Primary Dependencies**: Typer + Rich (CLI), pytest, ruff, mypy; internal seams
`specify_cli.state.retention` (engine), `specify_cli.invocation.writer` (Op
records), `runtime.next.run_index` / `run_lock` (runs), `glossary.events` (log
naming), `kernel.locks` / `kernel.event_log_append` (locks)
**Storage**: files only — `.kittify/runtime/runs/`, `.kittify/events/glossary/`,
`.kittify/derived/`, `kitty-ops/`, `kitty-specs/`, `.kittify/config.yaml`
**Testing**: pytest (`tests/core/test_event_log_retention.py` for the engine,
`tests/cli/commands/test_doctor_event_logs.py` for the command,
`tests/specify_cli/invocation/test_doctor_ops.py` for the Op predicate)
**Target Platform**: any platform the CLI supports (Linux, macOS, Windows); the
engine's removal path already carries the Windows lock-order note
**Project Type**: single project — `src/` package + `tests/`
**Performance Goals**: a preview over 1,000 Op records and 1,000 glossary logs in
under 2 s (NFR-001); each Op record read at most once per scan
**Constraints**: read-only preview (NFR-002); deletion strictly inside a
registry-declared local tier root (NFR-003); deterministic verdicts (NFR-004); no
new configuration keys (C-003); no new top-level report key (C-005)
**Scale/Scope**: two state families, one engine module, one owner-module predicate,
one CLI docstring, one how-to page, one changelog entry

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Charter gate | How this plan satisfies it |
| --- | --- |
| ATDD-First Discipline (C-011) | Each WP's first commit is a failing test through the pre-existing entry point (`scan_retention` / `doctor event-logs`) that pins the new verdict; impl commits follow. Reviewer checks RED on the planning base, GREEN at the WP head. |
| Canonical sources, no second list (DIRECTIVE_025) | The collector table stays driven by the registry's `cleanup_policy`; the "is this Op open" rule moves to the Op record's owner instead of being copied. |
| Single canonical authority | `invocation.writer.open_invocation_ids` becomes the one predicate for Op openness; `doctor.ops.list_orphan_ops` and `state.retention` both call it. No new copy of the closure-spine rule. |
| Terminology canon (Mission vs Feature) | All new prose says Mission, Op, run, glossary log, exactly as the existing command docs do. |
| `__all__` convention (C-007) | New reason/kind constants stay out of `specify_cli.state.retention.__all__` (tests and docs read them as module names, exactly like the existing `REASON_*` constants); the one new public function in `invocation.writer` has in-src callers, so the dead-symbol gate stays green. |
| Code quality | `mypy --strict` clean; docstrings on every new public name; help text updated with examples preserved. |
| Documentation standards | CLI reference regenerated from the live Typer surface, how-to page updated for the new verdicts, changelog entry under `[Unreleased]`. |
| Pre-existing Failure Reporting Rule | Any red that reproduces on a pristine `origin/main` is cited, not hidden. |
| Never merge / PR-only | The mission ends at a green draft PR flipped to ready for review. |

No violations; Complexity Tracking is not needed.

## Project Structure

### Documentation (this mission)

```
kitty-specs/prune-unlinked-runs-and-op-logs-01M66YMR/
├── plan.md              # This file
├── research.md          # Discovery + Phase 0 findings (reproduction, decisions)
├── data-model.md        # Phase 1: link states, verdicts, reasons
├── quickstart.md        # Phase 1: how to try it and what to expect
├── contracts/
│   └── doctor-event-logs.md   # Phase 1: additive report contract
├── checklists/requirements.md
├── spec.md
└── tasks/               # Phase 2 output
```

### Source Code (repository root)

```
src/
├── specify_cli/
│   ├── state/retention.py            # engine: link resolution, verdicts, collectors
│   ├── invocation/writer.py          # Op records: open_invocation_ids (new owner predicate)
│   ├── doctor/ops.py                 # list_orphan_ops now calls the owner predicate
│   └── cli/commands/_event_logs_doctor.py   # command docstring (help text)
├── glossary/                         # unchanged: log naming, checkpoint/resume
└── runtime/next/                     # unchanged: run index, run cursors

tests/
├── core/test_event_log_retention.py          # engine verdicts + apply
├── cli/commands/test_doctor_event_logs.py    # command surface, JSON, reasons
└── specify_cli/invocation/test_doctor_ops.py # Op-open predicate stays identical
docs/
├── api/cli-commands.md                       # regenerated from the Typer surface
├── guides/how-to/monitoring/clean-up-local-event-logs.md
└── changelog/CHANGELOG.md
```

**Structure Decision**: single project. The change is confined to the retention
engine, one owner predicate and the surfaces that document the report.

## Implementation Concern Map

### IC-01 — One owner for "is this Op open"

- **Purpose**: an Op log's protection depends on its Op's state; that rule must not
  exist twice (doctor surface and cleanup engine would drift).
- **Relevant requirements**: FR-005, FR-006, FR-013, C-004
- **Affected surfaces**: `src/specify_cli/invocation/writer.py` (new
  `open_invocation_ids`, the `_NON_OP_JSONL` set moves here),
  `src/specify_cli/doctor/ops.py` (`list_orphan_ops` calls it),
  `tests/specify_cli/invocation/test_doctor_ops.py`
- **Sequencing/depends-on**: none
- **Risks**: `list_orphan_ops` must keep its exact ordering and its exclusion of
  `ops-index.jsonl`, `lifecycle.jsonl`, `propagation-errors.jsonl` and
  `op-closures.jsonl`; the existing tests pin that, so they are the regression net.
  Reading 1,000 records once per scan (NFR-001) is why the predicate returns a set
  rather than a per-id probe.

### IC-02 — Link states and the verdict rule

- **Purpose**: replace "Mission resolved / not resolved" with owned / unlinked /
  unknown, so an item that names nothing is judged on age while one that names an
  unknown Mission stays protected.
- **Relevant requirements**: FR-001, FR-002, FR-003, FR-004, FR-008, FR-010,
  FR-011, FR-012, C-001, C-002, NFR-004
- **Affected surfaces**: `src/specify_cli/state/retention.py`
  (`_Unit`, `_ledger_verdict`, `_run_mission`/`_read_snapshot_mission`,
  reason constants, `_delete_run` docstring residual)
- **Sequencing/depends-on**: none
- **Risks**: the identity rule (`mission_id` is the only runtime identity; a slug is
  read only from a record with no id) must not widen — `inputs.mission_slug` is read
  only for a snapshot that records no identity at all. Ambiguity must keep reading
  as unknown. Existing tests that pin `Mission not found` for an anonymous run must
  be split, not deleted: the recorded-unknown and ambiguous cases stay.

### IC-03 — Op-scoped log collection

- **Purpose**: collect `profile-invocation-<id>.events.jsonl` as its own family,
  rank it among itself and delete it through the existing glossary deleter.
- **Relevant requirements**: FR-005, FR-006, FR-007, FR-009, FR-012, C-005, C-006
- **Affected surfaces**: `src/specify_cli/state/retention.py`
  (`_collect_glossary_logs`, new `KIND_OP_LOG`, new collector entry, `_DELETERS`)
- **Sequencing/depends-on**: IC-01 (needs the open set), IC-02 (needs the link state)
- **Risks**: `keep_runs` ranking must stay per family, so the Op logs get their own
  collector and kind; the `_`-prefixed (`_cli`, `_renderer`) exclusion, the symlink
  exclusion and the `_assert_deletable` root check must be preserved verbatim.

### IC-04 — Surfaces an operator reads

- **Purpose**: the help text, the how-to and the changelog must describe the new
  verdicts so the operator can predict the command.
- **Relevant requirements**: FR-008, FR-014, NFR-002
- **Affected surfaces**: `src/specify_cli/cli/commands/_event_logs_doctor.py`,
  `docs/api/cli-commands.md` (regenerated), the how-to page, `CHANGELOG.md`
- **Sequencing/depends-on**: IC-02, IC-03 (the wording follows the vocabulary)
- **Risks**: `docs/api/cli-commands.md` is generated — run
  `uv run python -m scripts.docs.build_cli_reference --write` and the freshness
  check, never hand-edit the generated block.

## Complexity Tracking

Not applicable: no charter violation needs justification.

## Phase 0 / Phase 1 outputs

- `research.md` — reproduction, owner map, decisions D1–D7 (written in discovery,
  extended here with the survey findings below).
- `data-model.md` — link states, verdict order, reason vocabulary, kind vocabulary.
- `contracts/doctor-event-logs.md` — the additive report contract.
- `quickstart.md` — how an operator reproduces the fix and reads the new reasons.

### Survey notes (recorded in research.md)

- `src/specify_cli/state/retention.py` is the only engine; the CLI module only
  renders `RetentionPlan.to_dict` / `RetentionResult.to_dict`, so a new verdict needs
  no CLI branch — only new `reason` and `kind` values flow through.
- `tests/core/test_event_log_retention.py` pins the current "resolves nowhere is
  kept" behaviour for four shapes (unknown id, anonymous, corrupt snapshot,
  unindexed). Only the anonymous and unindexed shapes change; the test is split so
  the other two stay pinned.
- `tests/cli/commands/test_doctor_event_logs.py` pins the JSON contract keys and the
  human rendering; new reasons are additive, so the key set is unchanged.
- `docs/api/cli-commands.md` is generated by `scripts/docs/build_cli_reference.py`
  and checked by `scripts/docs/check_cli_reference_freshness.py` (a CI gate), so the
  docstring change must be regenerated, not hand-edited.
- `tests/architectural/test_no_dead_symbols.py` walks `__all__`: new module-level
  constants are read by tests and by `retention` itself, and the new public
  function has two in-src callers.
