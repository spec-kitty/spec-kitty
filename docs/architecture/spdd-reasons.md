---
title: SPDD and the REASONS Canvas
description: Optional set of Spec Kitty built-in artifacts that records change-intent and change-boundary as a structured artifact alongside the spec and plan.
doc_status: active
updated: '2026-10-08'
type: explanation
audience: docs/context/audience/internal/lead-developer.md
---
# SPDD and the REASONS Canvas (opt-in artifact set)

This is an **optional** set of built-in Charter Pack artifacts. Projects that do not activate it see no
behavior change. Projects that do select it gain a structured way to capture
the *intent* and *boundary* of a mission's changes — separate from, and
additive to, the existing `spec.md`, `plan.md`, and `tasks.md`.

Pack scope: paradigm + two tactics + styleguide + directive + template
fragment + skill + this doc. Activation is one change to the active charter. There is
no new artifact kind, no new loader path, and no new template engine.

> **Mission status:** the pack ships with mission
> [`spdd-reasons-doctrine-pack-01KQC4AX`](../../kitty-specs/spdd-reasons-doctrine-pack-01KQC4AX/spec.md).
> See that mission's `spec.md`, `data-model.md`, and `quickstart.md` for the
> authoritative requirements (FR-001 through FR-020, C-001 through C-007).

---

## Why this exists

High-risk and multi-WP missions accumulate decisions that the spec captures
as requirements and the plan captures as architecture, but neither captures
in a way a reviewer can use as a *boundary* — a thing the implementation is
not supposed to cross without an explicit deviation.

A REASONS Canvas fills that gap. It is a small, agent-curated record of:

- what the mission is required to do (Requirements),
- what concepts it touches (Entities),
- which approach was selected and which were rejected (Approach),
- which surfaces are inside the change boundary (Structure),
- the ordered steps and tests (Operations),
- the conventions the change must respect (Norms), and
- the safeguards the change must not violate (Safeguards).

It is not a duplicate of the spec, plan, or code. It is a *change-intent
record* and a *change boundary*.

---

## Spec Kitty's adaptation of SPDD

Structured-Prompt-Driven Development (SPDD) in the wider literature treats
prompts and code as co-truth that must stay synchronized as prose mirrors
of one another. **Spec Kitty does not adopt that stance.**

In Spec Kitty:

- **Code is the source of truth for current behavior.** What the system
  does is determined by the code that runs, not by any document.
- **The REASONS canvas is the source of truth for *change-intent*.** It
  records what we agreed to change, what we agreed not to change, and the
  boundary that bounds the change.
- **"Sync" means keeping the canvas's intent record and change boundary
  accurate** as new information arrives — *not* mirroring the codebase as
  prose.

This distinction is constraint **C-005** of the SPDD/REASONS mission and
is the philosophical guardrail of every other artifact in this pack. If a
canvas update would require duplicating the codebase as prose, that is a
signal the canvas has slid out of scope; trim it back to intent and
boundary.

---

## What the REASONS Canvas is

A canvas is a markdown file at `kitty-specs/<mission>/reasons-canvas.md`
with seven required sections plus one append-only section:

| Section | Captures |
|---|---|
| **Requirements** | Problem statement, acceptance criteria, definition of done. |
| **Entities** | Domain concepts, relationships, canonical glossary terms. |
| **Approach** | Selected strategy and the tradeoffs of rejected alternatives. |
| **Structure** | Code surfaces affected, components, dependencies, ownership boundaries. |
| **Operations** | Ordered implementation steps and test strategy. |
| **Norms** | Coding conventions, observability rules, team rules. |
| **Safeguards** | Hard constraints, invariants, security and performance limits, things not to break. |

Plus:

| Section | Captures |
|---|---|
| **Deviations** *(append-only)* | `<date> — <wp> — <description> — <rationale>` for each approved deviation from the canvas. |

The canvas is per-mission. Per-WP focus is delivered as a *summary slice*
of the mission canvas during implement and review prompts — there is no
separate per-WP canvas file.

