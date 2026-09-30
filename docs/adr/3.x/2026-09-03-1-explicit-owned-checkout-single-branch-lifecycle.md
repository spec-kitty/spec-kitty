---
title: 'ADR: Explicit Owned-Checkout Extends to the Single-Branch Mission Lifecycle'
description: 'Extends the fail-closed --owned-checkout affordance to the whole single-branch mission lifecycle via one shared preflight authority, restricted to single_branch topology.'
status: Accepted
date: '2026-09-03'
---

## Context and Problem Statement

[ADR 2026-08-12-1] established explicit checkout ownership and exposed
`--owned-checkout PATH` on exactly two commands: `mission create` and `next`.
That decision deliberately left the remaining mission-mutating commands out of
scope, naming the caller-versus-declared-workspace guard as follow-up work
([#3128]).

AI agents routinely operate from a task-owned linked worktree, not the
repository-root checkout. With only `create` and `next` owned-aware, the rest of
the single-branch lifecycle — prerequisite checks, task finalization, spec
commit, acceptance, task moves, and status transitions — could still only
rediscover the repository-root checkout. From an owned worktree those commands
either refused, or worse, resolved and wrote to the *wrong* mission surface. The
ownership boundary existed but stopped one command in.

This ADR records the decision to complete that surface for the single-branch
topology, the shared authority that carries it, and the topology restriction it
accepts. It extends — and does not supersede — [ADR 2026-08-12-1]; the
`OwnershipClaim` primitive and refusal taxonomy from that decision remain the
foundation.

## Decision Drivers

- Finish the owned-checkout lifecycle so a valid single-branch worktree workflow
  never has to fall back to the repository-root checkout to make progress.
- Reuse the existing ownership, mission-resolution, protection, and
  fail-closed-metadata authorities rather than inventing a second resolver.
- Keep every flagless (non-opted-in) caller byte-for-byte unchanged.
- Fail closed on every invalid ownership, topology, branch, or index condition —
  never silently degrade an owned-mode operation to primary-checkout behavior.
- Bound the blast radius: admit only the topology whose write model the owned
  root actually captures.

## Decision

### One shared preflight authority

Adopt `specify_cli.core.owned_mission` — `OwnedMission`, `resolve_owned_mission`,
and `require_unstaged_index` — as the single preflight shared by every owned
lifecycle command. `OwnedMission` is a validated *carrier*, not a new resolver:
it composes the authorities that already exist rather than re-deriving placement.

`resolve_owned_mission` validates, in order and fail-closed:

- repository identity and exact checkout root, via
  `checkout_ownership.resolve_ownership_claim` / `error_for_claim` (the
  [ADR 2026-08-12-1] primitive);
- mission identity, via the canonical `context.mission_resolver.resolve_mission`
  (a corrupt or non-object `meta.json` is skipped at indexing time, surfacing a
  structured `FEATURE_CONTEXT_UNRESOLVED`, not a traceback);
- mission-directory containment within the claimed checkout's `kitty-specs/`;
- single-branch topology, via `core.paths.load_meta_fail_closed`;
- current branch equals the mission target branch (detached HEAD refused) and,
  when supplied, the caller's `--target-branch` matches;
- protected-destination refusal, via `ProtectionPolicy`;
- whole-batch path containment before any staging (`OwnedMission.files`).

The validated owned root is threaded onward as an explicit `effective_root`
override through mission-context resolution, the placement seam, acceptance
gates, status transitions, commit routing, and runtime cutover. No opted-in
layer may replace it with `get_main_repo_root` or another ambient resolver — the
same invariant [ADR 2026-08-12-1] set for `next`.

### The affordance now spans the single-branch lifecycle

`--owned-checkout PATH` is additionally exposed on
`agent mission check-prerequisites`, `agent mission finalize-tasks`,
`spec-commit`, `accept`, `agent tasks move-task`, and `agent tasks mark-status`.
As before, the option names an exact checkout root for that invocation and is
never inferred from CWD, environment, path naming, or the nearest `.kittify`.

### Single-branch only, by construction

Owned mode is restricted to the `single_branch` topology. A `LANES`, `COORD`, or
`LANES_WITH_COORD` mission opted into `--owned-checkout` is refused with the
structured `OWNED_TOPOLOGY_UNSUPPORTED`, and the transactional emitters refuse
with `OWNED_TRANSACTION_UNAVAILABLE` rather than degrading to an uncommitted
fallback.

The rationale is that coordinated topologies route lifecycle writes through a
*coordination* worktree and branch that the single owned-root override does not
model. Admitting them would reintroduce exactly the cross-checkout write hazard
the ownership boundary exists to prevent. Fail-closed refusal is the safe scope
until a coordinated-topology owned model is designed.

## Consequences

### Positive

- The single-branch worktree workflow is complete: an owned agent can run the
  whole lifecycle without ever targeting the wrong checkout.
- One preflight authority governs every owned lifecycle command, composed from
  the existing ownership/resolution/protection/metadata seams — no second
  placement resolver.
- Every refusal is structured (`OWNED_*`), and every flagless caller is
  unchanged.

### Negative and accepted trade-offs

- The explicit `effective_root` override is threaded through many call sites.
  This duplication is intentional, for the same reason [ADR 2026-08-12-1] gave:
  rediscovery would erase the boundary. (A landing-pass fold routed the
  omit-the-keyword convention through the single `effective_root_kwargs` helper
  so the threading has one definition.)
- Coordinated topologies are not owned-aware. An operator who used
  `--owned-checkout` on `create`/`next` for a coord/lanes mission hits a hard
  `OWNED_TOPOLOGY_UNSUPPORTED` refusal on the later lifecycle commands. This is a
  deliberate fail-closed scope, not a silent gap.
- `owned_mission` still re-derives some validation (branch/topology probes, a
  whole-tree containment scan) on each resolve, and re-implements a few checks
  that canonical helpers also provide. That SSOT/performance cleanup is tracked
  as follow-up and does not change behavior.

## Alternatives Considered

### Extend `--owned-checkout` to coordinated topologies now

Rejected for this decision. Coordinated topologies write through a coordination
worktree/branch the owned-root override does not capture; a correct owned model
for them needs its own design. Fail-closed refusal is the safe interim scope.

### Let each lifecycle command grow its own ownership check

Rejected. That would fork the ownership/topology/branch invariants across
commands and let them drift — the second-resolver hazard [ADR 2026-08-12-1]
already refused. One shared `owned_mission` preflight keeps a single authority.

### Degrade to the repository-root checkout when owned validation fails

Rejected. Silent degradation is the original cross-write defect. Every invalid
condition is a structured refusal instead.

## Amendments

### 2026-09-28 — Validated ownership fact and per-command topology

Mission `owned-checkout-lifecycle-authority-01M3M2ZB` (issues #3449, #4252, #4867, #5026, #5277).

- **The preflight now produces a validated ownership fact.** `resolve_owned_mission` returns `mission_runtime.OwnedCheckout`, a frozen value object carrying `repository_root`, `owned_root`, `mission_dir`, `mission_slug`, `topology` and `target_branch`. It can be minted only inside `specify_cli.core.owned_mission`, through a private `_mint`; direct construction raises `TypeError`. `OwnedMission` and `effective_root_kwargs` are deleted with no alias left at mission end. The type lives in `mission_runtime`, not `core/owned_mission.py`, because the `runtime` and `mission_runtime` layers must consume it without a new outbound edge into the CLI application layer (C-003; enforced by `tests/architectural/test_layer_rules.py`).
- **Validated once per command.** A command validates ownership at most once, at its entry point, through `cli/commands/_owned_checkout.py` (`resolve_owned_or_adopt`), and hands the resulting fact to every downstream read. Readers never re-validate. Sites that previously re-derived ownership — for example `coordination/status_transition.py` and `cli/commands/accept.py` — now consume the fact instead (FR-003, NFR-002).
- **Supersedes the `effective_root` threading consequence** ("The explicit `effective_root` override is threaded through many call sites …", Consequences, Negative and accepted trade-offs). All bare owned-root parameters (census in this mission's plan, Scale/Scope) become `owned: OwnedCheckout | None`. An architectural gate with an **empty allowlist** forbids the identifier `effective_root` in `src/` outside the org-pack module rule (the unrelated `OrgPackConfig.effective_root` under `src/charter/**`, `src/specify_cli/doctrine/**`, `_doctrine_collect.py` and `analysis_inputs.py`), and separately forbids any bare owned-root path parameter under any name (`owned_root`, `owned_checkout`, `checkout_root` or `effective_root` typed as a path). This is a deliberate no-ratchet conversion, not a leeway ledger (operator decision `01M3M65D…`).
- **Per-command topology** (supersedes "Single-branch only, by construction" for `next`; the lifecycle commands of this ADR keep that restriction). The validated fact records the mission's stored topology, and each command declares its own allowed set. `next` accepts `NEXT_OWNED_TOPOLOGIES = {single_branch, lanes, lanes_with_coord, coord}` (decision `01M3M4GM…`), preserving the coordination-topology support it already had rather than newly narrowing it. The lifecycle commands of this ADR (`agent tasks status`, `setup-plan`, `context resolve`, `finalize-tasks`, `move-task`, `mark-status`, `spec-commit`, `accept`) keep `LIFECYCLE_OWNED_TOPOLOGIES = {single_branch}` and still refuse other topologies with `OWNED_TOPOLOGY_UNSUPPORTED`. The placement-layer duplicate refusal `_require_owned_single_branch` is deleted, because topology is now decided once, at minting, not re-derived at each consumer.
- **Owned status reads under `.worktrees/`.** The canonical coordination surface resolver decides whether a path is refused as a coordination worktree, from the validated fact plus the registered-worktree facts — never from path shape. There is no parallel status-source label; status-source classification stays with that one resolver (FR-013, FR-014, C-002).
- **Stale repository-root copies.** When the repository root checkout holds a copy of the owned mission, owned reads resolve from the owned checkout, never from the repository root checkout's copy, and report `stale_repository_root_copy` in JSON output and on stderr (FR-007, decision `01M3M2ZX…`).
- **Newly covered commands; typed refusal for `agent action`.** `agent tasks status`, `agent mission setup-plan` and `agent context resolve` gain `--owned-checkout`. `agent action implement` and `agent action review` accept the flag only to refuse it with `OWNED_ACTION_UNSUPPORTED`, and the refusal names `next --owned-checkout` and `agent tasks move-task --owned-checkout` as the supported path (decision `01M3M4GZ…`; follow-up #5100).
- **One claim-commit review base.** Every WP review prompt, owned or not, finds its base through one claim-commit helper: the last `claimed` event id recorded in the status log, then the unique commit that introduced it. It fails closed with `OWNED_REVIEW_BASE_UNAVAILABLE` when neither can be resolved. The three duplicate commit-subject matchers this ADR's design otherwise left in place are deleted (FR-010, FR-025, decision `01M3M70Y…`).
- **New error codes.** `OWNED_CHECKOUT_IS_REPOSITORY_ROOT`, `OWNED_CHECKOUT_IS_MISSION_WORKTREE`, `OWNED_ACTION_UNSUPPORTED`, `OWNED_REVIEW_BASE_UNAVAILABLE`, `OWNED_COORDINATION_WORKSPACE_UNAVAILABLE`.

## References

- Foundational decision (extended, not superseded): [ADR 2026-08-12-1]
- Caller/workspace mismatch follow-up: [#3128]
- Scoped shadow-workspace design: [#3129]
- Windows fixture repair (related, still open): [#3822]
- Owned-checkout lifecycle authority mission: [`kitty-specs/owned-checkout-lifecycle-authority-01M3M2ZB/spec.md`](../../../kitty-specs/owned-checkout-lifecycle-authority-01M3M2ZB/spec.md), [`plan.md`](../../../kitty-specs/owned-checkout-lifecycle-authority-01M3M2ZB/plan.md)
- [#3449], [#4252], [#4867], [#5026], [#5277]

[ADR 2026-08-12-1]: ./2026-08-12-1-checkout-ownership-for-mission-create-and-next.md
[#3128]: https://github.com/Priivacy-ai/spec-kitty/issues/3128
[#3129]: https://github.com/Priivacy-ai/spec-kitty/issues/3129
[#3822]: https://github.com/Priivacy-ai/spec-kitty/issues/3822
[#3449]: https://github.com/spec-kitty/spec-kitty/issues/3449
[#4252]: https://github.com/spec-kitty/spec-kitty/issues/4252
[#4867]: https://github.com/spec-kitty/spec-kitty/issues/4867
[#5026]: https://github.com/spec-kitty/spec-kitty/issues/5026
[#5277]: https://github.com/spec-kitty/spec-kitty/issues/5277
