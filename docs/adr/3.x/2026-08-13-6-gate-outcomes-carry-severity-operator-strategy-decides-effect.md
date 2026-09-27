---
title: 'ADR: Gate outcomes carry a typed severity; an operator-configured error-handling strategy decides the CLI effect'
description: 'Gate outcomes carry a typed severity; an operator strategy maps it to the CLI effect. The default blocks at BLOCKING only; trust failures are always BLOCKING.'
status: Accepted
date: '2026-08-13'
related:
- docs/architecture/mission-gates.md
- docs/adr/3.x/2026-08-13-2-gates-are-declarative-asset-backed-doctrine-artefacts.md
- docs/adr/3.x/2026-08-13-4-executable-doctrine-runs-only-from-trusted-publishers.md
---
# Gate outcomes carry a typed severity; an operator-configured strategy decides the CLI effect

**Filename:** `2026-08-13-6-gate-outcomes-carry-severity-operator-strategy-decides-effect.md`

**Status:** Accepted (2026-09-27, amended in place)

**Date:** 2026-08-13 (proposed) · 2026-09-27 (amended and accepted)

**Deciders:** Operator (ATDD)

**Technical Story:** Resolves the fail-closed ([ADR 2026-08-13-2](2026-08-13-2-gates-are-declarative-asset-backed-doctrine-artefacts.md))
vs skip-and-proceed ([ADR 2026-08-13-4](2026-08-13-4-executable-doctrine-runs-only-from-trusted-publishers.md))
contradiction the dialectics pass surfaced. Instead of a per-gate boolean disposition, gate
outcomes are typed by severity and the CLI effect is an operator policy. Implementation tracks
#3416 (minimal kernel ladder) and #3417 (strategy).

---

## Amendment note (2026-09-27)

Accepted together with ADR -2 and ADR -4 as one set, after the pack-trust ADR review
(architect-alphonso / paula-patterns squad, operator-approved 2026-09-27). The body is
**rewritten in place**. Changes against the Proposed text:

- **Contradiction fixed.** The Proposed text defined `RECOVERABLE` as "may proceed degraded" but
  made the default `block_above(RECOVERABLE)`, which blocks it. The default now **blocks at
  `BLOCKING` only**; `RECOVERABLE` proceeds degraded and is recorded loudly.
- **Could-not-run severities are fixed by the dispatcher**, not declared by the gate. This answers
  the 2026-08-15 fail-open reconcile question on #2535/#2599/#3417 with reading (a): machinery
  faults are `RECOVERABLE`, trust and tamper failures are `BLOCKING`.
- **Guardrail added:** repository-committed configuration cannot demote trust or tamper outcomes
  below `BLOCKING`; the effective strategy is surfaced in every verdict.
