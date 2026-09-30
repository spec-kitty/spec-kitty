---
title: 'Doctrine Migration: Architecture Alignment Review'
description: 'Architecture-alignment review of the doctrine migration: how the migration fits the target architecture and the open concerns, in a field-table record.'
doc_status: deprecated
updated: '2026-04-04'
---
# Doctrine Migration: Architecture Alignment Review

> **Retired (deprecated).** Design shipped via the org-doctrine-layer three-layer model (all 8 layer-rule tests pass; PRs #305/#348; drivers #832/#883/#1013/#391). Preserved as a historical record.

| Field | Value |
|---|---|
| Date | 2026-03-26 |
| Scope | Review of `specify_cli` to `doctrine` asset migration against `architecture/2.x` claims |
| Related PRs | feature/agent-profile-implementation branch |
| Reviewer role | Architect (per `architect.agent.yaml` profile) |

## Purpose

Assess whether the completed migration of mission YAML files, command templates,
and content templates from `specify_cli` to `doctrine` aligns with the claims
and invariants documented in `architecture/2.x/`. Identify discrepancies that
need architecture document updates or follow-on implementation work.

---

## Summary Verdict

The migration is **architecturally aligned** with the target state described
across the C4 documents, ADRs, and initiatives. All asset resolution now routes
through `doctrine` as the single source of truth, matching the stated goal.
However, **5 architecture documents contain stale claims** that describe the
pre-migration state as current.

---

## Discrepancy 1: Implementation Mapping Status is Stale

**Location:** `docs/architecture/04_implementation_mapping/README.md`, line 312

**Architecture claims:**
> MissionRepository package relocation | In Progress |
> `src/specify_cli/missions/` still exists as a legacy resolution fallback and
> has not been fully removed. Full cleanup is a deferred task.

**Actual state:** The asset relocation is **complete**. All mission YAML files
(`mission.yaml`, `mission-runtime.yaml`, `expected-artifacts.yaml`), command
templates, and content templates have been removed from `specify_cli/`. The
directory `src/specify_cli/missions/` retains only Python code modules:

- `__init__.py` (re-exports `PrimitiveExecutionContext`, `execute_with_glossary`)
- `primitives.py` (glossary-aware primitive runner)
- `glossary_hook.py` (glossary hook coordinator)
- `.contextive.yml` (glossary term definitions)

The "legacy resolution fallback" for asset files no longer functions -- there
are no mission assets to fall back to.

**Required update:** Change status from "In Progress" to "Complete" and
clarify that `specify_cli/missions/` retains only Python code for the glossary
subsystem, not mission assets.

---

## Discrepancy 2: Loop B Connector Path is Pre-054

**Location:** `docs/architecture/04_implementation_mapping/README.md`, line 99

**Architecture claims:**
```
-> src/specify_cli/missions/*/command-templates/implement.md (Connector)
```

**Actual state:** Command template source is
`src/doctrine/missions/*/command-templates/implement.md`. This was already
flagged in the 054 postmortem (`initiatives/2026-03-054-postmortem/README.md`,
line 89) but has not been corrected.

**Required update:** Fix the Loop B code path to reference
`doctrine/missions/*/command-templates/`.

---

## Discrepancy 3: Agent Tool Connectors Row is Pre-054

**Location:** `docs/architecture/04_implementation_mapping/README.md`, line 36

**Architecture claims:**
> `specify_cli/missions/` still exists as a legacy resolution path and fallback
> during the transition.

**Actual state:** The transition is complete. The source-of-truth path is
`doctrine/missions/*/command-templates/`. The fallback clause should be removed.

**Required update:** Remove the legacy fallback clause from the Agent Tool
Connectors row.

---

## Discrepancy 4: `expected-artifacts.yaml` is Undocumented

**Location:** Not present in any architecture document.

**Actual state:** `expected-artifacts.yaml` files exist for 3 mission types
(software-dev, research, documentation) under `src/doctrine/missions/`. They
define step-aware, class-tagged, blocking-semantics artifact requirements and
are consumed by the dossier `ManifestRegistry` via
`MissionRepository.get_expected_artifacts()`.

This is a doctrine-owned artifact type with:
- A dedicated `MissionRepository` method (line 129 of `repository.py`)
- Consumer code in `src/specify_cli/dossier/manifest.py`
- Test coverage in `src/specify_cli/dossier/tests/test_manifest.py`

**Required update:** Add `expected-artifacts.yaml` to the Doctrine Stack Layer
Model table in `04_implementation_mapping/README.md` under Process Templates,
or create a dedicated row. Consider whether a JSON Schema contract is warranted.

---

## Discrepancy 5: 5-Tier Resolver Chain Not Enumerated

**Location:** Multiple documents reference the resolver without specifying tiers.

ADR `2026-02-23-1` (line 44) says:
> Runtime default mission/template assets resolve from doctrine package assets
> when higher-precedence tiers are absent.

ADR `2026-02-17-2` (line 22) says:
> Discovery precedence follows canonical runtime order.

But **no architecture document enumerates the 5 tiers**. The authoritative
definition exists only in code (`src/specify_cli/runtime/resolver.py`):

| Tier | Label | Path Pattern |
|---|---|---|
| 1 | OVERRIDE | `.kittify/overrides/{templates,command-templates}/` |
| 2 | LEGACY | `.kittify/{templates,command-templates}/` |
| 3 | GLOBAL_MISSION | `~/.kittify/missions/{mission}/{templates,command-templates}/` |
| 4 | GLOBAL | `~/.kittify/{templates,command-templates}/` |
| 5 | PACKAGE_DEFAULT | `doctrine/missions/{mission}/{templates,command-templates}/` |

**Required update:** The resolver tier enumeration belongs in
`04_implementation_mapping/README.md` under the Tiered Template Resolution
Pipeline row, or in the runtime-execution-domain container detail.

---

## Observations (Aligned, No Action Needed)

### `CentralTemplateRepository` is Implementation-Only

The migration created a `CentralTemplateRepository` class
(`src/doctrine/templates/repository.py`) to provide API access to non-mission-
scoped central command templates. This is not mentioned in any architecture
document. This is acceptable -- it is an implementation detail of the doctrine
package, not an architectural component. If it grows in scope, consider adding
it to the Doctrine component table.

### `specify_cli/templates/` Correctly Removed

The non-mission-scoped content templates directory was correctly removed. The
only architecture reference to it is the clarify-removal ADR
(`2026-03-20-1`, line 115), which documents the removal. No stale references
remain.

### Glossary Code Correctly Retained in `specify_cli/missions/`

ADR `2026-03-25-1` (Glossary Type Ownership) documents that
`glossary_hook.py` and `primitives.py` remain in `specify_cli/missions/` due to
the lazy-import pattern needed to avoid dependency cycles. The migration
correctly preserved these files.

### `MissionTemplateRepository` Remains Deferred

Multiple documents correctly identify this as deferred work. The current
`MissionRepository` serves the immediate need. No discrepancy.

### Kernel Dependency Graph is Accurate

The architecture correctly shows `kernel` as the zero-dependency floor with
`doctrine` depending on nothing except `kernel`. The migration did not alter
this relationship.

---

## Pre-Existing Test Failures (Not Migration-Caused)

The following test failures exist on the base branch and are unrelated to the
migration:

| Test | Failure | Root Cause |
|---|---|---|
| `test_template_compliance::test_task_prompt_templates_include_branch_contract_metadata` | `planning_base_branch`, `merge_target_branch`, `branch_strategy`, `## Branch Strategy` missing from task-prompt-template.md | Doctrine content gap: task-prompt templates lack branch contract metadata |
| `test_template_compliance::test_planning_templates_use_deterministic_branch_helpers` | `branch-context --json` missing from specify.md command templates | Doctrine content gap: specify templates lack deterministic branch-context helper |
| `test_atomic_write::test_atomic_write_interrupt_preserves_original` | `specify_cli.core.atomic` has no attribute `os` | Unrelated module refactor broke mock target |
| `test_atomic_write::test_atomic_write_keyboard_interrupt_cleanup` | Same as above | Same as above |
| `test_feature_metadata::test_atomic_write_cleanup_on_failure` | Same as above | Same as above |
| `test_feature_metadata::test_cleanup_on_write_failure` | Same as above | Same as above |

---

## Recommended Follow-On Tasks

1. **Update `04_implementation_mapping/README.md`** -- fix the 3 stale claims
   identified above (discrepancies 1-3). Low effort, high alignment value.

2. **Document `expected-artifacts.yaml`** in the doctrine stack layer model.
   Consider whether it needs a JSON Schema contract.

3. **Document the 5-tier resolver chain** in the architecture. This is the
   single most important runtime behavior for asset resolution and it exists
   only in code comments today.

4. **Fix the pre-existing `test_template_compliance` failures** by adding
   branch contract metadata to doctrine task-prompt templates. This is a
   doctrine content issue, not a migration issue.

5. **Fix the pre-existing `test_atomic_write` mock failures** by updating
   the mock target to match the current `specify_cli.core.atomic` module
   structure.
