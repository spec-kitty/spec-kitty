---
title: Supported Harnesses
description: Support matrix for Spec Kitty 3.2 AI coding harnesses, including first-class, supported, experimental, and unsupported hosts.
doc_status: active
updated: '2026-07-20'
---
# Supported Harnesses

This page is the canonical 5-tier support matrix for AI coding harnesses ("agents") that Spec Kitty integrates with. Each row conforms to the `HarnessEntry` schema in `kitty-specs/spec-kitty-3-2-docs-01KS4KSZ/data-model.md`. The research procedure that backs each classification lives in `docs/archive/plans/3-2-doc-publication/3-2-harness-research-method.md`.

**Access date for citations:** 2026-06-03.

---

## Tier legend

| Tier | One-line definition |
|------|---------------------|
| **first_class** | Installed by default; canonical UX (slash command or Agent Skill); integration-tested; current external doc citation. |
| **supported** | Installed by the standard installer; current external doc citation; may lack first-class integration tests or have a degraded mechanism. |
| **partial** | Installer touches the host but coverage is incomplete, or no current external citation could be located. |
| **experimental** | Provisional coverage that may break without notice; typically depends on another harness's installation. |
| **archived** | No longer covered by the installer, or the upstream project is deprecated; coverage (if any) lives in `docs/migrations/`. |

Full tier criteria and promotion rules are maintained in `docs/archive/plans/3-2-doc-publication/3-2-harness-research-method.md` §5 and §6.

---

## Support matrix

| Harness | Key | Installed surface | Mechanism | Tier | Citation (accessed 2026-06-03) | Notes |
|---------|-----|-------------------|-----------|------|--------------------------------|-------|
| Claude Code | `claude` | `.claude/commands/` | slash_command | **first_class** | https://docs.claude.com/en/docs/claude-code/overview | Reference harness; integration-tested in `src/specify_cli/`. |
| Codex CLI | `codex` | `.agents/skills/spec-kitty.*/SKILL.md` | skill | **first_class** | https://github.com/openai/codex | Heaviest agent skills integration; canonical skill tree at `.agents/skills/`. |
| OpenCode | `opencode` | `.opencode/command/` | slash_command | **supported** | https://opencode.ai/docs | `/spec-kitty.*` command set installed via standard installer. |
| Cursor | `cursor` | `.cursor/commands/` | slash_command | **supported** | https://cursor.com/docs | `/spec-kitty.*` command set installed via standard installer. |
| Google Gemini CLI | `gemini` | `.gemini/commands/` | slash_command | **supported** | https://github.com/google-gemini/gemini-cli | `/spec-kitty.*` command set installed via standard installer. |
| Qwen Code | `qwen` | `.qwen/commands/` | slash_command | **supported** | https://github.com/QwenLM/qwen-code | `/spec-kitty.*` command set installed via standard installer. |
| Amazon Q CLI | `q` | `.amazonq/prompts/` | prompt | **supported** | https://docs.aws.amazon.com/amazonq/latest/qdeveloper-ug/ | Retained as legacy alongside Kiro rebrand per `CLAUDE.md`. |
| GitHub Copilot | `copilot` | `.github/prompts/` | prompt | **supported** | https://docs.github.com/en/copilot/customizing-copilot/adding-custom-instructions-for-github-copilot | Prompt-file mechanism; `/spec-kitty.*` set installed. |
| Augment Code (Auggie) | `auggie` | `.augment/commands/` | slash_command | **supported** | https://docs.augmentcode.com/auggie/overview | `/spec-kitty.*` command set installed via standard installer. |
| Roo Cline | `roo` | `.roo/commands/` (existing projects only) | slash_command | **deprecated** | https://docs.roocode.com/ | Roo Code shut down on 2026-05-15. `spec-kitty init --ai roo` is rejected; existing `.roo/` dirs are preserved and a deprecation notice is shown on `spec-kitty upgrade`. |
| Kilo Code | `kilocode` | `.kilocode/workflows/` | workflow | **supported** | https://kilocode.ai/docs | Workflow mechanism; `/spec-kitty.*` set installed. |
| Windsurf | `windsurf` | `.windsurf/workflows/` | workflow | **supported** | https://docs.windsurf.com/windsurf/cascade/workflows | Workflow mechanism; `/spec-kitty.*` set installed. |
| Kiro | `kiro` | `.kiro/prompts/` | prompt | **partial** | https://kiro.dev/docs | Prompt-file surface only for Spec Kitty 3.3 plugin-install scoping; not a plugin/Powers bundle candidate until upstream exposes and verifies a package primitive. |
| Google Antigravity | `antigravity` | `.agent/workflows/` | workflow | **partial** | https://www.antigravity.google/docs/rules-workflows | Local live CLI verification was unavailable on 2026-06-03; installed surface remains documented as partial until current Antigravity CLI workflow paths are smoke-tested. |
| Pi TUI | `pi` | `.agents/skills/spec-kitty.*/SKILL.md` | skill | **partial** | https://pi.dev/docs/latest/skills | Installer-supported command-skill packages; keep partial until a real-session smoke test is recorded. |
| Mistral Vibe | `vibe` | `.agents/skills/` via `.vibe/config.toml` `skill_paths` | skill | **experimental** | https://docs.mistral.ai/mistral-vibe/terminal/quickstart | Uses the shared `.agents/skills/spec-kitty.*` packages plus a `.vibe/config.toml` `skill_paths` entry. Behaviour may change with Vibe upstream. |
| Letta Code | `letta` | `.agents/skills/spec-kitty.*/SKILL.md` | skill | **partial** | https://docs.letta.com/letta-code/skills | Installer-supported command-skill packages; keep partial until a real-session smoke test is recorded. |

---

## Cross-reference quick view

| Tier | Count | Members |
|------|-------|---------|
| first_class | 2 | Claude Code, Codex CLI |
| supported | 9 | OpenCode, Cursor, Gemini CLI, Qwen Code, Amazon Q CLI, GitHub Copilot, Augment Code, Kilo Code, Windsurf |
| partial | 4 | Kiro, Google Antigravity, Pi TUI, Letta Code |
| experimental | 1 | Mistral Vibe |
| deprecated | 1 | Roo Cline (shut down 2026-05-15) |
| archived | 0 | |
| **Total** | **17** | |

---

## Promotion path

A harness moves up tiers only when new evidence lands. See `docs/archive/plans/3-2-doc-publication/3-2-harness-research-method.md` §6 for the full rule. Summary:

1. **`partial` → `supported`** when (a) the installer produces a full `/spec-kitty.*` set, (b) a current external citation is recorded, and (c) at least one smoke test has been documented.
2. **`supported` → `first_class`** when (a) integration tests exercise the harness end-to-end, (b) the mechanism is the harness's canonical UX, (c) the per-harness page under `docs/guides/harnesses/<key>.md` is non-stub, and (d) the promotion is logged in CHANGELOG.
3. **Demotion** happens when citations cannot be re-verified across two freshness audits, the upstream is deprecated, or the installer ceases to produce a valid surface.

Tier moves are recorded in this matrix's row notes and the project CHANGELOG.

---

## Maintenance

- The inventory step is re-run on every release; the citation step is re-run on every release as part of the freshness audit (WP13).
- This matrix is the published artifact; the procedure that backs it is maintained at `docs/archive/plans/3-2-doc-publication/3-2-harness-research-method.md`.
- Per-harness "how-to" pages live at `docs/guides/harnesses/<key>.md` and are promoted under the plan's matrix-first default (decision `01KS4KTS4V300M9MMTS1AJEGXY`).
