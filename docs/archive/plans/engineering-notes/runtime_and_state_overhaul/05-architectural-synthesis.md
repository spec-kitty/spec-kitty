---
title: 05 — Architectural Synthesis
description: 'Architectural synthesis across notes 01-04 of the runtime and state overhaul: the single root cause, the forces in tension, and the invariants to preserve.'
doc_status: deprecated
updated: '2026-06-03'
---
# 05 — Architectural Synthesis

Architect's reading across `01`–`04`. This is interpretation, not new fact; every claim traces to a
prior document. Goal: name the single root cause, the forces in tension, and the invariants the
to-be design must satisfy — so `06` can propose domains and we can choose between options with eyes open.

---

## 1. The one-sentence root cause

> **Mission execution context is computed by every caller instead of owned by one model, so the
> physical truth (which tree, which branch, which dir) is reconstructed — differently — at each of
> ~40 sites, and the gaps between those reconstructions are the bug class.**

The status *domain* is clean (`status/` is bounded, event-sourced, State-Pattern). The defect is not
in *how state transitions*; it is in *how each surface decides where state lives and where commands
may run*. That decision is **topology resolution**, and it currently has **no owner** — it is
smeared across `cli/commands/agent/*`, `implement.py`, `runtime_bridge.py`, `orchestrator_api`, and
two half-resolvers (`resolve_mission_read_path` for reads, `BookkeepingTransaction` for writes).

