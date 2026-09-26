# Mission Specification: Opt-in hosted drain and ledger flags

**Mission Branch**: `claude/spec-kitty-mission-impl-8u6zmc` (target = planning base)
**Created**: 2026-09-26
**Status**: Draft
**Input**: Issue #4971 — "Config-based, opt-in SaaS/Zeitgeist interaction: two flags (ledger + drain-to-server) and stop shipping a hard-coded live endpoint". Brief-intake mode: the issue is a comprehensive brief; the operator answered the four open architecture questions on 2026-09-26 (see *Operator decisions*).

## Intent Summary

**Primary actor:** an operator (developer) running Spec Kitty missions locally while Team Kitty
server-side development is frozen.
**Trigger:** any lane transition, lifecycle beat, runtime step, decision, or hosted command.
**Desired outcome:** nothing leaves the machine unless the operator has explicitly opted in, twice
(repository *and* personal activation); the local execution-state record stays fully produced and
queryable for the upcoming local dashboard; the shipped build never targets a live hosted server on
its own.
**Invariant:** the committed lane ledger (`status.events.jsonl`) and decision ledger (`decisions/`)
are a non-optional floor — no flag in this mission can stop them being written or committed
("Git carries DONE"; #4311).

## Operator decisions (2026-09-26, architecture checkpoint)

| # | Question | Decision |
|---|----------|----------|
| D-1 | Where does the drain flag live? | **Both**: the repository opts in (`.kittify/config.yaml`) **and** the developer activates it globally (user-global Spec Kitty config). Drain is effective only when both are on; either off or absent ⇒ off. |
| D-2 | What does the ledger flag gate? | **Option (c)**: automatic refresh of the gitignored, derived local execution-state projection after each lane transition. It never gates the lane ledger, its commit, the committed status snapshot, the decision ledger, the runtime run journal, or invocation records. |
| D-3 | Behaviour with no configured hosted endpoint | Explicit hosted commands stop with setup guidance naming the environment variable and the config key; automatic paths stay silent and send nothing. |
| D-4 | Rename the retired-vocabulary endpoint key `[sync].server_url`? | **No** — keep it; the rename is a separate follow-up. |

## Domain Language

| Canonical term | Meaning | Avoid |
|---|---|---|
| **Drain** | Any live, outbound hosted interaction that happens *automatically* as a side-effect of local work: Zeitgeist moments (status, lifecycle, runtime, decision live-frame), presence/focus frames, capability resolution/minting for those, and live stream subscriptions. The "NOW" path. | "sync", "SaaS sync", "fan-out enabled" |
| **Lane ledger** | `status.events.jsonl` — sole authority for WP lane state, always written and committed. | "ledger" unqualified |
| **Decision ledger** | `decisions/` (index, `DM-<ulid>.md`) + `decisions.events.jsonl` — permanent decision record (#4311). | |
| **Execution-state projection** (the "ledger" flag's subject) | Derived, gitignored, always-rebuildable local snapshot of a mission's execution state under `.kittify/derived/<mission>/`; the local dashboard's query source. Never authoritative. | "the ledger" |
| **Hosted endpoint** | The Team Kitty base address the CLI authenticates against. Config-supplied only. | "packaged default", "sync server" |

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Frozen-server default: nothing leaves the machine (Priority: P1)

A developer installs Spec Kitty (or upgrades) with no hosted configuration and runs a whole mission
— specify, implement, move tasks through all lanes, record decisions, `spec-kitty next`.

**Why this priority**: it is the operator directive driving the issue: server work is frozen, the
build must not talk to the live server, and local work must be unaffected.

**Independent Test**: run a full lane walk and a decision round-trip with networking instrumented;
assert zero outbound hosted requests, exit 0, and an unchanged lane/decision ledger.

**Acceptance Scenarios**:
1. **Given** no drain configuration anywhere, **When** a WP is moved through every lane, **Then** no
   moment, presence, focus or capability request is attempted, every command exits 0, and the lane
   ledger is written and committed exactly as before.
2. **Given** the developer was previously logged in and holds a cached relay credential, **When**
   drain is off, **Then** the cached credential is not used and nothing is sent.
3. **Given** a repository that ships a hosted auth file and turns drain on in its committed config,
   **When** a developer who has not activated drain globally clones it and transitions a WP,
   **Then** nothing is sent.
4. **Given** drain off, **When** the developer runs the live watch/status stream command, **Then**
   it reports that drain is off (naming how to enable it) and opens no subscription.

### User Story 2 — Deliberate opt-in keeps real-time working (Priority: P1)

A developer on a team that still uses the relay enables drain in both scopes and configures the
hosted endpoint.

**Why this priority**: opt-in must be a working path, not a dead switch; drain-off must not
silently defeat the real-time guarantee when drain is on (#4311 coupling).

**Independent Test**: with both scopes on and a stub relay, a lane transition produces exactly one
moment offer — same as today's behaviour.

**Acceptance Scenarios**:
1. **Given** drain on in the repository config **and** in the developer's global config, **When** a
   WP transitions, **Then** the moment is offered exactly as before this mission.
2. **Given** drain on in only one of the two scopes, **When** a WP transitions, **Then** nothing is
   sent and the drain status report names the scope that is off.
3. **Given** drain on, **When** the developer asks for drain status, **Then** the output shows the
   effective state and which file decided each scope.

### User Story 3 — Local execution-state projection for the local dashboard (Priority: P2)

A developer with drain off wants an always-fresh local execution-state snapshot for the upcoming
local dashboard.

**Why this priority**: the ledger flag's purpose; needed before the local dashboard ships, but the
no-network posture (US1) matters more.

**Independent Test**: toggle the ledger flag over a full lane walk; compare the projection files and
the lane ledger bytes.

**Acceptance Scenarios**:
1. **Given** the ledger flag on (default) and drain off, **When** a WP transitions, **Then** the
   derived execution-state projection is refreshed to match the lane ledger, and nothing is sent.
2. **Given** the ledger flag off, **When** a WP transitions, **Then** no projection is refreshed
   automatically, the on-demand materialize command still produces it, and the lane ledger, its
   commit and the committed status snapshot are byte-identical to the flag-on run.
3. **Given** a git operation (rebase/merge) in progress, **When** a transition would refresh the
   projection, **Then** the refresh is skipped without error.

### User Story 4 — No shipped live endpoint (Priority: P1)

A fresh install has no packaged hosted address. Hosted commands need an explicit endpoint.

**Why this priority**: operator directive (2026-09-23), deliberately reversing #3980 D-5 for the
frozen-server period.

**Independent Test**: with no environment variable and no config key, resolve the hosted target and
run `auth login`/`auth status`; assert a guidance error (no traceback) and no network call.

**Acceptance Scenarios**:
1. **Given** no endpoint configured, **When** the developer runs `spec-kitty auth login`, **Then**
   it exits non-zero with guidance naming `SPEC_KITTY_SAAS_URL` and `config.toml [sync].server_url`,
   and contacts no host.
2. **Given** no endpoint configured, **When** the developer runs `spec-kitty auth status` (or any
   other hosted diagnostic), **Then** it reports "no hosted endpoint configured" without a
   traceback.
3. **Given** an endpoint configured via environment or config, **When** the developer logs in,
   **Then** behaviour is unchanged from today (precedence env > config; split-brain guard intact).
4. **Given** a machine whose config still names the retired `app.spec-kitty.ai`, **When** the
   upgrade migration runs, **Then** the stale value is removed (not rewritten to a live default)
   and the operator is told to configure an endpoint explicitly.

### Edge Cases

- Drain config file is unparseable (repo or global) ⇒ drain treated as **off** (fail closed), with
  one warning; local work unaffected.
- Drain value is present but non-boolean ⇒ off + warning (never truthiness-coerced).
- Drain toggled between two commands in one shell ⇒ the new value applies on the next command
  (the value is read per invocation, not frozen at import).
- Existing kill switch `SPEC_KITTY_NO_MOMENT_HANDLERS` set while drain on ⇒ the kill switch still
  wins (it only ever narrows).
- Ledger flag unparseable/non-boolean ⇒ default (on) + warning; lane state unaffected either way.
- Hosted endpoint configured but drain off ⇒ explicit commands (login, tracker) work; automatic
  drain paths stay silent.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status |
|----|-------|------------|----------|--------|
| FR-001 | Repository drain key | As an operator, I want a boolean `hosted.drain` key in `.kittify/config.yaml` (default off/absent) so that a repository can declare it permits live drain. | High | Approved |
| FR-002 | Personal drain activation | As a developer, I want a boolean drain activation in my user-global Spec Kitty config (default off) so that no committed file can switch live drain on for me without my consent. | High | Approved |
| FR-003 | Effective drain = both | As an operator, I want drain to be effective only when FR-001 and FR-002 are both on, so that either party can keep data on the machine. | High | Approved |
| FR-004 | Drain gates every automatic hosted egress | As an operator, I want drain-off to stop every automatic outbound hosted interaction — status/lifecycle/resolved-binding/runtime moments, decision live-frame, presence and focus frames, relay capability resolution and minting (including use of a cached credential), live-work publishing — before any network or credential access, so that nothing leaves the machine. | High | Approved |
| FR-005 | Drain gates live subscriptions | As an operator, I want the live stream/watch/history commands and their MCP equivalents to refuse with guidance when drain is off, so that no live subscription is established. | High | Approved |
| FR-006 | Drain off never degrades local work | As a developer, I want every local command to exit exactly as it would without hosted features when drain is off, so that the frozen server never blocks my mission. | High | Approved |
| FR-007 | Drain status visible | As a developer, I want a command that reports the effective drain state and which file decided each scope, plus a way to set my personal activation, so that I can see and change my posture without editing files by hand. | Medium | Approved |
| FR-008 | Ledger key | As an operator, I want a boolean `ledger.projection` key in `.kittify/config.yaml` (default on) so that I control automatic production of the local execution-state projection. | Medium | Approved |
| FR-009 | Projection refresh on transition | As a developer, I want the derived execution-state projection refreshed after each successful lane transition when the ledger flag is on, so that the local dashboard always reads fresh state without the network. | Medium | Approved |
| FR-010 | Ledger floor | As an operator, I want the ledger flag to never affect the lane ledger, its commit, the committed status snapshot, the decision ledger, the runtime run journal or invocation records, so that lane state and the permanent record are intact under every setting. | High | Approved |
| FR-011 | No packaged hosted endpoint | As an operator, I want the hosted endpoint to resolve only from `SPEC_KITTY_SAAS_URL` or `config.toml [sync].server_url`, with no built-in live address, so that a fresh install targets no hosted server. | High | Approved |
| FR-012 | Guidance when unconfigured | As a developer, I want explicit hosted commands (login, status, doctor, tracker, routes, decision widen) to stop with setup guidance when no endpoint is configured — never a traceback — and automatic paths to stay silent. | High | Approved |
| FR-013 | Retired-target migration opt-in | As an operator upgrading a machine configured for the retired `app.spec-kitty.ai`, I want the migration to drop that stale value and tell me to configure an endpoint, rather than rewriting it to a live address. | Medium | Approved |
| FR-014 | Decision record | As a maintainer, I want an ADR recording the reversal of #3980 D-5 (packaged default) and the two-scope drain consent model, so that the policy change is governed rather than silent. | High | Approved |
| FR-015 | Documentation | As an operator, I want the configuration reference, environment-variable reference and the Team Kitty context page updated to the opt-in model, so that docs mirror shipped behaviour. | Medium | Approved |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Zero egress by default | With no drain configuration and no endpoint configured, a full lane walk (9 lanes) plus one decision round-trip makes **0** outbound hosted requests (asserted by instrumenting every hosted network edge). | Privacy | High | Approved |
| NFR-002 | Gate is non-vacuous | An architectural test proves every hosted network edge sits behind the drain gate (concrete floor ≥ the 4 known edges; a self-mutation check shows removing a gate call turns the test red; allowlist shrink-only). | Reliability | High | Approved |
| NFR-003 | No latency cost | Drain-off adds no measurable wall-clock to a lane transition (gate check < 5 ms; no network timeouts are waited on). | Performance | Medium | Approved |
| NFR-004 | Lane FSM integrity | Across all 4 combinations of {ledger on/off} × {drain on/off}, lane-ledger bytes, status-ref commit count and the reduced snapshot are identical. | Reliability | High | Approved |
| NFR-005 | Coverage | New and changed code reaches ≥ 90% diff coverage; ruff, ruff format and mypy report 0 issues on touched files. | Quality | High | Approved |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Server frozen | No server-side (SaaS or Zeitgeist) change is required or made. | Business | High | Approved |
| C-002 | Sync stays dead | Do not resurrect the sync daemon/queue/consent transport; do not reuse `SPEC_KITTY_ENABLE_SAAS_SYNC` or `SPEC_KITTY_SYNC_*` as the drain gate; no new `SYNC_`/`SAAS_`/`TEAMSPACE` identifiers. | Technical | High | Approved |
| C-003 | Canonical config | Reuse the existing config-loading patterns (`.kittify/config.yaml` section loaders; user-global `config.toml` as used by `[moments]`); no new config file format. | Technical | High | Approved |
| C-004 | Layering | Respect `kernel <- charter <- {glossary, runtime, mission_runtime} <- specify_cli`; add no new `runtime -> specify_cli` import edge. | Technical | High | Approved |
| C-005 | #4311 coupling | Any live-publish retry (present or future, #4311) must sit behind the same drain gate; drain-off is a clean skip, never a diagnostic-as-error. #4311's commit-on-record is untouched. | Technical | High | Approved |
| C-006 | Endpoint key name | Keep `config.toml [sync].server_url`; its rename is out of scope (D-4). | Technical | Medium | Approved |
| C-007 | Scope of "zero network" | "Zero network" means no `*.spec-kitty.ai` / Team Kitty / Zeitgeist host. The PyPI upgrade-check notice is out of scope (it already has `SPEC_KITTY_NO_UPGRADE_CHECK`). | Scope | Medium | Approved |

### Key Entities

- **Drain posture**: effective boolean + per-scope provenance (repository value/source file, personal value/source file, kill-switch override).
- **Ledger posture**: effective boolean + source.
- **Hosted endpoint target**: resolved address or *unconfigured*, with provenance (env / config).
- **Execution-state projection**: derived per-mission snapshot (lane state, progress, lifecycle) under `.kittify/derived/<mission>/`.

## Success Criteria *(mandatory)*

- **SC-001**: A fresh install running a complete mission contacts no hosted server (0 requests).
- **SC-002**: An operator who opts in (both scopes + endpoint) sees live moments exactly as before (1 moment per transition).
- **SC-003**: Lane state and the decision record are identical under all 4 flag combinations.
- **SC-004**: With the ledger flag on, the local projection matches the lane ledger after every transition (100% of transitions in the lane walk).
- **SC-005**: Every explicit hosted command without an endpoint ends with actionable guidance, 0 tracebacks.

## Assumptions

- The user-global config is `config.toml` under the Spec Kitty home (the same home `[moments]` uses); the drain activation lives in a new `[hosted]` table there.
- `.kittify/derived/` stays gitignored; the projection uses the existing derived-views writers, fed by a write-free snapshot.
- #4311's bounded retry is not yet on main; C-005 is satisfied by construction because the gate sits at the network edge.

## Out of scope / follow-ups

- Renaming `[sync].server_url` (D-4) — follow-up issue.
- Retiring `SPEC_KITTY_ENABLE_SAAS_SYNC` residue (tracker/readiness gate) — may be folded only where it touches the same lines; otherwise follow-up.
- #5113 (decision open/resolve on an unmaterialized coord worktree) — tooling friction met during this mission, tracked separately.
