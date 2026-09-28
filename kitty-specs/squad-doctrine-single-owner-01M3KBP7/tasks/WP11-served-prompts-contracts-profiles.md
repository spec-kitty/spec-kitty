---
work_package_id: WP11
title: 'Served prompts, step contracts and profiles reference the owners (#5221 C/E, #5078 prompt, #5220 profiles)'
dependencies:
- WP02
- WP04
- WP05
- WP08
requirement_refs:
- FR-019
- FR-020
- FR-026
- FR-027
- FR-028
planning_base_branch: claude/squad-doctrine-single-owner-rzqpvw
merge_target_branch: claude/squad-doctrine-single-owner-rzqpvw
branch_strategy: Planning artifacts for this mission were generated on claude/squad-doctrine-single-owner-rzqpvw. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into claude/squad-doctrine-single-owner-rzqpvw unless the human explicitly redirects the landing branch.
subtasks:
- T055
- T056
- T057
- T058
- T059
phase: Phase 2 - Owners
history:
- at: '2026-09-28T09:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks (fold-in revision)
agent_profile: curator-carla
authoritative_surface: packs/built-in/missions/mission-steps/software-dev/
create_intent:
- tests/doctrine/test_served_prompts_single_owner.py
execution_mode: code_change
model: sonnet
owned_files:
- packs/built-in/missions/mission-steps/software-dev/*/prompt.md
- packs/built-in/missions/mission-steps/software-dev/*/step.yaml
- packs/built-in/missions/built_in_step_contracts/*.step-contract.yaml
- packs/built-in/agent_profiles/implementer-ivan.agent.yaml
- packs/built-in/agent_profiles/node-norris.agent.yaml
- packs/built-in/agent_profiles/frontend-freddy.agent.yaml
- packs/built-in/agent_profiles/drupal-dries.agent.yaml
- packs/built-in/agent_profiles/reviewer-renata.agent.yaml
- packs/built-in/agent_profiles/python-pedro.agent.yaml
- packs/built-in/agent_profiles/java-jenny.agent.yaml
- packs/built-in/agent_profiles/architect-alphonso.agent.yaml
- tests/doctrine/agent_profiles/test_supply_chain_profile_bindings.py
- tests/doctrine/test_served_prompts_single_owner.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP11 – Served prompts, step contracts and profiles reference the owners (#5221 C/E, #5078 prompt, #5220 profiles)

## ⚡ Do This First: Load Agent Profile

FIRST run `spec-kitty agent profile show curator-carla` (add `--all` if it reports the profile as not activated in this repo) and `spec-kitty charter context --action implement --json`. Apply the resolved initialization, boundaries, directives and tactics, then state which ones you applied.

- **Profile**: `curator-carla`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## Branch Strategy

- **Planning base branch**: `claude/squad-doctrine-single-owner-rzqpvw`
- **Merge target branch**: `claude/squad-doctrine-single-owner-rzqpvw`
- Execution worktrees are allocated per computed lane from `lanes.json`. Work only in the workspace that `spec-kitty implement WP11` resolves.

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

This WP makes the served surfaces reference the owners created in WP04 (squad and disposition contract), WP05 (`test-first-bug-fixing`) and WP08 (supply chain). Research R-8, R-9 and R-10 have the evidence.

- **Supply-chain copies → references.** These surfaces currently restate the pillars or steps: the 3 software-dev prompts (implement :161-169, plan :264-268, review), the 3 served guideline files (WP02-owned: an **out-of-map** edit, so record the rationale), the 3 step contracts and the 8 profiles.
  - Replace each restatement with a reference to `DIRECTIVE_051` plus the `supply-chain-install-safety` tactic and the ecosystem toolguide.
  - Close the gaps: IoC is missing in the implement and plan prompts, and lockfile checks were split across copies.
  - **Keep** WP02's pinned supply-chain heading and the `DIRECTIVE_051` mention in the three guideline files, and run `tests/doctrine/missions/test_guidelines_single_owner.py`.
- **Disposition contract (FR-027).** Every citer of `contracts/adversarial-evidence-contract.md` now cites `adversarial-squad-deployment`:
  - the plan and review prompts and guidelines;
  - reviewer-renata :70, :169;
  - the step contracts.

  Update `tests/doctrine/agent_profiles/test_supply_chain_profile_bindings.py:13-41`.
- **E: slug citations.** Step contracts under `missions/built_in_step_contracts/` cite directives by slug (`024-locality-of-change`); there are 64 citations. Convert them to `DIRECTIVE_NNN`.
  - Resolution by URN is confirmed to work (`executor.py:663`, a direct URN lookup; verify).
  - Add a test that each citation resolves.
- **#5078 prompt.** In `mission-steps/software-dev/implement/prompt.md:329-335`, the WP agent pushes its branch and reports to the orchestrator. The orchestrator opens the draft PR and records the CI run ID in `workflow-evidence.md`, consistent with `mission-wrap-up-sequence` and DIRECTIVE_045. Every commit instruction in the served prompts uses `spec-kitty safe-commit <files> -m … --to-branch <branch>`; check implement `prompt.md:323`.
- **#5220 profile retargets.**
  - implementer-ivan :136, node-norris :165, frontend-freddy :173 and drupal-dries :204 drop the `bug-fixing-checklist` tactic reference and gain `collaboration.operating-procedures: [test-first-bug-fixing]`. That field mints `requires` edges.
  - java-jenny already declares it (:64).
  - reviewer-renata :143 keeps `code-review-incremental`.

## Subtasks

### T055 – Red-first test `tests/doctrine/test_served_prompts_single_owner.py` (own commit, RED)

- No prompt, guideline, step contract or profile restates the pillar list; they reference `DIRECTIVE_051`.
- No `adversarial-evidence-contract.md` reference remains anywhere in `packs/built-in`.
- Step contracts cite `DIRECTIVE_\d{3}` and no `\d{3}-[a-z-]+` slug, and every citation resolves.
- The implement prompt assigns draft-PR opening to the orchestrator and has no raw `git commit`.
- No profile cites `bug-fixing-checklist`, and the four profiles declare `test-first-bug-fixing` in `operating-procedures`.

### T056 – Prompts and guidelines (the guidelines are out-of-map)

### T057 – Step contracts: slugs, supply-chain and disposition references

### T058 – The #5078 implement prompt

### T059 – Profiles: supply chain, disposition and the checklist retarget

## Test Strategy

```bash
pytest tests/doctrine/test_served_prompts_single_owner.py tests/doctrine/agent_profiles tests/doctrine/missions/test_guidelines_single_owner.py -q
pytest tests/doctrine -q -m "not slow" -k "step_contract or contract or profile or prompt"
pytest tests/doctrine/test_shipped_profiles.py tests/architectural/test_no_legacy_terminology.py -q
```

## Handoff-to-WP09 (commit body)

- The profile edge deltas: the `operating-procedures` requires edges, and the removed checklist edges.
- The step-contract directive edges, if any are minted.
- `tests/architectural/test_operating_procedures_resolve.py` and `test_doctrine_census.py` may pin counts.

## Activity Log

- 2026-09-28T09:00:00Z – system – Prompt created (fold-in revision).
