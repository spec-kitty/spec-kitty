---
title: Spec Kitty 3.2 Documentation — Information Architecture
description: 'Information-architecture design for the Spec Kitty 3.2 documentation refresh (WP08): the section structure, navigation groups, and page-placement decisions.'
doc_status: deprecated
updated: '2026-08-12'
---

> ⚠ **Retired 2026-08-12 (`doc_status: deprecated`).** Working note for the 3.2 documentation mission `spec-kitty-3-2-docs-01KS4KSZ` (14/14 WPs done 2026-05-21); the docs are published (now 3.2.6). Content preserved as an audit-trail record.

# Spec Kitty 3.2 Documentation — Information Architecture

**Mission:** `spec-kitty-3-2-docs-01KS4KSZ`
**work package:** WP08 (T025, T026)
**Requirements:** FR-011 (IA spine), FR-012 (gap list)
**Inputs:**
- `docs/development/3-2-page-inventory.yaml` (WP02 — 402 rows)
- `docs/api/cli-commands.md` (WP07 — rebuilt reference)
- `kitty-specs/spec-kitty-3-2-docs-01KS4KSZ/spec.md`, `plan.md` (Project Structure §)

---

## 1. Purpose

This document is the 3.2 Divio information architecture for `docs/`. It enumerates every planned 3.2 page across the four Divio types — **Tutorials** (learn), **How-to guides** (task), **Reference** (lookup), **Explanation** (understand) — and assigns a disposition (`reuse`, `rewrite`, `archive`, `migrate-note`, `new`) to every existing page under those four directories, so that subsequent missions can land the rewrite without ambiguity.

Divio four-type guidance is the IA spine:
- **Tutorial** — a guided learning path for a brand-new user. Goal: build confidence with a working result.
- **How-to** — an opinionated recipe for a specific job a competent user is already trying to do.
- **Reference** — austere, complete description of an API/CLI/file/schema surface. Lookup-grade.
- **Explanation** — conceptual prose for a user who already kind of works the tool and wants to understand *why*.

Each planned 3.2 page is anchored to exactly one Divio type.

---

## 2. Tutorials

Audience scope: first-time users, evaluators, and operators learning a brand-new capability hands-on. Every tutorial ends with a verifiable success criterion the reader can check without help.

| Page | Title | Target audience | Prerequisites | Success criterion | Nav placement | Inventory row / origin |
|------|-------|-----------------|---------------|-------------------|---------------|------------------------|
| `docs/guides/install-and-first-mission.md` | Install Spec Kitty and run your first mission | Brand-new evaluator; no Spec Kitty experience | A supported Python (≥3.11) and one supported harness installed (Claude Code recommended) | User has run `spec-kitty init`, created a sample mission, and reached `for_review` with no errors | `tutorials/install-and-first-mission` (top of TOC) | NEW (plan.md Project Structure) — supersedes `getting-started.md` + `your-first-mission.md` |
| `docs/guides/first-charter-governed-workflow.md` | Your first charter-governed workflow | Evaluator who completed the install tutorial | Install-and-first-mission tutorial; project initialized | User has authored a charter, generated doctrine, and watched governance directives apply to a mission run | `tutorials/first-charter-governed-workflow` | NEW — supersedes `charter-governed-workflow.md` |
| `docs/guides/first-3-2-mission.md` | Your first 3.2 mission using `spec-kitty next` | Evaluator familiar with the runtime; new to 3.2 | Project initialized at 3.2; one supported harness configured | User has driven a full mission to merge using only `spec-kitty next --agent <name>` as the loop control | `tutorials/first-3-2-mission` | NEW — embodies the 3.2 runtime loop |
| `docs/guides/multi-harness-workflow.md` | Your first multi-harness workflow | Evaluator with two harnesses installed (e.g., Claude Code + Codex) | First-3-2-mission tutorial; two supported harnesses installed | User has run one mission split across two harnesses (e.g., implementer in Claude Code, reviewer in Codex) | `tutorials/multi-harness-workflow` | NEW — supersedes legacy `multi-agent-workflow.md` |

**Planned tutorials: 4.**

### Tutorial cross-references (inventory ↔ plan)

| Planned page | Inventory row(s) it replaces / extends |
|--------------|-----------------------------------------|
| `install-and-first-mission.md` | replaces `docs/guides/getting-started.md`, `docs/guides/your-first-mission.md` |
| `first-charter-governed-workflow.md` | replaces `docs/guides/charter-governed-workflow.md` |
| `first-3-2-mission.md` | NEW (no direct predecessor) |
| `multi-harness-workflow.md` | replaces `docs/guides/multi-agent-workflow.md`, `docs/guides/missions-overview.md` (the latter folds in as context) |

