---
title: Agent Plan Artifacts Reference
description: Reference for agent plan artifacts generated during missions. Learn the role of spec.md, plan.md, tasks.md, and checklists/requirements.md.
doc_status: active
updated: '2026-08-13T00:00:00Z'
kind: Reference
---
# Agent Plan Artifacts Reference

This document catalogs whether each supported harness has a plan mode, where it
saves plan files to disk, and the confidence level of that information.

Used by `spec-kitty intake --auto` via `src/specify_cli/intake_sources.py` to
scan for pre-existing agent-generated plans that can serve as intake context.

Last updated: 2026-08-13

---

## Harness Sections

### Claude Code (`claude`)

| Field | Value |
|-------|-------|
| Plan mode | Yes |
| Artifact path(s) | `~/.claude/plans/<random-name>.md` (default); configurable via `plansDirectory` |
| Filename pattern | `*.md` (auto-generated adjective-noun names, e.g. `graceful-riding-pillow.md`) |
| User-configurable | Yes — set `plansDirectory` in `~/.claude/settings.json` (user-level) or `.claude/settings.json` (project-level); relative paths resolve from workspace root |
| Confidence | Verified-empirical |
| Source | Empirical test on this machine (claude 2.1.114, 2026-04-20); confirmed by [ClaudeLog FAQ](https://claudelog.com/faqs/what-is-plans-directory-in-claude-code/) and [GitHub issue #14866](https://github.com/anthropics/claude-code/issues/14866) |

**Notes**: Default location is `~/.claude/plans/` (global, not project-scoped). There are multiple open
feature requests to change the default to a project-local path; the behavior may change in future
versions. Project-level `plansDirectory` in `.claude/settings.json` is the recommended way to store
plans alongside source. Plans are auto-named; there is no deterministic filename without configuring a
fixed directory. The `plansDirectory` setting accepts both absolute and workspace-relative paths.
Known bug (issue #14186 / #19537): project-level `plansDirectory` is sometimes ignored in favour of
the global default.

---

### GitHub Copilot (`copilot`)

| Field | Value |
|-------|-------|
| Plan mode | Yes (public preview in VS Code, JetBrains, Eclipse, Xcode) |
| Artifact path(s) | `—` (no stable on-disk plan file; plans are conversational or session-local) |
| Filename pattern | `—` |
| User-configurable | No stable path exposed |
| Confidence | Inferred |
| Source | [GitHub Changelog 2025-11-18](https://github.blog/changelog/2025-11-18-plan-mode-in-github-copilot-now-in-public-preview-in-jetbrains-eclipse-and-xcode/); [GitHub Docs — Planning a project](https://docs.github.com/en/copilot/tutorials/plan-a-project) |

**Notes**: Copilot's plan mode (Copilot Workspace) generates structured implementation plans, but
these are primarily surfaced inside the IDE/web UI, not persisted to a deterministic project-level
path by default. Session artefacts may appear under `~/.copilot/session-state/<session-id>/` but
this path is session-keyed and not stable for scanning. Custom instructions live in
`.github/copilot-instructions.md` but that is instructions, not a plan output. No officially
documented project-level plan file path was found as of 2026-04-20.

---

### Google Gemini CLI (`gemini`)

| Field | Value |
|-------|-------|
| Plan mode | Yes (`--approval-mode=plan`, `/plan` command, or `Shift+Tab`) |
| Artifact path(s) | `~/.gemini/tmp/<project>/<session-id>/plans/` (default); configurable to `.gemini/plans/` within project root |
| Filename pattern | `*.md` |
| User-configurable | Yes — set `general.plan.directory` in `.gemini/settings.json`; must be inside project root |
| Confidence | Verified-docs |
| Source | [Gemini CLI plan-mode docs](https://geminicli.com/docs/cli/plan-mode/); [GitHub source gemini-cli/docs/cli/plan-mode.md](https://github.com/google-gemini/gemini-cli/blob/main/docs/cli/plan-mode.md) |

**Notes**: Default path is a managed temp directory keyed by project and session; files are
automatically cleaned up after 30 days. If a custom `general.plan.directory` is set (e.g.
`.gemini/plans`), files are **not** automatically cleaned up. The custom directory must stay within
the project root — absolute paths or paths escaping the workspace are rejected. Useful configuration
for scan purposes:
```json
{ "general": { "plan": { "directory": ".gemini/plans" } } }
```

---

### Cursor (`cursor`)

| Field | Value |
|-------|-------|
| Plan mode | Yes (`Shift+Tab` to activate) |
| Artifact path(s) | `~/.cursor/plans/` (default, global); `.cursor/plans/` (project-local, requires "Save to Workspace") |
| Filename pattern | `*.md` |
| User-configurable | Limited — no `plansDirectory` setting; user can manually click "Save to Workspace" to move a plan to `.cursor/plans/` in the project |
| Confidence | Verified-docs |
| Source | [Cursor Plan Mode docs](https://cursor.com/docs/agent/plan-mode); [Cursor community forum](https://forum.cursor.com/t/plan-mode-files-not-saving-in-cursor-plans/137539); [Cursor blog — Introducing Plan Mode](https://cursor.com/blog/plan-mode) |

**Notes**: Plans are ephemeral by default and live in `~/.cursor/plans/` (global). To commit them to
the repo, the user must explicitly click "Save to Workspace", which creates `.cursor/plans/<name>.md`
in the project. There is no programmatic way to force a project-local save. Multiple community
requests for a configurable `plansDirectory` are open as of 2026-04-20.

---

### Qwen Code (`qwen`)

| Field | Value |
|-------|-------|
| Plan mode | Yes (read-only approval mode; `--approval-mode plan` or `Shift+Tab`) |
| Artifact path(s) | `~/.qwen/todos/<session-id>.json` (internal todo list, not a readable plan file) |
| Filename pattern | `—` (no stable Markdown plan file; todo state is JSON) |
| User-configurable | No |
| Confidence | Verified-docs |
| Source | [Qwen Code TodoWriteTool docs](https://qwenlm.github.io/qwen-code-docs/en/developers/tools/todo-write/); [GitHub qwen-code/docs/developers/tools/todo-write.md](https://github.com/QwenLM/qwen-code/blob/main/docs/developers/tools/todo-write.md) |

**Notes**: Qwen Code's plan mode is read-only like Gemini CLI's. It uses a `todo_write` tool that
persists task lists to `~/.qwen/todos/` as session-specific JSON files — not human-authored Markdown
plan documents. There is no confirmed on-disk Markdown artifact in a deterministic project-level path.
The `.qwen/` project directory is used for configuration, not plan output.

---

### OpenCode (`opencode`)

| Field | Value |
|-------|-------|
| Plan mode | Yes (built-in `plan` mode; toggle with `Tab`) |
| Artifact path(s) | `.opencode/plans/<timestamp>-<slug>.md` |
| Filename pattern | `[0-9]*-*.md` |
| User-configurable | No (path is hard-coded to `.opencode/plans/` within the project) |
| Confidence | Verified-docs |
| Source | [OpenCode Modes docs](https://opencode.ai/docs/modes/) — "edit tool cannot modify existing files, except for files located at `.opencode/plans/*.md`" |

**Notes**: `.opencode/plans/` is the only directory writable in plan mode; all other file
modifications are blocked. Files are named `<unix-timestamp>-<url-slug>.md`. Global plans (not
scoped to a project) go to `~/.local/share/opencode/plans/` but that path is less useful for
project-scoped scanning.

---

### Windsurf (`windsurf`)

| Field | Value |
|-------|-------|
| Plan mode | Yes (Wave 10 Planning Mode; available in Cascade) |
| Artifact path(s) | `~/.windsurf/plans/` (default, global) |
| Filename pattern | `*.md` |
| User-configurable | No stable project-level path documented |
| Confidence | Verified-docs |
| Source | [Windsurf Cascade Modes docs](https://docs.windsurf.com/windsurf/cascade/modes) — "Plans are stored in your `~/.windsurf/plans` directory and are available in the @mentions menu."; [Wave 10 blog](https://windsurf.com/blog/windsurf-wave-10-planning-mode) |

**Notes**: Windsurf stores plans globally at `~/.windsurf/plans/`, not in a per-project directory.
The plans are referenced via `@mentions` for follow-up sessions. As of 2026-04-20, there is no
documented mechanism to override the storage location to a project-local directory. Plans are
Markdown files and are persistent (not auto-cleaned).

---

### Kilocode (`kilocode`)

| Field | Value |
|-------|-------|
| Plan mode | Yes (inherited from OpenCode codebase; `plan` mode) |
| Artifact path(s) | `.opencode/plans/<timestamp>-<slug>.md` (bug: plans currently save to `.opencode/` directory, not `.kilocode/`) |
| Filename pattern | `[0-9]*-*.md` |
| User-configurable | No |
| Confidence | Inferred |
| Source | [Kilocode GitHub issue #6370](https://github.com/Kilo-Org/kilocode/issues/6370) — "Plan files in ask mode are saved in a opencode directory"; [issue #6907](https://github.com/Kilo-Org/kilocode/issues/6907) — "In the planning mode cannot create a plan file in plans folder" |

**Notes**: Kilocode is forked from OpenCode and inherits its plan mode. However, a known bug
(reported February–March 2026) causes plan files to be written to `.opencode/plans/` instead of a
Kilocode-specific directory. The correct target path — `.kilocode/plans/` — is not yet reliably
used. Active bug; behaviour may change in future releases. Neither path is confirmed stable as of
2026-04-20.

---

### Augment Code (`auggie`)

| Field | Value |
|-------|-------|
| Plan mode | Yes (strict read-only; can activate mid-conversation) |
| Artifact path(s) | `~/.augment/plans/` |
| Filename pattern | `*.md` |
| User-configurable | No |
| Confidence | Inferred |
| Source | [Augment Code changelog](https://www.augmentcode.com/changelog) mentions plan mode improvements; search result snippets attribute `~/.augment/plans/` as the save location; not confirmed in official docs page |

**Notes**: The `~/.augment/plans/` path appears in secondary sources (changelog summaries, third-party
guides). The canonical Augment Code docs page does not explicitly document this path as of
2026-04-20. Classified as Inferred rather than Verified-docs. The path is global (not
project-scoped), limiting its usefulness for project-level scanning.

---

### Roo Cline (`roo`) — deprecated

> Roo Code shut down on 2026-05-15 and is no longer a supported harness
> (`spec-kitty init --ai roo` is rejected). The entry below is retained as a
> historical capability record only.

| Field | Value |
|-------|-------|
| Plan mode | Unclear |
| Artifact path(s) | `—` |
| Filename pattern | `—` |
| User-configurable | N/A |
| Confidence | Unknown |
| Source | [Roo Code docs — Using Modes](https://docs.roocode.com/basic-usage/using-modes); [Roo Code docs — Custom Modes](https://docs.roocode.com/features/custom-modes) |

**Notes**: Roo Code has built-in modes: Code, Architect, Ask, Debug. The "Architect" mode is the
closest to a plan mode — it restricts the agent to planning and analysis. However, no official
documentation confirms that Architect or any other mode saves a standalone Markdown plan file to a
deterministic on-disk path. The `.roo/` directory is used for rules and custom mode configs, not
plan outputs. A `customStoragePath` setting exists but has known bugs. No plan-file artifact path
could be verified as of 2026-04-20.

---

### Amazon Q / Kiro (`q` / `kiro`)

**Amazon Q Developer** and **Kiro** are treated together here because they share the `q`/`kiro`
harness keys in spec-kitty's agent model, though they are distinct products.

#### Amazon Q Developer

| Field | Value |
|-------|-------|
| Plan mode | Unclear |
| Artifact path(s) | `—` |
| Filename pattern | `—` |
| User-configurable | N/A |
| Confidence | Unknown |
| Source | [Amazon Q Developer docs](https://docs.aws.amazon.com/amazonq/latest/qdeveloper-ug/software-dev.html) |

**Notes**: Amazon Q Developer (CLI / IDE plugin) does not document a dedicated plan mode with
file-system plan output as of 2026-04-20. Workspace cache lives at `~/.aws/amazonq/cache/`. No
confirmed plan-file path.

#### Kiro

| Field | Value |
|-------|-------|
| Plan mode | Yes (spec-driven development — "Spec" mode) |
| Artifact path(s) | `.kiro/specs/<feature-name>/requirements.md`, `.kiro/specs/<feature-name>/design.md`, `.kiro/specs/<feature-name>/tasks.md` |
| Filename pattern | `requirements.md`, `design.md`, `tasks.md` (under `.kiro/specs/<slug>/`) |
| User-configurable | No (path is fixed; spec files are committed to the repo by design) |
| Confidence | Verified-docs |
| Source | [Kiro Specs docs](https://kiro.dev/docs/specs/) — "Specifications are stored under `.kiro/specs`"; [Kiro blog — spec-driven development](https://kiro.dev/blog/kiro-and-the-future-of-software-development/) |

**Notes**: Kiro's model differs from other harnesses. Rather than a single "plan file", Kiro
generates a structured three-file spec bundle under `.kiro/specs/<feature>/`. These files are
explicitly intended to be version-controlled alongside source code. The `feature-name` slug is
derived from the task description. Steering documents (comparable to rules/instructions) live in
`.kiro/steering/*.md`.

---

### Google Antigravity (`antigravity`)

| Field | Value |
|-------|-------|
| Plan mode | Yes (Planning mode; produces Implementation Plan and Task List artifacts) |
| Artifact path(s) | `—` (plan artifacts are surfaced in the IDE UI and knowledge base; no stable per-project Markdown file path documented) |
| Filename pattern | `—` |
| User-configurable | Unclear |
| Confidence | Inferred |
| Source | [Google Antigravity docs](https://antigravity.google/docs/implementation-plan); [Codelabs — autonomous pipelines](https://codelabs.developers.google.com/autonomous-ai-developer-pipelines-antigravity); [Antigravity tutorial](https://antigravity.codes/tutorial) |

**Notes**: Antigravity creates a `.gemini/antigravity/brain/` persistent knowledge base at the
project root where agents record architectural decisions. Planning mode produces an Implementation
Plan artifact and a Task List artifact, but these are primarily surfaced inside the IDE/agent panel,
not as simple project-root Markdown files. The `.agents/` directory is used for workflow/skill
configuration, not plan output. No deterministic file path for scanning was confirmed as of
2026-04-20.

---

### Mistral Vibe (`vibe`)

| Field | Value |
|-------|-------|
| Plan mode | Yes (built-in `plan` agent profile — read-only, auto-approves safe tools) |
| Artifact path(s) | `—` (no on-disk plan file output documented; plan stays conversational) |
| Filename pattern | `—` |
| User-configurable | N/A |
| Confidence | Inferred |
| Source | [Mistral Vibe docs — Agents & Skills](https://docs.mistral.ai/mistral-vibe/agents-skills); [Mistral Vibe GitHub](https://github.com/mistralai/mistral-vibe) |

**Notes**: Vibe has a `plan` agent profile that restricts tools to read-only operations. Config lives
in `.vibe/config.toml` (project) or `~/.vibe/config.toml` (global). Local project skills are stored
in `.vibe/skills/`. No documentation was found confirming that the `plan` agent profile saves plan
output to a deterministic on-disk path. Classified as Inferred (no plan-file output).

---

## `source_agent` Mapping

This table shows the `source_agent` string used in `intake_sources.py` and intake events for each
configured harness key.

| Harness | Config key | `source_agent` value |
|---------|------------|----------------------|
| Claude Code | `claude` | `claude-code` |
| GitHub Copilot | `copilot` | `copilot` |
| Google Gemini | `gemini` | `gemini` |
| Cursor | `cursor` | `cursor` |
| Qwen Code | `qwen` | `qwen` |
| OpenCode | `opencode` | `opencode` |
| Windsurf | `windsurf` | `windsurf` |
| Kilocode | `kilocode` | `kilocode` |
| Augment Code | `auggie` | `augment` |
| Roo Cline | `roo` | `roo` |
| Amazon Q / Kiro | `q` / `kiro` | `amazon-q` |
| Google Antigravity | `antigravity` | `antigravity` |
| Mistral Vibe | `vibe` | `vibe` |
| Generic handoff packet | `handoff` | omitted (`source_agent` taken from packet `source_tool` when present) |

---

## Active scan entries in `intake_sources.py`

Only harnesses with **Verified-docs** or **Verified-empirical** confidence and a deterministic
project-level (or configurable) path are included as active tuples in `HARNESS_PLAN_SOURCES`.

| Harness | Active? | Reason |
|---------|---------|--------|
| Claude Code | No | Default path is global (`~/.claude/plans/`); project-level only when `plansDirectory` is explicitly set in `.claude/settings.json`. Auto-named files not deterministically findable without config. |
| GitHub Copilot | No | No confirmed project-level plan file path. |
| Google Gemini | Yes (conditional) | `.gemini/plans/` is the opt-in project-local path; scannable when configured. |
| Cursor | Yes (conditional) | `.cursor/plans/` is the project-local path when user clicks "Save to Workspace". |
| Qwen Code | No | No Markdown plan file; only JSON todos in global `~/.qwen/todos/`. |
| OpenCode | Yes | `.opencode/plans/*.md` is the verified, hard-coded project-level path. |
| Windsurf | No | Global-only path `~/.windsurf/plans/`; no project-level path. |
| Kilocode | No | Path is buggy (saves to `.opencode/plans/` not `.kilocode/plans/`); unstable. |
| Augment Code | No | Global-only `~/.augment/plans/`; path is Inferred, not Verified. |
| Roo Cline | No | No confirmed plan file path. |
| Amazon Q | No | No confirmed plan file path. |
| Kiro | Yes | `.kiro/specs/<slug>/requirements.md`, `design.md`, `tasks.md` are the verified spec artifacts. |
| Antigravity | No | No confirmed project-level plan file path. |
| Mistral Vibe | No | No confirmed plan file output on disk. |
| Generic handoff packet | Yes | `.handoff/*.md` is the project-local drop directory for tool-agnostic handoff packets (`docs/contracts/handoff-packet-v1.md`). |

---

## Scan Behaviour Notes

### Multiple files from the same harness directory

When a harness directory (e.g. `.opencode/plans/`) contains more than one `.md` file, `scan_for_plans()` returns each file as a separate candidate. All will share the same harness key. The files are returned in `sorted()` order (alphabetical by filename).

For harnesses that use timestamp-prefixed filenames (e.g. `2026-04-01-feature-foo.md`), alphabetical order matches chronological order. The most-recent plan will appear **last** in the candidate list. If `--auto` finds multiple candidates, the numbered prompt will list them in this order — users should choose the highest-numbered entry for the most-recent plan, or pass an explicit path to skip the prompt entirely.

---

## How to Update

When new evidence changes the status of a harness:

1. Update this document: add the new source URL and change the Confidence value.
2. Promote to an active entry in `HARNESS_PLAN_SOURCES` in
   `src/specify_cli/intake_sources.py` if confidence is now Verified-docs or
   Verified-empirical.
3. Move the corresponding TODO comment in `intake_sources.py` to the active list.
4. Update the "Active scan entries" table above.
5. Commit with a message referencing this file and the issue/PR that confirmed the information.

**Confidence levels**:

| Level | Meaning |
|-------|---------|
| Verified-docs | Path confirmed in official documentation or source code |
| Verified-empirical | Path confirmed by direct observation on a live machine |
| Inferred | Path derived from secondary sources (changelogs, community posts, third-party guides) — not confirmed in official docs |
| Unknown | No credible source found |
