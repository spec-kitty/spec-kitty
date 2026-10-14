---
title: "Research note — #6164 Remove the frozen hosted / sync / drain surfaces from open-core"
mission: issue-6164-remove-hosted-from-core
issue: 6164
updated: 2026-10-13
status: grounding-complete / ESCALATION-PENDING
---

# Research note — issue #6164

Read-only code-grounding + two discovery squads (code-grounding, related-issues),
run before any edit. The branch `issue-6164-remove-hosted-from-core` is cut from
`origin/main` @ `fe26f8f8`. Governing authorities read in full: #6164, charter
ADR `2026-10-06-1` (+ amendment 2026-10-12), ADR `2026-09-26-3` (hosted-interaction
opt-in), ADR `2026-10-01-2` (Mission Status Read API), CLAUDE.md, `.kittify/charter/charter.md`,
procedure `semi-auto-delivery`.

## 0. Headline

**#6164 cannot be executed as a literal "delete the listed files + sever imports".**
Two independent squads converged on the same conclusion: the issue's REMOVE-list is
**factually wrong in 3 places**, **incomplete in ~6 load-bearing places** (the removal
will not compile without them), and names **2 shared modules whose deletion forces a
behavior change in a KEEP path**. These are escalation-class decisions (brief §2;
procedure `semi-auto-delivery` pause-and-escalate). They are listed in §5. The run is
PAUSED for an operator ruling before any deletion.

Baseline evidence: the four named gate files are GREEN before any change —
`tests/architectural/test_remote_contact_owner.py tests/architectural/test_pyproject_shape.py
tests/architectural/test_shared_package_boundary.py tests/cli/test_hosted_surface_visibility.py`
→ **61 passed in 266.58s (exit 0)**.

## 1. Invariants that must survive (with authority)

- **Produce-drain adapter seam `status/adapters.py` stays live** (ADR `2026-10-06-1`
  amendment 2026-10-12: "Producing an event never depends on whether a drain is enabled").
  The registry machinery (`register_*_fanout_handler`, `fire_*_fanout`, `reset_handlers`)
  survives as a publish/subscribe seam; the Zeitgeist handlers that currently occupy its
  three slots are removed, leaving the seam handler-less (every `fire_*` no-ops over an
  empty list). Drain is **always off** in open-core (ADR `2026-09-26-3` R-1: two gates,
  no env var, neither ships configured), so the fan-out is already observably inert — the
  seam surviving handler-less is behavior-neutral.
- **Local event / decisioning ledger (`status/`, `decisions/`) + the Mission Status Read
  API** stay green. The Read API is read-only and drain-independent (ADR `2026-10-01-2`
  D-6: "returns the same answer whether hosted drain is on or off"); it has no edge into
  the REMOVE-set beyond the shared `status/` reducer read models.
- **`tracker` stays visible for local providers (`beads`, `fp`)**; `research` (mission
  research command) and `issue-matrix` stay.
- **The two retirement/backfill migrations are KEPT** (consumers still need the cleanup):
  `upgrade/migrations/m_4_0_0_retired_hosted_target.py`,
  `m_4_0_0rc5_hosted_endpoint_session_backfill.py`.
- **`charter sync` / charter-pack freshness is untouched** — it is `charter.activation.sync`
  (entry points: `cli/commands/charter/{generate.py,__init__.py,_status_collectors.py}`).
  The issue's guessed path `cli/commands/charter/sync.py` does not exist. Name collision only.
