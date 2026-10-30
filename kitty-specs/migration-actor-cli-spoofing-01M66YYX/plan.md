# Implementation Plan: Caller-supplied migration actors are not seeds

**Branch**: `issue-6754-migration-actor-cli-spoofing` | **Date**: 2026-10-30 | **Spec**: [`spec.md`](./spec.md)
**Input**: Mission specification from `kitty-specs/migration-actor-cli-spoofing-01M66YYX/spec.md`

## Summary

`is_migration_actor` classifies a reconstruction seed purely on the actor string's
`migration:` prefix, so any command that records a caller-chosen identity verbatim can
manufacture a seed. Three surfaces do exactly that today: `agent status emit --actor`,
the four `orchestrator-api` lifecycle verbs, and the hidden `implement --actor`. The
fix refuses a caller-supplied seed-shaped identity on those three surfaces, before any
lock, allocation or append, and makes the shared lenient builder
(`actor_from_option`) fail closed so a future call site cannot silently re-open the
hole. In-process migration writers — which build their rows directly and never touch
the emit shell — remain the only producers of a `migration:` actor. No wire shape, no
decoder and no reader-side rule changes.

## Technical Context

**Language/Version**: Python 3.11+ (repository floor; `mypy --strict` clean)
**Primary Dependencies**: `typer` (CLI), `pydantic`, `spec-kitty-events` 11.0.0 (`diary` reducer, read-only here), no new dependency
**Storage**: append-only `status.events.jsonl` per Mission (unchanged; no new append path, no schema change)
**Testing**: `pytest` (fast tier + the touched subsystem directories); red-first through the real Typer entry points; `tests/_support/reconstruction_seed.py` as the behavioural seed probe
**Target Platform**: CLI on Linux, macOS, Windows 10+ (cross-platform, no platform-specific code)
**Project Type**: single project — `src/specify_cli/`
**Performance Goals**: the guard is one string predicate over an already-parsed option; no file read, no lock, no git call; a successful command's wall time is unchanged on the fixture (NFR-002)
**Constraints**: no events-contract change (C-001); no new append path (C-002); reader side untouched (C-003); refusal never rewrites the value (FR-010)
**Scale/Scope**: 3 refusing surfaces, 2 lenient-builder call sites switched to an explicit `recorded=True`, 1 new leaf predicate, 1 new matrix test module, 1 changelog entry + 1 architecture doc paragraph

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Charter rule | Status |
| --- | --- |
| Single canonical authority (`DIRECTIVE_044`) | **Pass** — one predicate + one message in `status/models.py`, next to `MIGRATION_ACTOR_PREFIX` and `is_migration_actor`; every surface calls it (NFR-005). |
| Architectural alignment (`DIRECTIVE_001`), external contract packages | **Pass** — `spec_kitty_events` untouched; no frozen events path (`services/`, ADR `2026-10-29-1`) touched. |
| ATDD-first / red-first (`DIRECTIVE_034`, C-011) | **Pass** — the existing spoof pin test (`test_migration_actor_is_stored_whole_and_stays_a_reconstruction_seed`) is inverted to a refusal test first, watched fail, then the guard lands. |
| Locality of change (`DIRECTIVE_024`), smallest viable diff | **Pass** — 5 source files, ~40 production lines; no refactor of the actor seam. |
| No new persistence / no second write path (`C-001`, ADR `2026-10-22-1`) | **Pass** — the fix removes ways to write, never adds one. |
| Terminology canon (`Mission`, not `Feature`) | **Pass** — "Mission" throughout. |
| `NO_FULL_HEAVY_SUITES_IN_MISSION` | **Pass** — targeted suites only (`tests/status/`, `tests/specify_cli/cli/commands/agent/`, `tests/specify_cli/orchestrator_api/`, the two named architectural gates). |
| Changelog + docs (`DIRECTIVE_037`) | **Pass** — `docs/changelog/CHANGELOG.md` `[Unreleased]` entry (FR-011) and the `docs/architecture/status-model.md` "The actor" section. |

No violations, so no Complexity Tracking rows.

**Supply-chain**: no dependency added, upgraded or removed → the `DIRECTIVE_051` /
`supply-chain-install-safety` controls are not engaged; recorded here so the silence is
not ambiguous.

## Project Structure

### Documentation (this mission)

```
kitty-specs/migration-actor-cli-spoofing-01M66YYX/
├── spec.md              # What and why (authored)
├── plan.md              # This file
├── research.md          # Phase 0: grounding, surface survey, decisions (authored)
├── data-model.md        # Phase 1: identities, refusal outcome, invariants
├── quickstart.md        # Phase 1: how to witness the refusal and the allowed arms
└── tasks.md             # Phase 2 output (/spec-kitty.tasks — not created here)
```

`contracts/` is intentionally absent: this Mission adds no data shape, endpoint or event
field. The one externally visible surface is the `orchestrator-api` failure envelope, and
it reuses the already-contracted, already-allowlisted `error_code: USAGE_ERROR`
(`src/specify_cli/core/upstream_contract.json`, precedent: `wp_lifecycle.py`'s invalid
`--evidence-json`), so no contract artifact or allowlist edit is needed. `meta.json`
records `"contracts": "none"` with that rationale.

### Source Code (repository root)

