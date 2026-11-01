---
title: 'ADR: Sync Daemon Identity Contract and Cleanup Classification'
description: 'The `--spec-kitty-daemon-root` scope marker becomes the sole kill authority for sync daemons; `owner.json` is health reporting and interpreter identity only stale-version evidence.'
status: Superseded
doc_status: superseded
kind: ADR
date: '2026-06-30'
superseded_by: docs/adr/3.x/2026-09-06-1-convergence-retirement-and-client-repo-inversion.md
---

> **Superseded (2026-09-06)** by
> [`2026-09-06-1-convergence-retirement-and-client-repo-inversion.md`](2026-09-06-1-convergence-retirement-and-client-repo-inversion.md).
> The sync daemon this ADR governs was retired by the Convergence (#3881 / #3824); daemon identity,
> `owner.json`, and orphan reaping no longer exist. Retained as historical record.

## Context and Problem Statement

On 2026-06-30 a Spec Kitty machine accumulated **18 orphan sync daemons** on
ports `9401–9418`, spanning package versions `3.2.2`, `3.2.3`, and `3.2.4`.
Each CLI upgrade left the prior-version daemon running because the old reaper
skipped any candidate whose executable or interpreter identity differed from
the current process — a third identity condition that silently gated cleanup.
The result was unbounded orphan accumulation across upgrades.

The root cause had two distinct but interacting facets:

1. **Stale executable-identity skip gate.** The reaper excluded same-scope
   daemons whose `exe()` / `argv[0]` did not match the current process's
   interpreter. On macOS framework Python (Homebrew), the kernel rewrites both
   fields to the `Python.app` stub after re-exec, so legitimate same-scope
   daemons from the same interpreter became invisible to the reaper. Across
   upgrades the interpreter path itself changes, making every prior-version
   daemon permanently un-reapable regardless of scope identity.

2. **No authoritative daemon-local identity contract.** Kill decisions were
   partly delegated to the `owner.json` health payload — a reporting artefact
   written by the running daemon that reflects self-reported state, not a
   source of kill authority. This made the kill boundary non-deterministic:
   a daemon that failed to write `owner.json` could neither be identified nor
   cleaned up.

These two defects combined to produce the 18-orphan leak tracked in issues
[#2261](https://github.com/Priivacy-ai/spec-kitty/issues/2261) and
[#1071](https://github.com/Priivacy-ai/spec-kitty/issues/1071).

Mission `sync-daemon-orphan-cleanup-01KWC2A3` (`kitty-specs/sync-daemon-orphan-cleanup-01KWC2A3/`)
resolves both defects. Three decision moments were opened during planning to
settle the key design questions; each is cited below at the relevant decision.

## Decision Drivers

- Provably-stale same-scope daemons from prior versions must be auto-cleaned
  at startup (FR-007, FR-008).
- No process may be killed without a positive identity proof — killing by
  port alone is prohibited (C-004).
- `owner.json` is a health-reporting artefact, not kill authority (FR-003).
- Ambiguous candidates (cross-root, pre-marker, wedged) must be surfaced to
  the operator rather than silently killed (FR-002, FR-009).
- The cleanup model must be expressible as a concrete classification so the
  operator can see exactly which class each candidate falls into (FR-001,
  FR-004).
- The decision must be recorded as an ADR so it is discoverable (C-005,
  DIRECTIVE_003).

## Decision Outcome

The mission adopts a **daemon-root scope-marker-as-primary-kill-authority**
model with an explicit three-class `cleanup_class` verdict per candidate.

### D-1 — Daemon-root scope marker is the primary kill authority

A candidate sync daemon is eligible for automatic cleanup when, and only
when, **both** of the following hold:

1. Its command-line carries the `--spec-kitty-daemon-root=<path>` scope
   marker naming the **same** daemon state root as the current foreground
   process.
2. Its command-line has the production spawn shape: a `-c` flag whose script
   payload references `run_sync_daemon`.

Executable / interpreter identity (the old third condition) is **stale-version
evidence only and is NOT a kill gate** (FR-008). Same-scope daemons from a
prior installed version therefore flip from *skipped* to *reaped* — this is
the direct fix for the 18-orphan accumulation.

`owner.json` (`owner_present`) is recorded in the identity record for
diagnostics and reporting but is **never consulted for kill decisions**
(FR-003). `owner.json` is health-reporting data; the scope marker is kill
authority.

### D-2 — Explicit `daemon_family` tag required in the health payload

Every Spec Kitty sync daemon embeds an explicit `daemon_family: "sync"` field
in its `/api/health` response (added in WP04). The cleanup path asserts that
the family is `"sync"` before acting; a missing field (pre-WP04 daemon) is
defaulted to `"sync"` only when the port is in the sync range `[9400, 9450)`
and the production spawn shape is present. Dashboard-family listeners (port
range `[9237, 9337)`) are never touched by the sync cleanup path regardless
of any other identity signal (C-001, C-002, NFR-001/002/003).

### D-3 — Three-class `cleanup_class` model

Every scanned in-range listener is assigned exactly one of three verdicts
(`src/specify_cli/sync/classification.py`):

| `cleanup_class` | Meaning | Kill authority |
|---|---|---|
| `safe_auto` | Sync daemon, port in `[9400, 9450)`, self-reported PID/port match actual listener, singleton scope positively proven, not the recorded singleton. | Auto-cleaned at startup and by `auth doctor --reset`. |
| `operator_required` | Appears to be SK sync but is pre-marker, cross-root, missing PID, missing daemon-local identity, or wedged/unresponsive (see D-01 below). | Only cleaned by `auth doctor --reset --force` or interactive confirmation. |
| `never_touch` | Third-party listener, dashboard-family, cross-family, out-of-range, or otherwise unidentifiable as SK sync. | Never killed under any circumstances. |

A `skip_reason` accompanies every non-`safe_auto` record, making the
classification auditable via `auth doctor --json`.

### D-4 — Wedged listeners are `operator_required`, not `safe_auto`

*Decision moment `01KWC36NQBY670Q52B7C4SX2KH`*

An in-range listener that does **not** answer `/api/health` (wedged/hung)
but whose command-line carries a recognisable scope marker is classified
`operator_required/unresponsive` rather than `safe_auto`. A live
`/api/health` self-report is required for `safe_auto`; cmdline scope-proof
alone is insufficient. Wedged daemons are surfaced by `auth doctor` and
cleaned by `auth doctor --reset`, but are **never** auto-killed at startup.

This is the more conservative choice: it ensures the startup fast-path only
kills daemons that are provably responsive and correctly self-identifying,
not merely ones whose argv happened to carry the right marker.

### D-5 — `operator_required` daemons require explicit `--force` or interactive confirmation

*Decision moment `01KWC36QG4ZH8J79J9G1Y06FCD`*

`auth doctor --reset` auto-cleans `safe_auto` daemons without confirmation.
For `operator_required` daemons (cross-root, pre-marker, wedged/ambiguous),
an explicit interactive `y/N` prompt or the `--force` flag (for
non-interactive / `--json` callers) is required before any signal is sent.
This guards against the reaper-over-kill failure mode — killing a legitimately
separate daemon that shares a port range but belongs to a different `$HOME` or
state root.

### D-6 — #1071 same-`$HOME` singleton leak is live-reconfirmed by automated test

*Decision moment `01KWC36SFC7XVDVA9QQTN1NAK8`*

The same-`$HOME` singleton leak documented in issue #1071 (multiple
same-scope daemons accumulating under one `$HOME`/runtime root) is
live-reconfirmed via an automated regression test in the live-subprocess
harness (`tests/sync/test_issue_1071_singleton_reconfirmation.py`) before
the issue is closed. Manual reconfirmation plus documentation alone is
insufficient — the test provides durable, machine-checked evidence that the
new scope-marker authority resolves the leak.

## Consequences

### Positive

- **18-orphan leak fixed by construction.** The daemon-root scope marker as
  primary authority removes the executable-identity skip gate that caused
  stale daemons to accumulate across upgrades. Same-scope stale daemons from
  any prior version are now auto-reaped at startup (FR-007, FR-008).
- **Deterministic kill boundary.** The `cleanup_class` verdict is computed
  from stable cmdline data, not from self-reported health payloads. The
  boundary is the same on every host and does not depend on `owner.json`
  being present or accurate.
- **No silent kills.** `operator_required` candidates are always surfaced
  with `skip_reason` and a one-step remediation command (`auth doctor --reset
  --force`). Third-party listeners are never touched.
- **Auditable classification.** `auth doctor --json` exposes the full
  identity record and `cleanup_class` for every in-range candidate, enabling
  scripted and CI-driven inspection.
- **Durable regression proof.** `test_issue_1071_singleton_reconfirmation.py`
  proves no singleton leak remains under the new authority.

### Negative

- **Pre-marker daemons (spawned before this mission shipped) require operator
  action.** A daemon started before the `--spec-kitty-daemon-root=` marker
  was introduced has no scope marker in its cmdline, making positive
  attribution impossible. It is surfaced as `operator_required/pre_marker`
  and cleaned by `auth doctor --reset --force` — not automatically. This is a
  one-time migration cost for existing installations; daemons spawned after
  this mission lands always carry the marker.
- **Wedged daemons require the operator path.** A process that hangs before
  responding to `/api/health` cannot prove its own identity, so it is not
  auto-cleaned. The operator must run `auth doctor --reset` (or `--force`) to
  clear them.

### Neutral

- The `owner.json` (`owner_present`) field remains in the identity record for
  diagnostics and reporting; it does not affect the kill decision.
- The `daemon_family` field was added to the `/api/health` payload in WP04;
  absence of the field is tolerated (defaulted to `"sync"` for in-range
  spawn-shaped daemons) for backward compatibility with pre-WP04 daemons.

## Confirmation

This decision is confirmed when:

1. `auth doctor --json` reports `cleanup_class` and `skip_reason` for every
   in-range candidate.
2. Startup auto-clean removes all `safe_auto` same-scope stale-version
   daemons and does not spawn an additional process (AS-1 / FR-006/007/008).
3. `auth doctor --reset` sweeps `safe_auto`; `--force` additionally sweeps
   `operator_required`. `never_touch` candidates are untouched in all paths.
4. `tests/sync/test_issue_1071_singleton_reconfirmation.py` is green (no
   singleton leak under the same-`$HOME` scenario).
5. The boundary regression matrix (dashboard ↔ sync port isolation) remains
   clean under all four cleanup entrypoints.

## More Information

- **Mission spec / research / plan:**
  [`kitty-specs/sync-daemon-orphan-cleanup-01KWC2A3/`](../../../kitty-specs/sync-daemon-orphan-cleanup-01KWC2A3/)
- **Decision moments:**
  [`decisions/DM-01KWC36NQBY670Q52B7C4SX2KH.md`](../../../kitty-specs/sync-daemon-orphan-cleanup-01KWC2A3/decisions/DM-01KWC36NQBY670Q52B7C4SX2KH.md) (wedged-listener classification),
  [`decisions/DM-01KWC36QG4ZH8J79J9G1Y06FCD.md`](../../../kitty-specs/sync-daemon-orphan-cleanup-01KWC2A3/decisions/DM-01KWC36QG4ZH8J79J9G1Y06FCD.md) (`operator_required` confirmation flow),
  [`decisions/DM-01KWC36SFC7XVDVA9QQTN1NAK8.md`](../../../kitty-specs/sync-daemon-orphan-cleanup-01KWC2A3/decisions/DM-01KWC36SFC7XVDVA9QQTN1NAK8.md) (#1071 reconfirmation method)
- **Key implementation surfaces:**
  `src/specify_cli/sync/classification.py` (classifier + `DaemonIdentityRecord`),
  `src/specify_cli/sync/owner.py` (`reap_orphan_daemons`, `ReapResult`),
  `src/specify_cli/sync/orphan_sweep.py` (`enumerate_identity_records`, `reset_orphans`),
  `src/specify_cli/sync/daemon.py` (`DAEMON_SCOPE_ARG_PREFIX`, `_daemon_scope_root`)
- **Operator runbook:**
  [`docs/operations/sync-daemon-orphan-cleanup.md`](../../operations/sync-daemon-orphan-cleanup.md)
- **Regression test:** `tests/sync/test_issue_1071_singleton_reconfirmation.py`
- **Related issues:**
  [#2261](https://github.com/Priivacy-ai/spec-kitty/issues/2261) (primary: 18-orphan report),
  [#1071](https://github.com/Priivacy-ai/spec-kitty/issues/1071) (same-`$HOME` singleton leak)
