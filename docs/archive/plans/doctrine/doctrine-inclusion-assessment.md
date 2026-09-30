---
title: Doctrine Inclusion Assessment
description: 'Assessment (2026-04-01) of which doctrine artifacts to include, based on PRs #305/#348 and the agent-profile-implementation-rebased branch.'
doc_status: deprecated
updated: '2026-04-05'
---
# Doctrine Inclusion Assessment

> **Retired (deprecated).** Design shipped via the org-doctrine-layer three-layer model (all 8 layer-rule tests pass; PRs #305/#348; drivers #832/#883/#1013/#391). Preserved as a historical record.

Status: assessment as of 2026-04-01, based on PR #305 / #348 and the
`feature/agent-profile-implementation-rebased` branch.

## Context

PR #305 (superseded by #348) establishes three peer landscape containers:
`specify_cli` (control plane), `doctrine` (knowledge library), and
`charter` (governance onboarding). This assessment evaluates how far that
work brings us toward three goals: agent profiles, mission type customization,
and ad-hoc experimentation via doctrine composition.

## Pillar 1: Agent Profiles

### What landed

- `AgentProfile` Pydantic model with 6 sections: context_sources, purpose,
  specialization, collaboration, mode_defaults, initialization_declaration.
- `AgentProfileRepository` with two-source loading (shipped + project
  `.kittify/charter/agents/`), field-level merge, hierarchy traversal
  (`get_children`, `get_ancestors`), and cycle/orphan validation.
- DDR-011 weighted matching: language (0.40), framework (0.20), file-pattern
  (0.20), keyword (0.10), exact-id (0.10), plus workload penalty and
  complexity adjustment.
- 10 shipped profiles: generic-agent, architect, implementer,
  python-implementer, designer, reviewer, planner, researcher, curator,
  human-in-charge (proposed).
- CLI surface: `spec-kitty agent profile list | show | create | hierarchy | init`.
- Tool context injection: `_render_profile_context_fragment()` writes profile
  to agent-specific command directories.

### What is not yet connected

- **Runtime consumption**: `mode_defaults` is defined but nothing in the
  `spec-kitty next` loop alters prompt depth, governance loading, or
  template selection based on the active profile.
- **Fuzzy matching**: Specialization signals use exact string comparison.
  No fuzzy or semantic matching for languages/frameworks/keywords.
- **Nondeterministic tiebreaker**: When base_score is 0, `routing_priority /
  100.0` becomes the sole differentiator, which can produce nondeterministic
  selection across profiles with equal routing priority.

### Maturity: ~80%

The domain model, repository, CLI, and matching algorithm are complete and
tested. The missing piece is runtime integration: the next loop and prompt
generation should consume the resolved profile to scope governance depth and
template selection.

## Pillar 2: Mission Type Customization

### What landed

- `MissionTemplateRepository` with value objects (`TemplateResult`,
  `ConfigResult`) that preserve origin and resolution tier metadata.
- `MissionType` half-open enum with `MissionType.with_name("custom-name")`
  factory for user-defined mission types.
- `ProjectMissionPaths` singleton for `.kittify/missions/` resolution,
  supporting custom mission directories.
- `MissionStepContract` with `DelegatesTo` linking actions to doctrine
  artifact kinds (paradigm, tactic, directive, etc.) and candidate lists.
  4 shipped step contracts (implement, specify, plan, review).
- `MissionStepContractRepository` with save/merge for custom contracts.
- Action index system: `actions/<action>/index.yaml` maps each mission
  action to the specific directives, tactics, styleguides, toolguides, and
  procedures relevant to that step.
- 5-tier resolution chain: override > legacy > global-mission > global >
  package.
- 4 built-in mission types: software-dev, research, plan, documentation.

### What is not yet connected

- **No CLI for custom mission creation**: `MissionType.with_name()` exists
  but there is no `spec-kitty mission create` command.
- **No schema validation for custom mission.yaml**: Custom missions are
  loadable but not validated against the Pydantic schema at creation time.
- **No mission composition surface**: Step contracts and procedures exist as
  structured primitives but nothing lets a user compose a workflow from
  those primitives via CLI or YAML authoring.
- **No custom mission discovery**: The runtime does not scan
  `.kittify/missions/` for user-authored mission types.

### Maturity: ~45%

The infrastructure (factory, resolver, repositories, step contracts, action
indices) is solid. The gap is a user-facing authoring and discovery surface.
A user wanting a custom mission must currently hand-write all YAML artifacts
and know the internal directory conventions.

## Pillar 3: Ad-hoc Experimentation / Doctrine Composition

### What landed

- `DoctrineService` lazy aggregator exposing all 8 artifact repositories:
  agent_profiles, directives, tactics, styleguides, toolguides, paradigms,
  procedures, mission_step_contracts.
- `compile_charter()` full pipeline: interview answers -> sanitize
  against catalog -> build references (transitive) -> render markdown.
- `build_charter_context()` with action-scoped depth loading (depth-1
  compact, depth-2 full references) and first-load state tracking.
- `Procedure` artifact model with two-source repository and save support.
- `ProcedureRepository` supports creating custom procedures in
  `.kittify/procedures/`.
- Action index scoping: `charter/context.py` loads doctrine
  per-action, building directive/tactic/extended lines only for the current
  workflow step.
- Mission dossier system: artifact indexing, manifest registry,
  completeness hashing, REST API endpoints.

### What is not yet connected

- **No compiler** (the #327 gap): Action indices and step contracts exist
  as structured sources, but nothing compiles them into the generated
  command templates that runtime actually consumes. The template
  copy/overlay machinery (migrations deploying to 12 agent directories) is
  still the active delivery mechanism.
- **No ad-hoc workflow composition surface**: No CLI command to compose a
  custom workflow from directives + tactics + procedures.
- **Limited doctrine authoring**: `Procedure` can be created via
  repository, but `Directive`, `Tactic`, `Paradigm`, `Styleguide`, and
  `Toolguide` cannot be created from the CLI. They must ship in the
  doctrine package or exist in the catalog.
- **No custom step contract CLI**: `MissionStepContractRepository.save()`
  exists but no CLI wraps it.

### Maturity: ~25%

The foundation (DoctrineService, action-scoped context, procedures,
charter pipeline) is in place. The compiler proposed in #327 is the
critical missing bridge that would make doctrine the authoritative source
for mission behavior rather than an advisory layer sitting beside the
template overlay machinery.

## The Compiler Gap (#327)

Issue #327 proposes a compiler that:

1. Consumes structured doctrine sources (step contracts, procedures,
   directives, tactics, action indices, mission definitions).
2. Generates complete mission bundles (command-templates, action indices,
   guidelines, mission-runtime.yaml, manifest metadata).
3. Makes runtime/init/upgrade consume only compiled outputs.
4. Separates public actions (stable slash-command surface) from internal
   runtime steps (richer execution graph).

Until this compiler exists, doctrine has a split-brain shape:

- Mission behavior lives in `mission.yaml` / `mission-runtime.yaml`.
- Governance lives in doctrine artifacts.
- Prompt behavior lives in authored `.md` command templates.
- Template copies drift across 12 agent directories.

The compiler would collapse these into a single authored-source -> compiled-
output pipeline. It is the architectural move that transforms doctrine from
"advisory" to "authoritative."

## The dependency violation (C1 from PR #305 review)

`src/doctrine/missions/primitives.py` and
`src/doctrine/missions/glossary_hook.py` import from `specify_cli.glossary.*`.
This violates the stated C4 boundary: doctrine should have no dependency on
specify_cli. `doctrine/pyproject.toml` does not declare this dependency, so
standalone installation would fail at import time.

This needs resolution before the doctrine package can be independently
distributed. Options:

1. Move glossary primitives into doctrine (if they are domain knowledge).
2. Inject glossary as a dependency through an interface/protocol.
3. Relocate the importing modules back into specify_cli.

## Skills as the Near-Term Lever (DONE)

While the compiler (#327) is the right long-term direction, updating the
agent skill layer is the most impactful near-term move for day-to-day agent
experience.

The following skill updates have been applied in `src/doctrine/skills/`:

- **spec-kitty-runtime-next**: Added "Doctrine-Aware Step Execution"
  section covering agent profile loading at init, action-scoped context at
  step boundaries, on-demand tactic/directive retrieval, and the anti-
  pattern of upfront context dumps.
- **spec-kitty-charter-doctrine**: Added "Programmatic Doctrine
  Access" section documenting `DoctrineService` entry points, agent profile
  resolution via DDR-011, action index scoping, `MissionStepContract`
  delegation semantics, and the iterative context loading pattern.
- **spec-kitty-mission-system**: Added "Doctrine Composition Layer" section
  explaining `MissionStepContract` as the action contract layer, `Procedure`
  as reusable workflow primitives, and action indices as the doctrine
  scoping mechanism.
- **README.md**: Added `src/doctrine/skills/README.md` documenting the
  skills-vs-mission-composition boundary, the iterative loading pattern,
  and the full skill inventory.

All three skill descriptions were updated to reference the new doctrine
surfaces in their trigger lists.

The iterative context loading pattern taught by these skills is compatible
with the future compiler: skills teach agents how to consume doctrine
outputs, regardless of whether those outputs come from hand-authored
templates or a compiled bundle.

## Recommendations

### Short-term (next 1-2 specs)

3. Wire agent profile resolution into the `spec-kitty next` prompt
   generation path so profile.mode_defaults and
   profile.specialization.boundaries influence template selection and
   governance depth.
4. Fix the C1 dependency violation (doctrine -> specify_cli imports).
5. Add `--cov=src/doctrine` to CI coverage jobs (C2).

### Medium-term (compiler track, #327)

6. Define the revised mission composition schema (public actions vs
   internal steps, procedure refs).
7. Pilot the compiler against the `software-dev` mission.
8. Add `spec-kitty mission create` CLI for custom mission type scaffolding.

### Long-term

9. Retire the template copy/overlay migration machinery for compiler-backed
   missions.
10. Enable ad-hoc workflow composition via CLI-driven step contract and
    procedure authoring.
