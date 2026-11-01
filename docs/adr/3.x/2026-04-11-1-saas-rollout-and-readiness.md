---
title: SaaS Rollout Gate and Hosted Readiness Split
description: 'Separates hosted rollout visibility from per-prerequisite readiness diagnostics into one saas package, leaving the old flag modules as thin re-export shims.'
status: Superseded
date: '2026-04-11'
superseded_by: docs/adr/3.x/2026-09-06-1-convergence-retirement-and-client-repo-inversion.md
doc_status: superseded
kind: ADR
updated: '2026-04-11T00:00:00Z'
---

> **Superseded (2026-09-06)** by
> [`2026-09-06-1-convergence-retirement-and-client-repo-inversion.md`](2026-09-06-1-convergence-retirement-and-client-repo-inversion.md).
> The `specify_cli.saas` rollout/readiness package this ADR governs was deleted by the Convergence
> (#3881 / #3824); residual readiness re-homed to `tracker/saas_readiness.py`, the SaaS-sync flag to
> `core/saas_sync_config.py`. Retained as historical record.

## Context and Problem Statement

Spec Kitty uses `SPEC_KITTY_ENABLE_SAAS_SYNC=1` as the explicit opt-in gate
controlling whether the hosted tracker/sync surface is visible at all.  On
customer machines where the variable is absent the CLI fails closed — no hosted
commands appear, no SaaS network traffic occurs.  On internally designated test
machines the variable is set and the full hosted surface becomes available.

Before this mission the rollout gate had two structural problems:

1. **Duplicated gate logic.** `is_saas_sync_enabled()` and
   `saas_sync_disabled_message()` were duplicated verbatim in both
   `src/specify_cli/tracker/feature_flags.py` and
   `src/specify_cli/sync/feature_flags.py`.  Neither module was the clear owner;
   every new consumer had to choose one arbitrarily.

2. **Single generic gate error inside enabled mode.** Once the env var was set
   the CLI hid the tracker command group correctly at registration time, but
   inside that enabled surface each command performed ad hoc preflight checks and
   emitted one generic "not enabled" error regardless of what prerequisite was
   actually missing.  NFR-002 ("100% of readiness failures must name the missing
   prerequisite") was unachievable under the old model.

There was also no structured policy for background-daemon auto-start.
`ensure_sync_daemon_running()` would unconditionally start the daemon from any
call site, including help and local-only dashboard commands that should never
trigger hosted network activity.

## Decision Drivers

* **NFR-001** — In the absence of `SPEC_KITTY_ENABLE_SAAS_SYNC`, 100% of hosted
  tracker visibility and execution paths must remain hidden or blocked.
* **NFR-002** — In enabled mode, 100% of readiness failures must name the
  missing prerequisite and the next corrective action.
* **NFR-003** — Help and local-only commands must not start hosted background
  networking even on enabled internal machines.
* **C-001** — The stealth rollout posture (hidden by default) must be preserved;
  the env var is not removed in this mission.
* **C-002** — `spec-kitty-tracker` is a pinned external dependency and must not
  carry rollout logic.
* Backwards compatibility across existing call sites without a flag-day
  migration.

## Considered Options

* **Option 1:** Per-command flag in each tracker command instead of a shared
  evaluator.
* **Option 2:** Single unified gate that mixes visibility control and readiness
  evaluation.
* **Option 3:** Add rollout logic to `spec-kitty-tracker==0.3.0`.
* **Option 4:** Environment variable for background-daemon policy.
* **Option 5:** Project-level daemon config in this mission.
* **Option 6 (chosen):** New shared `saas/` package for rollout + readiness;
  intent-gated daemon; user-level config key for daemon policy.

## Decision Outcome

**Chosen option: Option 6**, because it separates the two concerns (visibility
and per-prerequisite diagnostics) into cohesive abstractions without a flag-day
migration, while preserving the existing rollout posture for all customer machines.

### Core Decisions

**Decision 1 — Consolidate rollout gating into `src/specify_cli/saas/`.**

A new top-level package `src/specify_cli/saas/` (`rollout.py`, `readiness.py`)
is the single owner of the `SPEC_KITTY_ENABLE_SAAS_SYNC` check and of the
hosted-readiness evaluator.  The existing `tracker/feature_flags.py` and
`sync/feature_flags.py` become thin re-export shims that delegate to
`specify_cli.saas.rollout` — no call-site renaming is required in this mission.

**Decision 2 — Introduce `HostedReadiness` evaluator with a 6-state enum.**

`src/specify_cli/saas/readiness.py` exposes `ReadinessState` (a closed `Enum`
with six members) and `evaluate_readiness()`, which checks prerequisites in a
defined order and returns a frozen `ReadinessResult` whose `message` and
`next_action` fields describe the first failing prerequisite.  The check order is:

1. Rollout gate (`ROLLOUT_DISABLED`)
2. Auth token (`MISSING_AUTH`)
3. Host URL via `specify_cli.auth.config.get_saas_base_url()` (`MISSING_HOST_CONFIG`)
4. Network reachability — only when `probe_reachability=True` (`HOST_UNREACHABLE`)
5. Tracker binding — only when `require_mission_binding=True` (`MISSING_MISSION_BINDING`)
6. All checks passed (`READY`)

The `MISSING_HOST_CONFIG` check reads `SPEC_KITTY_SAAS_URL` through
`specify_cli.auth.config.get_saas_base_url()` — the authoritative D-5 source.
`SyncConfig.get_server_url()` is **not** used here.

**Decision 3 — Background-daemon policy is a user-level config key.**

`BackgroundDaemonPolicy` (`AUTO` | `MANUAL`, default `AUTO`) is added to the
existing `SyncConfig` class in `src/specify_cli/sync/config.py`, persisted as
`[sync] background_daemon` in `~/.spec-kitty/config.toml`.  Project-level
override is explicitly deferred (see Consequences).

**Decision 4 — Daemon startup is intent-gated via `DaemonIntent`.**

`DaemonIntent` (`LOCAL_ONLY` | `REMOTE_REQUIRED`) is a new enum in
`src/specify_cli/sync/daemon.py` required as a mandatory keyword-only argument
on `ensure_sync_daemon_running()`.  The function returns a typed
`DaemonStartOutcome` and refuses to start the daemon when:

```
intent != DaemonIntent.REMOTE_REQUIRED
  OR
policy == BackgroundDaemonPolicy.MANUAL
```

**Decision 5 — `spec-kitty-tracker==0.3.0` remains ungated.**

No rollout logic is added to the tracker package.  Tracker is a pinned external
dependency and is not the owner of rollout posture (C-002).  The CLI and SaaS
own the gate; tracker is a downstream consumer.

**Decision 6 — The `SPEC_KITTY_ENABLE_SAAS_SYNC` gate is not removed.**

The stealth rollout posture is preserved unchanged.  The env var continues to
control whether the hosted surface is visible.  Removing it is explicitly out of
scope for this mission.

## Consequences

### Positive

* `HostedReadiness` is the single fan-in point for any new hosted prerequisite —
  future missions add `ReadinessState` members rather than sprinkling ad hoc
  checks across commands.
* Operators gain a new config knob (`[sync].background_daemon`) that controls
  auto-start behavior without touching rollout gating.
* The three daemon call sites (`src/specify_cli/dashboard/server.py`,
  `src/specify_cli/dashboard/handlers/api.py`, `src/specify_cli/sync/events.py`)
  now declare intent explicitly, and a CI grep guard in
  `tests/sync/test_daemon_intent_gate.py` prevents silent proliferation.
* NFR-002 is achievable: every non-`READY` state has a frozen message and a
  `next_action` that names the specific missing prerequisite.

### Negative

* BC shims at `src/specify_cli/tracker/feature_flags.py` and
  `src/specify_cli/sync/feature_flags.py` remain; collapsing them is a future
  cleanup mission once every call site migrates to `specify_cli.saas.rollout`.
* `SyncConfig` is a plain class (not a dataclass); the new
  `get_background_daemon()` / `set_background_daemon()` methods follow the
  existing getter/setter pattern rather than a simpler field declaration.

### Neutral

* Project-level override of daemon policy is explicitly deferred.  The migration
  path is a `resolve_background_daemon_policy(repo_root)` helper that layers
  project config over user config; the new enum and intent gate stay unchanged
  when that helper is introduced.
* Subdividing `MISSING_AUTH` into `NO_TOKEN | EXPIRED_TOKEN` is deferred — the
  current auth lookup does not distinguish between the two states.  Adding a
  member is additive and requires no structural change to the evaluator.
* The rollout env-var itself is **not removed** — stealth rollout remains in
  force during the current internal-testing window.

### Confirmation

This decision is validated when:

1. A machine without `SPEC_KITTY_ENABLE_SAAS_SYNC` shows no hosted tracker
   surface and `is_saas_sync_enabled()` returns `False` from a single canonical
   location (`specify_cli.saas.rollout`).
2. With `SPEC_KITTY_ENABLE_SAAS_SYNC=1`, readiness failures each name their
   specific missing prerequisite rather than a generic gate message.
3. Local-only and help commands do not start the background daemon.
4. `[sync] background_daemon = manual` in `~/.spec-kitty/config.toml` suppresses
   daemon auto-start even when `REMOTE_REQUIRED` intent is declared.
5. `tests/sync/test_daemon_intent_gate.py` fails if any new call site omits the
   `intent=` argument.

## Pros and Cons of the Options

### Option 1: Per-command flag in each tracker command

Each hosted tracker command carries its own readiness-check logic and calls the
gate function directly.

**Pros:**

* Localized — each command is self-contained.

**Cons:**

* Duplicates the env-var read at every command.
* No per-prerequisite messaging; NFR-002 is still unachievable.
* Any new prerequisite requires touching every command.

### Option 2: Single unified gate mixing visibility and readiness

One gate function controls both whether commands are visible and whether they
have all required prerequisites.

**Pros:**

* Fewer abstractions.

**Cons:**

* Conflates stealth rollout (product policy) with operational diagnostics
  (runtime state).  NFR-002 is unachievable because the gate cannot name
  which prerequisite is missing without knowing the caller's context.

### Option 3: Add rollout logic to `spec-kitty-tracker==0.3.0`

Push the gate into the tracker package itself.

**Pros:**

* Gate travels with the functionality.

**Cons:**

* Explicitly forbidden by C-002.  Tracker is a pinned external dependency and
  is not the owner of rollout posture.  The CLI and SaaS own that boundary.

### Option 4: Environment variable for background-daemon policy

Use a second env var (e.g., `SPEC_KITTY_DAEMON_MODE`) to control daemon startup.

**Pros:**

* Easy to set in CI pipelines.

**Cons:**

* Overloads the env-var surface and risks confusing the rollout story.
  `SPEC_KITTY_ENABLE_SAAS_SYNC` already carries rollout intent; a sibling var
  for daemon policy creates ambiguity about which var does what.

### Option 5: Project-level daemon config in this mission

Add `[sync] background_daemon` to `.kittify/config.yaml` alongside user-level
config.

**Pros:**

* Per-repo CI policy without touching the user config file.

**Cons:**

* Scope creep for this mission.  The layering adds complexity before any use
  case requires it.  Documented as the future migration path instead.

## More Information

**Mission artifacts governing this ADR:**

* `kitty-specs/082-stealth-gated-saas-sync-hardening/spec.md`
* `kitty-specs/082-stealth-gated-saas-sync-hardening/plan.md`
* `kitty-specs/082-stealth-gated-saas-sync-hardening/research.md` (R-001 through R-006)
* `kitty-specs/082-stealth-gated-saas-sync-hardening/contracts/saas_rollout.md`
* `kitty-specs/082-stealth-gated-saas-sync-hardening/contracts/hosted_readiness.md`
* `kitty-specs/082-stealth-gated-saas-sync-hardening/contracts/background_daemon_policy.md`

**Implementation seams this ADR governs:**

* `src/specify_cli/saas/rollout.py` (WP01 — canonical rollout gate)
* `src/specify_cli/saas/readiness.py` (WP02 — hosted-readiness evaluator)
* `src/specify_cli/sync/config.py` (WP03 — `BackgroundDaemonPolicy` + `get_background_daemon()`)
* `src/specify_cli/sync/daemon.py` (WP04 — `DaemonIntent`, `DaemonStartOutcome`, intent-gated `ensure_sync_daemon_running()`)
* `src/specify_cli/cli/commands/tracker.py` (WP05 — tracker CLI uses `evaluate_readiness()`)
* `src/specify_cli/tracker/feature_flags.py` (BC shim — re-exports `specify_cli.saas.rollout`)
* `src/specify_cli/sync/feature_flags.py` (BC shim — re-exports `specify_cli.saas.rollout`)

**Prior ADRs in the same rollout-gate lineage:**

* `2026-02-27-1-cli-tracker-surface-gated-by-saas-sync-flag.md` — original decision to gate tracker via `SPEC_KITTY_ENABLE_SAAS_SYNC`
* `2026-02-27-2-host-owned-tracker-persistence-boundary.md`
* `2026-04-19-1-cli-auth-uses-encrypted-file-only-session-storage.md`
