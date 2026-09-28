---
work_package_id: WP01
title: Consumer retirement migration (shared, data-driven)
dependencies: []
requirement_refs:
- FR-009
planning_base_branch: claude/squad-doctrine-single-owner-rzqpvw
merge_target_branch: claude/squad-doctrine-single-owner-rzqpvw
branch_strategy: Planning artifacts for this mission were generated on claude/squad-doctrine-single-owner-rzqpvw. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into claude/squad-doctrine-single-owner-rzqpvw unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-squad-doctrine-single-owner-01M3KBP7
base_commit: 9ae4bc81a01b933984550429b9149ca759fe6927
created_at: '2026-09-28T07:26:59.918021+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
phase: Phase 1 - Foundations
history:
- at: '2026-09-28T09:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks (fold-in revision)
agent_profile: python-pedro
authoritative_surface: src/specify_cli/upgrade/migrations/
create_intent:
- src/specify_cli/upgrade/migrations/_retired_activation.py
- src/specify_cli/upgrade/migrations/m_4_0_0rc5_retire_single_owner_doctrine_ids.py
- tests/specify_cli/upgrade/migrations/test_retired_activation.py
- tests/specify_cli/upgrade/migrations/test_m_4_0_0rc5_retire_single_owner_doctrine_ids.py
execution_mode: code_change
model: sonnet
owned_files:
- src/specify_cli/upgrade/migrations/_retired_activation.py
- src/specify_cli/upgrade/migrations/m_3_2_6_retire_rtk_search_tooling.py
- src/specify_cli/upgrade/migrations/m_4_0_0rc5_retire_single_owner_doctrine_ids.py
- tests/specify_cli/upgrade/migrations/test_retired_activation.py
- tests/specify_cli/upgrade/migrations/test_m_4_0_0rc5_retire_single_owner_doctrine_ids.py
- tests/architectural/test_no_dead_modules.py
- tests/architectural/charter_path_literal_allowlist.yaml
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Consumer retirement migration (shared, data-driven)

## ⚡ Do This First: Load Agent Profile

FIRST run `spec-kitty agent profile show python-pedro` (add `--all` if it reports the profile as not activated in this repo) and `spec-kitty charter context --action implement --json`. Apply the resolved initialization, boundaries, directives and tactics, then state which ones you applied.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## Branch Strategy

- **Planning base branch**: `claude/squad-doctrine-single-owner-rzqpvw`
- **Merge target branch**: `claude/squad-doctrine-single-owner-rzqpvw`
- Execution worktrees are allocated per computed lane from `lanes.json`. Work only in the workspace that `spec-kitty implement WP01` resolves.

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

This mission deletes, renames, moves or re-kinds several activatable doctrine ids. The charter compiler is fail-closed: `charter.activation.compiler` raises `UnknownArtifactIdError` for an unknown `activated_*` stem. The rc35 migration copied default-pack lists verbatim into consumer projects. Every consumer that activated a retired id would therefore hard-fail after upgrade. This WP ships ONE data-driven migration that prevents that.

**Retirement table** (research R-11). Put it in the migration module as data:

| kind key | retired stem | reference prefix | successor (kind key, stem) |
|---|---|---|---|
| `activated_styleguides` | `adversarial-squad-cadence` | `STYLEGUIDE` | none |
| `activated_tactics` | `bug-fixing-checklist` | `TACTIC` | (`activated_procedures`, `test-first-bug-fixing`) |
| `activated_tactics` | `locality-of-change` | `TACTIC` | (`activated_tactics`, `avoid-gold-plating`) |
| `activated_tactics` | `common-docs-curation` | `TACTIC` | (`activated_tactics`, `common-docs-scaffold`), (`activated_tactics`, `common-docs-write`), (`activated_tactics`, `common-docs-find`) |
| `activated_tactics` | `boring-code-review` | `TACTIC` | (`activated_styleguides`, `boring-code-review`) |
| `activated_tactics` | `behavior-driven-development` | `TACTIC` | (`activated_tactics`, `bdd-scenario-formulation`) |
| `activated_tactics` | `iterative-deepening-review` | `TACTIC` | none (moves to the in-house pack) |
| `activated_procedures` | `tracker-organisation-workflow` | `PROCEDURE` | none (moves to the in-house pack) |

Verify each `activated_*` key name and catalog prefix against real files:
- `src/charter/activation/packs/default.yaml`
- this repo's `.kittify/charter/charter.yaml`, around lines 34, 77, 80, 110 and 168, and the catalog `id:` blocks.

Other mission WPs choose the final id of the renamed/re-kinded successors (`bdd-scenario-formulation`, the `boring-code-review` styleguide id). If the mission's WP05 or WP07 changes an id, update the table; coordinate via the Activity Log.

**Rules**:
1. **Match by kind key.**
   - Directive `024-locality-of-change` lives under `activated_directives` and must never be touched.
   - Only remove a stem from the list named by its kind key.
2. **Skip ids the project can still resolve.**
   - An id moved to `packs/internal` still resolves for a project that loads that org pack, as this repository does via `.kittify/config.yaml` → `doctrine.org.packs`.
   - Before removing, check whether the id still resolves for the project. Use a cheap check, for example the project's configured org-pack roots containing a file for that id. Leave it alone if it resolves.
   - Document the check and test both branches.
3. **Successor activation**: append the successor stem to its `activated_*` list **only when that list already exists** and lacks it.
   - An absent key means "not narrowed"; see `m_3_2_x_normalize_activation_absence`. Never create keys.
   - Do not add catalog blocks. The next `charter generate` compiles them.