The seven-section skeleton lives at
`src/charter/offering/templates/fragments/reasons-canvas-template.md` and is what
the skill renders for new missions.

---

## Activation

Activation is a charter-time decision and is fully opt-in. Run the
[charter interview](../guides/how-to/governance/setup-governance.md) and select **any one** of
the following library items:

- paradigm `structured-prompt-driven-development`
- tactic `reasons-canvas-fill`
- tactic `reasons-canvas-review`
- directive `DIRECTIVE_038`

Selecting the paradigm is the typical case. Selecting only the directive is
allowed for teams that want the change-boundary rule without explicit
canvas authoring tooling. Selecting both tactics without the paradigm is
also allowed for teams that want the canvas authoring/review playbooks but
do not want a paradigm-level commitment.

Verify activation with:

```bash
spec-kitty charter context --action specify --json
```

When the pack is active, the response includes an "SPDD/REASONS Guidance"
subsection. When it is not, the response is byte-or-semantically identical
to a project that never selected the pack (constraint **C-002**, validated
by the inactive-baseline snapshot tests).

---

## Lifecycle behavior when active

The pack is wired into the charter context machinery so each workflow
action receives a scoped slice of REASONS guidance:

| Action | REASONS guidance the agent receives |
|---|---|
| `/spec-kitty.specify` | Requirements + Entities authoring guidance. |
| `/spec-kitty.plan` | Approach + Structure authoring guidance. |
| `/spec-kitty.tasks` | Operations + WP boundary guidance. |
| `/spec-kitty.implement` | Full WP-scoped canvas summary in the implement prompt. |
| `/spec-kitty.review` | Canvas as comparison surface; drift gate active. |

When the pack is **inactive**, none of these scopes inject any extra text
and command-template prompts render identically to current Spec Kitty
output.

---

## Generating and updating the canvas

The canvas is authored by the agent skill
`spk-charter-spdd-reasons` (built-in at
`src/charter/offering/skills/spk-charter-spdd-reasons/SKILL.md`). The skill is
triggered by any of the following phrases in user input:

- "use SPDD"
- "use REASONS"
- "generate a REASONS canvas"
- "apply structured prompt driven development"
- "make this mission SPDD"

When triggered, the skill:

1. Detects whether the SPDD/REASONS pack is active for the current
   project. If not active and the user demands enforcement, it
   *escalates* — it does **not** silently enforce.
2. Loads mission context: `spec.md`, `plan.md`, `tasks.md`, per-WP
   prompts, charter context, glossary, research notes, contracts, and
   relevant code references.
3. Renders or updates `kitty-specs/<mission>/reasons-canvas.md` from the
   seven-section template fragment.
4. **Preserves user-authored content.** When a section already contains
   user prose, the skill merges by appending or refining — never by
   silent rewrite.
5. On request, compiles a per-WP REASONS summary as a focused slice of
   the canvas scoped to a single work package.

Trigger the skill mid-mission to retrofit a canvas onto a mission that
started before the pack was activated; the skill will work from the
existing artifacts without overwriting them.

---

## The review gate

When the pack is active, the reviewer agent uses the canvas as a comparison
surface during `/spec-kitty.review`. Each WP review classifies the
implementation against the canvas using the **drift taxonomy**:

| Outcome | Meaning | Effect |
|---|---|---|
| `approved` | Implementation matches the canvas. | WP advances. |
| `approved_with_deviation` | Implementation diverged but the deviation is recorded. | WP advances; canvas Deviations log appended. |
| `canvas_update_needed` | The canvas was wrong; reality is correct. | Canvas updated; WP advances. |
| `glossary_update_needed` | Terminology conflict surfaced. | Glossary updated; WP advances. |
| `charter_follow_up` | Charter directive needs revisiting. | Follow-up scheduled; WP advances. |
| `follow_up_mission` | Out-of-bounds work belongs in a separate mission. | Mission filed; WP advances on what was in-bounds. |
| `scope_drift_block` | Unrecorded scope drift. | WP rejected. |
| `safeguard_violation_block` | A canvas Safeguard was violated. | WP rejected. |