```
src/specify_cli/
├── status/
│   ├── models.py                     # + refusal leaf (predicate + canonical message)
│   ├── actor.py                      # actor_from_option: fail closed unless recorded=True
│   └── __init__.py                   # facade export for the new leaf
├── cli/commands/
│   ├── agent/status.py               # emit: refuse --actor before any write
│   ├── agent/tasks_move_task_hops.py # recorded-identity call site opts in (recorded=True)
│   ├── agent/tasks.py                # add-history recorded-identity call site opts in
│   └── implement.py                  # hidden --actor refused before allocation
└── orchestrator_api/
    └── wp_lifecycle.py               # 4 lifecycle verbs refuse --actor (USAGE_ERROR)

tests/
├── status/test_caller_seed_refusal_6754.py        # NEW: the refusal/allowed matrix
├── status/test_status_emit_structured_actor_6400.py  # inverted: emit now refuses
└── specify_cli/cli/commands/agent/test_move_task_structured_actor_6400.py  # allowed arms pinned

docs/
├── changelog/CHANGELOG.md            # [Unreleased] entry (#6754)
└── architecture/status-model.md      # "The actor": who may write a seed
```

**Structure Decision**: single project; the change stays inside the status bounded
context plus its CLI adapters, exactly where the actor seam already lives.

## Implementation Concern Map

### IC-01 — The refusal authority

- **Purpose**: One place decides "this caller-supplied identity is seed-shaped" and owns the wording, so no surface invents its own rule or message.
- **Relevant requirements**: FR-001, FR-010, NFR-005, SC-004
- **Affected surfaces**: `src/specify_cli/status/models.py` (next to `MIGRATION_ACTOR_PREFIX`, `actor_identity_str`, `is_migration_actor`), `src/specify_cli/status/__init__.py` (facade export, `__all__` order kept alphabetical)
- **Sequencing/depends-on**: none — every other concern calls it.
- **Risks**: the predicate must mirror `is_migration_actor` exactly (same prefix, same projection) or a value could be refused that is not a seed; the message must name the option and the remedy without leaking a machine path.

### IC-02 — The three refusing surfaces

- **Purpose**: Refuse a seed-shaped `--actor` before any state changes on every surface that would otherwise record it verbatim.
- **Relevant requirements**: FR-002, FR-003, FR-004, NFR-001
- **Affected surfaces**: `cli/commands/agent/status.py` (`emit`; exit 1 + `_output_error` envelope under `--json`), `orchestrator_api/wp_lifecycle.py` (`start-implementation`, `start-review`, `transition`, `append-history`; `_fail(cmd, "USAGE_ERROR", …)`), `cli/commands/implement.py` (hidden `--actor`, refused beside the existing `--mission` no-selector guard, before `detect_context` allocates anything)
- **Sequencing/depends-on**: IC-01
- **Risks**: placing the guard after a lock or an allocation would leave partial state (NFR-001); the orchestrator-api refusal must use an already-allowlisted error code so the outbound contract gate stays green; `implement` has a JSON mode that must stay parseable.

### IC-03 — Fail-closed lenient builder and its two legitimate callers

- **Purpose**: Default `actor_from_option` to refusing a seed-shaped value, and let only the two recorded-identity replays opt in, so a future call site fails closed.
- **Relevant requirements**: FR-005, FR-006, FR-007, SC-002
- **Affected surfaces**: `status/actor.py` (`actor_from_option(..., recorded: bool = False)` and its docstring), `cli/commands/agent/tasks_move_task_hops.py` (`_mt_structured_actor` recorded branch), `cli/commands/agent/tasks.py` (`_add_history_actor` recorded branch)
- **Sequencing/depends-on**: IC-01
- **Risks**: the `--agent` arm must keep its strict-parse behaviour (tool `migration`, never a seed) — it never reaches `actor_from_option`; the recorded branch must stay byte-identical for a recorded seed, or #6400's pin test goes red for the wrong reason.

### IC-04 — Matrix pinning, docs and changelog

- **Purpose**: State the refusal/allowed boundary in tests and in the docs a user reads, and record the compatibility consequence.
- **Relevant requirements**: FR-009, FR-011, SC-001, SC-003
- **Affected surfaces**: `tests/status/test_caller_seed_refusal_6754.py` (new), the two #6400 test modules (invert the spoof pin; keep the allowed arms), `docs/changelog/CHANGELOG.md`, `docs/architecture/status-model.md`
- **Sequencing/depends-on**: IC-01, IC-02, IC-03
- **Risks**: the migration-writer arms need a fixture that actually runs a backfill (or asserts the writer's own row construction), not a mock; the changelog entry must state the refusal *and* the remedy, under 1,200 characters.

## Phase 0 — Research

Complete in [`research.md`](./research.md): D-1 reproduction and non-supersession, D-2
seed producers and the `_unsafe` allowlist, D-3 the surface-by-surface spoofability
survey, D-4 the option choice and the rejected alternatives, D-5 the fail-closed
builder, D-6 the compatibility consequence. No `NEEDS CLARIFICATION` remains.

## Phase 1 — Design

- [`data-model.md`](./data-model.md) — the three identity kinds, the refusal outcome, the invariants and the state/transition rules.
- [`quickstart.md`](./quickstart.md) — witness the refusal on each surface and confirm the allowed arms still work.
- `contracts/` — none: no new event field, endpoint or payload shape; the orchestrator-api envelope reuses the allowlisted `USAGE_ERROR` code (`meta.json` records `"contracts": "none"`).

## Complexity Tracking

No Charter Check violations. The guard is a predicate plus six call sites; no new module,
no new dependency, no new layer.
