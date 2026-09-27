---
title: Spec Kitty slash commands reference — CLI quick reference
description: Quick reference guide for Spec Kitty slash commands. Learn how to invoke specify, plan, tasks, implement, review, accept, and consolidate within AI coding agents.
doc_status: active
updated: '2026-08-15'
---
# Slash Command Reference

Slash commands are invoked inside your AI agent (Claude Code, Codex CLI, Cursor, etc.). They are generated from Spec Kitty command templates and typically accept optional free-form arguments.

Syntax format in this reference:
- `COMMAND`: `/spec-kitty.<name> [arguments]`
- `Arguments`: free-form text passed as `$ARGUMENTS` in templates

---

## /spec-kitty.specify

**Syntax**: `/spec-kitty.specify [description]`

**Purpose**: Create or update a mission specification from a natural-language description.

**Prerequisites**:
- Run from the repository root checkout (no worktree).
- If the mission should land on a branch other than the current branch, resolve that intent first with `spec-kitty agent mission branch-context --json --target-branch <branch>`.
- Discovery interview is required before generating artifacts.

**What it does**:
- Runs a discovery interview and confirms an intent summary.
- Determines mission (software-dev or research).
- Calls `spec-kitty agent mission create` to create mission scaffolding.

**Creates/updates**:
- `kitty-specs/<feature>/spec.md`
- `kitty-specs/<feature>/meta.json`
- `kitty-specs/<feature>/checklists/requirements.md`

