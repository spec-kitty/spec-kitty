---
title: 'ADR 4 (2026-04-08): Charter and Doctrine Are Not Init-Time Concerns'
description: 'Strips the doctrine interview and default application out of init; a charter is authored afterwards via /spec-kitty.charter against an already-created project.'
status: Accepted
date: '2026-04-08'
doc_status: active
kind: ADR
updated: '2026-04-08T00:00:00Z'
---

## Context and Problem Statement

`spec-kitty init` accumulated a large body of charter and doctrine logic over time. As of feature 076, the init command contains three major charter/doctrine functions that run during every initialization:

1. **`_run_doctrine_stack_init()`** (`init.py:520–572`): Runs a doctrine stack interview, asking the developer a series of questions about project governance: tech stack, development philosophy, team norms, and agent behavior preferences. Writes answers to `kitty-specs/doctrine/`.

2. **`_run_inline_interview()`** (`init.py:433–516`): An interactive prompt sequence that collects charter-level project metadata before the user has made any decisions about what the project actually is.

3. **`_apply_doctrine_defaults()`** (`init.py:392–429`): Applies a set of inferred default doctrine values based on detected project characteristics.

These three functions account for hundreds of lines of init and represent a substantial portion of the init runtime when run interactively.

**The fundamental architectural error:** All three functions run at machine-initialization time, before the user has a project. Charter and doctrine describe a specific project's governance — its team conventions, its technology choices, its agent escalation policies. None of these decisions can be made meaningfully before a project exists.

**How it accumulated:** spec-kitty was originally a per-project tool. Running `spec-kitty init` inside a project directory was the correct entry point. Charter questions ran after the project existed. When the global runtime model was introduced (see ADR-A), `spec-kitty init` became a machine-level setup command, but the charter/doctrine code was never removed. The result is a machine setup command that asks project-specific questions before any project exists.

**Impact:** New developers are confronted with project governance questions during what should be a simple machine setup. If they guess at answers (the only option), those answers accumulate as authoritative doctrine in the global runtime — creating misleading governance artifacts that apply to no specific project.

## Decision Drivers

* **Logical ordering:** A developer cannot answer project-specific questions before the project exists.
* **Correct command surface:** `spec-kitty init` configures the machine. Charter is authored via `/spec-kitty.charter` after `/spec-kitty.specify` creates the project.
* **Reduced init complexity:** Removing the charter stage cuts hundreds of lines from init.py and eliminates `test_init_doctrine.py` entirely.
* **User experience:** Machine setup should be fast and unambiguous. Charter authoring is a richer, deliberate process that belongs in a project context.

## Considered Options

* **Option A: Remove charter/doctrine entirely from init (chosen)**
* **Option B: Keep charter in init, make it optional via a flag**
* **Option C: Move charter to a `spec-kitty setup` per-project command**

## Decision Outcome

**Chosen option: Option A — All charter/doctrine code is removed from `spec-kitty init`. Charter is authored via `/spec-kitty.charter` after the project is created.**

### What Is Removed

| Removed code | Location | Lines |
|-------------|----------|-------|
| `_run_doctrine_stack_init()` | `init.py:520–572` | ~50 lines |
| `_run_inline_interview()` | `init.py:433–516` | ~80 lines |
| `_apply_doctrine_defaults()` | `init.py:392–429` | ~35 lines |
| Call site for doctrine stage | `init.py:1261` | 1 line |
| `test_init_doctrine.py` | `tests/` | Entire file deleted |

### The Correct Workflow

```
Machine setup:
  spec-kitty init                    # Bootstrap ~/.kittify/, configure agents

Project creation:
  spec-kitty init my-new-project     # Create project directory + minimal scaffold
  cd my-new-project
  /spec-kitty.specify [description]  # Define project goals + mission
  /spec-kitty.charter                # Author project governance (charter + doctrine)
  /spec-kitty.plan                   # Plan features
```

Charter belongs at step 4 — after the developer knows what the project is, who is working on it, and what governance norms apply.