**Charter directives take precedence over canvas content.** If the canvas
contradicts a charter directive, the charter wins and the canvas should be
updated. The canvas never overrides governance.

The drift gate **only activates for projects whose charter selected the
pack** (FR-018). Inactive projects see no review-behavior change.

---

## How this differs from prompts-as-truth

| Concern | Generic SPDD | Spec Kitty SPDD/REASONS |
|---|---|---|
| What is the source of truth for current behavior? | Prompt + code, kept synchronized. | **Code.** Always. |
| What does "sync" mean? | Mirroring code as prose. | Keeping the change-intent record and change boundary accurate. |
| What is a canvas? | A complete prose mirror of the system. | A change-intent record bounded by the current mission. |
| Can the canvas override code? | Sometimes, by re-generation. | No. Code is reality; the canvas describes intent for one mission. |
| What happens when implementation diverges? | Re-sync the prose. | Classify the divergence: deviation, canvas update, glossary update, charter follow-up, follow-up mission, scope drift block, or safeguard violation block. |

The short version: the canvas is a *change ledger*, not a *system mirror*.

---

## When NOT to use it

The pack adds value when there is meaningful change-boundary risk. It is
overhead in cases where the boundary is obvious or the work is small. Do
**not** activate (or, if active, do not generate a canvas) for:

1. **Tiny fixes** — typos, dependency bumps, single-line bug fixes. The
   diff *is* the canvas.
2. **Throwaway spikes** you intend to discard. Authoring a canvas for code
   you will delete tomorrow is wasted work.
3. **Emergency patches.** The triage path is "fix now, document later" —
   a post-hoc canvas (or a follow-up mission) is more appropriate than
   blocking the patch on canvas authoring.
4. **Pure visual exploration** — design experiments, layout iterations,
   prototype demos where the value is in the artifact you can show, not
   in the boundary you can enforce.

Activating the pack on a project where most missions fall in these
categories will produce friction without payoff. Prefer to leave it
inactive at the project level and trigger the skill *ad hoc* on the
specific high-risk missions where it earns its keep.

---

## Example A — Lightweight mission

> "Rename the `foo_v2` API surface to `foo`."

This is a one-WP mission with low architectural risk but real user impact.
A canvas is still useful as a one-page sanity check, but most sections can
be brief.

**Requirements**
- Problem: callers and docs reference `foo_v2`; we want them on `foo`.
- Acceptance: every reference to `foo_v2` outside deprecation shims is gone.
- Definition of done: deprecation shim ships with a clear sunset date.

**Entities**
- `foo_v2` (the deprecated symbol).
- `foo` (the canonical symbol).
- Deprecation shim (the temporary forwarder).

**Approach**
- Add `foo` as the canonical symbol. Re-point internals. Keep `foo_v2` as
  a deprecation shim that delegates to `foo` and emits a warning.
- Rejected: hard rename without a shim (breaks downstream).

**Structure** — *brief*. Files: `src/foo/api.py`, `docs/api/foo.md`,
the shim module.

**Operations**
1. Add `foo` symbol mirroring `foo_v2`.
2. Re-point internal callers.
3. Convert `foo_v2` to a thin deprecation shim.
4. Update docs and the migration note.

**Norms** — *brief*. Standard project conventions; no special rules.

**Safeguards**
- No breaking change to clients on the `foo_v2` name within the
  deprecation window (one minor release minimum).
- Deprecation warning must include the sunset version.

This canvas is one screen of markdown. Approach, Structure, and Norms can
remain short. The value is in the explicit Safeguards: a reviewer can
detect a diff that violates the deprecation timeline at a glance.

---

## Example B — High-risk multi-WP mission (`DIRECTIVE_038` carries weight)

> "Introduce a new auth middleware."

This mission spans WPs that touch session storage, API ingress, and
observability. The canvas pays for itself the first time it catches a
safeguard violation in a diff.

