# Research: Golden-Path NFR Budget

Phase 0 output. This document grounds `plan.md`'s decisions in evidence gathered during
this planning pass — CI-gate verification against the live workflow files, and a hands-on
profiling investigation of `spec-kitty init`'s own cost, which turned out to be the single
most load-bearing finding for both Lever A and Lever C.

## CLI-startup cost decomposition (the load-bearing finding)

**Question**: FR-002/FR-003 both need a concrete mechanism. Spec.md deliberately names none
(Ruling 5 for FR-002; FR-003 cites only PR #4417's own "~0.2s/call Typer command-surface
construction" figure, itself derived from timing `spec-kitty --help`). Is `--help`'s measured
cost ($\approx$0.83s warm, per the readiness session) actually representative of a real
golden-path subcommand's startup cost?

**Method**: reproduced the isolated CLI-invocation environment `run_cli`/`run_cli_subprocess`
use (`PYTHONPATH` → `src/`, `SPEC_KITTY_TEMPLATE_ROOT` → repo root, `SPEC_KITTY_TEST_MODE=1`,
`NO_COLOR=1`), with `HOME` additionally overridden to a scratch directory (so this
investigation never touched the real `~/.kittify`). Ran `spec-kitty init . --ai codex
--non-interactive` against three successive fresh git repos under the same fake `HOME`:

| Run | HOME state | Instrumentation | Wall-clock |
|-----|-----------|------------------|-----------|
| 1 | cold (first-ever run) | none | 16.338s |
| 2 | warm (global asset cache already populated by run 1) | none | 9.094s |
| 3 | warm (same as run 2) | `cProfile` | 24.898s (instrumented; ≈9.2s uninstrumented-equivalent at cProfile's typical ~2.7x overhead, consistent with run 2) |

**Finding**: `cProfile`'s own cumulative-time report for run 3, sorted by cumulative time,
shows `ensure_global_agent_commands()` (`src/specify_cli/runtime/agent_commands.py:503`) at
14.941s cumulative — **≈60% of the whole invocation's profiled time** — almost entirely
inside `ruamel.yaml.main.load` (17.257s cumulative across 287 calls, reached via
`_render_agent_commands` → `render_command_template` → `render_template_text`). Reading
`assess_global_agent_commands()` (`src/specify_cli/runtime/agent_commands.py:343-420`)
confirms why: with `agent_keys=None` (the default `ensure_global_agent_commands()` passes,
called unconditionally from `main_callback()` at `src/specify_cli/__init__.py:145-152` on
every invocation not already fast-pathed for `next`/`live-work hook`/`session-start`), the
function iterates **every** key in `AGENT_COMMAND_CONFIG` (`src/specify_cli/core/config.py:55`
— 13 slash-command agents: claude, gemini, copilot, cursor, qwen, opencode, windsurf,
kilocode, auggie, q, kiro, antigravity, llxprt) and calls `_render_agent_commands(key, ...)`
for each — rendering all `PROMPT_DRIVEN_COMMANDS` (`src/specify_cli/shims/registry.py:57` —
8 commands) per agent, i.e. 104 template renders, **before** any comparison against existing
destination bytes. There is no freshness pre-check anywhere in the call chain: the function
always renders, then diffs; it never skips the render because "nothing changed since last
time."

**Why this survived `--help`-based measurement**: click processes `--help` as an eager option
during argument parsing and exits before a group's non-eager callback body executes. `--help`
therefore never reaches `main_callback`'s body at all — it does not pay `ensure_runtime()`,
`ensure_global_agent_skills()`, or `ensure_global_agent_commands()`'s cost. PR #4417's own
~0.2s/call figure and this session's readiness measurement (`spec-kitty --help` at 0.83s
warm) are both accurate measurements of `--help`'s own cost, but neither is a representative
proxy for a real subcommand invocation's cost — which is exactly what 9 of the golden path's
12 subprocess calls are (all except the two `next` calls, which use the existing
`_is_next_invocation` fast path).

**Reconciliation against the readiness session's own numbers**: the readiness session
measured the golden path's `call` phase (11 remaining subprocess calls after the fixture's
`init`) at 73.58s — averaging ~6.7s/call. If ~9 of those 11 calls each pay a multi-second
`ensure_global_agent_commands()` tax (consistent with, though likely smaller in absolute
terms on that machine than, this session's own ~5-17s range depending on instrumentation and
hardware), the arithmetic is consistent: a handful of seconds per non-fast-pathed call,
summed across ~9 such calls, plausibly accounts for the majority of the measured 73.58s,
with the two fast-pathed `next` calls contributing comparatively little.

