---
work_package_id: WP14
title: Remove read-side shims; CLI-root legacy gate
dependencies:
- WP12
- WP13
requirement_refs:
- FR-011
- C-001
planning_base_branch: issue-3732-charter-pack-rename
merge_target_branch: issue-3732-charter-pack-rename
branch_strategy: Planning artifacts for this mission were generated on issue-3732-charter-pack-rename. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-3732-charter-pack-rename unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-charter-pack-cutover-01M491G6
base_commit: b068bc50f681dfc6394a41e5f80fecaa1a801448
created_at: '2026-10-07T21:39:29.546770+00:00'
subtasks:
- T070
- T071
- T072
- T073
- T074
phase: Phase 4 - Removal (no aliases, no shims)
history:
- at: '2026-10-06T19:30:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/migration/legacy_charter_gate.py
create_intent:
- src/specify_cli/migration/legacy_charter_gate.py
- tests/specify_cli/migration/test_legacy_charter_gate.py
- tests/charter/test_governance_fail_closed.py
execution_mode: code_change
owned_files:
- src/specify_cli/migration/legacy_charter_gate.py
- src/specify_cli/__init__.py
- src/charter/activation/sync.py
- src/charter/offering/drg/org_pack_config.py
- src/charter/activation/mission_type_profiles.py
- src/specify_cli/tracker/config.py
- src/specify_cli/tracker/local_service.py
- src/specify_cli/cli/commands/tracker.py
- tests/specify_cli/migration/test_legacy_charter_gate.py
- tests/charter/test_governance_fail_closed.py
- tests/charter/test_governance_key_compat.py
- tests/agent/cli/commands/test_tracker.py
- tests/tracker/test_config.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP14 – Remove read-side shims; CLI-root legacy gate

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

After WP18 lands, the `/ad-hoc-profile-load` skill is deleted: load profiles with `spk-charter-profile-load` instead (use whichever exists in your checkout).

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If the profile cannot be loaded, run `spec-kitty agent profile list` and pick the best match for `task_type: implement`.

---

## ⚠️ IMPORTANT: Review Feedback

- **Has review feedback?** Check the `review_ref` field in the event log (`spec-kitty agent tasks status`) or the Activity Log below.
- **You must address all feedback** before your work is complete.
- **Report progress** in the Activity Log as you address each item.

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the Activity Log below or in the status event log.]*

---

## Markdown Formatting

Wrap HTML/XML tags in backticks. Use language identifiers in code blocks.

---

## Objectives & Success Criteria

With the migration in place (WP11/WP12), every read-side fallback for the retired layout goes, and one seam at the CLI root refuses to run on an unmigrated project (FR-011, C-001):

- Removed: the `doctrine.org.*` and `organisation_packs` branches of `load_pack_registry` with `LegacyOrgPackDoctrineKeyWarning`; `apply_legacy_governance_selection_key_compat`, its private alias and `LegacyGovernanceKeyWarning`; the `.kittify/doctrine/` read fallback and `LegacyDoctrineRootWarning`; the tracker `doctrine` ownership key, `LegacyTrackerOwnershipKeyWarning`, `--doctrine-mode`, and the `doctrine_mode` JSON/human output.
- `spec-kitty <any command>` in a project (or the current checkout) where `detect_legacy_charter_layout` finds something exits 1 with code `LEGACY_CHARTER_STATE` and the contracts/cli.md message; `upgrade`, `init`, `--version`, `--help` still run.
- `load_governance_config` (and the two raw `governance` readers) fail closed on a legacy `governance.doctrine` key, naming `spec-kitty upgrade`; nothing is silently dropped.
- `PackContext.from_config` stays total (never raises because of a legacy key; it just no longer reads one).
- Shim tests are deleted, not adapted. Every WP01 test marked `pending_until("WP14")` (FR-011) is green.

## Context & Constraints