- **Scoping (open question 4) resolved:** a minimal kernel ladder ships first; consolidating the
  other Severity enums is follow-on debt (#3416), not a precursor.
- Stale reference fixed: `status/doctor.py` `Severity` is now at line 33.

## Context and Problem Statement

The gate design produced two conflicting per-gate booleans: gates flip **fail-closed** (block on
failure), but untrusted packs were to be **skipped** (proceed). Same un-run gate, opposite
outcomes, decided by *why* it did not run — and the "skip" branch silently no-ops security gates
in CI. A single boolean cannot express "proceed, but degraded, and record it," which is the real
operator need for many checks (a docs lint failing should not necessarily block a transition; a
missing security gate should).

The live behaviour adds a constraint. The **C-003 invariant — gate evaluation never breaks
`move-task`** — is implemented by `_mt_fail_open_gate`
(`src/specify_cli/cli/commands/agent/tasks_move_task.py`, FR-013), which turns any gate
exception into an unverified `NO_COVERAGE` warning. Any new model must keep that promise for
machinery faults without extending it to security failures.

The codebase already has the ingredients, **fragmented across five sites**:
`kernel.glossary_types.Severity` (`src/kernel/glossary_types.py:70`), `audit.models.Severity` +
its threshold `fail_on: Severity | None` with `severity <= fail_on_threshold`
(`src/specify_cli/audit/models.py:47,53,203`), `status.doctor.Severity`
(`src/specify_cli/status/doctor.py:33`), the charter-lint `SEVERITY_ORDER` blocking ladder
(`src/specify_cli/charter_runtime/lint/findings.py`, consumed by `analysis_report.py`), and
the `strictness` literals (`kernel.glossary_types.Strictness`, `runtime … schema.py`). The
`audit` module is already *exactly* the "block above a threshold" pattern requested.

## Decision Drivers

* One coherent model for "what happens when a check does not pass," across failed / degraded /
  informational / could-not-run outcomes.
* Operator owns strictness, not each gate author — mirrors linter/typechecker strictness config.
* Security and trust failures fail closed; machinery faults never silently pass and never break
  `move-task` (C-003).
* Do not add a **sixth** Severity enum; converge on one canonical ladder — without making that
  convergence a blocker for the gate work.

## Decision Outcome

**A gate produces a typed outcome; the operator's error-handling strategy maps it to a CLI
effect.**

* **Severity ladder** (`ERROR_SEVERITY`): `BLOCKING` > `RECOVERABLE` > `WARN` > `INFO`.
  `RECOVERABLE` means "the system proceeds in a **degraded** fashion": the outcome is recorded
  and surfaced loudly, and the transition is not stopped under the default strategy.
* **Every gate outcome carries a severity.** Who sets it depends on the outcome:

  | Outcome | Severity | Set by |
  |---|---|---|
  | Untrusted pack, hash mismatch against pin or consent, tamper detected at dispatch (ADR -4) | `BLOCKING` | dispatcher (fixed) |
  | Runner crash, timeout, missing interpreter, unconfinable host (ADR -2 baseline) | `RECOVERABLE` | dispatcher (fixed) |
  | A detected violation (the check ran and failed) | the gate's declared `severity` | gate |
  | Pass | — | — |

  Fail-open therefore survives **only for machinery faults**, and only as a recorded degraded
  outcome, never as a silent pass. Trust and tamper failures fail closed. This keeps C-003 for
  the grandfathered `spec-kitty-pre-review` code gate: its machinery faults map to
  `RECOVERABLE`, so `move-task` still completes, degraded and on the record.
* **The operator selects an error-handling strategy** in `.kittify` config, e.g.
  `block_above(threshold)` — outcomes at or above the threshold block the transition; below it,
  the CLI proceeds (degraded) and records the finding. This is the existing `audit` `fail_on`
  threshold pattern, generalised.
* **A default strategy ships: block at `BLOCKING` only.** `BLOCKING` stops a transition;
  `RECOVERABLE` proceeds degraded and is recorded loudly; `WARN` and `INFO` are recorded. Because
  trust failures are fixed at `BLOCKING`, security gates fail **closed** out of the box, and CI
  without operator trust seeding blocks loudly rather than silently no-ops.
* **Guardrail: no demotion of trust failures from the repository.** `.kittify/config.yaml` is
  committed, so a strategy read from repository configuration can make things stricter but can
  never make trust / tamper outcomes non-blocking. Those outcomes block regardless of the
  configured threshold.
* **Surface the effective strategy.** Every verdict records the effective strategy and where it
  came from, so "why did this pass?" always has an answer.
* **Canonical severity, minimal first.** `ERROR_SEVERITY` is defined once in the kernel (the
  layering-correct home, importable by doctrine) as a **minimal ladder for gates**, and the gate
  schema references it. Migrating the other four Severity enums onto it is follow-on debt
  (#3416 rescoped), not a precursor that blocks the gate work (#3417, #3418).

### Consequences

#### Positive

* One knob for strictness; the fail-closed/skip contradiction dissolves — the *operator's*
  threshold decides, uniformly, except for trust failures, which always block.
* The long-standing fail-open question has one answer that both keeps `move-task` unbreakable
  for machinery faults and closes the silent-skip hole for security.
* `RECOVERABLE` expresses "proceed degraded," which no boolean could.
* A minimal kernel ladder unblocks the gate work now and is the anchor the later consolidation
  converges on.

#### Negative

* Until the follow-on consolidation lands there are temporarily **six** Severity definitions;
  the kernel ladder must be the one every new consumer uses.
* A permissive operator strategy can still weaken *non-trust* gates (a violation declared
  `BLOCKING` can be demoted by the configured threshold); the effective-strategy record makes that
  visible rather than preventing it.

#### Neutral

* The strategy grammar (`block_above(threshold)` vs a per-severity action map) is a config-schema
  detail (open question).

### Resolved and open questions

1. *Open:* extend/rename `kernel.glossary_types.Severity`, or mint a new `ERROR_SEVERITY` next to
   it and migrate later? (Either way it lives in the kernel.)
2. *Open:* strategy grammar: single `block_above(threshold)`, or a per-severity action map
   (`{BLOCKING: block, RECOVERABLE: warn, WARN: warn, INFO: log}`)?
3. *Resolved (2026-09-27):* could-not-run severities are fixed by the dispatcher; a detected
   violation carries the gate's declared severity.
4. *Resolved (2026-09-27):* a minimal kernel ladder ships inside the gate work; full
   consolidation is follow-on.
