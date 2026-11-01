---
work_package_id: WP01
title: Promote kind_vocabulary's scanning seams and ratchet the retired names
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- FR-005
- FR-006
- FR-007
- NFR-001
- NFR-002
- NFR-003
- NFR-004
- SC-001
- SC-002
- SC-003
- SC-004
planning_base_branch: issue-6434-kind-vocabulary-scan-api
merge_target_branch: issue-6434-kind-vocabulary-scan-api
branch_strategy: Planning artifacts for this mission were generated on issue-6434-kind-vocabulary-scan-api. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6434-kind-vocabulary-scan-api unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
- T007
- T008
phase: Phase 1 - Refactor
history:
- at: '2026-11-01T15:20:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/charter/activation/
create_intent:
- tests/architectural/test_charter_kind_vocabulary_public_scan_api.py
execution_mode: code_change
model: ''
owned_files:
- src/charter/activation/kind_vocabulary.py
- src/charter/activation/identity_index.py
- src/charter/activation/action_governance_bundle.py
- src/charter/activation/compiler.py
- src/charter/activation/context.py
- src/charter/activation/pack_manager.py
- tests/charter/activation/test_identity_index.py
- tests/charter/activation/test_compile_check_identity_6433.py
- tests/charter/activation/test_context_identity_reuse.py
- tests/charter/test_directive_resolution_memoization.py
- tests/charter/test_resolver_directive_activation_keying.py
- tests/charter/test_kind_vocabulary_scan_roots.py
- tests/charter/test_org_scan_dirs_activation_regression.py
- tests/charter/test_action_governance_bundle_activation.py
- tests/charter/test_synthesized_in_force_snapshot.py
- tests/charter/test_context_service_seams.py
- tests/charter/test_context_display_charter_md.py
- tests/charter/synthesizer/test_styleguide_reach_only.py
- tests/charter/synthesizer/test_reach_only_delivery.py
- tests/charter_offering/test_owner_delivery.py
- tests/charter_offering/drg/test_org_pack_node_inference.py
- tests/charter_offering/drg/test_recursion_parity_gate.py
- tests/charter_offering/test_activation_parity_guard.py
- tests/charter_offering/drg/test_unknown_kind_fails_loudly.py
- tests/architectural/test_charter_kind_vocabulary_public_scan_api.py
- docs/changelog/unreleased/6434-kind-vocabulary-scan-api.internal.md
- src/charter/activation/interview.py
- src/charter/activation/context_renderers/delivery_table.py
- tests/charter/test_activation_consumers.py
- tests/charter/test_context_org_chain.py
- tests/charter/test_action_bundle_tension_arbiters.py
- tests/charter/test_action_governance_bundle_org_fragment.py
- tests/charter/test_default_in_force_snapshot.py
- tests/specify_cli/cli/commands/charter/test_synthesize_styleguide_edge_6442.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Promote `kind_vocabulary`'s scanning seams and ratchet the retired names

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the
frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `codex`

If the profile cannot be resolved, run `spec-kitty agent profile show python-pedro`.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via
  `spec-kitty agent tasks status`).
- **You must address all feedback** before your work is complete.
- **Report progress**: record each addressed item with
  `spec-kitty agent tasks add-history WP01 --note "..."`.

---

## Objectives & Success Criteria

Promote the artifact-discovery seams that issue spec-kitty/spec-kitty#6434 names — the
`kind_vocabulary` scanning and id helpers, `IdentityIndex`'s per-kind scan, and the two
governance seams — from underscore-private names to documented public names, move **every**
call site in `src/` and `tests/` onto them, and prove with an architectural ratchet that no
retired underscore name remains reachable and none can return.

Done means:

- `charter.activation.kind_vocabulary.__all__` exports `scan_roots`, `scan_dir_matches`,
  `built_in_scan_dir`, `iter_artifact_paths`, `artifact_id_field`, `read_artifact_id`,
  `parse_artifact_id`, `artifact_config_stem`.
- `IdentityIndex` is written entirely against those names and exposes `scan(kind)`.
- `charter.activation.action_governance_bundle.load_action_governance_bundle` and
  `charter.activation.compiler.direct_root_urns` are public and imported as such.
- No `src/` or `tests/` file references a retired name; the new ratchet is green and has
  been observed red first.
- Behaviour is unchanged: the scan-count, memoization, parity, identity and
  governance-bundle suites pass with **unchanged expectations**.

## Context & Constraints

