# Plan research: runtime seams for the charter-pack cutover

Mission: `charter-pack-cutover-01M491G6`. Branch `issue-3732-charter-pack-rename`, package version `4.0.0rc6`.
Scope: FR-001, FR-005 to FR-012, FR-017 and US2. This document was produced read-only. No `.codegraph/` index exists, so the evidence comes from grep and reads.
Line numbers refer to the checkout as read on 2026-10-06.

---

## 1. Run-first migration (FR-012, C-008)

### 1.1 How migrations are selected and ordered today

| Step | Evidence | Behaviour |
|---|---|---|
| Discovery | `upgrade/migrations/__init__.py` `auto_discover_migrations()` | Imports every `m_*.py` through `pkgutil` in alphabetical order. **An ImportError in any module raises `MigrationDiscoveryError`, which blocks every upgrade.** It is called from `cli/commands/upgrade.py:1634` and from `compat/planner.py:95`. |
| Registry order | `upgrade/registry.py:64-71` `get_all()` | `sorted(..., key=Version(target_version))`. The sort is stable, so ties keep registration order, which is filename order. Same-version ordering already depends on this (for example `m_unify_charter_activation_finalize.py:42-52`). |
| Selection | `upgrade/registry.py:74-119` `get_applicable(from, to, project_path)` | Includes a migration when `from < target <= to`. Separately, when `target == from` **and** `detect()` is true, it is included too. That `detect()` runs once, at selection time (`:98-117`). |
| Callers of the selector | `runner.py:169`, `cli/commands/upgrade.py:1829` (`migrations_needed`, the plan and the "no migrations" branch), `upgrade.py:2016-2064` (planner JSON, dry-run parity), `upgrade/detector.py:72`, `compat/planner.py:709-716` | All of them must agree. `tests/compat/test_dry_run_parity.py` pins that they do. |
| Applying | `runner.py:225-246` | The runner goes through the list in order and **stops at the first failure** (`break`, `:246`). |
| Per migration | `runner.py:297-407` `_apply_migration` | (a) `metadata.has_migration(id)` → skip (`:314-321`). Only a `result == "success"` record counts (`metadata.py:258-267`). (b) `detect()` is false → record `skipped / "Not applicable"` (`:349-361`). (c) `can_apply()` is false → **failed** (`:364-372`). (d) `apply()` → record `success` or `failed` (`:397-405`). |
| Recording | `metadata.py:269-302` `record_migration` | The record is idempotent per `(id, result)`. It is persisted immediately (`runner.py:703-721`). |
| Version stamp | `runner.py:250`, `:723-750` | After a successful run, `version` and `schema_version` are stamped. On failure the pre-run stamp is restored (`VersionStamp`, `version_stamp_boundary` in `upgrade.py`). |
| Upper bound | `m_unify_charter_activation_finalize.py:36-40`, `tests/architectural/test_migration_chain_integrity.py:317-330` | A migration whose `target_version` is higher than the installed package version never runs. The chain's last target must be at least the `pyproject.toml` version. |
| Chain gate | `test_migration_chain_integrity.py:205-300` | The test walks `get_all()` and **fails on any backward step**. |
| Unused field | `migrations/base.py:93-95` `min_version` | It is declared, but nothing in `src/` reads it. |

### 1.2 Fresh install and already-at-head projects

- **Fresh `init`**: `cli/commands/init.py:1438-1447` stamps `version = __version__` and `schema_version`, and records **no** `applied_migrations`. On a later `upgrade`, `from == to`, so only migrations whose target is the current version and whose `detect()` is true are selected. The cutover's `detect()` is false on a fresh layout, so it is neither selected nor recorded.
- **Project at head with legacy content** (for example a merge brought `.kittify/doctrine/` back): if the cutover's `target_version` equals the stamped version, the `target == from && detect()` branch selects it. The cutover's `detect()` must therefore be **content-driven, never version-driven**.
- **Pre-cutover project**: selected through the version window as usual.

### 1.3 Options for running first

| Option | Verdict | Why |
|---|---|---|
| Low sentinel `target_version` (for example `0.0.1`) | Reject | It would be selected only for `unknown` (0.0.0) projects, or through same-version `detect()`. A project at 3.2.x would never get it. |
| Pre-phase hook in `MigrationRunner.upgrade` | Reject | The CLI computes `migrations_needed` itself (`upgrade.py:1829`). It skips the runner when that list is empty (`:1835-1843`) and prints the plan from it. The planner JSON and `detector.py` also select on their own. A runner-only hook would make the preview diverge from the run, and when the cutover is the only pending item it would never be called. |
| Dependency field (`runs_after` / `runs_before`) | Reject | The registry has no graph. A topological sort is more machinery than one ordering fact needs. |
| **`runs_first: bool` class attribute, applied in `get_applicable`** | **Recommend** | See the decision below. |

**Decision.**
- Add `runs_first: ClassVar[bool] = False` to `BaseMigration`.
- After `get_applicable` selects migrations as it does today, stable-partition the result: `[m for m in applicable if m.runs_first] + [m for m in applicable if not m.runs_first]`.
- Keep `get_all()` sorted by semver, so the chain-integrity gate is unchanged.
- In `register()`, reject a second `runs_first` class.
- Give the cutover `target_version` the release version: `4.0.0rc7`, bumped in the same mission. `4.0.0rc6` would also work, because selection is content-driven, but the bump keeps the chain test's terminal-version rule honest.
- Set `runs_on_worktrees = True`. Non-integrating worktrees are migrated and auto-committed on their own branch. Lane and coordination worktrees are skipped anyway (see §2).
- New tests:
  - `get_applicable("3.1.0", head)[0].migration_id == <cutover>`;
  - the same order from `detector.py` and the planner JSON;
  - a planted second `runs_first` class is refused.