---

## 3. How-to guides

Audience scope: operators with a concrete job to do (install on this OS, run a mission in this host, recover from this failure). Each how-to is a tight task recipe — no conceptual prose, no full reference dumps.

### 3.1 Install / upgrade / uninstall family

| Page | Title | Target audience | Prerequisites | Success criterion | Nav placement | Inventory row / origin |
|------|-------|-----------------|---------------|-------------------|---------------|------------------------|
| `docs/guides/install-macos.md` | Install Spec Kitty on macOS | macOS operators | Python ≥3.11; Homebrew or pipx | `spec-kitty --version` reports current 3.2.x release | `how-to/install/macos` | NEW (plan §Install) |
| `docs/guides/install-linux.md` | Install Spec Kitty on Linux | Linux operators (Ubuntu/Debian/Arch/RHEL family) | Python ≥3.11; pipx or uv | `spec-kitty --version` reports current 3.2.x release | `how-to/install/linux` | NEW |
| `docs/guides/install-windows.md` | Install Spec Kitty on Windows | Windows operators (PowerShell or WSL2) | Python ≥3.11; pipx or uv on PATH | `spec-kitty --version` reports current 3.2.x release | `how-to/install/windows` | NEW |
| `docs/guides/initialize-a-repo.md` | Initialize a repo with `spec-kitty init` | Operator who has installed the CLI | CLI installed; empty or pre-existing repo | Repo has `.kittify/`, `kitty-specs/`, host command files; `spec-kitty agent runtime status` runs clean | `how-to/lifecycle/initialize` | NEW (extracted from `install-spec-kitty.md`, `non-interactive-init.md`) |
| `docs/guides/upgrade-cli.md` | Upgrade the Spec Kitty CLI | Operator on an older CLI release | Existing install via pipx/pip/uv | `spec-kitty --version` reports the target release; existing missions still load | `how-to/lifecycle/upgrade-cli` | NEW (extracts CLI half of `install-and-upgrade.md`) |
| `docs/guides/upgrade-project.md` | Upgrade project files for a new Spec Kitty release | Operator with an initialized repo | CLI upgraded to target release | Project files (templates, host commands, runtime contracts) match target release; no drift warnings from `spec-kitty agent runtime status` | `how-to/lifecycle/upgrade-project` | NEW (extracts project half of `install-and-upgrade.md`; also retires `upgrade-to-0-12-0.md`) |
| `docs/guides/uninstall.md` | Uninstall Spec Kitty cleanly | Operator removing Spec Kitty from machine or repo | None | CLI binary removed and project files preserved; or repo files cleaned up with `spec-kitty agent project clean` (depending on chosen mode) | `how-to/lifecycle/uninstall` | NEW |

### 3.2 Run-a-mission-in-host family

