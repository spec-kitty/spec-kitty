---
title: 'ADR 2026-06-11-1: Op as a First-Class Execution Artifact (Mission ⟷ Op ⟷ ad-hoc)'
description: 'Names the Op — a bounded, doctrine-governed, immediately dispatched action with a durable record — as the one primitive shared by ad-hoc dispatch and lifecycle flows.'
status: Accepted
date: '2026-06-11'
doc_status: active
kind: ADR
updated: '2026-06-11T00:00:00Z'
---

## Context and Problem Statement

`spec-kitty dispatch` opens bounded, doctrine-governed agent actions that run
immediately — no spec, no plan, no work
packages, no lane worktree — yet they still load governance context, route to an
agent profile, and produce a durable record. The implementation lives in
`src/specify_cli/invocation/` and already emits `OpStartedEvent` /
`OpCompletedEvent` (see `src/specify_cli/invocation/__init__.py`), but the
**concept** these commands express has never been named or ratified at the
architecture level. #1688 (the proposal, now closed/superseded into this ADR)
diagnosed the gap precisely: the records were treated as scratch byproducts of
"governance machinery" rather than as instances of a real unit of work.

Two epics now press on the same gap from different directions:

- **#1804 (Ops execution layer)** wants a durable, governed, queue-backed
  execution artifact for standalone dispatch. It has **no ADR** — it is the highest-value
  architecture gap in `work/EPIC_ARCHITECTURE_CORRELATION.md`.
- **#1802 (pre/post-mission lifecycle)** wants bounded, governed flows that sit
  *outside* a Mission's spec→merge loop: an **intake** flow before a Mission
  exists and a **correction** flow after a Mission has merged.

Both want the same thing: *a bounded, doctrine-governed action with a durable
record and no full Mission lifecycle.* Left unguided, #1804 and #1802 would each
mint their own primitive — two parallel abstractions for one shape. The
mission's binding constraint **C-005 (single source of truth — no parallel
narrative/abstraction surfaces)** forbids that. This ADR is the seam that
prevents the divergence: it names the shared primitive **once** so both epics
build on it rather than beside it.

The decision matters now because `OpStartedEvent`/`OpCompletedEvent` are already
in the codebase. Ratifying the concept before #1804/#1802 land code is the
cheapest moment to converge; after, we would be unifying two shipped primitives.

## Decision Drivers

- **C-005 — one abstraction, not two.** #1804 (Ops) and #1802 (lifecycle) must
  share a single execution primitive.
- **Screaming the tier.** The tier between a full Mission and an ungoverned
  ad-hoc shell command must be a named, discoverable concept, not an emergent
  property of three sibling commands.
- **Durability + governance without the full planning loop.** The primitive must carry real
  doctrine context and a permanent trace, while staying lighter than a Mission
  (no spec/plan/tasks/worktree/merge).
- **Coherence with the current execution shapes.** Any execution-context,
  commit, or status mechanics the Op touches must reference the *canonical*
  surfaces (`mission_runtime`, `core/commit_guard`, the append-only status
  event log), never the retired ones.

## Considered Options

- **Option A — Two primitives (status quo drift):** let #1804 build an "Ops"
  artifact and #1802 build a separate "lifecycle flow" artifact.
- **Option B — One shared primitive: the Op (chosen).** Ratify the Op as the
  single tier between Mission and ad-hoc; pre/post-mission lifecycle flows are
  Ops, not a parallel concept.
- **Option C — Fold everything into Mission:** model intake/correction/dispatch
  as degenerate Missions.

## Decision Outcome

**Chosen option: "Option B — One shared primitive: the Op."**

### What an Op is

An **Op** is a *bounded, doctrine-governed agent action, dispatched immediately,
that produces a durable governed record without a full Mission lifecycle.* It is
to `dispatch` what a Mission is to the
spec→plan→tasks→implement→review→merge loop: lighter, immediate, no planning
loop — but real work, real doctrine, real record.

The Op lifecycle is a short dispatch loop, not a Mission state machine:

1. **Route** — resolve the operator request to an agent profile (explicit
   `--profile`, else the router). Ambiguous handles fail closed (no silent
   fallback), consistent with the identity-selector rule.
2. **Load governance context** — assemble the action-scoped doctrine payload for
   the resolved profile (the same charter-context surface a Mission step uses).
3. **Open a durable Op record** — append an `OpStartedEvent` to the append-only
   audit trail (`src/specify_cli/invocation/`).
4. **Agent acts on the panel** — the dispatched agent does the work under the
   loaded governance context; the CLI does not perform the work itself.