**Mechanism chosen** (see `plan.md` §Lever C): add a freshness-stamp pre-check to
`assess_global_agent_commands()`, comparing CLI version + a content signature of the command
templates source directory + the resolved agent-key set against a stamp stored under
`home / "cache"` (the same cache root `AssetPreparation` already uses,
`src/specify_cli/runtime/asset_preparation.py:165-178`), short-circuiting before any
`_render_agent_commands()` call when the stamp matches.

**Mechanism considered and NOT chosen**: scoping `ensure_global_agent_commands()`'s
`agent_keys` to only the current project's configured agent(s) (read from
`.kittify/config.yaml`) instead of the full `AGENT_COMMAND_CONFIG` set. This would cut the
render workload proportionally (e.g. ~1/13 for a single-agent project) but changes the
*design intent* of the existing code — today, every invocation keeps ALL 13 agents' commands
globally warm regardless of which project/agent is active, so a user switching between
projects using different agents never pays a first-invocation cost for the "new" agent. The
freshness-stamp mechanism preserves that design intent (once warm, staying warm costs
~nothing regardless of agent-key scope) while fixing the actual structural defect (no
freshness check at all today), so it was preferred as the smaller, safer, more targeted fix.
This alternative is recorded here rather than silently discarded, per the charter's
`§Communication governance` traceability expectation — it is not proposed as a
NEEDS-OPERATOR-DECISION fork, since it is a plan-phase engineering choice between two
in-scope mechanisms for the same FR, not a scope/constraint question the spec or rulings left
open.

## CI-gate verification (live workflow files, not cached knowledge)

Read directly rather than assumed, 2026-09-23, against this checkout's actual
`.github/workflows/*.yml`:

- `ci-router.yml`'s `e2e` dorny filter group (lines ~178-180 at read time): maps only
  `tests/e2e/**` and `tests/cross_cutting/**`.
- `ci-router.yml`'s `cli` dorny filter group: maps only `src/specify_cli/cli/**`.
- `ci-router.yml`'s `tests-e2e` job (name `tests (e2e)`): `needs: [changes]`,
  `if: needs.changes.outputs.e2e == 'true'`, 25-minute timeout, runs `uv sync --frozen
  --all-extras && uv run --frozen pytest tests/e2e -q`. No `--durations` flag present today.
