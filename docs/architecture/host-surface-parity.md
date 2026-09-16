---
title: Host-Surface Parity Matrix
description: Spec Kitty's authoritative matrix of how each supported host surface teaches the governance-injection contract for spec-kitty dispatch, with per-surface parity status.
doc_status: active
updated: '2026-06-15'
type: explanation
audience: docs/context/audience/internal/system-architect.md
---
# Host-Surface Parity Matrix

This is Spec Kitty's authoritative record of how each supported host surface teaches hosts about the governance-injection contract for `spec-kitty dispatch "<request>"` and `spec-kitty profile-invocation complete`.

**Keeping this matrix fresh**: any new host integration MUST add a row here; any change to how a host surface teaches the dispatch loop MUST update the corresponding row. The coverage test at `tests/specify_cli/docs/test_host_surface_inventory.py` enforces that every surface from `src/specify_cli/upgrade/migrations/m_0_9_1_complete_lane_migration.py::AGENT_DIRS` has exactly one row.

**Schema and parity rubric**: see [kitty-specs/phase-4-closeout-host-surfaces-and-trail-01KPWA5X/contracts/host-surface-inventory.md](../../kitty-specs/phase-4-closeout-host-surfaces-and-trail-01KPWA5X/contracts/host-surface-inventory.md).

**Canonical skill packs referenced by `guidance_style=pointer` rows**:
- [`src/charter/offering/skills/spec-kitty/SKILL.md`](../../src/charter/offering/skills/spec-kitty/SKILL.md) — Codex CLI, Vibe, Pi, Letta Code source skill; installed as `.agents/skills/spec-kitty/SKILL.md` where the host consumes agent skills. <!-- tool-surface: ignore -->
- [`src/charter/offering/skills/spec-kitty-runtime-next/SKILL.md`](../../src/charter/offering/skills/spec-kitty-runtime-next/SKILL.md) — Claude Code.

---

