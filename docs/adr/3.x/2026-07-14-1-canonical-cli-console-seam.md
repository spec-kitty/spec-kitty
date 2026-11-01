---
title: 'ADR: Canonical CliConsole seam — one CLI output object, plain --json, object-not-env determinism'
description: 'Why Spec Kitty routes all CLI output through a single CliConsole seam: plain --json by construction, colour toggled on the object (never os.environ), no shim, CLI-layer scope.'
status: Accepted
date: '2026-07-14'
doc_status: active
kind: ADR
updated: '2026-07-14T00:00:00Z'
---

# Canonical CliConsole seam — one CLI output object, plain `--json`, object-not-env determinism

**Status:** Accepted

**Date:** 2026-07-14

**Deciders:** Stijn Dejongh (operator), Claude (Opus 4.8)

**Technical Story:** Fixes [#2632](https://github.com/Priivacy-ai/spec-kitty/issues/2632); shipped in mission #2620 / PR #2629. Deferred non-CLI scope tracked as [#2634](https://github.com/Priivacy-ai/spec-kitty/issues/2634).

---

## Context and Problem Statement

The Claude Code harness (and many developer shells / CI agents) exports `FORCE_COLOR=3`. Rich honours `FORCE_COLOR` **above** `NO_COLOR`/`TERM=dumb` and decides colour at *render* time, and every command module constructed its own module-level `console = Console()` that **snapshots the ambient colour environment at import time**. Two failures fell out of this (#2632, ~81 pre-existing red tests across ~15 files):

- **(a) `--json` corruption.** `console.print_json(json.dumps(payload))` syntax-highlights the JSON, so under forced colour the machine output carries ANSI escapes and `json.loads(result.output)` raises `Expecting value: line 1 column 1`. This is a real user-facing bug, not just a test artefact: any caller piping `spec-kitty … --json | jq` under a colour-forcing harness gets corrupt output.
- **(b) substring brittleness.** Styled human output splits literal substrings (`"delivered 1"` renders as `delivered \x1b[0m\x1b[1;32m1\x1b[0m`), so `assert "x" in result.output` false-REDs even though the behaviour is identical to CI's plain environment.

An existing fix existed but was scoped to exactly one directory (`tests/specify_cli/cli/commands/agent/conftest.py`), and it worked by *enumerating and monkeypatching each module's console* — the fragile whack-a-mole this ADR eliminates.

## Decision Drivers

- **`--json` must be plain by construction**, independent of terminal, env, or harness — machine output is data, never a styled display.
- **Determinism must be a property of the object, not the environment.** Mutating `os.environ["NO_COLOR"]` in a fixture *works* but leaks into subprocesses and sibling tests — rejected by the operator.
- **No shim, no new debt.** This lands inside a debt-*reduction* mission; the shared console is to be *moved*, not shadowed by a back-compat re-export.
- **Single seam.** One object every module shares, so colour policy (and future output policy) is changed in one place — not re-derived per module.
- **Drop-in compatibility.** The seam is passed to `Live(console=…)`, `Progress(console=…)`, and functions typed `console: Console`, so it must *be* a `rich.console.Console`, not a proxy.

## Considered Options

1. **Harden the ~81 assertions** to strip ANSI / parse structured output. Rejected: 81 spot-fixes, masks the product `--json` bug, and the next styled-output test re-hits it.
2. **Suite-level conftest that sets `NO_COLOR` in `os.environ`.** Rejected: env mutation leaks into subprocesses and neighbouring tests, and does not fix the product bug for real `--json` consumers.
3. **Pin/downgrade `rich`.** Rejected: chases a moving dependency, doesn't encode the invariant, and doesn't address `FORCE_COLOR` semantics (which are correct — the app was wrong to route machine output through a styled console).
4. **A canonical `CliConsole` seam (chosen).** One shared `Console` subclass whose `--json` output is plain by construction and whose colour is toggled *in place on the object* for tests.

For the seam's home we considered `src/kernel/cli/`, but `kernel` is the zero-dependency import floor (its README forbids CLI/rich concerns and any spec-kitty-package imports). CLI output is a `specify_cli` concern — so the seam lives at `src/specify_cli/cli/console.py`.

## Decision Outcome

**Chosen option:** a single canonical `CliConsole` seam, because it fixes both the product `--json` corruption and the test brittleness at one point, with no env mutation and no shim.

- `src/specify_cli/cli/console.py` defines `class CliConsole(Console)` and the shared singletons `console` (stdout) and `err_console` (stderr).
- `emit_json(payload)` / `print_json(...)` **bypass Rich's highlighter and write plain JSON** — so every existing `--json` call site becomes safe simply by routing through the seam.
- `set_plain(bool)` toggles colourless rendering **in place** (`no_color=True`, `_color_system=None`). Because it subclasses `Console`, it is a drop-in for `Live`/`Progress`/`console: Console`; and because every module imports the *same* singleton, one `set_plain(True)` call in a single autouse fixture neutralises colour across the whole suite — no `os.environ` involved.
- The whole **CLI layer** (`cli/` + `cli/commands`, ~77 ad-hoc `Console()` constructions) is **moved** onto the seam; the old definitions are deleted, and the 18 `from …cli.helpers import console` importers are repointed to `…cli.console` (no shim). A structural guard (`tests/architectural/test_cli_console_single_seam.py`) forbids raw `Console(...)` anywhere under `src/specify_cli/cli/` except the seam module.

### Consequences

#### Positive

- `--json` output is plain and `jq`-safe regardless of `FORCE_COLOR`/terminal — a real product-correctness fix, not just green tests.
- Test determinism is achieved by configuring one object; no environment mutation, no per-module console monkeypatching (the fragile `agent/conftest.py` enumeration collapses to one `set_plain` call).
- ~77 ad-hoc `Console()` constructions eliminated; the arch guard keeps the seam singular by construction (debt reduction that holds).

#### Negative

- A large mechanical diff folded into an already-large PR.
- The seam covers the CLI layer only. ~14 non-CLI module-level consoles remain (`sync/`, `readiness/`, `retrospective/`, `core/`, `identity/`, `charter_runtime/`, `template/`, `upgrade/`), and **one of them — `retrospective/cli.py:277` `_console.print_json` — is an active `--json` corruption vector** with the same root cause. These are **deferred to [#2634](https://github.com/Priivacy-ai/spec-kitty/issues/2634)**, not because they are safe, but because migrating them cleanly requires resolving a **layering question**: those are lower-layer packages, and importing `cli.console` from them would invert the dependency direction. The right fix is likely to relocate the seam to a home both layers can import (e.g. a `specify_cli`-root console module) — a design decision that deserves its own change rather than a rushed rider here.

#### Neutral

- The few deliberately-special CLI consoles (`width=200`/`width=120`/`highlight=False`/dynamic `color_system`) remain distinct instances, but of the seam class (`CliConsole(...)`), so they still get plain `--json` and `set_plain`.

### Confirmation

- `tests/architectural/test_cli_console_single_seam.py` (AST guard: no raw `Console(...)` under `cli/` outside the seam) + a non-vacuity companion.
- Fast unit tests for `CliConsole` (`emit_json`/`print_json` plain under `force_terminal=True`; `set_plain` in-place toggle; `err_console` targets stderr).
- The #2632 files pass under `FORCE_COLOR=3`, and a regression constructs a colour-forced `CliConsole` and asserts `--json` output carries no `\x1b` and `json.loads` succeeds.
