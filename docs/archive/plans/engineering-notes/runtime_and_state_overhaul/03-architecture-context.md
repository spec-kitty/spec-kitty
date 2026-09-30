---
title: '03 — Architecture Context: 3.x Intent, Deep-Dive Review, CAACS Audits'
description: 'Architecture context for the runtime and state overhaul: what 3.x intent, the deep-dive review, and the CaaCS audits already commit to and flag as debt.'
doc_status: deprecated
updated: '2026-06-03'
---
# 03 — Architecture Context: 3.x Intent, Deep-Dive Review, CAACS Audits

What the existing architecture already commits to, and what the audits already flag as debt that an
execution-context redesign would touch. Sources: `docs/adr/3.x/*`,
`docs/plans/engineering-notes/architectural-review/2026-05-25-deep-dive-architectural-review.md`,
`docs/archive/plans/engineering-notes/architecture-audits/2026-05-spec-kitty-caacs.md`, `docs/archive/plans/engineering-notes/architecture-audits/2026-05-caacs-meta-assessment.md`.

> Note: `docs/3.x` is currently empty — the 3.x **ADR set is the architectural intent** (there is no
> consolidated 3.x behavioral spec yet; `docs/architecture/README-3.x.md:8-10`). The redesign must
> reconcile the ADRs directly rather than cite one canonical runtime doc.

---

## A. What the architecture already commits to (binding precedents)

### A1 — Lanes own git; WPs own accounting

ADR `2026-04-03-1-execution-lanes-own-worktrees-and-mission-branches`:
- `ExecutionLane` is the **branch + worktree** unit; `WorkPackage` is the **planning / review /
  accounting** unit (`:61-66`). One integration branch per mission; only it merges to `main`.
- `lanes.json` is **mandatory, fail-closed** runtime input — `implement`/`review`/`accept`/`merge`
  MUST fail closed when it is absent/malformed; **no fallback** to per-WP worktrees or detection
  (`:86-89`). Shipped commands must **never** create/merge `.worktrees/<feature>-WP##` (`:155-156`).
- Branch naming: `kitty/mission-<slug>` (integration), `kitty/mission-<slug>-lane-<id>` (lane).
- **Progress accounting is two-dimensional**: WP state AND lane state must both be visible (`:132-134`).

> **Consequence:** the execution context is **lane-scoped for git** and **WP-scoped for accounting**.
> Both axes must be first-class. It must *consume* `lanes.json` (including `dependencies`).

### A2 — Lane behavior is a polymorphic State Pattern over an event log

ADR `2026-04-06-1-wp-state-pattern-for-lane-behavior`:
- Replaced lane logic scattered across **46 files / 358 string literals / 3 duplicated `LANES`
  tuples** with an ABC + frozen-dataclass State Pattern; each of the **9 lanes** owns its
  `allowed_targets()`, guards, `progress_bucket()`, `display_category()`; `TransitionContext`
  replaces an 8-arg kwargs bag (`:42-54`).
- Promotes `in_review` to a **first-class 9th lane** (`:51,138`). `in_review` outbound transitions
  require a `ReviewResult` in `TransitionContext` (`:139`). `doing` remains an alias resolved at the boundary (`:63`).

> **Consequence:** route lane transitions through `wp_state_for()` / `TransitionContext` + the event
> log — do **not** re-scatter string literals. The status domain is already bounded; consume it.

### A3 — Lifecycle starts are service-owned and atomic

ADR `2026-05-01-1-atomic-work-package-start-lifecycle`:
- Start is **semantic** = two events (`planned→claimed`, `claimed→in_progress`). Pre-ADR each
  surface emitted independently → crash strands at `claimed`; retry semantics varied by surface (`:28-44`).
- Spec Kitty supports **15 coding-agent hosts + orchestration/API** — lifecycle correctness cannot
  live in a host-specific wrapper (`:39-43`).
- Decision: a **shared lifecycle service** — `start_implementation_status()` / `start_review_status()`
  — writes multi-edge **atomic batches**, materializes once, same-actor resume / different-actor
  conflict (`:69-97`). Atomic persistence = append full batch to temp JSONL then replace the canonical log (`:99-101`).
