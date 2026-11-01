---
title: '06 — Domains & Splits: Technical Concretization'
description: 'Technical concretization of the consolidated domain model for the runtime and state overhaul: the proposed domains and splits, grounded in package fan-out findings.'
doc_status: deprecated
updated: '2026-06-03'
related:
- docs/archive/plans/engineering-notes/runtime_and_state_overhaul/16-codebase-reassessment-fanout.md
- docs/archive/plans/engineering-notes/runtime_and_state_overhaul/17-consolidated-domain-model.md
---
# 06 — Domains & Splits: Technical Concretization

> **Rewritten (2026-06-03)** as the **technical/codebase concretization of the consolidated model
> ([17](https://github.com/spec-kitty/spec-kitty/blob/main/docs/archive/plans/engineering-notes/runtime_and_state_overhaul/17-consolidated-domain-model.md))**, grounded in the fan-out package findings
> ([16](https://github.com/spec-kitty/spec-kitty/blob/main/docs/archive/plans/engineering-notes/runtime_and_state_overhaul/16-codebase-reassessment-fanout.md) H6). The earlier "for discussion" sketch (C1–C6 context
> catalogue, options A/B/C) is preserved in git history; its still-relevant parts (the owner-shape
> options, the e2e ratchet, the #992 alignment) are folded in below.

**Premise (Stijn):** *each domain is a **bounded module with external API entry points**; **communication
artefacts** cross between modules through those entry points.* This is the hinge from the conceptual
model (`17`) to code: map every model element to a **package home**, an **API entry point**, and a
**status** (exists / to-harden / net-new), then sequence the migration (Strangler).

---

## 1. Module map — model element → package home → API entry point → status

| Model element (`17`) | Kind | Package home (code, `16` H6) | API entry point(s) | Status |
|----------------------|------|------------------------------|--------------------|--------|
| **Governance** | domain (module) | `src/charter/` ⊕ `src/doctrine/` (two clean contexts) | `DoctrineService`, `build_charter_context(action=…)`, `AgentProfileRepository`, `ProfileRegistry` | **exists** |
| ↳ **GovernanceContext** | per-domain Context | `charter/context.py` (action-scoped bundle) | `build_charter_context` / `_load_action_doctrine_bundle` | exists |
| **Mission Management** | domain (module) | `kitty-specs/<slug>/` artefacts + planning cmds (`cli/commands/agent/tasks.py`, `agent/mission.py`) | `tasks-finalize`, `mission` CRUD, `bootstrap_canonical_state` | **exists** |
| ↳ **Mission / WorkPackage** | aggregates | `kitty-specs/` + `status/wp_metadata.py` | WP frontmatter + status events | exists |
| **Status / Kanban** | **Mission Management-owned; OHS facade** | `src/specify_cli/status/` | `status/__init__.py` facade (`read_events`/`reduce`/`materialize`/`get_wp_lane`/`emit_*`) | **exists; boundary NOT enforced → [#1664](https://github.com/Priivacy-ai/spec-kitty/issues/1664)**. Decided 2026-06-03: Status belongs to Mission Management — it publishes a facade, all other domains are consumers. Shared-context framing removed. |
| ↳ **`MissionStatus` aggregate** | aggregate root | (would wrap `status/`) | `MissionStatus.load/claim/transition/save` | **net-new** (today: free functions over `Lane`/`StatusEvent`) |
| **Execution / Runtime** | domain (module) | `src/runtime/next/_internal_runtime/` (canonical) + `runtime_bridge.py` | `decide_next`, `start_mission_run`, `get_or_start_run` | **exists** |
| ↳ **MissionRun** | aggregate | `runtime/next/_internal_runtime/{schema,engine}.py` | `MissionRunSnapshot` / `MissionRunRef` | exists; **can't name its Mission → [#1663](https://github.com/Priivacy-ai/spec-kitty/issues/1663)** |
| ↳ **ExecutionContext** (≈ ActionContext) | per-domain Context | `src/specify_cli/core/execution_context.py` | `resolve_action_context` (OHS) | **exists; to HARDEN (#1619)** |
| ↳ **Effector** | Actor realized in Execution | TBD (unify 3 vocabularies) | TBD | **net-new naming** |
| **Shared Kernel** | code module | `core/paths.py`, `workspace/root_resolver.py`, `mission_metadata`, `missions/_read_path_resolver.py` | `resolve_mission_identity`, `resolve_mission_read_path`, `get_status_read_root`/`get_main_repo_root`, `canonicalize_feature_dir` | **exists; the two OHS facades are the entry points** |
| **InfraContext** | ambient Context | `kernel/paths.py` (`get_kittify_home`), `charter/catalog.py` (`resolve_doctrine_root`), `state/contract.py` | `get_kittify_home`, `resolve_*_root`, `StateRoot` | exists |
| **Communication artefact** (Executor Prompt) | boundary artefact | `runtime/next/prompt_builder.py` (rendered text) | `build_prompt` → temp-file path | exists; **3 projections to consolidate** (below) |

**Reading:** the model is **mostly already in code**. Net-new is small and named: the `MissionStatus`
aggregate, the `Effector` type, and a unified communication-artefact contract. The #1619 core work is
**hardening one existing entry point** (`resolve_action_context` / ExecutionContext) and **enforcing one
existing boundary** (`status/`, #1664).

---

## 2. The communication-artefact contract (consolidate 3 projections)

Today the governed invocation produces **three** parallel projections (`16` H4) — we should converge them on one contract:

| Projection | Today | Consumer | Target |
|------------|-------|----------|--------|
| **Executor Prompt** | rendered text, `prompt_builder.py` → temp file (path returned) | LLM Effector | the canonical **communication artefact** |
| **`ActionContext.to_dict()` JSON** | `cli/commands/agent/context.py:111` | agent-context CLI / shim | a *serialization* of the same ExecutionContext (keep as a wire view) |
| **`OperationalContext`** (frozen VO) | `charter/invocation_context.py:155`, built at the decision boundary, **not passed to the prompt builder** | logs / composition | fold into the artefact assembly (or retire) |

**Target:** one **communication-artefact assembly** that takes (Mission/WP intent · GovernanceContext ·
ExecutionContext) and produces the artefact the Effector consumes — with the JSON `to_dict()` as a
*view* of the ExecutionContext, not a fourth independent thing. This is the technical form of "domains
exchange communication artefacts through API entry points."

> **Higher-priority than first ranked (Stijn, 2026-06-03).** This is not just cleanup — the drift between
> the projections is an active correctness problem feeding two concerns:
> 1. **"The Effector must load applicable profile + charter guidance before performing work."** Today
>    this is a **single line in the prompt**, *not* updated on lane transitions / reassignments, and *not*
>    enforced by the Python harness. One assembled artefact (re-rendered per transition) is the mechanism
>    that makes profile/charter loading current and enforceable.
> 2. **UI display drift.** The dashboard shows a single **effector string**, while the WP metadata holds
>    the profile/role values assigned at `tasks-finalize`. They disagree because they are different
>    projections. Consolidating the assembly removes the drift.
> → Raised in the Strangler sequence (§6) accordingly.

---

## 3. The `Effector` type (net-new) — unify the fragmented Actor

The Actor metamodel is fragmented across **three vocabularies** (`16` H3): runtime `Literal["human","llm","service"]`
(`_internal_runtime/schema.py:62`), retrospective `Literal["human","agent","runtime"]`
(`retrospective/schema.py`), decisions `Literal["human","llm","service"]`, and free-form `str` in
`status/emit.py`. The **Effector** is the execution-domain realization (`Effector = Actor ∩ Execution`).

**DECIDED (Stijn, 2026-06-03): named-in-docs for now — no code type yet.**
- *Rationale for a future type (the technical reason it exists):* the same concept ("who acted") is
  typed **4 inconsistent ways** today, and the `status` actor is an unvalidated free string
  (`"claude"`, `"merge"`). That is a latent drift/translation risk — e.g. is `"agent"` (retrospective)
  the same kind as `"llm"` (runtime)? Joining the decisions/status/retrospective logs on actor identity
  is currently lossy. A single frozen value type (`kind` enum + `id` + optional `profile_ref`) would
  make actor-kind canonical across all four surfaces.
- *Why defer:* it is a consistency risk, **not an active blocker** (DIRECTIVE_024 locality / don't
  over-engineer). **Trigger to materialize:** the first concrete actor-kind-mismatch bug, or when a
  feature needs to join those logs on actor identity. Until then, "Effector" is modeling vocabulary
  (the Actor realized in Execution), captured in the docs.
- *Trade-off (record for the decision):* **CON** — a first-class type adds surface area and risks
  over-modelling / over-engineering a concept that is today just an actor string. **PRO** — if modeled
  as an **enum** (+ identity), it buys cross-surface consistency and type-safety (no more `"agent"` vs
  `"llm"` ambiguity, no unvalidated free-form `actor` strings).

---

## 4. Package placement under the layer meta-guard

Constraints from `16` H6 / `tests/architectural/test_layer_rules.py`:

- **Spine:** `kernel ← doctrine ← charter ← specify_cli`; **`runtime/` and `glossary/` are siblings at
  the charter level**. `runtime` may import `specify_cli.*` **except** `specify_cli.cli` / `specify_cli.next`.
- **A net-new top-level `mission_runtime/` would fail `test_no_unregistered_src_packages`** until
  registered in `_DEFINED_LAYERS` (both `conftest.py` and `test_layer_rules.py`).

**Placement decisions (revised from the old §4):**
- **DECIDED (Stijn, 2026-06-03): a net-new `mission_runtime/` umbrella package.** Rationale: **Screaming
  Architecture** (the package structure should name the domain) + **Strangler Fig** (the new home grows
  alongside the old, surfaces migrate into it). This is preferred over harden-in-place for domain
  clarity. **Constraint:** it must be **registered in the layer meta-guard** (`_DEFINED_LAYERS` in both
  `conftest.py` and `test_layer_rules.py`), or `test_no_unregistered_src_packages` fails. The hardened
  `ExecutionContext` (today `core/execution_context.py`) migrates *into* this umbrella under Strangler.
- **`MissionStatus` aggregate** wraps `status/` — lives in `src/specify_cli/status/` (Mission Management's module). **Full read+write interface from day one** (no stepping-stone `MissionStatusAuthority`); `BookkeepingTransaction` is infrastructure called internally by the aggregate; domain invariants already live in `status/transitions.py`. Decided 2026-06-03.
- **`Effector`/`Actor` type — DECIDED: named-in-docs for now** (not a code type yet). Rationale below (§3).
  If materialized later, a low-layer shared type (`kernel/` or `actor.py`) so the three vocabularies converge without an illegal up-import.

---

## 5. The ExecutionContext owner shape (options carried forward)

The old A/B/C options now scope specifically to **the ExecutionContext owner + the commit seam**
(not a whole new "MissionExecutionContext"):

- **A — value object + resolver:** harden `resolve_action_context` to return an immutable, complete
  `ExecutionContext` (read/write/dest/cwd/prompt). Simple; doesn't enforce atomicity.
- **B — operation service:** an `ExecutionOperation` that owns the commit seam (`worktree_root == destination_ref`),
  closing #1618/#1348. Bigger; enforces I-4.
- **C — Strangler façade:** route surfaces through a stable `resolve_action_context` interface first,
  delegate to today's resolvers, swap implementation later.

**Lean (unchanged, now code-grounded):** **C → B.** Strangler via the *existing* `resolve_action_context`
OHS entry point (it already fuses planning+execution actions — `16` H1), converging on a commit-owning
operation service. Option A is the fallback.

---

## 6. Strangler sequencing (the migration order)

Ordered by isolation / value, tied to the filed issues and the keepers:

1. **Build the e2e ratchet** — `next → implement → move-task → review → status` parity from **main and
   lane CWD** (#1619 AC-5). The gate that proves a surface was unified, not re-masked. *(do first)*
2. **Enforce the Status boundary** (#1664) — make the Mission Management-owned `status/` module an actually-bounded domain (import test mirroring `test_shared_package_boundary.py`).
3. **Harden ExecutionContext** — route the residue surfaces (`02` §4: `agent/status.py`, `runtime_bridge`
   query-mode, `workflow.py` fix-mode, …) through `resolve_action_context`; delete duplicated path-builders.
4. **Consolidate the 3 context projections** → one communication-artefact contract (§2). **(Raised — §2:
   fixes the un-enforced/un-updated Effector profile+charter loading and the UI single-string drift.)**
5. **MissionRun → Mission reference** (#1663) — contained; unblocks "runtime knows its mission".
6. **Effector unification** (§3) — converge the Actor vocabularies. *(Deferred; trade-off in §3.)*
7. **Commit-seam atomicity** — make `(worktree_root, destination_ref)` a single self-validating
   **CommitTarget** owned by the operation (one atomicity domain), closing #1618/#1348. **Gate cleared (2026-06-03):** forensic pass of the `safe_commit` call graph confirms the invariant is already enforced — `safe_commit` asserts `worktree.HEAD == destination_ref` before any staging, keyword-only args, `mypy --strict` enforced, no silent fallback. 7 direct call sites; all clean. `CommitTarget` is therefore an ergonomic improvement on clean code, not a safety gate. Safe to implement at step 7 with no design risk to steps 1–6.

---

## 7. Open questions (now technical) + keepers

> **Tracked in [#1666](https://github.com/Priivacy-ai/spec-kitty/issues/1666)** (child of #992, blocks #1619).

**Keepers (code-validated, don't re-litigate):** Mission ≠ MissionRun; MissionType ∈ Governance(doctrine);
the execution spine; Context is per-domain; Shared Kernel is a code module.

**Decided (Stijn, 2026-06-03):**
1. **Effector** — **named-in-docs for now** (no code type until actor-kind drift causes a concrete bug). (§3)
2. **`mission_runtime/`** — **net-new umbrella** (Screaming Architecture + Strangler), registered in the layer meta-guard. (§4)

**Decided (Stijn + @robertDouglass, 2026-06-03) cont'd:**
3. **Atomicity (I-4) — DECIDED: enforce** `(worktree_root, destination_ref)` as a single self-validating
   **CommitTarget** (Option B; one atomicity domain → *closes* #1618/#1348, not just avoids). **Gate cleared:** forensic pass of the `safe_commit` call graph confirms the invariant is already structurally enforced by `safe_commit` itself (HEAD assertion before staging, `mypy --strict`, no fallback). 7 direct call sites, all clean. `CommitTarget` is ergonomic hardening of clean code; safe to implement at step 7 with no design risk to steps 1–6. (§5/6; background below)
4. **Communication-artefact contract — DECIDED: one assembly**, prompt-text + JSON as serializations of
   the same assembled context. **Priority raised** (not step-5 cleanup) — it is the mechanism for
   enforceable, transition-current Effector profile/charter loading and removes the UI display drift (§2).
5. **`MissionStatus` aggregate — DECIDED: build full aggregate directly; no stepping stone.** Status belongs to Mission Management (not a shared context). `MissionStatus` owns both read path and write path; `BookkeepingTransaction` stays as infrastructure called internally. Domain invariants already in `status/transitions.py` — they move into the aggregate, not into `BookkeepingTransaction`. No `MissionStatusAuthority` intermediate. Decided 2026-06-03 (@robertDouglass).
6. **Naming ratification (DIRECTIVE_032) — DECIDED:** GovernanceContext / ExecutionContext / InfraContext / Effector / communication-artefact ratified. ADR required before code lands. Decided 2026-06-03 (@robertDouglass).

### Background (Q3 resolved, Q4 background retained)

> **Q3 resolved 2026-06-03:** forensic pass complete — see §7 item 3 above.

**Q3 — `worktree_root == destination_ref` (the commit-atomicity invariant).** A commit goes through
`safe_commit(repo_root, worktree_root, destination_ref, …)`. `worktree_root` = the git worktree you
commit *from* (lane / coord / main checkout — i.e. "where the Effector did the work"); `destination_ref`
= the branch the commit should land *on*. The guard (`git/commit_helpers.py:858`) reads the worktree's
HEAD and **rejects unless HEAD == destination_ref** — you can only commit to a branch your worktree is
actually on. So it binds **two** facts: the **ExecutionContext** ("where the Effector works", the
worktree) **and** a **VersionControl** fact (the destination branch). The #1619 bug class is callers
passing a *mismatched* pair (worktree=main, destination=coord branch) → `safe_commit` says "checkout the
coord branch in main" → the manual-branch-switching loop (#1617/#1618/#1348). **The decision:** make the
pair a single self-validating value (the "CommitTarget") owned by the operation, so a status transition
and its commit are **one atomicity domain** and a mismatched pair is *impossible to construct* (closes
the class) — vs. keeping it a runtime check (avoids but doesn't close).

**Q4 — communication-artefact contract.** The governed invocation currently emits **three** independent
projections of the same underlying context (`16` H4): (1) the **Executor Prompt** rendered text
(`prompt_builder.py`) the Effector reads; (2) **`ActionContext.to_dict()` JSON** for programmatic/shim
consumers; (3) **`OperationalContext`** (a frozen VO of model/profile/role) built at the decision
boundary, logged but *not* passed to the prompt builder. They are assembled separately from overlapping
sources, so they can **drift** (e.g. the prompt's profile vs the logged `OperationalContext` profile).
**The decision:** one assembly that renders the artefact from (intent · GovernanceContext ·
ExecutionContext), with the prompt-text and the JSON as two **serializations of the same assembled
context** (not three independent objects) — vs. leaving the projections separate. Lower priority (Strangler step 5; needs ExecutionContext hardened first).

---

## 8. Path to a decided design

> **All §7 questions decided as of 2026-06-03.** Remaining work is ADR drafting + implementation.

1. **Draft ADRs** (vocabulary ratified per DIRECTIVE_032) → `docs/adr/3.x/`: (a) domain model (`17`) + Status ownership; (b) ExecutionContext owner + one-atomicity-domain commit rule; (c) Effector/Actor.
2. **Build the e2e ratchet** (step 6.1).
3. **Strangler increments** in the order of §6, each gated by the ratchet.
4. **Close #1619** when no raw mission-state reads remain outside the resolver (except documented fallbacks) and the e2e parity test is green from both CWDs.

> **Alignment:** this is the execution/state slice of team epic **#992 "centralize domain invariants"**
> (`03` C); reconcile explicitly. Free-wins #1663/#1664 are independently shippable down-payments.