**Why this exists.** Issue #6434 is a pre-PR review finding on the #6404–#6408 Mission: PR
#6440 added `IdentityIndex`, which consumes five private `kind_vocabulary` helpers, and a
dozen test modules reach through the same private names to count scans and seed graphs. The
issue asks for a small module-internal scanning API in `kind_vocabulary` that
`IdentityIndex` consumes and the tests probe.

**Read before you edit**:

- `kitty-specs/issue-6434-kind-vocabulary-scan-api-01M6BTT8/spec.md` (FR-001…FR-007, the
  constraints C-001…C-004)
- `kitty-specs/issue-6434-kind-vocabulary-scan-api-01M6BTT8/plan.md` (the public-surface
  table and the invariants each existing test pins)
- `kitty-specs/issue-6434-kind-vocabulary-scan-api-01M6BTT8/research.md` (the naming and
  remove-don't-alias decisions)
- `src/charter/activation/kind_vocabulary.py` (module docstring: it is already described as
  "the single seam"; only its scanning half is private)

**Hard constraints**

- **No behaviour change** (C-001): precedence order, recursion, the reserved immediate
  `built-in/` exclusion, the directive id round-trip/ambiguity rule, the fail-soft
  `built_in_dir` handling and the fail-open bundle posture all stay exactly as they are.
- **Remove, do not alias** (C-002): no `_scan_roots = scan_roots` compatibility shim, no
  deprecation warning. Update the call sites instead.
- **Single authority** (C-003): `kind_vocabulary` remains the only discovery authority. Do
  not create a `scanning.py`, do not re-export `charter.offering.*` discovery helpers, and
  do not let `identity_index` grow its own scanning logic.
- **Layering** (NFR-002): `charter` may import `doctrine`/`kernel`, never `specify_cli`.
- **Anchored renames only**: lookalike helpers must not move —
  `neutrality/lint._iter_mission_scan_roots`, `_iter_charter_scan_roots`,
  `_default_scan_roots`, `catalog._resolve_scan_roots`, `pack_assembler._read_id`,
  `kind_vocabulary._org_scan_dirs`, `_layer_scan_dirs`, `_scan_cache_key`.
- Do not touch `packs/built-in/` or `packs/internal/` (generated pins), and do not weaken
  or skip any gate.

## Branch Strategy

- **Strategy**: Planning artifacts were generated on `issue-6434-kind-vocabulary-scan-api`;
  completed changes must merge back into that branch.
- **Planning base branch**: `issue-6434-kind-vocabulary-scan-api`
- **Merge target branch**: `issue-6434-kind-vocabulary-scan-api`

Execution workspaces are allocated per computed lane from `lanes.json`; enter the workspace
`spec-kitty agent action implement WP01 --agent <name>` gives you and never build a
worktree path by hand.

## Subtasks & Detailed Guidance

### Subtask T001 – Write the ratchet test and observe it red

- **Purpose**: This is the mission's red-first proof. A refactor has no failing behaviour to
  reproduce, so the failing thing is the coupling itself: a test that fails while any call
  site still reaches a retired name.
- **Steps**:
  1. Create `tests/architectural/test_charter_kind_vocabulary_public_scan_api.py`.
  2. Scan `src/` and `tests/` for the retired attribute names, as an AST or text scan over
     `*.py` files (no import of the scanned modules is required). The retired set:
     `kind_vocabulary._scan_roots`, `._scan_dir_matches`, `._iter_artifact_paths`,
     `._read_id`, `._parse_id`, `._id_field_for`, `._config_stem`, `._built_in_scan_dir`,
     `IdentityIndex._scan`, `action_governance_bundle._load_action_governance_bundle`,
     `compiler._direct_root_urns`. Match the module-alias form used across the repo
     (`kind_vocabulary._scan_roots`, `compiler._direct_root_urns`) **and** the
     `from … import _name` form; do not match the same suffix on unrelated modules
     (`pack_assembler._read_id`, `lint._default_scan_roots`, `catalog._resolve_scan_roots`).
  3. Add a **negative control**: run the same scanner over a synthetic snippet string that
     contains one retired reference and assert it is detected — so the scanner cannot pass
     by observing nothing at all.
  4. Add a **positive control**: assert each promoted public name exists on its module and is
     in `kind_vocabulary.__all__`. Before the promotion this assertion fails; that is the
     expected red.
  5. Run it and record the red output:
     `uv run pytest tests/architectural/test_charter_kind_vocabulary_public_scan_api.py -q`
  6. Keep the test in the fast tier (`pytest.mark.fast`, AST/`Path.read_text` only — no pack
     fetch, no full YAML parse) per NFR-003.
- **Files**: `tests/architectural/test_charter_kind_vocabulary_public_scan_api.py`
- **Notes**: Follow the shape used by neighbouring architectural tests (module docstring
  naming the invariant, `pytestmark`, a helper that returns findings, one test per claim).

### Subtask T002 – Promote `kind_vocabulary`'s scanning and id helpers

- **Purpose**: Turn the private discovery helpers into the named module-internal API the
  issue asks for.
- **Steps**:
  1. In `src/charter/activation/kind_vocabulary.py`, rename the definitions and every
     internal call in the module:

     | Today | Public name |
     | --- | --- |
     | `_id_field_for` | `artifact_id_field` |
     | `_parse_id` | `parse_artifact_id` |
     | `_read_id` | `read_artifact_id` |
     | `_config_stem` | `artifact_config_stem` |
     | `_scan_dir_matches` | `scan_dir_matches` |
     | `_built_in_scan_dir` | `built_in_scan_dir` |
     | `_scan_roots` | `scan_roots` |
     | `_iter_artifact_paths` | `iter_artifact_paths` |

  2. Add all eight to `__all__` (keep it sorted as the module already does).
  3. Give each a docstring that states the contract a caller can rely on: what it returns,
     the ordering it preserves, and the failure mode (`None` vs raise). The existing
     docstrings already carry this content — keep it, adjust the cross-references, and add a
     one-line contract sentence where the body is dense.
  4. Keep private (no consumer outside this module): `_org_scan_dirs`, `_layer_candidate_dir`,
     `_layer_scan_dirs`, `_built_in_step_contract_dir`, `_under_reserved_builtin_subdir`,
     `_scan_cache_key`, `_declares_id`, `_searched_layers`, `_org_roots_clause`,
     `_directive_ids_by_stem`, `_directive_stem_represents`.
  5. Update the docstring cross-reference in
     `src/charter/activation/pack_manager.py` (`kind_vocabulary._config_stem` →
     `artifact_config_stem`).
  6. Move the test call sites: `tests/charter/activation/test_identity_index.py`,
     `tests/charter/activation/test_compile_check_identity_6433.py`,
     `tests/charter/test_directive_resolution_memoization.py`,
     `tests/charter/test_kind_vocabulary_scan_roots.py` (monkeypatch targets and helper
     names), and the docstring references in
     `tests/charter_offering/test_activation_parity_guard.py`,
     `tests/charter/test_org_scan_dirs_activation_regression.py`,
     `tests/charter_offering/drg/test_recursion_parity_gate.py`.
- **Files**: `src/charter/activation/kind_vocabulary.py`,
  `src/charter/activation/pack_manager.py`, and the test files listed above.
- **Notes**: Do not renumber or reorder anything; the ordering rules in `scan_roots` /
  `_org_scan_dirs` are the flat-wins invariant and must not move. `pack_manager._config_stem`
  is a different private helper in a different module — leave it alone and only fix the
  docstring reference to `kind_vocabulary`.

### Subtask T003 – Rewire `IdentityIndex` and make its scan public

- **Purpose**: Remove the production coupling the issue reports, and give the scan-count
  probes a documented seam.
- **Steps**:
  1. In `src/charter/activation/identity_index.py`, replace
     `kind_vocabulary._id_field_for`, `._scan_roots`, `._scan_dir_matches`,
     `._config_stem`, `._read_id` with the public names (in `_scan`, in
     `_declared_id_of`, and in the `_declared_id_of` docstring).
  2. Rename `IdentityIndex._scan` to `IdentityIndex.scan` and document it: "Scan the layer
     roots for *kind* once and return its precedence-ordered identity entries; the public
     seam the scan-count probes wrap." Keep it idempotent per index instance (`_table`
     caching unchanged).
  3. Update the two tests that wrap the seam:
     `tests/charter/activation/test_context_identity_reuse.py` and
     `tests/charter/test_resolver_directive_activation_keying.py` (`IdentityIndex._scan` →
     `IdentityIndex.scan`, monkeypatch target and wrapper).