- **Layering rule:** semantic lifecycle starts are **service-owned**; raw transition validation is **state-machine-owned** (`:116-118`).

> **Consequence:** this is the **strongest existing precedent** for a unified context/service seam.
> A `MissionExecutionContext` should **extend, not bypass** this service.

### A4 — Identity is a ULID (`mission_id`), not a number

ADR `2026-04-09-1-mission-identity-uses-ulid-not-sequential-prefix` (+ `2026-05-10-1` deterministic
historical repair):
- `mission_id` (creation-time ULID) is the **canonical machine identity** for every selector, state
  file, merge primitive, WP reference, status artifact, sync payload (`:74-78`). `mission_number` is
  display-only; `feature_slug` is a software-dev compat alias. Historical backfill is
  content-addressed and offline-deterministic.

> **Consequence:** the context object keys identity on `mission_id` for lookup/locking/event routing — never `mission_number`/`feature_slug`.

### A5 — `done` ≠ `approved`; acceptance runs on the integration branch

ADRs `2026-04-03-2` (review/approval distinct) + `2026-04-03-3` (feature acceptance on the
integrated mission branch):
- `for_review` = ready to inspect; `approved` = review granted; `done` = integrated + acceptance
  evidence recorded. **Evidence is split per transition** (`:84-95`).
- WP review may happen on a lane branch, but feature QA and `accept` **MUST** happen on the **mission
  integration branch** (`:53-58`), with negative-invariant verifiers (proven absence).

> **Consequence:** the context must carry differentiated evidence per transition and know that
> `done`/acceptance is a **mission-branch** fact, not an aggregate of lane approvals.

### A6 — The Mission Type / Mission / Mission Run ontology (critical noun boundary)

ADR `2026-04-04-2-mission-type-mission-and-mission-run-terminology-boundary`:
- **Mission Type** = reusable blueprint (lifecycle actions, guards, templates, action indices, doctrine bindings).
- **Mission** = concrete tracked item under `kitty-specs/<mission-slug>/`, canonical id `mission_slug` / `mission_id`.
- **Mission Run** = one persisted runtime/session instance under `.kittify/runtime/`, identified by `mission_run_id`; **must never alias a tracked mission slug** (`:113-124`).