| Page | Title | Target audience | Prerequisites | Success criterion | Nav placement | Inventory row / origin |
|------|-------|-----------------|---------------|-------------------|---------------|------------------------|
| `docs/guides/harnesses/claude-code.md` | Run a mission in Claude Code | Claude Code user | Claude Code installed; project initialized | One mission driven end-to-end from inside Claude Code | `how-to/harnesses/claude-code` | NEW (supersedes/extends `claude-code-integration` + `claude-code-workflow` tutorials) |
| `docs/guides/harnesses/codex.md` | Run a mission in OpenAI Codex CLI | Codex CLI user | Codex CLI installed; project initialized | One mission driven end-to-end from Codex | `how-to/harnesses/codex` | NEW |
| `docs/guides/harnesses/opencode.md` | Run a mission in OpenCode | OpenCode user | OpenCode installed; project initialized | One mission driven end-to-end from OpenCode | `how-to/harnesses/opencode` | NEW |
| `docs/guides/harnesses/cursor.md` | Use Spec Kitty inside Cursor | Cursor user | Cursor installed; project initialized | Operator runs `/spec-kitty.*` commands from Cursor and completes a mission step | `how-to/harnesses/cursor` | NEW |
| `docs/guides/harnesses/gemini.md` | Use Spec Kitty with Gemini CLI | Gemini CLI user | Gemini CLI configured | Mission step driven via Gemini | `how-to/harnesses/gemini` | NEW |
| `docs/guides/harnesses/pi-tui.md` | Use the Pi TUI with Spec Kitty | Pi TUI user | Pi TUI installed | Mission step driven via the Pi TUI | `how-to/harnesses/pi-tui` | NEW |
| `docs/guides/harnesses/qwen.md` | Run a mission with Qwen | Qwen user | Qwen agent configured | Mission step driven via Qwen | `how-to/harnesses/qwen` | NEW (tier-gated by decision `01KS4KTS4V300M9MMTS1AJEGXY`) |
| `docs/guides/harnesses/amazon-q.md` | Run a mission with Amazon Q Developer | Amazon Q user | Amazon Q installed | Mission step driven via Amazon Q | `how-to/harnesses/amazon-q` | NEW (tier-gated) |
| `docs/guides/harnesses/copilot.md` | Run a mission with GitHub Copilot CLI | Copilot CLI user | Copilot CLI configured | Mission step driven via Copilot CLI | `how-to/harnesses/copilot` | NEW (tier-gated) |
| `docs/guides/harnesses/augment.md` | Run a mission with Augment | Augment user | Augment configured | Mission step driven via Augment | `how-to/harnesses/augment` | NEW (tier-gated) |
| `docs/guides/harnesses/roo.md` | Run a mission with Roo Code | Roo user | Roo installed | Mission step driven via Roo | `how-to/harnesses/roo` | NEW (tier-gated) |
| `docs/guides/harnesses/kilocode.md` | Run a mission with Kilocode | Kilocode user | Kilocode installed | Mission step driven via Kilocode | `how-to/harnesses/kilocode` | NEW (tier-gated) |
| `docs/guides/harnesses/kiro.md` | Run a mission with Kiro | Kiro user | Kiro installed | Mission step driven via Kiro | `how-to/harnesses/kiro` | NEW (tier-gated) |
| `docs/guides/harnesses/windsurf.md` | Run a mission with Windsurf | Windsurf user | Windsurf installed | Mission step driven via Windsurf | `how-to/harnesses/windsurf` | NEW (tier-gated) |

### 3.3 Diagnose family

| Page | Title | Target audience | Prerequisites | Success criterion | Nav placement | Inventory row / origin |
|------|-------|-----------------|---------------|-------------------|---------------|------------------------|
| `docs/guides/diagnose-setup.md` | Diagnose a Spec Kitty setup | Operator whose install or repo state seems broken | CLI installed | `spec-kitty agent runtime status` returns a clean report or the operator has a concrete next action | `how-to/diagnose/setup` | rewrite of `diagnose-installation.md` |

### 3.4 Recover family

| Page | Title | Target audience | Prerequisites | Success criterion | Nav placement | Inventory row / origin |
|------|-------|-----------------|---------------|-------------------|---------------|------------------------|
| `docs/guides/recover-from-interrupted-missions.md` | Recover from an interrupted mission | Operator whose mission was stopped mid-run | Mission in `in_progress` or partial state | Mission resumes cleanly via `spec-kitty next` or is rolled back to a known good lane state | `how-to/recover/interrupted-mission` | rewrite — merges `recover-from-implementation-crash.md` semantics into the 3.2 runtime loop |
| `docs/guides/recover-from-merge-failure.md` | Recover from a merge failure | Operator whose merge attempt failed | Mission in `for_merge` or post-merge error | Merge replays cleanly or operator has rolled back to a known state | `how-to/recover/merge-failure` | rewrite of `recover-from-interrupted-merge.md` + `troubleshoot-merge.md` |
| `docs/guides/recover-from-stale-generated-files.md` | Recover from stale generated files | Operator whose host command files / templates have drifted | Project initialized | `spec-kitty agent runtime status` is clean; drift warnings cleared via `spec-kitty agent project sync` | `how-to/recover/stale-files` | NEW (3.2-specific — addresses the docs-freshness gates introduced in this mission) |

### 3.5 Other 3.2-current how-tos retained

The following existing how-to pages remain in 3.2 (full disposition in §6.2). They are listed here for nav completeness; they are not re-described above because their existing titles already match the 3.2 use case once minor rewrites land:

`accept-and-merge.md`, `adhoc-specialist-session.md`, `build-custom-orchestrator.md`, `create-an-org-doctrine-pack.md`, `create-plan.md`, `create-specification.md`, `generate-tasks.md`, `gstack-glossary-observations.md`, `handle-dependencies.md`, `implement-work-package.md`, `keep-main-clean.md`, `manage-agents.md`, `manage-glossary.md`, `parallel-development.md`, `review-work-package.md`, `run-external-orchestrator.md`, `run-governed-mission.md`, `run-mutation-tests.md`, `setup-codex-spec-kitty-launcher.md`, `setup-governance.md`, `switch-missions.md`, `sync-workspaces.md`, `synthesize-doctrine.md`, `troubleshoot-charter.md`, `use-dashboard.md`, `use-operation-history.md`, `use-retrospective-learning.md`, `use-wps-yaml-manifest.md`.

**Planned how-to pages (counting net post-rewrite): 36** = 7 lifecycle + 14 harnesses + 1 diagnose + 3 recover + 11 retained-current (after consolidating `merge-feature.md` into `accept-and-merge.md` and dropping `install-spec-kitty.md` + `non-interactive-init.md` + `install-and-upgrade.md` + `upgrade-to-0-12-0.md` + `troubleshoot-merge.md` + `recover-from-interrupted-merge.md` + `recover-from-implementation-crash.md` + `diagnose-installation.md` per §6.2).

---

## 4. Reference

Audience scope: experienced operators and integrators looking something up. No prose, no narratives — schemas, command surfaces, file layouts, supported values.

| Page | Title | Target audience | Prerequisites | Success criterion | Nav placement | Inventory row / origin |
|------|-------|-----------------|---------------|-------------------|---------------|------------------------|
| `docs/api/cli-commands.md` | CLI command reference | Operators and integrators | None | Reader finds every non-hidden CLI command, flag, and exit code without reading prose | `reference/cli/commands` | rewrite (WP07 already landed the 3.2 rebuild) |
| `docs/api/slash-commands.md` | Slash commands and host command files | Operators using harness `/` commands | None | Reader finds the canonical slash command name, target host file path, and behavior for every host | `reference/cli/slash-commands` | rewrite — extended to enumerate per-host command file paths (e.g., `.claude/commands/`, `.agents/skills/spec-kitty.<command>/`, etc.) |
| `docs/api/agent-subcommands.md` | Agent subcommands | Implementer agents and orchestrator-API integrators | None | Reader finds every `spec-kitty agent ...` subcommand, its flags, and its JSON output shape | `reference/cli/agent-subcommands` | rewrite (per plan §Project Structure — "Updated to 3.2 surface") |
| `docs/api/file-structure.md` | Generated project file structure | Operators inspecting an initialized repo | None | Reader can locate every file/dir Spec Kitty writes into a project (`.kittify/`, `kitty-specs/`, host command files, etc.) and its purpose | `reference/files/structure` | rewrite — refreshed to current 3.2 surface |
| `docs/api/configuration.md` | Configuration reference | Operators tuning behavior | None | Reader finds every config key (in `.kittify/config.*` and per-mission overrides) with type, default, and where it’s read | `reference/files/configuration` | rewrite for 3.2 keys |
| `docs/api/environment-variables.md` | Environment variables | Operators and CI integrators | None | Reader finds every `SPEC_KITTY_*` environment variable with semantics and default | `reference/files/env-vars` | rewrite for 3.2 |
| `docs/api/supported-harnesses.md` | Supported harnesses matrix | Operators and procurement reviewers | None | Reader sees every supported harness with tier, supported version range, install hint, and link to its how-to | `reference/harnesses/matrix` | NEW (per plan §Project Structure) |
| `docs/api/init-lifecycle.md` | `spec-kitty init` lifecycle | Operators debugging init | None | Reader can map every phase of init (preflight, scaffold, host wiring, doctrine sync, finalize) to the files it writes | `reference/lifecycle/init` | NEW |
| `docs/api/upgrade-lifecycle.md` | Upgrade lifecycle | Operators upgrading projects | None | Reader can map every phase of upgrade (drift detect, plan, apply, verify) to behavior + flags | `reference/lifecycle/upgrade` | NEW |
| `docs/api/terminology.md` (or `glossary.md`) | Glossary | All readers | None | Reader can look up every canonical term used elsewhere in the docs (mission, mission type, mission run, WP, lane, harness, charter, doctrine, runtime loop, etc.) | `reference/glossary` | rewrite — promote to canonical 3.2 glossary, reconcile with `contextive-glossaries.md` |

The following existing reference pages remain in 3.2 (disposition in §6.3): `agent-plan-artifacts.md`, `charter-commands.md`, `event-envelope.md`, `missions.md`, `orchestrator-api.md`, `profile-invocation.md`, `retrospective-schema.md`, `supported-agents.md`, `README.md`.