- **No CHANGELOG entry** (#6164 constraint). This removes a never-shipped-configured surface.

## 2. Confirmed REMOVE-set (unambiguous)

Whole packages: `src/specify_cli/zeitgeist_client/` (20 files), `src/specify_cli/saas_client/`
(6 files), `src/specify_cli/auth/` (~35 files, whole tree).
Hidden hosted CLI command modules: `cli/commands/auth.py` + 7 `_auth_*.py`,
`cli/commands/{live_work.py,moments.py,routes.py,zeitgeist.py}`.
Hosted posture/core: `core/saas_sync_config.py` (defines `sync_active`, `is_saas_sync_enabled`,
`SAAS_SYNC_ENV_VAR`); `status/zeitgeist_bridge.py`.
Tracker SaaS provider: `tracker/saas_client.py`, `tracker/saas_readiness.py`,
`tracker/saas_service.py` (unnamed by the issue but backs the SaaS branches + `issue_search`),
`tracker/feature_flags.py` (back-compat shim re-exporting `saas_sync_config`).

Residue identifiers to delete-or-excise (acceptance checkbox): `SPEC_KITTY_ENABLE_SAAS_SYNC`,
`SPEC_KITTY_SYNC_*`, `SPEC_KITTY_SAAS_URL` / `[sync].server_url`, `sync_active()`,
`OWNED_SYNC_UNSUPPORTED` (the last survives only as dead comments in two KEEP files).

### #4204 delivery seam — already retired
GitHub #4204 was CLOSED `not_planned` on 2026-10-13 (today), in service of this removal.
`src/specify_cli/{delivery,event_journal,sync}` are already gone (Aug-2026 sync retirement);
no SQLite delivery-ledger file remains in `src/`. The live residue is in-memory only:
`live_work/coalesce.py` (burst coalescer) and `zeitgeist_client/receipts.py`
(`zeitgeist-receipts.sqlite3`, identity-only receipts) — both inside REMOVE packages.

## 3. REMOVE-set the issue OMITS but which is load-bearing (removal will not compile without)

- `src/specify_cli/live_work/` (14 files) — depends on `zeitgeist_client` + `hosted_posture`
  + `zeitgeist_bridge`; reached lazily + drain-gated from KEEP `retrospective/lifecycle_events.py`.
- `src/specify_cli/widen/` (8 files) — SaaS audience-widening; depends on `saas_client` +
  `hosted_posture`; reached from KEEP charter/plan interviews + `cli/commands/charter/_widen.py`.
- `src/specify_cli/events/runtime_moments.py` — runtime moment producer (drain); reached from
  `status/adapters.py` producer wiring.
- `src/specify_cli/readiness/auth.py` — auth leg of the otherwise-KEEP `readiness/` package.
- `src/specify_cli/tracker/origin.py` + `tracker/origin_consumer.py` — SaaS-first pending-origin
  binding wired into mission-creation via `tracker/__init__.py`.
- `src/specify_cli/cli/commands/charter/_widen.py` — charter-interview widen leg (imports
  `saas_client`+`widen`); the surrounding charter interview is KEEP.

## 4. KEEP-side surgery (sever cleanly, enabler-first per brownfield discipline)

- `status/adapters.py` — drop the `zeitgeist_bridge` import + `ensure_zeitgeist_moment_handlers`
  default wiring + the import-tail registration + the three `hosted_posture.drain_posture` gates
  + the runtime-moment-producer wiring; KEEP the registry/fire/reset machinery. Seam survives
  handler-less. (This is more than import-severing — it is the ADR KEEP guarantee made concrete.)
- `status/emit.py`, `coordination/status_transition.py` — consume `hosted_posture.ledger_posture`
  to gate the LOCAL `.kittify/derived/<mission>/` execution-state projection (ADR `2026-09-26-3`
  D-2/FR-010 — this is a LOCAL feature, NOT hosted). See §5-E: `ledger_posture`/`LedgerPosture`
  must be RELOCATED out of the deleted `hosted_posture.py`, not deleted.
- `core/env.py` — KEEP module; excise the sync/moment-handler residue (`SPEC_KITTY_SYNC_DISABLE`
  kill-switch, `MOMENT_HANDLER_DISABLE_ENV_VARS`, `sync_kill_switch_active`,
  `moment_handlers_disabled_reason`) once adapters no longer registers handlers; KEEP
  `is_truthy`/`is_interactive`/`pre_review_gate_skip_reason`.
- `cli/commands/__init__.py` — remove `_HOSTED_SURFACE_NAMES`, `_hosted_surface_entries`,
  `_set_hosted_surfaces_hidden`, `reveal_hosted_surfaces`, the five hosted registrars + their
  `_ALL_COMMAND_REGISTRARS`/`_COMMAND_REGISTRARS` entries, the `issue-search` registration line
  + map entry, the live-work hook fast-path; and the `reveal_hosted_surfaces(app, sys.argv)` call
  in `src/specify_cli/__init__.py`. KEEP `tracker` + `research`.
- `readiness/coordinator.py`, `cli/commands/mission_type.py`, `cli/commands/tracker.py` — sever
  `is_saas_sync_enabled`/`saas_sync_disabled_message` + the SaaS tracker branches.
- `tracker/service.py`, `tracker/config.py`, `tracker/__init__.py` — remove SaaS branches,
  `SAAS_PROVIDERS`, the `feature_flags` re-exports, the origin-consumer registration; keep the
  local (beads/fp) dispatch via `tracker/factory.py`.
- `tracker/store.py` — **nothing to remove** (no saas/egress imports). Issue over-specified.
- `decisions/emit.py` — only docstring refs + the KEEP seam call `fire_lifecycle_saas_fanout`
  (stays, no-ops). No surgery beyond docstrings.
- `cli/commands/decision.py` — sever the lazy `from specify_cli.saas_client import SaasClient`
  hosted branch of `decision widen`; keep the local decision-ledger core.

## 5. ESCALATIONS — operator decisions required BEFORE deletion

Both squads independently flagged these; all five verified firsthand by this session.

- **§5-A `tracker/egress_verdict.py` — SHARED; deleting removes a fail-closed consent gate on a
  KEEP path (behavior change).** Its `EgressDestination.LOCAL_SUBPROCESS` branch is the sole
  consent gate protecting the KEPT beads/fp local tracker sync (spawns the global `bd`/`fp`
  executable with issue data). Used by KEEP `tracker/local_service.py:37,223,246,264`. Polarity:
  at LOCAL_SUBPROCESS, absent key ⇒ REFUSE (`LocalTrackerEgressRefusedError`). Only the
  `HOSTED_SERVICE` branch is hosted. **Decision:** (a, recommended) KEEP the file, drop only the
  `HOSTED_SERVICE` branch, keep the three local guards — non-breaking, honors "keep tracker local
  providers"; (b) delete it + the guards and accept losing the local consent gate (a security
  behavior change). The issue text implies (b) but conflates the local gate with hosted egress.
