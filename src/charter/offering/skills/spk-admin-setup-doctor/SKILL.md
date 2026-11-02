---
name: spk-admin-setup-doctor
description: "Install, verify, and repair Spec Kitty commands, skills, agent paths, runtime prerequisites, and common setup failures."
---

# spk-admin-setup-doctor

Use this skill when Spec Kitty is missing commands, skills, runtime files,
agent config, or expected local behavior.

## Flow

1. Run `spec-kitty doctor` first: a bare invocation runs the fast, read-only default
   checks (`command-files`, `state-roots`, `ops`) and exits 0 when healthy, 1 when a check
   reports a finding, naming the subcommand behind it. Drill into
   `spec-kitty doctor <subcommand>` (add `--json` for machine-readable detail) and use the
   subcommand's repair flag (`--fix`, `--repair`, `--close-stale`) only for the surface it
   flags.
2. Verify slash commands and skills exist for the active agent surface.
3. Repair generated command skills before editing installed copies by hand.
4. Use setup references to diagnose common failures.

## Legacy Alias

For detailed diagnostics and path matrices, use `spec-kitty-setup-doctor` when
available.
