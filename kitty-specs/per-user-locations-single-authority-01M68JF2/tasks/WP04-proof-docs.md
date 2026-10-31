---
work_package_id: WP04
title: Mutation proof, changelog and docs
dependencies:
- WP02
- WP03
requirement_refs:
- FR-011
- NFR-004
- NFR-005
- SC-005
planning_base_branch: issue-6488-per-user-locations-single-authority
merge_target_branch: issue-6488-per-user-locations-single-authority
branch_strategy: Planning artifacts for this mission were generated on issue-6488-per-user-locations-single-authority. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6488-per-user-locations-single-authority unless the human explicitly redirects the landing branch.
subtasks:
- T013
- T014
- T015
- T016
phase: Phase 4 - Proof and documentation
history:
- timestamp: '2026-10-31T08:55:00Z'
  agent: python-pedro
  action: Prompt generated via /spec-kitty.tasks
authoritative_surface: docs/adr/
create_intent: []
execution_mode: code_change
owned_files:
- docs/adr/**
- docs/changelog/CHANGELOG.md
- docs/development/how-to/service-pins.md
- docs/development/how-to/sync-packs.md
- docs/guides/how-to/installation/install-and-upgrade.md
- src/charter/offering/packs/**
- src/kernel/**
- src/runtime/next/**
- src/specify_cli/compat/**
- src/specify_cli/core/**
- tests/architectural/test_no_legacy_terminology.py
tags: []
tracker_refs: []
---

# Work Package Prompt: WP04 – Mutation proof, changelog and docs

## Objective

Prove the guard is not vacuous, then land the user-facing record of a change that moves
files on disk.

## T013 — Mutation proof (SC-003)

For each of the six callers, in turn: put the pre-fix rule back
(`user_cache_dir() / "spec-kitty" / <subpath>`, or for `compat/cache` the direct
`platformdirs.user_cache_dir("spec-kitty")` call), run
`uv run pytest -q -k user_dirs_convergence` (WP02's guard), confirm it **fails and names
that caller**, then restore the file. Record all six results (the failing assertion line)
in `traces/approach.md` of this Mission's directory.

A caller whose revert leaves the suite green is not covered by the guard: fix the guard
before recording the result.

## T014 — Changelog (SC-005)

One `[Unreleased]` entry in `docs/changelog/CHANGELOG.md` (root `CHANGELOG.md` is a
symlink to it). Impact-first bold lead with `(#6488)`, then **before** and **after**, under
1,200 characters. It must say:

- `platformdirs` is now the one rule for per-user cache, state and config;
- macOS: `~/Library/Caches/spec-kitty` (cache) and `~/Library/Application Support/spec-kitty`
  (state and config) — cache and marker files move there;
- Windows: `%LOCALAPPDATA%\spec-kitty\Cache` and `%LOCALAPPDATA%\spec-kitty`;
- Linux: unchanged except the one-time marker, which moves to
  `${XDG_STATE_HOME:-~/.local/state}/spec-kitty`;
- the old locations are discarded on the next command (disposable caches; nothing is
  migrated), and XDG variables still win on every platform.

## T015 — Docs (FR-011)

Update the pages that name a cache path so they state the rule rather than one Linux path:

- `docs/development/how-to/sync-packs.md` — `open-packs` cache location and the remedy in
  its `PACK_DIGEST_MISMATCH` row;
- `docs/development/how-to/service-pins.md` — the service-asset cache location and the
  remedy rows;
- `docs/guides/how-to/installation/install-and-upgrade.md` — the upgrade-nag cache path.

Keep the Linux path visible (`${XDG_CACHE_HOME:-~/.cache}/spec-kitty/...`) and add the macOS
and Windows equivalents in one sentence each. Do not edit a historical ADR under the repository's
`docs/adr` tree — those are records, not current guidance.

## T016 — Verification sweep

```bash
uv run python -m scripts.docs.check_docs_freshness --ci          # errors=0
uv run pytest tests/architectural/test_no_legacy_terminology.py -q
uv run ruff check src/kernel src/charter/offering/packs src/runtime/next src/specify_cli/compat src/specify_cli/core
uv run mypy src/kernel/user_dirs.py src/kernel/user_dirs_legacy.py
```

Then set the issue-matrix verdict for #6488 (implemented) and report the exact commands and
exit codes in the PR's `## Tests run`.

If `check_docs_freshness` reports a diff you did not cause (shared machine state, another
agent rewriting the global asset cache), record it in the PR's `## Deferred` with the
reason instead of regenerating the whole reference.

## Definition of done

- Six of six mutation reverts detected, recorded in the tracer.
- Changelog entry present, under the limit, with before/after and `(#6488)`.
- Three how-to pages state the platform rule; docs freshness errors=0.
- No ADR edited; no full heavy suite run.
