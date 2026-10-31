---
work_package_id: WP03
title: Legacy location discard
dependencies:
- WP01
requirement_refs:
- FR-009
- FR-010
- NFR-003
- SC-004
planning_base_branch: issue-6488-per-user-locations-single-authority
merge_target_branch: issue-6488-per-user-locations-single-authority
branch_strategy: Planning artifacts for this mission were generated on issue-6488-per-user-locations-single-authority. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6488-per-user-locations-single-authority unless the human explicitly redirects the landing branch.
subtasks:
- T009
- T010
- T011
- T012
phase: Phase 3 - Cleanup
history:
- timestamp: '2026-10-31T08:55:00Z'
  agent: python-pedro
  action: Prompt generated via /spec-kitty.tasks
authoritative_surface: src/kernel/
create_intent:
- src/kernel/user_dirs_legacy.py
- tests/kernel/test_user_dirs_legacy.py
execution_mode: code_change
owned_files:
- src/kernel/user_dirs_legacy.py
- src/specify_cli/__init__.py
- tests/kernel/test_user_dirs_legacy.py
- tests/performance/test_cli_startup_agent_commands_freshness.py
tags: []
tracker_refs: []
---

# Work Package Prompt: WP03 – Legacy location discard

## Objective

Remove the cache and marker directories the pre-convergence rules wrote, once, safely, and
without ever touching a path that is still live.

Read: `research.md` D5 and D6, `data-model.md` "Entity: Legacy location" and invariants
L1–L4.

## The trap this WP exists to avoid

On Linux the **pre-fix state root** (`$XDG_STATE_HOME/spec-kitty`, else the literal
`~/.cache/spec-kitty`) is the **post-fix cache root**. A naive "delete the old state
directory" step would delete `~/.cache/spec-kitty` — the live open-packs cache, the live
service cache and the live upgrade-check cache — on every Linux machine, including shared
build hosts. The rule is therefore: **never discard a candidate that is the current
directory of any kind** (cache, state, config). On Linux this makes the whole step a no-op;
that is the correct behaviour, not a missing feature.

## Red-first (T009)

`tests/kernel/test_user_dirs_legacy.py`, one shared fixture, both halves asserted together so
neither can drift:

- faked macOS with a planted `~/.cache/spec-kitty/upgrade-check.json`: the legacy root is
  **gone** after the discard, and the resolved `~/Library/Caches/spec-kitty` is **untouched**;
- faked Linux with a planted `~/.cache/spec-kitty/open-packs/`: still present afterwards
  (it is the live cache), and the resolved state directory `~/.local/state/spec-kitty` is
  untouched;
- a candidate that is a **symlink** to a directory outside the home folder: survives;
- a candidate containing a **git checkout**: survives (`remove_tool_owned_tree` raises
  `ToolOwnedPathUnproven`; the discard must catch it);
- a candidate whose removal **fails** (monkeypatched `Path`/`shutil` raising `OSError`):
  the function returns cleanly, logs at debug, writes nothing to stdout, and the caller's
  exit code is unchanged.

## Implementation (T010)

`src/kernel/user_dirs_legacy.py`:

- `legacy_cache_roots()`, `legacy_state_roots()`, `legacy_config_roots()` — tuples of
  `Path`, each derived from the **pre-fix** rules documented in `data-model.md`, with a
  comment naming the caller that wrote there;
- `discard_legacy_locations() -> tuple[Path, ...]` — returns what it actually removed;
  skips any candidate equal to `user_cache_dir()`, `user_state_dir()` or
  `user_config_dir()`; skips symlinks; delegates removal to
  `kernel.tree_removal.remove_tool_owned_tree(candidate, tool_root=<the base it came
  from>, reason="pre-#6488 spec-kitty cache/state", best_effort=True)`; catches
  `ToolOwnedPathUnproven` and `OSError`; never raises, never prints.
- Module docstring states L1–L4 and points at this WP's rationale.

Do **not** migrate anything: these are disposable caches plus one re-showable marker
(C-004).

## Wiring (T011)

Register the discard as a fourth owner in the CLI startup list in
`src/specify_cli/__init__.py` (`prepare_startup_assets(owners)`), labelled for the warning
text, e.g. `("per-user cache locations", discard_legacy_locations)`. Owner failures are
already isolated there (#6473) and the discard swallows its own errors anyway. Add a test
asserting the owner is present in that list, so a refactor cannot silently drop it.

## Validation

```bash
uv run pytest tests/kernel/test_user_dirs_legacy.py -q
uv run pytest tests/performance/test_cli_startup_agent_commands_freshness.py -q
uv run ruff check src/kernel/user_dirs_legacy.py src/specify_cli/__init__.py
uv run mypy src/kernel/user_dirs_legacy.py
```

## Definition of done

- One discard entry point, bounded to the enumerated legacy roots.
- Never deletes a current directory, a symlinked escape, or a git checkout.
- Runs at most once per process from the startup owners list; silent on failure.
- Red-first tests cover both halves (removed / preserved) on one fixture.