> **Consequence (most important for #1619):** a `MissionExecutionContext` is, in the canonical
> ontology, a **Mission Run** concept — runtime/session state keyed by `mission_run_id`, *distinct*
> from the tracked Mission (`mission_id`) and the Mission Type blueprint. Conflating these is the
> exact failure this ADR exists to prevent. **Name and layer the new object accordingly.**

### A7 — Runtime is CLI-internal; events/tracker are public-import-only

ADR `2026-04-25-1-shared-package-boundary`: runtime surface lives under
`src/specify_cli/next/_internal_runtime/`; `spec-kitty-runtime` is retired; events/tracker consumed
only via `spec_kitty_events.*` / `spec_kitty_tracker.*`; enforced by architectural import tests + clean-install CI.

> **Consequence:** keep the redesign's runtime home CLI-internal and the events/tracker access on the public-import boundary.

### A8 — Layered doctrine config is field-merge + visible collisions

ADR `2026-05-16-1-doctrine-layer-merge-semantics`: layered config resolution is field-level merge
with explicit `DoctrineLayerCollisionWarning`. Peripheral, but relevant if the context assembles layered mission/doctrine config.

---

## B. The current bounded-context map (from the 2026-05-25 deep-dive review)

| Bounded Context | Canonical package | Boundary status |
|-----------------|-------------------|-----------------|
| Charter (governance source) | `src/charter/` | **clean — zero inverse imports** |
| Doctrine (rulebook + DRG + profiles) | `src/doctrine/` | **clean — zero inverse imports** |
| Constitution | `src/constitution/` | self-contained (not investigated) |
| Dashboard | `src/dashboard/` + `src/specify_cli/dashboard/` | bifurcated |
| **Mission lifecycle** (specify→…→merge) | `cli/commands/*.py` + `specify_cli/runtime/` + `src/runtime/` | **scattered** |
| **Status / kanban** (lane state machine) | `src/specify_cli/status/` | **clean per 060-cleanup; bounded** |
| Glossary / terminology | `specify_cli/glossary/` + `src/doctrine/` | acceptable, re-check |

**Protected strength:** dependency direction is correct — `charter` and `doctrine` do **not** import
`specify_cli` (`:35-36`). Keep it.

**Named smell directly relevant to us (`:37-38`):** the four charter packages under `specify_cli/`
are a **runtime split (lifecycle vs read-only vs check), not a domain split → leaky boundary.** This
is the canonical example of the anti-pattern the overhaul must avoid.

**Review's decomposition stance:** a **moratorium** on new top-level `specify_cli/*/` packages;
scattered mission-lifecycle concerns should land under a `mission_runtime/`-style umbrella (`:108-112`).

**Execution/state bugs the review flags as architectural:**
- **F-02** — `agent action implement` worktree creation does **not** consume `lanes.json::dependencies` → lane workspaces don't inherit upstream commits (`:127`).
- **F-03** — squash-merge path does not emit post-merge `done` events on the target branch (`:128`).
- **F-06** — no `lane-cross-cutting` class for integrative/QA work spanning lanes (`:131`).

---

## C. CAACS audit findings (complexity / coupling hotspots)

`2026-05-spec-kitty-caacs.md` + meta-assessment:

- **Bus factor ≈ 1** (≈89.5% src single-author) — highest knowledge-concentration risk in the repo (`:141-146`).
- **F2 = the execution/state hotspot cluster** (all DDD=**core**):

  | File | SLOC | Worst fn (CC) |
  |------|------|---------------|
  | `cli/commands/agent/tasks.py` | 3746 | `finalize_tasks` **CC=160**, `move_task` CC=139 |
  | `cli/commands/agent/workflow.py` | 1895 | `review` CC=84 |
  | `cli/commands/implement.py` | 718 | CC=44 (workspace resolution) |
  | `cli/commands/merge.py` | 1599 | `_run_lane_based_merge_locked` CC=63 |
  | `next/runtime_bridge.py` | 2552 | "a hub, not a bridge"; F-46 fn; MI=C |
  | `status/emit.py` | 656 | `batch` CC=40 |
  | `core/worktree.py` | 681 | git worktree mgmt |
  | `orchestrator_api/commands.py` | 1097 | external orchestration API |

- **Densest temporal coupling** is exactly the mission-state ↔ git-worktree transaction:
  `agent/{tasks,workflow}.py` ↔ `implement.py` ↔ `merge.py` ↔ `core/worktree.py` — **22 of the top-30
  coupled pairs** involve one of these six files (`:289-330`). ~**70% of changes** there ship without
  matching test updates (`:429-445`).
- `finalize_tasks` (CC=160) actually lives in `mission.py` despite `tasks.py` naming — a name/location coupling smell (`:683-685`).
- Cross-cutting observation: *"the `agent/` directory is doing too much … everything-the-mission-touches-funnels-here"* (`:732-737`).
- **Team has already filed epic [#992 "centralize domain invariants"]** as the F2 remediation vehicle (meta-assessment `:25-28`), plus #984 (wrong-checkout reads from detached worktrees). DM-D resolution: **document/transfer knowledge first, then refactor** (`:181`).

---

## D. Net architectural reading for #1619

A `MissionExecutionContext` is — in the project's own ontology — a **Mission Run** object that must:

1. key identity on **`mission_id`** (ULID), distinct from `mission_run_id` (A4, A6);
2. be **lane-scoped for git** and **WP-scoped for accounting**, consuming **fail-closed `lanes.json` including dependencies** (A1, F-02);
3. **delegate** lifecycle starts to the existing atomic service (A3) and lane transitions to the State-Pattern + event log (A2) — *consume* the bounded status domain, don't re-implement it;
4. respect **`approved` ≠ `done`** and **integration-branch acceptance** (A5, F-03);
5. live under a **`mission_runtime/`-style home** that decomposes today's scattered lifecycle code and the `runtime_bridge.py` hub (deep-dive `:108-112`);
6. align with **epic #992** and pair structural change with **test build-out + knowledge transfer** (bus-factor / DM-D), because it lands in the repo's single densest, most complex, least-tested core cluster.
