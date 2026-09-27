---
title: 'ADR: Transition gates are declarative, asset-backed, first-class doctrine artefacts'
description: 'Replaces the named-Python-handler gate registry with a declarative `gate` kind whose asset runs as an allowlisted interpreter plus argv, confined, after the trust check.'
status: Accepted
date: '2026-08-13'
related:
- docs/architecture/mission-gates.md
- docs/architecture/doctrine-kinds.md
- docs/adr/3.x/2026-08-13-1-built-in-mission-subtree-stays-nested-retire-legacy-step-contracts.md
- docs/adr/3.x/2026-08-13-4-executable-doctrine-runs-only-from-trusted-publishers.md
- docs/adr/3.x/2026-08-13-6-gate-outcomes-carry-severity-operator-strategy-decides-effect.md
---
# Transition gates are declarative, asset-backed, first-class doctrine artefacts

**Filename:** `2026-08-13-2-gates-are-declarative-asset-backed-doctrine-artefacts.md`

**Status:** Accepted (2026-09-27, amended in place)

**Date:** 2026-08-13 (proposed) · 2026-09-27 (amended and accepted)

**Deciders:** Operator (ATDD)

**Technical Story:** Follows [ADR 2026-08-13-1](2026-08-13-1-built-in-mission-subtree-stays-nested-retire-legacy-step-contracts.md),
which retires the legacy `MissionStepContract` surface that currently carries gate bindings.
Gate semantics must be re-homed onto the unified `MissionStep` model as part of that removal.
Implementation tracks the #2535 gate epic (#3418 gate kind, #3419 dispatcher, #3420 re-home
binding, #3421 `execute_dir`).

---

## Amendment note (2026-09-27)

Accepted together with [ADR 2026-08-13-4](2026-08-13-4-executable-doctrine-runs-only-from-trusted-publishers.md)
and [ADR 2026-08-13-6](2026-08-13-6-gate-outcomes-carry-severity-operator-strategy-decides-effect.md)
as one set, after the pack-trust ADR review (architect-alphonso / paula-patterns squad,
operator-approved 2026-09-27). The body below is **rewritten in place** so it no longer carries
text that the 2026-08-13 post-dialectics revision had superseded. Changes against the Proposed
text:

- The shell-string `entrypoint` (`python {asset} --strict`) and `disposition: fail_closed` are
  removed. Invocation is a structured `interpreter` + `args[]`; the outcome is a severity-bearing
  verdict whose effect ADR -6 decides.
