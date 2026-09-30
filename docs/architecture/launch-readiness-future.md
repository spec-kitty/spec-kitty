---
title: Launch-Readiness Behavior (Coming Soon)
description: "Pre-launch design intent for Teamspace: how hosted-readiness defaults flip from opt-in to on, and the launch-coordinator playbook. None of it is in effect today."
doc_status: superseded
updated: '2026-09-30'
type: explanation
audience: docs/context/audience/internal/maintainer.md
---
# Launch-Readiness Behavior (Coming Soon)

> **Superseded; kept as a pre-Zeitgeist design record.** This plan was framed
> around the retired sync transport: `SPEC_KITTY_ENABLE_SAAS_SYNC` no longer
> gates hosted behavior, and there is no `spec-kitty sync` command. Hosted
> interaction is now opt-in twice on the client (drain, managed with
> `spec-kitty moments drain on|off|status`) and gated on the server by team
> membership and repository admission. Read
> [Team Kitty and Zeitgeist](../context/team-kitty.md) and ADR
> [`2026-09-26-3`](../adr/3.x/2026-09-26-3-hosted-interaction-opt-in.md) for the
> current model.

> **Status (2026-09-27): the packaged-default half of the flip was reversed
> (endpoint opt-in, ADR
> [`2026-09-26-3`](../adr/3.x/2026-09-26-3-hosted-interaction-opt-in.md)).**
> The #3980 flip below briefly landed a packaged default
> `https://team.spec-kitty.ai` baked into the CLI; that default has since
> been **removed** — there is no built-in fallback endpoint any more, and
> every explicit caller raises `HostedEndpointUnconfigured` with setup
> guidance unless `SPEC_KITTY_SAAS_URL` or `config.toml [sync].server_url`
> is set explicitly. The "Default SaaS URL" row below is stale design intent
> that did not survive; do not treat it as current or planned behavior. See
> [Team Kitty and Zeitgeist](../context/team-kitty.md) for the current,
> opt-in-first transport and
> [environment variables](../api/environment-variables.md) for the current
> reference.

## Why this doc exists

The Spec Kitty CLI today is local-first. Hosted auth, sync, and
tracker flows are opt-in behind the `SPEC_KITTY_ENABLE_SAAS_SYNC=1`
environment variable. At the public Teamspace launch, the user-facing
defaults change. This doc is the reference the launch coordinator
flips on. Until that flip happens, treat every section below as a
**design intent**, not a description of current behavior.

If you are an end user today, you will not see any of this. The
public docs and the CLI's defaults continue to describe the
local-first experience.

## What changes at launch

The table below frames the launch as a delta from today. **"Today"
columns describe behavior on `main` right now; "At launch" columns
describe behavior that will ship at the launch milestone.**

| Dimension | Today (pre-launch) | At launch |
|---|---|---|
| `SPEC_KITTY_ENABLE_SAAS_SYNC` | **Opt-in gate.** Unset / falsy = local-first; truthy = hidden hosted-readiness mode for internal operators. | **Override only.** Hosted readiness is on by default; the variable becomes an internal escape hatch (e.g., `SPEC_KITTY_ENABLE_SAAS_SYNC=0` to force local-only). |
| Default SaaS URL | Operators must set `SPEC_KITTY_SAAS_URL` explicitly to dial dev / staging. There is no user-facing default. | **Reversed, see banner above.** ~~A user-facing default URL ships baked into the CLI. End users do not set `SPEC_KITTY_SAAS_URL`.~~ Endpoint opt-in (ADR `2026-09-26-3`) means this never shipped as permanent behavior: there is no packaged default, at launch or since — every user configures `SPEC_KITTY_SAAS_URL` or `config.toml [sync].server_url` explicitly. |
| Sync default | Sync commands no-op unless hosted mode is explicitly enabled. | Sync runs by default for Teamspace-connected repos. The same suppression contract still applies (interactive / non-interactive / machine-output). |
| Tracker discovery | Tracker calls only happen behind the opt-in gate. | Tracker discovery happens by default for Teamspace-connected repos; unreachable-tracker states surface via the readiness coordinator. |
| `spec-kitty auth login` | Documented as the canonical hosted login flow for internal operators dogfooding the hidden mode. | Documented as the canonical hosted login flow for **all** users joining a Teamspace. |
| Public docs framing | Local-first. Hosted is "optional / opt-in / later". | Local-first remains the on-ramp; Teamspace becomes "available" — never retroactively backdated as "always was". |

## Dev / staging overrides still apply after launch

`SPEC_KITTY_SAAS_URL` and the other operator-only overrides survive
the launch flip. They remain internal developer tools — they are not
user behavior either before or after launch. Internal contributors
who need to point a session at a dev or staging hosted environment
continue to use the workflow documented in
[Internal Hosted-Readiness Mode (Pre-Launch)](../operations/internal-hosted-readiness.md).

