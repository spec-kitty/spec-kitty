---
work_package_id: WP10
title: Dogfood the migration, charter, docs and glossary
dependencies:
- WP01
- WP09
requirement_refs:
- FR-010
- FR-015
- FR-023
planning_base_branch: claude/squad-doctrine-single-owner-rzqpvw
merge_target_branch: claude/squad-doctrine-single-owner-rzqpvw
branch_strategy: Planning artifacts for this mission were generated on claude/squad-doctrine-single-owner-rzqpvw. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into claude/squad-doctrine-single-owner-rzqpvw unless the human explicitly redirects the landing branch.
subtasks:
- T051
- T052
- T053
- T054
phase: Phase 4 - Dogfood
history:
- at: '2026-09-28T09:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks (fold-in revision)
agent_profile: curator-carla
authoritative_surface: .kittify/charter/
create_intent:
- tests/doctrine/test_dogfood_single_owner.py
execution_mode: code_change
model: sonnet
owned_files:
- .kittify/charter/**
- .kittify/metadata.yaml
- docs/development/reference/quality-and-tech-debt-standing-orders.md
- docs/development/agent-fleet.md
- docs/api/agent_profiles/implementer-ivan.md
- docs/development/3-2-docs-retrieval-index.yaml
- packs/built-in/glossary_packs/spec-kitty-core.glossary-pack.yaml
- packs/internal/glossary_packs/spk-internal.glossary-pack.yaml
- tests/doctrine/test_dogfood_single_owner.py
- packs/built-in/pack-manifest.yaml
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP10 – Dogfood the migration, charter, docs and glossary

## ⚡ Do This First: Load Agent Profile

FIRST run `spec-kitty agent profile show curator-carla` (add `--all` if it reports the profile as not activated in this repo) and `spec-kitty charter context --action implement --json`. Apply the resolved initialization, boundaries, directives and tactics, then state which ones you applied.

- **Profile**: `curator-carla`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## Branch Strategy

- **Planning base branch**: `claude/squad-doctrine-single-owner-rzqpvw`
- **Merge target branch**: `claude/squad-doctrine-single-owner-rzqpvw`
- Execution worktrees are allocated per computed lane from `lanes.json`. Work only in the workspace that `spec-kitty implement WP10` resolves.

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

1. **Dogfood (FR-010).**
   - First, on the lane workspace, run `spec-kitty charter context --action plan --json` and record whether it fails on the retired ids. That is the consumer failure WP01's migration exists for.
   - Apply WP01's migration to this repo: instantiate the class and call `apply(repo_root)`, or use the upgrade runner.
   - Regenerate the compiled charter surfaces (`charter.yaml`, `graph.yml`, `_LIBRARY/*` sidecars) through the canonical charter CLI. Read the `--help` of `spec-kitty charter generate|sync|synthesize` and use what refreshes them from source. **Never hand-edit compiled output.**
   - If the generator rewrites large unrelated regions, stop and fall back to the minimal regeneration, with the rationale recorded.
   - `.kittify/metadata.yaml:~337` is a historical log line; leave it.
   - Afterwards, `grep -rn` for each retired id under `.kittify/` shows only history and `evidence/`, and `charter context --action plan|implement|review` succeeds.
2. **Charter prose** (`.kittify/charter/charter.md`, the human source):
   - Standing Order #1 (~62-65) points at the `adversarial-squad-deployment` procedure and does NOT enumerate point-cuts. Suggested wording: "Run a profile-loaded adversarial squad at the planning point-cuts the procedure defines, casting the profiles whose focus answers that point-cut's question. Optional and advisory, never a hard gate."
   - Check ~190 and ~205 for point-cut lists.
   - Check the other standing orders for retired ids.
   - Add an `Updated: 2026-09-28` header line in the file's convention.
   - If `charter.md` is regenerated from `interview/answers.yaml` / `charter.yaml`, edit the generator's source instead.
3. **Docs:**
   - `docs/development/reference/quality-and-tech-debt-standing-orders.md` (~29-40, a second point-cut table): replace it with a pointer to the procedure plus a one-line profile-per-task summary.
   - `docs/development/agent-fleet.md:~53` and `docs/api/agent_profiles/implementer-ivan.md:36` (bug-fixing-checklist): update both.
   - Bump `updated:` frontmatter.
   - Regenerate `docs/development/3-2-docs-retrieval-index.yaml` with its canonical script (find it: `grep -rln 3-2-docs-retrieval-index scripts`). It names the retired styleguide.
   - Run `python scripts/docs/check_docs_freshness.py --ci` (errors=0) and `python scripts/docs/docs_index.py --write`.
4. **Glossary (FR-015, FR-023 alias):**
   - Move "adversarial squad" from `packs/internal/glossary_packs/spk-internal.glossary-pack.yaml` (~80) into `packs/built-in/glossary_packs/spec-kitty-core.glossary-pack.yaml`, in that file's entry schema. Refine the definition: profile-loaded delegates, each casting a distinct lens chosen for the point-cut's question; optional and advisory; owned by the `adversarial-squad-deployment` procedure.
   - Add a behaviour/behavior alias entry (for example "behaviour-driven development", alias "behavior-driven development"), per the glossary schema's alias mechanism.
   - Then run `spec-kitty doctrine regenerate-graph`: the manifest hashes the glossary pack. WP10 co-owns the manifest (dependency-ordered after WP09) for this regeneration.

## Subtasks

### T051 – Red-first test `tests/doctrine/test_dogfood_single_owner.py` (own commit, RED)

- The term is in built-in, not in internal.
- The behaviour/behavior alias resolves.
- SC-001: reusing `tests/doctrine/_single_owner_detectors.py` (WP04), neither `.kittify/charter/charter.md` Standing Order #1 nor `docs/development/reference/quality-and-tech-debt-standing-orders.md` restates a point-cut list or a headcount. Positive control: the detector flags the current text of both.

### T052 – Dogfood the migration and charter regeneration

### T053 – Charter prose and docs

### T054 – Glossary

## Test Strategy

```bash
spec-kitty charter context --action plan --json >/dev/null && spec-kitty charter context --action implement --json >/dev/null && echo OK
spec-kitty doctrine regenerate-graph --check
pytest tests/doctrine/test_squad_glossary_term.py -q ; pytest tests/glossary -q -m "not slow"
pytest tests/charter -q -k "glossary or charter_md or consistency"
pytest tests/cross_cutting/packaging/test_packaging_safety.py tests/architectural/test_no_legacy_terminology.py -q
```

## Activity Log

- 2026-09-28T09:00:00Z – system – Prompt created (fold-in revision).
