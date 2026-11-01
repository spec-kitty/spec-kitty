---
title: "spk-admin-setup-doctor"
description: "Install, verify, and repair Spec Kitty commands, skills, agent paths, runtime prerequisites, and common setup failures."
doc_status: active
updated: '2026-07-21T00:00:00Z'
related: [docs/api/skills/index.md]
kind: Reference
---

# spk-admin-setup-doctor

## What it does

Diagnoses and repairs a broken or incomplete Spec Kitty installation: missing
slash commands, missing skills, missing agent config, or other runtime files
your harness expects but can't find. It runs the appropriate setup or doctor
command, verifies slash commands and skills exist for the active agent
surface, and repairs generated command skills rather than hand-editing
installed copies.

## When to reach for it

Reach for this skill when Spec Kitty isn't behaving as installed — slash
commands are missing, `spec-kitty next` is blocked for setup reasons rather
than mission reasons, doctrine assets appear absent, or your agent can't find
its skills. It is not for generic coding questions unrelated to Spec Kitty,
for advancing a running mission (`spec-kitty next` / `spk-run-next` owns
that), or for editorial glossary maintenance.

## Trigger phrases

Per the legacy alias's description (`spec-kitty-setup-doctor`): "set up Spec
Kitty," "skills missing," "next is blocked," "runtime is broken," "doctrine
assets are missing," "my agent can't find the skills."

## Flow

1. Run the setup or doctor command appropriate to the install.
2. Verify slash commands and skills exist for the active agent surface.
3. Repair generated command skills before editing installed copies by hand.
4. Use setup references to diagnose common failures.

## What it does not do

It does not handle generic coding questions with no Spec Kitty context,
direct runtime loop advancement, or editorial glossary maintenance.

## Legacy alias

For detailed diagnostics and path matrices — including the
`spec-kitty doctor skills --json` / `--fix` commands, the agent path matrix,
and a catalog of known failure signatures — use `spec-kitty-setup-doctor`
when available.
