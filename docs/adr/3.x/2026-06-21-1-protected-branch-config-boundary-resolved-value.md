---
title: Protected-branch configuration is a standalone boundary-resolved value, 
  not a nested context sub-object
description: 'Protected-branch configuration resolves once into a standalone value object with `is_protected(ref)`, because the `safe-commit` deadlock site holds no mission context.'
status: Accepted
date: '2026-06-21'
doc_status: active
kind: ADR
updated: '2026-06-21T00:00:00Z'
---

## Context and Problem Statement

The set of branches Spec Kitty refuses direct commits to ("protected branches") is
hardcoded to `{main, master}` (`git/commit_helpers.py:420`), decided by **branch name
only**, and re-read independently at ~8 callsites that each call
`protected_branches(repo_root)` (and re-shell `git remote show origin`). Two consequences:

1. **Owners cannot configure it.** Any repo whose primary is named `main`/`master`
   deadlocks the sanctioned `/spec-kitty.specify` flow (the #1619 P0); owners have no way
   to declare intent.
2. **The protection authority is scattered.** `coordination/policy.py` even documents
   itself as "the single chokepoint for protected-branch refusal" yet still re-reads the
   set at `:214` — a live #1868 "authority in name only" instance.

The mission must make the protected set **owner-configurable** (declared in `.kittify`
config, default unchanged), **resolved once at the outermost boundary**, and **propagated
inward** so core logic stops touching git/filesystem for the protection decision (the
mission's pillar C, FR-007/008/009/010).

The architectural question this ADR settles: **what object carries the resolved
protected-branch set, and how does it reach the decision callsites?** The initial proposal
was to introduce a new `EnvironmentContext` and **nest it as a sub-object on an existing
context** (`ExecutionContext`/`WorkspaceContext`) for reuse and propagation.

## Decision Drivers

* The boundary must be reachable from **every** protection callsite — above all the
  deadlock site, the standalone `spec-kitty safe-commit` process.
* "Resolve once at the boundary, propagate inward; no core git/fs reads after" (FR-007/
  NFR-003).
* Single authority + an enforceable regression guard (FR-010 / #1868).
* Minimal coupling and no premature abstraction; the change must not balloon into a
  config-loader unification refactor.
* Reuse what already exists rather than reinventing decision machinery.

## Considered Options

* **A — Standalone boundary-resolved value object**, one `resolve(repo_root)` resolver,
  passed explicitly, feeding the existing `commit_guard.evaluate(ProtectionState)` seam.
* **B — `EnvironmentContext` nested as a sub-object on `ExecutionContext`** (the original
  proposal) as the primary carrier.
* **C — Nested on `WorkspaceContext`** (the per-WP, JSON-persisted context).
* **D — No new object**: make `protected_branches()` read `.kittify` config (memoized) and
  keep calling it at each site.

## Decision Outcome

**Chosen option: "A — standalone boundary-resolved value object", with cohesive scope**
(carries `protected_branches`, the resolved `operator_hatch_active` hatch state, and an
`is_protected(ref)` method), because it is the only shape that reaches the deadlock callsite
and it adopts — rather than duplicates — the decision seam that already exists.

The decisive fact, reached independently by four of the five squad agents (and conceded by
the fifth): **no protection callsite holds a built `ExecutionContext` at the decision
point.** The deadlock site — `spec-kitty safe-commit` — is a standalone process with no
mission identity, and the only `ExecutionContext` factory (`resolve_action_context`) *requires*
action+mission+wp and **fails closed with no fallback**. A context-nested carrier (Options
B/C) therefore **cannot reach the very callsite the mission exists to fix** without
fabricating a mission context that does not (and during the create→first-write window,
cannot) exist. Option C additionally serialises owner config into per-WP JSON snapshots —
a stale-config leak.

The boundary-resolved *decision* already exists: `core/commit_guard.py`
`evaluate(target, ProtectionState(is_protected), capability)` is pure/IO-free and takes a
`ProtectionState` computed at the boundary. The scattered part is only the **input**. So
the mission lifts the input to a single resolver and routes the ~8 callsites through it —
no new decision machinery.

The operator's composition instinct is preserved but demoted: the value object **may**
later be attached as an `ExecutionContext` fragment for the in-loop callers
(implement/tasks/accept) as a coherence improvement — explicitly **not** the primary carrier
and not on this mission's critical path.

### Consequences

#### Positive

* The deadlock callsite (`safe_commit_cmd.py`) resolves the policy at its own boundary
  (where `repo_root` is known) and works without any mission context.
* One sanctioned resolver makes the FR-010 guard a clean grep boundary; `coordination/policy.py`
  becomes a *real* chokepoint instead of a named-only one.
* Reuses the existing `ProtectionState`/`commit_guard.evaluate` seam — pillar C shrinks to
  "lift input + route callsites", de-risking the mission.
* The `is_protected()` method folds the duplicated `not hatch and ref in protected` idiom
  (3 sites) and makes the hatch boundary-resolved too.

#### Negative

* Explicit threading: each command must resolve the value at its entry and pass it down
  (shallow, at the boundary each already owns — strictly less than nesting would require).
* Risk of a forgotten resolve falling back to a direct `protected_branches()` call — mitigated
  by the FR-010 architectural guard.

#### Neutral

* A future second repository/environment setting can promote the value into a richer
  `RepositoryConfig` object; deferred until a real second field arrives (YAGNI).
* Consolidating the four scattered `.kittify/config.yaml` loaders is explicitly out of scope
  here (a separate strangler).

### Confirmation

The decision is validated when: the #1619 repro completes on a `main`-primary repo using only
sanctioned commands (SC-001); the protection decision performs zero post-resolution git/fs
reads (NFR-003); the FR-010 guard is green and bans direct `protected_branches(repo_root)` /
hardcoded-set decisions outside the single resolver; and default-config repos behave
byte-identically (NFR-004). Confidence: high — the carrier shape was stress-tested by an
adversarial dialectic and the input/decision split is already present in the code.

## Pros and Cons of the Options

### A — Standalone boundary-resolved value

A frozen value with one `resolve(repo_root)` resolver, passed explicitly, feeding
`commit_guard.evaluate(ProtectionState)`.

**Pros:** reaches every callsite incl. the parentless deadlock site; minimal coupling;
cleanest single-authority guard; reuses the existing decision seam.
**Cons:** explicit (shallow) threading at ~8 sites; needs the guard to prevent drift.

### B — `EnvironmentContext` nested on `ExecutionContext`

Carry the set as a sub-object/fragment on the per-action context.

**Pros:** idiomatic with the existing fragment family; free for in-loop callers.
**Cons:** **cannot reach the deadlock site** (no `ExecutionContext` there; factory fails
closed); couples a repo-scoped fact to a per-action composite; "EnvironmentContext" name
collides with `os.environ` and the existing "environment = worktree-vs-code" usage.

### C — Nested on `WorkspaceContext`

Carry it on the per-WP, JSON-persisted workspace context.

**Pros:** none material here.
**Cons:** scope inversion (repo-scoped vs per-WP); **serialises owner config into stale
JSON snapshots**, breaking "owner edits config and observes the change"; still absent at the
deadlock site.

### D — No new object (config-aware `protected_branches()`)

Make the existing free function read `.kittify` config, keep calling it everywhere.

**Pros:** smallest diff; fixes the deadlock + configurability.
**Cons:** fails pillar C — the read stays *at the callsite* (FR-007/NFR-003) and FR-010 can't
ban the very function it would have to allow; the #1868 scatter persists.

## More Information

* Mission spec + decision record: `kitty-specs/specify-protected-primary-coherence-01KVMBD6/spec.md`
  (FR-007/008/009/010) and `…/research/protected-branch-carrier-decision.md` (full squad synthesis,
  callsite matrix, boundary seams).
* Decision seam reused: `src/specify_cli/core/commit_guard.py` (`evaluate` + `ProtectionState`).
* Input lifted to the resolver: `src/specify_cli/git/commit_helpers.py:420,485-531,1017-1031`.
* Why nesting fails at the deadlock site: `src/specify_cli/cli/commands/safe_commit_cmd.py`
  (no mission context) and `src/mission_runtime/resolution.py:855` (`resolve_action_context`,
  no-fallback).
* Related: ADR `2026-06-03-2-executioncontext-owner-and-committarget.md`,
  ADR `2026-06-19-1-coord-empty-surface-fallback.md`.
