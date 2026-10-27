# Implementation Plan: Status contract readers

> **Phase split (operator decision 2026-10-27, Decision Moment `01M5ZD4PNEEMAFHA7SN4VJZR2N`).** `spec-kitty-events` 11.0.0's reducer decoder (`diary.decode_actor`) accepts only the 4-key actor `{tool, role, profile, model}`, and every status read goes through it. This mission therefore WRITES the 4-key structured actor on every agent/operator path, with `profile` taken only from asserted sources (dispatch invocation → `--profile` → compact `--agent` segment → null). The WP-frontmatter fill and the `profile_source` key are deferred to a follow-up that first ships an events release whose decoder accepts the fifth key (readers first), then flips the CLI writers through an explicit pin-floor bump (never an automatic capability gate: committed logs are shared across clones on different installs). The CLI-side readers in this mission (`decode_actor` accepting the 5-key shape, `actor_full_identity` ignoring a `wp_frontmatter` profile) still land, so the CLI is ready when writers flip.

**Branch**: `issue-6400-structured-status-actor` | **Date**: 2026-10-27 | **Spec**: [spec.md](spec.md)
**Input**: Mission specification from `kitty-specs/status-contract-readers-01M5ZAAC/spec.md`

## Summary

Two reader/contract fixes on the status event surface, kept CLI-side so they survive the Java
write-service cut-over (ADR 2026-10-22-1: the CLI composes the command, actor included).

1. **#6448** — `status_lanes.py` derives its lane constants from `spec_kitty_events.status.Lane`.
   `CANONICAL_LANES` keeps its name and meaning (the authorable lanes: every package lane but
   `genesis`, in package order), now computed from `PACKAGE_LANES` minus an explicit
   `NON_AUTHORABLE_LANES`. A parity test pins the CLI's own `Lane` enum to the package enum
   plus the read sentinel `uninitialized`.
2. **#6400** — one pure actor builder in a new `status/actor.py` produces
   `{tool, role, profile, profile_source, model}`. It resolves the profile in a fixed order
   (invocation → flag → agent string → WP frontmatter → null) and the role from the hop.
   Every agent/operator write path calls it; `decode_actor` reads the 5-key shape alongside the
   legacy shapes; `actor_full_identity` drops a `wp_frontmatter` profile.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: typer, rich, ruamel.yaml, `spec-kitty-events` (pinned `>=11.0.0,<12`; `Lane` and `StatusTransitionPayload.actor: Union[str, Dict]` already fit), pytest, mypy
**Storage**: append-only `status.events.jsonl` (no format version change; one extra optional actor key)
**Testing**: pytest; red-first ATDD per WP through the real entry points (`agent tasks move-task`, `agent tasks mark-status`, `agent action implement/review`, `agent status emit`, `orchestrator-api`), unit tests for the builder/decoder/identity; blast radius `tests/status`, `tests/unit`, move-task/mark-status tests, `make test-fast`
**Target Platform**: CLI on Linux/macOS/Windows
**Project Type**: single
**Performance Goals**: at most one extra WP-frontmatter read per command invocation (NFR-001)
**Constraints**: no new append path (C-001); wall-clock ordering untouched (C-002); system writers keep string actors (C-003); identity comparisons byte-identical on existing logs (C-004); Read API contract unchanged (C-005)
**Scale/Scope**: ~12 source modules, 4 work packages
**Dependencies**: none added, upgraded or removed (supply-chain controls of DIRECTIVE_051 not triggered)

## Charter Check