- `spec.md` FR-011, C-001, C-008, US2 scenario 5, Edge Cases ("Lane worktrees created before the upgrade").
- `contracts/cli.md` "Unmigrated project (FR-011)": exit **1**, code `LEGACY_CHARTER_STATE`, exact message text. (`research/runtime-seams.md` §3 proposed exit 4; the contract is the later artifact and wins. If WP01's acceptance test asserts a different code, the test is the contract (C-006): follow it and log the discrepancy.)
- `contracts/errors.md` (`LEGACY_CHARTER_STATE` payload: first finding, remedy text).
- `research/runtime-seams.md` §3 entire: root callback anatomy (`specify_cli/__init__.py:119-179`), exemptions, worktree root resolution, cost budget, "Where the legacy shapes are read today" table, and the required fail-closed governance load (`GovernanceConfig` has no `extra="forbid"`, `charter/activation/schemas.py:201-209`).
- WP11's `src/specify_cli/migration/legacy_charter_layout.py` (`detect_legacy_charter_layout(root) -> tuple[str, ...]`): reuse it; do not write a second predicate.
- Upstream: WP02 replaced `kernel/doctrine_root.py` with `kernel/charter_pack_paths.py` and carried the read fallback over as `resolve_project_pack_read_root` / `LEGACY_PROJECT_PACK_DIRNAME` / `LegacyDoctrineRootWarning`; WP02 and WP03 added further temporary legacy symbols that this WP deletes (T070 step 3 lists them all); WP10 removed the compat-helper call from `m_unify_charter_activation_finalize.py` (`:231,247`): confirm.

Constraints:

- **C-001**: deleted means deleted: no warning class kept "for external filtering", no hidden flag, no JSON key "for downstream consumers".
- **Version-bump rule**: CLAUDE.md "Any changes to `__init__.py` require a version bump in `pyproject.toml` and a `CHANGELOG.md` entry". Your edit to `src/specify_cli/__init__.py` triggers it. Per tasks.md "Version" (orchestrator ruling): no WP bumps the version (the cutover targets the current `4.0.0rc6`), and the rule is satisfied by the changelog entry. Keep the edit to one call and add a CHANGELOG Unreleased line for the gate (WP24 owns the changelog Before/After).
- **Cost**: the gate runs on every invocation; it may add at most two `stat`s and one small read per checked root, never a YAML parse on the common path, never a `charter.*` import.
- Files owned by completed upstream WPs are logged follow-up edits: the kernel module, `analysis_inputs.py`, `cli/commands/_doctrine_collect.py` and `tests/architectural/dead_symbol_allowlist.yaml` (WP02), `synthesizer/reconcile.py` (WP03), the acceptance tests (WP01). `tests/doctrine/**` belongs to WP23 (a later directory rename): your edits there are logged too.
- **Neighbours**: WP15 runs after you (it depends on WP14) and leaves `_doctrine_collect.py` to you; WP17 (upstream) already renamed `CharterPackConfigError` → `ActiveCharterConfigError`; WP13 (upstream) edited a remediation string in `org_pack_config.py`. WP18 may run in a parallel lane: never edit a file it owns.
- Code style: ruff + mypy clean, complexity ≤ 15, no unexplained suppressions.
- Commit often (`refactor(charter)!: remove governance.doctrine compat shim (#3732)`), never push to `main`.

## Branch Strategy

- **Strategy**: lane-based; the lane is assigned in `lanes.json` by `spec-kitty agent mission finalize-tasks`.
- **Planning base branch**: `issue-3732-charter-pack-rename`
- **Merge target branch**: `issue-3732-charter-pack-rename`

> Populated automatically by `spec-kitty agent mission finalize-tasks`. Do not change manually.

## Red-first (C-006 / C-011)

First commit: remove the `pending_until("WP14")` strict-xfail markers in `tests/acceptance/charter_pack_cutover/` (`grep -rn 'pending_until("WP14")' tests/acceptance/charter_pack_cutover/`): legacy-state commands fail with `LEGACY_CHARTER_STATE`, the exempt commands run, legacy keys are no longer read, `--doctrine-mode` is unknown, `doctrine_mode` is absent from JSON. WP01's flip map assigns you all `test_fr011_*` in `test_cli_surface.py` (incl. `test_fr011_pack_context_from_config_total`) except `test_fr011_exempt_invocations`, which is unmarked (it passes at base; a regression guard that must stay green). The NFR-002 row "cr02 compat test deleted" belongs to WP16, which deletes `tests/architectural/test_lifted_cli_doctrine_charter_cr02_compat.py` with the doctrine group; do not touch it. Run, paste red output, change no assertion.

## Subtasks & Detailed Guidance

### Subtask T070 – Remove legacy key/path fallbacks and compat warnings

- **Dead-symbol debt surfaced by WP05**: drain the two `tests/architectural/dead_symbol_allowlist.yaml` entries `PackRegistry` and `save_pack_registry` (`src/charter/offering/drg/org_pack_config.py`): take them out of `__all__` if only tests and the module itself use them, or give them a real production caller; delete the allowlist entries (268 → 266).

- **Path-allowlist sites handed over by WP03** (analysis C1): repoint every remaining legacy-segment site through `kernel.charter_pack_paths` and delete its entry from `tests/architectural/charter_pack_path_allowlist.yaml`: `src/charter/activation/drg_activation.py:163`, `src/charter/activation/_drg_helpers.py:177`, `org_pack_loader.py:536`, `org_pack_discovery.py:158,269`, `mission_step_contracts/executor.py:583`, `cli/commands/_doctrine_collect.py:94,141,173` (verify paths; line numbers are from planning). Also the nested org layout `"doctrine/{}"` in `src/charter/activation/pack_manager.py` (same treatment as `kind_vocabulary.py`), and the looped built-in fallback candidates in `src/charter/activation/_doctrine_paths.py` and `src/specify_cli/tool_surface/providers/agent_profiles.py` (WP03 review: the gate learns the loop-then-join shape). WP14 leaves only entries whose drain owner is WP25, each named; WP25 closes the list empty. These files are owned by WP19/WP20 or unowned; editing them is allowed by the tasks.md cross-WP rule (they cannot run in parallel with WP14); log each.

- **Purpose**: the migration is now the only reader of legacy state.
- **Steps**:
  1. `src/charter/offering/drg/org_pack_config.py`:
     - In `load_pack_registry` (`:436-527`) delete the legacy-doctrine branch (`:505-508`) and the `organisation_packs` branch (`:509-517`); delete `_LEGACY_ORG_PACKS_KEY` (`:57`), `LegacyOrgPackDoctrineKeyWarning` (`:101-105`), `_warn_legacy_org_pack_doctrine_key_once` (`:109-126`), `_registry_from_legacy_organisation_packs` (`:695-721`); simplify `_registry_from_org_packs_block` (`:665-681`) to the canonical key only; update the docstring (no "Legacy read shapes" list) and the module's `__all__`.
     - `_build_legacy_single_pack` / `_LEGACY_DEFAULT_PACK_NAME` also serve the **canonical** `charter_packs.org.local_path` single-pack form (runtime-seams §3 table). The spec renames only the legacy form. Decide with evidence: if no test, doc or fixture uses the canonical single-pack form, delete it (C-001: it is a second shape for one concept) and let the WP11 migration's single-pack rewrite cover it (log the decision so WP11's rewrite is checked); otherwise keep it, rename the helper away from "legacy", and record why. Either way `ensure_pack_identity`'s `name == "default"` built-in special case (`:764`) must not misidentify an org pack: test it.
     - `strict=True` behaviour (`_require_well_shaped_org_config`) must not start rejecting a config just because a legacy key is present (the CLI gate owns that).
  2. `src/charter/activation/sync.py` (`:236-317`): delete `_LEGACY_GOVERNANCE_SELECTION_KEY`, `LegacyGovernanceKeyWarning`, `_warn_legacy_governance_key_once`, `apply_legacy_governance_selection_key_compat`, the private alias `_apply_legacy_governance_selection_key_compat`. T073 adds the fail-closed check.
  3. **Every temporary legacy symbol WP02 and WP03 introduced** (orchestrator decision, FI-B1/AR-S2). Inventory first, then delete each:
     - `resolve_project_pack_read_root`, `LEGACY_PROJECT_PACK_DIRNAME` and `LegacyDoctrineRootWarning` in `src/kernel/charter_pack_paths.py` (WP02 T011); repoint **every** `resolve_project_pack_read_root(..., quiet=True)` call site (about 25 read sites, WP02 T013/T014 and WP03 T016/T017) to `project_pack_root(repo_root)`;
     - the legacy half of the dual dirty-scope prefix in `charter_runtime/preflight/runner.py` `_DIRTY_SCOPE_PATHS` (WP02 T014);
     - the legacy comparison in `charter/offering/service.py:48` (`LEGACY_PROJECT_PACK_DIRNAME`, WP02 T013);
     - `_is_legacy_artifact_prefix` in `charter/activation/synthesizer/manifest.py` (WP03);
     - the `test_*_legacy_root_read_fallback` tests (WP03 T020);
     - the FR-016 path-authority gate's kernel legacy-segment exemption in `tests/architectural/test_charter_pack_path_authority.py`, and the two FR-016 allowlist entries assigned to WP14 (`kind_vocabulary.py:297`, `_doctrine_paths.py:32`; WP03 T019).

     Check: `git grep -n -e LEGACY_PROJECT_PACK_DIRNAME -e resolve_project_pack_read_root -e _is_legacy_artifact_prefix -e legacy_root_read_fallback -e LegacyDoctrineRootWarning -- src tests` returns nothing (except the cutover migration and `legacy_charter_layout.py`, which spell the legacy root on their own). Each file is owned by an upstream WP: logged follow-ups.
  4. `src/specify_cli/cli/commands/_doctrine_collect.py:1088` (`governance_block.get("charter") or governance_block.get("doctrine")`): canonical only, via the T073 helper.
  5. `tests/architectural/dead_symbol_allowlist.yaml`: remove the entries for every deleted symbol (`LegacyGovernanceKeyWarning` around `:268`, `:1219`; `LegacyOrgPackDoctrineKeyWarning` and the `kernel.doctrine_root` entries around `:310-323`; `LegacyTrackerOwnershipKeyWarning`). Shrink only.
  6. Prose that only describes the deleted shims (docstrings in `org_pack_loader.py:16,442`, `merge.py:558`, `_retired_activation.py:76`, `pack_context.py:747`) is FR-018/FR-010 territory; fix it only where it now states something false about behaviour, and log it.