**Rationale.**
- Every selector already funnels through `get_applicable`, so the preview, the dry run, the planner JSON and the real run stay identical with one change.
- The runner, including the worktree loop (`runner.py:437-441`, which filters the same list), needs no change.
- `_apply_migration` re-runs `detect()` at apply time (`runner.py:336`), so every later migration sees the post-cutover state.

**Residual.** Same-version migrations (`target == from`) still have `detect()` evaluated once at selection time, before the cutover runs (`registry.py:98-117`, documented in `m_3_2_x_normalize_activation_absence.py:78-89`). If one of them detects a legacy shape, it can be deselected. This applies only to projects stamped exactly at that migration's version, and the next `upgrade` picks it up.

**Alternatives.** Copy the legacy-aware readers into a migration-private helper that the older migrations import. This is the squad's alternative in `postspec-squad-architecture.md:111`. It keeps the old order, but leaves a second copy of every shim alive in `src/`, which the FR-018 gate would then have to allowlist.

### 1.4 Making the rc35 migration a recorded no-op

- **Decision.** Keep the module `m_3_2_0rc35_default_charter_pack.py`, the class and `migration_id = "3.2.0rc35_default_charter_pack"`. Delete the body:
  - drop the module-level `from specify_cli.charter_pack_registry import ...` (`:49-52`) and `_DEFAULT_YAML_PATH` (`:71-77`);
  - `detect()` returns `False`;
  - `can_apply()` returns `(False, "Superseded by the charter-pack cutover")`;
  - `apply()` returns `MigrationResult(success=True, warnings=[...])`.
- The runner then records it as `skipped / "Not applicable"` (`runner.py:349-361`).
- In-repo precedent: `m_2_1_2_fix_charter_doctrine_skill.py:1-24`, a stub that is "Superseded by 3.1.1_charter_rename".
- **Rationale.** Module-level imports of deleted modules break **discovery** of every migration, not just this one. Keeping the id preserves upgrade history for projects that already recorded it.
- **Alternative.** Delete the module. Rejected, because old metadata would then carry an unknown id; harmless, but the chain record is lost. The direct-call tests must also go: `tests/upgrade/test_m_3_2_0rc35_default_charter_pack.py`, plus the references in `tests/architectural/test_no_dead_modules.py` and `charter_path_literal_allowlist.yaml`.

### 1.5 Older migrations that break, or undo the cutover, after shim removal or FR-005/FR-008 deletions

| Migration (target) | Dependency | Failure mode | Required action |
|---|---|---|---|
| `m_3_2_0rc35_default_charter_pack` (3.2.0rc35) | top-level import of `specify_cli.charter_pack_registry` (`:49`); `default.yaml` path (`:71-77`, `:152-157`); `merge_pack_into_config` | **Discovery-wide ImportError** once FR-005 deletes the registry. `apply` fails without `default.yaml`, and if kept alive it would rewrite stale lists. | Recorded no-op (§1.4). |
| `m_unify_charter_activation` (3.2.6rc1) | **top-level** `from charter.activation.default_pack import load_default_pack_activation_ids` (`:59`); `promote_activations(..., default_ids=...)` (`:280-289`) | Discovery-wide ImportError after FR-005. On an absent key, promotion seeds the default list (`activation_engine.py:514-573`, "used only when a key is absent"). That **re-narrows keys the cutover just reset to absent.** Also, `cli/commands/charter/interview.py:75-127` imports `load_default_pack_ids` from this migration module. | Covered by FR-015. Promotion into an absent key becomes a no-op, because absent means all are effective (`artifact_kinds.py:247-258`, `pack_context.py:734-738`). Move `load_default_pack_ids` out of the migration module. |
| `m_3_2_x_normalize_activation_absence` (3.2.6rc1) | writes an explicit `[]` for every **absent** per-artifact key (module docstring `:1-23`; `detect`/`apply` `:365-420`) | **Conflicts with run-first.** On a pre-3.2.6 project, the cutover resets stale keys to absent, then this migration writes `[]`, which means "nothing activated". That breaks NFR-001 and US2 scenario 6. Its premise ("absence means nothing") is contradicted by today's runtime (`effective_when_absent == "all"`). Also: lazy `pack_manager.ACTIVATION_YAML_KEYS` (`:160`) needs repointing if FR-009 moves the module. | **Neutralise** (recorded no-op, like §1.4), or limit it to minting the `charter:` pointer. Flag this for the owner. Even outside this mission, its interaction with the stale-list reset is the NFR-001 pre-rc35 fixture's main hazard. |
| `m_unify_charter_activation_finalize` (3.2.6rc1) | lazy `from charter.activation.sync import apply_legacy_governance_selection_key_compat` (`:231`, used `:247`); lazy `pack_manager.ACTIVATION_YAML_KEYS` (`:124`) | ImportError at **apply** time (not discovery) on a project that still has a standalone legacy `governance.yaml`, once FR-011 deletes the compat function. | The cutover (run first) rewrites `governance.doctrine` → `governance.charter` in the standalone `governance.yaml` (spec inventory row "Governance selection"). Delete the compat call from the fold. Repoint the `ACTIVATION_YAML_KEYS` import with FR-009. |
| `m_2_1_2_fix_glossary_context_skill` (2.1.2) | reads `charter.offering/skills/spec-kitty-glossary-context/SKILL.md` (`:69-81`), deleted by FR-008 | `apply` returns `"Cannot locate canonical SKILL.md for glossary-context"`, so **pre-2.1.2 projects fail to upgrade**. | Recorded no-op stub. |
| `m_3_1_1_charter_rename` (3.1.1) | renames the project-level `spec-kitty-constitution-doctrine` skill directory to **`spec-kitty-charter-doctrine`** (`:407-433`). It reads no deleted source. | Runs **after** the cutover, so it re-creates a directory under a name FR-008 retires. Project-root retirement is driven by the manifest (§5), so this unmanaged directory is preserved forever. | Skip the rename when the target name is in `RETIRED_CANONICAL_SKILL_NAMES`, and delete the old directory instead. Alternatively, add `spec-kitty-constitution-doctrine` to the retired list as well. |
| `m_2_1_2_fix_runtime_next_skill`, `m_2_1_2_fix_orchestrator_api_skill`, `m_2_1_2_install_git_workflow_skill`, `m_2_1_2_install_mission_system_skill`, `m_3_2_0rc30_fix_runtime_next_result_default`, `m_3_2_0rc35_fix_prompt_file_workaround` | read `charter.offering/skills/spec-kitty-{runtime-next,orchestrator-api-operator,git-workflow,mission-system}/` | Not affected by OD-7's five deletions. They **will** break in the follow-up mission that folds the rest of the `spec-kitty-*` layer. | Record this for the follow-up. |
| `m_3_2_0rc35_activate_builtin_mission_types`, `m_3_2_6_retire_rtk_search_tooling`, `m_4_0_0rc5_retire_single_owner_doctrine_ids` | mention `default.yaml` in docstrings only (`:40-46`, `:5`, `:28`). The retire pair uses `_retired_activation._still_resolves_via_org_pack` → `load_pack_registry` (`_retired_activation.py:74-80`). | With run-first they read canonical `charter_packs.org.packs`. If the cutover had **not** run first, a legacy-key project would read an empty org registry and retire ids that are still resolvable through the org pack. | None beyond run-first. Docstrings are FR-018 territory. The snapshots must cover lists both before and after these rewrites, as the spec already requires. |
| `m_2_0_11_install_skills`, `m_2_1_1_repair_skill_pack`, `m_3_0_3_globalize_skill_pack`, `m_3_2_0rc35_spk_skill_pack` | install from `resolve_project_skill_catalog`. Project pack skills are read from `.kittify/doctrine/skills` (`skills/catalog.py:60`). | They read the old root unless FR-016 repoints the catalog. After the run-first move, the old root is gone. | FR-016 must land before or with FR-012 (C-008 already says so). |
| `m_3_2_7_heal_provenance_paths`, `m_4_0_0rc5_heal_template_set_provenance` | provenance sidecars and `charter.yaml` | The cutover rewrites provenance paths first. These heal built-in-pack paths only. | Fixture: an rc5 project with synthesized artifacts. |