5. **Close the Op** — append an `OpCompletedEvent` with the real outcome.

An Op carries a `ModeOfWork` (`task_execution`, `mission_step`, or `query`, per
`src/specify_cli/invocation/modes.py`). The Op record is the durable trace; durability is a
*property of the artifact*, not a bolt-on. (#1688 framed the original
two-invocation durability bug as a symptom of this missing concept; naming the Op
resolves it structurally.)

### The three execution tiers

| Tier | Lifecycle | Governance | Durable record | Workspace |
|---|---|---|---|---|
| **Mission** | spec → plan → tasks → implement → review → merge | full doctrine + step contracts | mission artifacts + status event log | lane worktrees + mission branch |
| **Op** | route → context → record → act → close | action-scoped doctrine payload | `OpStartedEvent` / `OpCompletedEvent` trail | none (acts in the current checkout) |
| **ad-hoc** | none | none | none | none |

The Op is the **governed middle tier**. The distinction from ad-hoc is exactly
governance + durability: an ad-hoc shell command is ungoverned and untraced; an
Op is governed and traced. The distinction from a Mission is the absence of the
planning loop, work packages, and dedicated worktrees.

### Pre/post-mission lifecycle flows are Ops (the C-005 unification)

The binding clause of this ADR: **pre/post-mission lifecycle actions (#1802) are
Ops, not a second primitive.**

- **Intake Op** — a pre-mission flow (e.g. triaging a request into a future
  Mission) is an Op: bounded, governed, durable-recorded, no Mission yet.
- **Correction Op** — a post-merge flow (e.g. a governed follow-up fix after a
  Mission has merged) is an Op: bounded, governed, durable-recorded, no new
  Mission.

Epics #1804 (Ops) and #1802 (lifecycle) therefore consume **one** abstraction.
Epic #1804 builds the Op artifact and its queue-backed durability; #1802's
intake/correction flows are *modes of dispatching an Op*, not a parallel artifact
type. Neither epic may mint a competing primitive — doing so reintroduces the
C-005 violation this ADR exists to prevent.

### Coherence with the canonical execution shapes (binding)

Where an Op touches execution mechanics, it consumes the **current canonical
surfaces** — never the retired ones:

- **Execution context.** If an Op needs resolved context, it calls
  `resolve_action_context` from **`mission_runtime`**
  (`src/mission_runtime/resolution.py`), which returns the immutable
  `ExecutionContext` value object (`src/mission_runtime/context.py`). The retired
  `specify_cli/core/execution_context.py` path and the value-object's old
  home are historical — see ADR
  [`2026-06-07-1-execution-state-canonical-surface.md`](2026-06-07-1-execution-state-canonical-surface.md)
  and the 2026-06-10 addendum to
  [`2026-06-03-2-executioncontext-owner-and-committarget.md`](2026-06-03-2-executioncontext-owner-and-committarget.md).
- **Commit safety.** Ops run in the operator's current checkout, so most Ops do
  not commit at all. Any Op that *does* create a commit routes its protection
  decision through the single policy seam `core.commit_guard.evaluate`
  (`src/specify_cli/core/commit_guard.py`) — the **one** protected-branch
  decision (C-GUARD-1). The destination is carried as the canonical
  `CommitTarget(ref: str, kind: CommitTargetKind)` value object
  (`kind ∈ {PRIMARY, COORDINATION, FLATTENED}`), and authorization is the
  asserted-at-the-surface `GuardCapability` parameter — never derived from
  message text, file content, env, or op records. An Op carries no special
  protected-branch privilege: its default capability is
  `GuardCapability.STANDARD`. This is the delivered `(ref, kind)` /
  `GuardCapability` shape (Strangler step 7, delivered across missions 01KTPKST +
  01KTRC04), **not** the retired `(worktree_root, destination_ref)` sketch.
- **Status.** An Op never drives the 9-lane WP status machine; the append-only
  Op event trail is its sole record. WP lane state remains the exclusive
  authority of the status event log and is untouched by Ops.

### Consequences

#### Positive

- #1804 and #1802 build on one ratified primitive — C-005 holds; no parallel
  abstraction.
- The execution layer gains a named, discoverable middle tier; the "missing
  concept" #1688 identified is closed.
- Op durability is structural (the artifact owns its trail), so the original
  two-invocation durability failures cannot recur as one-off patches.
- The Op's mechanics are pinned to the canonical execution surfaces, so the
  layer cannot drift back onto the retired `execution_context.py` /
  `(worktree_root, destination_ref)` shapes.

#### Negative

- `OpStartedEvent`/`OpCompletedEvent` and the `invocation/` package predate this
  ratification; #1804 must reconcile the shipped event/record shapes with the
  ratified concept (rename/relocate work is implementation scope, tracked under
  #1804, not this ADR).

#### Neutral

- This ADR ratifies the *concept and boundaries*; the durable queue-backed
  storage mechanics (#1804) and the intake/correction dispatch surfaces (#1802)
  are designed in their own implementation specs, governed by this seam.

### Confirmation

The decision is confirmed when #1804 and #1802 both reference this ADR as their
architecture anchor and neither introduces a competing execution primitive — i.e.
`work/EPIC_ARCHITECTURE_CORRELATION.md` shows the #1804 Ops gap closed (mission
success criterion SC-2) and #1802 listed against this ADR. Confidence: high —
the Op shape is already partially expressed in shipped code (`OpStartedEvent` /
`OpCompletedEvent`, `ModeOfWork`), so this ratifies an emergent reality rather
than proposing a speculative one.

## Pros and Cons of the Options

### Option A — Two primitives (status-quo drift)

Let #1804 and #1802 each define their own artifact.

**Pros:**

- No coordination needed between the two epics up front.

**Cons:**

- Direct C-005 violation: two abstractions for one shape.
- Guarantees future consolidation debt (unifying two shipped primitives).
- The execution-layer concept stays unnamed and undiscoverable.

### Option B — One shared primitive: the Op (chosen)

Ratify the Op as the single Mission ⟷ ad-hoc tier; lifecycle flows are Ops.

**Pros:**

- Satisfies C-005 — one primitive, two consumers.
- Names a real, already-emergent concept; closes the #1688 gap structurally.
- Pins Op mechanics to canonical execution surfaces.

**Cons:**

- Requires #1804 to reconcile pre-existing `invocation/` shapes with the
  ratified concept.

### Option C — Fold everything into Mission

Model intake/correction/dispatch as degenerate Missions.

**Pros:**

- Reuses the existing Mission machinery.

**Cons:**

- Forces the full planning loop (spec/plan/tasks/worktree/merge) onto bounded
  immediate actions — the exact weight the Op tier exists to avoid.
- Pollutes the Mission state machine and status authority with non-Mission work.

## Adjudications (WP06 — escalated from WP02's approved review)

Two cross-cutting items in the architecture surface were escalated for the
architect to adjudicate. They are recorded here because they belong to the
`architecture/3.x/adr/**` authority this WP owns.

### Adjudication 1 — Charter authority-path modernization: **deferred**

**Finding.** The charter's default authority pointer for architectural intent
(`charter.context_renderers.authority_paths.DEFAULT_AUTHORITY_PATHS`) still cites
`architecture/2.x/adr/`, while `architecture/3.x/adr/` is the canonical track.

**Decision: defer the flip, with a sanctioned recovery path.** Rationale:

1. **Not broken today.** WP02's living layout converted the post-cutover 2.x ADR
   paths into back-compat **symlinks into `3.x/`**, and the renderer is
   existence-gated. So `architecture/2.x/adr/` still resolves; the pointer is a
   back-compat *alias*, not a dangling link. The modernization is a clarity
   improvement, not a correctness fix.
2. **The true blast radius exceeds the sanctioned chain.** The flip's enumerated
   chain was: `authority_paths.py` → the two software-dev SOURCE prompt templates
   → regenerated agent copies → two contract tests
   (`test_template_governance_payload_contract.py`,
   `test_wp_prompt_governance_contract.py`) → the twelve-agent parity baselines.
   Investigation found **three additional surfaces outside that chain** that
   assert the `2.x/adr/` default and would break on a flip:
   `tests/charter/test_context_authority_paths.py`,
   `tests/charter/test_sync_authority_paths.py`, and
   `tests/charter/test_schemas_additive_fields.py`. It also requires
   re-coordinating `.kittify/charter/charter.md` — a file **WP02 owns** and which
   WP02 deliberately left annotated as `architecture/2.x/adr/  # 2.x-era
   architectural decisions (historical)` alongside a separate active
   `architecture/adrs/` entry. Flipping the default unilaterally from WP06 would
   reach across the WP02 ownership boundary and beyond the enumerated chain.
3. **Per the WP06 mandate**, when the flip requires surfaces beyond the
   enumerated chain, the sanctioned action is to record a reasoned deferral here
   rather than improvise a partial, test-breaking flip.

**Recovery path (when undertaken).** Do all links together, in one change:
flip `DEFAULT_AUTHORITY_PATHS` and its docstrings → update both software-dev
SOURCE prompt templates (`implement/prompt.md`, `review/prompt.md`) → regenerate
agent copies via the documented upgrade flow → update the two governance-contract
tests → update the three `tests/charter/` assertions → re-coordinate
`.kittify/charter/charter.md` with the owning WP → regenerate the twelve-agent
parity baselines (`PYTEST_UPDATE_SNAPSHOTS=1 pytest tests/specify_cli/regression/`)
and commit the baselines *with* the template change → confirm
`pytest tests/architectural/` green. This is a coherent follow-up Op/mission, not
a WP06 side effect.

**Addendum — 2026-06-12 — EXECUTED** (WP07, mission `name-vs-authority-remediation-01KTYGTE`):
The deferred flip was executed in full. All seven chain links landed atomically:

1. `src/charter/context_renderers/authority_paths.py` `DEFAULT_AUTHORITY_PATHS` flipped
   `architecture/2.x/adr/` → `architecture/3.x/adr/`; module docstring and dict docstring updated.
2. Both source prompts updated: `src/doctrine/missions/mission-steps/software-dev/implement/prompt.md`
   and `review/prompt.md`.
3. Two governance-contract tests updated: `tests/architectural/test_template_governance_payload_contract.py`
   (fixture directory + two path assertions) and `tests/specify_cli/next/test_wp_prompt_governance_contract.py`
   (inline charter string, `adr_path_present` check, self-sufficiency regex extended to `[23]\.x`).
4. Three `tests/charter/` assertions updated: `test_context_authority_paths.py`,
   `test_sync_authority_paths.py`, `test_schemas_additive_fields.py`.
5. `.kittify/charter/charter.md` line 317 annotation updated
   (`architecture/3.x/adr/ # canonical architectural decisions (3.x era)`).
6. Twelve-agent parity baselines regenerated via
   `PYTEST_UPDATE_SNAPSHOTS=1 pytest tests/specify_cli/regression/` — 26 baseline files
   updated (13 agents × implement + review); no other baseline churn observed.
7. `pytest tests/architectural/ -q` fully green post-flip.

No 2.x-pointing authority default remains in any active code path.

### Adjudication 2 — Duplicate `doctrine-layer-merge-semantics` ADR: **3.x is canonical (already resolved by WP02)**

**Finding.** `2026-05-16-1-doctrine-layer-merge-semantics.md` existed in both
`2.x/adr/` and `3.x/adr/`; `docs/explanation/org-doctrine-layer.md` linked the
2.x copy.

**Decision: `architecture/3.x/adr/` is canonical for this ADR; the 2.x path is a
back-compat pointer.** This is consistent with the era rule WP02 recorded in
`architecture/3.x/adr/README.md` ("This folder is canonical for 3.x decisions.
Back-compat symlinks at the old `architecture/2.x/adr/<filename>` paths point
here"). WP02 already converted the 2.x copy into a **symlink** into `3.x/`, so
the duplication is structurally resolved — there is one canonical file. The only
residual action is editorial: the stale 2.x link in
`docs/explanation/org-doctrine-layer.md` is repointed at the canonical 3.x path
(done as part of this WP, with a one-line out-of-map rationale).

## More Information

- Mission spec (FR-007): `kitty-specs/doctrine-glossary-architecture-consolidation-01KTNWFC/spec.md`
- Proposal (superseded into this ADR): [#1688](https://github.com/Priivacy-ai/spec-kitty/issues/1688)
- Consuming epics: [#1804](https://github.com/Priivacy-ai/spec-kitty/issues/1804) (Ops), [#1802](https://github.com/Priivacy-ai/spec-kitty/issues/1802) (lifecycle), [#1810](https://github.com/Priivacy-ai/spec-kitty/issues/1810) (dispatch collapse)
- Current Op surface in code: `src/specify_cli/invocation/` (`OpStartedEvent` / `OpCompletedEvent`, `ModeOfWork`), `src/specify_cli/cli/commands/{dispatch,profile_invocation,invocations_cmd}.py`
- Canonical execution surfaces: ADR [`2026-06-07-1-execution-state-canonical-surface.md`](2026-06-07-1-execution-state-canonical-surface.md) (`mission_runtime`); ADR [`2026-06-03-2-executioncontext-owner-and-committarget.md`](2026-06-03-2-executioncontext-owner-and-committarget.md) + its 2026-06-10 addendum (`CommitTarget(ref, kind)`, step 7 delivered); `src/specify_cli/core/commit_guard.py` (`GuardCapability`, single `evaluate`)
- Correlation matrix: `work/EPIC_ARCHITECTURE_CORRELATION.md` (Ops gap → SC-2)
