---
work_package_id: WP08
title: 'Supply-chain doctrine owner: DIRECTIVE_051, neutral tactic, per-ecosystem toolguides (#5221 C)'
dependencies:
- WP02
requirement_refs:
- FR-026
planning_base_branch: claude/squad-doctrine-single-owner-rzqpvw
merge_target_branch: claude/squad-doctrine-single-owner-rzqpvw
branch_strategy: Planning artifacts for this mission were generated on claude/squad-doctrine-single-owner-rzqpvw. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into claude/squad-doctrine-single-owner-rzqpvw unless the human explicitly redirects the landing branch.
subtasks:
- T038
- T039
- T040
phase: Phase 2 - Owners
history:
- at: '2026-09-28T09:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks (fold-in revision)
agent_profile: curator-carla
authoritative_surface: packs/built-in/tactics/security/
create_intent:
- tests/doctrine/test_supply_chain_single_owner.py
- packs/built-in/toolguides/javascript-supply-chain.toolguide.yaml
- packs/built-in/toolguides/JAVASCRIPT_SUPPLY_CHAIN.md
- packs/built-in/toolguides/python-supply-chain.toolguide.yaml
- packs/built-in/toolguides/PYTHON_SUPPLY_CHAIN.md
- packs/built-in/toolguides/java-supply-chain.toolguide.yaml
- packs/built-in/toolguides/JAVA_SUPPLY_CHAIN.md
execution_mode: code_change
model: sonnet
owned_files:
- packs/built-in/directives/051-supply-chain-install-safety.directive.yaml
- packs/built-in/tactics/security/supply-chain-install-safety.tactic.yaml
- packs/built-in/tactics/architecture/dependency-hygiene.tactic.yaml
- packs/built-in/toolguides/javascript-supply-chain.toolguide.yaml
- packs/built-in/toolguides/JAVASCRIPT_SUPPLY_CHAIN.md
- packs/built-in/toolguides/python-supply-chain.toolguide.yaml
- packs/built-in/toolguides/PYTHON_SUPPLY_CHAIN.md
- packs/built-in/toolguides/java-supply-chain.toolguide.yaml
- packs/built-in/toolguides/JAVA_SUPPLY_CHAIN.md
- tests/doctrine/test_supply_chain_single_owner.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP08 – Supply-chain doctrine owner: DIRECTIVE_051, neutral tactic, per-ecosystem toolguides (#5221 C)

## ⚡ Do This First: Load Agent Profile

FIRST run `spec-kitty agent profile show curator-carla` (add `--all` if it reports the profile as not activated in this repo) and `spec-kitty charter context --action implement --json`. Apply the resolved initialization, boundaries, directives and tactics, then state which ones you applied.

- **Profile**: `curator-carla`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## Branch Strategy

- **Planning base branch**: `claude/squad-doctrine-single-owner-rzqpvw`
- **Merge target branch**: `claude/squad-doctrine-single-owner-rzqpvw`
- Execution worktrees are allocated per computed lane from `lanes.json`. Work only in the workspace that `spec-kitty implement WP08` resolves.

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

#5221 section C, the owner half; research R-10 has the evidence. WP11 later repoints the prompts, guidelines, step contracts and profiles to this owner.

- **DIRECTIVE_051 states its pillars once.** They currently appear four times: intent :11-28, procedures :42-79, integrity :81-99, validation :101-110. Keep one statement; the procedures and validation reference it without restating it.
- **Node LTS** leaves the any-ecosystem directive and moves to the JS/TS toolguide (decision).
- **`supply-chain-install-safety` stays the ONE operational tactic, made ecosystem-neutral** (pinned id):
  - drop `applies_to_languages: [javascript, typescript]` (:4);
  - keep ecosystem-neutral steps only: registry, freshness, lifecycle scripts as a concept, incident IoC, lockfile as a concept;
  - move the JS/TS specifics (npm/pnpm/yarn, package-lock, Node LTS) to `javascript-supply-chain.toolguide.yaml` + `JAVASCRIPT_SUPPLY_CHAIN.md`, following the `gherkin.toolguide.yaml` + `GHERKIN.md` pattern;
  - add `python-supply-chain` (pip/uv/poetry lock, hashes, index pinning);
  - add `java-supply-chain` only if the evidence in the repo supports it (grep profiles and prompts for maven/gradle guidance). Otherwise do not create it, and record why.
- **`dependency-hygiene`** (JS/TS steps :93-155) references the tactic and the JS toolguide instead of restating them.
- **Disposition** in `supply-chain-install-safety` :83-94 cites `adversarial-squad-deployment` (the contract owner, WP04) instead of `contracts/adversarial-evidence-contract.md`.

## Subtasks

### T038 – Red-first test `tests/doctrine/test_supply_chain_single_owner.py` (own commit, RED)

- 051 states each pillar exactly once: `== 1` per pillar term (registry, freshness, lifecycle scripts, incident IoC, lockfile). No "Node LTS".
- The tactic has no `applies_to_languages` and no ecosystem tokens (npm, pnpm, yarn, package-lock, pip, poetry, maven).
- The JS/TS steps (lockfile, lifecycle scripts, Node LTS) exist in the JS toolguide.
- The Python toolguide exists and loads.
- `dependency-hygiene` references the tactic id and restates no pillar list.
- No `adversarial-evidence-contract.md` reference remains in this WP's files.

### T039 – 051 and the neutral tactic

### T040 – Toolguides and `dependency-hygiene`

## Test Strategy

```bash
pytest tests/doctrine/test_supply_chain_single_owner.py -q
pytest tests/doctrine -q -m "not slow" -k "supply or toolguide or tactic or directive"
```

## Handoff-to-WP09 (commit body)

- toolguide nodes and edges (tactic → toolguides `suggests`);
- the `applies_to_languages` change (profile-scope edges may move);
- activation of the new toolguides in `default.yaml`.

## Activity Log

- 2026-09-28T09:00:00Z – system – Prompt created (fold-in revision).
