# Implementation Plan: Scoped agent-profile sentinel lookup for the board

**Branch**: `issue-6917-sentinel-scoped-profile-read` | **Date**: 2026-11-01 | **Spec**: [spec.md](./spec.md)
**Input**: Mission specification from `kitty-specs/issue-6917-sentinel-scoped-profile-read-01M6BV17/spec.md`

## Summary

`spec-kitty agent tasks status` builds `ActiveCharterService` (pack context, activation ledger,
offering service) and then the complete `AgentProfileRepository` — 26 shipped profile documents
plus the 358-node lineage graph — to answer one structural boolean per claimed row
(`profile.sentinel`, the 👤 marker). Measured on this checkout: 1.14 s for the service build and
0.94 s for the first catalogue read, inside a ~4 s command.

The fix keeps the same authority and the same parsing pipeline, and stops materialising what a
read-only render never reads:

1. `AgentProfileRepository` gains an opt-in `only_ids` scope that parses only
   `<profile-id>.agent.yaml` in each layer (built-in → org → project) through its existing
   validation, merge, skip and language-scope code. Default `None` = unchanged.
2. The shipped lineage graph goes back to being built on first use (#6462's `_graph()` accessor,
   lost in a later refactor), so profile-map readers stop paying 0.54 s for successor edges they
   never traverse.
3. One new, pinned accessor on the charter sole door — `ActiveCharterService.agent_profile_sentinels(ids)`
   — plus a light builder (`build_agent_profile_sentinels`) that skips `PackContext` because
   `sentinel` is structural, exactly like `get_provenance()`.
4. `tasks_status_cmd` collects the ids its rendered rows name, performs one scoped lookup, and
   answers the marker from that mapping.

## Technical Context

**Language/Version**: Python 3.12 (project floor 3.11 per `pyproject.toml`; `requires-python >=3.11`)
**Primary Dependencies**: pydantic (profile validation), ruamel.yaml (pack parsing), typer (CLI); no new dependency
**Storage**: filesystem pack trees (`packs/built-in/`, org pack roots, `.kittify/charter-packs/`) — N/A for a database
**Testing**: pytest, targeted fast suites plus `tests/architectural/` gates; a census test counting agent-profile YAML parses through the production `status` render
**Target Platform**: CLI on Linux/macOS developer hosts and CI
**Project Type**: single project (Python package `specify_cli` + `charter` internal runtime)
**Performance Goals**: board render parses ≤ the number of distinct profile ids its rows name (≤ 3 for a two-profile board, 26 today) and the charter-side marker cost drops from ~2.1 s to ≤ 0.5 s warm
**Constraints**: no new dependency; no change to the default `AgentProfileRepository` load; no new construction site outside the charter sole door, builder and offering layer; `sentinel` stays structural (never activation-gated)
**Scale/Scope**: one render path, three source modules touched in `src/charter/`, one CLI module, one new accessor; ~120 lines of production change

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Charter rule | How this plan satisfies it |
| --- | --- |
| Single canonical authority | The read reuses `AgentProfileRepository`'s loader (one parser, one merge, one language gate). No raw-YAML reader is added; `AgentProfileRepository` stays the authority for profile content. |
| Architectural alignment / module seams | Implementation lands in `charter/offering/` (owner of the repository), `charter/activation/resolver.py` (sole door) and `active_charter_service_builder.py` (the ONE builder). `specify_cli` calls the accessor only. |
| ATDD-first | The census test is written first and must fail on unmodified `src` (26 profile parses) before the scope exists. |
| Terminology canon | Uses the mission/agent-profile/sentinel vocabulary; no retired "doctrine" naming in new code or docs. |
| Standing order 2 (campsite) | Removes the eager graph load the same code path pays today, restoring a previously shipped decision rather than inventing one. |
| Standing order 5 (canonical sources, no shrink-only allowlist) | Zero new exclusions in the sole-door gates. |
| `NO_FULL_HEAVY_SUITES_IN_MISSION` | Validation = targeted fast suites + architectural gates + the new census test; CI owns the full matrix. |
| DIRECTIVE_024 locality / DIRECTIVE_025 boy-scout | Edits stay at the call site and in the repository they use; no opportunistic refactor of `tasks_status_cmd`'s unrelated phases. |

No violations; `Complexity Tracking` stays empty.

## Project Structure

### Documentation (this mission)

```
kitty-specs/issue-6917-sentinel-scoped-profile-read-01M6BV17/
├── plan.md              # This file
├── research.md          # Discovery + Phase 0 decisions
├── data-model.md        # Phase 1: entities and the scoped-read contract
├── quickstart.md        # Phase 1: how to verify the delivered behaviour
├── contracts/
│   └── agent-profile-sentinels.md   # the pinned accessor contract
└── tasks.md             # Phase 2 output (/spec-kitty.tasks)
```

### Source Code (repository root)