---

## 2. Worktree upgrade and `approved_bound`

**What `spec-kitty upgrade` does to worktrees.**
- `upgrade.py:1650`: `--no-worktrees` skips worktrees. Otherwise `runner.upgrade(..., include_worktrees=True, auto_commit=should_auto_commit_for_worktree(...))` (`upgrade.py:1864-1870`).
- `runner.py:81-112` (#5457): **integrating worktrees are skipped entirely**. An integrating worktree is one whose branch parses as a mission, lane or coordination branch, or whose HEAD is detached. Nothing is written, stamped or committed in it. Lanes get project-global state "by integration".
  - Consequence: the squad's premise in `postspec-squad-testability.md:127` ("upgrade migrates worktrees and auto-commits onto lane branches") is **outdated**. In-flight lane and coordination worktrees, including this mission's own `.worktrees/charter-pack-cutover-01M491G6-coord`, keep `.kittify/doctrine/` and legacy keys until they integrate.
  - Only non-integrating worktrees under `.worktrees/` (plain directories, or non-mission branches) are migrated. The runner auto-commits them on their own branch when the project's `auto_commit` is on (`autocommit.py:189-200`), restricted to a porcelain diff against the pre-write baseline (`runner.py:478`, `:610-623`).
- The main checkout is committed by the finalizer only when `auto_commit` is configured (`autocommit.py:174-186`). This repository has `auto_commit: false` (`.kittify/config.yaml`).
- A directory move should be reported through `autocommit.record_upgrade_mutation(src, dst, is_move=True)` (`:94-106`) so the commit owns the moved files. Files dirty at baseline are never swept (`:242-284`). That matches the spec's "uncommitted edits carried over, operator commits".

**Is a `.kittify/`-only lane commit after approval exempt from `approved_bound`?**
**Yes, for `.kittify/` paths only.**
- `approved_bound.check_lane` (`consolidation/approved_bound.py:349-394`) refuses only commits returned by `content_commits` (`:323-337`). `content_commits` drops merge commits and every commit whose changed paths are all bookkeeping.
- The predicate is `reconciliation._is_bookkeeping` (`reconciliation.py:1197-1281`): any path equal to repo-root `.kittify/` or starting with `.kittify/` (`:1277-1278`) counts as bookkeeping. So `.kittify/doctrine/** → .kittify/charter-packs/**`, `config.yaml`, `charter.yaml` and the manifests are exempt.
- **Not exempt:** `.gitignore` (FR-012 rewrites its `.kittify/doctrine/**` rules), anything in agent directories (`.claude/`, `.agents/` and so on, when tracked), and `CLAUDE.md`/`AGENTS.md`. A lane commit after approval that touches any of these refuses with `LANE_MOVED_AFTER_APPROVAL`.
- **Rebasing** a lane onto the upgraded target rewrites its commits, so the approval stamps leave the lane: `APPROVAL_STAMP_NOT_ON_LANE` (`approved_bound.py:375-377`).
- **Merging** the upgraded target into the lane is safe:
  - the merge commit is skipped (`content_commits`);
  - the target's commits are excluded by the claim base (`commits_beyond(..., [claim_base, *stamps])`).

**Decision.**
- The runbook (FR-017) and the FR-011 worktree message say: *"merge (not rebase) the upgraded target branch into the lane, or finish and consolidate the mission before upgrading."*
- Do not make the cutover migration touch integrating worktrees; #5457's invariant stands.
- Do not widen `_is_bookkeeping` to cover `.gitignore`. That width is already a recorded residual in CLAUDE.md.

**Alternative.** Have `upgrade` refuse while live lanes exist (consumer squad S2). This is stricter and wedges in-flight missions; offer it as a `--dry-run` warning at most.

---

## 3. Detection seam for unmigrated projects (FR-011)

**Where the root callback lives.**
- `specify_cli/__init__.py:119-163` `main_callback`. `--version` is an eager option (`:121-123` → `version_callback`, `:100-116`), so it exits before the callback body.
- The body short-circuits for `upgrade_intent` (`:128-131`) and `defer_root_bootstrap` (`:133-135`).
- Global asset repair (`ensure_runtime`, `ensure_global_agent_skills`, `ensure_global_agent_commands`) runs for every invocation except the `next`, live-work-hook and session-start fast paths (`:137-152`).
- It then calls `_run_startup_project_gates(ctx)` (`:154-162`, `:165-179`). That function already hosts the **schema-version gate**: `migration/gate.py:89-154` `check_schema_version` → `compat.planner.plan` → `BLOCK_PROJECT_MIGRATION`, exit 4, a message naming `spec-kitty upgrade`.
  - It is skipped when `.kittify/` is absent (`gate.py:112-115`) or the command is in `_EXEMPT_COMMANDS = {"upgrade", "init"}`.
  - Help and version are allowed by the planner (`planner.py:393-395`).
  - The safety registry (`compat/safety.py:105-133`) also marks `migrate`, `status`, `doctor`, `help`, `version` and a few `agent` read-only commands as SAFE.

**Commands that run without a project.** `locate_project_root()` returns `None`, so the gates are skipped (`__init__.py:170-179`). This covers `init`, `upgrade --cli`, `--version`, `--help` and any command used outside a repository. There is one caveat: `SPECIFY_REPO_ROOT` returns a directory even without `.kittify/` (`core/paths.py:241-247`). The existing `.kittify/` early return covers that case, and the new check must reuse it.

**Root resolution and worktrees.** `locate_project_root` returns the **main** repository root even inside a worktree (`core/paths.py:197-235`). A seam that checks only that root does not see a stale lane worktree. The spec's edge case says an unmigrated worktree hits the error, which means the current checkout root (the git top level of the working directory) must also be checked. That is one extra `stat`.

**Decision.**
- Add one function, `detect_legacy_charter_layout(root: Path) -> tuple[str, ...]`, in a light module with no `charter.*` import (for example `specify_cli/migration/legacy_charter_layout.py`). It returns the names of the legacy shapes found.
- Call it from `_run_startup_project_gates`, immediately after `check_schema_version`, for the main root and for the current checkout root when that differs.
- Raise on any hit, unless the command is `upgrade` or `init`, or the invocation is `--version` or `--help`.
  - **Clarification for the owner:** the spec lists only `upgrade`, `init` and `--version`. The planner always allows `--help`, so keep it allowed.
- Exit code 4, the same as `BLOCK_PROJECT_MIGRATION`.
- The message names `spec-kitty upgrade`, `docs/migrations/charter-pack-cutover.md`, and for a worktree hit the merge-not-rebase remedy from §2.
- The cutover migration's `detect()` calls the same function, plus the non-structural checks (stale lists, skills, provenance), so the gate and the migration cannot disagree.
- Structural shapes it checks, cheapest first:
  1. `stat(.kittify/doctrine)`;
  2. `stat(.kittify/charter/governance.yaml)` (the standalone legacy file);
  3. read the bytes of `.kittify/config.yaml` (about 1 KB here). Apply a substring prefilter for `doctrine` / `organisation_packs`, and only on a hit run `yaml.safe_load` and test the top-level `doctrine.org`, `organisation_packs` and `governance.doctrine` keys.
- Do **not** read `charter.yaml` on every invocation. In this repository it is 154,952 bytes and contains 24 `doctrine` substrings (profile ids and summaries), so a prefilter does not help. Handle `governance.doctrine` inside `charter.yaml` at its only read site instead. `charter.activation.sync.load_governance_config` (`sync.py:337-352`) should raise the renamed config error naming `spec-kitty upgrade` when the `governance` mapping carries `doctrine`.
  - **This is required, not optional.** `GovernanceConfig` (`charter/activation/schemas.py:201-209`) has no `extra="forbid"`. Once the compat shim is removed, a legacy `doctrine:` selection would be **silently dropped** and the selected directives lost.
- Cost: two `stat` calls plus one ~1 KB read on the common path, with no YAML parse. That is well under the existing gate's `metadata.yaml` read.

**Rationale.** The seam reuses the existing gate slot, exemption vocabulary and exit-code family. It is content-driven (it catches a legacy shape reintroduced by a merge) and costs nothing measurable.

**Alternatives.**
- (a) Bump `MIN/MAX_SUPPORTED_SCHEMA` 3→4 (`migration/schema_version.py:22-27`). This needs no extra I/O, and older CLIs would get `BLOCK_CLI_UPGRADE` on migrated projects, a useful side effect. However:
  - the safety registry lets `status`, `doctor`, `migrate` and `agent …` read-only commands through, which conflicts with "every command except upgrade/init/--version";
  - it detects a stamp, not content;
  - it touches 14 test files with `schema_version: 3` and 28 that import the constants.
  - It is a reasonable **addition** to the content check, but not a replacement for it.
- (b) A Typer group-level callback check. It sits outside the gate slot and would duplicate the exemption logic.

**Where the legacy shapes are read today (functions to delete or repoint).**

| Shape | Reader (file:line) |
|---|---|
| `doctrine.org.packs` / `doctrine.org.local_path` | `charter/offering/drg/org_pack_config.py:436-527` `load_pack_registry`. The legacy branch (`:505-508`) calls `_registry_from_org_packs_block(data, "doctrine")` (`:665-681`), with `_LEGACY_ORG_PACKS_KEY` (`:57`), `LegacyOrgPackDoctrineKeyWarning` (`:101`) and `_warn_legacy_org_pack_doctrine_key_once` (`:109-126`). `_build_legacy_single_pack` (`:684-692`) also serves the **canonical** `charter_packs.org.local_path` single-pack form, auto-named `default`. Decide whether the canonical single-pack form stays: the spec renames only the legacy form, and the name `default` collides with the preset. |
| `organisation_packs` | `org_pack_config.py:509-517` and `_registry_from_legacy_organisation_packs` (`:695-721`). Consumers reach it only through `load_pack_registry`: `charter/activation/pack_context.py:743-760` `_read_org_packs`, `org_pack_loader.py`, and `upgrade/migrations/_retired_activation.py:74-80`. |
| `governance.doctrine` | `charter/activation/sync.py:244` `_LEGACY_GOVERNANCE_SELECTION_KEY`; `:248` `LegacyGovernanceKeyWarning`; `:277-310` `apply_legacy_governance_selection_key_compat`; `:317` the private alias; called at `:351` `load_governance_config`. Other callers: `charter/activation/mission_type_profiles.py:68,1380`; `specify_cli/analysis_inputs.py:60-63`; `upgrade/migrations/m_unify_charter_activation_finalize.py:231,247`; plus a direct fallback in `cli/commands/_doctrine_collect.py:1088` (`governance_block.get("charter") or governance_block.get("doctrine")`). |
| `.kittify/doctrine/` (read fallback) | `kernel/doctrine_root.py:76-104` `resolve_doctrine_read_root`, `LegacyDoctrineRootWarning` (`:49`); its only caller is `charter/activation/synthesizer/reconcile.py:612`. **Note:** the old root is not just a fallback. It is the **live** read *and write* root at about 25 hard-coded joins, for example `synthesizer/write_pipeline.py:40,70` (writes), `doctrine_synthesizer/apply.py:195` (writes), `synthesizer/project_drg.py:460`, `resynthesize_pipeline.py:370,453,482`, `offering/drg/project_scan.py:73,200`, `skills/catalog.py:60`, `review/gate_bindings.py:74`, `runtime/next/runtime_bridge_composition.py:286`, `mission_step_contracts/executor.py:176`, `charter/_layer_roots.py:21`, `_fresh_doctrine.py:108,147,157`, `_status_collectors.py:211`, `profiles_cmd.py:105`, `calibration/walker.py:347,395`, `glossary/entity_pages.py:72`, `charter_runtime/lint/_drg.py:51`, `_drg_helpers.py:196`, `kind_vocabulary.py:295`, `pack_manager.py:288`, `mission_type_profile_repository.py:52`, `_doctrine_collect.py:244,352,616,1175`, `doctrine.py:650`. That is FR-016's inventory. CI also filters on it: `.github/workflows/ci-router.yml:233`. `.kittify/charter-packs` appears in `src/` only in `kernel/doctrine_root.py:46`. |
| Unrelated "doctrine" key, keep | `specify_cli/tracker/config.py:10` `_LEGACY_OWNERSHIP_KEY = "doctrine"` (tracker field ownership; its own comment says it is distinct from the charter rename). Add it to the occurrence map as out of scope. |

---

## 4. The `spec-kitty doctrine` group (FR-006/FR-007)

The group is registered as a hidden, deprecated alias (`cli/commands/__init__.py:234-251`, registrar map `:628`). Its app callback prints a deprecation notice (`doctrine.py:88-99`). The notice is not attached to `org_app`, so `charter org` does not print it.

| Old leaf | Handler (file:line) | Already under `charter`? | FR-006 home |
|---|---|---|---|
| `doctrine fetch` | `doctrine.py:132` `fetch` | yes, same handler: `charter/_app.py:27,77` | `charter fetch` (move the handler out of `doctrine.py`) |
| `doctrine new` | `doctrine.py:653` `new` | yes `_app.py:75` | `charter new` |
| `doctrine validate` | `doctrine.py:841` `validate` | yes `_app.py:76` | `charter validate` |
| `doctrine org init` | `doctrine.py:956` `org_init` (on `org_app`) | yes, `org_app` re-added `_app.py:78` | `charter org init` |
| `doctrine org validate` | `doctrine.py:1092` `org_validate` | yes (same `org_app`) | `charter org validate` |
| `doctrine pack validate` | `doctrine.py:398` `pack_validate` | no | `charter pack validate` |
| `doctrine pack assemble` | `doctrine.py:428` `pack_assemble` | no | `charter pack assemble` |
| `doctrine regenerate-graph [--check]` | `doctrine.py:251` `regenerate_graph` | no | `charter pack regenerate-graph [--check]` |
| `doctrine asset list` | `_doctrine_asset.py:125` | no | `charter pack asset list` |
| `doctrine asset path` | `_doctrine_asset.py:158` | no | `charter pack asset path` |
| `doctrine mission-type list` | `doctrine.py:1141` `mission_type_list` | equivalent: `charter/mission_type.py:195` with `--include-inactive` (`:203-212`) | `charter mission-type list --include-inactive` |
| (charter) `pack consistency-check` | `charter/pack.py:37` | n/a | `charter consistency-check` (OD-8) |
| (charter) `pack path <name>` | `charter/pack.py:262` (argument "Built-in pack name (e.g. 'default', 'minimal')") | n/a | takes a **pack** name (FR-006) |
| (charter) `pack apply` | `charter/pack.py:279` | n/a | removed (FR-005); replaced by `charter activate --preset` (FR-001) |

**In-repo callers of the old spellings, outside historical roots.** Excluded: `kitty-specs/`, `docs/adr/`, `docs/reports/`, `docs/plans/`, `docs/archive/`, `.kittify/evidence/`, released changelog sections, and the stale agent copies under `.claude/worktrees/`.

- **CI**: `.github/workflows/packs.yml:225` (`uv run --frozen spec-kitty doctrine regenerate-graph --check`), `:229` (error remediation string); `:22`, `:213` (prose/job name).
- **Makefile**: `:47` (comment naming `spec-kitty doctrine asset path`).
- **Pack manifest**: `packs/built-in/pack-manifest.yaml:1377` `generated_by: spec-kitty doctrine regenerate-graph`. This line is written from `specify_cli/doctrine/builtin_manifest.py:48` `GENERATED_BY`. Change the constant, then regenerate. Do not hand-edit the manifest: `tests/architectural/test_pack_manifest_no_author_edit.py` would flag it.
- **CLAUDE.md** (a symlink to `AGENTS.md`): `:49` (`run spec-kitty doctrine regenerate-graph`), `:648` (`spec-kitty doctor doctrine --json`).
- **packs/internal**: `README.md:83`; `assets/test-quality-scan.py:35,39,40`; `procedures/executive-debrief-generation.procedure.yaml:47`; `procedures/test-suite-quality-assessment.procedure.yaml:47`; `skills/report-debrief.skill.md:16`; `toolguides/TEST_QUALITY_TRIAGE.md:36`; `toolguides/test-quality-triage.toolguide.yaml:21`.
- **packs/built-in**: `styleguides/common-docs.styleguide.yaml` (5), `tactics/common-docs-write.tactic.yaml` (3), `tactics/common-docs-find.tactic.yaml` (2), `tactics/common-docs-scaffold.tactic.yaml`, `directives/042-common-docs.directive.yaml`, `assets/docs_structural_lint.py` (2), `assets/docs_structural_lint.config.yaml`, `agent_profiles/doctrine-daphne.agent.yaml`. These need individual triage, because some hits are the prose "doctrine asset(s)".
- **src (strings/remediation)**:
  - `cli/commands/doctrine.py` (20; it is deleted);
  - `_doctrine_asset.py` (6);
  - `charter/mission_type.py` (3, help text pointing at `doctrine mission-type list`);
  - `cli/commands/mission_type.py:1695`;
  - `cli/commands/regen.py:17`;
  - `charter/offering/drg/migration/hand_authored_overlay.py:22,2027`;
  - `cli/commands/__init__.py:236-251`;
  - `_completion_manifest.json` (7; regenerate with `python -m specify_cli.completion --regenerate`, gate `tests/architectural/test_completion_manifest_freshness.py`).
- **docs (living)**:
  - `docs/api/cli-commands.md` (40), `docs/development/docs-retrieval-index.yaml` (17);
  - `docs/guides/how-to/governance/create-an-org-doctrine-pack.md` (8), `docs/migrations/doctrine-local-overlay-to-org-layer.md` (4);
  - `docs/development/how-to/create-a-doctrine-artifact.md` (3), `docs/architecture/doctrine-kinds.md` (3);
  - one each in `docs/context/charter.md`, `docs/architecture/org-doctrine-layer.md`, `docs/architecture/diagrams/03_components/README.md`, `docs/convergence/charter-fetch.md`, `docs/development/reference/ci-gate-mechanics.md`, `docs/development/reference/terminology-exemptions.md`, `docs/api/skills/spk-admin-setup-doctor.md`;
  - `docs/changelog/release-notes-3.2.6.md` (released, so historical);
  - `research-outputs/governance-at-the-gate/*` (decide whether this is a historical root).
- **This repository's `.kittify`**: `.kittify/charter/charter.md`, which is consumer-generated prose and out of scope per the FR-018 note.
- **Tests**: 69 files mention the group (`git grep` over `tests/`). The main ones are `tests/cli/test_doctrine_commands.py`, `tests/cli/test_doctrine_org_commands.py`, `tests/specify_cli/cli/commands/test_doctrine_{new,asset,regenerate_graph,hard_fail_surfacing}.py`, and the architectural gates `test_lifted_cli_doctrine_charter_cr02_compat.py`, `test_lifted_cli_doctrine_retirement.py`, `test_no_deprecated_doctrine_command_in_guidance.py`, `test_doctrine_regenerate_graph_roundtrip.py` and `test_docs_cli_reference_parity.py`.

**`spec-kitty doctor doctrine`** (`cli/commands/doctor.py:1077-1180`, renderers in `_profile_health_render.py:102-262`).
- It reports org-pack snapshot health per configured pack (version, artifact counts, `org-charter.yaml` policy), profile, skill and glossary-pack load health, sanctioned and unsanctioned built-in overrides, cross-grain collisions, operating-procedure resolution, and the Selections block.
- Exit code 1 when the report is unhealthy.
- JSON keys:
  - top level (`_profile_health_render.py:222-233`): `org_configured`, `packs[]`, `selections`, `org_drg`, `profile_health`, and `collisions` when org packs are configured;
  - `packs[]` entries: `name`, `local_path`, `source_type`, `url`, `ref`, `snapshot_present`;
  - `profile_health`: `report.to_dict()` from `_doctrine_health.py:231`, with keys including `healthy`, `discovered_count`, `valid_count`, `invalid_profiles`, `invalid_packs`, `invalid_skills`, `skills`, `skill_count`, `glossary_packs`, `term_count`, `packs`, `pack_count`, `pack_id`, `org`, `project`, `org_drg`, `layer`, `path`, `error_summary`, `loaded`, `skipped`.
- The no-packs text says "No org doctrine configured."
- **Recommendation:** rename it to `spec-kitty doctor charter-packs`. `doctor charter` would read as the active charter, and `charter status` already covers that. Keep the JSON keys, which are neutral, except that `org_drg` stays (DRG is not retired vocabulary). Reword the human strings ("No org charter packs configured"). Add the change to the FR-017 Before/After table.
- **Callers:** 30 test files; `create-an-org-doctrine-pack.md` (11), `org-doctrine-layer.md` (8), `docs-retrieval-index.yaml` (4), `cli-commands.md` (4), `packs/built-in/procedures/onboard-external-agent-to-pack.procedure.yaml` (3), `create-a-pack-skill.md` (2), `doctrine-local-overlay-to-org-layer.md` (2), and remediation strings in `charter/offering/drg/{merge,validator,override_policy}.py`, `agent_profiles/operating_procedures.py`, `kind_vocabulary.py`, `drg_activation.py`, `activation_engine.py`, `action_grain.py`, `artifact_kinds.py`, `specify_cli/doctrine/{snapshot,pack_validator}.py`, `_cutover_doctor.py`, `charter/_status_collectors.py`, and `AGENTS.md:648`.
- **Alternative:** leave `doctor doctrine` as is and put it on the FR-018 allowlist. This is weaker, because the consumer squad named it as a visible gap (`postspec-squad-consumer.md:142`).

---

## 5. Skill retirement (FR-008)

- **The name list.** `skills/retired.py:9-16` `RETIRED_CANONICAL_SKILL_NAMES` is the canonical set plus `RETIRED_STANDALONE_SKILL_NAMES`.
- **User-global roots: name-based, on every CLI run.**
  - `specify_cli/__init__.py:144-150` calls `ensure_global_agent_skills()` for every invocation except the `next`, live-work-hook, session-start and upgrade-intent paths.
  - That function (`runtime/agent_skills.py:237-260`) assesses with `selection=None`.
  - In `assess_global_agent_skills` (`:196-206`), every existing directory under each global skill root that is not in the shipped catalog is **retired when its name is in `RETIRED_CANONICAL_SKILL_NAMES`**. Otherwise it is preserved as an "Unproven custom skill".
  - So adding the five folded names plus the seven `spk-doctrine-*` names to the set removes them from `~/.claude/skills` and similar roots on the next CLI run after the install. No upgrade is needed.
- **Project roots: manifest-based, at upgrade or init.**
  - `skills/installer.py:757-775` `_retirable_paths` and `:786-861` `_prepare_project_skills`: entries in `.kittify/skills-manifest.json` whose path the current catalog no longer expects are retired when `retire=True`. A file edited by the user is backed up first (`:833-855`).
  - `RETIRED_CANONICAL_SKILL_NAMES` is **not** consulted for project roots, except in `m_3_2_0rc35_spk_skill_pack.py:151`.
  - The project manifest is regenerated by the upgrade finalizer's surface repair: `upgrade/assessment.py:121-139` `prepare_upgrade_repairs` → `assess_skill_installation(..., resolve_project_skill_catalog(...))`, where `retire` defaults to True. It is also regenerated by `install_all_skills` (`installer.py:335-342`) in the skill migrations, and by `init` (`init.py:336`, `:1137`, which uses `install_skills_for_agent` with `retire=False`).
  - A project directory that has **no** manifest entry is never retired. Examples: a hand-copied skill, or the `spec-kitty-charter-doctrine` directory recreated by `m_3_1_1` (§1.5).
- **Command-skill manifest.** `.kittify/command-skills-manifest.json` (`skills/command_installer.py:392`, `manifest_store.py`) tracks `spec-kitty.<command>` command skills. They are written by `command_installer.install` (`init.py:155`, `agent/config.py:188`, `_command_surface_doctor.py:329`) and pruned by `prune_stale` (`:1135`). **None of the FR-008 names is a command skill**, so this manifest changes only if a slash command is renamed, and FR-006 renames none.
- **Decision.**
  - (a) Add every removed skill id to `RETIRED_CANONICAL_SKILL_NAMES` (global roots, every run).
  - (b) Rely on the finalizer's manifest reconciliation for project roots. Do **not** reimplement skill removal inside the cutover migration; that would create a second writer next to the installer that owns those files.
  - (c) Handle the manifest gap by adding an explicit step to the cutover migration. The step removes project directories named in the retired set **only when the content hash matches a shipped version**, the same idea as `m_2_1_2_remove_release_skill.py:60`. Unmanaged copies with any other hash are kept and listed in the summary as kept-for-review.
  - (d) Neutralise `m_2_1_2_fix_glossary_context_skill` and patch `m_3_1_1` (§1.5).
- **This repository.**
  - Generated agent copies are git-ignored (`.gitignore:50,80,84,130-136`: `.codex/`, `.claude/`, `.agents/`, `.cursor/`, `.kittify/skills-manifest.json`, `.kittify/command-skills-manifest.json`). The only tracked copies are the four `spec-kitty-standalone.md` files (`.cursor/commands`, `.gemini/commands`, `.github/prompts`, `.opencode/command`); they reference `src/doctrine/skills/spec-kitty/SKILL.md`, a stale path that is not an FR-008 name.
  - Tracked derived surfaces to regenerate or edit:
    - `docs/api/skills/spk-doctrine-profile-load.md` (rename it) and `docs/api/skills/index.md`;
    - `src/specify_cli/_completion_manifest.json` (`python -m specify_cli.completion --regenerate`);
    - the canonical command baseline and skill snapshot (`spec-kitty regen`, `cli/commands/regen.py`);
    - `packs/built-in/pack-manifest.yaml` (`charter pack regenerate-graph` after the rename, if any pack references the skills).
  - Local, untracked agent copies are refreshed with `spec-kitty upgrade` (finalizer surface repair) or `spec-kitty agent config sync`. User-global copies are refreshed on any CLI run.
  - Ignore `.claude/worktrees/agent-*`: these are stale sub-agent checkouts, and any FR-018 scan must exclude them.

---

## 6. Error-code contract (FR-009)

**Emitters of `CHARTER_PACK_CONFIG_INVALID` and `CharterPackConfigError`.**
- Definition: `charter/activation/pack_context.py:63-67`, a `KittyInternalConsistencyError` with code `"CHARTER_PACK_CONFIG_INVALID"`. It is exported in `__all__` at `:40`.
- Raised by:
  - `pack_context.py:294-300` `_config_error`;
  - `pack_manager.py:651,659`;
  - `consistency_check.py:309,337,341,343`;
  - `scope.py:265`;
  - `default_pack.py:150` (deleted by FR-005);
  - `specify_cli/core/mission_creation_scaffold.py:142`.
- The JSON code **literal** appears in `charter/mission_type.py:143` (`mission_type_error_boundary`, `json_error(code, …)`).
- `error_code: exc.code` is emitted by `agent/mission_create.py:542-552` and by the generic `KittyInternalConsistencyError` renderers in `charter/synthesize.py:684-695` and `charter/list_cmd.py:331-341` (`f"{e.code}: {e.body}"`).
- `charter/activate.py:103-111` `render_pack_config_error` calls the code a "stable diagnostic code" (`:106`).

**Catchers by class name** (each needs the rename):
- `runtime/next/decision.py:28,711`; `runtime/next/prompt_builder.py:27,518`;
- `specify_cli/analysis_inputs.py:146,155`; `cli/commands/agent/mission_create.py:492,542`;
- `charter/activate.py:50,851`; `charter/deactivate.py:41,295`; `charter/mission_type.py:33,138-143`;
- `cli/commands/upgrade.py:499,503,543,549,1029-1031,1035-1042,1060-1072`;
- `provisioning/default_charter.py:51,119`; `tool_surface/providers/agent_profiles.py:30,116,196`;
- `charter/activation/consistency_check.py:26,1582`; `charter/activation/compiler.py:680` (docstring).

**`CharterPackManager`**: defined at `pack_manager.py:701` (`__all__` `:116`). Used in `consistency_check.py:27,371,1579`, `charter/activate.py:51,226,287,888`, `charter/deactivate.py:42,114,158,301` and `charter/list_cmd.py:17,197`, plus docstrings in `activation_engine.py:5`, `mission_type_profiles.py:1010`, `mission_type_repository.py:455`, `spdd_reasons/activation.py:98`, `charter_activate.py:10` and `_layer_roots.py:46`.

**Tests and goldens.**
- `tests/core/golden/mission_create_refusals.json:601` (`"message": "CHARTER_PACK_CONFIG_INVALID"`).
- Code-string asserts:
  - `tests/charter/test_pack_context.py:468,481,489`, `test_pack_context_charter_yaml.py:206,216,226,235,351`;
  - `test_activation_engine_charter_yaml.py:154`, `test_compiler_charter_yaml.py:276`, `test_context_include.py:304`;
  - `tests/core/test_mission_create_activation_gate.py:56,60,73`;
  - `tests/next/test_cli_boundary_scope_config_4600.py:55`;
  - `tests/specify_cli/cli/commands/agent/test_mission_create_json_remediation.py:1,6,82,87,89`;
  - `tests/specify_cli/cli/commands/charter/test_charter_list_commands.py:421,423`;
  - `tests/specify_cli/test_charter_activate_cli.py:10,322,331`;
  - `tests/specify_cli/upgrade/test_upgrade_provisions_mission_type_activations.py:215`;
  - `tests/agent/cli/commands/test_charter_synthesize_cli.py:456`.
- About 40 test files import the classes. The heaviest are `tests/charter/test_pack_manager.py` (42 hits), `test_pack_manager_catalog.py` (18) and `test_activation_engine_charter_yaml.py` (14). Others: `tests/_factories/__init__.py:21`, `tests/architectural/test_json_contract_enumeration.py:318`, `tests/architectural/charter_path_literal_allowlist.yaml`.

**Docs.**
- `docs/api/orchestrator-api.md:343` names `CharterPackConfigError` as a pass-through upstream code.
- `docs/configuration/yaml-libraries.md` mentions it once.
- `docs/changelog/CHANGELOG.md:1765,2938` are released sections, so historical.
- **`src/charter/activation/ERROR_CODES.md` does not list this code.** It documents only the encoding codes, mirrored from `_diagnostics.py`. FR-009/FR-017 therefore have no existing error-code page to update. Either add an entry for the new code (recommended, since `activate.py:106` promises stability) or say in the changelog that the page is absent.
- Historical: `docs/reports/test-sanitation/**`, `docs/adr/4.x/2026-10-06-1-…:25,45`, `.kittify/evidence/**`.

**Decision.**
- Rename to `ActiveCharterConfigError` with code `ACTIVE_CHARTER_CONFIG_INVALID`, and rename `CharterPackManager` to `ActiveCharterManager`. Choosing the "active charter" sense follows ADR 2026-10-06-1, because the error is about the project's activation configuration, not a distributable pack.
- No alias.
- Route the one hard-coded literal (`charter/mission_type.py:143`) through `exc.code`, so the code string has one source.
- Update the golden and the ~15 code-string asserts.
- Add a changelog Before/After row and an `ERROR_CODES.md` entry.

**Rationale.** A single source for the literal leaves one place for the FR-018 gate to watch. The name follows the ADR's three-meaning split.

**Alternative.** Keep the code string and rename only the classes. Rejected by FR-009 as written.
