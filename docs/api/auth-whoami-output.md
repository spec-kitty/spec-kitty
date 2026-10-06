---
title: auth whoami output reference
description: Full stdout shape of spec-kitty auth whoami, including the SaaS diagnostic lines the generated --help text doesn't mention.
doc_status: active
updated: '2026-08-27'
---
# `auth whoami` output reference

> **Status (2026-10-06):** Team Kitty is no longer actively supported
> ([ADR 2026-10-06-1](../adr/4.x/2026-10-06-1-team-kitty-surfaces-are-hidden-unless-drain-is-on.md)).
> This page describes code that still ships but is off by default; do not build
> toward it unless the operator asks for hosted work.


The generated [`spec-kitty auth whoami`](cli-commands.md#spec-kitty-auth-whoami)
section only carries the `--help` text, which still describes the original
single-line contract: print the email and exit 0, or exit 1 if not
authenticated. Since #177/#182 the command prints more on stdout. Both
behaviors are real and covered by
`tests/cli/commands/test_auth_whoami.py`; this page documents what `--help`
does not.

## What prints, in order

1. **The email** — a bare `print()`, always the first non-empty line. This is
   the machine-consumed identity token; preflight/canary scripts that read
   "the first non-empty output line" are unaffected by anything below.
2. **The `SaaS:` line** — the same endpoint `auth login`/`auth status` use,
   from `_print_saas_target` (`src/specify_cli/cli/commands/_auth_status.py`):
   - `  SaaS:           <resolved-url> (from SPEC_KITTY_SAAS_URL | from config.toml [sync].server_url)`, or
   - `  SaaS:           not configured — set SPEC_KITTY_SAAS_URL (or [sync].server_url in config.toml)` when nothing resolves.
3. **`Session SaaS:`** — only when the stored session recorded an issuer URL:
   `  Session SaaS:   <issuer-url> (authenticated session)`.
4. **A mismatch warning** — only when the session's issuer disagrees with the
   currently-resolved endpoint:
   `  Session is for <issuer>; <source> now points at <resolved-url> — run spec-kitty auth login --force`.

Lines 2-4 all print through the same shared `console` (stdout) as the email —
there is no separate stderr channel for them today. A consumer that wants a
single clean identity token should keep reading "the first line", not "all of
stdout".

## Why the split exists

`whoami_impl`'s docstring (`src/specify_cli/cli/commands/_auth_whoami.py`)
states the intent directly: keep the identity line bare and first so the
pre-existing machine contract holds, while giving a human running the command
interactively the same SaaS visibility `auth status` already has.
