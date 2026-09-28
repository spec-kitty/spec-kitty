---
work_package_id: WP02
title: Guidelines single owner (#5202, P0)
dependencies: []
requirement_refs:
- FR-016
- FR-017
planning_base_branch: claude/squad-doctrine-single-owner-rzqpvw
merge_target_branch: claude/squad-doctrine-single-owner-rzqpvw
branch_strategy: Planning artifacts for this mission were generated on claude/squad-doctrine-single-owner-rzqpvw. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into claude/squad-doctrine-single-owner-rzqpvw unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-squad-doctrine-single-owner-01M3KBP7
base_commit: 14c9706c9803677346bc28629d5a29b088946f4e
created_at: '2026-09-28T07:27:45.566176+00:00'
subtasks:
- T006
- T007
- T008
- T009
- T010
phase: Phase 1 - Foundations
history:
- at: '2026-09-28T09:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks (fold-in revision)
agent_profile: python-pedro
authoritative_surface: packs/built-in/missions/mission-steps/software-dev/
create_intent:
- tests/doctrine/missions/test_guidelines_single_owner.py
execution_mode: code_change
model: sonnet
owned_files:
- packs/built-in/missions/mission-steps/software-dev/implement/guidelines.md
- packs/built-in/missions/mission-steps/software-dev/plan/guidelines.md
- packs/built-in/missions/mission-steps/software-dev/review/guidelines.md
- packs/built-in/missions/mission-steps/software-dev/tasks/guidelines.md
- packs/built-in/missions/software-dev/actions/*/guidelines.md
- packs/built-in/missions/documentation/actions/*/guidelines.md
- packs/built-in/missions/research/actions/*/guidelines.md
- src/charter/offering/missions/repository.py
- tests/doctrine/missions/test_referential_integrity.py
- tests/doctrine/missions/test_repository.py
- tests/doctrine/test_wp_authoring_contract_roundtrip.py
- tests/doctrine/missions/test_guidelines_single_owner.py
- tests/architectural/_builtin_pack_provenance_baseline.yaml
- docs/architecture/04_implementation_mapping/README.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – Guidelines single owner (#5202, P0)

## ⚡ Do This First: Load Agent Profile

FIRST run `spec-kitty agent profile show python-pedro` (add `--all` if it reports the profile as not activated in this repo) and `spec-kitty charter context --action implement --json`. Apply the resolved initialization, boundaries, directives and tactics, then state which ones you applied.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## Branch Strategy

- **Planning base branch**: `claude/squad-doctrine-single-owner-rzqpvw`
- **Merge target branch**: `claude/squad-doctrine-single-owner-rzqpvw`
- Execution worktrees are allocated per computed lane from `lanes.json`. Work only in the workspace that `spec-kitty implement WP02` resolves.

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

**P0 defect.** `src/charter/offering/missions/repository.py:510` loads `<mission>/actions/<action>/guidelines.md`. Its only consumer, `src/charter/activation/context_renderers/bootstrap_text.py:65-71`, swallows errors. Meanwhile the ADR (`docs/adr/3.x/2026-08-13-1-*`, lines ~36-37), CLAUDE.md and the org-pack overlay (`mission_step_repository.py:477,511`) name `mission-steps/<type>/<step>/guidelines.md` as canonical. Four software-dev pairs drifted in opposite directions. The operator decision: **`mission-steps/` is the single owner.**

Done means:
- The loader reads `mission-steps/<type>/<action>/guidelines.md`.
- All 17 `packs/built-in/missions/*/actions/*/guidelines.md` files are deleted. The `index.yaml` files next to them stay; WP09 owns them.
- The 4 software-dev `mission-steps` files carry the merged correct content.
- The absence guard and loader test are green.
- The stale docs are corrected.

## Subtasks & Detailed Guidance

### T006 – Red-first test (own commit, RED)

Create `tests/doctrine/missions/test_guidelines_single_owner.py`, markers `unit, fast, doctrine`:
- (a) no `packs/built-in/missions/*/actions/*/guidelines.md` exists;
- (b) for every mission type and action that has `mission-steps/<type>/<action>/guidelines.md`, `MissionRepository` returns that file's content and its origin names the `mission-steps` path;
- (c) the served software-dev implement, plan and review guidelines each contain the supply-chain section heading, verbatim as it appears in today's `mission-steps` copy (pin the exact heading string), and that section mentions `DIRECTIVE_051`. Add that mention if the merged text lacks it. `review` states the dependency rule as approved/done. WP08 later trims these sections to references, so pin ONLY the heading and the `DIRECTIVE_051` mention, never the pillar text;
- (d) no served guideline says "main repository" or "inflating them with a status commit".

### T007 – Merge the four software-dev files (onto the `mission-steps` base)

- `implement:11` and `review:21`: take "repository root checkout" from `actions/`.
- Keep the supply-chain sections: implement `:34+`, plan `:28+`, review `:30+`, all from `mission-steps/`.
- `review:9`: rewrite to "dependencies are approved or done and present in the review base". The gate is `dependency_readiness_for_wp`, where `approved` satisfies it.
- `tasks:26`: take "unnecessary overhead" from `actions/`.
- `diff` each pair first and check every hunk; research R-7 lists them.

### T008 – Repoint the loader

- Edit `_action_guidelines_path` (or equivalent) in `src/charter/offering/missions/repository.py` to use `mission-steps/<mission>/<action>/guidelines.md`.
- Check the org-pack/overlay path in `mission_step_repository.py` stays consistent.
- Update `tests/doctrine/missions/test_repository.py:318-345` (origin string) and `tests/doctrine/test_wp_authoring_contract_roundtrip.py:53-59,124-160`, which pins both tasks copies.

### T009 – Delete the 17 `actions/*/guidelines.md`

- Replace `_GUIDELINES_COPIED_STEPS` / the byte-identity assert in `tests/doctrine/missions/test_referential_integrity.py:93,200` with the absence guard. Keep one guard; don't duplicate T006.
- Update `tests/architectural/_builtin_pack_provenance_baseline.yaml` entries for deleted paths, around lines 122, 137, 175 and 177. Counts may only go down.
- `tests/doctrine/fixtures/content-manifest.json` is a frozen historical snapshot of `src/charter/offering/...` paths. Leave it.
- Grep `src/` and `tests/` for other readers of `actions/*/guidelines.md` (`grep -rn "guidelines.md" src tests`) and fix each.

### T010 – Docs

- Correct `docs/architecture/04_implementation_mapping/README.md:176,402` to the `mission-steps` source.
- Verify CLAUDE.md's "Template Source Location" already names `mission-steps/`. It should need no change; if it does, the edit is out-of-map.

## Test Strategy

```bash
pytest tests/doctrine/missions -q
pytest tests/doctrine/test_wp_authoring_contract_roundtrip.py tests/doctrine/missions/test_guidelines_single_owner.py -q
pytest tests/charter -q -k "context or bootstrap"
pytest tests/architectural/test_no_legacy_terminology.py -q
# provenance ratchet: locate with find tests -name "*provenance_ratchet*"
spec-kitty charter context --action implement --json | grep -i "supply" | head -3   # served content check
```

## Review Guidance

- The supply-chain text reaches `charter context --action implement` at head and not at base.
- The org-pack overlay still works.
- No reader of `actions/*/guidelines.md` remains.

## Activity Log

- 2026-09-28T09:00:00Z – system – Prompt created (fold-in revision).
- 2026-09-28 – claude (python-pedro, sonnet) – Implemented on lane-b; the orchestrator recorded this entry on the planning branch.
  - Commits:
    - `2eb0ce69`: red-first test, RED 21 failed / 35 passed
    - `82168836`: merge
    - `e819a102`: loader repoint
    - `f7263960`: delete the 17 `actions/*/guidelines.md` files and add the absence guard
    - `aa9ced4d`: docs
    - `660ce8ed` + `be41de49`: accidental kitty-specs commit and its guard-prescribed revert
  - Tests:
    - `tests/doctrine/missions`: 523 passed
    - roundtrip + single-owner tests: 65 passed
    - `tests/doctrine`: 3298 passed, 3 errors (test_packaging_parity build subprocess, identical at base)
    - `tests/charter -k "context or bootstrap"`: 639 passed, 1 failed (test_presence_gate_bundle_authority refuses the linked worktree, identical at base)
    - provenance ratchet + terminology: 100 passed
  - `regenerate-graph --check`: fresh.
  - Moved to for_review.
