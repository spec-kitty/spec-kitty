---
title: Sync Daemon Orphan Cleanup — Operator Runbook
description: How to inspect, classify, and clean up stale Spec Kitty sync daemons.
doc_status: deprecated
updated: '2026-08-31'
related:
- docs/adr/3.x/2026-06-30-1-sync-daemon-identity-and-cleanup-classification.md
---

# Sync Daemon Orphan Cleanup — Operator Runbook

> **Removed in 3.2.6; kept as historical record.** The sync daemon and its
> cleanup commands described here are gone. This page is scheduled for deletion
> in 3.2.7.

This runbook covers the two-command operator path for diagnosing and cleaning
up stale Spec Kitty sync daemons that accumulate after upgrades. It covers
what each cleanup class means, what is never touched, the JSON fields for
scripting, and the hosted-auth/sync test environment gate.

**Architectural background:**
[`docs/adr/3.x/2026-06-30-1-sync-daemon-identity-and-cleanup-classification.md`](../adr/3.x/2026-06-30-1-sync-daemon-identity-and-cleanup-classification.md)

---

## Why orphans accumulate

Normal `spec-kitty` upgrades leave the prior sync daemon running. Earlier
reaper implementations skipped any candidate whose interpreter identity
differed from the current process — so every version upgrade made the prior
daemon permanently un-reapable, and orphans would accumulate across
upgrades on a single machine.