- **Files**: `org_pack_config.py`, `sync.py`, `_doctrine_collect.py`, the kernel module and `reconcile.py` (follow-ups), `dead_symbol_allowlist.yaml`.
- **Parallel?**: yes, beside T071.

### Subtask T071 – Tracker CR-03 removal (`doctrine` key, `--doctrine-mode`, `doctrine_mode`)

- **Purpose**: canonical `ownership` only (spec FR-011; research §3 suggested keeping the key, the spec rules it out).
- **Steps**:
  1. `src/specify_cli/tracker/config.py`: delete `_LEGACY_OWNERSHIP_KEY` (`:39`), `LegacyTrackerOwnershipKeyWarning` (`:42-46`), `_warn_legacy_ownership_key_once` (`:49-65`), the legacy branch in `from_dict` (`:270-286`), and the key from `_KNOWN_KEYS` (`:233-237`). Consequence to check: a stale `doctrine` key would now be captured into `_extra` and written back on save; that is acceptable only because the CLI gate blocks unmigrated projects first; verify that the gate's predicate covers `tracker.doctrine` (WP11 added it), and add a test.
  2. `src/specify_cli/cli/commands/tracker.py`: delete the hidden `--doctrine-mode` option (`:704-709`) and its use (`:780-782`), the `_warn_legacy_ownership_key_once` import (`:33`); rename `_doctrine_modes()` (`:380`) to `_ownership_modes()`; the human status line `- doctrine_mode:` (`:974`) becomes `- ownership_mode:` reading `payload["ownership_mode"]`.
  3. `src/specify_cli/tracker/local_service.py:211-218`: delete `"doctrine_mode"` and its comment from the status payload.
  4. Tests: in `tests/agent/cli/commands/test_tracker.py` delete `test_tracker_doctrine_mode_alias_warns` (around `:588`) and the CR-03 comment block; add a test that `--doctrine-mode` exits 2 (unknown option) with a positive control that `--ownership-mode` binds. In `tests/tracker/test_config.py` (`:276-319`) the "pre-062 config with doctrine" fixtures: delete the legacy-read tests; keep any canonical-key test.