| Gate | Result |
|---|---|
| Single canonical authority | PASS: one lane authority (the package), one actor builder (`status/actor.py`); `build_resolved_actor`/`build_self_asserting_actor` delegate to it instead of growing a second shape |
| Architectural alignment | PASS: `status_lanes` imports the public `spec_kitty_events.status`; no new layer edge; no Python append path (ADR 2026-10-22-1) |
| DDD + tiered rigour | PASS: actor value object and identity rule get the most rigour (pure unit tests + per-path ATDD) |
| ATDD-first | PASS: each WP opens with a failing test through the pre-existing entry point |
| Terminology | PASS: Mission/work package; no `feature*` additions; `--agent` on mark-status follows existing flag naming |
| Tidy-first (SO #2) | PASS: WP02 starts with a behaviour-preserving extraction of the actor seam |
| No heavy suites (NO_FULL_HEAVY_SUITES_IN_MISSION) | PASS: targeted + blast radius + `make test-fast`; named arch gates only (`test_shared_package_boundary.py`, `test_layer_rules.py`, `test_no_legacy_terminology.py`) |

No violations; Complexity Tracking empty.

## Project Structure

### Documentation (this mission)

```
kitty-specs/status-contract-readers-01M5ZAAC/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/status-actor.md
└── tasks.md          # /spec-kitty.tasks
```

### Source Code (repository root)

```
src/specify_cli/
├── status_lanes.py                         # IC-01: derived lane constants
├── status/
│   ├── actor.py                            # IC-02: NEW ProfileSource, role_for_hop, build_status_actor, planned_profile_for_wp
│   ├── models.py                           # IC-02: decode_actor 5-key, actor_full_identity drops wp_frontmatter
│   ├── resolved_binding.py                 # IC-02: profile_source on the binding (not in to_delta)
│   ├── emit.py                             # IC-02: build_resolved_actor / build_self_asserting_actor delegate
│   └── work_package_lifecycle.py           # IC-04: orchestrator transitions
├── cli/commands/agent/
│   ├── workflow.py                         # IC-02: _resolve_dispatch_binding stamps invocation|flag
│   ├── tasks_move_task_executor.py         # IC-03: every hop + paired note
│   ├── tasks_move_task_hops.py             # IC-03: role per hop
│   ├── tasks_verdict_persistence.py        # IC-03: verdict annotation
│   ├── tasks_mark_status.py, tasks.py      # IC-04: actor + --agent
│   ├── workflow_executor.py                # IC-04: implement/review annotations
│   └── status.py                           # IC-04: agent status emit
└── orchestrator_api/wp_lifecycle.py        # IC-04
tests/
├── status/ (unit: actor builder, decode, identity, lanes)
└── specify_cli/cli/commands/agent/ (ATDD per write path)
```

**Structure Decision**: single project; changes stay inside `specify_cli` (status package and agent commands).

## Design decisions

- **D-1 Lane names.** `CANONICAL_LANES` keeps its name (8 importers, public in `status.__all__`)
  and is documented as the authorable subset; adding a second name for the same tuple would be
  a duplicate authority. New: `PACKAGE_LANES` (all package lanes, ordered) and
  `NON_AUTHORABLE_LANES = frozenset({"genesis"})`. `event_log_merge` keeps reading the declared
  order through `CANONICAL_LANES`.
- **D-2 Where provenance lives.** Inside the actor dict (`profile_source`), so one object
  carries who acted; `StatusTransitionPayload.actor` accepts any dict. The decoder accepts
  exactly `{tool, role, profile, model}` (legacy) or that plus `profile_source`; `profile_source`
  must be one of the four values or `null`, and `null` iff `profile` is `null`.
- **D-3 Resolution order.** `invocation` (Op record via `--invocation-id`) → `flag`
  (`--profile`) → `agent_string` (compact `--agent` segment) → `wp_frontmatter` → `null`.
  The binding carries its own source, set in `_resolve_dispatch_binding`; `to_delta` is
  unchanged, so the resolved-binding annotation keeps its shape.
- **D-4 Role.** `reviewer` for hops into `in_review`/`approved`/`done` and any hop whose
  from-lane is `in_review`; `implementer` otherwise. Annotations take the role of the action
  that writes them (paired note = its hop's role; verdict = reviewer; subtask marks =
  implementer).
- **D-5 Identity.** `actor_full_identity` uses the profile only when `profile_source` is not
  `wp_frontmatter`. Legacy dicts (no key) and strings behave as today. `_actor_key` and
  `actor_identity_str` are untouched (tool-based).
- **D-6 Frontmatter read.** `planned_profile_for_wp(feature_dir, wp_id)` reads the WP file
  once through `read_wp_frontmatter`; any read/parse failure yields `None` (never blocks a
  transition). Callers compute it once per command.
- **D-7 System writers.** Unchanged; follow-up issue filed at closeout.

## Implementation Concern Map

### IC-01 — Lane set derived from the events package

- **Purpose**: one lane authority; `genesis` handled explicitly.
- **Relevant requirements**: FR-001, FR-002, FR-003, SC-004
- **Affected surfaces**: `src/specify_cli/status_lanes.py`; tests under `tests/status/`
- **Sequencing/depends-on**: none
- **Risks**: import cycle if `status_lanes` pulls status orchestration (it only imports the package)

### IC-02 — Actor value and readers

- **Purpose**: the single builder, profile provenance, decoder and identity rule.
- **Relevant requirements**: FR-004, FR-005, FR-006, FR-012, FR-013, FR-014
- **Affected surfaces**: `status/actor.py` (new), `status/models.py`, `status/resolved_binding.py`, `status/emit.py`, `cli/commands/agent/workflow.py` (`_resolve_dispatch_binding`)
- **Sequencing/depends-on**: none (tidy-first extraction first)
- **Risks**: the 4-key strictness of `decode_actor` is load-bearing (#FR-015 silent corruption); widen without loosening

### IC-03 — move-task and verdict writers

- **Purpose**: every move-task hop, its paired note, and the verdict note carry the actor.
- **Relevant requirements**: FR-007, FR-010
- **Affected surfaces**: `tasks_move_task_executor.py`, `tasks_move_task_hops.py`, `tasks_move_task.py`, `tasks_verdict_persistence.py`
- **Sequencing/depends-on**: IC-02
- **Risks**: overlap with #6715 (`tasks_move_task.py`); keep edits local to actor construction

### IC-04 — mark-status, action, emit and orchestrator writers

- **Purpose**: the remaining named write paths carry the actor; mark-status gains `--agent`.
- **Relevant requirements**: FR-008, FR-009, FR-011
- **Affected surfaces**: `tasks_mark_status.py`, `tasks.py`, `workflow_executor.py`, `status.py`, `orchestrator_api/wp_lifecycle.py`, `status/work_package_lifecycle.py`; docs `docs/architecture/status-model.md`; changelog
- **Sequencing/depends-on**: IC-02
- **Risks**: orchestrator-api is a machine contract; its JSON output does not change, only the stored actor