In other words: **the dev/staging override path is the same forever;
only the user-facing defaults change at launch.**

## Launch-day remediation commands

These commands are what end users will run at launch in each
readiness scenario the coordinator surfaces. They are copy-pasteable;
each appears on its own line so a CLI nag panel can render them
verbatim.

```bash
spec-kitty auth login
```

```bash
spec-kitty upgrade --cli
```

```bash
spec-kitty sync doctor
```

| Scenario at launch | Command users will run |
|---|---|
| Logged out on a connected Teamspace | `spec-kitty auth login` |
| CLI upgrade required for compatibility with the hosted side | `spec-kitty upgrade --cli` |
| Sync / tracker subsystem unreachable | `spec-kitty sync doctor` |

The exact wording the CLI prints in each case is set by the
readiness coordinator and its sister modules. This doc does not
restate the byte-stable strings; it points the reader at them.

## Upgrade readiness UX

The launch readiness coordinator owns the upgrade prompt. It uses the
existing compatibility planner and `NagCache` state, then adds user-facing
choices:

- Upgrade now.
- Always keep me up to date.
- Not now.
- Never ask again.

"Not now" snoozes the same remote version on a conservative cadence:
24 hours, then 48 hours, then 7 days. A newly discovered remote version
restarts that cadence. "Never ask again" is also anchored to the remote
version the user dismissed.

Auto-upgrade is fail-closed. It only runs for known-safe install methods
where the CLI can call the owning package manager directly (`pipx`, `uv tool`,
Homebrew, and pip installs). Unknown, source, or system-package installs print
manual guidance and do not mutate the environment.

Upgrade readiness never prompts, mutates the upgrade cache, or invokes an
auto-upgrade subprocess during JSON, quiet, help, version, CI, non-TTY, or
`SPEC_KITTY_NO_NAG=1` invocations. These outputs remain safe for wrappers that
parse stdout.

Operator overrides:

```bash
SPEC_KITTY_UPGRADE_DISABLED=1 spec-kitty upgrade --cli
SPEC_KITTY_UPGRADE_AUTO=1 spec-kitty upgrade --cli
SPEC_KITTY_UPGRADE_NEVER_ASK=1 spec-kitty upgrade --cli
SPEC_KITTY_NAG_THROTTLE_SECONDS=86400 spec-kitty upgrade --cli
```

See [Environment Variables Reference](../api/environment-variables.md)
for the exact active env keys.

## Operator playbook for the launch flip

This is the high-level launch coordinator checklist, not a
release-cut runbook. Exact versions, dates, and step ordering live
in the release-cut documentation in `architecture/` and the
`spec-kitty-saas` repo.

1. Confirm the hosted side is generally available and the readiness
   coordinator has clean dogfooding evidence behind
   `SPEC_KITTY_ENABLE_SAAS_SYNC=1`.
2. Cut a CLI release where the **default** behavior of the rollout
   gate inverts: hosted readiness is on unless explicitly disabled.
3. Update public docs (README, `docs/index.md`, the relevant
   tutorials) to introduce Teamspace as **available** — never as
   "always was". The current pre-launch local-first framing remains
   the on-ramp.
4. Move this doc from `docs/architecture/` to a launch-day "what's
   new" location, or update its banner from
   `Status: pre-launch` to `Status: launched` once the flip is
   live. **Do not retroactively edit this doc as if its content
   were always current.**
5. Keep the internal hosted-readiness how-to in place; rewrite its
   "When this page applies" section to reflect that the dev /
   staging override path is now the only thing it covers.

Step 3's "available — never as 'always was'" line is the load-bearing
editorial rule. It is what keeps the launch honest.

## What this doc deliberately does not specify

- **Exact dates or version numbers.** Those live in the release-cut
  runbook, not in a conceptual explanation doc.
- **Server-side behavior.** Hosted-side changes are owned by the
  `spec-kitty-saas` repo and its release notes.
- **Marketing copy.** This doc speaks to operators planning the
  flip; user-facing announcement copy is owned elsewhere.
- **Migration steps for users who set `SPEC_KITTY_ENABLE_SAAS_SYNC=1`
  pre-launch.** Their setup keeps working; the variable becomes a
  no-op-redundant override at launch. If a deprecation is needed,
  it ships in a separate release-cut PR.

## Related

- [Internal Hosted-Readiness Mode (Pre-Launch)](../operations/internal-hosted-readiness.md)
  — the active dogfooding doc for today.
- [Recovery: Logged out on a connected teamspace](../operations/logged-out-teamspace.md)
  — the recovery contract that ships at launch unchanged.
- [Environment variables reference](../api/environment-variables.md)
  — the canonical entries for `SPEC_KITTY_ENABLE_SAAS_SYNC` and
  `SPEC_KITTY_SAAS_URL`.
- [Upgrade the Spec Kitty CLI](../guides/how-to/installation/upgrade-cli.md)
  — backs the `spec-kitty upgrade --cli` remediation snippet.
