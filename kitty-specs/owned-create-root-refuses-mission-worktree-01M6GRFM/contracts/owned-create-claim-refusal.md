# Contract: the create-level owned claim refuses a Mission worktree

Mission: `owned-create-root-refuses-mission-worktree-01M6GRFM` · Issue: #6956
Surface: `specify_cli.core.owned_mission.resolve_owned_create_root`

## Inputs

| Input | Meaning |
| --- | --- |
| `repository_root` | the resolved repository root checkout `R` |
| `checkout` | the raw `--owned-checkout` claim (absolute, relative-to-`cwd`, or a symlink) |

## Outcome

Either an `OwnedCreateRoot` whose `checkout` is the resolved claimed checkout, or
`ActionContextError`.

## Refusal matrix

| Condition | `error.code` | Notes |
| --- | --- | --- |
| foreign repository, broken pointer, nested directory, repository root | `OWNERSHIP_*` / `OWNED_CHECKOUT_IS_REPOSITORY_ROOT` | unchanged, from `_require_owned_claim` |
| registered `.worktrees` worktree whose name ends `-coord` | `OWNED_CHECKOUT_IS_MISSION_WORKTREE` | new (FR-001) |
| registered `.worktrees` worktree whose name parses as `<slug>-lane-<id>` | `OWNED_CHECKOUT_IS_MISSION_WORKTREE` | new (FR-002) |
| unreadable git worktree registry, on a `.worktrees` claim | `WORKTREE_REGISTRY_UNAVAILABLE` | new, fail closed (NFR-002) |
| any other linked checkout of `R` | admitted | unchanged (FR-005) |
| `-coord`-shaped directory git does not register (husk) | not this code | refused earlier as a non-checkout (`OWNERSHIP_NESTED`) |

Ordering: the refusal happens before the `OwnedCreateRoot` is minted, therefore before
`agent mission create` performs any branch switch, commit or scaffold.

## Consumers (all inherit the matrix through the one minter)

- `specify_cli.cli.commands.agent.mission_create._mint_owned_create_root` — `agent mission create`
- `specify_cli.cli.commands._owned_checkout.startup_project_checkout` — read-only startup gates;
  a refusal keeps the repository root (never redirects the gates to the refused checkout)
- `specify_cli.cli.commands._owned_checkout.resolve_owned_op_record_root` — `dispatch`,
  `profile-invocation complete`, `invocations list`
- `specify_cli.cli.commands._owned_checkout.refuse_owned_action` — handle-less `agent action`

## Non-goals (unchanged by this contract)

- No stored `MissionTopology`, write-branch or Mission-identity validation: the Mission the
  create will make does not exist yet.
- No change to `resolve_owned_mission` (the leaf), `adopt_owned_checkout`, or the leaf's
  `lanes.json`-based lane comparison.