### Consequences

#### Positive

* init is simpler, faster, and logically coherent.
* Developers are not asked project-specific questions during machine setup.
* No doctrine artifacts are created before a project exists; the global runtime contains no project-specific data.
* `test_init_doctrine.py` is deleted entirely, reducing the test surface area.
* Three large function definitions removed from `init.py`, reducing maintenance burden.

#### Negative

* Developers who relied on init to bootstrap charter artifacts must use `/spec-kitty.charter` instead. This is a workflow change for existing users, but the new workflow is logically correct.
* Documentation that describes charter-during-init must be updated.

#### Neutral

* The charter authoring capability is unchanged; only its entry point moves from `spec-kitty init` to `/spec-kitty.charter`.

### Confirmation

Correct behavior is confirmed when: running `spec-kitty init` on a machine with no existing projects produces no files in `kitty-specs/doctrine/` and issues no charter-related prompts. Confirmed by integration tests and by verifying that `_run_doctrine_stack_init`, `_run_inline_interview`, and `_apply_doctrine_defaults` do not appear in `init.py`.

## Pros and Cons of the Options

### Option A: Remove charter/doctrine from init entirely (chosen)

Delete `_run_doctrine_stack_init()`, `_run_inline_interview()`, and `_apply_doctrine_defaults()`. Charter is authored exclusively via `/spec-kitty.charter`.

**Pros:**
* Logically correct: project governance cannot be authored before the project exists.
* Simpler init; faster machine setup.
* One clear answer to "where do I write my charter?": `/spec-kitty.charter`.

**Cons:**
* Existing users who relied on init for charter must update their workflow (minor; new workflow is better).

### Option B: Keep charter in init, make it optional via a flag

Retain the charter/doctrine functions but gate them behind a `--with-charter` flag. Skip by default.

**Pros:**
* Preserves backward compatibility for users who liked running charter during init.
* No user workflow change.

**Cons:**
* The code remains in `init.py` even though the default path skips it.
* The flag encourages the logically wrong workflow (running charter before a project exists).
* Every init flag is a maintenance commitment. A flag for a wrong workflow is a maintenance commitment to a wrong workflow.

**Why Rejected:** Optional code is still code. The workflow is wrong regardless of whether it is gated. The right answer is to remove it and document the correct workflow.

### Option C: Move charter to a `spec-kitty setup` per-project command

Create a new `spec-kitty setup` command that handles per-project initialization including charter. Remove charter from init.

**Pros:**
* Distinguishes machine init from project init at the CLI command level.
* `spec-kitty setup` would be the natural home for charter, `.gitignore` writing, and other per-project concerns.

**Cons:**
* Creating `spec-kitty setup` is a significant new surface area.
* `/spec-kitty.charter` already exists and is the intended charter authoring surface.
* Implementing `spec-kitty setup` in the context of feature 076 would expand scope beyond the init overhaul.

**Why Rejected:** `/spec-kitty.charter` is the correct and already-implemented charter authoring surface. A new `spec-kitty setup` command is the right long-term direction but is out of scope for feature 076. The per-project setup concern is documented as a Non-Goal in the spec.

## More Information

* **Spec:** `kitty-specs/076-init-command-overhaul/spec.md` — FR-015 (command completes without creating or prompting about charter, doctrine, missions, REPO_MAP/SURFACES, or dashboard), Non-Goals section ("Per-project setup... belongs in a future `spec-kitty setup`")
* **Related ADR:** ADR-A (2026-04-08-1) — Global `~/.kittify/` as machine-level runtime (establishes the machine/project boundary that makes this separation necessary)
* **Related ADR:** ADR-6 (2026-01-23-6) — Config-driven agent management
* **Code locations:**
  * `src/specify_cli/init.py:392–572` — the three doctrine functions to be removed
  * `src/specify_cli/init.py:1261` — call site for `_run_doctrine_stack_init`
  * `tests/specify_cli/test_init_doctrine.py` — test file to be deleted