**Planned reference pages: 19** = 10 newly planned/rewritten above + 9 retained-current from inventory.

---

## 5. Explanation

Audience scope: readers who have *used* the tool and now want to understand the model. Conceptual, narrative, often diagrammatic.

| Page | Title | Target audience | Prerequisites | Success criterion | Nav placement | Inventory row / origin |
|------|-------|-----------------|---------------|-------------------|---------------|------------------------|
| `docs/architecture/what-is-spec-kitty-3-2.md` | What is Spec Kitty in 3.2 | Operators and decision-makers | None — but readers benefit from one mission of experience | Reader can articulate the 3.2 product in one paragraph and place it next to peers (Devin, Aider, plain Cursor, etc.) | `explanation/intro/what-it-is` | NEW |
| `docs/architecture/mission-model.md` | The mission model | Operators past their first mission | One mission run | Reader can name mission types, mission runs, WPs, lanes, and acceptance/merge gates | `explanation/mission/model` | rewrite of `mission-system.md` (already current but pre-3.2 voice) |
| `docs/architecture/charter-and-doctrine.md` | Charter and doctrine | Operators using governance | First-charter-governed-workflow tutorial | Reader can explain charter sections, directive IDs, tactic IDs, action-critical scoping, and the doctrine compile pipeline | `explanation/governance/charter-doctrine` | rewrite — folds in `charter-synthesis-drg.md` and `org-doctrine-layer.md` |
| `docs/architecture/runtime-loop-and-next.md` | The runtime loop and `spec-kitty next` | Operators driving missions | First-3-2-mission tutorial | Reader can explain the next-step contract, action index, step boundaries, and how harnesses plug in | `explanation/runtime/loop` | NEW — supersedes `runtime-loop.md` |
| `docs/architecture/harness-integration.md` | Harness integration | Operators and integrators | Multi-harness tutorial | Reader can explain how host command files are generated, how host shells call the CLI, and how tiers are decided | `explanation/runtime/harness-integration` | NEW |
| `docs/architecture/version-compatibility.md` | Version compatibility | Operators upgrading | None | Reader can explain the CLI ↔ project-files compatibility window and the upgrade path policy | `explanation/runtime/version-compat` | NEW |
| `docs/architecture/pip-vs-pipx-vs-uv.md` | Install tradeoffs: pip vs pipx vs uv | Operators choosing a packaging path | None | Reader can pick an install method with eyes open (isolation, upgrade ergonomics, virtualenv interactions) | `explanation/lifecycle/install-tradeoffs` | NEW |
| `docs/architecture/workspace-git-and-branches.md` | Workspace, git, and branches | Operators wondering why worktrees | First mission with a multi-WP merge | Reader can explain mission branches, lane worktrees, auto-commit, and merge replay | `explanation/runtime/git-model` | rewrite — folds `git-workflow.md`, `git-worktrees.md`, `execution-lanes.md`, `kanban-workflow.md` |

The following existing explanation pages remain in 3.2 (disposition in §6.4): `ai-agent-architecture.md`, `divio-documentation.md`, `documentation-mission.md`, `governed-profile-invocation.md`, `multi-agent-orchestration.md`, `retrospective-learning-loop.md`, `spec-driven-development.md`.

**Planned explanation pages: 15** = 8 newly planned/rewritten above + 7 retained-current from inventory.

---

## 6. Gap list (existing pages → disposition)

This is the disposition table for **every** existing page under the four Divio directories per `docs/development/3-2-page-inventory.yaml`. Tag values come straight from the inventory.

Disposition values:
- `reuse` — page is current and stays as-is (modulo `version_tag` frontmatter add in a later mission).
- `rewrite` — page exists but its content needs a 3.2-aligned rewrite.
- `archive` — page is 1.x/2.x and moves out of current nav per WP09.
- `migrate-note` — page is 3.1 and becomes a migration note per plan default.
- `new` — page does not exist; create during this mission's implement phase.

### 6.1 `docs/guides/` (8 existing pages)

