---
title: 'ADR: hosted interaction is opt-in, twice, with no packaged endpoint'
description: 'Reverses the #3980 packaged hosted-endpoint default and records the two-scope live-drain consent model plus the ledger-projection flag this mission ships (#4971).'
status: Accepted
date: '2026-09-26'
---

## Context and Problem Statement

Team Kitty's server side has been frozen for development while the SaaS and Zeitgeist relay
mature. Against that freeze, the CLI still shipped a hard-coded live default
(`https://team.spec-kitty.ai`, #3980) and automatically fanned status, lifecycle, runtime, and
decision moments out to it whenever an endpoint resolved — with no per-developer or per-repository
consent step. On 2026-09-23 the operator directed that the shipped build stop targeting a live
hosted server on its own: nothing should leave a fresh install's machine unless the developer has
explicitly opted in.

There is a gap in the record this ADR closes first. Mission `team-kitty-launch-defaults-01M1XJ4Y`
WP01 *planned* the ADR that would have recorded the original packaged-default decision
(`2026-09-07-1-packaged-hosted-target-default.md`), but that file was **never written**
(research.md R4 for this mission). Reversing an undocumented decision has no prior record to
amend, so this ADR is the sole governance record covering both the original packaged-default
decision this mission reverses and the new two-scope drain consent model that replaces it.

Two further constraints shaped the design:

- The committed lane ledger (`status.events.jsonl`) and decision ledger (`decisions/`) are a
  non-optional floor ("Git carries DONE", #4311) — no opt-in flag in this mission may be able to
  stop them being written or committed, only the *automatic outbound hosted* side effects.
- A future bounded live-publish retry for #4311 is anticipated but not yet on `main`; whatever gate
  this mission adds must also bind that future edge, not just today's callers (C-005).

## Decision

Reverse the packaged default and replace it with a two-scope, explicit opt-in ("drain") plus a
narrower, unrelated flag for the local execution-state projection ("ledger"). Recorded verbatim in
spirit from the mission's Operator decisions table and its post-spec squad resolutions:

- **D-1 — Drain lives in two places, both required.** `.kittify/config.yaml` → `hosted.drain`
  (repository opt-in) **and** the developer's runtime-root `config.toml` → `[hosted] drain`
  (personal activation). Effective drain requires both on; either off or absent is off. Managed by
  `spec-kitty moments drain on|off|status [--repo]`.
- **D-2 / FR-010 — The ledger flag gates only the derived projection.** `.kittify/config.yaml` →
  `ledger.projection` (default `true`) gates automatic refresh of the gitignored, derived,
  always-rebuildable local execution-state projection under `.kittify/derived/<mission>/` — never
  the lane ledger, its commit, the committed status snapshot, the decision ledger, the run journal,
  or invocation records. The two flags are orthogonal axes: one gates outbound network side
  effects, the other gates a purely local, re-derivable read model.
- **D-3 — Explicit vs automatic guidance split.** An explicit hosted command run with no configured
  endpoint stops with setup guidance naming `SPEC_KITTY_SAAS_URL` and `config.toml
  [sync].server_url`, no traceback (`HostedEndpointUnconfigured`) — most such commands exit
  non-zero, but a status-reporting command (`auth status`) exits 0 with the same guidance, since
  reporting "not configured" is itself a successful answer. An automatic path (a lane transition, a
  lifecycle beat) resolves the endpoint via `resolve_server_target_or_none()` and stays silent when
  none is configured.
- **FR-004 — Widen and interview startup skip their hosted prereq probe when drain is off.** (Not
  independently lettered in the Operator decisions table; folded into FR-004's "every automatic
  hosted egress" requirement, not to be confused with plan.md's unrelated "D7" personal-writer
  strictness label.) `widen/prereq.py::check_prereqs` and the charter/specify/plan interview
  startups
  (`cli/commands/charter/interview.py`, `missions/plan/plan_interview.py`,
  `missions/plan/specify_interview.py`) each check `hosted_posture.drain_posture().enabled` before
  making any call against the injected SaaS client — with drain off, the automatic hosted prereq
  probe these startups would otherwise run is skipped outright, consistent with D-3's "automatic
  paths stay silent" rule rather than surfacing a probe failure.
- **D-4 / C-006 — Keep `[sync].server_url`'s name.** Its rename is a separate, out-of-scope
  follow-up; this mission does not touch the key name.
- **D-5 — The personal activation file is the runtime-root `config.toml`.** Resolved by
  `specify_cli.paths.get_runtime_root()` — `~/.spec-kitty/config.toml` on POSIX,
  `SPEC_KITTY_HOME`-overridable — the same file that already carries `[sync].server_url`. This is
  **not** `~/.kittify/config.toml`, where `[moments]` already lives; the two are deliberately
  different files, and `moments drain status` prints the resolved absolute path of every file it
  reads (including this one) so the distinction is never silent.
- **D-6 / FR-016 — Logged-in machines keep their endpoint.** A machine with a stored auth session
  from before the packaged default was removed has that session's `issuer_url` backfilled into
  `[sync].server_url` by an upgrade migration when no endpoint is configured — read-only against
  the session store, never for a retired first-party host, never overwriting an explicit value, and
  never enabling drain on its own. A configured endpoint and an enabled drain are independent
  facts.
- **R-1 — No environment variable can enable drain, in either scope.** The only env vars
  `hosted_posture.drain_posture()` itself consults as narrowers are the three folded into
  `moment_handlers_disabled_reason()` — `SPEC_KITTY_NO_MOMENT_HANDLERS`, `SPEC_KITTY_SYNC_DISABLE`,
  and the deprecated alias `SPEC_KITTY_SYNC_MINIMAL_IMPORT` — any of which forces the effective
  posture off even with both scopes on. `[moments] agents = "off"` is a **separate, non-env-var**
  axis: the global or per-repo `[moments]` config key (`~/.kittify/config.toml` or
  `<repo>/.kittify/config.toml`) that narrows which moments reach agent context. `DrainPosture`
  itself does not read it — it is tracked independently, alongside drain's own narrowers, by
  `moments drain status` (`_drain_narrowers` in `cli/commands/moments.py`) as a second axis that
  can also block a moment even when drain is fully on. A per-repo `.kittify/config.toml` never
  carries the personal drain activation either — only the runtime-root `config.toml` does (D-5).
- **R-2 — Explicit endpoint configuration is not drain-enablement.** `.kittify/saas-auth.json`
  (its own token) and a `SPEC_KITTY_SAAS_URL` sourced from a committed `.kitty.env` both count as
  explicit operator configuration of *where* hosted traffic would go, never as consent for it to be
  sent automatically.
- **R-3 — Drain gates all relay traffic, not auth or the tracker.** Every relay CLI command and MCP
  relay tool — including operator-typed commands such as `zeitgeist send/reply/outbox approve` —
  pre-flights `require_drain("relay")` before any credential read. `auth login/logout/status/
  whoami/doctor` and tracker commands are gated only by whether an endpoint is configured, not by
  drain.
- **R-4 / FR-013 — The retired-target migration now deletes, it no longer rewrites (#4259).**
  `m_4_0_0_retired_hosted_target` previously *rewrote* a saved `config.toml [sync].server_url`
  naming the retired first-party address (`https://app.spec-kitty.ai`) to the packaged default;
  endpoint opt-in (D-1..D-5, reversing #3980) removed that packaged default from the resolver
  entirely, so rewriting to a live address here would silently point a machine that never
  configured a hosted endpoint at one. The migration's `apply()` now **deletes** the stale key
  instead and prints the same `SPEC_KITTY_SAAS_URL` / `config.toml [sync].server_url` setup
  guidance an unconfigured explicit command would show — every other saved value is untouched.
  A machine that already has `team.spec-kitty.ai` recorded from an earlier run of this same
  migration (before this behavior change) is a distinct, explicitly-preserved case: it keeps that
  value as explicit, opt-in configuration. Drain still defaults off in both cases, so no automatic
  traffic follows from a configured endpoint alone.

The operator surface for the whole model is `spec-kitty moments drain on|off|status [--repo]
[--json]`, which reads and writes exclusively through `core.hosted_posture` (never a second
config reader or writer) and reports the effective posture, both scopes' values and source files,
active narrowers, the ledger-projection posture, and all four hosted-posture file paths — existing
or not.

## Consequences

- **A fresh install talks to no server.** With no endpoint configured and drain off by default,
  neither `SPEC_KITTY_SAAS_URL` nor `config.toml [sync].server_url` need to be set for local work
  — specify, plan, tasks, implement, lane transitions, decisions — to complete unaffected; the
  committed lane and decision ledgers are unconditionally intact under every setting (FR-010).
  "Zero network" here means no `*.spec-kitty.ai` / Team Kitty / Zeitgeist host is contacted; the
  PyPI upgrade-check notice is explicitly out of this scope — it already has its own opt-out,
  `SPEC_KITTY_NO_UPGRADE_CHECK` (C-007).
- **The #4311 coupling is closed by construction, not by a future patch (C-005).** #4311's bounded
  live-publish retry is not yet on `main`; because the drain gate sits at the network edge
  (`transport.ZeitgeistClient.offer`, the capability gateway, the relay CLI/MCP surfaces) rather
  than at each call site that might someday retry, any future retry path inherits the same
  drain-off clean-skip behavior automatically. A drain refusal is never a diagnostic-as-error and
  is never retried.
- **Two independent opt-ins replace one implicit default.** An operator who wants live drain must
  turn on both the repository scope and their own personal scope — there is no single switch, and
  no environment variable can shortcut either one (R-1). This is a deliberate friction increase
  over the pre-#3980-reversal behavior, in service of the "twice, explicitly" requirement in
  #4971's brief.
- **Forward references, not relitigated here:** renaming `[sync].server_url` (D-4) stays a separate
  follow-up issue; retiring the `SPEC_KITTY_ENABLE_SAAS_SYNC` residue is likewise deferred except
  where a future change happens to touch the same lines. This ADR records only what this mission
  shipped.