- **Files**: `src/charter/activation/identity_index.py`,
  `tests/charter/activation/test_context_identity_reuse.py`,
  `tests/charter/test_resolver_directive_activation_keying.py`,
  `tests/charter/activation/test_identity_index.py` (if its probe needs the new name).
- **Notes**: Keep the wrapper shape (`original = IdentityIndex.scan;
  monkeypatch.setattr(IdentityIndex, "scan", counted)`) so the counted call is still exactly
  one per kind. Do not move per-root scanning into the index or change `_table` caching.

### Subtask T004 – Move the scan-seam tests onto the public seams

- **Purpose**: The issue's second half: tests must stop coupling to underscore names.
- **Steps**:
  1. `tests/charter/activation/test_identity_index.py`: the `scan_calls` fixture wraps
     `kind_vocabulary.scan_dir_matches`; `_parse_id` → `parse_artifact_id`;
     `_id_field_for` → `artifact_id_field`; `_config_stem` → `artifact_config_stem`;
     `_built_in_scan_dir` → `built_in_scan_dir`.
  2. `tests/charter/test_directive_resolution_memoization.py`: same two seams
     (`scan_dir_matches`, `parse_artifact_id`).
  3. `tests/charter/activation/test_compile_check_identity_6433.py`:
     `iter_artifact_paths`, `artifact_config_stem`, `read_artifact_id`,
     `artifact_id_field`.
  4. Leave every assertion and every expected count **exactly** as it is (NFR-001). If a
     count changes, stop — that is a behaviour change, not a rename.
