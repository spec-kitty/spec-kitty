---
work_package_id: WP06
title: Common Docs doctrine owners (#5221 A)
dependencies:
- WP02
requirement_refs:
- FR-024
planning_base_branch: claude/squad-doctrine-single-owner-rzqpvw
merge_target_branch: claude/squad-doctrine-single-owner-rzqpvw
branch_strategy: Planning artifacts for this mission were generated on claude/squad-doctrine-single-owner-rzqpvw. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into claude/squad-doctrine-single-owner-rzqpvw unless the human explicitly redirects the landing branch.
subtasks:
- T027
- T028
- T029
- T030
- T031
phase: Phase 2 - Owners
history:
- at: '2026-09-28T09:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks (fold-in revision)
agent_profile: curator-carla
authoritative_surface: packs/built-in/styleguides/
create_intent:
- packs/built-in/assets/docs_structural_lint.config.yaml
- tests/doctrine/test_common_docs_single_owner.py
execution_mode: code_change
model: sonnet
owned_files:
- packs/built-in/directives/037-living-documentation-sync.directive.yaml
- packs/built-in/directives/042-common-docs.directive.yaml
- packs/built-in/styleguides/common-docs.styleguide.yaml
- packs/built-in/styleguides/docs-freshness-sla.styleguide.yaml
- packs/built-in/styleguides/publication-authority.styleguide.yaml
- packs/built-in/tactics/common-docs-curation.tactic.yaml
- packs/built-in/tactics/common-docs-scaffold.tactic.yaml
- packs/built-in/tactics/common-docs-write.tactic.yaml
- packs/built-in/tactics/common-docs-find.tactic.yaml
- packs/built-in/assets/docs_structural_lint.py
- packs/built-in/assets/docs_structural_lint.py.asset.yaml
- packs/built-in/assets/docs_structural_lint.config.yaml
- packs/internal/styleguides/spec-kitty-docs-lint-config.styleguide.yaml
- packs/built-in/missions/documentation/governance-profile.yaml
- packs/built-in/missions/mission-steps/documentation/publish/guidelines.md
- packs/built-in/missions/mission-steps/documentation/publish/prompt.md
- packs/built-in/missions/mission-steps/documentation/validate/guidelines.md
- packs/built-in/missions/mission-steps/documentation/validate/prompt.md
- tests/docs/test_docs_structural_lint.py
- tests/docs/test_touched_set_gates.py
- tests/docs/test_doc_status_durable.py
- tests/doctrine/styleguides/test_models.py
- tests/doctrine/test_common_docs_single_owner.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP06 – Common Docs doctrine owners (#5221 A)

## ⚡ Do This First: Load Agent Profile

FIRST run `spec-kitty agent profile show curator-carla` (add `--all` if it reports the profile as not activated in this repo) and `spec-kitty charter context --action implement --json`. Apply the resolved initialization, boundaries, directives and tactics, then state which ones you applied.

- **Profile**: `curator-carla`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## Branch Strategy

- **Planning base branch**: `claude/squad-doctrine-single-owner-rzqpvw`
- **Merge target branch**: `claude/squad-doctrine-single-owner-rzqpvw`
- Execution worktrees are allocated per computed lane from `lanes.json`. Work only in the workspace that `spec-kitty implement WP06` resolves.

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

All items are from #5221 section A. Research R-10 has the evidence.

- **A1:** ADRs use MADR `status`, never `doc_status`. Fix `common-docs-curation.tactic.yaml:33-44` (which is being folded anyway) and `common-docs-scaffold.tactic.yaml:47`. 042 (:30-34, :56-59) is the owner.
- **A2:** state the section count once, in the styleguide's own list. Remove the hard-coded "13" from:
  - 042;
  - `missions/documentation/governance-profile.yaml`;
  - the scaffold tactic.

  The `tactic.graph.yaml` label is regenerated by WP09. Also:
  - the curation tactic's 12-section list goes with the fold;
  - make the built-in routing (`common-docs.styleguide.yaml:140-146`) target only sections that are in its own list;
  - make the prose at `:113` match the allowlists the config actually holds (`:160-162`).
- **A3:** the lint's `doc_status: point_in_time` / `closeout` markers (`:154-158`) sit outside 042's five values. Either declare them as lint-asset-owned marker values, clearly separate from the five `doc_status` values, or map them onto the five. Tests pin the current values: `tests/docs/test_docs_structural_lint.py`, `test_touched_set_gates.py`, `test_doc_status_durable.py` and `tests/doctrine/styleguides/test_models.py`. Choose the least disruptive option consistent with 042 and record it.
- **A4:** DIRECTIVE_037 owns "docs in the same change as behaviour". Replace the other statements with references to 037 at their natural granularity:
  - 042:50;
  - styleguide :16;
  - docs-freshness-sla :10;
  - publication-authority :9, :19, :70 (publication-authority:9's "same commit or the same mission" conflicts);
  - documentation publish guidelines :37 and prompt :52 ("same change set or queued", now only the `mission-steps` copy after WP02).
- **A5:** move the lint config out of the styleguide YAML into `packs/built-in/assets/docs_structural_lint.config.yaml`, owned by the lint asset.
  - `assets/docs_structural_lint.py:95-97` pins the wrapper key `structural_lint_config`. Keep that key inside the data file so the loader contract is unchanged.
  - The internal override `packs/internal/styleguides/spec-kitty-docs-lint-config.styleguide.yaml` keeps working through the same key.
  - Update `docs_structural_lint.py.asset.yaml` to declare the data file.
- **Fold `common-docs-curation`** into scaffold, write and find: move each unique step to the natural owner, then delete the tactic. Record the consumers for WP09 and WP10:
  - `.kittify/charter/charter.yaml:168`
  - `tests/specify_cli/test_documentation_drg_nodes.py`
  - `tests/doctrine/drg/test_reachability.py`
  - the provenance baseline
- **Documentation validate vocabulary:** accept / mitigate / block-publish (validate guidelines :31, :63; prompt :55). Map it onto the squad procedure's disposition contract (FR-027, WP04): state the mapping and cite `adversarial-squad-deployment`.

## Subtasks

### T027 – Red-first test (own commit, RED)

`tests/doctrine/test_common_docs_single_owner.py`:
- no ADR `doc_status` guidance;
- "13" appears nowhere as a hard-coded section count outside the styleguide list;
- the same-change rule is stated in full only in 037, and the others reference `DIRECTIVE_037`;
- the curation tactic is absent AND each of its unique steps is present in scaffold, write or find (positive assertions, one per carried step);
- the section count is not restated as a number or number word ("13", "thirteen") outside the styleguide list;
- A2: every built-in routing target is a section in the styleguide's own list;
- A3: every lint marker value is either one of 042's five `doc_status` values or declared in the lint asset's data file;
- the validate guidelines/prompt state the accept/mitigate/block-publish → disposition-contract mapping and cite `adversarial-squad-deployment`;
- the lint config data file exists and loads through the asset's loader.

### T028 – A1 and A2 edits

### T029 – A3 and A5 (data file, asset loader, tests/docs updates)

### T030 – A4 (the same-change rule owner) and the validate vocabulary mapping

### T031 – Curation fold and delete, plus the handoff

## Test Strategy

```bash
pytest tests/doctrine/test_common_docs_single_owner.py tests/docs -q
pytest tests/doctrine -q -m "not slow" -k "common_docs or styleguide or asset or documentation"
pytest tests/specify_cli/test_documentation_drg_nodes.py -q   # expected to need WP09 regen; record
```

## Handoff (commit body; must record: Handoff-to-WP09 / Handoff-to-WP10)

Edge and label changes, the retired id's consumers, and the `.kittify` charter entries.

## Activity Log

- 2026-09-28T09:00:00Z – system – Prompt created (fold-in revision).
