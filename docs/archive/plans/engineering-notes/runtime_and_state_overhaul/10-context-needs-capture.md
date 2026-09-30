---
title: '10 — Context Needs: Requirements Capture (idea → working code)'
description: Requirements capture (Phase 2, intuition pass) of what each context needs in the runtime and state overhaul; some claims later revised by note 11.
doc_status: deprecated
updated: '2026-06-15'
related:
- docs/archive/plans/engineering-notes/runtime_and_state_overhaul/11-dialectic-and-revised-claims.md
---
# 10 — Context Needs: Requirements Capture (idea → working code)

**Phase:** 2 (requirements) · **Date:** 2026-06-03 · **Status:** intuition pass (lens 1 of 3)

> **⚠ Claims revised by [11](11-dialectic-and-revised-claims.md).** The D2 (behaviour) and D6
> (interaction policy) `[C]`/`[C-gap]` conclusions below were adversarially tested. Net: behaviour is
> already resolved live (fix = single owner, not "unfreeze"); interaction policy should be
> **resolved-and-frozen at plan time** (not per-run-mutable); mission phase is distributed-first-class
> (don't add a new enum). Read `11` for the reconciled positions.

**Goal:** specify **WHAT must be known**, **by which actor** (code / user / agent), **at which step**
of the idea-to-working-code process — across six context dimensions. This is the requirements
baseline the eventual context model + BPMN/interaction/model diagrams must satisfy.

## Method — three lenses, in order

1. **Intuition** (this pass) — architect + operator gut, *before* consulting sources. Captures what
   we believe is needed, so the sources confirm/deny rather than anchor us.
2. **Existing docs** — corroborate against User Journeys (`docs/plans/user_journey/`,
   `architecture/3.x/`), ADRs, status-model docs.
3. **Existing code** — corroborate against the actual resolvers/call sites (builds on `02`/`07`).

Every claim is tagged: **[I]** intuition · **[D]** docs · **[C]** code · **[✓]** corroborated across
≥2 lenses. This pass is almost entirely **[I]**; later passes promote cells to **[✓]** or flag conflicts.

## Actors

- **Code** — the CLI/runtime; what it must *resolve* to execute correctly.
- **User** — the human operator; what they must *know or decide*.
- **Agent** — the AI coding agent(s); what they're *told* (via prompts/skills/profiles) and must obey.

## Steps (idea → working code)

| Phase | Steps | One-line |
|-------|-------|----------|
| **P0 Govern** | charter, constitution, doctrine activation | project-level rules (once) |
| **P1 Frame** | mission create, specify, clarify | what are we building |
| **P2 Design** | plan, research | how will we build it |
| **P3 Decompose** | tasks → tasks-finalize (lanes computed) | break into WPs + lanes |
| **P4 Build** | implement: claim → workspace → code → quality-gate → commit → transition | make one WP real |
| **P5 Verify** | review (per WP), accept (per mission) | prove it correct |
| **P6 Integrate** | merge (lane → integration → main), emit `done` | ship it |
| **P7 Learn** | retrospect | capture learning |

## Dimension ↔ fragment map (continuity with `09`)

The six dimensions are the *requirements view*; the `09` fragments are the *structural view*. They line up:

| Dimension | `09` fragment(s) |
|-----------|------------------|
| D1 Filesystem / Infra locations | F1 `InfrastructureEnv` + F2 `FilesystemLayout` |
| D2 Charter context / behaviours | F1 (doctrine roots) + action-scoped charter context + F4 (profile) |
| D3 Version-control concerns | F3 `VersionControlScape` |
| D4 Mission state | F0 `MissionIdentity` + mission-level F5 |
| D5 Work-package state | F5 `MissionStatus` (per-WP) |
| D6 Interaction process | F4 `OperationalContext` (config) + lane plan (F2/F5) + policy |

That the *needs* (D1–D6) and the *structure* (F0–F5) map cleanly is itself a sanity signal — but
it's circular until docs/code confirm the needs. Hence lens 1 first.

---

# Intuition pass — what must be known

> Everything below is **[I]** unless tagged otherwise. Read it as "Alphonso's gut, structured for
> Stijn to correct and extend." Gaps and `?` are deliberate invitations.

## D1 — Filesystem / Infra locations

| Actor | Must know | First needed | Notes |
|-------|-----------|--------------|-------|
| Code | shipped/built-in doctrine root; `~/.kittify` home; `~/.spec-kitty` sync; primary repo root | P0 | install/repo-scoped, ambient |
| Code | `kitty-specs/<slug>/` mission dir; derived dir | P1 | mission-scoped |
| Code | `.worktrees/` root; coord worktree path; lane worktree path(s); status **read** dir; status **write** dir; prompt source dir; allowed cwd | P3→P4 | derived from identity + conventions; **the contested set** |
| User | where their mission artefacts live (`kitty-specs/<slug>`); where code workspaces are; **which dirs are generated copies they must not edit** | P1 | the CLAUDE.md "edit source not copies" rule lives here |
| Agent | which workspace to `cd` into for code; that lane worktrees **sparse-exclude** status files; where shared artefacts live; prompt source | P4 | today's prompts get this wrong (#1616) |

**Intuition:** infra (install) is stable & ambient; filesystem (mission) is *derived once* from
identity + topology conventions. The "contested set" (read/write dirs, worktrees) is exactly what
no one owns today. **Key question:** *when* is the coord worktree created — at `tasks-finalize` or
first `implement`? The answer sets when D1's mission-scope facts become resolvable. `[I→C]`

## D2 — Charter context / applicable behaviours

| Actor | Must know | First needed | Notes |
|-------|-----------|--------------|-------|
| Code | active doctrine pack(s) + activated artifacts; mission-type definition (action sequence, step contracts, templates); gates implied by directives | P0 / per step | resolved per (mission_type, action) |
| Code | the **action-scoped** guidance bundle for the current step (directives/tactics/styleguides) | every step | already built (`charter context --action`) `[C]` |
| Code | the **agent profile** bound to this step (identity, boundaries, canonical verbs) | each step | DDR-011 matching `[C]` |
| User | what governance applies; what the charter selected (doctrine packs, SPDD?); what's enforced vs advisory | P0 | |
| Agent | their profile; the action-scoped directives/tactics for **this** step; the **step contract** (what to do, in what order); the rendered prompt | each step | this is the agent's whole operating contract |

**Intuition + corroboration:** this dimension is largely *already modeled* (DoctrineService + action
index + profiles), but the **behaviour ↔ runtime-state binding is via the activity ledger** (Stijn).
The open `?` (does behaviour depend on runtime state?) is now **answered: yes**, with a mechanism — and a gap.

**`[C]` What the activity ledger actually is** (two layers):
- Invocation event trail — `src/specify_cli/invocation/record.py` / `writer.py` → append-only
  `kitty-ops/{id}.jsonl` (started/completed with `profile_id, action, actor`).
- Profile-invocation **lifecycle log** (the canonical ledger) — `src/specify_cli/invocation/lifecycle.py`
  → `.kittify/events/profile-invocation-lifecycle.jsonl`, paired started/completed records carrying
  `canonical_action_id, phase, agent, mission_id, wp_id, at, reason` (`lifecycle.py:290-341`).

**`[C]` The gap (the binding is aspirational, not wired):** the ledger is **observational only**
today. Profile/role/directive injection does **not** read it — it resolves from the **frozen mission
template step** via `_resolve_step_agent_profile(run_dir, current_activity)` (`runtime_bridge.py:2167`),
then renders directives through `build_charter_context(profile=…)` (`prompt_builder.py:373-428`). The
ledger entry is written *around* that, not consulted *by* it.

> **Design implication:** Stijn's intuition describes the *intended* model — behaviour bound to the
> activity. The code binds behaviour to the *frozen step* and treats the activity ledger as audit.
> The redesign target is to make the activity ledger (or its reducer) the **canonical source** for
> "which profile/role/directives apply now," so D2 genuinely derives from D4/D5 rather than from a
> snapshot frozen at run-start. This is a real, nameable gap. `[C-gap]`

## D3 — Version-control concerns

| Actor | Must know | First needed | Notes |
|-------|-----------|--------------|-------|
| Code | target branch; coordination branch; lane branch(es); integration branch; current branch; worktree HEAD; **destination_ref** per op; base branch for lanes; protected branches | P1→P6 | branch names derived from identity |
| Code | the **`worktree_root == destination_ref`** invariant (the atomicity kernel) | every write/commit | `safe_commit` enforces; the F2×F3 seam |
| User | which branch their work lands on; that they should **not** manually switch branches | P4 | the manual-switching loop is the pain |
| Agent | do **not** checkout/switch branches; where status auto-commits; which branch code goes on | P4 | prompts contradict this today (#1616) |

**Intuition:** VC facts are *derived from identity* (naming) + *git state* (current/HEAD). The
**destination + worktree pairing** is the load-bearing invariant — when it's wrong, agents get told
to "checkout the coord branch in main" and the loop starts. **Question:** is `base branch for lanes`
(F-02: lanes should inherit upstream commits) a VC concern or an interaction-process concern (D6)?
I lean D6 *decides* it, D3 *expresses* it. `[I]`

## D4 — Mission state (macro)

| Actor | Must know | First needed | Notes |
|-------|-----------|--------------|-------|
| Code | mission identity (id / slug / mid8 / run_id / type); meta facts (coordination_branch, target_branch); mission **phase** (planning / implementing / integrating / done); `lanes.json` | P1→P6 | the Mission Run instance |
| User | overall mission progress (kanban summary); "is it ready to merge / accept" | P3→P6 | |
| Agent | which mission; current phase; the **purpose/goal** (`purpose_context`) | each step | grounds the agent's intent |

**Intuition:** mission state is the *macro* state — the Mission Run. Distinct from per-WP state.
**Question:** is "phase" (planning vs implementing) explicit anywhere today, or only inferable from
which artefacts exist? I suspect inferable — which is a gap. `[I→C]`

## D5 — Work-package state (micro)

| Actor | Must know | First needed | Notes |
|-------|-----------|--------------|-------|
| Code | per-WP lane (9-lane FSM); dependencies + **readiness** ({approved,done}); claim actor; evidence per transition; review result; blocked/canceled | P3→P6 | the `MissionStatus` aggregate |
| User | which WPs are done / blocked / in-progress; what can be parallelized now | P4→P5 | |
| Agent | which WP to claim (ready + deps satisfied); current lane; the **next legal transition**; the evidence it must produce | P4→P5 | drives the implement-review loop |

**Intuition:** WP state = the event-sourced `MissionStatus` (doc `07`/`09` F5). The *micro* state.
This is the cleanest dimension — `status/` already owns it; the need is identity-keyed access via
context, not per-caller `feature_dir` archaeology. `[I✓ with 02/07]`

## D6 — Desired interaction process (parallelism / merge / workspaces)

| Actor | Must know | First needed | Notes |
|-------|-----------|--------------|-------|
| Code | the **lane plan** (which WPs share a lane → parallelism), from `lanes.json` (DAG + write-scope overlap); **merge strategy** (merge/squash/rebase) from config; workspace storage convention; stale-lane rebase policy; dependency-driven sequencing | P3→P6 | partly config, partly computed, partly doctrine |
| User | how much parallelism they want; **how to merge**; where workspaces live; conflict handling | P3 / P6 | operator choices |
| Agent | may I run in parallel (and ignore others' commits); which lane I'm in; when to rebase | P4 | |

**Intuition + corroboration:** D6 is the *policy/preferences* dimension — and corroboration confirms
it is the **most under-modeled**, with a precise picture of what exists vs aspirational. Stijn's
refinement: *strategy can be set per-run (MissionRun owns it), but the user usually has a
**preferential approach in their project charter*** — i.e. a **charter-default → per-run-override**
resolution chain. Reality today:

| Policy | State today | Citation |
|--------|-------------|----------|
| **Merge strategy** (merge/squash/rebase) | **Real chain ✓** — `CLI flag > .kittify/config.yaml merge.strategy > default(SQUASH)`; per-mission override persisted in `MergeState.strategy` | `merge/config.py:6-7,39-84`; `merge/state.py:78`; `merge.py:2177` |
| **Branch strategy** | **Extracted-but-dead** — `BranchStrategyConfig` is parsed from charter into `governance.yaml` but **never consumed** by runtime | `charter/schemas.py:70-75,131`; `charter/extractor.py` |
| **Execution / parallelism strategy** | **Nonexistent as policy** — execution lanes are a *static paradigm* (one-lane-at-a-time), not a selectable strategy; no config/charter field | `doctrine/paradigms/built-in/execution-lanes.paradigm.yaml:4-10` |
| **MissionRun policy slot** | **Missing** — `MissionRunSnapshot` has no `merge_strategy`/`execution_strategy`/`parallelism`/`branch_strategy` field; `policy_snapshot` only holds `strictness`/`default_route`/`extras` | `next/_internal_runtime/schema.py:523-536,435-437` |

> **Design implication:** the **charter-default → per-run-override** chain Stijn describes **exists
> only for merge strategy.** Branch strategy is extracted from charter but disconnected; execution
> strategy doesn't exist; MissionRun has no slot to own any of it. The target is to **generalize the
> merge-strategy precedence pattern into a first-class, persisted `MissionInteractionPolicy`**
> (charter default → config → per-run override), resolved at P3, persisted on the Mission Run,
> consumed at P4/P6 — which also *closes the dead branch-strategy extraction*. Strong intuition
> **confirmed and sharpened.** `[C]` `[C-gap]`

---

## Cross-cutting intuitions (to test)

1. **The need-set grows monotonically by phase, then *projects* per operation.** P0–P3 *accumulate*
   facts (identity → behaviours → topology → lane plan); P4–P6 *consume a projection* of them. This
   matches the fragment/composite split (`09`): accumulation = fragments; projection = composites. `[I]`
2. **Agents need a strict subset of what code needs — but stated as imperatives.** Every agent "must
   know" is "code resolved X, and tells the agent to act within X." So agent-facing prompts should be
   a *render* of the same context (I-6), never an independent source. `[I✓ with #1616]`
3. **Users mostly need *visibility + a few decisions*.** Their decisions cluster at P0 (governance),
   P1 (what), P3 (interaction policy: parallelism/merge), P6 (merge go/no-go). Between those they
   need *visibility*, not inputs. This suggests D6 is where the user's will is captured and then
   honored by code/agents downstream. `[I]`
4. **Two facts are conspicuously *unowned* today and appear in multiple dimensions:** mission
   **phase** (D4) and **interaction policy** (D6). **Interaction policy is now corroborated as
   unowned `[C]`** (merge strategy is the only piece with a real home; branch/execution strategy are
   dead/absent; MissionRun has no policy slot). Mission **phase** remains `[I→C]` (still to confirm).
   Both should become explicit, persisted Mission-Run facts.
5. **A third unowned binding surfaced:** the **activity ledger → behaviour** link (D2). The ledger
   exists and is written, but behaviour is resolved from the *frozen run-start template step*, not
   from the live activity. So "what should the agent be/do *now*" is bound at run-start, not at
   activity time. `[C-gap]`

> **Correction to `07` §2:** `07` reported `OperationalContext` as "exists, wired." More precisely:
> its builders (`build_operational_context_for_claim/_for_decision`) **are invoked** at live sites
> (`implement.py:826`, `agent/workflow.py:1268`, `runtime_bridge.py:2326`), so the object **is
> constructed** — but `invocation_context.py:9-11` still declares it an *unwired in-flight stub
> allowlisted in the dead-symbol test*, i.e. **constructed but contract-unsettled / likely not
> consumed downstream**. Net effect for us is *favorable*: F4 is early-stage and **malleable** — we
> can shape it as the execution-preferences fragment (and fold in the activity-ledger binding)
> without fighting a settled contract.

## Planned outputs (once corroborated)

- **Needs matrix** — D1–D6 × {Code/User/Agent} × P0–P7, promoted to **[✓]**.
- **BPMN** — the idea→working-code flow with swimlanes (User / Code / Agent) and the context
  resolved/consumed at each gateway.
- **Interaction diagrams** — per key operation (claim, implement, review, merge): who resolves which
  context, what's passed.
- **Model diagram** — fragments + composites + aggregates (refines `09`).

---

## Where I need you (next move)

This is lens 1 — my intuition, structured. Before I corroborate against docs/code, I want **your
intuition** layered in:

1. **Correct/extend the cells** — especially D6 (interaction process), where your operator intuition
   is the primary source, and the four `?` questions above (coord-worktree timing; behaviour↔state
   coupling; base-branch ownership; explicit phase/policy).
2. **The big intuition I want to test with you:** should **mission phase** (D4) and **interaction
   policy** (D6) become *explicit, persisted Mission-Run facts* rather than inferred? I suspect both
   are missing first-class concepts that this whole bug class partly stems from.
3. **Pick the corroboration order** — which dimension do we take into the docs (User Journeys) and
   then the code first? My instinct: **D6 then D3** (the two most under-modeled and most
   bug-adjacent), leaving D2/D5 (already largely modeled) for last.

Tell me where my intuition is wrong or thin, add yours, and point me at the first dimension — then I'll bring in the User Journeys.
