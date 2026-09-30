---
title: 3.2 CLI Reference Audit — Meta-Issues
description: Enumerates every observed mismatch between the live spec-kitty Typer surface, its rendered --help text, and the CLI-reference docs, with a schema for the findings.
doc_status: deprecated
updated: '2026-08-12'
---

> ⚠ **Retired 2026-08-12 (`doc_status: deprecated`).** Working note for the 3.2 documentation mission `spec-kitty-3-2-docs-01KS4KSZ` (14/14 WPs done 2026-05-21); the docs are published (now 3.2.6). Content preserved as an audit-trail record.

# 3.2 CLI Reference Audit — Meta-Issues

This file enumerates every observed mismatch between the live `spec-kitty` Typer surface, its rendered `--help` text, and the documentation that references it. Rows here are the canonical artefact for FR-010 of mission `spec-kitty-3-2-docs-01KS4KSZ`. They are **not** runtime tickets; each row is a candidate for a follow-up code or doc fix outside this mission, which is constrained by C-002 (no Typer code edits) and C-006 (all CLI/help mismatches land here).

## Schema

Each row follows the `MetaIssueEntry` shape defined in [`kitty-specs/spec-kitty-3-2-docs-01KS4KSZ/data-model.md`](../../../../kitty-specs/spec-kitty-3-2-docs-01KS4KSZ/data-model.md#metaissueentry).

Columns:

| Column | Meaning |
| --- | --- |
| `command_path` | Space-joined command path as exposed by Typer (e.g., `spec-kitty agent decision open`). Use `PATH NO LONGER VISIBLE` for stale entries that no longer resolve. |
| `source_file` | Repo-relative source file that defines the command, or `n/a` for purely doc-side stale references. |
| `source_function` | The Python function name that registers / implements the command, or `TBD` when introspection cannot pinpoint it. |
| `observed_help` | Verbatim help summary surfaced by `spec-kitty … --help` at audit time. |
| `observed_behavior_or_test_evidence` | Concrete evidence: live behavior, test name, or referencing doc path. |
| `problem_type` | One of seven canonical values (see legend below). |
| `recommended_fix` | Short description of the corrective action (code change, doc rewrite, deprecation cleanup). |
| `owner_area` | Codebase area best positioned to take the fix: `agent`, `mission`, `core`, `docs`, `tracker`, `doctor`, etc. |
| `blocking_status` | `blocking`, `non_blocking`, or `resolved` (see legend). |

### `problem_type` legend

- `inaccurate` — the help text describes behaviour that differs from what the command actually does.
- `incomplete` — the help text omits options, defaults, or side effects that operators need to know.
- `stale` — the help text or documentation references a command/flag that no longer exists.
- `missing` — a documented command path is not surfaced by the live Typer tree at all.
- `confusing` — the surface is technically correct but contradicts itself (e.g., labelled "Internal" while top-level visible).
- `version_leakage` — the help text or doc surfaces version-specific guidance that should be archived or migrated.

(`MetaIssueEntry.ProblemType` only enumerates six members today; if a future audit needs a seventh value, extend the schema in `data-model.md` first.)

### `blocking_status` legend

- `blocking` — must be resolved before the 3.2 publication checklist closes.
- `non_blocking` — acknowledged, slated for a later mission.
- `resolved` — fix landed and verified; row retained for traceability.

## Seed rows (from `cli-audit-3-2.md`)

| command_path | source_file | source_function | observed_help | observed_behavior_or_test_evidence | problem_type | recommended_fix | owner_area | blocking_status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `spec-kitty implement` | `src/specify_cli/cli/commands/implement.py` | `implement` | `Internal - allocate or reuse the lane worktree for a work package.` | Command is registered on the top-level `spec-kitty` Typer app (no `hidden=True`); `docs/api/cli-commands.md` lists it among user-facing commands; tutorials such as `docs/guides/missions-overview.md` instruct operators to invoke `spec-kitty implement WP##` directly. | confusing | Either drop the "Internal -" prefix from the help text to match the user-facing exposure, or mark the command `hidden=True` and re-route users through `spec-kitty agent action implement` exclusively. Decide and align help + docs together. | core | blocking |
| `spec-kitty agent context update-context` | `src/specify_cli/cli/commands/agent/context.py` | _(removed)_ | `PATH NO LONGER VISIBLE` | `src/specify_cli/cli/commands/agent/context.py:131` carries the comment `# update-context command removed — agent_context.py was deleted in WP10.`; the live tree only exposes `spec-kitty agent context resolve`. Stale references remain in `docs/api/agent-subcommands.md`, `docs/guides/missions-overview.md`, and `docs/guides/claude-code-workflow.md`. | stale | Remove every doc reference to `agent context update-context` and replace with `agent context resolve` where the intent matches; add a migration note for operators following older tutorials. | docs | blocking |
| `spec-kitty agent workflow implement` | `src/specify_cli/cli/commands/agent/__init__.py` (Typer wiring), `src/specify_cli/cli/commands/agent/workflow.py` | `implement` (registered under the `action` Typer name via `app.add_typer(workflow.app, name="action", ...)`) | `PATH NO LONGER VISIBLE` | `agent/__init__.py` mounts `workflow.app` as `agent action`, so the canonical path is `spec-kitty agent action implement`. `docs/guides/implement-work-package.md` and several skill prompts still instruct operators to run `spec-kitty agent workflow implement`. | stale | Rewrite the affected how-to and skill prompts to use `spec-kitty agent action implement`; consider a deprecation alias if external automation relies on the old name. | docs | blocking |
| `spec-kitty agent feature`, `spec-kitty agent workflow` | `src/specify_cli/cli/commands/agent/__init__.py` | n/a (no Typer registration) | `PATH NO LONGER VISIBLE` | `docs/api/agent-subcommands.md` (legacy hand-authored copy) described `agent feature` and `agent workflow` as compatibility aliases, but neither name is mounted on `agent.app` today. Only `mission`, `tasks`, `context`, `release`, `action`, `status`, `tests`, `decision`, `retrospect`, and the hidden `profile` alias are wired. | stale | Drop the legacy alias copy from documentation; if alias retention is desired, add an explicit Typer registration with `hidden=True` and document it. | docs | non_blocking |
| `spec-kitty mission switch`, `spec-kitty mission-type switch` | `src/specify_cli/cli/commands/mission_type.py` | `switch_cmd` (registered via `@app.command("switch", deprecated=True)`; `mission.py` re-exports `mission_type.app`) | `[REMOVED] Switch active mission - this command was removed in v0.8.0.` | Both paths render help (`--help` exits 0), but executing the command itself raises `typer.Exit(1)` after printing an error. Audit page (`cli-audit-3-2.md`) flagged the help-vs-behaviour mismatch. | confusing | Either fully remove the deprecated command (so `--help` 404s like other removed paths) or rewrite the help summary to match the removed-but-still-discoverable behaviour. Update tutorials that historically used `mission switch`. | mission | non_blocking |
| `spec-kitty agent profile` vs `spec-kitty agent profile list` | `src/specify_cli/cli/commands/agent/__init__.py` (mounts `profiles_cmd.app` under `profile` with `hidden=True`), `src/specify_cli/cli/commands/profiles_cmd.py` | `list_profiles` | Parent group `spec-kitty agent profile` is hidden (`hidden=True`); child `spec-kitty agent profile list` is visible because `profiles_cmd.app` does not propagate hidden status. | The visible child appears in completion and `--help` walking even though its parent group is suppressed. The audit captured the mismatch as a UX cliff: users can hit the child without seeing the parent help banner. | confusing | Pick one path: (a) surface the parent group at top-level by adding `spec-kitty profiles list` (consistent with `profiles_cmd.app`), or (b) hide the child too so the asymmetry disappears. Update reference docs once chosen. | agent | non_blocking |

## How to add new rows

When the freshness checker (or an operator running `spec-kitty … --help` interactively) finds another mismatch, append a new row to the table above with the same nine columns. Cite a file path with a line range or a test name in `observed_behavior_or_test_evidence` so reviewers can verify without re-running the live tree. Rows whose `problem_type` is `stale` and whose docs have been removed should be flipped to `blocking_status: resolved` rather than deleted, to preserve the audit trail.
