---
title: Profile-Load Reliability (Squads & WP Prompts)
description: 'Why adversarial and research squads stopped loading charter agent profiles, and the stabilization design: resolve-then-inject, fail-loud dispatch, and /spk-load-profile.'
doc_status: active
updated: '2026-09-30'
audience: docs/context/audience/internal/maintainer.md
related:
- docs/architecture/governed-profile-invocation.md
- docs/architecture/multi-agent-orchestration.md
- docs/architecture/charter-backend-service-future.md
---
# Profile-Load Reliability (Squads & WP Prompts)

This document records a corroborated investigation into why **research / adversarial
squads recently stopped loading charter agent profiles**, and defines the **near-term
stabilization design**. The deployable charter-backend evolution that this
work makes possible is a **separate, backlog-scoped** design — see
[Charter Backend Service (Future)](charter-backend-service-future.md).

> **Status (2026-09-30).** Partly shipped. The activation-allowlist fix (#3810, §4.1)
> and the `directive:<id>` selector fix (#3816, §6 D1) shipped in 3.2.6. #3814 was closed.
> The rest is open on the **4.x Work** milestone: the orchestrator-injects contract
> (#3811, §4.2), `/spk-load-profile` (#3812, §4.3) and WP-prompt hygiene (#3813, §4.4).
> The charter-backend spike (#3815) stays in the Product backlog. Where the sections below
> say "3.2.6", read it as the cycle the design was written for.

> **Provenance.** Root cause established 2026-08-30 by five agents across four lenses
> (researcher, debugger, reviewer, architect), each profile-loaded through the
> charter API. The squad overturned an initial mis-attribution (see §2.4) and converged
> on the activation-allowlist root cause with live-command and git evidence.

> **Tracking.** Epic [#3809](https://github.com/spec-kitty/spec-kitty/issues/3809)
> ("squads must never dispatch unprofiled"). Children originally scoped to **3.2.6**: #3810 (activation-
> allowlist bug, §4.1), #3811 (orchestrator-injects fail-loud contract, §4.2), #3812
> (`/spk-load-profile`, §4.3), #3813 (WP-prompt hygiene, §4.4), #3816 (`directive:<id>`
> selector bug, §6 D1). In **Product backlog**: #3815 (charter-backend design spike) and
> #3814 (research/doc template parity — demoted post scope-review as purely additive).
> Hard dependency edges are encoded on the issues: #3810→#3811→#3812→#3813 (#3814 is a latent backlog edge — applies only if scheduled)
> (#3816 is a *soft* compaction edge on #3811, not a hard block).

## 1. Symptoms

Squad delegates dispatched at a point-cut (per the `adversarial-squad` skill) were
expected to load a doctrine lens via the charter API and act under it. Recently, delegates
assigned certain lenses acted **unprofiled** — no initialization, boundaries, directives,
or tactics applied — while nothing errored visibly at the orchestrator.

## 2. Root cause — a charter activation-allowlist gap (Issue 1)

The loading **mechanism is healthy**. In live testing, 7/7 *activated* profiles resolved
`EXIT 0` through `spec-kitty agent profile show <id>`, and `spec-kitty charter context
--action <x> --json` never failed. The failure is a **data + fail-open** defect, not a
code or template regression.

### 2.1 The gate

`src/specify_cli/cli/commands/profiles_cmd.py:337` (FR-014, introduced in #1636
`488fe34e0c`) refuses any profile absent from the charter's `activated_agent_profiles`
allowlist:

```
Error: profile 'doctrine-daphne' is not activated.
```

The two source files exist (`packs/built-in/agent_profiles/doctrine-daphne.agent.yaml`,
`…/randy-reducer.agent.yaml`) and are declared DRG nodes — they are **de-activated, not
missing**. Count check: **25 source profiles, 23 activated → the 2 omitted are exactly the
2 the squad skill recommends.**

### 2.2 The regression commit

`9a99801f1b` (2026-08-08, *"feat(charter): activate writing-comms & diagramming doctrine
set"*) first **materialized** the allowlist (23 entries) in
`.kittify/charter/charter.yaml:1744`, silently omitting `doctrine-daphne` and
`randy-reducer`. The parent commit had **no allowlist key** → three-state `None` → *all*
built-in profiles resolved (NFR-001 back-compat), so squads worked before that date. This
matches "recently stopped."

### 2.3 It ships upstream

`src/charter/activation/packs/default.yaml:187` — the built-in default charter pack — carries its own
narrower (16-entry) allowlist that **also omits both profiles**. **Every new project inherits the gap**,
not just this dogfooding checkout.

### 2.4 The seam gap (why it's silent)

The `adversarial-squad` skill
(`src/charter/offering/skills/adversarial-squad/SKILL.md`, `randy-reducer` at line 43,
`doctrine-daphne` at line 47) **hardcodes** those persona names with no reconciliation
against the activated set.
Its fallback clause sanctions reading the raw YAML **only for "a read-only harness that
cannot invoke the CLI."** A *de-activation* `EXIT 1` is a **different failure mode the
clause does not cover** — so a compliant delegate has no sanctioned recovery and proceeds
**unprofiled**. There is no canonical "squad-eligible profiles" query; the skill roster
and the activation set drifted apart the moment the allowlist was compiled.

> **Adjudicated divergence.** An initial trace blamed #1840 `60f038cee2` (2026-07-28) for
> flipping the load instruction from a YAML read to a CLI call. The debugger and architect
> lenses refuted this: #1840 **strengthened** the instruction (it never removed loading);
> the CLI works for any *activated* profile. The true cause is the 2026-08-08 allowlist.
> A secondary, narrower contributor remains for genuinely CLI-less harnesses: #1840's
> fallback YAML path has since drifted across two relocations.

## 3. Secondary finding — WP-prompt naming hygiene (Issue 2, LOW)

- **`ad-hoc-load` does not exist anywhere** (0 hits). It is a conflation; the real token
  is `/ad-hoc-profile-load`.
- `/ad-hoc-profile-load` is a **deliberately maintained, test-locked** (`tests/doctrine/
  test_spk_skill_pack.py:127`) compatibility alias for canonical
  `spk-doctrine-profile-load`. It **resolves correctly** — nothing is broken. This is
  canonical-naming drift (LOW), not a defect.
- Software-dev WP source templates reference the legacy alias
  (`packs/built-in/missions/software-dev/templates/task-prompt-template.md:31`, the
  `implement`/`review`/`tasks(-packages)` prompts, `reviewer-implementer-role-separation.
  tactic.yaml:26`, and the rc35 handoff migration).
- **`research` and `documentation` task-prompt templates carry no profile-load section at
  all** — a real cross-mission-type inconsistency, but *additive*, not a rename target.

## 4. Near-term stabilization design

Three coordinated changes. The activation-data fix restores squads immediately; the
orchestrator-injects contract closes the failure **class**.

### 4.1 Fix the activation data (close by construction)

Activate the two doctrine lenses everywhere the allowlist is authored:
- This project: `spec-kitty charter activate agent-profile doctrine-daphne randy-reducer`
  (or edit `charter.yaml` + `charter sync`).
- Upstream default pack: add both to `src/charter/activation/packs/default.yaml:187`.
- **Regression guard:** a test asserting *every lens the `adversarial-squad` skill names
  resolves `EXIT 0`* (or, equivalently, source-profile-count parity for squad-eligible
  lenses). This discharges directive 043 (close-by-construction) for these two instances; the failure **class** closes on §4.2 — see §6 D4.

### 4.2 Orchestrator-resolves-then-injects (the durable seam fix)

Make the **orchestrator** — the one context that reliably *can* resolve — load each lens
**once**, with overlays / `specializes_from` lineage / `enhances`/`overrides` applied, and
**inject the resolved profile + compact action context inline** into each delegate prompt.
Consequences:
- Removes the subagent's **mandatory** dependency on a runtime call (CLI *or* backend) — the
  injected floor is self-contained; on-demand pulls remain `required-capable` per §6 D1. Works for
  read-only, shell-less, headless, and stale-cached-copy harnesses alike.
- **Fail-loud by construction:** an unresolved / de-activated lens errors *at the
  orchestrator*, which substitutes, activates, or aborts — a delegate can **never** be
  dispatched unprofiled. This is what converts Issue 1's class from "silent unprofiled" to
  "loud at dispatch."
- **Provenance:** injected delegates run as sub-invocations under the orchestrator's own Op
  trail ([governed profile invocation](governed-profile-invocation.md)) — they open no
  separate Op, keeping the audit record uniform with the `dispatch --profile` path (§4.3).
- Use `charter context`'s existing `mode: compact`; inject profile-init + boundaries +
  directive **IDs**, not full bodies. Keep a *hybrid*: a runtime pull for an on-demand
  tactic stays **allowed where available** (sharpened to `required-capable` in §6 D1).

### 4.3 The `/spk-load-profile <id> <instructions>` primitive

Consolidate `spk-doctrine-profile-load` + the `ad-hoc-profile-load` alias into a single
dispatch primitive `/spk-load-profile <name|id> <instructions>` that both **resolves** the
profile and **carries the task** the profiled agent runs — the surface the orchestrator
emits under §4.2. Retain the two existing names as **redirecting aliases** (they are
test-locked — redirect, never delete). *(New surface: `/spk-load-profile` does not exist
today.)* Per §6 D3 this is a redirect/emitter over `dispatch --profile`, **not** a third
resolution engine (directive 044).

### 4.4 WP-prompt hygiene (LOW, optional)

If pursued, rename WP-template references `/ad-hoc-profile-load → /spk-load-profile`,
**keeping the leading slash**, and:
- **Exclude** the alias-*declaring* surfaces (`spk-doctrine-profile-load/SKILL.md:35`,
  `src/charter/offering/skills/README.md:116`) — they are test-locked; editing them goes red.
- Do it via a **new forward migration**, not by editing the shipped rc35 migration in
  place (mutating emitted text diverges already-migrated installs).
- Gate on `pytest tests/doctrine/test_spk_skill_pack.py`.
- The research/documentation missing-section gap is a **separate additive** item.

## 5. Scope boundary

| Near-term (shipped or queued) | Backlog |
|---|---|
| §4.1 activation-data fix + regression guard (shipped, #3810) | Deployable charter backend service (API/MCP) |
| §4.2 orchestrator-injects contract + fail-loud dispatch (#3811, 4.x Work) | Remote compute / shared cache / out-of-cycle context precompute |
| §4.3 `/spk-load-profile` consolidation (#3812, 4.x Work) | — |
| §4.4 WP-prompt hygiene (optional, LOW; #3813, 4.x Work) | — |

The backend evolution is deliberately **out of the near-term scope**. §4.2 is intentionally a transport
change the *orchestrator* owns, so a future backend slots in behind the **same resolution
contract** without touching delegates. See
[Charter Backend Service (Future)](charter-backend-service-future.md).

> **Freeze note.** The `adversarial-squad` skill and charter packs are doctrine surfaces;
> during the 3.2.x cycle some changes fell under the doctrine-surface freeze (`pr:deferred`). Sequence
> the data fix (§4.1) first — it restores squads with the least surface.

## 6. Dialectic review outcomes (2026-08-30)

Four dialectic squads (thesis ↔ antithesis, 8 profile-loaded delegates) stress-tested the
§4/§5 design. All four converged; none required synthesizer escalation. This section
**amends** the sections named. Confidence figures are the delegates' own.

### D1 — Resolution locus (§4.2): **hybrid, sharpened**

Thesis (inject, 0.8) and antithesis (live-resolve, HIGH-on-facts) agree the answer is the
hybrid §4.2 already names, but both narrow it:
- **Injection carries a fail-loud FLOOR** — resolved profile identity + boundaries + proof
  of successful resolution, **pinned at dispatch**. This is what makes "never dispatch
  unprofiled" true and is the *only* path for CLI-less/shell-less/headless harnesses.
- **On-demand pulls stay `required-capable`, not merely "allowed where available"** — a
  delegate that needs an unanticipated tactic/body must be able to pull it live where the
  harness permits; otherwise the on-demand path silently degrades on exactly the harnesses
  that need it. Do **not** freeze *everything*.
- **Two new must-fix findings (live-verified by the antithesis):**
  1. **`spec-kitty charter context --include directive:<id>` returns `EXIT 1` "No directive
     found"** for every directive ID tested (agent-profile and tactic selectors
     work; the *directive* selector does not). This makes "inject IDs, not bodies"
     (§4.2) a **dead end** — delegates cannot expand injected directive IDs. Fix the
     selector, or inject directive bodies. **Filed as #3816 (P1, Bug); fixed in 3.2.6.**
  2. **Sequencing dependency: §4.1 must land before any §4.2 injection rollout.** Injecting
     a resolved roster *today* would freeze the current 23-of-25 allowlist (daphne/randy
     de-activated) into every delegate with **no runtime recovery** — converting Issue 1
     from "silent unprofiled" into "silently *wrong* roster, permanently." A live delegate
     self-heals once §4.1 lands; an injected one cannot.

### D2 — Backend service (§4.2-future / charter-backend-service-future.md): **keep backlog** (0.8 / 0.85, convergent)

Both sides independently affirm the existing scope filing. The backend is the *right*
boundary and *right to defer*. Hard gates before it leaves backlog:
- Land §4.1 + §4.2 **first** — the backend fixes zero Issue-1 defects; a warm cache over
  the same omitted allowlist is "faster and more consistently wrong."
- **Design cache-invalidation before any cache is trusted** — a warm authority serving
  stale doctrine violates the fail-loud invariant. This must land *on paper first*.
- **Never a hard dependency** — degradation always falls back to in-process resolution,
  never to unprofiled dispatch.
- **Promotion triggers (a number, not an argument):** (1) measured resolution latency
  materially on the dispatch critical path; (2) ≥2 repos in one program sharing a
  centrally-refreshed corpus; (3) a real shell-less fleet dispatched by a non-orchestrator
  surface. *(Live corroboration: a delegate's own CLI resolved doctrine from a sibling fork
  checkout, not CWD — the environment-drift motivation is real but not yet urgent.)*

### D3 — `/spk-load-profile` shape (§4.3): **consolidate, but reconcile with `spec-kitty dispatch`**

Thesis (0.72) and antithesis (moderate-high) converge: consolidation's atomicity win is
real **for the orchestrator-emitted dispatch case**, but a naive `<id> <instructions>`
free-text positional is the wrong shape. **§4.3 is amended:**
- **`spec-kitty dispatch` already carries load+task** (task positional, `--profile` flag —
  `dispatch.py:225-232`). `/spk-load-profile` must be a **redirect/emitter over
  `dispatch --profile` + the §4.2 inject contract, not a third resolution engine**
  (directive 044 — else it duplicates `dispatch`).
- **`<instructions>` must be passed structurally, not as a bare positional tail** — mirror
  `dispatch`'s inversion, so there is no `<id> <instructions>` whitespace-split ambiguity.
- **Keep a load-only interactive path** — the "adopt a profile" trigger has no single task;
  `<instructions>` is optional, and pure-load must stay first-class and testable
  independently of task text.

### D4 — Issue 1 fix (§4.1 vs §4.2): **data-first, seam-closes** (0.85 / 0.85, convergent on sequencing)

- **§4.1 data fix is the correct primary *first* move** — smallest surface, clears the
  freeze, restores squads, and (with the guard) discharges directive 043 for these two
  instances. Apply at **both** authoring sites (`charter.yaml` + `default.yaml:187`).
- **§4.2 is the actual *class* close** — data alone leaves the fail-open fallback and the
  two-list drift intact; the class recurs on the next `charter sync`/de-activation.
- **Critical guard-design refinement (both delegates):** the §4.1 regression guard **must
  derive its lens list from a single canonical "squad-eligible profiles" query**, not a
  hand-copied list — otherwise it becomes a *third* drift-prone copy. That query is the
  **seed of §4.2** (one source consumed by the skill roster, the guard, and the injector).
- **Do not mark Issue 1 closed on §4.1 alone** — close it on §4.2; track §4.1 as mitigation.

### New tickets surfaced by the dialectic (filed post-review)

- **[Bug]** `charter context --include directive:<id>` selector returns `EXIT 1` for valid
  directive IDs (D1.i above) — blocks the inject-IDs compaction strategy. **Filed #3816.**
- **[Constraint]** the fail-loud contract's guard and injector must consume one canonical
  squad-eligible query (D4) — **folded into #3810/#3811 acceptance criteria.**
- **[Constraint]** `/spk-load-profile` reconciles with `dispatch --profile` and keeps a
  load-only path (D3) — **folded into #3812 acceptance criteria.**