The reaper now uses the **daemon-root scope marker**
(`--spec-kitty-daemon-root=<path>` embedded in the daemon's command line) as
the primary kill authority. Executable or interpreter identity is stale-version
*evidence only*, not a skip gate. Same-scope daemons from any prior version are
auto-cleaned at startup.

---

## The two-command operator path

You have accumulated old sync daemons — for example, after several upgrades.

```bash
# Step 1 — Inspect (read-only, never kills anything)
spec-kitty auth doctor

# Output: one row per in-range listener
#   PID · PORT · VERSION · CLASS (safe_auto | operator_required) · REASON
```

```bash
# Step 2 — Clean the safe ones (same-scope stale daemons)
spec-kitty auth doctor --reset

# Output summary:
#   swept: N  (safe_auto daemons that were cleaned)
#   skipped: M  (operator_required — see step 3)
#   failed: K  (could not kill — permissions or race)
```

```bash
# Step 3 — Only when step 2 reported skipped operator_required daemons
#           that you recognise as yours (e.g. a stale cross-checkout daemon)
spec-kitty auth doctor --reset --force
```

That is the complete path from "many orphans" to "clean." No other commands or
manual `kill` invocations are needed for the standard upgrade case.

---

## Cleanup classes

Every in-range listener is assigned exactly one `cleanup_class` verdict.

### `safe_auto`

The daemon is:
- a Spec Kitty sync daemon (port in `[9400, 9450)`, live `/api/health` response)
- its self-reported PID/port match the actual listener
- its singleton scope is positively proven (scope marker present and matches
  this host's daemon state root)
- it is **not** the currently-recorded singleton

`safe_auto` daemons are cleaned automatically at startup (no user action
required) and also by `auth doctor --reset`.

### `operator_required`

The listener looks like a Spec Kitty sync daemon but one or more conditions
cannot be positively confirmed. Common sub-reasons:

| `skip_reason` | Meaning |
|---|---|
| `pre_marker` | No `--spec-kitty-daemon-root=` marker in command line. Daemon was spawned before the scope-marker was introduced. |
| `cross_root` | Scope marker is present but names a different daemon state root (different `$HOME` or container). |
| `unresponsive` | Listener did not answer `/api/health` (wedged/hung). |
| `pid_port_mismatch` | Health self-report PID/port differ from the actual OS listener. |
| `missing_pid` | Could not determine the PID of the process holding the port. |

`operator_required` daemons are **never** auto-killed at startup. They are
surfaced by `auth doctor` (with `skip_reason`) and cleaned only by
`auth doctor --reset --force` or interactive confirmation.

### `never_touch`

The process is not identifiable as a Spec Kitty sync daemon. This includes:

- **Third-party listeners** — any process on a port in `[9400, 9450)` that
  does not identify as Spec Kitty sync.
- **Out-of-range processes** — a Spec Kitty-looking process listening outside
  the reserved range.

`never_touch` candidates are excluded from all cleanup paths and are never
reported in the `auth doctor` orphan table. They are invisible to the operator
intentionally.

---

## What is never touched

The following are **always** excluded from sync cleanup regardless of any
other identity signal:

- **Third-party applications** squatting on a port in `[9400, 9450)`. A
  foreign health response causes immediate `never_touch` classification.
- **Out-of-range processes** (outside `[9400, 9450)`).
- **The currently-recorded singleton** — the live daemon is never a cleanup
  candidate, even if a cleanup pass runs while it is active.

---

## JSON output for scripting and CI

```bash
# Inspect — full identity records per orphan
spec-kitty auth doctor --json | jq '.orphans[] | {port, pid, cleanup_class, skip_reason}'

# Reset — structured result
spec-kitty auth doctor --reset --json | jq '.reset_result'
# → { "swept": [...], "skipped": [...], "failed": [...] }
```

### `reset_result` fields

| Field | Type | Contents |
|---|---|---|
| `swept` | array | One entry per daemon cleaned. Fields: `pid`, `port`, `package_version`, `protocol_version`, `cleanup_path` (`http_shutdown` \| `terminate` \| `kill`), `reason`. |
| `skipped` | array | One entry per `operator_required` daemon not cleaned (because `--force` was absent). Fields: `pid`, `port`, `cleanup_class`, `skip_reason`. |
| `failed` | array | One entry per daemon that survived every escalation attempt (permission or race). Fields: `pid`, `port`, `failure_reason`. |

`swept[]`, `skipped[]`, and `failed[]` account for every candidate: no entry
is silently dropped from the result.

---

## Hosted auth / sync test environment gate

On this development machine, hosted auth/sync test commands require the
`SPEC_KITTY_ENABLE_SAAS_SYNC=1` environment variable:

```bash
SPEC_KITTY_ENABLE_SAAS_SYNC=1 spec-kitty auth doctor
SPEC_KITTY_ENABLE_SAAS_SYNC=1 spec-kitty auth doctor --reset
```

Without this variable, the hosted auth/sync paths are gated off and the
commands operate in local-only mode. CI sets this variable explicitly for
jobs that require hosted connectivity.

---

## Developer / test quickstart

The venv is assumed warm. The live-subprocess test suite uses real loopback
ports and real PIDs; run it serially:

```bash
# Classification + reset
PWHEADLESS=1 .venv/bin/pytest tests/sync/test_daemon_orphan_classification.py -n0 -q

# Boundary regression matrix
PWHEADLESS=1 .venv/bin/pytest tests/sync/test_daemon_cleanup_boundary.py -n0 -q

# #1071 singleton reconfirmation
PWHEADLESS=1 .venv/bin/pytest tests/sync/test_issue_1071_singleton_reconfirmation.py -n0 -q
```

Lint and type gates:

```bash
.venv/bin/ruff check src/specify_cli/sync tests/sync
.venv/bin/mypy --strict src/specify_cli/sync
```

---

## #1071 regression coverage

Issue [#1071](https://github.com/Priivacy-ai/spec-kitty/issues/1071) tracked a
same-`$HOME` singleton leak — multiple same-scope sync daemons accumulating
under one `$HOME`/runtime root. That leak is covered by the automated
regression test `tests/sync/test_issue_1071_singleton_reconfirmation.py`,
which spawns multiple same-scope sync daemons under a single shared
`$HOME`/daemon-root, invokes the canonical reaper (`reap_orphan_daemons`),
and asserts that stale same-scope daemons are reaped and exactly **one**
singleton survives — no leak.

If a residual same-`$HOME` leak is found in the future, open a new scoped
issue and add a targeted test case to the reconfirmation suite rather than
reworking this test.