- **§5-B `core/secret_redaction.py` — issue premise WRONG; it is a KEEP surface, not hosted-egress.**
  It is a general fail-closed env-var value-redaction allowlist (`redact()`), imported by the
  env-file doctor `cli/commands/_env_file_doctor.py:38` (KEEP operator surface). Deleting it
  breaks the doctor or strips a fail-closed property (would leak secret env values into `doctor`
  output). **Recommendation: KEEP the file; only excise the hosted var *names* from its
  `_PRINTABLE_VARS` allowlist.**
- **§5-C KEPT migrations functionally depend on the `auth/` package (not just an import).**
  `m_4_0_0rc5` reads a stored encrypted auth session via
  `auth.secure_storage.file_fallback.peek_stored_session` (its whole job, ADR `2026-09-26-3`
  D-6/FR-016) + `auth.config.is_retired_first_party_url` + `auth.server_target.resolve_server_target_or_none`;
  `m_4_0_0_retired_hosted_target` imports `auth.config` (`DEFAULT_HOSTED_SAAS_URL`,
  `is_retired_first_party_url`). Making the import lazy does NOT help — the package is gone.
  **Decision:** how much of the session-peek reader + host-match helpers to vendor/localize into
  the migrations (or a tiny kept helper) to keep FR-016 honest for already-upgraded machines,
  vs. accepting that with `auth/` gone there are no new sessions so the backfill becomes a
  best-effort no-op (inline only `is_retired_first_party_url`, which is a pure host match).
