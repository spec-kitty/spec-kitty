---
title: 3.2 Harness Research Method
description: Defines a repeatable, evidence-driven procedure for classifying the AI coding harnesses (agents) Spec Kitty supports, naming the sources of authority used.
doc_status: deprecated
updated: '2026-08-12'
---

> ⚠ **Retired 2026-08-12 (`doc_status: deprecated`).** Working note for the 3.2 documentation mission `spec-kitty-3-2-docs-01KS4KSZ` (14/14 WPs done 2026-05-21); the docs are published (now 3.2.6). Content preserved as an audit-trail record.

# 3.2 Harness Research Method

**Purpose:** Define a repeatable, evidence-driven procedure for classifying the AI coding harnesses (a.k.a. "agents") that Spec Kitty supports. The output of this method is the support matrix at [`docs/api/supported-harnesses.md`](../../../api/supported-harnesses.md).

**Sources of authority:**
- [`CLAUDE.md`](../../../../CLAUDE.md) §"Supported AI Agents" — canonical list of installed surfaces.
- `kitty-specs/spec-kitty-3-2-docs-01KS4KSZ/start-here.md` §"Supported Harness Research" plus the current CLI agent registry — 17 candidate subjects.
- [`data-model.md`](../../../../kitty-specs/spec-kitty-3-2-docs-01KS4KSZ/data-model.md) §"HarnessEntry" — schema each row must satisfy.

**Access date for all citations in this revision:** 2026-05-21.

---

## 1. Subject list — 17 candidate harnesses

| # | Harness | Key |
|---|---------|-----|
| 1 | Claude Code | `claude` |
| 2 | Codex CLI | `codex` |
| 3 | OpenCode | `opencode` |
| 4 | Cursor | `cursor` |
| 5 | Google Gemini CLI | `gemini` |
| 6 | Pi TUI | `pi` |
| 7 | Qwen Code | `qwen` |
| 8 | Amazon Q CLI | `q` |
| 9 | GitHub Copilot | `copilot` |
| 10 | Augment Code (Auggie) | `augment` |
| 11 | Roo Cline | `roo` |
| 12 | Kilo Code | `kilocode` |
| 13 | Kiro | `kiro` |
| 14 | Windsurf | `windsurf` |
| 15 | Mistral Vibe | `vibe` |
| 16 | Letta Code | `letta` |
| 17 | Google Antigravity | `antigravity` |

The set is the union of (a) directories present in the repo, (b) entries in `CLAUDE.md`'s command-surface and command-skill tables, (c) entries in `src/specify_cli/core/config.py`'s `AI_CHOICES`, and (d) entries in `start-here.md` §"Supported Harness Research" (per R-003).

---

## 2. Inventory step — on-disk evidence

For each candidate harness, the research process records:

1. **Installed surface directory** — the conventional path Spec Kitty deploys command/skill/prompt files to (e.g., `.claude/commands/`, `.agents/skills/spec-kitty.<command>/`, `.amazonq/prompts/`); legacy `.codex/` roots may still appear on older hosts.
2. **Presence check** — `ls -d <dir>` against the active host; record present/absent and file count.
3. **Cross-reference** — every present surface must match an entry in `CLAUDE.md` §"Supported AI Agents".

### 2.1 Procedure

Run from repo root (or this lane worktree):

```bash
# .codex/ is probed as a legacy root only — current Codex support lives in .agents/skills/
ls -d .claude/ .codex/ .opencode/ .cursor/ .gemini/ .qwen/ .amazonq/ \
       .augment/ .kiro/ .kilocode/ .roo/ .windsurf/ .agent/ .agents/ \
       .vibe/ .github/prompts 2>/dev/null

for d in .claude/commands .codex .opencode/command .cursor/commands \
         .gemini/commands .qwen/commands .amazonq/prompts .augment/commands \
         .kiro/prompts .kilocode/workflows .roo/commands .windsurf/workflows \
         .agent/workflows .agents/skills .github/prompts; do
  echo "=== $d ==="
  ls "$d" 2>/dev/null | head -10
done
```

### 2.2 Findings (snapshot 2026-05-21)