- An **interpreter allowlist** is added (it was binding in #2599 and had been lost from this ADR).
- "Determinism enforced by a network-denied sandbox" is replaced by the concrete v1
  **refuse-unconfinable** baseline from #2540; OS-level sandboxing stays in #2541.
- A hard ordering invariant is added: nothing is resolved or executed before the ADR -4 trust
  check passes.
- `asset` must become activatable for gate use; open question 1 is resolved (pre-review stays a
  grandfathered code gate).

The 2026-08-13 dialectics pass (`work/gate-design-dialectics/`, `99-COHERENCE.md`) is folded into
the body: gate stays a first-class `ArtifactKind`, the outcome is a structured verdict, and
`spec-kitty-pre-review` stays a code gate.

## Context and Problem Statement

Today a transition gate is a **binding** in a step-contract YAML — `on_transition:
"in_progress->for_review"`, `handler: "spec-kitty-pre-review"`, `fail_open: true` — where
`handler` is a *name* into `GATE_REGISTRY` (`src/specify_cli/review/gate_registry.py`), a
Python dict whose `run: Callable[[TransitionGateContext], GateVerdict]` is compiled code.
The binding is data, but the **check logic is Python registered in-process**. There is
exactly one handler, and every gate fault is converted to a warning by `_mt_fail_open_gate`
(`src/specify_cli/cli/commands/agent/tasks_move_task.py`). The `GateBinding` fields
`handler_kind` and `fail_open` (`src/charter/offering/missions/step_contracts.py`) are declared
but never read.

Two problems: (1) adding a gate requires a code deploy (a new registered handler), not a
doctrine edit, so gates cannot ship as part of a mission-type's doctrine pack; (2) retiring
`MissionStepContract` (ADR 2026-08-13-1) removes the surface the gate binding lives on, so
gate semantics must move to the unified `MissionStep` model regardless.

Gates are **deterministic** — a simple code check or a script (documentation linting,
consistency checks, structural validation). That determinism is the lever: the check can be
declared as data and shipped in the pack rather than compiled into the CLI. Built-in already
ships such a script (`packs/built-in/assets/docs_structural_lint.py`) that nothing executes.

## Decision Drivers

- Gates should ship *with* the mission-type doctrine that needs them, per-type where relevant.
- Single canonical authority — one step model (`MissionStep`), one gate mechanism.
- Reuse the existing `asset` kind (the sanctioned way to ship executable logic downstream)
  rather than invent a second code-shipping mechanism.
- No shell surface: a declarative gate must not be a way to smuggle an arbitrary command line
  into a pack.
- Determinism must be preserved and enforced (gates are pure checks, never mutate state), with
  a baseline that ships now and needs no new dependency.

## Considered Options

- **A — Keep the Python handler registry**, add handlers as needed (status quo, code-deploy per gate).
- **B — Declarative `gate` artefact kind**, check logic referenced from an `asset`, invoked as an
  allowlisted interpreter plus an argv list.
- **C — Inline command strings** in the gate/step YAML (no asset), executed directly.

## Decision Outcome

**Chosen option: "B".** A gate is a **first-class doctrine `ArtifactKind`** (`gate`), tiered
and DRG-participating like every other kind, reusable by id. The ~8 totality-map edits a new
kind costs are accepted as the price of a uniform kind model (operator decision).

- **Code ships as an `asset`** (unchanged loose-contract inert blob, `mime` + `path`,
  resolved to a path, never auto-executed). The gate *references* the asset by id. `asset` is
  today excluded from activation (`_NON_AUGMENTATION_ELIGIBLE_KINDS` in
  `src/charter/offering/artifact_kinds.py`); it **must become activatable for gate use** so a
  gate's asset resolves through the same charter/DRG chain as the gate itself.
- **Structured invocation, no shell.** The gate declares `interpreter` plus `args[]`. `{asset}`
  is substituted as **one argv element** (the resolved asset path); it is never interpolated into
  a string. The process is spawned without a shell. This removes shell injection and the
  "`sys.executable` lacks the pack's dependencies" trap.
- **Interpreter allowlist.** The dispatcher accepts only vetted interpreter tokens (initially
  `python`) and maps each to a concrete executable itself. A gate can never name an arbitrary
  executable. Without the allowlist, `interpreter: sh` with `args: [-c, "..."]` is the shell
  again. A gate naming an interpreter outside the allowlist is refused at load time.
- **The outcome is a structured verdict carrying a severity**, not an exit code plus a
  per-gate fail-closed boolean. The verdict channel is a capped structured (JSON) payload.
  Block-vs-proceed is decided by the operator's error-handling strategy over the severity
  ladder — see [ADR 2026-08-13-6](2026-08-13-6-gate-outcomes-carry-severity-operator-strategy-decides-effect.md).
- **Determinism baseline (v1): refuse-unconfinable.** Every gate run gets the #2540 containment
  baseline: an environment allowlist, a dedicated process group killed on timeout plus
  `setrlimit` bounds, path confinement to the resolved execution context, and the capped
  verdict channel. If a capability probe shows the host cannot apply the baseline, the result is
  a **could-not-run** outcome (severity fixed by ADR -6) — **never an unconfined run**.
  OS-level sandboxing (network namespaces, seccomp and similar) remains follow-on work in #2541.
  The baseline applies to trusted packs as well: trust is not containment.
- **Ordering invariant (hard).** No asset is resolved and nothing is executed before the
  [ADR 2026-08-13-4](2026-08-13-4-executable-doctrine-runs-only-from-trusted-publishers.md)
  trust check has passed for the pack that ships the gate. Order: gate definition → trust
  check (including the dispatch-time re-hash) → asset resolution → execution-context stamping
  → confined run.
- **Binding lives on the `MissionStep`** (`gates: [{on_transition, gate: <id>}]`) —
  definition (what the check is) and binding (when it fires) are cleanly separated. This
  keeps the edge-scoped transition model and `TransitionGateContext`.
- **One generic dispatcher plus a few code gates.** `GATE_REGISTRY` gains one generic
  `declarative-gate` dispatcher that reads the gate, runs it as above, and returns a
  `GateVerdict`. Named per-gate Python handlers are not added any more.
  **`spec-kitty-pre-review` stays a grandfathered code gate**: its inputs are an injected
  `ScopeSource`, a baseline and the changed-files SSOT, not cwd plus an exit code, so it does not
  fit the declarative shape. It keeps its live never-break-`move-task` behaviour, mapped onto
  the ADR -6 severity model.

Shape of a gate definition:

```yaml
id: docs-structural-lint
schema_version: "1.0"
asset: common-docs-structural-lint   # asset id, resolved only after the trust check passes
interpreter: python                  # allowlisted token, never a free executable
args: ["{asset}", "--strict"]        # {asset} is one argv element; no shell string
executionTarget: primary             # ADR 2026-08-13-3 surface selector
timeout_seconds: 120
severity: RECOVERABLE                # severity for a *detected violation* (ADR -6)
```

### Consequences

#### Positive

- Adding/changing a gate is a doctrine edit, shippable per mission-type in the pack.
- One code-shipping mechanism (assets); the asset kind keeps its inert loose contract.
- No shell surface: the interpreter allowlist plus argv substitution closes injection by
  construction.
- Determinism is enforced by a baseline that ships without a new dependency, and a host that
  cannot apply it yields an honest could-not-run outcome instead of an unconfined run.

#### Negative

- "Execute an asset" is **net-new machinery** — assets are resolved to a path today and
  never executed (see [ADR 2026-08-13-3](2026-08-13-3-gate-execution-targets-through-kernel-surface-selector.md)
  for *where* it runs and [ADR 2026-08-13-4](2026-08-13-4-executable-doctrine-runs-only-from-trusted-publishers.md)
  for *whether* it may run).
- Making `asset` activatable for gate use touches the single canonical exclusion set and every
  consumer of it (org-pack loader, charter cascade).
- The v1 baseline does not deny network access at the OS level; that waits on #2541.

#### Neutral

- A new `gate` `ArtifactKind` is added shortly after `mission_step_contract` is removed — net
  kind count roughly unchanged, but the new kind is declarative-data, not a code registry.
- The interpreter allowlist is dispatcher configuration; widening it is a reviewed code change,
  not a pack edit.

### Resolved and open questions

1. *Resolved (2026-09-27):* `spec-kitty-pre-review` stays a single grandfathered code gate.
2. *Open:* one asset per gate, or may a gate carry its own blob (collapsing asset+gate for
   non-reused checks)?
3. *Open:* gate→asset DRG edge: reuse `requires`, or a dedicated relation?
4. *Open:* where gate *inputs* come from (env vars vs args vs cwd contents). Depth handled in
   ADR -3; whatever is chosen must pass the environment allowlist.