| Existing page | Inventory tag | Disposition | Target IA slot |
|---------------|---------------|-------------|----------------|
| `docs/guides/charter-governed-workflow.md` | current | rewrite | replaced by `tutorials/first-charter-governed-workflow.md` |
| `docs/guides/claude-code-integration.md` | current | rewrite | content migrates to `how-to/harnesses/claude-code.md`; tutorial slot retired (tutorials are harness-agnostic in 3.2) |
| `docs/guides/claude-code-workflow.md` | current | rewrite | content migrates to `how-to/harnesses/claude-code.md`; tutorial slot retired |
| `docs/guides/getting-started.md` | current | rewrite | replaced by `tutorials/install-and-first-mission.md` |
| `docs/guides/missions-overview.md` | current | rewrite | conceptual material moves to `explanation/mission-model.md`; tutorial slot retired |
| `docs/guides/multi-agent-workflow.md` | current | rewrite | replaced by `tutorials/multi-harness-workflow.md` |
| `docs/guides/orchestrator-quickstart.md` | current | reuse | `tutorials/orchestrator-quickstart` |
| `docs/guides/your-first-mission.md` | current | rewrite | replaced by `tutorials/install-and-first-mission.md` (note: title also de-features per Terminology Canon) |

### 6.2 `docs/guides/` (38 existing pages)

| Existing page | Inventory tag | Disposition | Target IA slot |
|---------------|---------------|-------------|----------------|
| `docs/guides/2-1-main-cutover-checklist.md` | migration | migrate-note | moves under `docs/migration/` per WP09 archive plan |
| `docs/guides/accept-and-merge.md` | current | rewrite | `how-to/lifecycle/accept-and-merge` — absorb `merge-feature.md` |
| `docs/guides/adhoc-specialist-session.md` | current | reuse | `how-to/governance/adhoc-specialist-session` |
| `docs/guides/build-custom-orchestrator.md` | current | reuse | `how-to/orchestrator/build-custom` |
| `docs/guides/create-an-org-doctrine-pack.md` | current | reuse | `how-to/governance/org-doctrine-pack` |
| `docs/guides/create-plan.md` | current | rewrite | `how-to/mission/create-plan` — refresh to 3.2 voice |
| `docs/guides/create-specification.md` | current | rewrite | `how-to/mission/create-specification` — refresh to 3.2 voice |
| `docs/guides/diagnose-installation.md` | current | rewrite | replaced by `how-to/diagnose-setup.md` |
| `docs/guides/generate-tasks.md` | current | rewrite | `how-to/mission/generate-tasks` — refresh to 3.2 |
| `docs/guides/gstack-glossary-observations.md` | current | reuse | `how-to/glossary/gstack-observations` |
| `docs/guides/handle-dependencies.md` | current | reuse | `how-to/mission/handle-dependencies` |
| `docs/guides/implement-work-package.md` | current | rewrite | `how-to/mission/implement-work-package` — rename `agent workflow` → `agent action` (per plan §Project Structure) |
| `docs/guides/install-and-upgrade.md` | current | rewrite | split into `how-to/upgrade-cli.md` + `how-to/upgrade-project.md` |
| `docs/guides/install-spec-kitty.md` | current | rewrite | folded into `how-to/install-macos.md` / `install-linux.md` / `install-windows.md` + `initialize-a-repo.md` |
| `docs/guides/keep-main-clean.md` | current | reuse | `how-to/mission/keep-main-clean` |
| `docs/guides/manage-agents.md` | current | rewrite | `how-to/runtime/manage-agents` — refresh to 3.2 |
| `docs/guides/manage-glossary.md` | current | reuse | `how-to/glossary/manage` |
| `docs/guides/merge-feature.md` | current | rewrite | merged into `accept-and-merge.md` (Terminology Canon — no `feature` in canonical names) |
| `docs/guides/non-interactive-init.md` | current | rewrite | folded into `how-to/initialize-a-repo.md` |
| `docs/guides/parallel-development.md` | current | reuse | `how-to/runtime/parallel-development` |
| `docs/guides/recover-from-implementation-crash.md` | current | rewrite | folded into `how-to/recover-from-interrupted-missions.md` |
| `docs/guides/recover-from-interrupted-merge.md` | current | rewrite | folded into `how-to/recover-from-merge-failure.md` |
| `docs/guides/review-work-package.md` | current | rewrite | `how-to/mission/review-work-package` — refresh to 3.2 |
| `docs/guides/run-external-orchestrator.md` | current | reuse | `how-to/orchestrator/run-external` |
| `docs/guides/run-governed-mission.md` | current | rewrite | `how-to/governance/run-governed-mission` — refresh to 3.2 |
| `docs/guides/run-mutation-tests.md` | current | reuse | `how-to/quality/run-mutation-tests` |
| `docs/guides/setup-codex-spec-kitty-launcher.md` | current | rewrite | folded into `how-to/harnesses/codex.md` |
| `docs/guides/setup-governance.md` | current | rewrite | `how-to/governance/setup` — refresh to 3.2 |
| `docs/guides/switch-missions.md` | current | reuse | `how-to/runtime/switch-missions` |
| `docs/guides/sync-workspaces.md` | current | reuse | `how-to/runtime/sync-workspaces` |
| `docs/guides/synthesize-doctrine.md` | current | reuse | `how-to/governance/synthesize-doctrine` |
| `docs/guides/troubleshoot-charter.md` | current | reuse | `how-to/diagnose/charter` |
| `docs/guides/troubleshoot-merge.md` | current | rewrite | folded into `how-to/recover-from-merge-failure.md` |
| `docs/guides/upgrade-to-0-12-0.md` | current | migrate-note | moves under `docs/migration/` (release-specific) |
| `docs/guides/use-dashboard.md` | current | reuse | `how-to/runtime/use-dashboard` |
| `docs/guides/use-operation-history.md` | current | reuse | `how-to/runtime/use-operation-history` |
| `docs/guides/use-retrospective-learning.md` | current | reuse | `how-to/quality/use-retrospective-learning` |
| `docs/guides/use-wps-yaml-manifest.md` | current | reuse | `how-to/mission/use-wps-yaml-manifest` |

