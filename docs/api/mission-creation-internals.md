---
title: mission-creation internals reference
description: 'mission-creation internals: the mission_creation module family, the patch-routing rule, and where to add a create-time decision.'
doc_status: active
updated: '2026-10-05'
type: reference
audience: docs/context/audience/internal/maintainer.md
---
# `mission_creation` internals reference

`spec-kitty agent mission create` and the orchestrator-api `specify` verb both
call `create_mission_core()` in `src/specify_cli/core/mission_creation.py`. That
module used to hold all of mission creation in about 2,360 lines. Since #5634 it
is a façade over a family of sibling modules. This page is for a maintainer who
changes create-time behaviour.

## Module map

The façade keeps `create_mission_core` (the public entry point), which
delegates to `_create_mission_core_failure_atomic` (the failure-atomic wrapper,
which also takes the private identity inputs `_mission_id` and `_created_at`),
`_create_mission_core_impl` (the orchestration) and the historical import
surface. Every other definition moved into one sibling, and the façade
re-exports it with `from ... import x as x`. The bodies moved verbatim; the
decision-core and seam cleanups then reshaped several leaves (the protected
mint's `_ProtectionProbe` and gather ladder, the rollback's
`CreateRollbackJournal`, the meta build/write split). `logger` is the same logger
object as before: the leaves that log pin its name, and the façade re-exports it.

| Module | Responsibility | Key names |
|--------|----------------|-----------|
| `mission_creation_errors` | errors, the result type, the bootstrap commit-skip set | `MissionCreationError`, `MissionAlreadyExistsError`, `MissionBranchExistsError`, `MissionCreationResult` |
| `mission_creation_identity` | slug, friendly name and purpose inputs | `_mint_mission_id` (the identity seam), `KEBAB_CASE_PATTERN`, `_validate_create_inputs`, `_resolve_purpose` |
| `mission_creation_roots` | repository root, write root and current branch | `_CreateRoots`, `_resolve_create_roots` |
| `mission_creation_duplicates` | live-duplicate detection over `kitty-specs/` | `_list_mission_scaffolds`, `_find_live_duplicate_mission`, `_refuse_live_duplicate` |
| `mission_creation_protected_mint` | the protected-target mission-branch mint for `single_branch` | `_ProtectionProbe` (the per-create protection decision), `_refuse_protected_recreate`, `_mint_protected_branch_for_topology`; `_target_is_protected` is a one-shot compatibility wrapper over the probe |
| `mission_creation_scaffold` | the mission directory scaffold, tasks README and create-time governance | `render_tasks_readme_content`, `_resolve_create_governance`, `_scaffold_mission_dir` |
| `mission_creation_meta` | `meta.json` assembly, the coordination-branch mint, and the `meta.json` write | `_MetaBuild`, `_build_create_meta`, `_write_create_meta` |
| `mission_creation_events` | creation events and the coordination status seed | `_emit_create_events`, `_commit_coord_create_events`, `_seed_coord_surface_for_create` |
| `mission_creation_commit` | the scaffold commit, origin binding and the result | `_commit_feature_file`, `_commit_create_scaffold`, `_build_create_result` |
| `mission_creation_rollback` | failure-atomic rollback of a failed create | `CreateRollbackJournal`, `_CoordCreateRollbackContext`, `_restore_git_state_after_failed_create` |
| `mission_creation_decisions` | pure decision cores: no git, filesystem, clock or ULID | `decide_protected_mint`, `coord_rollback_action` |

`mission_creation.<name>` stays importable for every name the module exposed
before the split; `tests/core/test_mission_creation_family.py` pins that list.

`_create_mission_core_impl` runs the create steps in this order: scaffold,
`_build_create_meta` (which mints the coordination branch), the protected-target
mint `_mint_protected_branch_for_topology`, then `_write_create_meta`. The mint
is called from the orchestration, not from the meta builder, and it runs before
the write because it can set `meta["mission_branch"]`.

## The patch-routing rule

Tests patch names on the façade, for example
`monkeypatch.setattr(mission_creation, "build_mission_created_payload", ...)`. A leaf that
called such a name directly would ignore the patch. Today the patch-routed set (patched
names a leaf reads) is `{build_mission_created_payload}`; the other `_mc.` calls in
the leaves are cross-leaf calls. So:

- A leaf calls a name tests patch on `mission_creation`, or a function another
  `mission_creation*` module owns, as `_mc.<name>(...)`, after a function-local
  `from specify_cli.core import mission_creation as _mc`.
- Every other call in a leaf is direct, and patching the leaf intercepts it.
- No leaf imports the façade at module scope, and the decisions module never
  imports it. Leaves import classes and constants of other leaves directly.
- Leaves that log use `logging.getLogger("specify_cli.core.mission_creation")`.

`tests/core/test_mission_creation_family.py` computes the routed set from the
patch census (`tests/_support/patch_census.py`) and fails on a bare reference to
a routed name, on a foreign function used bare, and on an `_mc.` reference to a
name nobody patches. It reads an import alias as the name it imports, and it
also fails on `<module alias>.<routed name>` (for example
`import specify_cli.core.git_ops as g; g.get_current_branch()`), on an import
of a patched name or of another family module's function under any alias, and
on `sys.modules[...]` in a leaf. When a test starts patching a new façade name that a leaf
reads, route that read in the same change.

## Fixing a create's identity

A create mints its `mission_id` in `mission_creation_identity._mint_mission_id()`
and reads the clock for `created_at` in the meta leaf. A test or caller that
needs a fixed identity (a resume into the same directory, a branch name known in
advance) passes `_mission_id=` and `_created_at=` to
`mission_creation._create_mission_core_failure_atomic`, the failure-atomic body
`create_mission_core` delegates to, instead of patching `ULID` or `now_utc_iso`.
The public signature of `create_mission_core` does not carry them.

## Where to add a create-time decision

1. Put the rule in `mission_creation_decisions.py` as a pure function over plain
   values. It may not do I/O; `tests/core/test_mission_creation_purity.py`
   checks that with an import allow-list and a ban on file and process calls.
2. Unit-test every branch in `tests/core/test_mission_creation_decisions.py`.
3. Gather the facts in the leaf that owns the step (the adapter) and pass them
   in. Keep the order in which facts are probed, so an error still raises at the
   same point.

Behaviour of the whole create path is pinned by the golden matrix in
`tests/core/test_mission_creation_golden_*.py` and the CLI golden in
`tests/specify_cli/cli/commands/agent/test_mission_create_golden_cli.py`.