- **§5-D scope expansion (the §3 omitted packages).** The removal will not compile without also
  removing `live_work/`, `widen/`, `events/runtime_moments.py`, `readiness/auth.py`,
  `tracker/{saas_service,origin,origin_consumer,feature_flags}.py`, `cli/commands/charter/_widen.py`.
  They are purely hosted. **Recommendation: include them** (they are consequences of the named
  removals, not new scope), with operator acknowledgment per brief "do not expand scope".
- **§5-E `hosted_posture.ledger_posture`/`LedgerPosture` relocation (required severing, not a
  judgment call).** Deleting `core/hosted_posture.py` wholesale breaks the LOCAL derived-projection
  feature. Plan: relocate `ledger_posture` + `LedgerPosture` + their repo-bool helpers to a kept
  module (e.g. `core/ledger_posture.py`), re-point `status/emit.py` + `coordination/status_transition.py`.
  Behavior-neutral. Flagged for awareness; proceeding as planned unless told otherwise.

## 6. Gates — what changes (named-file discipline, NO_FULL_HEAVY_SUITES_IN_MISSION)

- `test_remote_contact_owner.py` — scopes only remote-contacting **git** argv outside
  `src/kernel/git/`; empty allowlist; HTTP relay contact is not in this census. Removing hosted
  code only reduces git-contact sites → **stays green, no edit**. (Baseline green.)
- `test_shared_package_boundary.py` — enforces events/tracker external-import boundary only; no
  auth/saas/zeitgeist refs → **unaffected, no edit**. (Baseline green.)
- `test_pyproject_shape.py` — removed packages are subpackages of `specify_cli`, not top-level
  wheel trees → **no edit**. (Baseline green.)
- `tests/cli/test_hosted_surface_visibility.py` — directly asserts `_HOSTED_SURFACE_NAMES`
  hidden/reveal behavior → **obsolete; delete or invert** to assert those names no longer register.
- `tests/architectural/test_hosted_drain_gate.py` — proves hosted edges sit behind the drain gate;
  with hosted edges gone it would fail to import the removed modules → **delete / empty its edge list**.
- `tests/architectural/test_no_retired_subsystems.py` — has a POSITIVE test asserting
  `from specify_cli import saas_client` is STILL allowed → **flip it**; add the removed packages to
  `_RETIRED_PATHS` + the pyproject TID251 ban list.
- `tests/docs/test_check_cli_reference_freshness.py` — baseline is 252 **visible** commands; the
  hosted surfaces are hidden (not visible) so removing them does not move the visible count →
  expected to stay green; regenerate `docs/api/cli-commands.md` and confirm.

## 7. Packaging / deps

- Wheel `packages` list unchanged (subpackages of `specify_cli`). Clean the coverage/ruff/mypy
  exclude lists that name removed files, and the pyproject TID251 ban list (add new retired modules).
- Possibly-orphaned deps to verify before dropping: `cryptography` (auth secure-storage), `mcp`
  (zeitgeist stdio adapter). KEEP `httpx`/`requests` (charter pack sources).

## 8. Relocation (PR B) — BLOCKED

PR B relocates the REMOVE-set + its tests into `spec-kitty/event-router`. Attaching that repo via
the `add_repo` tool is **denied by this session's auto-mode classifier** (reason "Permission Grant");
retried once. This is a background run with no live approval path. event-router's layout could not be
inspected, so the landing shape for the moved code is undetermined. **Operator action: grant a
permission rule for `mcp__claude-code-remote__add_repo` (or attach event-router to the session).**
The core REMOVE-set (PR A's file set) is defined by #6164 and is independent of event-router's layout,
so PR A's engineering can proceed once the §5 escalations are ruled on.

## 9. Related issues / discovery verdict

- `Closes`: #6164. `Refs`: #4204 (closed `not_planned` today, effectively closed-by this removal).
- #645 (charter extraction, GA-gating) — does NOT touch any REMOVE-set file; no conflict.
- #4971, #2875 (hosted/sync) — already closed; no open sibling blocks or conflicts with this work.
- `domain:hosted` label = exactly the three client packages this removes. No related surfaces beyond
  those mapped in §2–§4; stated explicitly (not an omission).
