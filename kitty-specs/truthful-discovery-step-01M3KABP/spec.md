# Mission Specification: Truthful software-dev discovery step and finalize shim cleanup

**Mission Branch**: `claude/project-thread-silj7c`
**Created**: 2026-09-28
**Status**: Draft
**Input**: GitHub issues #5254 and #5233, grounded by a profile-loaded research squad on main 4e81f4d5 (operator request, Stijn, 2026-09-28).

## Intent Summary

A mission agent that follows only the canonical prompt `spec-kitty next` issues must be able to finish that step. Today the first software-dev step (`discovery`) instructs the agent to run `spec-kitty research`, which for a software-dev mission creates nothing, requires a filled `plan.md` that cannot exist yet, and is invoked without its required `--mission` argument. The plan step already owns authoring `research.md` and `data-model.md`. Separately, `spec-kitty research` never scaffolds `research.md` or `data-model.md` even for the research mission, because it asks for template names the research pack does not ship.

- **Primary actor**: a mission agent driving a software-dev mission through `spec-kitty next`.
- **Trigger**: `next` issues the `discovery` step (the first software-dev step, before specify).
- **Desired outcome**: the agent can satisfy every success criterion the discovery prompt states, using only supported, working commands and without bypassing runtime guards.
- **Invariant**: the research command never fabricates empty artifacts and never truncates user-authored research without explicit force (#4926).
- **Boundary**: the plan step remains the single owner of software-dev `research.md` / `data-model.md` structure; no second software-dev scaffold authority is introduced (decision DM-01M3KAD2G6HZMB6TF4W049WCB9).

A second, independent slice removes a no-op production function kept only as a test patch target (#5233) and restores the real behaviour its tests claim to cover.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Discovery step is executable as issued (Priority: P1)

An agent starts a software-dev mission and receives the discovery step from `next`. It follows the prompt: records its findings where the prompt says, and meets the prompt's success criteria. Nothing in the prompt sends it to a command that refuses, no-ops, or depends on a later step's artifact.

**Why this priority**: it is a live blocker for real missions (#5151) and every new software-dev mission hits it first.

**Independent Test**: start a software-dev mission in a scratch repo, obtain the discovery step through `next`, carry out its instructions through the supported CLI, and check each advertised success criterion.

**Acceptance Scenarios**:

1. **Given** a freshly created software-dev mission with no `plan.md`, **When** the agent follows the issued `discovery` prompt, **Then** every command it is told to run exits successfully and every success criterion names an artifact the agent can author with the instructions given.
2. **Given** the discovery prompt, **When** it names a CLI invocation, **Then** that invocation carries every argument the CLI requires.
3. **Given** the plan prompt, **When** it describes Phase 0 research, **Then** it says to extend an existing `research.md` rather than replace it.

### User Story 2 - Research mission scaffolds its own templates (Priority: P2)

An operator on a research-type mission runs `spec-kitty research --mission <handle>` after planning. The command creates `research.md` and `data-model.md` from the research pack's shipped templates, plus the two CSV stubs.

**Why this priority**: the command advertises four artifacts but can only ever produce two, for every mission type.

**Independent Test**: create a research mission with a filled plan, run the command, and compare each created file with its shipped template.

**Acceptance Scenarios**:

1. **Given** a research mission with a filled plan, **When** `spec-kitty research` runs, **Then** `research.md` and `data-model.md` are created with the shipped template content.
2. **Given** a software-dev mission, **When** `spec-kitty research` runs, **Then** it still creates no empty files and reports truthfully that no template exists.
3. **Given** a user-authored `research.md`, **When** `spec-kitty research` runs without force, **Then** the file is untouched.

### User Story 3 - No test-only no-op in production code (Priority: P3)

A maintainer reading `agent/mission.py` sees only functions the product calls. Tests that assert the finalize command is read-only in validate-only mode exercise the real divergent-branch case they describe.

**Why this priority**: tech debt; no user-visible behaviour change.

**Independent Test**: `git grep _ensure_branch_checked_out` returns nothing; the finalize tests pass; the read-only test fails if validate-only mode moves HEAD off a branch that differs from the target.

**Acceptance Scenarios**:

1. **Given** the codebase, **When** searching for the retired checkout shim, **Then** there are no definitions, patches, or references.
2. **Given** a mission whose target branch differs from the checked-out HEAD, **When** `finalize-tasks --validate-only` runs, **Then** HEAD, the working tree, and the index are unchanged.

### Edge Cases

- The discovery prompt is also served as the `/spec-kitty.research` slash command and skill; the rewritten text must be correct in both entry points.
- A coordination-topology mission: research artifacts are primary-partition kinds and must land on the primary surface.
- A project override at `.kittify/overrides/templates/` must still win over the pack default.
- A mission running on the primary branch (for example `main`) must not be told to stop by the prompt's location pre-flight.
- The `research/` CSV stubs must still scaffold for mission types that ship them.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Discovery prompt names an executable authoring path | As a mission agent, I want the `discovery` step prompt (the mission-step `research` prompt) to tell me to record findings directly in the mission's `research.md` (create or extend), a path that works before a spec or plan exists, so that I can complete the step. | High | Open | [build] | no |
| FR-002 | Every discovery instruction is satisfiable | As a mission agent, I want every instruction in the `discovery` prompt (its location pre-flight, which today stops on `main` even though planning runs on the target branch; its workflow-context claims; its steps; its success criteria) to be achievable by following the prompt alone before a plan exists, so that I never need a manual workaround. | High | Open | [build] | no |
| FR-003 | Prompt command invocations are complete | As a mission agent, I want any command the discovery prompt names to include its required arguments, so that it does not fail on usage errors. | High | Open | [build] | no |
| FR-004 | Plan prompt says to extend existing research | As a mission agent, I want the software-dev plan prompt's Phase 0 text to say to extend an existing `research.md` and not replace it, so that discovery work is kept. Verified by a prompt-text invariant test. | Medium | Open | [build] | no |
| FR-005 | Research command uses the research pack's shipped templates | As an operator on a research mission, I want `spec-kitty research` to create `research.md` and `data-model.md` from the shipped templates, so that the command delivers what it advertises. | High | Open | [build] | no |
| FR-006 | Template lookup follows the canonical resolution chain | As an operator, I want research templates resolved through the canonical template resolver used for other mission templates (project overrides, org packs, user home, then the shipped pack default), so that a fresh install finds the shipped templates without a populated home directory. The resulting tier change (the legacy project-mission and project-root `templates/` tiers are no longer read) is documented in the changelog, and the now-unused legacy research resolver is retired. | Medium | Open | [build] | no |
| FR-007 | Empty-artifact and truncation protection kept | As an operator, I want the research command to keep refusing to create empty files or overwrite authored research without force (#4926), so that no data is lost. | High | Open | [ratchet] | yes — paired with FR-005's positive control on the same fixture |
| FR-008 | End-to-end discovery test | As a maintainer, I want an integration test that creates a fresh software-dev mission with no `plan.md`, takes the `discovery` prompt that `next` issues, extracts every `spec-kitty` invocation it tells the agent to run, runs each one (exit 0, every required option present), and then shows `next` advancing past `discovery`, without bypassing runtime guards, so that prompt and CLI cannot drift apart again. | High | Open | [build] | no |
| FR-009 | Retired checkout shim removed | As a maintainer, I want the no-op `_ensure_branch_checked_out` and every test patch of it removed, so that tests only patch real seams. | Low | Open | [build] | no |
| FR-010 | Validate-only read-only test covers the divergent-branch case | As a maintainer, I want the validate-only read-only test to run with HEAD on a branch different from the mission target, so that it proves what its docstring claims. | Low | Open | [build] | no |
| FR-011 | Dead dossier-sync patch removed | As a maintainer, I want the test patch of the retired `specify_cli.status.fire_dossier_sync` hook in the coordination no-strand test removed, so that the test does not rely on a no-op. The public import-compatibility shim in `specify_cli.status` itself stays (C-004). | Low | Open | [build] | no |
| FR-012 | `/spec-kitty.research` contract is explicit for every mission type | As an operator on any mission type, I want the single `/spec-kitty.research` prompt (rendered from the software-dev source for all types) to state when `spec-kitty research --mission <handle>` applies (a mission type that ships research templates, after its plan is filled) and that it creates nothing for types without templates, so that the scaffold FR-005 fixes stays reachable by agents and nobody is sent to a no-op. | High | Open | [build] | no |
| FR-013 | Agent-facing research guidance agrees | As a mission agent, I want every agent-facing surface that describes the research step or command (the `spk-mission-research` skill, the command-map reference, the slash-command API doc, and the prompt's own workflow-context text) to state the same ordering and invocation as the rewritten prompt, so that no surface contradicts another. | Medium | Open | [build] | no |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | No regression in existing research tests | All existing research-command, prompt-invariant and finalize tests pass. Tests that pin the old behaviour are updated to the new truthful behaviour and justified in the PR; known ones: `tests/agent/test_commands.py` (software-dev produces nothing; patches the legacy resolver), `tests/specify_cli/cli/commands/test_research_preservation.py` (seeds the legacy tier and asserts no template for any type). | Reliability | High | Open |
| NFR-002 | Code quality gates | New and changed code passes ruff, ruff format and mypy with zero new findings and no new suppressions; every function stays at cyclomatic complexity 15 or below. | Maintainability | High | Open |
| NFR-003 | Diff coverage | Changed source lines reach at least 90% coverage from the mission's tests. | Maintainability | High | Open |
| NFR-004 | Test runtime | The new end-to-end discovery test completes in under 30 seconds on a developer machine. | Performance | Medium | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Single research-structure authority | No software-dev research scaffold template is added; the plan step remains the owner of software-dev `research.md` / `data-model.md` structure. | Technical | High | Open |
| C-002 | Edit source templates only | Prompt changes are made in `packs/built-in/missions/mission-steps/`, never in generated agent copies. Carve-out: the FR-013 surfaces (`src/charter/offering/skills/spk-mission-research/`, the `spk-start-command-map` reference, `docs/api/slash-commands.md`) are themselves sources and change together with the prompt. | Technical | High | Open |
| C-003 | No version bump | The package version stays at the current untagged release candidate; the changelog entry goes under `[Unreleased]`. | Business | High | Open |
| C-004 | Scope boundary | Out of scope: research-mission guards and event schemas (#4221), the specify placeholder and discovery-lifecycle issues (#3909, #3932), retiring the deprecated `mission-runtime.yaml`, the test "patch seam" indirection in finalize/charter commands, and the 3.2.6 dossier-sync import shim. | Business | Medium | Open |
| C-005 | No production behaviour change for #5233 | Removing the shim and fixing its tests changes no runtime behaviour. | Technical | Medium | Open |

### Key Entities

- **Discovery step**: the first software-dev runtime step, served from the mission-step `research` prompt; also exposed as `/spec-kitty.research`.
- **Research artifacts**: `research.md`, `data-model.md`, `research/evidence-log.csv`, `research/source-register.csv` in the mission directory (primary partition).
- **Research template**: a pack- or project-supplied file the research command copies into a missing artifact.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An agent following only the issued software-dev discovery prompt meets 100% of its stated success criteria in the end-to-end test, with zero failing or no-op commands. — [build] · no-op passable: no
- **SC-002**: For a research mission, the research command produces 4 of 4 advertised artifacts (today 2 of 4), each non-empty. — [build] · no-op passable: no
- **SC-003**: For a software-dev mission, the research command creates 0 empty files and overwrites 0 authored files. — [ratchet] · no-op passable: yes — positive control is SC-002 on the same test module
- **SC-004**: Zero occurrences of `_ensure_branch_checked_out` remain under `src/` and `tests/` (immutable mission snapshots under `kitty-specs/` keep their history). — [build] · no-op passable: no

## Assumptions

- The discovery prompt is the only built-in prompt instructing `spec-kitty research` for a mission type without research templates (confirmed by the grounding scan of `packs/built-in/missions/mission-steps/`).
- The research pack's `research-template.md` and `data-model-template.md` are the intended scaffolds for the research command's `research.md` and `data-model.md`.
- The research-mission fixture for US2 uses a `plan.md` that passes the strict plan-filled validation, so FR-005's positive control fails only for the reason under test.
- Operator confirmation of the extracted requirement set is taken from the instruction to kick off a mission from the research; the operator may override on the PR.

## Dependencies

- Related: #4926 (closed, guard kept), #4221 (open, sibling), #5204 (closed, command-existence guard), #3909 and #3932 (open, adjacent discovery surface), #1878 (parent of #5233), #1861 (origin of the read-only test).
