---
work_package_id: WP02
title: Drupal Dries profile artifact
dependencies:
- WP01
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-009
- FR-011
- NFR-001
planning_base_branch: feat/drupal-dries-profile
merge_target_branch: feat/drupal-dries-profile
branch_strategy: Planning artifacts for this mission were generated on feat/drupal-dries-profile. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into feat/drupal-dries-profile unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-drupal-dries-profile-01M28X69
base_commit: 1edeb3524d48c3097fd5bde1b6f79984f9654f17
created_at: '2026-09-11T20:35:34.055106+00:00'
subtasks:
- T007
- T008
- T009
- T010
- T011
- T012
- T013
history:
- at: '2026-09-11T19:28:35Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: curator-carla
authoritative_surface: packs/built-in/agent_profiles/
create_intent:
- packs/built-in/agent_profiles/drupal-dries.agent.yaml
execution_mode: code_change
owned_files:
- packs/built-in/agent_profiles/drupal-dries.agent.yaml
- packs/built-in/agent_profiles/README.md
- src/charter/offering/agent_profiles/README.md
role: curator
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – Drupal Dries profile artifact

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `curator-carla`
- **Role**: `curator`

## Objective

Author `packs/built-in/agent_profiles/drupal-dries.agent.yaml` — the artifact that makes User
Story 1 true. One file. Between 140 and 215 lines.

## Context

- **Spec**: FR-001, FR-002, FR-003, FR-009, FR-011, NFR-001
- **Data model**: [data-model.md](../data-model.md) E1 and E2 give the field-by-field contract and
  invariants I1.1–I1.5 — treat that as the specification for this file
- **Research**: R-005 (the directive set and where it came from), R-006 (the boundary distinction),
  R-007 (no invented thresholds)
- **Contract**: [contracts/profile-contract.md](../contracts/profile-contract.md) C-P1

### Read before writing

```bash
packs/built-in/agent_profiles/java-jenny.agent.yaml   # 185 lines — the closest precedent
packs/built-in/agent_profiles/node-norris.agent.yaml  # 201 lines — the two-registry case
```

Do not invent structure. Every field you need already exists in those files.

### Source material

```bash
curl -sSL https://raw.githubusercontent.com/amazeeio/drupal-agents-md/main/Vanilla/AGENTS.md
```

1,492 lines. **Distil, never copy** (C-003). Section map in [research.md](../research.md).

### ⚠️ Standing rule

Do **not** run `spec-kitty doctrine regenerate-graph`, and do **not** edit any `*.graph.yaml`. Those
belong to WP07. `regenerate-graph --check` will report stale after your change — that is expected,
not a defect.

## Branch Strategy

- **Planning branch**: `feat/drupal-dries-profile`
- **Final merge target**: `feat/drupal-dries-profile`
- Worktrees come from `lanes.json` via `spec-kitty implement WP02`. Do not create one by hand.

---

### Subtask T007: Identity, roles, capabilities, routing

**Purpose**: The block the resolver keys on.

**Steps**:

```yaml
profile-id: drupal-dries
name: Drupal Dries
description: Drupal-specialist implementer covering modules, configuration, and Drupal-native theming with PHPUnit and coding-standard discipline
schema-version: "1.0"
roles:
  - implementer
applies_to_languages:
  - php
  - twig
  - yaml
capabilities:
  - drupal-module-implementation
  - entity-and-plugin-development
  - configuration-management
  - drupal-theming
  - phpunit-testing
  - code-review-response
routing-priority: 80
max-concurrent-tasks: 5
```

`routing-priority: 80` is the specialist norm — Java, Python, Node, and Freddy all use it. Do not
differentiate without a reason you can state.

**Validation**:
- [ ] `roles` is `[implementer]` only — not reviewer, not debugger (specify decision)
- [ ] No `specializes-from` field. The model **rejects** it; lineage is WP07's Python change

---

### Subtask T008: Purpose and specialization

**Purpose**: What Dries does, what it knows peripherally, and — the load-bearing part — what it will
not touch.

**Steps**:

1. `purpose`: a paragraph in the voice of the peer profiles. Name ATDD/TDD discipline, the Drupal
   quality gate, and an explicit refusal of architectural decisions.
