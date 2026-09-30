# Data Model: Owned-checkout lifecycle authority

## OwnedCheckout (value object, `mission_runtime.owned_checkout`)

| Field | Type | Meaning |
|---|---|---|
| `repository_root` | `Path` (resolved) | The repository root checkout R. Used only for repository-root-only concerns (charter authoring, stale-copy detection). |
| `owned_root` | `Path` (resolved, canonical) | The owned checkout P. |
| `mission_dir` | `Path` | `P/kitty-specs/<mission_slug>`. |
| `mission_slug` | `str` | The resolved mission slug. |
| `topology` | `MissionTopology` | The mission's stored topology, as recorded at validation. |
| `write_branch` | `str` | The branch every owned write lands on and P's current branch at validation time: `expected_write_branch(meta)` — the #5100 minted `mission_branch` for a protected-target single_branch mission, else the mission's `target_branch`. Renamed from `target_branch` (architecture review of the origin/main merge): it is **not** the landing (merge) branch. Display surfaces (`context resolve`, `setup-plan`) read the landing `target_branch` from the fact's own `mission_dir/meta.json` and carry the write branch as `destination_ref` / `expected_checkout_branch`. |

**Invariants** (checked in `__post_init__`; pure path logic, no I/O):
- `owned_root != repository_root`.
- `mission_dir` is inside `owned_root / "kitty-specs"`.
- `mission_dir.name == mission_slug`.
- The object was created through `_mint` (private sentinel). Direct construction raises `TypeError`.

**Behaviour**: `files(paths) -> list[Path]` checks that paths are contained in `mission_dir` and raises `OwnedCheckoutPathRefused` on escape. It replaces `OwnedMission.files` and maps to `OWNED_MISSION_PATH_REFUSED` at the CLI edge.