### 6.3 `docs/api/` (16 existing pages)

| Existing page | Inventory tag | Disposition | Target IA slot |
|---------------|---------------|-------------|----------------|
| `docs/api/README.md` | current | rewrite | `reference/index` — refresh as Divio reference landing |
| `docs/api/agent-plan-artifacts.md` | current | reuse | `reference/artifacts/agent-plan` |
| `docs/api/agent-subcommands.md` | current | rewrite | `reference/cli/agent-subcommands` (3.2 surface) |
| `docs/api/charter-commands.md` | current | reuse | `reference/cli/charter-commands` |
| `docs/api/cli-commands.md` | current | rewrite | `reference/cli/commands` (WP07 already rebuilt) |
| `docs/api/configuration.md` | current | rewrite | `reference/files/configuration` (3.2 keys) |
| `docs/api/environment-variables.md` | current | rewrite | `reference/files/env-vars` (3.2) |
| `docs/api/event-envelope.md` | current | reuse | `reference/schemas/event-envelope` |
| `docs/api/file-structure.md` | current | rewrite | `reference/files/structure` (3.2 layout) |
| `docs/api/missions.md` | current | reuse | `reference/missions/index` |
| `docs/api/orchestrator-api.md` | current | reuse | `reference/api/orchestrator` |
| `docs/api/profile-invocation.md` | current | reuse | `reference/governance/profile-invocation` |
| `docs/api/retrospective-schema.md` | current | reuse | `reference/schemas/retrospective` |
| `docs/api/slash-commands.md` | current | rewrite | `reference/cli/slash-commands` — extend with per-host command file paths |
| `docs/api/supported-agents.md` | current | rewrite | folded into `reference/supported-harnesses.md` (rename + matrix) |
| `docs/api/terminology.md` | current | rewrite | `reference/glossary` — promote to canonical 3.2 glossary |

### 6.4 `docs/architecture/` (15 existing pages)

| Existing page | Inventory tag | Disposition | Target IA slot |
|---------------|---------------|-------------|----------------|
| `docs/architecture/ai-agent-architecture.md` | current | reuse | `explanation/runtime/ai-agent-architecture` |
| `docs/architecture/charter-synthesis-drg.md` | current | rewrite | folded into `explanation/charter-and-doctrine.md` |
| `docs/architecture/divio-documentation.md` | current | reuse | `explanation/meta/divio` |
| `docs/architecture/documentation-mission.md` | current | reuse | `explanation/meta/documentation-mission` |
| `docs/architecture/execution-lanes.md` | current | rewrite | folded into `explanation/workspace-git-and-branches.md` |
| `docs/architecture/git-workflow.md` | current | rewrite | folded into `explanation/workspace-git-and-branches.md` |
| `docs/architecture/git-worktrees.md` | current | rewrite | folded into `explanation/workspace-git-and-branches.md` |
| `docs/architecture/governed-profile-invocation.md` | current | reuse | `explanation/governance/profile-invocation` |
| `docs/architecture/kanban-workflow.md` | current | rewrite | folded into `explanation/workspace-git-and-branches.md` (lane/kanban mapping section) |
| `docs/architecture/mission-system.md` | current | rewrite | replaced by `explanation/mission-model.md` |
| `docs/architecture/multi-agent-orchestration.md` | current | reuse | `explanation/runtime/multi-agent-orchestration` |
| `docs/architecture/org-doctrine-layer.md` | current | rewrite | folded into `explanation/charter-and-doctrine.md` |
| `docs/architecture/retrospective-learning-loop.md` | current | reuse | `explanation/quality/retrospective-learning-loop` |
| `docs/architecture/runtime-loop.md` | current | rewrite | replaced by `explanation/runtime-loop-and-next.md` |
| `docs/architecture/spec-driven-development.md` | current | reuse | `explanation/methodology/spec-driven-development` |