| Harness | Expected directory | On-disk? | Files observed |
|---------|--------------------|----------|----------------|
| Claude Code | `.claude/commands/` | partial (dir exists, no `commands/` subdir in this lane) | — |
| Codex CLI | `.agents/skills/spec-kitty.*` | yes (skills) | `.agents/skills/spec-kitty` (skill package directory, not the SKILL.md file) <!-- tool-surface: ignore --> |
| OpenCode | `.opencode/command/` | yes | `spec-kitty-standalone.md` |
| Cursor | `.cursor/commands/` | yes | `spec-kitty-standalone.md` |
| Gemini CLI | `.gemini/commands/` | yes | `spec-kitty-standalone.md` |
| Pi TUI | `.agents/skills/spec-kitty.*` | yes (skills) | shared command-skill packages |
| Qwen Code | `.qwen/commands/` | yes | `spec-kitty-standalone.md` |
| Amazon Q | `.amazonq/prompts/` | yes | `spec-kitty-standalone.md` |
| GitHub Copilot | `.github/prompts/` | yes | `spec-kitty-standalone.md` |
| Augment Code | `.augment/commands/` | yes | `spec-kitty-standalone.md` |
| Roo Cline | `.roo/commands/` | yes | `spec-kitty-standalone.md` |
| Kilo Code | `.kilocode/workflows/` | yes | `spec-kitty-standalone.md` |
| Kiro | `.kiro/prompts/` | yes | `spec-kitty-standalone.md` |
| Windsurf | `.windsurf/workflows/` | yes | `spec-kitty-standalone.md` |
| Google Antigravity | `.agent/workflows/` | yes | `spec-kitty-standalone.md` |
| Vibe | `.agents/skills/` via `.vibe/config.toml` | yes (shared with Codex) | shares `.agents/skills/spec-kitty` (skill package directory, not the SKILL.md file) <!-- tool-surface: ignore --> |
| Letta Code | `.agents/skills/spec-kitty.*` | yes (skills) | shared command-skill packages |

**Notes:**
- `spec-kitty-standalone.md` is the lane-bootstrap surface; the full `/spec-kitty.*` command set lives at the source under `src/specify_cli/missions/*/command-templates/` and is materialized by `spec-kitty agent config sync` (see `CLAUDE.md` §"Adding/Removing Agents").
- `.agents/skills/spec-kitty/` is the agent skills package directory (not the SKILL.md file) shared between Codex CLI, Mistral Vibe, Pi, and Letta Code (per `CLAUDE.md` §`Agent Skills Agents`). <!-- tool-surface: ignore -->
- Current Codex CLI support uses the shared agent skills packages under `.agents/skills/spec-kitty.<command>/SKILL.md`. Legacy `.codex/` roots were not observed in this lane; they may still exist on hosts initialized by older CLI versions and are documented as legacy-only (see `docs/api/environment-variables.md` §CODEX_HOME).
- Google Antigravity (`.agent/workflows/`) is present in the current CLI agent registry and is included in the matrix.

---

## 3. Canonical mechanism step

Each row in the support matrix records exactly one `mechanism` value from the `HarnessMechanism` enum in `data-model.md`:

| Mechanism | Meaning | Examples |
|-----------|---------|----------|
| `slash_command` | The harness exposes user-typed `/...` commands. | Claude Code `.claude/commands/`, Cursor `.cursor/commands/`. |
| `prompt` | The harness reads prompt files at runtime. | Amazon Q `.amazonq/prompts/`, Kiro `.kiro/prompts/`, GitHub Copilot `.github/prompts/`. |
| `workflow` | The harness drives multi-step workflows defined by YAML/Markdown. | Windsurf `.windsurf/workflows/`, Kilo Code `.kilocode/workflows/`, Google Antigravity `.agent/workflows/`. |
| `skill` | The harness loads agent skills packages with `SKILL.md`. | Codex CLI, Mistral Vibe, Pi, Letta Code (via `.agents/skills/`). |
| `command_file` | The harness reads command files outside a `commands/` directory. | reserved; no current harness uses this mode. |
| `config` | The harness needs an additional config-file edit before commands are visible. | Vibe (`.vibe/config.toml` `skill_paths`). |