4. **Surfaces**, each optional:
   - `.kittify/config.yaml` (`activated_*`);
   - `.kittify/charter/charter.yaml` (`activated_*` plus `catalog` blocks with `id: <PREFIX>:<stem>`);
   - `.kittify/charter/references.yaml` (`references` blocks);
   - `.kittify/charter/interview/answers.yaml` (any `selected_*` list naming the stem; confirm the key names in this repo's file around line 139).

   Nothing is ever created. Malformed YAML is skipped, never fatal. Round-trip ruamel keeps comments and quoting.
5. **Consumer `graph.yml`.** Build a fixture project whose `.kittify/charter/graph.yml` carries a node and edge for an id that does not exist in doctrine; use a fake id, because the real ids are deleted in other lanes. Run the charter context/compile entry point against it. If the stale node breaks it, add `graph.yml` node and edge removal to the migration's surfaces, with tests. Either way, record the evidence.
6. The retirement table is data that WP09's consistency test imports. Expose it as a module-level constant `RETIREMENTS`.
7. `migration_id = "4.0.0rc5_retire_single_owner_doctrine_ids"`, `target_version = "4.0.0rc5"`. See the rationale in `m_4_0_0rc5_hosted_endpoint_session_backfill.py`'s docstring.

## Subtasks & Detailed Guidance

### T001 – Red-first tests (own commit, RED)

Write `tests/specify_cli/upgrade/migrations/test_m_4_0_0rc5_retire_single_owner_doctrine_ids.py` and `tests/specify_cli/upgrade/migrations/test_retired_activation.py`, markers `unit, fast`. Cover:
- `detect` is parametrized over every table row and every surface;
- `apply` removes duplicates too, keeps sibling entries, and asserts semantic equality minus the removals;
- successor appended only when the target list exists;
- directive `024-locality-of-change` is untouched while the tactic of the same slug is removed;
- the org-pack-resolvable skip;
- the second run is a no-op with `success=True`;
- a bare project produces an identical directory-tree snapshot;
- malformed YAML is skipped;
- `dry_run` writes nothing.

### T002 – Extract `_retired_activation.py`

- Take the generic logic from `m_3_2_6_retire_rtk_search_tooling.py`.
- Parametrize it with a frozen dataclass: `Retirement(kind_key, stem, reference_prefix, successors: tuple[tuple[str, str], ...] = ())`.
- Keep functions small (complexity ≤ 15).
- Use `charter.bundle.CHARTER_YAML` instead of re-spelling `charter.yaml`, to satisfy `tests/architectural/test_charter_path_literal_authority.py`.
- The leading underscore keeps the registry from importing it as a migration; that is the `_merge_driver_seeding.py` precedent.

### T003 – Thin rtk migration

- Rebuild the rtk migration on the helper, behaviour-preserving.
- `tests/specify_cli/upgrade/migrations/test_m_3_2_6_retire_rtk_search_tooling.py` must pass **unmodified**.
- Its public constants, id, version and surfaces stay: config, charter and references only.

### T004 – The new migration

- Data table plus the thin class.
- The docstring explains why: single-owner doctrine consolidation retires these ids, the compiler is fail-closed, and this is the same precedent as rtk.

### T005 – Allowlists

- Add the new migration module to the auto-discovered list in `tests/architectural/test_no_dead_modules.py`, next to the rtk entry.
- Remove the rtk entry from `tests/architectural/charter_path_literal_allowlist.yaml` once its literal is gone. The allowlist is shrink-only; add an entry for the helper only if unavoidable, with a rationale.

## Test Strategy

```bash
pytest tests/specify_cli/upgrade/migrations/test_m_3_2_6_retire_rtk_search_tooling.py tests/specify_cli/upgrade/migrations/test_m_4_0_0rc5_retire_single_owner_doctrine_ids.py tests/specify_cli/upgrade/migrations/test_retired_activation.py -q
pytest tests/upgrade -q -k "registry or ordering or migration"
pytest tests/architectural/test_no_dead_modules.py tests/architectural/test_charter_path_literal_authority.py tests/architectural/test_no_stale_charter_path_literals.py -q
ruff check <files> && ruff format --check <files> && mypy <src files>
```

## Review Guidance

- The rtk test file is byte-unchanged and green.
- No near-duplicate logic remains.
- The directive/tactic slug collision is tested.
- The red-first commit precedes the implementation commit.

## Activity Log

- 2026-09-28T09:00:00Z – system – Prompt created (fold-in revision).
- 2026-09-28 – claude (python-pedro, sonnet) – Implemented on lane-a; the orchestrator recorded this entry on the planning branch.
  - Commits:
    - `78eccf98`: red-first tests, red by `ModuleNotFoundError` at collection
    - `def775d2`: helper, rtk rebuild, 8-row `RETIREMENTS` table, allowlist drain (50→49), plus an out-of-map FLOOR bump in `test_charter_path_literal_authority.py`
  - Consumer `graph.yml`: no reader in `src/`, so it is excluded from the migration's surfaces; an AST regression guard pins that.
  - Tests:
    - migration tests: 56 passed
    - `tests/upgrade -k registry|ordering|migration`: 517 passed, 1 failed (`test_readonly_gitignore_clear_error`, a root-permission environment false-red on an untouched module)
    - architectural gates: 26 passed
    - ruff: clean
  - Moved to for_review.
