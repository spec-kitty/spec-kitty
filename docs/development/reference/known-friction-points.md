---
title: 'Known Current Friction Points'
description: 'A time-stamped, fast-drifting list of current repo and tooling friction points a maintainer or agent hits mid-mission; re-verify against the tracker before trusting specifics.'
doc_status: active
updated: '2026-10-01'
audience: docs/context/audience/internal/maintainer.md
type: reference
related:
- docs/development/how-to/pr-landing.md
- docs/development/getting-started/onboarding-run.md
- docs/development/testing/testing-flakiness.md
- docs/development/testing/testing-parallel.md
- docs/development/reference/red-main-and-release-readiness.md
- docs/adr/3.x/2026-07-17-1-red-main-is-honest-ci-is-release-authority.md
---
# Known Current Friction Points

> **This page is deliberately time-sensitive and drifts fast.** It captures
> repo and tooling friction that a maintainer — or an agent acting in a
> maintainer capacity — is likely to hit while running a mission *today*. It is
> **not** durable doctrine: specific issue numbers, version gates, and toggles
> change as the codebase moves. Always re-verify against the authoritative
> sources before trusting a specific number:
> [`CLAUDE.md`](../../../AGENTS.md) (its "Test-run baseline-red gotcha" note),
> [ADR 2026-07-17-1](../../adr/3.x/2026-07-17-1-red-main-is-honest-ci-is-release-authority.md),
> and the issue tracker.

**Snapshot date: 2026-09-30 · Spec Kitty 4.0.0rc5 (4.x cycle).** Proof that this list drifts:
`#2772` was a known-red P0 when this note was first drafted and has since been
closed — so the "known reds" below are already a different set than a month ago.

## The friction points

- **`main` may be legitimately RED.** Honest P0 reproductions are left red on
  purpose ([ADR 2026-07-17-1](../../adr/3.x/2026-07-17-1-red-main-is-honest-ci-is-release-authority.md));
  currently open examples: **#2736**, **#1834**. Before "fixing" any red,
  **attribute** it — reproduce on `upstream/main` / the merge-base. Never
  green-wash a `@pytest.mark.regression` red; that erases a deliberate
  release-blocker signal.