- **Files**: the four test modules above.
- **Notes**: These tests are the behaviour pin; only names may change in this subtask.

### Subtask T005 – Rename `_load_action_governance_bundle` to `load_action_governance_bundle`

- **Purpose**: The name is already exported in `__all__` with a leading underscore; the
  rename removes the inconsistency and stops tests importing private surface.
- **Steps**:
  1. `src/charter/activation/action_governance_bundle.py`: rename the definition, its
     `__all__` entry, and the internal call site (`_resolve_action_bundle`).
  2. `src/charter/activation/context.py`: keep its private alias import
     (`from … import load_action_governance_bundle as _load_action_governance_bundle`) so
     the AST/signature tests that inspect `context_module._load_action_governance_bundle`
     keep their meaning; update the comment that names the wrapper vs the loader.
  3. Move the test imports/calls: `tests/charter_offering/test_owner_delivery.py`,
     `tests/charter_offering/drg/test_org_pack_node_inference.py`,
     `tests/charter/test_synthesized_in_force_snapshot.py`,
     `tests/charter/test_context_service_seams.py`,
     `tests/charter/test_action_governance_bundle_activation.py`,
     `tests/charter/synthesizer/test_styleguide_reach_only.py`,
     `tests/charter/synthesizer/test_reach_only_delivery.py`.
  4. Do not rename `_ActionGovernanceBundle`, `_resolve_action_bundle`,
     `resolve_action_governance_bundle`, or `_catalog_default_or_activated`.
- **Files**: the two source modules and the test modules listed.
- **Notes**: `tests/charter/test_context_display_charter_md.py` inspects
  `context_module._load_action_governance_bundle`; if the alias keeps that name it needs no
  change — verify by running it, and only edit it if the assertion breaks.

### Subtask T006 – Rename `compiler._direct_root_urns` to `direct_root_urns`

- **Purpose**: Same review finding; the second governance seam tests import.
- **Steps**:
  1. `src/charter/activation/compiler.py`: rename the definition and its one call site in
     `_resolve_transitive_reference_graph`'s caller (line ~1667).
  2. Move the test imports/calls in `tests/charter/synthesizer/test_styleguide_reach_only.py`
     and `tests/charter/synthesizer/test_reach_only_delivery.py`; update the docstring
     reference in `tests/charter_offering/drg/test_unknown_kind_fails_loudly.py`.
  3. The reach-only tactic/styleguide exclusions stay untouched — the function body does not
     change.
- **Files**: `src/charter/activation/compiler.py` and the three test modules.
- **Notes**: Do not add it to `compiler.__all__` if that module does not declare one; keep
  the change to the name and the call sites.

### Subtask T007 – Changelog entry

- **Purpose**: Record the change for a searcher who finds the old name in history (C-004).
- **Steps**:
  1. Add an entry under `## [Unreleased]` in `docs/changelog/CHANGELOG.md` (the root
     `CHANGELOG.md` is a symlink; edit the file under `docs/`), in the section that carries
     the charter/governance entries.
  2. Shape: bold impact-first lead ending in `(#6434)`, then **Before:** / **After:**, under
     1,200 characters. It must say plainly that this is an internal `charter`-layer API
     promotion with no behaviour change, that the old underscore names are removed rather
     than aliased, and name the public replacements a searcher would grep for.
  3. Do not claim a user-facing CLI change.
- **Files**: `docs/changelog/CHANGELOG.md`
- **Notes**: Match the surrounding entries' wording and formatting exactly; do not renumber
  or move other entries.

