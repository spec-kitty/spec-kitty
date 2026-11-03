# Data Model — tracer-append owned-Mission routing

There is no persisted data model change. This mission changes **which inputs** one CLI
command selects; the entities below are the existing ones it must now read from the right
place.

## Entities (existing, unchanged in shape)

### Owned checkout fact (`mission_runtime.OwnedCheckout`)

Minted once per command by `specify_cli.core.owned_mission` through the CLI seam. Fields
this mission consumes:

| Field | Role here |
| --- | --- |
| `owned_root` | the checkout that owns the Mission; becomes the writer's `repo_root` |
| `mission_dir` | `P/kitty-specs/<slug>`; the containment root for the tracer file |
| `mission_slug` | the Mission handle the tracer entry belongs to |
| `write_branch` | the branch `P` is on and every owned write must land on |
| `repository_root` | `R`; only `resolve_for_owned` needs it (to union the protected sets) |
| `topology` | must be in `LIFECYCLE_OWNED_TOPOLOGIES` (today `single_branch`) |

### Tracer entry (existing)

The dated, attributed line appended to `kitty-specs/<slug>/traces/<category>.md`. Format,
idempotence and merge semantics are owned by `tracer_writer` and are **not** changed.

## Inputs that move from root-derived to fact-derived

| Input | Today (`main`) | After |
| --- | --- | --- |
| write root passed to `append_tracer_finding` | `get_main_repo_root(cwd)` → `R` | `owned.owned_root` → `P` when a fact exists, else `R` |
| protection policy | `ProtectionPolicy.resolve(R)` | `ProtectionPolicy.resolve_for_owned(owned, mission)` when a fact exists, else `resolve(R)` |
| target branch for the post-commit ff-advance | `get_feature_target_branch(R, mission)` → `R`'s copy | `owned.write_branch` when a fact exists, else unchanged |
| owned fact handed to the write seam | never (no parameter) | `owned` keyword, `None` for the non-owned path |

## Refusal contract (unchanged codes, new reachability)

| Situation | Code | Where raised | Written? |
| --- | --- | --- | --- |
| `--owned-checkout` names `R` | `OWNED_CHECKOUT_IS_REPOSITORY_ROOT` | `resolve_owned_or_refuse` | nothing |
| `--owned-checkout` names a lane/coordination worktree | `OWNED_CHECKOUT_IS_MISSION_WORKTREE` | `resolve_owned_or_refuse` | nothing |
| checkout does not own the named Mission | `OWNERSHIP_FOREIGN` (or typed sibling) | `resolve_owned_or_refuse` | nothing |
| topology not in `LIFECYCLE_OWNED_TOPOLOGIES` | `OWNED_TOPOLOGY_UNSUPPORTED` | `resolve_owned_or_refuse` | nothing |
| coord worktree not materialised | untyped `CoordinationWorktreeUnmaterialized` → structured `{ok: false, next_step}` | writer, unchanged | nothing (inside the stage thunk) |
| corrupt non-UTF-8 traces file | structured `{ok: false, next_step}` | writer, unchanged | nothing (read-before-write refuses) |
| blank `--actor` | `TracerAttributionError` | writer, unchanged | nothing |

The first four are the new reachability: they fire **before** `append_tracer_finding` is
called, so they cannot leave staging residue.

## Non-goals

- No change to `OwnedCheckout`, its minter, its topology sets, or its refusal codes.
- No change to the tracer file format, its lock, its merge behaviour, or the commit-outcome
  surfaces.
- No new persisted state, no new config key.