- **CI-environment false reds that pass locally:** auth
  (`logged_out_on_connected_teamspace`) and the pre-review gate opt-out
  (`SPEC_KITTY_SKIP_PRE_REVIEW_GATE`, its own name since #3980). Config, not
  your diff.
- **Stale-install false reds.** Commands that shell out to `spec-kitty` (e.g.
  the `merge-driver-*` commands) only reflect your working tree after
  `pip install -e .` / `uv pip install -e .`. Re-install after every rebase.
- **Stale-venv false reds.** A `ModuleNotFoundError` for a package that is
  declared and pinned usually means the `.venv` was never (re)synced, not a
  real regression — run `uv sync --frozen --all-extras` before recording it
  as pre-existing (#648).
- **The `pr:deferred` / `pr:skip-ci` labels skip some PR workflows — a green
  check can mean "not run," not "passed."** Jobs in `ci-windows.yml`,
  `check-spec-kitty-events-alignment.yml` and `release-readiness.yml` carry
  `if: !contains(github.event.pull_request.labels.*.name, 'pr:deferred') &&
  !contains(..., 'pr:skip-ci')`, so either label makes them report
  **skipped**. Check the PR's label list before treating an all-green run as
  evidence the change is safe; a skipped job is unverified, not clean. (See
  [pr-landing.md §4](../how-to/pr-landing.md) for how to classify checks once
  you *do* have real CI results to read.)
- **`charter lint`'s project-DRG input (`.kittify/doctrine/graph.yaml`) looks
  gitignored but is deliberately un-ignored — confirm it is tracked and
  in-diff before filing a lint finding.** `.gitignore` blanket-excludes
  `.kittify/doctrine/**` and then re-includes specific subpaths, including
  `!.kittify/doctrine/graph.yaml`; the file is meant to be committed and is
  the first candidate `charter_runtime/lint/_drg.py::_load_project_drg`
  reads (ahead of `merged_drg.json` / `drg.json` / `compiled_drg.json`). If
  it is stale or absent, `charter lint` silently falls back to
  `GraphState.BUILT_IN_ONLY` (or `MISSING`) and skips project-layer checks
  rather than failing loudly — so before treating a `charter lint` result as
  authoritative, confirm `git ls-files .kittify/doctrine/graph.yaml` shows it
  tracked and that `spec-kitty charter synthesize` regenerated it in your
  diff if doctrine artifacts changed.
- **In a lane or clone, a bare `python` / `pytest` imports the PRIMARY `src`, not
  your lane.** Always `uv run <cmd>`.
- **CI gates that pass locally, then fail on the PR:** the terminology guard
  (`terminology` job in `ci-router.yml`), the architectural battery (the
  always-on `architectural-fast` gate, which runs on every PR shape, plus the two
  code-scoped `architectural-heavy` legs), the canonical-producer lint (CP001 fires on a
  hand-rolled event dict with `event_type`+`payload` keys — build via
  `spec_kitty_events.lifecycle.*` instead; `scripts/lint_canonical_producers.py`),
  and the docs tests (`tests-docs` job). On the **rebased** tip, run the
  terminology guard, the specific `tests/architectural/` gate files your diff
  implicates (not the whole directory — see
  [`NO_FULL_HEAVY_SUITES_IN_MISSION`](../../../packs/internal/directives/no-full-heavy-suites-in-mission.directive.yaml);
  CI owns the full sweep), and
  `PYTHONPATH=. python scripts/docs/check_docs_freshness.py --ci` for docs
  changes before declaring a branch green.
- **No `git stash` in lane worktrees** — the stash stack is shared across
  worktrees, so a `pop` can steal a sibling lane's work-in-progress.
- **`move-task` can hang on fan-out.** Background it and set
  `SPEC_KITTY_NO_MOMENT_HANDLERS=1` (the old `SPEC_KITTY_SYNC_MINIMAL_IMPORT=1`
  spelling is still accepted as an alias, #3980).
- **After `finalize-tasks`, verify the issue-matrix / coordination state.** 3.2.6
  made the PRIMARY scaffolder idempotent; the coordination/consolidate reset
  path is not fully verified (not re-checked on 4.0.0rc5).
- **Docs scripts need `PYTHONPATH=.`**, and `build_cli_reference.py` defaults to
  the *wrong* output path — pass `--output docs/api/cli-commands.md
  --agent-output docs/api/agent-subcommands.md` explicitly.
- **Shared-package boundary:** anchor new runtime code in
  `src/runtime/next/_internal_runtime/`; the old `src/specify_cli/next/` shim
  was removed on 2026-07-03 — do not recreate it. Consume events / tracker
  only via `spec_kitty_events.*` / `spec_kitty_tracker.*`.
- **A pyenv-scoped editable `spec-kitty-cli` install shadows a pipx install.**
  Recurring: if `pyenv` manages the Python version active for this repo (a
  `.python-version` file, or `pyenv local`), an editable install left in that
  pyenv version's `site-packages` (an `_editable_impl_spec_kitty_cli.pth`
  pointing at some checkout's `src/`) resolves ahead of the pipx-installed
  `spec-kitty` on `PATH`, so the CLI silently runs a stale or unrelated
  checkout instead of the one you are working in. Detect:
  `which spec-kitty` (a pyenv shim, e.g. `~/.pyenv/shims/spec-kitty`, instead
  of the pipx shim under `~/.local/bin`) and `pip show -f spec-kitty-cli` in
  that pyenv version (an `_editable_impl_spec_kitty_cli.pth` / editable
  project-location entry is the tell). Fix: `pip uninstall spec-kitty-cli`
  inside the offending pyenv version, or reorder `PATH` so the pipx shim wins.
- **`.git/hooks/pre-commit` pins an absolute python interpreter.** The
  commit-guard hook Spec Kitty installs (`specify_cli.policy.hook_installer`)
  captures `sys.executable` at install time and hardcodes it into the hook —
  by design, so the hook does not depend on `PATH` (FR-009). Moving,
  deleting, or rebuilding `.venv` at a different location (a renamed clone, a
  relocated checkout) leaves the pinned path dangling. Symptom: `git commit`
  fails because the hook's interpreter path no longer exists. Fix: if only
  the interpreter binary vanished, `uv sync --frozen --all-extras` rebuilds
  `.venv` at the same path and the existing hook resolves again; if the
  checkout itself moved, delete `.git/hooks/pre-commit` and re-run
  `spec-kitty implement <any-WP>` (or any path that allocates a lane
  worktree) to regenerate the hook pinned to the new location.

## Maintaining this page

When you hit a new mid-mission friction point — or when one above stops being
true (a known-red P0 closes, a toggle is retired, a version gate passes) —
update this page and bump the snapshot date **and the version tag** in the same
change. Keep entries
short and actionable; deep rationale belongs in the linked runbooks, not here.

## See also

- [Landing contributor PRs](../how-to/pr-landing.md) — the maintainer landing runbook.
- [Onboarding run](../getting-started/onboarding-run.md) — the mission-run priming prompt that
  points here.
- [Test-flakiness handling policy](../testing/testing-flakiness.md) — the never-retry-to-green rule.
- [Red main and release readiness](red-main-and-release-readiness.md).
