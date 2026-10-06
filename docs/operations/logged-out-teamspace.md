---
title: 'Recovery: Logged out on a connected teamspace'
description: 'Recovery for a repository connected to a Spec Kitty teamspace when the local CLI session is logged out: the teamspace-aware recovery path sync commands surface.'
doc_status: active
updated: '2026-08-23'
---
# Recovery: Logged out on a connected teamspace

> **Status (2026-10-06):** Team Kitty is no longer actively supported
> ([ADR 2026-10-06-1](../adr/4.x/2026-10-06-1-team-kitty-surfaces-are-hidden-unless-drain-is-on.md)).
> This page describes code that still ships but is off by default; do not build
> toward it unless the operator asks for hosted work.


When a repository is connected to a Spec Kitty teamspace but the local CLI
session is logged out (no credentials, or refresh token expired), every
`spec-kitty sync ...` command surfaces a teamspace-aware recovery path
instead of just printing the generic `Run spec-kitty auth login` message.

This page documents the operator and CI contract for the recovery flow.

## Interactive operators

When `stdin` is a TTY (and `SPEC_KITTY_NON_INTERACTIVE` is not set), the CLI
renders a Rich panel naming the connected teamspace and offers three
single-keystroke choices:

```
┌─ Logged out on a connected teamspace ─────────────────────────────────┐
│ This repo is connected to teamspace acme-eng, but you are not logged  │
│ in. Command: spec-kitty sync now                                      │
│                                                                       │
│ Choose: Login to re-authenticate, Skip and continue with the legacy   │
│ message, Quit.                                                        │
└───────────────────────────────────────────────────────────────────────┘
[L]ogin / [S]kip / [Q]uit:
```

| Key | Action |
|-----|--------|
| `L` | Invokes `spec-kitty auth login` inline. On success the command exits 0 with `Re-run spec-kitty <command> to continue.` On `AuthenticationError`, falls through to the legacy message. |
| `S` | Skips recovery. The legacy `Run spec-kitty auth login` message prints and the command exits with its normal non-zero code. |
| `Q` | Quits without further output. Exit code matches the legacy non-zero path. |

## CI and scripts (non-interactive)

When `stdin` is not a TTY, or `SPEC_KITTY_NON_INTERACTIVE=1` is set, the CLI
writes a single stable line to `stderr` and exits with code `4`:

```
spec-kitty: logged_out_on_connected_teamspace teamspace=<slug> command=<name> action=run-spec-kitty-auth-login
```

CI snippets can match on either the stderr line or the exit code. The exit
code is the recommended discriminator since it is decoupled from the message
wording:

```bash
set +e
spec-kitty sync now
rc=$?
set -e
case "$rc" in
  0) echo "Synced." ;;
  4) echo "Logged out on a connected teamspace - re-auth required" ;;
  *) echo "Other failure (rc=$rc)" ;;
esac
```

## Environment variables

| Variable | Effect |
|----------|--------|
| `SPEC_KITTY_NON_INTERACTIVE=1` | Always treat the session as non-interactive, even on a TTY. Forces the structured stderr + exit 4 path. |
| `SPEC_KITTY_FORCE_INTERACTIVE=1` | Always show the interactive prompt, even when stdin is not a TTY (useful in headless terminals that misreport TTY state). Wins over `SPEC_KITTY_NON_INTERACTIVE`. |

## Backward compatibility

When the CLI cannot determine a previously connected teamspace (the repo has
never been associated with one), every command keeps its existing legacy
behavior: it prints `Run spec-kitty auth login` and exits with the same
non-zero code as before. The structured stderr line and exit code `4` are
**only** emitted when a teamspace is actually detected.

## Commands that participate

Hosted-only commands require a usable session and retain their normal refusal
behavior:

- `spec-kitty sync now`
- `spec-kitty sync status --check`
- `spec-kitty sync doctor`
- `spec-kitty sync routes`
- `spec-kitty sync share` / `spec-kitty sync unshare` / `spec-kitty sync opt-out --delete-private-data`

Local Mission commands are different. Their logged-out policy is explicit per
command so the local and hosted outcomes cannot be conflated:

| Command | Eligible local work while logged out | Interactive login | Authoritative local result |
|---------|----------------------------------------|-------------------|----------------------------|
| `spec-kitty agent mission create` | Completes eligible local artifact work | Never starts one | Local mission-creation result and exit code |
| `spec-kitty agent mission setup-plan` | Completes eligible local verification | Never starts one | Local verification payload and exit code |

After the sync transport was retired, `setup-plan` never attempts hosted
delivery: local verification is the authoritative result. Automation must not
start an interactive login on the operator's behalf.

The interactive recovery surface is intentionally limited to hosted-only
`sync` commands. Other commands (notably `spec-kitty auth doctor` and
`spec-kitty next`) keep their own existing flows.

## Related

- `spec-kitty auth login` -- the underlying login flow invoked by `L`.
- `spec-kitty sync doctor` -- the most informative diagnostic when sync
  appears broken; will offer the recovery prompt when applicable.
- [Internal Hosted-Readiness (Pre-Launch)](internal-hosted-readiness.md)
  -- the operator how-to for dogfooding the hidden hosted-readiness
  mode that surfaces this recovery path.
- Issue: [Priivacy-ai/spec-kitty#829](https://github.com/Priivacy-ai/spec-kitty/issues/829).