A harness may have a primary mechanism plus a secondary `config` step (e.g., Vibe = `skill` + `config`); the matrix records the primary mechanism and the secondary is noted in the row's `notes`.

---

## 4. Citation step

Every harness row at tier ≥ `supported` requires at least one current public-doc URL. Citations are recorded with the access date.

### 4.1 Canonical citation roots (access date 2026-05-21)

| Harness | Citation URL |
|---------|--------------|
| Claude Code | https://docs.claude.com/en/docs/claude-code/overview |
| Codex CLI | https://github.com/openai/codex |
| OpenCode | https://opencode.ai/docs |
| Cursor | https://cursor.com/docs |
| Gemini CLI | https://github.com/google-gemini/gemini-cli |
| Pi TUI | https://pi.dev/docs/latest/skills |
| Qwen Code | https://github.com/QwenLM/qwen-code |
| Amazon Q CLI | https://docs.aws.amazon.com/amazonq/latest/qdeveloper-ug/ |
| GitHub Copilot | https://docs.github.com/en/copilot/customizing-copilot/adding-custom-instructions-for-github-copilot |
| Augment Code (Auggie) | https://docs.augmentcode.com/auggie/overview |
| Roo Cline | https://docs.roocode.com/ |
| Kilo Code | https://kilocode.ai/docs |
| Kiro | https://kiro.dev/docs |
| Windsurf | https://docs.windsurf.com/windsurf/cascade/workflows |
| Google Antigravity | https://antigravity.im/documentation |
| Mistral Vibe | https://docs.mistral.ai/mistral-vibe/terminal/quickstart |
| Letta Code | https://docs.letta.com/letta-code/skills |

### 4.2 Citation rule

- Prefer the harness's primary documentation site over blog posts.
- Record the access date alongside each citation. The freshness audit (WP13) re-validates each link.
- A harness with no current public doc is classified at `partial` or lower until evidence lands.

---

## 5. Classification criteria — the five tiers

| Tier | Criteria |
|------|----------|
| `first_class` | (1) Installed surface present on disk; (2) primary command mechanism is the harness's canonical UX (slash command or skill); (3) at least one external doc citation ≤ 12 months old; (4) `spec-kitty agent config sync` produces a complete `/spec-kitty.*` set; (5) covered by integration tests in `src/specify_cli/`. |
| `supported` | (1) Installed surface present on disk; (2) covered by the standard installer; (3) at least one external doc citation ≤ 12 months old. May lack first-class integration tests or have a degraded command surface (e.g., requires a config edit). |
| `partial` | (1) Installer touches the host but coverage is incomplete (e.g., only `spec-kitty-standalone.md`, no `/spec-kitty.*` set); OR (2) no current external citation could be located. |
| `experimental` | (1) Coverage is intentionally provisional; (2) shipping behavior may break without notice. Vibe sits here because it shares its skill installation with Codex through a config file. |
| `archived` | (1) The harness is no longer covered by the installer; OR (2) the upstream project has been deprecated; OR (3) coverage was removed and lives in `docs/migrations/` only. |

### 5.1 Validation rules (mirror `data-model.md`)

- `support_tier in {first_class, supported}` ⇒ `external_doc_citations` is non-empty.
- `support_tier == archived` ⇒ `page_path` is under `docs/migrations/` or absent.
- `key` is unique across the matrix.
- Every row's `repo_directory` matches the directory in `CLAUDE.md` or is explicitly documented as a partial-tier exception.

---

## 6. Promotion rule

A harness moves up tiers only when **new evidence** lands; tier moves are recorded in the matrix's row history (notes column) and in CHANGELOG.

### 6.1 `partial` → `supported`

Promote when **all** of the following hold:

1. The installer (e.g., `spec-kitty agent config add <key>`) produces a complete `/spec-kitty.*` command set on disk.
2. A current external-doc citation (≤ 12 months old) is added to the matrix row.
3. A smoke test against a real session has been recorded (manual evidence is acceptable; document in the row's `notes`).

### 6.2 `supported` → `first_class`

Promote when **all** of the following hold:

1. Integration tests in `src/specify_cli/` exercise the harness's installed surface end-to-end.
2. The harness's command mechanism is the host's canonical UX (slash command or Agent Skill — not a prompt-file workaround).
3. The per-harness "how-to" page under `docs/guides/harnesses/<key>.md` exists and is non-stub.
4. CHANGELOG entry records the promotion.

### 6.3 Demotion

A harness demotes when:

- An external citation cannot be re-verified for two consecutive freshness audits (move to `partial`).
- The upstream project is deprecated or abandoned (move to `archived`).
- The installer no longer produces a valid command surface for the harness (move to `partial` or `archived` depending on intent).

---

## 7. Per-harness research dossier — 2026-05-21

The matrix in [`docs/api/supported-harnesses.md`](../../../api/supported-harnesses.md) is the canonical output. The research notes that fed each row are summarized below.

| Key | Display name | Mechanism | Tier | Citation | Notes |
|-----|--------------|-----------|------|----------|-------|
| `claude` | Claude Code | slash_command | first_class | https://docs.claude.com/en/docs/claude-code/overview | Reference harness; integration tests live in `src/specify_cli/`. |
| `codex` | Codex CLI | skill | first_class | https://github.com/openai/codex | Heaviest agent skills integration; `.agents/skills/spec-kitty.*/SKILL.md` is the authoritative skill tree. |
| `opencode` | OpenCode | slash_command | supported | https://opencode.ai/docs | `.opencode/command/` installed. |
| `cursor` | Cursor | slash_command | supported | https://cursor.com/docs | `.cursor/commands/` installed. |
| `gemini` | Google Gemini CLI | slash_command | supported | https://github.com/google-gemini/gemini-cli | `.gemini/commands/` installed. |
| `qwen` | Qwen Code | slash_command | supported | https://github.com/QwenLM/qwen-code | `.qwen/commands/` installed. |
| `q` | Amazon Q CLI | prompt | supported | https://docs.aws.amazon.com/amazonq/latest/qdeveloper-ug/ | `.amazonq/prompts/`; legacy alongside Kiro rebrand per `CLAUDE.md`. |
| `copilot` | GitHub Copilot | prompt | supported | https://docs.github.com/en/copilot/customizing-copilot/adding-custom-instructions-for-github-copilot | `.github/prompts/` installed. |
| `augment` | Augment Code (Auggie) | slash_command | supported | https://docs.augmentcode.com/auggie/overview | `.augment/commands/` installed. |
| `roo` | Roo Cline | slash_command | supported | https://docs.roocode.com/ | `.roo/commands/` installed. |
| `kilocode` | Kilo Code | workflow | supported | https://kilocode.ai/docs | `.kilocode/workflows/` installed. |
| `windsurf` | Windsurf | workflow | supported | https://docs.windsurf.com/windsurf/cascade/workflows | `.windsurf/workflows/` installed. |
| `kiro` | Kiro | prompt | partial | https://kiro.dev/docs | `.kiro/prompts/` installed but coverage is the standalone bootstrap only; promote once full `/spec-kitty.*` surface is verified. |
| `antigravity` | Google Antigravity | workflow | partial | https://antigravity.im/documentation | `.agent/workflows/` installed; keep partial until full command-set smoke evidence is recorded. |
| `pi` | Pi TUI | skill | partial | https://pi.dev/docs/latest/skills | `.agents/skills/spec-kitty.*/SKILL.md` installed; Pi docs confirm project `.agents/skills/` discovery and `/skill:<name>` invocation. |
| `vibe` | Mistral Vibe | skill | experimental | https://docs.mistral.ai/mistral-vibe/terminal/quickstart | Requires `.vibe/config.toml` `skill_paths` edit; depends on the shared command-skill installation. |
| `letta` | Letta Code | skill | partial | https://docs.letta.com/letta-code/skills | `.agents/skills/spec-kitty.*/SKILL.md` installed; keep partial until full command-set smoke evidence is recorded. |

---

## 8. Maintenance

- Re-run the inventory step (§2) on every release.
- Re-run the citation step (§4) on every release as part of the freshness audit (WP13).
- Update tiers per the promotion rule (§6); record demotions in CHANGELOG.
- The matrix (`docs/api/supported-harnesses.md`) is the canonical published artifact; this research method document is the procedural source of truth that explains how the matrix is built.