### 6.5 Gap list size

| Divio directory | Existing pages assessed |
|-----------------|------------------------|
| `docs/guides/` | 8 |
| `docs/guides/` | 38 |
| `docs/api/` | 16 |
| `docs/architecture/` | 15 |
| **Total** | **77** |

---

## 7. Planned-page totals by Divio type

| Divio type | Planned pages (post-3.2) |
|------------|--------------------------|
| Tutorials | 4 |
| How-to | 36 |
| Reference | 19 |
| Explanation | 15 |
| **Total** | **74** |

How-to count breakdown:
- 7 install/upgrade/uninstall lifecycle (incl. `initialize-a-repo.md`)
- 14 harness pages under `docs/guides/harnesses/`
- 1 diagnose page
- 3 recover pages
- 11 retained-current how-tos (post-consolidation)

Reference count breakdown:
- 10 rewritten/new core reference pages (CLI commands, slash commands, agent subcommands, file structure, configuration, env vars, supported-harnesses, init-lifecycle, upgrade-lifecycle, glossary)
- 9 retained-current reference pages (`README.md`, `agent-plan-artifacts.md`, `charter-commands.md`, `event-envelope.md`, `missions.md`, `orchestrator-api.md`, `profile-invocation.md`, `retrospective-schema.md`, plus the `supported-agents.md` slot which is folded into `supported-harnesses.md`)

Explanation count breakdown:
- 8 newly planned/rewritten conceptual pages (what-is-3-2, mission-model, charter-and-doctrine, runtime-loop-and-next, harness-integration, version-compatibility, pip-vs-pipx-vs-uv, workspace-git-and-branches)
- 7 retained-current explanation pages (`ai-agent-architecture.md`, `divio-documentation.md`, `documentation-mission.md`, `governed-profile-invocation.md`, `multi-agent-orchestration.md`, `retrospective-learning-loop.md`, `spec-driven-development.md`)

---

## 8. Definition of Done check (per WP08)

- [x] IA doc covers all four Divio directories (§2, §3, §4, §5).
- [x] Every CLI page in the WP07 reference is referenced in the IA (`docs/api/cli-commands.md` is the canonical reference slot; `agent-subcommands.md`, `slash-commands.md`, `charter-commands.md` are referenced explicitly in §4).
- [x] Gap list dispositions are explicit for every existing page across all four Divio directories (§6.1–§6.4 — 77 rows total).
- [x] No files outside `owned_files` are modified by this WP (this file is the sole owned target).

## 9. Notes for downstream WPs

- **WP09 (archive/migration plan)** owns the actual moves for `archive` and `migrate-note` rows in §6.
- **WP10/WP11 (harness research + matrix)** is the source of truth for the harness tier (Tier-1 vs Tier-2) — the 14 harness how-tos above will be tier-gated by decision `01KS4KTS4V300M9MMTS1AJEGXY`. If the tier resolution drops a harness to Tier-3 "experimental", its `how-to/harnesses/<name>.md` slot demotes to a single note inside `supported-harnesses.md` rather than a standalone page.
- **WP13/WP14 (publication checklist + finalization)** should treat §7 totals as the canonical scoreboard.
- All new tutorial / how-to / explanation slots follow the Terminology Canon (`mission` only — no `feature` in canonical names; legacy `your-first-mission.md` is explicitly retired in §6.1).

---

## 10. Related development docs

- [`docs/development/yaml-libraries.md`](../../../configuration/yaml-libraries.md) — YAML library choice guide: when to use ruamel.yaml (round-trip, write-back) vs PyYAML `safe_load` (read-only). Documents current-state usage, known mixed-usage sites, and the aspirational enforcement rule (FR-009).