This is a textbook **missing bounded context** with a **shallow interface** (Deep Module Design,
`04`): the knowledge a caller needs ("where is status for this mission, given my CWD and the
topology?") is not encapsulated, so all callers carry it — and drift.

## 2. Why point-fixes keep recurring (the mask mechanism)

Each child bug (#1615–#1618) was a *symptom of one missing abstraction* fixed locally:

- #1615 → "make these specific reads coord-aware" (routed *some* sites to `resolve_mission_read_path`).
- #1616 → "rewrite these specific prompt strings".
- #1617 → "pass the right `worktree_root` here".
- #1618 → "skip the second commit in this one path".

None introduced the owner. So **every new surface, or every old surface not in the fix's blast
radius, reintroduces the class** (`02` §4 lists ~10 residual surfaces, incl. `agent/status.py` which #1627 never touched). #1602 and #1348 are the same disease in adjacent organs: shared mutable state
with no single owner (#1602 = one file, two schemas; #1348 = one branch, two bypass rules).

**This is the definition of an architectural problem rather than a bug:** the cost of the next mask
is roughly constant, and the masks do not reduce the population of future masks.

## 3. The forces in tension (what makes this non-trivial)

| Force | Pulls toward | Source |
|-------|--------------|--------|
| **Topology must be resolved once, authoritatively** | A single context object | #1619 AC |
| **15+ host surfaces + orchestrator API + runtime must all consume it identically** | A *service/value* seam, not a per-command helper | ADR atomic-WP-start (`03` A3) |
| **Reads and writes legitimately target different trees** (lane code vs coord status) | Context must expose *distinct* read/write/destination, not one "feature_dir" | `02` two-resolver split |
| **`done`/acceptance is a mission-branch fact; status is coord; code is lane** | Context is **multi-rooted** (primary, coord, lane, integration) — not one root | ADRs A1/A5 (`03`) |
| **Lanes own git; WPs own accounting** | Two-dimensional context (lane axis + WP axis) | ADR A1 (`03`) |
| **Mission Run ≠ Mission ≠ Mission Type** | The new object is a *Mission Run* concern; don't conflate ids | ADR A6 (`03`) |
| **Densest, least-tested, bus-factor-1 cluster** | Strangler-Fig migration + test build-out, never big-bang | CAACS (`03` C), DIRECTIVE_024 (`04`) |
| **Boundaries by language, not by lifecycle stage** | Resist the charter-style runtime split | DIRECTIVE_031 + deep-dive smell (`03` B, `04`) |

The hardest tension is the third row: the seductive simplification ("one `feature_dir` to rule them
all") is **wrong** — the whole point is that a mission has *several* legitimate physical homes and
the context's job is to hand each caller the *right one for its operation*, not to collapse them.

## 4. Invariants the to-be design must satisfy (acceptance lens)

Derived from `01` AC + `03` ADRs + `04` directives. A design option is only viable if it can hold all of these:

**I-1 — Single resolution.** Topology (roots, branches, dirs, destination) is resolved **once per
operation** from `meta.json` + `lanes.json` + CWD, by one component. No surface re-derives raw paths. *(#1619 AC-1/2/3)*

**I-2 — Distinct, named outputs.** The context exposes at least `status_read_dir`,
`status_write_dir`, `destination_ref`, `coord_worktree`, `execution_workspace`, `allowed_command_cwd`,
`prompt_source_dir` as **separate** values — never one fused `feature_dir`. *(`02`, #1619 AC-1)*

**I-3 — Identity on `mission_id`.** Lookup/locking/event routing key on the ULID; `mission_run_id`
is a separate runtime identity; `mission_slug`/`mission_number` are display/compat. *(ADR A4/A6)*

**I-4 — One atomicity domain per operation.** A status transition and its companion artifacts commit
**together or not at all**, to one resolved `(worktree_root == destination_ref)` pair. No
"transactional emit + separate direct commit". *(#1618; ADR A3)*

**I-5 — Consume, don't re-implement, the status domain.** Lane transitions go through
`status/` (State Pattern + event log + the atomic lifecycle service). The context provides *where*;
`status/` decides *whether/how*. *(ADR A2/A3; `04` DDD)*

**I-6 — Prompts/help render from the context.** Agent-facing strings are **derived**, not authored
per-branch-assumption. The contract an agent reads cannot contradict where the CLI writes. *(#1616; #1619 AC-4)*

**I-7 — `lanes.json` is consumed fail-closed, including dependencies.** Workspace resolution honors
lane dependencies (closes F-02); absence is a hard error, never a silent per-WP fallback. *(ADR A1; deep-dive F-02)*

**I-8 — Mission-branch facts are distinct from lane facts.** `approved`→`done`/acceptance is bound
to the integration branch; the context must not let an aggregate of lane approvals masquerade as
`done`. *(ADR A5; F-03)*

**I-9 — No shared mutable state across boundaries.** One writer per file/aggregate; crossings are
explicit interfaces/events. *(DIRECTIVE_001/031; #1602)*

**I-10 — Incremental, test-anchored migration.** Strangler-Fig adoption with the e2e regression
(`next→implement→move-task→review→status` from main *and* lane CWD) as the gate. *(#1619 AC-5; DIRECTIVE_024; DM-D)*

## 5. What is already true and must be *preserved* (don't break these)

- `status/` boundedness and event-sourcing (060-cleanup). **Consume it.**
- `doctrine ← charter ← specify_cli` dependency direction. **Don't invert.**
- The atomic lifecycle service (`start_implementation_status`/`start_review_status`). **Extend it.**
- `CoordinationWorkspace` as the topology *primitive* (it already owns coord path/branch + sparse
  rules). The new context should **wrap/own** it, not duplicate it — note the ≥4 duplicated
  path-builders (`02`) are the thing to collapse *into* it.
- ULID identity + deterministic historical repair. **Key on it.**
- Public events/tracker boundary + CLI-internal runtime home. **Stay inside it.**

## 6. The shape of the answer (without yet choosing it)

The evidence points at a **Mission Run / execution-topology bounded context** that:

1. owns a **value object** resolved once per operation (call it provisionally `MissionExecutionContext`),
2. is produced by a **single resolver/factory** that folds in the four duplicated path-builders and
   the two half-resolvers,
3. exposes **distinct read/write/destination/cwd/prompt** surfaces (deep module),
4. **delegates** transitions to `status/` and lifecycle starts to the atomic service,
5. lives under a **new `mission_runtime/`-style package** (per the deep-dive's moratorium-on-new-top-level-packages stance and epic #992),
6. is adopted **incrementally**, with the e2e regression as the ratchet.

The genuinely open questions — value object vs service vs context-manager; how many sub-domains;
where the package boundary falls; how aggressive the migration is — are deferred to `06` and our
session. This synthesis only argues that *some* such context is **necessary**, not which variant is best.