**Lifecycle**:
1. A CLI entry point calls `resolve_owned_or_adopt`.
2. That calls `owned_mission.resolve_owned_mission` or `adopt_owned_checkout`, which runs the claim primitive and the containment, topology and branch checks, mints the fact with `OwnedCheckout._mint`, and then refuses a protected `write_branch` through `ProtectionPolicy.resolve_for_owned(fact)` — the one owned mission-scoped protection fold every owned write also uses (union of R's and P's configured protected branches; `commit_to_target` read from the fact's `mission_dir`). An owned `mission create` binds its `OwnedCreateRoot` to the new mission (`OwnedCreateRoot.bind_mission(feature_dir)` → `OwnedCreateMission`) for the same fold.
3. The fact is passed down, immutable, for the whole command.
4. It is never persisted.

## Validator (`specify_cli.core.owned_mission`, the sole minter)

| Function | Returns | Used by |
|---|---|---|
| `resolve_owned_mission(repository_root, checkout, handle, *, target_override=None, allowed_topologies=LIFECYCLE_OWNED_TOPOLOGIES)` | `OwnedCheckout` or raises `ActionContextError(code)` | every `--owned-checkout` command |
| `resolve_owned_create_root(repository_root, checkout)` | `OwnedCreateRoot` (typed, frozen; fields `repository_root: Path`, `checkout: Path`; a validated owned root before the mission exists, never a bare `Path`) | `agent mission create` |
| `adopt_owned_checkout(repository_root, cwd, handle, *, allowed_topologies)` | `OwnedCheckout \| None` | flagless owned-capable commands (FR-021) |
| `LIFECYCLE_OWNED_TOPOLOGIES` | `frozenset({SINGLE_BRANCH})` | ADR 2026-09-03-1 lifecycle commands |
| `NEXT_OWNED_TOPOLOGIES` | `frozenset({SINGLE_BRANCH, LANES, LANES_WITH_COORD, COORD})` | `next` |
| `OwnedMission(primary, root, directory, slug, target)` | `OwnedCheckout` | **transitional legacy factory function** marked `# TRANSITIONAL(WP18)`: accepts the old positional arguments, mints an `OwnedCheckout` (topology `SINGLE_BRANCH`) inside the minter module so G3 holds; deleted by WP18 |

## ResolvedWorkspace (extended)

The new `resolution_kind` value is `"owned_checkout"`:
- `worktree_path = owned.owned_root`
- `lane_id = None`
- `lane_wp_ids = []`
- `branch_name = owned.target_branch`

`enforce_checkout_identity` gains an arm that refuses when the invoking cwd is outside `worktree_path`.

## Error code registry (NFR-004)

| Code | Status | Raised when |
|---|---|---|
| `WORKTREE_INVOCATION_REFUSED` | existing (claim primitive, `UnownedNoOptInError`) | no opt-in claim |
| `OWNERSHIP_NESTED` | existing (claim primitive, `NestedCheckoutError`) | the claimed checkout is nested inside another linked checkout |
| `OWNERSHIP_FOREIGN` | existing (claim primitive, `ForeignOrMismatchedCheckoutError`) | the claimed checkout belongs to a different common repository |
| `OWNERSHIP_BROKEN_POINTER` | existing (claim primitive, `BrokenPointerCheckoutError`) | the claimed checkout's git topology cannot be read safely |
| `OWNED_MISSION_PATH_REFUSED` | existing | the mission dir or a path escapes P |
| `OWNED_TOPOLOGY_UNSUPPORTED` | existing (semantics now per command) | the stored topology is outside the command's allowed set |
| `OWNED_BRANCH_REFUSED` | existing | branch mismatch, detached HEAD, or a protected target |
| `OWNED_INDEX_REFUSED` | existing | staged changes before a write operation |
| `OWNED_OPTION_UNSUPPORTED` | existing (pre-existing wire string; becomes an `OwnedRefusalCode` member in WP14) | an option that is not supported together with `--owned-checkout` (e.g. `accept --diagnose --normalize-encoding`, auto-commit and `--resume-probe` in the task commands) |
| `OWNED_INPUT_INVALID` | existing (pre-existing wire string; becomes an `OwnedRefusalCode` member in WP14) | the owned invocation's input is malformed |
| `OWNED_CHECKOUT_IS_REPOSITORY_ROOT` | **new** | `--owned-checkout` names the repository root checkout |
| `OWNED_CHECKOUT_IS_MISSION_WORKTREE` | **new** | `--owned-checkout` names a lane worktree of the mission or a coordination worktree (flagless adoption returns `None` for the same checkouts instead of refusing) |
| `OWNED_ACTION_UNSUPPORTED` | **new** | `agent action implement` / `agent action review` with `--owned-checkout` |
| `OWNED_REVIEW_BASE_UNAVAILABLE` | **new** | no single claim commit, or no owned files |
| `OWNED_COORDINATION_WORKSPACE_UNAVAILABLE` | **new** | the coordination-workspace probe fails for owned `next` |
| `WORK_PACKAGE_UNRESOLVED` | existing (now scoped to P for owned) | the WP is absent from the owned mission dir |
| `WORKTREE_REGISTRY_UNAVAILABLE` | existing (`WorktreeRegistryUnavailable.error_code`) | the git worktree registry cannot be read while validating an explicit `--owned-checkout`; the minter fails closed |
| `FEATURE_CONTEXT_UNRESOLVED` | existing (`owned_mission.FEATURE_CONTEXT_UNRESOLVED`, a public module constant; pre-existing wire code, not an `OwnedRefusalCode` member) | the mission handle cannot be resolved inside the owned checkout |
| `MISSION_CONTEXT_CONFLICT` | existing (`owned_mission.MISSION_CONTEXT_CONFLICT`, a public module constant; pre-existing wire code, not an `OwnedRefusalCode` member) | the handle and the owned checkout name conflicting missions |

**Code constants.** Every code above is a member of `OwnedRefusalCode(StrEnum)` in `mission_runtime.owned_checkout` (value == name), exported from the `mission_runtime` root with `OwnedCheckout` (WP01). Code and tests import the member instead of repeating the literal; a `StrEnum` member compares equal to its string, so serialized payloads are unchanged.

The four claim-primitive codes are defined by the error classes in `src/specify_cli/core/checkout_ownership.py` and pass through the minter unchanged (`ActionContextError(error.error_code, str(error))`); their strings are `do_not_change` (occurrence map `logs_telemetry`). `emit_owned_refusal` (WP08) validates every emitted `error_code` against this whole table, including the three pre-existing wire codes that are single named constants rather than `OwnedRefusalCode` members.

## Payload field (FR-007)

`stale_repository_root_copy`: `{"path": str, "mission_id": str} | null`. It is a top-level key in the `--json` output of `agent tasks status`, `agent mission setup-plan`, `agent context resolve`, `next` and `agent mission finalize-tasks`, **emitted only in owned runs** (an `OwnedCheckout` fact is held, explicit or adopted): `null` when R holds no copy, the object when it does. Non-owned runs never emit the key, so their payloads stay byte-identical to the planning base (golden contracts unchanged for the non-owned shape). The human text goes to stderr, and to `warnings[]` where that list exists.

## Status event fact used by the review base (unchanged schema)

The last `WPStatusChanged` event with `to_lane == "claimed"` for the WP in P's `status.events.jsonl` supplies the `event_id`. The claim commit is the unique commit on P's `HEAD` history whose diff to `status.events.jsonl` introduced that `event_id`.

## State transitions

No lane-state-machine change. For owned WPs, the `claimed → in_progress → for_review` transitions are driven by `move-task --owned-checkout`, and the prompts come from `next --owned-checkout`.