**Requirements**
- Problem: today the API trusts a header set elsewhere; we need a
  middleware that validates tokens, materializes a principal, and gates
  protected routes.
- Acceptance: explicit threat model coverage (token theft, session
  fixation, replay), SLO targets for the middleware path.
- Definition of done: rollout plan executed, feature flag flipped, old
  code path removed.

**Entities**
- `Token` (opaque bearer credential).
- `Session` (server-side state keyed by `session_id`).
- `Principal` (authenticated identity exposed to handlers).
- All three are linked to canonical glossary terms.

**Approach**
- Selected: a middleware in the ingress chain that validates the token,
  loads the session from encrypted storage, and attaches the principal to
  the request.
- Rejected (with rationale): a per-handler decorator (too easy to
  forget); a sidecar process (adds an out-of-band dependency we do not
  need yet).

**Structure**
- Surface boundary: middleware owns token validation, session lookup, and
  principal materialization.
- Handlers own authorization decisions on the materialized principal.
- Storage layer owns at-rest encryption. Observability owns redaction.

**Operations**
- WP01: introduce middleware module and unit tests.
- WP02: add encrypted session store.
- WP03: wire middleware into ingress, gated by feature flag.
- WP04: cut handlers over to the principal.
- WP05: ship rollout — flip the flag, remove the old path.

**Norms**
- Structured logging keys are fixed (`event`, `principal_id`, `session_id`).
- Redaction rules apply to every log line touching credentials.

**Safeguards**
- **No plaintext token in logs**, ever.
- **No `session_id` outside encrypted storage.**
- **No breaking change to OAuth callbacks** during the rollout.
- Middleware path adds no more than 2ms of p99 latency on the gateway.

This canvas is what the reviewer checks every WP diff against:

- WP02 adds a debug log statement that includes the raw token? **Safeguard
  violation block** — the diff cannot land.
- WP03 changes the OAuth callback contract to add a new required
  parameter? **Safeguard violation block.**
- WP04 changes the principal type to include an extra field beyond what
  the canvas's Entities described? **Scope drift block** — either record
  a deviation or schedule a canvas update.

`DIRECTIVE_038` is what makes those blocks enforceable: it is the
charter-level rule that says "implementations must stay within the
approved canvas's Requirements, Operations, Norms, and Safeguards unless
a deviation is explicitly recorded."

---

## Related artifacts

Data artifacts ship under the built-in pack root `packs/built-in/`; the template fragment and skill stay in the source tree under `src/charter/offering/`:

| Kind | Path |
|---|---|
| Paradigm | `packs/built-in/paradigms/structured-prompt-driven-development.paradigm.yaml` |
| Tactic — fill | `packs/built-in/tactics/reasons-canvas-fill.tactic.yaml` |
| Tactic — review | `packs/built-in/tactics/reasons-canvas-review.tactic.yaml` |
| Styleguide | `packs/built-in/styleguides/reasons-canvas-writing.styleguide.yaml` |
| Directive | `packs/built-in/directives/038-structured-prompt-boundary.directive.yaml` |
| Template fragment | `src/charter/offering/templates/fragments/reasons-canvas-template.md` |
| Skill | `src/charter/offering/skills/spk-charter-spdd-reasons/SKILL.md` |

Mission seed material:

- [Mission spec](../../kitty-specs/spdd-reasons-doctrine-pack-01KQC4AX/spec.md)
- [Data model (full canvas semantics)](../../kitty-specs/spdd-reasons-doctrine-pack-01KQC4AX/data-model.md)
- [Quickstart (activation walkthrough)](../../kitty-specs/spdd-reasons-doctrine-pack-01KQC4AX/quickstart.md)
- [Research and ADRs](../../kitty-specs/spdd-reasons-doctrine-pack-01KQC4AX/research.md)

Related Spec Kitty docs:

- [How to set up project governance](../guides/how-to/governance/setup-governance.md) — the
  charter interview is where you opt into this pack.
- [Spec-driven development explained](spec-driven-development.md) —
  the broader workflow that the canvas slots into.
