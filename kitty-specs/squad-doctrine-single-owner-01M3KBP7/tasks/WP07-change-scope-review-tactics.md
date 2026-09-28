---
work_package_id: WP07
title: Change-scope reconciler, review tactics, kind change and in-house moves (#5221 B, D)
dependencies:
- WP02
requirement_refs:
- FR-023
- FR-025
- FR-028
planning_base_branch: claude/squad-doctrine-single-owner-rzqpvw
merge_target_branch: claude/squad-doctrine-single-owner-rzqpvw
branch_strategy: Planning artifacts for this mission were generated on claude/squad-doctrine-single-owner-rzqpvw. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into claude/squad-doctrine-single-owner-rzqpvw unless the human explicitly redirects the landing branch.
subtasks:
- T032
- T033
- T034
- T035
- T036
- T037
phase: Phase 2 - Owners
history:
- at: '2026-09-28T09:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks (fold-in revision)
agent_profile: curator-carla
authoritative_surface: packs/built-in/tactics/
create_intent:
- packs/built-in/styleguides/boring-code-review.styleguide.yaml
- packs/internal/tactics/tracker-backlog-iterative-deepening.tactic.yaml
- packs/internal/procedures/tracker-organisation-workflow.procedure.yaml
- tests/doctrine/test_change_scope_review_single_owner.py
execution_mode: code_change
model: sonnet
owned_files:
- packs/built-in/directives/reconcile-change-scope-tensions.directive.yaml
- packs/built-in/directives/024-locality-of-change.directive.yaml
- packs/built-in/directives/025-boy-scout-rule.directive.yaml
- packs/built-in/tactics/change-apply-smallest-viable-diff.tactic.yaml
- packs/built-in/tactics/avoid-gold-plating.tactic.yaml
- packs/built-in/tactics/locality-of-change.tactic.yaml
- packs/built-in/tactics/easy-to-change.tactic.yaml
- packs/built-in/tactics/boring-code-review.tactic.yaml
- packs/built-in/styleguides/boring-code-review.styleguide.yaml
- packs/built-in/tactics/architecture/deepening-opportunity-assessment.tactic.yaml
- packs/built-in/tactics/code-review-incremental.tactic.yaml
- packs/built-in/tactics/review-intent-and-risk-first.tactic.yaml
- packs/built-in/tactics/iterative-deepening-review.tactic.yaml
- packs/built-in/procedures/tracker-organisation-workflow.procedure.yaml
- packs/internal/tactics/tracker-backlog-iterative-deepening.tactic.yaml
- packs/internal/procedures/tracker-organisation-workflow.procedure.yaml
- packs/internal/drg/fragment.yaml
- packs/built-in/directives/039-lynn-cole-engineering-culture.directive.yaml
- tests/doctrine/test_change_scope_review_single_owner.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP07 – Change-scope reconciler, review tactics, kind change and in-house moves (#5221 B, D)

## ⚡ Do This First: Load Agent Profile

FIRST run `spec-kitty agent profile show curator-carla` (add `--all` if it reports the profile as not activated in this repo) and `spec-kitty charter context --action implement --json`. Apply the resolved initialization, boundaries, directives and tactics, then state which ones you applied.

- **Profile**: `curator-carla`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## Branch Strategy

- **Planning base branch**: `claude/squad-doctrine-single-owner-rzqpvw`
- **Merge target branch**: `claude/squad-doctrine-single-owner-rzqpvw`
- Execution worktrees are allocated per computed lane from `lanes.json`. Work only in the workspace that `spec-kitty implement WP07` resolves.

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

This WP covers #5221 sections B and D, plus #5220 item 8. Research R-9 and R-10 carry the evidence.

**B, change scope**
- `RECONCILE_CHANGE_SCOPE_TENSIONS`:
  - Name DIRECTIVE_052. The 052 → reconcile `suggests` edge exists; add the prose side, and hand WP09 a `reconciles_tension` edge if the tension vocabulary fits (see the `in_tension_with` / `reconciles_tension` edges in `directive.graph.yaml:~473-481` and `hand_authored_overlay.py`).
  - State the **tidy-first carve-out**: an opening campsite-clean is a distinct behaviour-preserving step that precedes the functional change; see charter.md "Reconciling change-scope tensions".
  - State the **tie-break**: DIRECTIVE_025 naming improvements are allowed inside the touched area; `change-apply-smallest-viable-diff` governs the file set, not in-file naming. This resolves `smallest-viable-diff:11,21` vs `025:29`.
- DIRECTIVE_025, for #5220 item 8: scope pre-existing-failure handling to the touched area, and defer classification to DIRECTIVE_030. Its "the waste" line (:37) must not contradict 030:17 or the charter's pre-existing-failure rule.
- Fold the `locality-of-change` **tactic** into `avoid-gold-plating` and delete it. Its evidence gate is 3+ real failures and 5/7 checks.
  - Reconcile the thresholds with `avoid-gold-plating:23-30`, `easy-to-change:24-29` and boring-code-review `:19-23` into one statement owned by avoid-gold-plating.
  - Repoint `deepening-opportunity-assessment.tactic.yaml:65`.
  - Directive `024-locality-of-change` is a different artifact: keep it, and only adjust prose if it names the tactic.
- `easy-to-change`, `avoid-gold-plating` and boring-code-review reference the reconciler. A tactic's reference to a directive mints `suggests`.

**D, review tactics**
- `code-review-incremental` builds on `review-intent-and-risk-first` by reference, with ONE risk taxonomy (pick the intent-first one), and no "confirm with the author" step (intent-first :9 → "record open intent questions in the review output").
  - The two tactics share 3 steps: incremental :14-17 vs intent-first :13.
  - About 20 consumers exist; keep both ids.
- `boring-code-review` **becomes a styleguide**. Create `styleguides/boring-code-review.styleguide.yaml`, following the styleguide schema, and delete the tactic.
  - Record its wiring for WP09: `action.graph.yaml:374,551`, both action indexes, `default.yaml:58`, `minimal.yaml:45`.
  - Record for WP10: `charter.yaml:77`.
  - Record the tests: `tests/charter/test_context.py`, `tests/doctrine/test_acceptance_criteria_non_vacuity_wiring.py`.
  - Directive 039 references it; update the reference type.
- `iterative-deepening-review` is backlog triage.
  - Rename it to `tracker-backlog-iterative-deepening` and move it to `packs/internal/tactics/`.
  - Move `tracker-organisation-workflow` (which references it at :129, :144) to `packs/internal/procedures/`.
  - Both leave built-in. Add them to the internal pack's `drg/fragment.yaml` in its existing shape.
  - Read `packs/internal/README.md` and ADR `docs/adr/3.x/2026-08-16-3-*` first.
  - Check nothing else in built-in references either id: `grep -rn "iterative-deepening-review\|tracker-organisation-workflow" packs/built-in src tests docs`. Any built-in → internal reference is forbidden, so record the remaining references for WP09 and WP10.

## Subtasks

### T032 – Red-first test (own commit, RED)

`tests/doctrine/test_change_scope_review_single_owner.py`:
- the reconciler names DIRECTIVE_052 and states the tidy-first carve-out and the tie-break;
- the `locality-of-change` tactic is absent AND its evidence gate (3+ real failures, the check list) is present in `avoid-gold-plating`, which states one threshold;
- DIRECTIVE_025 names `DIRECTIVE_030` for pre-existing-failure classification and no longer carries the line calling the proof "the waste";
- `boring-code-review` resolves as a styleguide and not as a tactic;
- `iterative-deepening-review` and `tracker-organisation-workflow` are absent from built-in and present in the internal pack;
- `code-review-incremental` references `review-intent-and-risk-first` and does not restate its steps;
- no built-in artifact references an internal-only id.

### T033 – Reconciler and 024/025 prose

### T034 – Fold and delete the locality tactic

### T035 – Review-tactic layering

### T036 – `boring-code-review` kind change

### T037 – In-house moves (internal pack and fragment)

## Test Strategy

```bash
pytest tests/doctrine/test_change_scope_review_single_owner.py -q
pytest tests/doctrine -q -m "not slow" -k "tactic or styleguide or directive or tension or internal or org_pack"
pytest tests/cross_cutting/packaging/test_packaging_safety.py -q
pytest tests/doctrine/drg/test_tension_arbiters.py tests/charter/test_tension_unreconciled.py -q
```

## Handoff (commit body; must record: Handoff-to-WP09 / Handoff-to-WP10)

All edge, activation, action-index and test updates listed above.

## Activity Log

- 2026-09-28T09:00:00Z – system – Prompt created (fold-in revision).