```
src/
├── charter/
│   ├── activation/
│   │   ├── resolver.py                      # ActiveCharterService: + agent_profile_sentinels(ids)
│   │   └── active_charter_service_builder.py# + build_agent_profile_sentinels(repo_root, ids)
│   └── offering/
│       ├── service.py                       # CharterOfferingService: + agent_profile_sentinels(ids)
│       └── agent_profiles/repository.py     # + only_ids scope, restored _graph() accessor
└── specify_cli/cli/commands/agent/
    └── tasks_status_cmd.py                  # one scoped lookup per render, marker from the mapping

tests/
├── charter/
│   ├── test_tasks_status_sentinel_scope_6917.py   # census + marker acceptance (new, red-first)
│   └── test_agent_profile_scoped_load.py          # scoped loader parity/edge cases (new)
├── charter_offering/test_human_in_charge_profile.py  # updated to the new marker contract
├── specify_cli/charter_runtime/test_cli_readers_honour_deny.py  # structural-sentinel ratchet
└── architectural/test_charter_sole_door_*.py      # gates must stay green, no new exclusions
```

**Structure Decision**: single project. The change follows the existing `charter` (governance
runtime) / `specify_cli` (CLI) split; no new package or module tree. The scoped capability lives in
the repository that owns profile parsing, the accessor in the sole-door module, and the light
builder in the module that already owns service construction.

## Complexity Tracking

*No Charter Check violations — this section is intentionally empty.*

## Implementation Concern Map

### IC-01 — Opt-in scoped load inside the profile repository

- **Purpose**: Let a caller ask the repository for a named id set only, without duplicating its
  parse/validate/merge/scope pipeline.
- **Relevant requirements**: FR-003, FR-007, C-003, SC-004
- **Affected surfaces**: `src/charter/offering/agent_profiles/repository.py`
- **Sequencing/depends-on**: none
- **Risks**: The id→file mapping is the `profile-id` ↔ `<id>.agent.yaml` convention; a parity test
  over the shipped catalogue plus overlay fixtures pins it. Overlay merges must still see the
  built-in base for a scoped id, so the built-in layer loads the requested ids even when only an
  org/project file names them.

### IC-02 — Lineage graph built on first use

- **Purpose**: Stop every profile-map reader from parsing the 358-node shipped DRG (`#6462`
  regression).
- **Relevant requirements**: NFR-002, SC-001
- **Affected surfaces**: `src/charter/offering/agent_profiles/repository.py`
- **Sequencing/depends-on**: IC-01 (same file; one coherent diff)
- **Risks**: An explicit `drg=` must stay authoritative; the `DRGLoadError` empty-graph degradation
  moves inside the accessor; nothing outside the class reaches `._drg` (verified).

### IC-03 — Sole-door accessor and light builder

- **Purpose**: Give `specify_cli` one sanctioned way to ask for sentinels that neither bypasses the
  boundary nor builds the activation layer.
- **Relevant requirements**: FR-001, FR-005, C-001, C-002, NFR-003, NFR-004
- **Affected surfaces**: `src/charter/offering/service.py`, `src/charter/activation/resolver.py`,
  `src/charter/activation/active_charter_service_builder.py`,
  `kitty-specs/.../contracts/agent-profile-sentinels.md`
- **Sequencing/depends-on**: IC-01
- **Risks**: Sole-door gates resolve constructors by qualname; all new construction stays in
  already-exempt files. `PackContext` is deliberately skipped, so a malformed `.kittify/config.yaml`
  must still fail closed through the layer resolution the builder does run.

### IC-04 — Board wiring and the red-first census

- **Purpose**: Make the render collect its ids once, consume the scoped mapping, and prove the
  bounded-parse property through the production entry point.
- **Relevant requirements**: FR-002, FR-004, FR-006, NFR-001, SC-001, SC-002
- **Affected surfaces**: `src/specify_cli/cli/commands/agent/tasks_status_cmd.py`,
  `tests/charter/test_tasks_status_sentinel_scope_6917.py`,
  `tests/charter_offering/test_human_in_charge_profile.py`,
  `tests/specify_cli/charter_runtime/test_cli_readers_honour_deny.py`
- **Sequencing/depends-on**: IC-03
- **Risks**: The marker seam is patched by name in `test_tasks_status_cmd_seam.py`; the function
  keeps its name and `tasks.py` re-export, only its lookup parameter changes type.

### IC-05 — Changelog and docs

- **Purpose**: Record the user-visible latency change and the new pinned accessor where
  maintainers look.
- **Relevant requirements**: FR-001 (documented contract), spec success criteria
- **Affected surfaces**: `docs/changelog/CHANGELOG.md`, `docs/architecture/` (only if the accessor
  contract belongs there), mission `contracts/`
- **Sequencing/depends-on**: IC-03
- **Risks**: Keep to one `[Unreleased]` entry naming both effects (issue #6917); do not regenerate
  the whole CLI reference (shared machine cache, other agents running).