### Subtask T008 – Run the targeted suites and prove the ratchet

- **Purpose**: Evidence that the promotion is complete and behaviour is unchanged.
- **Steps**:
  1. Ratchet green: `uv run pytest tests/architectural/test_charter_kind_vocabulary_public_scan_api.py -q`
  2. Retired-name sweep: `rg -n "_scan_roots|_scan_dir_matches|_iter_artifact_paths|_read_id|_parse_id|_id_field_for|_config_stem|_built_in_scan_dir|_load_action_governance_bundle|_direct_root_urns|IdentityIndex\._scan" src tests`
     — the only acceptable hits are on unrelated lookalike helpers
     (`lint._default_scan_roots`, `catalog._resolve_scan_roots`,
     `lint._iter_mission_scan_roots`, `pack_assembler._read_id`,
     `pack_manager._config_stem`, `context.py`'s deliberate private alias) and prose in
     docstrings that refers to those unrelated helpers. List them in your report.
  3. Behaviour pin:
     `uv run pytest tests/charter tests/charter_offering tests/specify_cli/cli/commands/charter -q`
  4. Fast tier: `make test-fast` (or `uv run pytest -m fast -q` if the target is unavailable);
     never a full heavy sweep (`NO_FULL_HEAVY_SUITES_IN_MISSION`).
  5. Type/lint the touched modules: `uv run mypy src/charter/activation/kind_vocabulary.py
     src/charter/activation/identity_index.py src/charter/activation/compiler.py
     src/charter/activation/action_governance_bundle.py` and
     `uv run ruff check src/charter/activation tests/architectural/test_charter_kind_vocabulary_public_scan_api.py`.
  6. Record each command and its result in the WP history
     (`spec-kitty agent tasks add-history WP01 --note "..."`).
- **Files**: no source edits; this subtask produces evidence.
- **Notes**: If a suite fails for a reason you cannot attribute to the rename, reproduce it
  on a clean `origin/main` worktree before concluding it is pre-existing, and say so.

## Test Strategy

- **Red first**: T001's ratchet must be observed failing before T002.
- **Behaviour pin, not new behaviour**: the existing scan-count, memoization, parity,
  identity-index and governance-bundle suites run with unchanged expectations. Do not
  relax, xfail or delete an assertion to make the rename pass.
- **Positive/negative control**: the ratchet's synthetic-snippet control proves the scanner
  can detect a retired name; the public-surface assertion proves the promotion happened.
- **Non-vacuity**: T008 step 2 is a manual cross-check of the same invariant the ratchet
  automates — if they disagree, the scanner is wrong.

## Definition of Done

- [ ] `tests/architectural/test_charter_kind_vocabulary_public_scan_api.py` exists, was
      recorded failing before T002, and passes at the tip with its positive and negative
      controls.
- [ ] All eight `kind_vocabulary` names are public, exported in `__all__`, and documented;
      the retired private names are deleted (no aliases).
- [ ] `IdentityIndex` uses only the public names and exposes `scan(kind)`.
- [ ] `load_action_governance_bundle` and `direct_root_urns` are public; their tests import
      the public names.
- [ ] No `src/`/`tests/` file references a retired name (except the unrelated lookalikes
      listed in T008 and `context.py`'s deliberate alias).
- [ ] `tests/charter`, `tests/charter_offering` and the charter CLI command tests pass;
      `make test-fast` passes; targeted `mypy`/`ruff` are clean.
- [ ] `docs/changelog/CHANGELOG.md` has an `[Unreleased]` entry with `(#6434)`.
- [ ] Every changed behaviour-free rename is visible in the commit message body.

## Risks & Reviewer Guidance

**Risks**: a rename that also changes evaluation order (must not); a test whose expected
scan count silently changes (must not); a ratchet that scans too broadly and flags unrelated
helpers (keep the anchored patterns); an over-eager `sed` that renames
`_iter_mission_scan_roots` or `catalog._resolve_scan_roots`.

**Reviewer focus**:

1. Diff the function bodies: only names and docstrings may change in
   `kind_vocabulary.py`, `identity_index.py`, `compiler.py`,
   `action_governance_bundle.py` — no logic, no reordering, no signature changes.
2. Confirm the tests changed only names and probe targets, not assertions or expected
   counts.
3. Confirm the ratchet is non-vacuous (negative control) and cannot pass on the pre-change
   tree (positive control).
4. Confirm no compatibility alias was left behind, and that the changelog does not claim a
   user-facing change.
5. Confirm the ratchet stays in the fast tier.
