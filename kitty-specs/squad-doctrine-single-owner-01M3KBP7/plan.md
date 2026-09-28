# Implementation Plan: Squad doctrine: single owner and profile-per-task rule

**Branch**: `claude/squad-doctrine-single-owner-rzqpvw` | **Date**: 2026-09-28 | **Spec**: [spec.md](spec.md)
**Input**: Mission specification from `kitty-specs/squad-doctrine-single-owner-01M3KBP7/spec.md` (GitHub #5219, #5220, #5221 / epic #5218, #5202, #5078; fold-in 2026-09-28)

## Summary

The procedure `adversarial-squad-deployment` becomes the single owner of squad doctrine. It gains:
- the profile-per-task rule;
- one point-cut list, with pre-spec *before* `/spec-kitty.specify`;
- an example casting table with a fixed line grammar that a test can parse;
- the unique content folded in from the styleguide.

Model-tier choice moves to `model-task-routing`.

The styleguide `adversarial-squad-cadence` is deleted and its four inbound edges are repointed or removed. A new upgrade migration strips the retired id from consumer projects. It is built on a helper extracted from the existing rtk-retirement migration. The harness skill shrinks to a pointer.

The fixed-lens specialisations reference the procedure and `refines` it, and the Debbie/Paula profiles gain a `squad-delegate` mode. The glossary term moves to the built-in pack.

## Technical Context

**Language/Version**: Python 3.11+ (migration helper, extractor curated edges, tests); YAML doctrine artifacts; Markdown skill.
**Primary Dependencies**: ruamel.yaml (round-trip migration I/O), pydantic doctrine models, the DRG extractor and calibrator (`spec-kitty doctrine regenerate-graph`).
**Storage**: Files only: pack YAML, generated `*.graph.yaml` and `pack-manifest.yaml`, and project `.kittify/` YAML.
**Testing**: pytest. Targeted doctrine/DRG/charter tests, the migration tests and the specific architectural gate files. No full `tests/architectural/` sweep (`NO_FULL_HEAVY_SUITES_IN_MISSION`).
**Target Platform**: The CLI (all platforms). Doctrine ships to consumers in the wheel.
**Project Type**: Single project.
**Performance Goals**: N/A. The migration is O(project files) and runs once per upgrade.
**Constraints**:
- Regenerate `pack-manifest.yaml` and graph fragments; never hand-edit them.
- The provenance ratchet may only go down, and pack prose carries no `#NNNN` issue references.
- Complexity ≤ 15, and `ruff`/`mypy` stay clean.
**Scale/Scope**: About 12 doctrine artifacts, one skill, two migration modules, one extractor tuple and about 8 test files.

## Charter Check

| Charter rule | Status |
|---|---|
| Single canonical authority (DIRECTIVE_044) | This is the mission's goal. One owner, and everything else references it by id plus an edge. |
| Squad optional, never a gate (Standing Order #1, C-001) | Preserved. No gate is added. The tracer → procedure edge stays `suggests`. |
| Pack tiers | The glossary term moves *into* built-in because the concept ships to consumers. The internal pack loses its duplicate. |
| Canonical sources | Graph fragments and the manifest come from `regenerate-graph`. The repo charter is updated through its source and the charter CLI. |
| ATDD / red-first | Each work package opens with a failing test that pins the new doctrine shape (owner rule, casting grammar, migration behaviour, edges). |
| No full heavy suites in mission | Only the named gate files run locally. |
| Consumer-safety (User Customization Preservation) | The migration only removes an exact, package-owned id. It never creates files and skips malformed YAML. |

No violations, so no complexity tracking is needed.

## Project Structure

### Documentation (this mission)

```
kitty-specs/squad-doctrine-single-owner-01M3KBP7/
├── spec.md
├── plan.md
├── research.md
├── traces/ (tooling-friction.md, approach.md, design-decisions.md)
└── tasks.md + tasks/WP*.md  (/spec-kitty.tasks)
```

### Source Code (repository root)

```
packs/built-in/procedures/adversarial-squad-deployment.procedure.yaml   # the owner
packs/built-in/styleguides/adversarial-squad-cadence.styleguide.yaml    # DELETED
packs/built-in/directives/{040,043,052}-*.directive.yaml
packs/built-in/procedures/mission-tracer-files.procedure.yaml
packs/built-in/paradigms/brownfield-onboarding.paradigm.yaml
packs/built-in/tactics/five-paradigm-parallel-debugging.tactic.yaml
packs/built-in/tactics/architecture/paula-patterns-architecture-scout-review.tactic.yaml
packs/built-in/tactics/testing/acceptance-criteria-non-vacuity.tactic.yaml  # comment only
packs/built-in/agent_profiles/{debugger-debbie,paula-patterns}.agent.yaml
packs/built-in/glossary_packs/spec-kitty-core.glossary-pack.yaml
packs/internal/glossary_packs/spk-internal.glossary-pack.yaml
packs/built-in/*.graph.yaml, packs/built-in/pack-manifest.yaml           # REGENERATED
src/charter/offering/skills/adversarial-squad/SKILL.md
src/charter/offering/drg/migration/extractor.py                          # _CURATED_ARTIFACT_EDGES
src/charter/offering/drg/migration/hand_authored_overlay.py              # comment
src/charter/offering/drg/models.py + docs/architecture/doctrine-relationships.md  # REFINES wording
src/specify_cli/upgrade/migrations/_retired_activation.py                # NEW shared helper
src/specify_cli/upgrade/migrations/m_3_2_6_retire_rtk_search_tooling.py  # thin, uses helper
src/specify_cli/upgrade/migrations/m_4_0_0rc5_retire_adversarial_squad_cadence.py  # NEW
.kittify/charter/**                                                      # this repo, via migration + charter CLI
docs/development/reference/quality-and-tech-debt-standing-orders.md, docs/development/agent-fleet.md
```

**Structure Decision**: No new modules beyond the migration helper, which follows the existing `_merge_driver_seeding.py` precedent for shared migration helpers.

## Fold-in addendum (2026-09-28)

The operator folded all of epic #5218 plus #5202 and #5078 into this mission: one mission, one PR. The concerns below replace the #5219-only map. Grounding came from a four-lens squad on `d95e60a2`; findings are summarised in `research.md` R-7..R-11.

**Generated-file ownership.** `pack-manifest.yaml` hashes every pack artifact, and `*.graph.yaml` are regenerated by the extractor. So exactly **one** concern (IC-10) owns:
- every generated file;
- the extractor, the overlay and `models.py`;
- the activation packs (`default.yaml`, `minimal.yaml`) and the action `index.yaml` wiring;
- every DRG golden.

Content concerns change artifact YAML and prose only. They are validated by schema-load and owner tests. The graph-freshness and manifest gates turn green once IC-10 regenerates. The operator decision on guidelines means `pack-manifest.yaml` does not hash `guidelines.md` / `prompt.md`, so IC-02 and IC-03 never touch generated files.

**Delivery-risk rule (#5218).** IC-10 adds a delivery test: for each epic owner (Quad-A, 025, 030, 034, 037, 051, 052, the squad procedure, the disposition contract), the `implement` and `review` context resolves it at head wherever it did at base.

## Implementation Concern Map

### IC-01 — Consumer retirement migration (shared, data-driven)
- **Purpose**: one migration handles every id retired, renamed, moved or changed in kind by this mission, and activates the successor where one exists. It is built on `_retired_activation.py`, extracted from the rtk migration without changing behaviour.
- **Requirements**: FR-009, SC-008, NFR-003. **Surfaces**: `src/specify_cli/upgrade/migrations/`, the migration tests, the dead-module and charter path-literal allowlists. **Depends**: none.
- **Risks**:
  - Directive `024-locality-of-change` shares a slug with the tactic. The migration matches by kind key.
  - Successors for a kind change (a tactic becoming a styleguide).
  - Moved-to-internal ids have no consumer successor.

### IC-02 — Guidelines single owner (#5202, P0)
- **Purpose**:
  - Make `mission-steps/` the served owner and repoint the loader.
  - Merge the correct halves of the four software-dev files and delete every `actions/*/guidelines.md`.
  - Replace the byte-identity guard with an absence guard and a loader-path test.
  - Correct the implementation-mapping docs.
- **Requirements**: FR-016, FR-017, SC-005. **Depends**: none. Lands first in the content sequence.

### IC-03 — Printed commit recipes (#5078 code)
- **Purpose**: every CLI-printed commit recipe becomes a safe-commit recipe with `--to-branch`, and the protected-primary case gets explicit guidance.
- **Requirements**: FR-018, SC-006. **Surfaces**: `workflow_executor.py`, `implement.py`, `tasks_parsing_validation.py`, `charter/_synthesis.py`, `mission_setup_plan.py`, and their tests. **Depends**: none.

### IC-04 — Squad single owner (#5219 content)
- **Purpose**:
  - The procedure owns the playbook and the casting examples, and now also hosts the disposition contract (FR-027).
  - The skill shrinks to a pointer and the styleguide is deleted.
  - Tracer-files, brownfield, DIRECTIVE_040/043/052, the two fixed-lens tactics and the Debbie/Paula profiles are all updated.
  - The lens guard and owner tests are added.
- **Requirements**: FR-001..FR-008, FR-011..FR-013, FR-027. **Depends**: IC-02.

### IC-05 — Testing, bug-fixing and BDD (#5220 content)
- **Purpose**:
  - Fold `bug-fixing-checklist` into `test-first-bug-fixing`, using the recorded decisions for sequencing and topology.
  - Terms get one owner.
  - One mutation band table.
  - BDD phase order, and the rename to `bdd-scenario-formulation`.
  - Gherkin toolguide notes.
- **Requirements**: FR-020..FR-023. **Depends**: IC-02.
- **Risks**: the profile retargets live in IC-08, and the edges live in IC-10.

### IC-06 — Common Docs (#5221 A)
- **Purpose**:
  - ADRs use MADR `status`.
  - The section count and the same-change rule each get one owner (037).
  - The lint config becomes a data file.
  - `common-docs-curation` is folded and retired.
  - Documentation publish/validate wording is corrected.
- **Requirements**: FR-024. **Depends**: IC-02.

### IC-07 — Change scope and review tactics (#5221 B, D; #5220 item 8)
- **Purpose**:
  - The reconciler names 052, and gains the carve-out and the tie-break.
  - The locality tactic folds into `avoid-gold-plating`.
  - DIRECTIVE_025 gets its pre-existing-failure scope.
  - Review tactics are layered.
  - `boring-code-review` becomes a styleguide.
  - `iterative-deepening-review` and `tracker-organisation-workflow` move to `packs/internal`.
- **Requirements**: FR-023 (item 8), FR-025, FR-028. **Depends**: IC-02.

### IC-08 — Supply chain, served prompts, step contracts and profiles (#5221 C/E, #5078 prompt)
- **Purpose**:
  - DIRECTIVE_051 states its pillars once, with an ecosystem-neutral tactic and per-ecosystem toolguides.
  - Prompts, guidelines and step contracts reference by id.
  - Directive citations become `DIRECTIVE_NNN`.
  - The implement prompt gets the PR-ownership change.
  - Every touched profile is updated, including the checklist → procedure retargets.
- **Requirements**: FR-019, FR-020 (profiles), FR-026, FR-028 (E). **Depends**: IC-02, IC-05.

### IC-10 — DRG wiring and regeneration (single owner of generated surfaces)
- **Purpose**:
  - Curated edges, overlay `when` fixes, and the REFINES wording.
  - Activation packs and action indexes.
  - Regenerate the graph and manifest.
  - Update every golden and pinned set.
  - Add the delivery test.
- **Requirements**: FR-005, FR-006, FR-008, FR-012, FR-014, FR-021 (edge), NFR-001, NFR-002, NFR-004, SC-004, SC-007. **Depends**: IC-04..IC-08.

### IC-11 — Dogfood, docs and glossary
- **Purpose**:
  - Run the migration on this repo and regenerate `.kittify` through the charter CLI.
  - Update the charter prose, the standing-orders and agent-fleet docs, and the `docs/api` profile page.
  - Glossary: the squad term moves to built-in, and a behaviour/behavior alias is added.
- **Requirements**: FR-010, FR-015, FR-023 (alias). **Depends**: IC-01, IC-10.

## Pinned successor ids (post-tasks squad, 2026-09-28)

Fixed at plan time so that WP01's migration table, WP09's activation packs and the content WPs agree:

| Retired / changed | Successor |
|---|---|
| styleguide `adversarial-squad-cadence` | none (procedure `adversarial-squad-deployment` owns it) |
| tactic `bug-fixing-checklist` | procedure `test-first-bug-fixing` |
| tactic `locality-of-change` | tactic `avoid-gold-plating` |
| tactic `common-docs-curation` | tactics `common-docs-scaffold`, `common-docs-write`, `common-docs-find` |
| tactic `boring-code-review` | styleguide `boring-code-review` (same id, new kind) |
| tactic `behavior-driven-development` | tactic `bdd-scenario-formulation` (`tactics/testing/`) |
| tactic `iterative-deepening-review` | internal tactic `tracker-backlog-iterative-deepening` (no consumer successor) |
| procedure `tracker-organisation-workflow` | internal procedure, same id (no consumer successor) |
| tactic `supply-chain-install-safety` | same id, made ecosystem-neutral; JS/TS specifics move to toolguide `javascript-supply-chain` |

**Execution mechanics:**
- **Lanes:** one lane per WP (dependency edges never collapse lanes). `implement` waits until every dependency is approved, then merges the dependency lane tips into the new workspace.
- **Lane-local CLI:** `PYTHONPATH=$PWD/src SPEC_KITTY_PACKS_ROOT=$PWD/packs python -m specify_cli …`.
- **Handoffs:** handoff notes and the expected-red list travel in commit bodies.
- **Models:** WP09 runs on opus.
