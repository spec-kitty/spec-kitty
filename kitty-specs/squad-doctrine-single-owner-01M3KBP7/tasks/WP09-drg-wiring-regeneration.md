---
work_package_id: WP09
title: DRG wiring, activation packs and regeneration (single owner of generated surfaces)
dependencies:
- WP01
- WP04
- WP05
- WP06
- WP07
- WP08
- WP11
requirement_refs:
- FR-005
- FR-006
- FR-008
- FR-012
- FR-014
- FR-021
- FR-023
planning_base_branch: claude/squad-doctrine-single-owner-rzqpvw
merge_target_branch: claude/squad-doctrine-single-owner-rzqpvw
branch_strategy: Planning artifacts for this mission were generated on claude/squad-doctrine-single-owner-rzqpvw. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into claude/squad-doctrine-single-owner-rzqpvw unless the human explicitly redirects the landing branch.
subtasks:
- T044
- T045
- T046
- T047
- T048
- T049
- T050
phase: Phase 3 - Wiring
history:
- at: '2026-09-28T09:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks (fold-in revision)
agent_profile: curator-carla
authoritative_surface: src/charter/offering/drg/
create_intent:
- tests/doctrine/test_owner_delivery.py
- tests/doctrine/drg/test_single_owner_edges.py
- tests/doctrine/test_retirement_table_consistency.py
- tests/doctrine/test_retired_ids_absent.py
execution_mode: code_change
model: opus
owned_files:
- src/charter/offering/drg/migration/extractor.py
- src/charter/offering/drg/migration/hand_authored_overlay.py
- src/charter/offering/drg/models.py
- docs/architecture/doctrine-relationships.md
- packs/built-in/*.graph.yaml
- packs/built-in/pack-manifest.yaml
- packs/built-in/missions/*/actions/*/index.yaml
- src/charter/activation/packs/default.yaml
- src/charter/activation/packs/minimal.yaml
- packs/built-in/directives/001-architectural-integrity-standard.directive.yaml
- tests/doctrine/drg/**
- tests/doctrine/test_paula_patterns_artifacts.py
- tests/doctrine/agent_profiles/test_context_sources_migration.py
- tests/doctrine/agent_profiles/fixtures/agent_profile_edges_before_consolidation.json
- tests/charter/test_profile_channel_delivery.py
- tests/charter/test_context.py
- tests/doctrine/test_acceptance_criteria_non_vacuity_wiring.py
- tests/specify_cli/test_documentation_drg_nodes.py
- tests/specify_cli/upgrade/test_normalize_activation_absence.py
- tests/doctrine/test_owner_delivery.py
- tests/doctrine/test_retirement_table_consistency.py
- tests/doctrine/test_retired_ids_absent.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP09 – DRG wiring, activation packs and regeneration (single owner of generated surfaces)

## ⚡ Do This First: Load Agent Profile

FIRST run `spec-kitty agent profile show curator-carla` (add `--all` if it reports the profile as not activated in this repo) and `spec-kitty charter context --action implement --json`. Apply the resolved initialization, boundaries, directives and tactics, then state which ones you applied.

- **Profile**: `curator-carla`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## Branch Strategy

- **Planning base branch**: `claude/squad-doctrine-single-owner-rzqpvw`
- **Merge target branch**: `claude/squad-doctrine-single-owner-rzqpvw`
- Execution worktrees are allocated per computed lane from `lanes.json`. Work only in the workspace that `spec-kitty implement WP09` resolves.

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

WP09 is the **single owner of every generated and wiring surface**. Collect every `Handoff-to-WP09:` block from the commit bodies of the merged dependency lanes (`git log --format=%B <merge-base>..HEAD`), cross-checked against the WP04–WP08/WP11 prompt files in `kitty-specs/squad-doctrine-single-owner-01M3KBP7/tasks/`, and implement them. Also verify that the union of every `Expected-red-until-WP09:` list is green at your head. Non-default relations are authored as curated `_CURATED_ARTIFACT_EDGES` entries (research R-2):
- a procedure's YAML `references` of type tactic/procedure mints `requires`;
- a tactic's YAML `references` mints `suggests`;
- `refines` has no YAML path.

**Known required edges** (verify against the handoffs):
- **#5219:**
  - REMOVE procedure → five-paradigm `requires`; WP04 removed the YAML entry, so confirm it is gone.
  - ADD procedure → `model-task-routing` `suggests`.
  - ADD `mission-tracer-files` → procedure `suggests`.
  - DIRECTIVE_052's curated edge: its styleguide target becomes `procedure:adversarial-squad-deployment`.
  - ADD `five-paradigm-parallel-debugging` → procedure `refines` and `paula-patterns-architecture-scout-review` → procedure `refines`.
  - FR-014, conditional: DIRECTIVE_001 → paula-scout becomes `suggests` ONLY if no reachability set loses an artifact. Note that `strategic-domain-classification` is reached via that tactic (`test_reachability.py` ~168). Otherwise keep `requires` and record why. `tests/doctrine/test_paula_patterns_artifacts.py:62-66` pins it.
- **#5220:**
  - `test-first-bug-fixing` → 034, 052 (`suggests`, load-bearing), 025, red-main and disciplined-defect-diagnosis;
  - `testing-principles` → `quadruple-a-test-format` (REQUIRED for delivery);
  - `bdd-scenario-formulation` and `bdd-scenario-lifecycle` → given-when-then (`requires`) and gherkin;
  - the BDD paradigm → its practices;
  - the overlay `when` at `hand_authored_overlay.py:1419-1428`;
  - the `tactic.graph.yaml` `when` text at the old :523/:1293 (it comes from the artifact YAML the content WPs changed; confirm after regeneration).
- **#5221:**
  - the reconciler / 052 `reconciles_tension` edge, if WP07 requested it;
  - the edges for the neutral supply-chain tactic and toolguides;
  - rewire the review action and step contract for the review-tactic layering;
  - `boring-code-review` as a styleguide in the action scope (`action.graph.yaml` via the action `index.yaml` files).
- **REFINES wording:** `models.py` `RELATION_DESCRIPTIONS[Relation.REFINES]` says "zero edges exist in the built-in graph today". Update it, and keep `docs/architecture/doctrine-relationships.md` word-for-word in sync (`tests/doctrine/test_relation_doc_parity.py`). Bump its `updated:` date.
- **Overlay comment** `hand_authored_overlay.py:~1294` must not name the deleted styleguide.
- **Activation packs** (`default.yaml`, `minimal.yaml`):
  - remove the retired ids (bug-fixing-checklist, locality-of-change tactic, common-docs-curation, behavior-driven-development tactic, iterative-deepening-review, tracker-organisation-workflow, boring-code-review from tactics);
  - add the successors (`bdd-scenario-formulation`, the boring-code-review styleguide, new supply-chain tactic/toolguides);
  - keep them consistent with WP01's migration table.

**Regenerate**: `spec-kitty doctrine regenerate-graph`, then `--check` must exit 0. Never hand-edit the generated files.

**Goldens and ledgers**:
- `tests/doctrine/drg/migration/test_extractor_projection.py`: add a numbered ledger entry for this mission's node and edge delta, and update entry (22).
- `tests/doctrine/drg/test_reachability.py`: remove the deleted ids; the pinned sets change for the quadruple-a edge (:354, :377, :467).
- Update the other pinned tests in `owned_files`.
- Every change carries a ledger note.

**Retirement-table consistency (SC-008)**: `tests/doctrine/test_retirement_table_consistency.py` imports WP01's `RETIREMENTS` and asserts:
- every retired stem is not resolvable in built-in doctrine;
- every successor is resolvable and activated in `default.yaml` where the retired id was;
- a fixture project activating every retired id compiles through `charter.activation.compiler` after the migration's `apply`.

**Retired-id grep (SC-002)**: `tests/doctrine/test_retired_ids_absent.py`.
- `src/` and `packs/` text files name no retired id, except under an allowlist: the migration module, and `packs/internal` for the moved ids.
- Positive control: at least one hit on the base commit, via `git show <base>:<path>` of a known file.

**Delivery test (SC-007)**: `tests/doctrine/test_owner_delivery.py`. This is a regression guard, NOT red-first.
- For each epic owner (quadruple-a-test-format, DIRECTIVE_025, DIRECTIVE_030, DIRECTIVE_034, DIRECTIVE_037, DIRECTIVE_051, DIRECTIVE_052, procedure adversarial-squad-deployment), assert it is resolved in the `implement` and `review` action context: the DRG resolution used by `charter context --action`, with the shipped default activation.
- Capture the BASE owner×action set ONCE, on a `git worktree add` of the planning base commit (`git merge-base HEAD origin/main`). Paste it as **hard-coded literals** in the test, with the command and output in the Activity Log. Never derive it from goldens this WP edits.
- Assert HEAD ⊇ BASE literal.
- The only permitted additions or exceptions, listed explicitly:
  - DIRECTIVE_052 must be delivered at `implement` via `test-first-bug-fixing` even if BASE lacked it;
  - the disposition contract is delivered as part of the squad procedure.

## Subtasks

### T044 – Red-first edge test `tests/doctrine/drg/test_single_owner_edges.py` and delivery test (own commit, RED)

### T045 – Curated edges, overlay fixes, FR-014 conditional

### T046 – REFINES wording and doc parity

### T047 – Activation packs and action indexes

### T048 – Regenerate, then run the gates

### T049 – Ledgers, reachability and pinned-test updates

### T050 – Cascade totals and census counts (grep tests for pinned cascade totals; update with rationale)

## Test Strategy

```bash
spec-kitty doctrine regenerate-graph && spec-kitty doctrine regenerate-graph --check
pytest tests/doctrine/drg -q
pytest tests/doctrine -q -m "not slow"
pytest tests/charter -q -m "not slow"
pytest tests/specify_cli/test_documentation_drg_nodes.py tests/specify_cli/upgrade/test_normalize_activation_absence.py -q
# named gates (locate each with find tests -name ...):
#   test_doctrine_regenerate_graph_roundtrip.py test_pack_manifest_no_author_edit.py test_builtin_pack_provenance_ratchet.py
#   test_operating_procedures_resolve.py test_doctrine_census.py test_relation_doc_parity.py test_directive_consistency.py
pytest tests/cross_cutting/packaging/test_packaging_safety.py tests/architectural/test_no_legacy_terminology.py -q
ruff check src/charter/offering/drg && ruff format --check src/charter/offering/drg && mypy src/charter/offering/drg
```

## Review Guidance

- `regenerate-graph --check` is clean.
- Every golden move has a ledger note.
- The delivery test proves HEAD ⊇ BASE.
- The FR-014 decision is evidenced.

## Activity Log

- 2026-09-28T09:00:00Z – system – Prompt created (fold-in revision).