- `ci-router.yml`'s fail-closed `unmatched` catch-all: computes `matched=true` if ANY of a
  fixed list of named src-backed filter-group outputs is `true`; `unmatched = any_src AND NOT
  matched`. `cli` is in that list, and so is `next` — **corrected per round-2 fresh-sweep
  finding PLAN-FRESH-002** (this section previously carried the same disproven claim
  plan.md's own PLAN-VERIFY-004 had already fixed): `src/specify_cli/runtime/agent_commands.py`
  IS covered by the `next` filter group (`ci-router.yml:116-119`, matching
  `src/specify_cli/runtime/**`; the same path is separately duplicated by the
  `specify_cli_runtime` group, `ci-router.yml:160-163`). `next`'s output participates in the
  `unmatched` union computation (`ci-router.yml:218`), so a diff touching only
  `src/specify_cli/runtime/agent_commands.py` sets `next=true` and does NOT trip `unmatched`
  alone — it is a normally-matched change, not an unmapped one. It also directly gates
  `architectural-heavy` via `needs.changes.outputs.next == 'true'` (`ci-router.yml:523`). This
  mission's actual diff also touches `tests/e2e/**` and
  `src/specify_cli/cli/commands/__init__.py`, so `unmatched` does not fire for this PR either
  way (see `plan.md`'s Router-filter note, which carries the fuller explanation).
- `ci-aggregate.yml`'s `diff-cover` job: `--fail-under=90`, changed-critical-path lines only,
  consumes `ci-modules.yml`/`module-tests.yml`'s coverage artefacts rather than re-running
  tests.
- `module-tests.yml`: collects per-shard coverage (`--cov-report=xml`) as evidence; no
  `--cov-fail-under` flag found in this workflow. No separate "kernel/mission-loader coverage
  floor" gate exists as a distinct threshold in this checkout.
- `ci-router.yml`'s always-on jobs (no filter-group `if:` gating them): `ruff` (lint +
  format), `commit-msg` (informational only — `git log ... || true`, no assertion),
  `markdownlint` (`npx markdownlint-cli2 ... || true` — always exits 0), `uv-lock` (`uv lock
  --check`), `import-linter` (`ruff check --select TID251 .`), `regen-check` (`spec-kitty
  regen --check`), `terminology` (`tests/architectural/test_no_legacy_terminology.py`),
  `layer-rules` (`tests/architectural/test_layer_rules.py` +
  `test_pyproject_shape.py`), `archive-freeze`
  (`tests/architectural/test_archive_root_byte_identical.py`).
- `ci-router.yml`'s `architectural-heavy` job: code-scoped, triggered by an OR across every
  named src-backed filter-group output (including `cli`) — this mission's diff triggers it
  via the `cli` group.
- `ci-nightly.yml`'s `performance-and-e2e` job: `schedule`/`workflow_dispatch` triggers only
  (not `pull_request`), sets `SPEC_KITTY_RUN_PERFORMANCE=1` before running `pytest -m
  performance`. `tests/architectural/test_performance_marker_guard.py` asserts no
  `pull_request`-triggered workflow selects `-m performance`/`-m e2e` — confirmed this
  guard's existence (did not re-read its full body; existence + its docstring-level intent
  match the wall-clock-half placement this plan requires).
- No `bandit`, `pip-audit`, or `pip_audit` reference found anywhere under
  `.github/workflows/*.yml` (grepped, zero hits) — these tools are not part of this
  checkout's CI today, contrary to what a stale doctrine summary might imply.
- `ci-router.yml`'s `glossary` filter group maps only `src/glossary/**` — untouched by this
  mission's diff.

## Baseline commit for pre-existing-red comparison

The dispatch's own ground-truth section names `6b4164dbf` (the readiness session's checkout
SHA) as a reference point but explicitly warns it may not be the current merge-base. This
plan does not hardcode a SHA into the baseline procedure for that reason — `plan.md`'s
Baseline method section requires computing `git merge-base issue-4213-golden-path-nfr-budget
origin/main` at implementation time rather than trusting `6b4164dbf` directly, since `main`
may have advanced between the readiness session (2026-09-22) and implementation.

## Sources

- Direct reads: `src/specify_cli/__init__.py`, `src/specify_cli/cli/commands/__init__.py`,
  `src/specify_cli/cli/commands/init.py`, `src/specify_cli/runtime/agent_commands.py`,
  `src/specify_cli/runtime/asset_preparation.py`, `src/specify_cli/core/config.py`,
  `src/specify_cli/shims/registry.py`, `tests/e2e/conftest.py`,
  `tests/e2e/test_charter_epic_golden_path.py`,
  `tests/performance/test_cli_startup_budget_4409.py`, `.github/workflows/ci-router.yml`,
  `.github/workflows/ci-aggregate.yml`, `.github/workflows/module-tests.yml`,
  `.github/workflows/ci-nightly.yml`, `.github/workflows/ci-quality.yml`, `pyproject.toml`.
- Hands-on measurement: 3 timed `spec-kitty init` invocations (isolated env, fake `HOME`,
  scratch project directories) plus one `cProfile`-instrumented run, this planning session,
  2026-09-23. Raw outputs not committed (scratch/temp only, per the dispatch's "no absolute
  paths containing the OS username" rule for anything written into the mission dir — none of
  the profiling scratch files were copied into this repository).
- Not re-derived: the readiness session's own golden-path timing (127.55s total, 73.58s
  call + 29.36s setup) — cited as-is from `_readiness/4211/measured-results.md`, per the
  dispatch's instruction not to re-run the whole 127s test during planning.
