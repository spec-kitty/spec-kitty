# Contract: CLI owned-checkout surface

| Command | `--owned-checkout` | Allowed topologies | Owned success output | Notes |
|---|---|---|---|---|
| `agent tasks status` | **new** | single_branch | the owned WP list plus `stale_repository_root_copy` | FR-004 |
| `agent mission setup-plan` | **new** | single_branch | `plan.md` created and committed in P, plus `stale_repository_root_copy` | FR-005 |
| `agent context resolve` | **new** | single_branch | `wp_file`/`workspace_path` under P, `resolution_kind="owned_checkout"`, `lane_id=null`, plus `stale_repository_root_copy` and `warnings[]` | FR-006 |
| `next` | existing (now through the validator) | single_branch, lanes_with_coord, coord | a step or blocked decision, plus `stale_repository_root_copy` | FR-002/008/009/010/012 |
| `agent mission finalize-tasks` | existing | single_branch | atomic, plus `stale_repository_root_copy` | FR-013/015 |
| `agent action implement` | **new** (refusal only) | none | exit ≠ 0, `OWNED_ACTION_UNSUPPORTED`, with guidance naming `next --owned-checkout` and `agent tasks move-task --owned-checkout` | FR-018 |
| `agent action review` | **new** (refusal only) | none | as above | FR-018 |
| `agent mission create` | existing | n/a (the mission does not exist yet) | unchanged; governance reads now come from P (FR-016) | goes through `resolve_owned_create_root` |
| `move-task`, `mark-status`, `spec-commit`, `check-prerequisites`, `accept` | existing | single_branch | unchanged behaviour (FR-022) | rewired onto the shared helper |

**Flagless.** Owned-capable commands run without the flag call `adopt_owned_checkout` on cwd. The result is either a fact or the unchanged repository-root behaviour (FR-021). If the same selector resolves to different mission ids in cwd's checkout and in R, the command keeps today's mission-surface-conflict refusal (US7-AS5).

**Stale-copy key.** `stale_repository_root_copy` is emitted only in owned runs (explicit or adopted fact). A non-owned run's JSON payload is byte-identical to the planning base.

**Option.** Every `--owned-checkout` declaration uses the shared alias `OwnedCheckoutOption`; gate G5 exempts parameters annotated with it (or with its help-preserving form `Annotated[Path | None, owned_checkout_option(help=...)]`) by the named `CLI_CLAIM_INPUT_RULE` (they carry the raw, unvalidated claim input to the minter).

**Refusals.** `emit_owned_refusal` keeps each command's existing JSON envelope keys. `error_code` is always one of the registered codes (data-model.md). No refusal writes to P or R.

**Help text.** It uses "repository root checkout" and "owned checkout"; never bare "primary" and never "feature".