2. `specialization.primary-focus`: modules, services and dependency injection, Entity API, plugins,
   hooks, Forms API, routing and controllers, configuration management, and Drupal-native theming
   (Twig, `*.libraries.yml`, `Drupal.behaviors`, render arrays, preprocess).
3. `specialization.secondary-awareness`: Batch/Queue APIs, Migration API, content moderation and
   workflows, Composer management, multisite.
4. `specialization.avoidance-boundary` — **read R-006 before writing this**:
   - architectural decisions (deferred to the architect)
   - infrastructure, deployment, server configuration
   - **generic browser component authorship — deferred to Frontend Freddy**
   - non-Drupal PHP frameworks (Symfony, Laravel) outside Drupal's own usage
   - managing other agents

   State the distinction explicitly: Dries **verifies** the Drupal-native theming JavaScript it
   authored; Freddy **authors** generic browser component work. Without that sentence this profile
   contradicts its own self-review protocol, which runs `npm run test`.
5. `specialization.success-definition`: tested idiomatic Drupal code passing all gates, approved by a
   reviewer.

**Validation**:
- [ ] The Freddy deferral names Frontend Freddy explicitly
- [ ] The verification-versus-authorship distinction is present in words, not implied
- [ ] Architectural decisions are refused

---

### Subtask T009: Collaboration, mode defaults, initialization declaration

**Steps**:

1. `collaboration`: `handoff-to: [reviewer]`; `handoff-from: [architect, planner]`;
   `works-with: [reviewer, curator, implementer]`; `output-artifacts`: source-code, unit-tests,
   kernel-tests, functional-tests, implementation-notes; `canonical-verbs`: implement, fix, refactor,
   test, debug.
2. `mode-defaults`: implementation, debugging, refactoring — each with `description` and `use-case`,
   in the Java Jenny shape.
3. `initialization-declaration`: first person, 8–12 lines. Identity, the gates run before handoff,
   the ATDD/TDD rhythm, the boundary, and what Dries does not decide. This is the text an operator
   sees on load — make it specific to Drupal, not a generic implementer paragraph.

**Validation**:
- [ ] Declaration names concrete Drupal gates, not "quality checks"
- [ ] Boundary restated in first person

---

### Subtask T010: Specialization context

**Purpose**: The matching surface for routing.

**Steps**:

```yaml
specialization-context:
  languages: [php, twig, yaml]
  frameworks: [drupal, symfony-components, composer, drush, phpunit, twig]
  file-patterns:
    - "modules/custom/**/*.php"
    - "modules/custom/**/*.module"
    - "**/*.info.yml"
    - "**/*.routing.yml"
    - "**/*.services.yml"
    - "**/*.permissions.yml"
    - "**/*.libraries.yml"
    - "themes/**/*.twig"
    - "**/src/Plugin/**/*.php"
    - "**/src/Form/**/*.php"
  domain-keywords: [drupal, drush, entity api, plugin, hook, twig, render array,
    config management, phpunit kernel test, dependency injection]
  writing-style: [pragmatic, convention-following]
  complexity-preference: [low, medium, high]
```

**Validation**:
- [ ] Patterns match real Drupal layouts (I1.3) — verify against the source guide's scaffolding section
- [ ] `symfony-components` appears as a framework Drupal *uses*, not as Symfony-framework competence

---

### Subtask T011: Self-review protocol

**Purpose**: FR-009. The gates Dries runs before handoff.

**Steps**: Author the ten steps from [data-model.md](../data-model.md) E2 — coding-standards, static
analysis, deprecation scan, PHPUnit, `npm run test`, `npm run test:a11y`, `composer audit`,
`drush cr`, acceptance review, locality review.

Three rules govern this block:

1. **No invented thresholds** (NFR-006, R-007). The source names no PHPStan level. Write the gate as
   "clean at the project's configured level". Do not write "level 5". Do not invent a coverage
   percentage.
2. **Environment-agnostic commands** (C-004). Bare `vendor/bin/phpcs`, `drush cr`, `composer audit`.
   Add exactly one note: containerized setups prefix these (`ddev drush cr`).
3. **The JS steps carry the R-006 caveat** — they verify theming JavaScript Dries authored; they do
   not make Dries the author of generic browser components.

