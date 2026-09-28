# Implementation Plan: Truthful software-dev discovery step and finalize shim cleanup

**Branch**: `claude/project-thread-silj7c` | **Date**: 2026-09-28 | **Spec**: [spec.md](spec.md)
**Input**: Mission specification from `kitty-specs/truthful-discovery-step-01M3KABP/spec.md`

Planning answers come from the grounding squad (researcher-robbie, architect-alphonso) and the post-spec adversarial squad (reviewer-renata, architect-alphonso). They are recorded in [research.md](research.md). The one scope decision (truthful authoring path, no software-dev scaffold) is DM-01M3KAD2G6HZMB6TF4W049WCB9.

## Summary

Three independent slices:

1. **Prompt truthfulness (#5254).** Rewrite the mission-step `research` prompt, which serves both as the software-dev `discovery` step and as `/spec-kitty.research` for every mission type. It becomes an authoring instruction: record findings in `kitty-specs/<mission>/research.md` (create or extend), with the CLI scaffold described as applying only to mission types that ship research templates, after their plan is filled. The pre-flight no longer stops on the primary branch. Align the plan prompt's Phase 0 text ("extend, don't replace") and the three other agent-facing surfaces (the `spk-mission-research` skill, the command map, the slash-command doc).
2. **Research command templates (#5254).** Resolve `research.md` / `data-model.md` from the research pack's shipped `research-template.md` / `data-model-template.md` through the canonical `specify_cli.runtime.resolver.resolve_template`. Keep `guard_destructive_overwrite` and the no-empty-file refusal (#4926) byte-for-byte. Retire the now-unused legacy `core.project_resolver.resolve_template_path`.
3. **Shim removal (#5233).** Delete `_ensure_branch_checked_out`, drop its three test patches and the dead `fire_dossier_sync` patch, and rebuild the validate-only read-only fixture so HEAD really differs from the target branch.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: typer, rich (CLI); pytest
**Storage**: files in `kitty-specs/<mission>/` (primary partition)
**Testing**: pytest. Red-first regression tests pinned to #5254 / #5233 (ADR 2026-07-17-1), later converted to focused unit and integration tests. The end-to-end discovery test follows the temp-repo `next` pattern in `tests/next/test_next_command_integration.py`.
**Target Platform**: Linux, macOS and Windows CLI
**Project Type**: single project
**Performance Goals**: the new end-to-end test runs in under 30 s (NFR-004)
**Constraints**: complexity ≤ 15; ruff, ruff format and mypy clean; diff coverage ≥ 90%; no version bump (C-003)
**Scale/Scope**: about 4 source files, 4 prompt/skill/doc sources, and about 8 test files

## Charter Check

- **Single canonical authority**: passes. There is no second research-structure authority (C-001), and template lookup moves onto the one canonical resolver (FR-006). The legacy resolver is retired rather than left as a parallel path.
- **Use canonical sources**: passes. Prompts are edited in `packs/built-in/missions/mission-steps/` only (C-002). Generated agent copies are not touched.
- **ATDD / red-first**: planned. Each slice opens with a failing test pinned to its issue.
- **Pack tiers**: passes. All edits are consumer doctrine and belong in `built-in`. Nothing moves to `internal`.
- **Terminology**: "Mission", never "feature", in new text. The step is named `discovery` (research prompt) wherever it could be confused with specify's discovery interview.
- **Quality standing orders**: campsite cleaning is limited to files already touched; tracer files are seeded at planning.

Re-check after design: no violations. The Complexity Tracking section is not needed.

## Project Structure

### Documentation (this mission)

```
kitty-specs/truthful-discovery-step-01M3KABP/
├── spec.md
├── plan.md
├── research.md
├── checklists/requirements.md
├── decisions/
└── tasks.md, tasks/        (created by /spec-kitty.tasks)
```

### Source Code (repository root)

```
packs/built-in/missions/mission-steps/software-dev/research/prompt.md   # discovery / /spec-kitty.research prompt
packs/built-in/missions/mission-steps/software-dev/plan/prompt.md       # Phase 0 "extend" wording
src/charter/offering/skills/spk-mission-research/SKILL.md
src/charter/offering/skills/spk-start-command-map/references/command-map.md
docs/api/slash-commands.md
src/specify_cli/cli/commands/research.py                                # template names + canonical resolver
src/specify_cli/core/project_resolver.py, src/specify_cli/core/__init__.py  # retire resolve_template_path
src/specify_cli/cli/commands/agent/mission.py                           # delete shim
tests/next/ (new end-to-end discovery test)
tests/specify_cli/cli/commands/test_research_preservation.py, tests/agent/test_commands.py
tests/regressions/test_issue_4890_legacy_finalize_effective_graph.py
tests/specify_cli/cli/commands/agent/test_feature_finalize_bootstrap.py
tests/specify_cli/cli/commands/review/test_issue_matrix_finalize_lint.py
tests/specify_cli/cli/commands/test_finalize_tasks_validate_only_readonly.py
tests/specify_cli/cli/commands/agent/test_coord_topology_no_strand.py
```

**Structure Decision**: single project, existing layout. No new modules.

## Implementation Concern Map

### IC-01 — Research command resolves shipped templates canonically

- **Purpose**: make `spec-kitty research` deliver all four advertised artifacts for mission types that ship templates, through the canonical resolver.
- **Relevant requirements**: FR-005, FR-006, FR-007; NFR-001; SC-002, SC-003
- **Affected surfaces**: `research.py` (`_write_research_asset`, the asset table at :264-271, import at :20), `core/project_resolver.py`, `core/__init__.py`, `test_research_preservation.py`, `test_commands.py`, `tests/research/`
- **Sequencing/depends-on**: none
- **Risks**:
  - Resolver tier change: the canonical resolver does not read `.kittify/missions/<type>/templates/` or project-root `templates/`, and it does read `.kittify/overrides/templates/`, org packs and the package default. This goes in the changelog.
  - `resolve_template` raises `FileNotFoundError`; map it to the existing "no template" outcome.
  - Destination names (`research.md`) differ from template names (`research-template.md`); keep the mapping in one table.
  - The CSVs resolve as `research/<name>.csv` in the same tier chain.
  - Removing a name from `specify_cli.core.__all__` touches `__init__.py`. Main is on an untagged rc, so no bump (C-003).

### IC-02 — Truthful discovery / research prompt and aligned guidance

- **Purpose**: every instruction in the prompt `next` issues for `discovery` is executable before a plan exists, and `/spec-kitty.research` states its per-mission-type contract.
- **Relevant requirements**: FR-001, FR-002, FR-003, FR-004, FR-012, FR-013
- **Affected surfaces**: research `prompt.md`, plan `prompt.md` Phase 0, `spk-mission-research/SKILL.md`, `command-map.md`, `docs/api/slash-commands.md`
- **Sequencing/depends-on**: none. The wording must match IC-01's final behaviour: IC-01 lands first or the two land together.
- **Risks**:
  - Generated copies under `.claude/` and similar directories are not edited.
  - Existing prompt-invariant tests (`tests/next/test_prompt_file_invariant.py`, `tests/doctrine/test_builtin_cli_command_references.py`) may pin text.
  - The skill change may trip the doctrine manifest or regen gates; run `spec-kitty doctrine regenerate-graph` if the pack manifest hashes skills.

### IC-03 — End-to-end discovery contract test

- **Purpose**: prompt and CLI cannot drift apart again (FR-008, SC-001).
- **Relevant requirements**: FR-003, FR-008; NFR-004
- **Affected surfaces**: a new test under `tests/next/`
- **Sequencing/depends-on**: IC-01, IC-02. It is written red first against today's prompt.
- **Risks**:
  - Extracting `spec-kitty` invocations from prose must be robust: only fenced code and inline code with a `spec-kitty ` prefix count, and placeholders like `<handle>` are substituted.
  - The test must not use `--result success` to skip guards. It advances `next` the supported way.

### IC-04 — Retire the finalize checkout shim

- **Purpose**: remove the test-only no-op and make the read-only test prove its claim (#5233).
- **Relevant requirements**: FR-009, FR-010, FR-011; C-005; SC-004
- **Affected surfaces**: `agent/mission.py:352-354`, the four finalize tests, `test_coord_topology_no_strand.py:103`
- **Sequencing/depends-on**: none (independent of IC-01 to IC-03)
- **Risks**:
  - `patch()` raises on a missing attribute, so the shim deletion and the patch removals go in one commit.
  - The divergent-branch fixture must keep the mission discoverable from HEAD, which is the #1861 shape.
