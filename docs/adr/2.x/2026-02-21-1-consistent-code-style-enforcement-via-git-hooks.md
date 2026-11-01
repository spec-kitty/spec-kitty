---
title: Consistent Code Style Enforcement via Git Hooks
description: Runs ruff format, ruff check, and mypy over staged files at commit time, accepting an opinionated formatter in exchange for feedback that beats the CI round trip.
status: Accepted
date: '2026-02-21'
doc_status: active
kind: ADR
updated: '2026-02-21T00:00:00Z'
---

## Context and Problem Statement

The spec-kitty codebase had no automated style enforcement at commit time. Formatting inconsistencies and lint violations would only surface during CI (after push), creating slow feedback loops and noisy diffs that mix style fixes with functional changes.

Python's formatter ecosystem offers opinionated tools (Black, ruff format) that eliminate style debates but impose constraints: they are length-based and do not support per-construct formatting rules. For example, Black/ruff format will collapse a multi-line comprehension with `for`/`if` clauses onto a single line if it fits within the configured line length. There is no option to force line breaks between `for` and `if` clauses independently of line length.

We evaluated whether custom lint rules could extend ruff's formatter to cover these preferences, but ruff (like Black) has a closed rule set with no plugin or extension system. Unlike JavaScript's ESLint or Rust's rustfmt, Python's formatting tools do not support layering custom rules on top of a baseline style.

## Decision Drivers

* Catch lint and format violations before they reach CI
* Eliminate style debates in code review
* Incremental enforcement — only check files being committed, not the entire codebase
* Validate commit messages before they reach the remote (commitlint)
* Accept minor personal style preferences as trade-offs for consistency

## Considered Options

* **Option 1:** No local enforcement (rely on CI only)
* **Option 2:** ruff format (Black-compatible) + ruff check + mypy via git hooks
* **Option 3:** ruff format + custom AST-based lint script for per-construct rules
* **Option 4:** Lower line-length to force natural line breaks on long constructs

## Decision Outcome

**Chosen option:** "Option 2: ruff format (Black-compatible) + ruff check + mypy via git hooks", because:

* It provides immediate feedback at commit time with zero CI wait
* Black-compatible formatting is the dominant Python standard, reducing onboarding friction
* Incremental enforcement (staged files only) avoids a mass-reformatting commit
* The trade-off of losing some multi-line formatting preferences (e.g., comprehension clause separation) is acceptable for the consistency gained

### Trade-offs Accepted

* **Comprehension formatting:** `for`/`if` clauses in comprehensions may collapse to a single line at `line-length = 120`. We accept this because there is no way to enforce per-construct line breaks in Black/ruff format without a plugin system, and writing a standalone AST checker for a single style preference adds maintenance burden disproportionate to the benefit.
* **Line length 120:** Wider than Black's default of 88. Chosen to match the existing codebase style, but it causes more expressions to fit on a single line. Reducing to 88 would restore more multi-line formatting but would require reformatting a significant portion of the codebase.

### Consequences

#### Positive

* Style violations caught before push, not after CI
* Commit messages validated against conventional commits before reaching the remote
* No style debates in code review — the formatter decides
* Incremental adoption — only touched files are checked

#### Negative

* Contributors must run `git config core.hooksPath .githooks` once after cloning
* Some multi-line formatting preferences cannot be expressed in Black/ruff format
* mypy strict mode on staged files may flag pre-existing issues in modified files

#### Neutral

* Hooks are versioned in `.githooks/` (not `.git/hooks/`) for portability
* CI continues to run the same checks as a safety net

## Implementation

### Git Hook Setup

Hooks are stored in `.githooks/` and activated per-clone:

```bash
git config core.hooksPath .githooks
```

### pre-commit Hook

Runs on staged `.py` files only (Added, Copied, Modified, Renamed):

1. `ruff format --check` — verify Black-compatible formatting
2. `ruff check` — lint rules (import order, unused imports, etc.)
3. `mypy --strict` — type checking (src/ files only)

### pre-push Hook

Runs on commits about to be pushed:

1. Determines commit range (remote SHA → local SHA)
2. Runs `commitlint` with `@commitlint/config-conventional`
3. Handles new branches (uses merge-base with default branch)

### Ruff Configuration

In `pyproject.toml`:

```toml
[tool.ruff]
line-length = 120

[tool.ruff.format]
quote-style = "double"
indent-style = "space"
line-ending = "auto"
```

## Future Considerations: Bootstrap Phase Integration

When spec-kitty gains a `bootstrap` or `init` phase (for onboarding new projects), it should:

1. **Prompt the user for their preferred code style guide** — e.g., Black (Python), Prettier (JS/TS), rustfmt (Rust), or a custom configuration
2. **Prompt for linting configuration** — e.g., ruff rule selection, ESLint config, clippy lints
3. **Generate `.githooks/` with appropriate pre-commit and pre-push hooks** tailored to the project's language and style choices
4. **Set `core.hooksPath`** automatically during bootstrap
5. **Store the style configuration** in the project's spec-kitty config (`.kittify/config.yaml`) so that migrations and upgrades can regenerate hooks if the hook templates evolve

This would make consistent style enforcement a first-class citizen of every spec-kitty project, not just spec-kitty itself. The hook templates could live alongside mission templates in `src/specify_cli/missions/` and be deployed the same way slash command templates are today.

## Pros and Cons of the Options

### Option 1: No Local Enforcement (CI Only)

**Pros:**
* Zero setup for contributors
* No local tooling requirements

**Cons:**
* Style violations only caught after push (slow feedback)
* Noisy PRs mixing style fixes with functional changes
* Commit message violations discovered late

### Option 2: ruff format + ruff check + mypy via Git Hooks

**Pros:**
* Immediate feedback at commit/push time
* Black-compatible formatting is industry standard
* Incremental enforcement on staged files only
* Hooks are versioned and portable

**Cons:**
* Requires one-time `git config` setup per clone
* Cannot express all formatting preferences (e.g., comprehension clause breaks)

### Option 3: ruff format + Custom AST Lint Script

**Pros:**
* Could enforce per-construct formatting rules (e.g., multi-line comprehensions)
* Full control over style beyond what Black offers

**Cons:**
* Maintenance burden for a custom linter
* Fragile — AST-based checks may not handle all edge cases
* Non-standard tooling that new contributors won't recognize
* Disproportionate effort for marginal style preferences

### Option 4: Lower line-length to 88 (Black Default)

**Pros:**
* More expressions naturally stay multi-line
* Matches Black's default, familiar to most Python developers

**Cons:**
* Would require reformatting ~400+ files in the existing codebase
* 88 chars may feel restrictive for a codebase already written at ~120
* Doesn't actually solve the per-construct problem — just makes it less frequent

## More Information

### Activating Hooks

After cloning the repository:

```bash
git config core.hooksPath .githooks
```

### Related Files

* `.githooks/pre-commit` — format + lint + type check on staged files
* `.githooks/pre-push` — commitlint on outgoing commits
* `pyproject.toml` — ruff and mypy configuration
* `commitlint.config.cjs` — conventional commit rules
* `package.json` — `@commitlint/config-conventional` dependency

### Related Decisions

* Standardized automated quality gates ADR (planned but not published) — CI-level quality enforcement that these hooks complement locally
