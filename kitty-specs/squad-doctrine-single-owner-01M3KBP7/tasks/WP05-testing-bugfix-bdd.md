---
work_package_id: WP05
title: Testing, bug-fixing and BDD doctrine owners (#5220)
dependencies:
- WP02
requirement_refs:
- FR-020
- FR-021
- FR-022
- FR-023
planning_base_branch: claude/squad-doctrine-single-owner-rzqpvw
merge_target_branch: claude/squad-doctrine-single-owner-rzqpvw
branch_strategy: Planning artifacts for this mission were generated on claude/squad-doctrine-single-owner-rzqpvw. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into claude/squad-doctrine-single-owner-rzqpvw unless the human explicitly redirects the landing branch.
subtasks:
- T021
- T022
- T023
- T024
- T025
- T026
phase: Phase 2 - Owners
history:
- at: '2026-09-28T09:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks (fold-in revision)
agent_profile: curator-carla
authoritative_surface: packs/built-in/procedures/
create_intent:
- packs/built-in/tactics/testing/bdd-scenario-formulation.tactic.yaml
- tests/doctrine/test_testing_doctrine_single_owner.py
execution_mode: code_change
model: sonnet
owned_files:
- packs/built-in/procedures/test-first-bug-fixing.procedure.yaml
- packs/built-in/procedures/disciplined-defect-diagnosis.procedure.yaml
- packs/built-in/procedures/bdd-scenario-lifecycle.procedure.yaml
- packs/built-in/tactics/testing/bug-fixing-checklist.tactic.yaml
- packs/built-in/tactics/testing/mutation-testing-workflow.tactic.yaml
- packs/built-in/tactics/testing/test-to-system-reconstruction.tactic.yaml
- packs/built-in/tactics/testing/tdd-red-green-refactor.tactic.yaml
- packs/built-in/tactics/testing/bdd-scenario-formulation.tactic.yaml
- packs/built-in/tactics/behavior-driven-development.tactic.yaml
- packs/built-in/tactics/architecture/development-bdd.tactic.yaml
- packs/built-in/styleguides/testing-principles.styleguide.yaml
- packs/built-in/styleguides/test-desiderata-and-boundaries.styleguide.yaml
- packs/built-in/styleguides/mutation-aware-test-design.styleguide.yaml
- packs/built-in/toolguides/GHERKIN.md
- packs/built-in/toolguides/gherkin.toolguide.yaml
- packs/built-in/toolguides/PYTHON_MUTATION_TOOLS.md
- packs/built-in/toolguides/TYPESCRIPT_MUTATION_TOOLS.md
- packs/built-in/directives/030-test-and-typecheck-quality-gate.directive.yaml
- packs/built-in/directives/034-test-first-development.directive.yaml
- packs/built-in/directives/036-black-box-integration-testing.directive.yaml
- packs/built-in/directives/use-mutation-testing-to-validate-test-quality.directive.yaml
- packs/built-in/paradigms/behaviour-driven-development.paradigm.yaml
- tests/doctrine/test_testing_doctrine_single_owner.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP05 – Testing, bug-fixing and BDD doctrine owners (#5220)

## ⚡ Do This First: Load Agent Profile

FIRST run `spec-kitty agent profile show curator-carla` (add `--all` if it reports the profile as not activated in this repo) and `spec-kitty charter context --action implement --json`. Apply the resolved initialization, boundaries, directives and tactics, then state which ones you applied.

- **Profile**: `curator-carla`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## Branch Strategy

- **Planning base branch**: `claude/squad-doctrine-single-owner-rzqpvw`
- **Merge target branch**: `claude/squad-doctrine-single-owner-rzqpvw`
- Execution worktrees are allocated per computed lane from `lanes.json`. Work only in the workspace that `spec-kitty implement WP05` resolves.

## Mission-wide rules (read before editing)

- **Charter**: `.kittify/charter/charter.md`. **Spec**: `kitty-specs/squad-doctrine-single-owner-01M3KBP7/spec.md`. **Plan**: `plan.md`. **Grounding evidence**: `research.md` R-7..R-11.
- **Epic rule (#5218)**: one owner states each rule. Every other artifact references the owner by id and does not restate it. This is not wholesale merging: directive = rule, tactic = how, styleguide = format, procedure = workflow, paradigm = worldview.
- **Delivery-risk rule**: when you trim a copy that was the only delivery path for an owner, record in the Activity Log which DRG edge WP09 must add. Content WPs do NOT edit edges, graphs or the extractor.
- **Generated files are owned by WP09 only**:
  - `packs/built-in/*.graph.yaml`
  - `packs/built-in/pack-manifest.yaml`
  - `src/charter/offering/drg/migration/{extractor,hand_authored_overlay}.py`
  - `src/charter/activation/packs/{default,minimal}.yaml`
  - `packs/built-in/missions/*/actions/*/index.yaml`
  - the DRG goldens

  In a content WP, `spec-kitty doctrine regenerate-graph --check` and the manifest-freshness tests are EXPECTED to be stale. Do not regenerate or hand-edit those files. Record the edges or activation changes WP09 must make in your Activity Log under a heading `### Handoff to WP09`.
- **Pinned ids (plan.md "Pinned successor ids")**:
  - `bdd-scenario-formulation` (tactic, `tactics/testing/`);
  - `boring-code-review` (styleguide; same id, new kind);
  - `supply-chain-install-safety` stays the ONE supply-chain tactic, made ecosystem-neutral, with its JS/TS steps moved to the `javascript-supply-chain` toolguide;
  - `tracker-backlog-iterative-deepening` (internal tactic).

  Do not invent other ids.
- **Pack prose**:
  - no `#NNNN` issue references (see `tests/architectural/_builtin_pack_provenance_baseline.yaml` and `test_builtin_pack_provenance_ratchet.py`; counts may only go down);
  - no version numbers;
  - the terminology canon applies: Mission, never Feature, and canonical `status commit`.
- **Validate every edited artifact loads**, through its repository (`from charter.offering.service import DoctrineService`) or the kind's schema tests. `procedure.schema.yaml` and most schemas are `additionalProperties: false`.
- **ATDD / red-first**: commit a failing test that pins the new doctrine shape BEFORE the content change, as its own commit.
- **Ownership map**: stay inside `owned_files`. A small out-of-map edit is allowed only with a one-line rationale in the Activity Log (no-overlap is the real guard).
- **No full heavy suites** (`NO_FULL_HEAVY_SUITES_IN_MISSION`): run targeted files and the named gate files only.
- **Commit** with `spec-kitty safe-commit <files> -m "<msg>" --to-branch <your lane branch>`. Lane branches are not protected. If safe-commit refuses, stop and report the refusal verbatim in the Activity Log; do not bypass it with raw git or `SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS`. Never commit on `main`.
- **Lane-local CLI (mandatory).** The global `spec-kitty` on PATH is an editable install of the ROOT checkout. Inside a lane worktree it reads the root's packs and code, not yours. For every doctrine or charter command in a lane (`doctrine regenerate-graph`, `charter context|generate|sync|synthesize`, `agent profile show`, upgrade/migration runs), invoke:
  `PYTHONPATH=$PWD/src SPEC_KITTY_PACKS_ROOT=$PWD/packs python -m specify_cli <args>`
  from the lane worktree root. pytest is already lane-local (`pytest.ini` sets `pythonpath = src`).
- **Handoff channel.** Handoff notes for later WPs (edges, activation, pinned tests) go in the **body of your final commit**, under a line `Handoff-to-WP09:` (or `Handoff-to-WP10:` / `Handoff-to-WP11:`), and are mirrored in your Activity Log. Downstream WPs read them with `git log --format=%B` over the merged dependency lanes.
- **Expected-red list.** Content WPs leave the generated graph and manifest stale on purpose. In your final commit body, under `Expected-red-until-WP09:`, list the exact test node ids that are red in your lane only because regeneration is deferred. Typical: `regenerate-graph --check`, `test_doctrine_regenerate_graph_roundtrip`, `test_pack_manifest_no_author_edit`, `test_shipped_graph_is_fresh_and_byte_identical`, reachability, census. Reviewers treat those as expected; WP09's reviewer verifies the whole union is green.
- **Before handoff**, run every red-first test of the WPs you depend on, so you never break a predecessor's pin.

## Objectives & Success Criteria

Resolve the 10 contradictions of #5220 so each rule has one owner (research R-9 has the evidence and line numbers, all live on `d95e60a2`).

| Rule | Owner |
|---|---|
| Reproduce via a stable entry point | 034 |
| Diagnose first; fix proportional to the cause | 052 (WP04 owns its file; reference only) |
| Refactor sequencing | 025 (WP07 owns its file) |
| Pre-existing failure classification | 030 |
| Per-test verdict | 041 |
| Beck's twelve desiderata ("Predictive", "Inspiring", "Clear test boundaries") | `test-desiderata-and-boundaries` |
| Mutation band table (one, triage bands; a CI break gate is a project opt-in) | `mutation-testing-workflow` tactic |

**Recorded decisions** (decision moments):
- **Tidy-first:** a separate behaviour-preserving commit on the surfaces the fix will touch, *before* the red repro (025 owns it). Refactor-after-green in `test-first-bug-fixing` is limited to the fix's own code.
- **Commit topology:** test and fix are committed together, unless a failing reproduction test already landed on the mainline under `red-main-release-discipline`. In that case the fix commit turns it green.
- **Mutation:** no numeric target. One band table, framed as triage bands. A CI break gate is an opt-in, with `break: 0` as the shipped default.
- **BDD tactic rename:** `behavior-driven-development` (tactic) → `bdd-scenario-formulation`, moved to `tactics/testing/`. The paradigm id `behaviour-driven-development` stays: never rename an id for spelling alone.

## Subtasks & Detailed Guidance

### T021 – Red-first owner test (own commit, RED)

`tests/doctrine/test_testing_doctrine_single_owner.py`:
- `bug-fixing-checklist` is absent and its four unique lines live in `test-first-bug-fixing`. The lines are: state expected/actual in one sentence (checklist:14); can't write the test → not understood (:19-20); record the root cause and document the fix (:31-32, :38-42); test-after-fix is only a confirmation test (:45).
- `test-first-bug-fixing` has no "refactor after" instruction before the fix, and states the commit-topology carve-out.
- The TypeScript toolguide still contains a CI break-gate example, marked as an opt-in, with `break: 0` as the default.
- Exactly one artifact contains a mutation band table. Detect a table or list pairing percentage ranges with verdict words. There is no `Target 80` and no `break: 60`.
- `testing-principles` no longer defines "Predictive", "Inspiring" or "Clear Test Boundaries" (or renames them), and references `quadruple-a-test-format`.
- The tactic id `bdd-scenario-formulation` exists under `tactics/testing/`, and `behavior-driven-development` (tactic) is absent.
- `development-bdd`'s step order puts example mapping (Discovery) before Formulation.

### T022 – Fold the checklist into `test-first-bug-fixing`, then delete it

- Carry over the four lines above.
- Add references to 034, 052, 025, `red-main-release-discipline` and `disciplined-defect-diagnosis`.
  - Procedure YAML `references` of type directive/procedure/tactic mint `requires`. Decide per reference whether `requires` is right. Advisory links (052 is `enforcement: advisory`) should be requested from WP09 as curated `suggests` edges instead; record them in the handoff.
  - The `test-first-bug-fixing` → 052 link is load-bearing (052 is not action-scoped), so it must exist in some form.
- Fix the minimal-fix wording (:40), the refactor order (:42-43) and the topology (:13-15, :50-53) per the decisions.
- Remove the checklist citation from `disciplined-defect-diagnosis` (:91-96) and soften its "minimal fix" at :66 to "proportional to the diagnosed cause".
- Also check `tdd-red-green-refactor` for the same refactor-after wording.
- The four profiles that cite the checklist belong to WP11. Record for WP11: implementer-ivan:136, node-norris:165, frontend-freddy:173, drupal-dries:204 retarget to `collaboration.operating-procedures: [test-first-bug-fixing]`.

### T023 – Terms: one owner

- `testing-principles` (lines 16, 19, 40-52): rename its colliding terms. For example, "Documenting" for the documents-the-system sense, and "One behaviour per test" for its boundary sense. Its real subject is refactor-stable test design.
- Reference `quadruple-a-test-format`, the test pyramid and over-mocking by id instead of restating them.
- Trim the inline Quad-A copy here and reference `quadruple-a-test-format` by id. Record in the handoff that the `testing-principles → quadruple-a` edge is REQUIRED; WP09's delivery test proves Quad-A still reaches implement/review.
- Retarget the "Inspiring" citation at `behavior-driven-development` (:100, now in the renamed file) and `test-to-system-reconstruction` (:70) to `test-desiderata-and-boundaries`.
- The overlay `when` at `hand_authored_overlay.py:1419-1428` is WP09's; hand it off.
- 036: make it cite the responsibility-boundary sense consistently, if needed.

### T024 – Mutation

- One band table, in `mutation-testing-workflow` (notes :59-61), framed as triage bands.
- Remove the other tables:
  - `mutation-aware-test-design:12` "Target 80%+";
  - `PYTHON_MUTATION_TOOLS.md:170-177`;
  - `TYPESCRIPT_MUTATION_TOOLS.md:196-203`;
  - the TS CI example `break: 60` at :162-176, which becomes an opt-in example with `break: 0` as the default, consistent with :38.
- Point those files to the tactic.
- The directive (`use-mutation-testing-to-validate-test-quality`, :47-57) keeps "signal, not a gate".

### T025 – BDD

- Create `tactics/testing/bdd-scenario-formulation.tactic.yaml` from `tactics/behavior-driven-development.tactic.yaml` and delete the old file.
  - Reference the `given-when-then-authoring` styleguide, the `gherkin` toolguide and the `bdd-scenario-lifecycle` procedure.
  - A tactic's YAML reference to a styleguide mints `suggests`; the spec wants `requires` for given-when-then, so hand that edge to WP09 as curated.
  - Move its toolchain notes into `GHERKIN.md` / `gherkin.toolguide.yaml`.
- `development-bdd:41-43`: follow the paradigm's order, with example mapping in Discovery first. It references `bdd-scenario-formulation` at :47.
- The paradigm `behaviour-driven-development` gains `references` to its practices: bdd-scenario-formulation, bdd-scenario-lifecycle, given-when-then-authoring and gherkin. Check the paradigm schema allows `references`; if not, hand the edges to WP09.
- `bdd-scenario-lifecycle`: reference given-when-then and gherkin.
- Record every consumer of the old id for WP09 and WP10: `default.yaml:47`, `charter.yaml:75`, the profile-edges fixture, and `grep -rn behavior-driven-development`.

### T026 – 030/034 edits

Only if needed for ownership clarity: 030 owns pre-existing-failure classification (025's side is WP07's), and 034 owns reproduction via a stable entry point. Minimal wording only.

## Test Strategy

```bash
pytest tests/doctrine/test_testing_doctrine_single_owner.py -q
pytest tests/doctrine -q -m "not slow" -k "tactic or procedure or styleguide or toolguide or directive or paradigm or mutation or bdd"
pytest tests/architectural/test_no_legacy_terminology.py -q
```

## Handoff (commit body; must record: Handoff-to-WP09 / Handoff-to-WP11 / Handoff-to-WP10)

- **Edges:**
  - `test-first-bug-fixing` → 034, 052, 025, red-main, disciplined-defect-diagnosis (with relations);
  - `testing-principles` → quadruple-a;
  - `bdd-scenario-formulation` and `bdd-scenario-lifecycle` → given-when-then (`requires`) and gherkin;
  - the BDD paradigm → its practices;
  - the overlay `when` text fix.
- **Activation:** `bug-fixing-checklist` and `behavior-driven-development` in `default.yaml` / `minimal.yaml`; add `bdd-scenario-formulation`.
- **Tests pinning the ids:**
  - `tests/doctrine/drg/test_drupal_dries_lineage.py:45`
  - `tests/doctrine/agent_profiles/test_context_sources_migration.py:83`
  - `tests/doctrine/agent_profiles/fixtures/agent_profile_edges_before_consolidation.json:259,359,579`
  - `tests/specify_cli/upgrade/test_normalize_activation_absence.py:118,126`
- **Docs:** `docs/api/agent_profiles/implementer-ivan.md:36` (WP10).

## Activity Log

- 2026-09-28T09:00:00Z – system – Prompt created (fold-in revision).
