---
title: 'Install-agnostic pre-commit hook fallback + spec-kitty migrate repin-hooks'
description: 'Pre-commit hook falls back to a PATH-resolved spec-kitty entrypoint when its pinned interpreter is gone, and a repair command re-pins already-broken repos.'
status: Accepted
doc_status: active
kind: ADR
date: '2026-08-27'
---
# Install-agnostic pre-commit hook fallback + `spec-kitty migrate repin-hooks`

**Filename:** `2026-08-27-1-precommit-hook-stable-entrypoint-and-repin-migration.md`

**Status:** Accepted

**Date:** 2026-08-27

**Deciders:** Robert (Human-in-Control), ratified 2026-08-27 on the issue

**Technical Story:** spec-kitty/EXPERIMENTAL-spec-kitty#254

---

## Context and Problem Statement

`src/specify_cli/policy/hook_installer.py` writes a `.git/hooks/pre-commit` shell script that
pins `sys.executable` — an absolute interpreter path — at install time, then `exec`s it
directly. This works until the install method changes: migrating a repo's spec-kitty install
from `pipx` to `uv tool install` moves (or removes) the pinned interpreter, and the *existing*
hook keeps pointing at a path that no longer exists. The next commit then fails at the shell
level with a bare `No such file or directory` naming a stale path — not a diagnosis, and no
command re-pins it.

Two prior regressions constrain the fix: #105 (the hook must not rely on a bare
`python`/`python3`/`py` resolved fresh off `PATH` — that lookup is exactly as fragile as the
absolute-path pin, just deferred) and #669 (the installer must preserve symlinks in
`sys.executable`, not resolve them — resolving strips a venv/pipx shim's `sys.prefix`
context).

## Decision Drivers

* No install method (pipx, uv, or anything else) should be able to leave a dead hook with no
  recovery path.
* The already-broken case (existing repos with a stale pin) needs a one-time repair, not just
  a fix for newly-installed hooks.
* Must not reintroduce #105 (bare `python` on `PATH`) or regress #669 (symlink preservation).
* The failure mode, when nothing is reachable, must name a concrete remedy — not surface a
  bare shell error.

## Considered Options

* **A.** Re-pin automatically on every commit (detect staleness, self-heal silently).
* **B.** Make the hook invoke a stable, install-agnostic entrypoint (`spec-kitty` resolved off
  `PATH`) as a fallback when the pinned interpreter is gone, **and** add a one-time
  `spec-kitty migrate repin-hooks` command for repos already broken. **(chosen)**
* **C.** Drop the absolute-path pin entirely; always resolve `spec-kitty` off `PATH`.

## Decision Outcome

**Chosen option: "B"**, matching the issue's ratified decision.

Concretely, as shipped:

- `hook_installer.HOOK_TEMPLATE` now guards the primary `exec` with `if [ -x "{interpreter}" ]`
  (pinned interpreter, preserved as a symlink per #669) and adds a second guarded branch:
  `if command -v {fallback_command}` execs `spec-kitty commit-guard-hook "$@"` resolved fresh
  off `PATH` at commit time. Neither branch is a bare, unguarded `python`/`python3` lookup, so
  #105 is not reintroduced.
- If neither the pinned interpreter nor `spec-kitty` on `PATH` is available, the hook exits 1
  with a message naming the concrete remedy: `spec-kitty migrate repin-hooks`.
- `spec-kitty commit-guard-hook` (`cli/commands/commit_guard_hook_cmd.py`, a hidden Typer
  command) is the install-agnostic fallback entrypoint — a thin `typer.Exit` wrapper around
  `specify_cli.policy.commit_guard_hook.main()`'s existing int return code.
- `spec-kitty migrate repin-hooks` (`cli/commands/migrate_cmd.py` +
  `cli/commands/migrate/repin_hooks.py`) re-runs the same install the `implement` lane already
  calls internally, re-pinning `.git/hooks/pre-commit` to the *current* interpreter. It takes
  no `--project-root` option (resolves the current repo via `locate_project_root()`, matching
  `backfill-identity`/`backfill-topology`), is idempotent, and does not depend on the hook it
  is repairing.

### Consequences

#### Positive
* An install-method migration (pipx -> uv, or any future method) can no longer leave a
  hook that hard-fails with an undiagnosable shell error — there is always a fallback path or
  a named remedy.
* Already-broken repos have a one-time, explicit repair command instead of requiring a manual
  hook reinstall.

#### Negative
* The hook script is slightly larger (two guarded `exec` branches instead of one) and takes a
  process-spawn cost for `command -v` on the (rare) fallback path.
* A second discovery mechanism (`PATH`-resolved `spec-kitty`) now exists alongside the pinned
  interpreter, which must both be kept working.

#### Neutral
* `spec-kitty migrate repin-hooks` mirrors the existing `migrate` subgroup's shape and adds no
  new CLI surface concepts.

### Confirmation

Success signals, verified at ship time: (1) with the pinned interpreter gone and `spec-kitty`
on `PATH`, a commit succeeds via the fallback branch; (2) with neither available, a commit is
blocked with the named remedy in stderr, not a bare shell path/126/127 error; (3)
`spec-kitty migrate repin-hooks` re-pins a hook to the current interpreter regardless of what
it was previously pinned to, and is idempotent.

## Pros and Cons of the Options

### A. Automatic silent self-heal on every commit
**Pros:** no user-visible repair step. **Cons:** silently rewriting a git hook on every commit
is a surprising side effect for something that should fail loudly and rarely; also does not by
itself cover the "neither entrypoint reachable" case, which still needs a named remedy.

### B. Install-agnostic fallback entrypoint + one-time repin command (chosen)
**Pros:** covers both the "hook still runs, just via a different path" case and the
already-broken repo case explicitly, with a named remedy when both are exhausted. **Cons:**
two code paths (pin + fallback) to maintain.

### C. Drop the pin, always resolve off `PATH`
**Pros:** simplest hook body. **Cons:** reintroduces #105's exact failure mode as the *only*
path (no absolute-path fast path), and loses the #669 symlink-preservation benefit of pinning
the exact interpreter the hook was installed under.

## More Information
- Issue: spec-kitty/EXPERIMENTAL-spec-kitty#254
- Related regressions: #105 (no bare `python` on `PATH`), #669 (preserve `sys.executable`
  symlinks, don't resolve).
- Standing distribution model (context, not directly actionable by this ADR): uv tool install
  from private GitHub Releases + `uv tool upgrade`.
