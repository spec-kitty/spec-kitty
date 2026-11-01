---
title: 'ADR 5 (2026-04-08): Shim Generation Supersedes Script-Type Dispatch'
description: 'Generated shims supersede shell-script dispatch: the bash and powershell script trees and the script-type flag are removed and must not be reintroduced.'
status: Accepted
doc_status: active
kind: ADR
date: '2026-04-08'
---

## Context and Problem Statement

Early versions of spec-kitty dispatched agent commands via shell scripts. The model worked as follows:

1. During `spec-kitty init`, the user was asked which script type to use: `bash` (for Unix/macOS) or `powershell` (for Windows).
2. init copied the appropriate script variant from the package into `.kittify/scripts/bash/` or `.kittify/scripts/powershell/` within the project directory.
3. Agent command files in directories like `.claude/commands/` and `.codex/prompts/` were configured to invoke these scripts.

The `--script` / `--script-type` CLI flag controlled this selection.

### What Replaced the Script Model

`shims/generator.py` was introduced as the active dispatch mechanism. Instead of shell scripts, it writes thin markdown files directly into each agent's native command directory. These files are self-contained: they describe the command's behavior inline, using the agent's native format. No shell process is invoked; the agent handles execution natively.

For Claude Code: `.claude/commands/spec-kitty.implement.md`
For GitHub Codex: `.codex/prompts/spec-kitty.implement.md`
For OpenCode: `.opencode/command/spec-kitty.implement.md`

All 13 supported agents use markdown or text-based command files. None invoke shell scripts.

### Current State at Removal

The `.kittify/scripts/bash/` and `.kittify/scripts/powershell/` directories are still referenced in `template/manager.py`. init copies them during initialization. However:

* No `.sh` or `.ps1` files exist in the package at the time of feature 076.
* The `copy_specify_base_from_local` function in `template/manager.py` (lines 131–150) copies the `scripts/` directory tree, but the source tree is empty.
* No code path in the spec-kitty runtime calls any script from `.kittify/scripts/`.
* init's cleanup logic removes these directories after the installation completes.

The result is: init creates `scripts/bash/` and `scripts/powershell/` directories, puts nothing in them (because the package has no scripts), then deletes them during cleanup. The `--script` flag influences which empty directory is created before it is deleted.

This is pure dead code: the flag exists, the directories are created and deleted, and nothing is affected by any of it.

## Decision Drivers

* **Remove dead code:** Code that has no runtime effect should not exist. It misleads developers reading the codebase and inflates the maintenance surface.
* **Clean CLI surface:** `--script` / `--script-type` is a visible CLI flag that implies a meaningful choice. Exposing it when the choice has no effect is confusing.
* **Alignment with the shim model:** `shims/generator.py` is the active, supported, tested dispatch mechanism. The script model is historical.

## Considered Options

* **Option A: Remove script directories, `--script` flag, and script-type selection logic (chosen)**
* **Option B: Keep scripts as a fallback for agents that don't support markdown commands**
* **Option C: Deprecate with a warning, remove in a future release**

## Decision Outcome

**Chosen option: Option A — The `scripts/bash/` and `scripts/powershell/` directories, the `--script` / `--script-type` flag, and all script-type selection logic are removed.**

### What Is Removed

| Removed artifact | Location | Notes |
|-----------------|----------|-------|
| `--script` / `--script-type` flag | `init.py:734`, `init.py:982–992` | Entire flag and selection block |
| Script-type selection logic | `init.py:982–992` | 10 lines of dead branching |
| `copy_specify_base_from_local` script section | `template/manager.py:131–150` | Empty directories were being copied |
| `.kittify/scripts/bash/` directory | Package templates | No files exist; directory removed |
| `.kittify/scripts/powershell/` directory | Package templates | No files exist; directory removed |

### What Replaces It

Nothing needs to replace it — `shims/generator.py` is already the active mechanism and has been since before feature 076. This removal acknowledges that the replacement already happened and cleans up the vestigial script infrastructure.

```python
# Active dispatch (shims/generator.py) — already in place:
def write_agent_command(agent_root: Path, command_name: str, template: str) -> None:
    """Write a markdown command file into the agent's native command directory."""
    ...
```

### Consequences

#### Positive

* `--script` disappears from the init help output. New users no longer see a flag that has no effect.
* `init.py` is shorter and clearer. The script-type selection block is removed without replacement.
* `template/manager.py` no longer copies an empty directory tree.
* The codebase more accurately describes the active dispatch model.

#### Negative

* None. The code being removed has no runtime effect. No user observes a behavior change.

#### Neutral

* Developers familiar with the historical script model will notice the flag is gone. The change is described in migration notes.

### Confirmation

Correct behavior is confirmed when: `spec-kitty init --help` does not list `--script` or `--script-type`; and `spec-kitty init` completes without creating `.kittify/scripts/` in the project directory. Both conditions are covered by the init integration test suite.

## Pros and Cons of the Options

### Option A: Remove script directories, flag, and selection logic (chosen)

Delete all script-related code. `shims/generator.py` is the only dispatch model.

**Pros:**
* Dead code is removed, not hidden.
* The codebase accurately describes the active architecture.
* One dispatch model to understand, test, and document.

**Cons:**
* None identified.

### Option B: Keep scripts as fallback for agents that don't support markdown commands

Retain the script infrastructure in case a future agent requires shell dispatch.

**Pros:**
* Preserves optionality for hypothetical future agents.

**Cons:**
* All 13 currently supported agents use native markdown/text command files. No known agent requires shell dispatch.
* The infrastructure has no scripts in it — the fallback cannot function even if a hypothetical agent needed it.
* Speculative preservation of dead infrastructure blocks clarity.

**Why Rejected:** All 13 supported agents use markdown-based commands. If a future agent requires a different dispatch model, the appropriate approach is to implement that model at the time it is needed — not to maintain empty scaffolding for a requirement that does not exist.

### Option C: Deprecate with a warning, remove in a future release

Print a deprecation notice when `--script` is passed, then remove the flag in the next minor version.

**Pros:**
* Gives users advance notice.
* Follows standard deprecation practices.

**Cons:**
* The `--script` flag already has zero effect. There are no users depending on its behavior. Deprecation warnings are appropriate for flags that do something; they are noise for flags that do nothing.
* Deprecation extends the maintenance window by at least one release cycle for code that should be removed immediately.

**Why Rejected:** The standard deprecation argument assumes users depend on the flag's behavior. A flag that has been dead code since the shim model was introduced has no users to warn. Deprecating dead code is itself a code smell.

## More Information

* **Spec:** `kitty-specs/076-init-command-overhaul/spec.md` — "Flags to Remove" table (`--script` / `--script-type`), "Code Paths to Remove" table (`.kittify/scripts/bash/` and `powershell/` copying, script type selection)
* **Active replacement:** `src/specify_cli/shims/generator.py` — the active dispatch mechanism that made scripts obsolete
* **Related ADR:** ADR-F (2026-04-08-6) — Global agent commands supersede per-project copies (describes the shim-generated command files that replaced scripts)
* **Code locations:**
  * `src/specify_cli/init.py:734, 982–992` — flag definition and selection block
  * `src/specify_cli/template/manager.py:131–150` — script directory copying to be removed