| surface_key | directory | kind | has_dispatch_guidance | has_governance_injection | has_completion_guidance | guidance_style | parity_status | notes |
|-------------|-----------|------|---------------------|--------------------------|-------------------------|----------------|---------------|-------|
| claude | .claude/commands/ | slash_command | yes | yes | yes | inline | at_parity | Priority slice 3.2.0a5 shipped standalone-invocation guidance via `src/charter/offering/skills/spec-kitty-runtime-next/SKILL.md` ("Standalone Invocations (Outside Missions)" section), which covers dispatch, governance_context_text injection, and profile-invocation complete. Distributed to Claude Code hosts via doctrine skill distribution — not via a file in .claude/commands/. |
| copilot | .github/prompts/ | slash_command | yes | yes | yes | pointer | at_parity | Pointer at `.github/prompts/spec-kitty-standalone.md` redirects to canonical `src/charter/offering/skills/spec-kitty/SKILL.md`. Shipped by WP04 (T016). |
| gemini | .gemini/commands/ | slash_command | yes | yes | yes | pointer | at_parity | Pointer at `.gemini/commands/spec-kitty-standalone.md` redirects to canonical `src/charter/offering/skills/spec-kitty/SKILL.md`. Shipped by WP04 (T016). |
| llxprt | .llxprt/commands/ | slash_command | yes | yes | yes | pointer | at_parity | LLxprt Code is a fork of Gemini CLI and loads the same TOML custom-command schema, so `.llxprt/commands/` carries the identical canonical command set rendered for `gemini`. Pointer at `.llxprt/commands/spec-kitty-standalone.md` redirects to canonical `src/charter/offering/skills/spec-kitty/SKILL.md`. |
| cursor | .cursor/commands/ | slash_command | yes | yes | yes | pointer | at_parity | Pointer at `.cursor/commands/spec-kitty-standalone.md` redirects to canonical `src/charter/offering/skills/spec-kitty/SKILL.md`. Shipped by WP04 (T016). |
| qwen | .qwen/commands/ | slash_command | yes | yes | yes | pointer | at_parity | Pointer at `.qwen/commands/spec-kitty-standalone.md` redirects to canonical `src/charter/offering/skills/spec-kitty/SKILL.md`. Shipped by WP04 (T016). |
| opencode | .opencode/command/ | slash_command | yes | yes | yes | pointer | at_parity | Pointer at `.opencode/command/spec-kitty-standalone.md` redirects to canonical `src/charter/offering/skills/spec-kitty/SKILL.md`. Shipped by WP04 (T017). |
| windsurf | .windsurf/workflows/ | slash_command | yes | yes | yes | pointer | at_parity | Pointer at `.windsurf/workflows/spec-kitty-standalone.md` redirects to canonical `src/charter/offering/skills/spec-kitty/SKILL.md`. Shipped by WP04 (T017). |
| kilocode | .kilocode/workflows/ | slash_command | yes | yes | yes | pointer | at_parity | Pointer at `.kilocode/workflows/spec-kitty-standalone.md` redirects to canonical `src/charter/offering/skills/spec-kitty/SKILL.md`. Shipped by WP04 (T017). |
| auggie | .augment/commands/ | slash_command | yes | yes | yes | pointer | at_parity | Pointer at `.augment/commands/spec-kitty-standalone.md` redirects to canonical `src/charter/offering/skills/spec-kitty/SKILL.md`. Shipped by WP04 (T018). |
| q | .amazonq/prompts/ | slash_command | yes | yes | yes | pointer | at_parity | Pointer at `.amazonq/prompts/spec-kitty-standalone.md` redirects to canonical `src/charter/offering/skills/spec-kitty/SKILL.md`. Shipped by WP04 (T018). |
| kiro | .kiro/prompts/ | slash_command | yes | yes | yes | pointer | at_parity | Pointer at `.kiro/prompts/spec-kitty-standalone.md` redirects to canonical `src/charter/offering/skills/spec-kitty/SKILL.md`. Shipped by WP04 (T018). |
| agent | .agent/workflows/ | slash_command | yes | yes | yes | pointer | at_parity | Pointer at `.agent/workflows/spec-kitty-standalone.md` redirects to canonical `src/charter/offering/skills/spec-kitty/SKILL.md`. Shipped by WP04 (T018). |
| codex | .agents/skills/ | agent_skill | yes | yes | yes | inline | at_parity | Priority slice 3.2.0a5 shipped the `src/charter/offering/skills/spec-kitty/SKILL.md` source skill to `.agents/skills/spec-kitty/SKILL.md` with all parity sections: "Discover profiles", "Open a governed invocation", "Governance context injection", and "Close the Op". Codex CLI reads the `.agents/skills/` tree directly. <!-- tool-surface: ignore --> |
| vibe | .agents/skills/ | agent_skill | yes | yes | yes | inline | partial | The canonical source skill `src/charter/offering/skills/spec-kitty/SKILL.md` is at parity and installs to `.agents/skills/spec-kitty/SKILL.md`. However, `.vibe/config.toml` is absent from this project — Vibe cannot load the skill pack without a `skill_paths` entry pointing at `.agents/skills/`. WP04 owned_files did not include `.vibe/config.toml`; the config.toml was not shipped. Remaining gap: add `.vibe/config.toml` with `skill_paths = [".agents/skills"]` to wire up Vibe's access to the existing skill pack. <!-- tool-surface: ignore --> |
| pi | .agents/skills/ | agent_skill | yes | yes | yes | inline | at_parity | Pi discovers project `.agents/skills/` directly, so the canonical Spec Kitty command-skill packages provide the same governance guidance used by Codex. Manifest at `.kittify/command-skills-manifest.json` records installed packages with agents including `pi`. <!-- tool-surface: ignore --> |
| letta | .agents/skills/ | agent_skill | yes | yes | yes | inline | at_parity | Letta Code prefers project `.agents/skills/`, so the canonical Spec Kitty command-skill packages provide the same governance guidance used by Codex. Manifest at `.kittify/command-skills-manifest.json` records installed packages with agents including `letta`. <!-- tool-surface: ignore --> |