**Validation**:
- [ ] No PHPStan level, coverage number, or mutation score anywhere
- [ ] Exactly one environment adaptation note
- [ ] JS steps carry the caveat

---

### Subtask T012: Directive and tactic references, and provenance

**Purpose**: FR-005 — these become graph edges automatically when WP07 regenerates.

**Steps**:

1. `directive-references`: 010 (Specification Fidelity), 024 (Locality of Change), 025 (Boy Scout),
   030 (Test and Typecheck Quality Gate), 034 (Test-First Development), 051 (Supply-Chain Install
   Safety). Each needs a `code`, `name`, and a `rationale` written for **Drupal** — 051's rationale
   should name Packagist/Composer and npm, which is why Dries carries it.
2. `tactic-references`: `dependency-hygiene`, `tdd-red-green-refactor`, `supply-chain-install-safety`,
   `bug-fixing-checklist` — each with a Drupal-specific rationale.
3. Provenance (FR-010): credit amazee.io's `drupal-agents-md` (Vanilla variant) as the distillation
   source, in a comment or a references field consistent with the peer files.

**Validation**:
- [ ] Six directives, four tactics, each with a rationale
- [ ] No rationale is a generic restatement of the directive's title
- [ ] Provenance present

---

### Subtask T013: Size and traceability audit

**Steps**:

1. `wc -l packs/built-in/agent_profiles/drupal-dries.agent.yaml` → must be 140–215 (NFR-001).
   Over? Move examples into WP03/WP04's styleguides, where they belong. Under 140 and the profile is
   probably missing a block — diff the field list against `java-jenny.agent.yaml`.
2. Sample ten Drupal claims in the file and trace each to the source guide or official Drupal
   documentation (NFR-006, SC-007). Anything untraceable comes out.
3. Confirm the Drupal 10.x/11.x + PHP 8.3+ baseline is stated (FR-011, C-005).
4. `uv run python -c "import yaml,pathlib; yaml.safe_load(pathlib.Path('packs/built-in/agent_profiles/drupal-dries.agent.yaml').read_text())"`

**Validation**:
- [ ] 140–215 lines
- [ ] Ten sampled claims all traceable
- [ ] Version baseline stated
- [ ] Parses as valid YAML

---

## Definition of Done

- [ ] Three files: the new profile YAML plus a registration row in EACH shipped-profile README
      (`packs/built-in/agent_profiles/README.md`, `src/charter/offering/agent_profiles/README.md`).
      `tests/doctrine/test_shipped_profiles.py::test_readme_profile_ids_match_shipped_yaml` globs
      the filesystem for its expected set and asserts both tables match exactly — an unregistered
      new profile reds it. Neither README is generated; both are hand-maintained.
- [ ] 140–215 lines; parses as YAML
- [ ] No `specializes-from` field
- [ ] Boundary names Frontend Freddy and carries the verification/authorship distinction
- [ ] Self-review protocol complete, with no invented threshold
- [ ] Six directive references and four tactic references, each with a Drupal-specific rationale
- [ ] Provenance credited
- [ ] Drupal 10.x/11.x + PHP 8.3+ baseline stated
- [ ] `uv run pytest tests/doctrine/agent_profiles/ -q` — WP01's profile-load assertions now pass
- [ ] No `*.graph.yaml` touched, no regeneration run

## Risks

| Risk | Mitigation |
|------|-----------|
| Source is 1,492 lines; profile caps at 215 | Declarations here, examples in WP03/WP04. If it overflows, the content is in the wrong artifact |
| Adding `specializes-from` because it reads naturally | Rejected at load. Lineage is WP07's Python change |
| Inventing a PHPStan level to make the gate concrete | Fabrication under NFR-006. "The project's configured level" is the honest form |
| Writing the boundary without the R-006 distinction | The profile would contradict its own JS gates |

## Reviewer Guidance

Read the `avoidance-boundary` first — it is where this WP most easily goes wrong. Confirm it names
Frontend Freddy and distinguishes verifying from authoring. Then grep the file for a digit following
"level" or a percent sign; either is likely an invented threshold. Confirm `wc -l` lands in band, and
that `git diff --stat` shows exactly one file.
