# Data model: pure decision cores

All types are frozen dataclasses in `src/specify_cli/core/mission_creation_decisions.py`. Functions are pure: no git, filesystem, subprocess, environment, clock or ULID access. They delegate rule content to the existing authorities instead of re-encoding it.

## ProtectedMintFacts → ProtectedMintDecision

| Field | Type | Source (adapter) |
|---|---|---|
| `mint_applies` | `bool` | `protected_mint_applies(topology, commit_to_target, target_protected)` |
| `target_has_commit` | `bool` | `git rev-parse --verify <target>^{commit}` |
| `dirty_outside_scaffold` | `tuple[str, ...]` | `status_entries`, filtered by the scaffold overlap rule |
| `branch_name` | `str` | `mission_branch_name(slug, mission_id=...)` (authority, not re-derived) |
| `branch_exists` | `bool` | `git rev-parse --verify refs/heads/<branch>` |
| `target_branch`, `write_root_display` | `str` | inputs, used only to format messages |

The decision is one of:

- `NoMint`
- `Refuse(kind: Literal["error", "branch_exists"], message: str)`
- `Mint(branch_name)`

Evaluation order (unchanged): applies → target has a commit → dirty → branch exists → mint. Message text is byte-identical to today.

The facts are gathered lazily, at the same points where today's probes run (R-4). Follow-up: #5676 adds an `occupants` fact and one precondition here.

## Protection

- `target_is_protected(policy: ProtectedTargetPolicy, target_branch: str, primary_for_protection: str) -> bool` delegates to `policy.is_protected_target`. `ProtectedTargetPolicy` is a structural `Protocol` (or a `TYPE_CHECKING`-only `ProtectionPolicy` type); the pure module never imports `specify_cli.git` at runtime.
- `protected_mint_applies(topology, commit_to_target: bool, target_protected: bool) -> bool` returns False unless the topology is SINGLE_BRANCH and `commit_to_target` is False.

## ScaffoldRouting

`is_coordination_routed(topology, *, owned: bool) -> bool` wraps `topology_mints_coordination_branch(topology)` together with the owned condition. It is the single definition replacing the two topology-based copies at `:1312` and `:2020`. The `:1874` site keys on `status_log_path` and owned, so it keeps its own condition unless a table test proves it identical (WP05 fold 4).

## MetaFlagPatch

`meta_flag_patch(pr_bound, retain_branches, retain_worktrees, commit_to_target) -> dict[str, bool]` returns only the keys whose flag is True. Absent means never default-written (#3131 invariant; meta key order is preserved by the caller's insertion order).

## Duplicates

- `DuplicateCandidate(dir_name: str, meta: Mapping | None, meta_unreadable: bool, abandoned: bool)`
- `match_live_duplicate(base_slug, mission_type, candidates) -> DuplicateCandidate | None`. It fails closed on unreadable meta, exactly as today.
- `is_abandoned(*, wp_lanes, event_count, spec_tracked) -> bool`. A status-log read failure (`StoreError`) is handled in the adapter as "live", exactly as today.

## Rollback

- `plan_orphan_scaffold_removal(post_names, pre_names, slug, tracked) -> tuple[str, ...]` keeps the same-prefix neighbour guard ("task-list" vs "task-list-api").
- `coord_rollback_action(created: bool, pre_seed_tip: str | None, current_tip: str | None) -> Delete | CasReset(expected, to) | Noop`
- `is_disposable_create_refusal(exc)` stays in the **rollback adapter**, because it needs `specify_cli.git.commit_helpers` exception types.

## Commit outcome and file sets

- `classify_scaffold_commit_failure(kind: CommitFailureKind) -> Literal["skip", "already_exists", "raise"]`. The adapter maps the exception type to `CommitFailureKind`, mirroring today's except-ladder.
- `created_file_sets(...) -> (created_files, uncommitted)` is the pure part of `_build_create_result`.

## Invariants (pinned by FR-011)

- Coordination-routed creation events land in the coordination worktree, and the status log stays off the target.
- Failed-create restore order: checkout first, then orphan branches and coordination surface (Mission dir cleared before worktree teardown and before the branch delete or CAS reset), then disposable scaffold, which is planned before the index restore.
- MISSION_ALREADY_EXISTS is raised before the mint refusal. The scaffold commit lands on the minted branch.
- mid8 is derived once. The meta commit comes after origin binding. At create, `tasks/README.md` is committed and `spec.md` is left untracked.
