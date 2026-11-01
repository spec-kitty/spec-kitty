---
title: Doctrine Artifact Governance Model
description: Stores directives, tactics, styleguides, and mission assets as typed schema-validated repository artifacts, and compiles charter bundles from them, not from prose.
status: Accepted
date: '2026-02-23'
doc_status: active
kind: ADR
updated: '2026-02-23T00:00:00Z'
---

## Context and Problem Statement

2.x introduces a doctrine layer that did not previously have an explicit ADR. We now have:

1. Typed doctrine artifacts under `src/doctrine/` (directives, tactics, styleguides, toolguides, schemas, mission assets).
2. A charter generation flow built from interview answers plus doctrine catalog selection.
3. Runtime/template loading paths that resolve packaged doctrine mission assets as canonical defaults.

Without an ADR, these choices are hard to evaluate and easy to accidentally regress.

## Decision Drivers

1. Make doctrine behavior auditable and deterministic.
2. Keep governance artifacts local-first and repository-native.
3. Enforce schema-level quality gates for doctrine artifacts.
4. Ensure charter generation references explicit doctrine selections.

## Considered Options

1. Keep doctrine behavior implicit in templates and command handlers.
2. Store doctrine as typed, schema-validated repository artifacts and compile charter bundles from them (chosen).
3. Move doctrine selection/generation to an external service.

## Decision Outcome

**Chosen option:** Store doctrine as typed, schema-validated repository artifacts and compile charter bundles from them.

### Decision Details

1. Doctrine artifacts are first-class files under `src/doctrine/` with schema contracts in `src/doctrine/schemas/`.
2. Charter generation compiles interview inputs plus doctrine selections into `.kittify/charter/` (`charter.md`, references, library files).
3. Runtime default mission/template assets resolve from doctrine package assets (`src/doctrine/missions/...`) when project and global overrides are absent.
4. Doctrine integrity is tested with fixture schema tests and in-repo artifact compliance tests.

### Consequences

#### Positive

1. Governance behavior is explicit, versioned, and reviewable.
2. Charter output is reproducible from interview + doctrine selection state.
3. Doctrine changes are testable in CI before user-facing execution.

#### Negative

1. Additional schema and test maintenance burden for doctrine artifacts.
2. More files and concepts for contributors to understand.

#### Neutral

1. Existing command UX is preserved while implementation becomes doctrine-backed.

## Confirmation

This decision is validated when:

1. Doctrine artifacts validate against schemas.
2. Cross-artifact references resolve (for example directive `tactic_refs`, tactic references, toolguide paths).
3. Charter generation produces deterministic bundles from the same inputs.
4. Runtime/template resolution selects doctrine package defaults when higher-precedence tiers are absent.

## More Information

Implementation references:

1. `src/doctrine/schemas/*.schema.yaml`
2. `src/doctrine/directives/test-first.directive.yaml`
3. `src/doctrine/tactics/*.tactic.yaml`
4. `src/doctrine/styleguides/**/*.styleguide.yaml`
5. `src/doctrine/toolguides/*.toolguide.yaml`
6. `src/specify_cli/charter/compiler.py`
7. `src/specify_cli/cli/commands/charter.py`
8. `src/specify_cli/runtime/home.py`
9. `src/specify_cli/runtime/resolver.py`
10. `tests/doctrine/test_schema_validation.py`
11. `tests/doctrine/test_artifact_compliance.py`