- **Files**: the three tracker sources and two test files.
- **Parallel?**: yes.

### Subtask T072 – CLI-root `LEGACY_CHARTER_STATE` gate

- **From WP17 review**: `activation_block._load_governance_activations` and `org_pack_discovery._load_doctrine_selection` still swallow `RetiredPackFieldError` on a first-load `charter context --no-mark-loaded` (a project `charter.yaml` with `doctrine_pack_id` silently drops the "Selected activations" block). Confirm the CLI-root gate refuses such a project first (the structural predicate covers `doctrine_pack_id`); either way make both helpers re-raise `RetiredPackFieldError` and add a test.

- **Purpose**: one detection seam, shared with the migration's `detect()` (research §3 decision).
- **Steps**:
  1. Create `src/specify_cli/migration/legacy_charter_gate.py`:
     - `LEGACY_CHARTER_STATE = "LEGACY_CHARTER_STATE"`; `EXEMPT_COMMANDS`: `upgrade`, `init`, every git merge driver (`merge-driver-*`, registered by `lanes/consolidation.py:66-136`; git runs them inside the checkout being merged, which is exactly the documented remedy for a pre-upgrade lane) and the hook entry points (the live-work and session-start hooks). These are git plumbing, not project commands (orchestrator decision, AR-S3; `contracts/cli.md` "Unmigrated project").
     - `check_legacy_charter_layout(project_root: Path, checkout_root: Path | None, *, invoked_subcommand: str | None, argv: Sequence[str]) -> None`: return immediately for exempt commands, for `--help`/`-h` anywhere in argv, for `--version`/`-v` (eager, normally already exited), and when `<root>/.kittify` is absent (reuse the same early return as `migration/gate.py:112-115`). Otherwise call `detect_legacy_charter_layout(project_root)` and, when `checkout_root` differs from `project_root`, on it too. On any finding: print the contracts/cli.md message to stderr with the first finding substituted, include the worktree sentence only when the finding came from a checkout that is not the main root, and `raise SystemExit(1)` (or the code WP01's test asserts).
     - Message source: one module constant; it names `spec-kitty upgrade` and `docs/migrations/charter-pack-cutover.md` (WP24 writes the runbook; do not create it here).
  2. Current checkout root: `locate_project_root()` returns the **main** root even inside a worktree (`core/paths.py:197-235`). Find the checkout root by walking from `Path.cwd()` up to the nearest `.git` entry (file or directory) without a subprocess; reuse a helper from `core/paths.py` (`is_worktree_context`, `_read_worktree_gitdir`) if one fits. Return `None` outside a git checkout.
  3. `src/specify_cli/__init__.py` `_run_startup_project_gates` (`:165-179`): after `check_schema_version(...)`, call the new function with `ctx.invoked_subcommand` and `sys.argv[1:]`. Keep the existing skips: `main_callback` already bypasses the gates for `upgrade_intent`, `defer_root_bootstrap`, the live-work hook and session-start (`:128-162`); those hook paths must keep exiting 0, so leave them ungated and say so in a comment.
  4. Do not add the check to `compat/safety.py`; the safety registry lets `status`, `doctor`, `migrate` and read-only `agent` commands through the **schema** gate, but FR-011 blocks every command except the exemptions.
- **Files**: `legacy_charter_gate.py`, `src/specify_cli/__init__.py`, `tests/specify_cli/migration/test_legacy_charter_gate.py`.
- **Tests**: CliRunner (or subprocess where the root callback needs real argv) for each finding kind → exit 1, code and runbook in stderr; `upgrade`, `init`, `--help`, `--version`, a `merge-driver-*` invocation and the hook entry points exit 0 on the same fixture; a migrated fixture passes (positive control); a lane-worktree checkout with `.kittify/doctrine/` while the main root is clean → refused with the worktree remedy; outside a project → no-op; a project whose `config.yaml` contains the word "doctrine" only in a comment → passes. Measure: the gate's own time on a clean project, median of 5, record it (NFR-style evidence; no hard timing assert unless under the `timing` marker).

### Subtask T073 – `load_governance_config` fails closed on legacy keys

- **Purpose**: without the shim, `GovernanceConfig` (no `extra="forbid"`) would silently drop a legacy `doctrine:` selection, losing the selected directives (research §3, "required, not optional").
- **Steps**:
  1. In `src/charter/activation/sync.py` add one helper, for example `require_canonical_governance(governance: Mapping[str, Any], *, source: Path) -> Mapping[str, Any]`, that raises the activation config error (`ActiveCharterConfigError`, WP17's name) when the mapping carries `doctrine`, with a message naming the file, the key, `spec-kitty upgrade` and the runbook. This is a validation diagnostic naming a replacement, which C-001 allows.
  2. Call it from `load_governance_config` (`sync.py:337-352`) before `GovernanceConfig.model_validate`, and from the two raw readers that used the compat function: `charter/activation/mission_type_profiles.py:68,1380` and `specify_cli/analysis_inputs.py:60-63` (they then read `.get("charter")` directly), and from `_doctrine_collect.py:1088` (T070 step 4).
  3. Check how callers handle the error: `mission create` and charter commands already render this exception class with its code (`agent/mission_create.py:542-552`, `charter/activate.py:103-111`); doctor-style diagnostics must report, not crash. Add a test per caller.
- **Files**: `sync.py`, `mission_type_profiles.py`, `analysis_inputs.py`, `_doctrine_collect.py`, `tests/charter/test_governance_fail_closed.py`.

### Subtask T074 – Delete shim tests; flip FR-011 xfails

- **Steps**:
  1. Delete: `tests/charter/test_governance_key_compat.py`; the legacy tests in `tests/doctrine/drg/test_org_pack_config_cr04_charter_packs.py` (`test_doctrine_org_packs_reads_with_warning`, `test_doctrine_org_packs_warns_only_once_per_process`, `test_charter_packs_wins_over_doctrine_org_when_both_present`); keep and retarget the canonical-key tests in that file (`test_charter_packs_org_packs_reads_without_warning`, save/round-trip) or delete the file if nothing canonical remains uncovered elsewhere. The kernel fallback tests (`tests/kernel/test_doctrine_root.py` or WP02's replacement): delete the legacy-root cases.
  2. Fixtures elsewhere that still **use** a legacy shape to set up an unrelated test (`git grep -n -e organisation_packs -e 'doctrine:' -e LegacyOrgPackDoctrineKeyWarning -- tests`; at planning time: `tests/runtime/test_bridge_io.py`, `tests/runtime/test_resolver_unit.py`, `tests/unit/mission_loader/test_command.py`, `tests/integration/test_*org*`, `tests/charter/test_org_drg_loader.py`, `tests/specify_cli/cli/commands/test_doctor_*`, …): convert the fixture to the canonical key. These files belong to no WP or to completed upstream WPs: logged follow-ups, one line each. Do not delete a test whose subject is not the shim.
  3. `tests/fixtures/mission_type_canonical/org_activated_custom_type/.kittify/config.yaml` comment mentions the legacy alias "still resolves": fix the comment.
  4. Run the WP14 acceptance tests: green.

## Test Strategy

```bash
make test-fast
uv run --frozen pytest tests/specify_cli/migration/test_legacy_charter_gate.py tests/charter/test_governance_fail_closed.py tests/agent/cli/commands/test_tracker.py tests/tracker/ -q
uv run --frozen pytest tests/acceptance/charter_pack_cutover/ -q
uv run --frozen pytest tests/charter/ tests/doctrine/ -q          # src/charter/offering/** changed
uv run --frozen pytest tests/specify_cli/migration/ tests/kernel/ tests/runtime/ tests/integration/test_org_pack_missing_path_hard_fails.py tests/integration/test_three_layer_drg_end_to_end.py -q
uv run --frozen pytest tests/specify_cli/cli/commands/ -k "doctor or charter or tracker" -q
uv run --frozen pytest tests/specify_cli/upgrade/migrations/test_charter_pack_cutover_keys.py -q      # migration still rewrites what the readers no longer read
uv run --frozen pytest tests/architectural/test_no_dead_symbols.py tests/architectural/test_dead_symbol_allowlist_contract.py tests/architectural/test_compat_shims.py tests/architectural/test_unregistered_shim_scanner.py tests/architectural/test_layer_rules.py tests/architectural/test_kernel_no_doctrine_import.py tests/architectural/test_ruff_format_enforcement.py -q
uv run --frozen pytest tests/architectural/test_no_legacy_terminology.py -q
uv run --frozen mypy src/specify_cli/migration/legacy_charter_gate.py src/specify_cli/__init__.py src/charter/activation/sync.py src/charter/offering/drg/org_pack_config.py src/specify_cli/tracker/ src/specify_cli/cli/commands/tracker.py src/specify_cli/analysis_inputs.py src/charter/activation/mission_type_profiles.py
uv run --frozen ruff check <touched files>
uv run --frozen ruff format --check --force-exclude <touched files>
```

Never bare `tests/architectural/` or `make test-full`. Classify unrelated reds per the CLAUDE.md baseline-red gotcha.

## Risks & Mitigations

- **Gate blocks a hook path** (exit non-zero in SessionStart/live-work): those paths stay ungated; tested.
- **Gate misses a stale lane worktree**: checkout-root check plus a worktree test.
- **Silent loss of governance selections**: fail-closed helper at every raw reader.
- **`PackContext.from_config` starts raising**: test that a legacy-only config yields an empty org registry, no exception.

## Definition of Done

- [ ] First commit removed only the WP14 markers; red output logged.
- [ ] Every shim, warning class, flag and JSON key listed in Objectives is gone; `git grep` for each name in `src/` returns nothing.
- [ ] CLI-root gate with exemptions, checkout-root check, contract message; latency recorded.
- [ ] Governance readers fail closed with a message naming `spec-kitty upgrade`.
- [ ] Shim tests deleted; fixtures converted; dead-symbol allowlist shrunk.
- [ ] No version bump (tasks.md "Version"); CHANGELOG Unreleased line for the gate added.
- [ ] T070 step 3 inventory grep returns nothing; every WP02/WP03 temporary legacy symbol deleted.
- [ ] All Test Strategy commands pass; mypy/ruff clean.

## Review Guidance

- Red-on-base → green-on-final for every `pending_until("WP14")` test.
- `git grep -n -e LegacyGovernanceKeyWarning -e LegacyOrgPackDoctrineKeyWarning -e LegacyDoctrineRootWarning -e LegacyTrackerOwnershipKeyWarning -e apply_legacy_governance_selection_key_compat -e doctrine-mode -e doctrine_mode -- src` → empty.
- Check the gate never imports `charter.*` and never parses YAML on a clean project.
- Check deleted tests tested only the shims; converted fixtures keep their original subject.
- Check `ensure_pack_identity` and the single-pack decision are tested and logged.
- Confirm mypy/ruff were run.

## Activity Log

> Entries in chronological order (oldest first). Format: `- YYYY-MM-DDTHH:MM:SSZ – <agent_id> – <action>`.

- 2026-10-06T19:30:00Z – system – Prompt created.
- 2026-10-07T23:40:00Z – claude (python-pedro) – Step 0 campsite (separate commits): census routed via charter.packs (3de779ea); DEFAULT_KIND_GATE derived from CORE_KIND_PLURALS (frozen value pinned by test_kind_gates); retired-field allowlist category drained (names out of __all__); PRESET_ID_UNRESOLVED names the unfetched org pack + `spec-kitty charter fetch` (same code); skill-catalog seam via resolve_builtin_skill_catalog (+_BUILTIN_ONLY_ALLOWED entry, rationale); test_context_noop_stability fixture -> .kittify/charter-packs. YAML writer emptied-mapping fix NOT done (follow-up).
- 2026-10-07T23:40:00Z – claude – Red-first 716552db: removed pending_until("WP14"); 59 failed / 4 passed (exempt invocations).
- 2026-10-07T23:40:00Z – claude – T072 47bf0250: CLI-root LEGACY_CHARTER_STATE gate (exit 1, contract text, worktree sentence for a checkout finding). NotADirectoryError classification: ABSENT in both _load_prefiltered and the retired-root lstat (.kittify as a file -> no finding). Gate median 0.035 ms (5 runs, clean project). Discrepancy logged: test_fr011_shims_removed expects exit 2 for `tracker status --doctrine-mode` on a legacy fixture while contracts/cli.md says every non-exempt command exits 1; test wins (C-006): unknown options report as Click usage errors first (tokenizer-only probe on the refusal path).
- 2026-10-07T23:40:00Z – claude – T071 e8097447: tracker doctrine key/--doctrine-mode/doctrine_mode removed.
- 2026-10-07T23:40:00Z – claude – T070/T073/T074 dbc79355: read shims deleted; single-pack decision: canonical charter_packs.org.local_path form deleted (no test/doc/fixture used it) -> config error naming packs[]; WP11 rewrite of the legacy doctrine.org single-pack form names the pack from local_path (never 'default'), checked. ensure_pack_identity keyed on 'built-in'. Nested <pack>/doctrine/<plural>/<layer> org layout and the repo-root doctrine/ candidate retired (FR-011 decision). rc5 _retired_activation reads the retired org keys itself (runs before rc6 rewrite).
- 2026-10-08T00:00:00Z – claude (python-pedro) – Review cycle 1 addressed (lane-n, all pushed):
  - B1 702af0f2: option (a) chosen — ActiveCharterConfigError.__str__ override dropped (shape unchanged per contracts/errors.md). Red: shape test + golden test_malformed_config_invalid_yaml (2 failed) -> green. Logged edit to WP01 acceptance test_fr011_load_governance_config_fails_closed: matches the code on str(), reads the remedy from .body.
  - B2 a7b6ea38: doctor doctrine reports a retired governance.doctrine in charter.yaml (org_drg.errors + org_drg.retired_governance_key {file,key,message}; human "Retired charter key" block; RC=1). False comment corrected (the gate never reads charter.yaml). Red 2 -> green.
  - Nested org layout / repo-root doctrine/ fallback ea922f6d: decision — retired (FR-011) but now loud: doctor doctrine org_drg.errors + org_drg.retired_layouts + "Retired layout" human block naming the flat layout and the runbook; no new error code. Detection in specify_cli.migration.legacy_charter_layout (FR-016 by-file exempt). Repo-root dir reported only where it used to be read. Red 3 -> green.
  - Fail-closed catalog bcf02dc7: _shipped_skill_names raises MigrationStateUnreadableError when no built-in skill catalog is found. Red -> green.
  - live-work narrowing 6f36f195: only `live-work hook` exempt; matrix/install/uninstall/watch gated (no merge/commit path calls them). Red 3 -> green.
  - Docstrings b0539355: org_pack_config save_pack_registry mention; rc5 ordering claim reworded.
  - Usage probe kept (contracts/cli.md amended by orchestrator).

## Carry-over from WP11 review (cycle 2, non-blocking)

- `specify_cli.migration.legacy_charter_layout._load_prefiltered` treats `NotADirectoryError` (e.g. `.kittify` is a regular file) as an unreadable config, while the retired-root `os.lstat` check treats the same error as "absent". Once the CLI-root gate (this WP) runs the predicate on every invocation, make the two agree (one classification for `NotADirectoryError`) and add a test with `.kittify` as a file. Record the chosen classification in the Activity Log.

## Carry-over from WP12 (approved)

- `test_context_noop_stability` setup errors: its fixture expects a tracked `.kittify/doctrine`, which WP11 moved to `.kittify/charter-packs`. Repoint it when you remove the legacy-root read paths (red at base since WP11; record it).
- The shared YAML writer (`render_yaml_document`, used by `prepare_activation_write`/`prepare_charter_yaml_section`) cannot render a mapping emptied of its last key; WP12 works around it by writing `{}` in `_charter_pack_cutover_resets.py`. If cheap, fix it at the writer and drop the workaround (logged out-of-ownership edit); otherwise record it as a follow-up.

## Carry-over from WP13 (step 0 — campsite repairs, separate commits, logged)

Red at WP13's base, introduced by approved WPs; fix first, red → green per gate file:
- `tests/architectural/test_doctrine_census.py` (3 tests): `charter.offering.packs.retired_fields` (WP17) has no DISPOSITION entry.
- `tests/architectural/test_charter_kind_vocabulary_single_authority.py::test_no_hand_authored_kind_vocabulary_literal_under_src`: hand-written `DEFAULT_KIND_GATE` literal in `src/specify_cli/upgrade/migrations/_charter_pack_cutover_snapshots.py` (WP12). It is frozen release data; derive it or exempt it only through the gate's existing frozen-snapshot mechanism if one exists — otherwise derive from `ArtifactKind` and assert equality with the frozen value in a test. Record the choice.
- `dead_symbol_allowlist.yaml` entries `category_c_charter_pack_cutover_retired_fields` (`RETIRED_PACK_FIELDS`, `RetiredField`): their rationale says they burn down at WP13, but the table is reached only through `reject_retired_fields`/`retired_field_errors` by design. Drain them (make the names private / drop from `__all__`) rather than re-word, as part of your dead-symbol drain.
- Operator wording (no new code): on a project that declares an org pack it has not fetched, `charter activate --preset minimal` refuses with `PRESET_ID_UNRESOLVED` saying ids "resolve nowhere". Make the reason name the declared-but-unfetched org pack and the remedy (fetch/sync the org pack), keeping the code.

Also from WP13: delete the legacy `doctrine.org.packs` warning in `org_pack_config.py` entirely (WP13 only changed its remedy text).
- `tests/architectural/test_skill_catalog_seam.py::test_nothing_outside_the_seam_builds_a_skill_registry`: `src/specify_cli/upgrade/migrations/_charter_pack_cutover_skills.py:~201` calls `SkillRegistry.from_package` directly (WP12). Route it through `resolve_project_skill_catalog` (or the seam's sanctioned entry) and keep WP12's skills tests green.