**Optional handoff-packet intake**: if `spec-kitty intake` staged a brief
whose YAML frontmatter declares `handoff_packet: 1` (an upstream requirements
tool's export), `/spec-kitty.specify` adopts that packet's FR/AC ids verbatim
instead of re-minting them — the discovery interview above still runs. A
packet-less brief, an unrecognised version, or malformed frontmatter all
degrade to today's plain-prose intake; the command never fails because the
overlay is absent or invalid. See [Handoff Packet v1](../contracts/handoff-packet-v1.md).

**Related**: `/spec-kitty.plan`, `/spec-kitty.charter`

---

## /spec-kitty.plan

**Syntax**: `/spec-kitty.plan [notes]`

**Purpose**: Create the implementation plan and design artifacts based on the spec.

**Prerequisites**:
- Run from the repository root checkout.
- Spec exists for the feature.

**What it does**:
- Conducts planning interrogation.
- Calls `spec-kitty agent mission setup-plan`.
- Generates planning artifacts and updates agent context files.

**Creates/updates** (as applicable):
- `kitty-specs/<feature>/plan.md`
- `kitty-specs/<feature>/research.md`
- `kitty-specs/<feature>/data-model.md`
- `kitty-specs/<feature>/contracts/`
- `kitty-specs/<feature>/quickstart.md`
- Agent context file (e.g., `CLAUDE.md`)

**Related**: `/spec-kitty.specify`, `/spec-kitty.tasks`, `/spec-kitty.research`

---

## /spec-kitty.tasks

**Syntax**: `/spec-kitty.tasks [notes]`

**Purpose**: Generate work packages and task prompts from spec and plan.

**Prerequisites**:
- Run from the repository root checkout.
- `spec.md` and `plan.md` exist.

**What it does**:
- Reads spec/plan (and optional research artifacts).
- Writes `tasks.md` plus one prompt file per work package.
- Calls `spec-kitty agent mission finalize-tasks` to populate dependencies.

**Creates/updates**:
- `kitty-specs/<feature>/tasks.md`
- `kitty-specs/<feature>/tasks/WPxx-*.md` (flat directory)

**Related**: `/spec-kitty.plan`, `/spec-kitty.implement`, `/spec-kitty.analyze`

---

## /spec-kitty.tasks-outline

**Syntax**: `/spec-kitty.tasks-outline [notes]`

**Purpose**: Create the work package manifest (`wps.yaml`) that defines each work package's metadata, dependencies, and file ownership. This is the first stage of staged work-package authoring; `tasks.md` is generated later from this manifest, not written by hand.

**Prerequisites**:
- Run from the repository root checkout.
- `spec.md` and `plan.md` exist for the mission.

**What it does**:
- Reads the spec and plan to identify work package boundaries.
- Writes `wps.yaml` as the single source of truth for WP `id`, `title`, `dependencies`, `owned_files`, `requirement_refs`, and `subtasks`.
- Leaves `tasks.md` untouched — it is generated automatically by `/spec-kitty.tasks-finalize` from `wps.yaml`.

**Creates/updates**:
- `kitty-specs/<mission>/wps.yaml`

**Related**: `/spec-kitty.plan`, `/spec-kitty.tasks-packages`, `/spec-kitty.tasks`

---

## /spec-kitty.tasks-packages

**Syntax**: `/spec-kitty.tasks-packages [notes]`

**Purpose**: Materialize one prompt file per work package (`tasks/WP*.md`) from the manifest in `wps.yaml`. This is the second stage of staged work-package authoring.

**Prerequisites**:
- Run from the repository root checkout.
- `wps.yaml` exists with complete WP definitions (written by `/spec-kitty.tasks-outline`).

**What it does**:
- Reads `wps.yaml` and generates an independent prompt file for each work package.
- Updates `wps.yaml` with per-WP `owned_files`, `requirement_refs`, `subtasks`, and `prompt_file` values, and assigns an agent profile per WP.

**Creates/updates**:
- `kitty-specs/<mission>/tasks/WP*.md`
- `kitty-specs/<mission>/wps.yaml` (per-WP details)

**Related**: `/spec-kitty.tasks-outline`, `/spec-kitty.tasks-finalize`

---

## /spec-kitty.tasks-finalize

**Syntax**: `/spec-kitty.tasks-finalize [options]`

**Purpose**: Finalize the mission's work packages — validate dependencies and requirement mapping, generate `tasks.md`, update WP frontmatter, and commit the task artifacts to the target branch. This is the final stage of staged work-package authoring.

**Prerequisites**:
- Run from the repository root checkout.
- WP prompt files and `wps.yaml` exist (from `/spec-kitty.tasks-packages`).

**What it does**:
- Runs `spec-kitty agent mission finalize-tasks`, starting with a `--validate-only` preflight.
- Validates dependencies (no cycles, no invalid references) and requirement mapping against `spec.md`.
- Computes lanes, generates `tasks.md`, updates WP frontmatter, and commits the artifacts automatically.

**Creates/updates**:
- `kitty-specs/<mission>/tasks.md`
- `kitty-specs/<mission>/tasks/WP*.md` (frontmatter: dependencies, requirement refs, lanes)

**Related**: `/spec-kitty.tasks-packages`, `/spec-kitty.implement`, `/spec-kitty.analyze`

---

## /spec-kitty.implement

**Syntax**: `/spec-kitty.implement [WP_ID]`

**Purpose**: Resolve the execution workspace and start implementation for a specific work package.

**Prerequisites**:
- Work packages exist in `kitty-specs/<feature>/tasks/`.
- Run from the repository root checkout for the action prompt; the execution workspace is created or reused by the CLI.

**What it does**:
- If explicit slash-command args are provided, forwards the WP selection into the resolver-first action flow.
- Step 1: `spec-kitty agent action implement WP## --agent <agent>` to show the prompt and move the WP to `doing`.
- Step 2: `spec-kitty implement WP##` to create or reuse the execution workspace.
- Implementation happens inside the resolved workspace path printed by the command.

**Creates/updates**:
- `.worktrees/<feature>-lane-<id>/`
- `kitty-specs/<feature>/tasks/WP##-*.md` lane status updates

**Related**: `/spec-kitty.tasks`, `/spec-kitty.review`

---

## /spec-kitty.review

**Syntax**: `/spec-kitty.review [WP_ID]`

**Purpose**: Review a completed work package and update its lane status.

**Prerequisites**:
- Run from any checkout where the mission can be resolved; review will attach to the canonical execution workspace if needed.
- WP must be in `lane: "for_review"`.

**What it does**:
- If `WP_ID` is provided, forwards it to the resolver-first workflow as an explicit `--wp-id`.
- Loads the WP prompt, supporting artifacts, and code changes.
- Performs structured review and records feedback via `--review-feedback-file`.
- Persists feedback in shared git common-dir and writes frontmatter `review_feedback` pointer (`feedback://...`) in the WP file.
- Moves the WP to `approved` (review passed, merge pending) or back to `planned` (needs changes). The merge workflow later records `done`.
- Updates `tasks.md` status when approved.

**Creates/updates**:
- `kitty-specs/<feature>/tasks/WP##-*.md` (review feedback, lane changes)
- `kitty-specs/<feature>/tasks.md` (checkbox status)

**Related**: `/spec-kitty.implement`, `/spec-kitty.accept`

---

## /spec-kitty.accept

**Syntax**: `/spec-kitty.accept [options]`

**Purpose**: Validate mission readiness and generate acceptance results.

**Prerequisites**:
- Run from any checkout or branch where mission auto-detection works.
- All WPs should be `approved` or `done`, with review feedback resolved.
- Run this after the implement-review loop and before `/spec-kitty.consolidate`.

**What it does**:
- Auto-detects mission slug and validation commands when possible.
- Runs `spec-kitty agent mission accept` to perform acceptance checks.
- Outputs acceptance summary and merge instructions.

**Creates/updates**:
- Acceptance output in the mission directory (and optional commits depending on mode)

**Related**: `/spec-kitty.review`, `/spec-kitty.consolidate`

---

## /spec-kitty.consolidate

**Syntax**: `/spec-kitty.consolidate [options]`

**Purpose**: Consolidate an accepted mission into the target branch and clean up worktrees.

**Prerequisites**:
- Run from any checkout where the mission can be resolved (repository root checkout or execution workspace).
- By default, consolidation lands in the mission's recorded target branch; use `--target <branch>` only when you intentionally want to override it.
- Mission must pass `/spec-kitty.accept`.

**What it does**:
- Executes `spec-kitty consolidate` with selected strategy and cleanup flags.
- Optionally pushes to origin and deletes worktrees/branches.
- After merge, run `/spec-kitty-mission-review`, then surface the retrospective
  captured at the runtime terminus. Canonical post-merge sequence (FR-019):
  1. **Mission review** — `/spec-kitty-mission-review` confirms spec→code fidelity.
  2. **Author or verify the retrospective** — under default policy, the runtime
     authored it during merge; verify via `cat .kittify/missions/<mission_id>/retrospective.yaml`.
     If absent (older mission, generator failure under warn policy), author with
     `spec-kitty retrospect create --mission <slug>`.
  3. **Surface findings** — `spec-kitty retrospect summary` aggregates across
     missions (read-only); `spec-kitty agent retrospect synthesize --mission <slug>`
     previews or applies proposals from one record (dry-run by default; add
     `--apply` to mutate).

**Creates/updates**:
- Merges mission branch into target branch.
- Deletes worktree and/or mission branch depending on flags.

**Related**: `/spec-kitty.accept`

---

## /spec-kitty.status

**Syntax**: `/spec-kitty.status`

**Purpose**: Display current kanban status for work packages.

**Prerequisites**:
- Run from a repo or worktree with access to `kitty-specs/<feature>/tasks/`.

**What it does**:
- Runs `spec-kitty agent tasks status`.
- Shows a lane-based status board, progress metrics, and next steps.

**Creates/updates**: None (read-only).

**Related**: `/spec-kitty.tasks`, `/spec-kitty.implement`

---

## /spec-kitty.dashboard

**Syntax**: `/spec-kitty.dashboard`

**Purpose**: Open or stop the Spec Kitty dashboard in the browser.

**Prerequisites**:
- Can run from the repository root checkout or any worktree.

**What it does**:
- Runs `spec-kitty dashboard` to start or stop the dashboard server.

**Creates/updates**: None (read-only status server).

**Related**: `/spec-kitty.status`

---

## /spec-kitty.charter

**Syntax**: `/spec-kitty.charter`

**Purpose**: Create or update the project charter.

**Prerequisites**:
- Run from the repository root checkout.

**What it does**:
- Runs a phase-based discovery interview (minimal or comprehensive).
- Writes project-wide principles to the charter file.

**Creates/updates**:
- `.kittify/charter/charter.md`

**Related**: `/spec-kitty.specify`, `/spec-kitty.plan`

---

## /spec-kitty.research

**Syntax**: `/spec-kitty.research [--force]`

**Purpose**: Scaffold research artifacts for Phase 0 research.

**Prerequisites**:
- Run from any checkout where the mission can be resolved.

**What it does**:
- Runs `spec-kitty research` to create research templates.

**Creates/updates**:
- `kitty-specs/<feature>/research.md`
- `kitty-specs/<feature>/data-model.md`
- `kitty-specs/<feature>/research/evidence-log.csv`
- `kitty-specs/<feature>/research/source-register.csv`

**Related**: `/spec-kitty.plan`

---

## /spec-kitty.analyze

**Syntax**: `/spec-kitty.analyze [notes]`

**Purpose**: Cross-artifact consistency analysis after tasks generation.

**Prerequisites**:
- Run from any checkout where the mission can be resolved.
- `spec.md`, `plan.md`, and `tasks.md` must exist.

**What it does**:
- Reads spec, plan, tasks, and charter (if present).
- Produces and persists an analysis report of gaps and conflicts.
- Records source artifact hashes so implementation can reject stale analysis.

**Creates/updates**:
- `kitty-specs/<feature>/analysis-report.md`

**Related**: `/spec-kitty.tasks`, `/spec-kitty.implement`

## Getting Started

- [Claude Code Integration](../guides/tutorials/claude-code-integration.md)
- [Claude Code Workflow](../guides/tutorials/claude-code-workflow.md)

## Practical Usage

- [Use the Dashboard](../guides/how-to/monitoring/use-dashboard.md)
- [Non-Interactive Init](../guides/how-to/installation/non-interactive-init.md)
