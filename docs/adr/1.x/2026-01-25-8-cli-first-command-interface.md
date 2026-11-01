---
title: CLI-First Command Interface
description: Requires every command to be fully drivable by flags and environment, with prompting as an optional layer, so CI and headless containers never stall on input.
status: Accepted
date: '2026-01-25'
doc_status: active
kind: ADR
updated: '2026-01-25T00:00:00Z'
---

## Context and Problem Statement

Spec Kitty commands currently mix interactive prompts with CLI flags. This makes
automation fragile and causes failures in non-TTY environments (CI, scripted
tests, headless containers). We need a consistent rule that every command can be
fully driven by CLI arguments without requiring interactive input, while still
allowing interactive UX when available.

## Decision Drivers

* CI/CD and automated testing must be reliable and deterministic.
* Non-TTY environments cannot use keypress-based menus.
* Agents and scripts should not need to simulate interactive input.
* Interactive UX is still valuable for humans at the terminal.
* Command behavior should be explicit, discoverable, and documented.

## Considered Options

* **Option 1:** CLI-first for all commands with optional interactive mode
* **Option 2:** Interactive-first with partial CLI overrides
* **Option 3:** Separate interactive and non-interactive command variants

## Decision Outcome

**Chosen option:** "Option 1: CLI-first for all commands with optional interactive mode",
because it guarantees automation compatibility while preserving interactive UX.
Every command must be fully operable via flags/env without prompting.

### Consequences

#### Positive

* All commands become scriptable and CI-friendly.
* Automated tests avoid brittle input mocking.
* CLI help becomes a complete contract for command behavior.
* Interactive UX remains available for manual use.

#### Negative

* More flags/options to maintain and document.
* Additional validation logic to reconcile interactive vs non-interactive paths.

#### Neutral

* Interactive prompts are treated as a convenience layer over CLI defaults.
* Non-interactive mode may require explicit flags for safety.

### Confirmation

We will validate this decision by:
* Ensuring every command has a complete CLI path with no required prompts.
* Maintaining CI tests that run commands in non-interactive mode.
* Auditing new commands for CLI completeness during review.

## Pros and Cons of the Options

### Option 1: CLI-first with optional interactive mode

**Pros:**

* Works in CI and automation by default
* Clear, testable command contract
* Keeps interactive UX for humans

**Cons:**

* Requires more flags and documentation
* Slightly more implementation complexity

### Option 2: Interactive-first with partial CLI overrides

**Pros:**

* Simpler UX for manual use
* Fewer flags to define initially

**Cons:**

* Automation remains brittle
* Non-TTY environments fail without workarounds
* Inconsistent behavior across environments

### Option 3: Separate interactive and non-interactive commands

**Pros:**

* Clear separation of concerns
* Simpler validation within each mode

**Cons:**

* Duplicated commands and help text
* Users must learn two interfaces
* Increased maintenance surface

## More Information

* Related implementation: `src/specify_cli/cli/commands/init.py` (non-interactive support)
* Docs: `docs/how-to/non-interactive-init.md`
