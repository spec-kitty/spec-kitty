---
title: Targeted Cleanup Scoping — sync.py and walker.py
description: 'Line-level scoping of the two highest-signal code-quality cleanup targets: the calibration/walker.py duplicated-literal cluster and the cli/commands/sync.py complexity god-module.'
doc_status: active
updated: '2026-09-30'
audience: docs/context/audience/internal/maintainer.md
related:
- docs/plans/code-quality/index.md
- docs/archive/plans/refactor/degod-unshim-roadmap.md
---
# Targeted Cleanup Scoping — `sync.py` and `walker.py`

> **Status (2026-09-30).** The `sync.py` half of this page is void:
> `src/specify_cli/cli/commands/sync.py` was removed with the sync transport (the
> Convergence, #3881). The `walker.py` half still applies (`src/specify_cli/calibration/walker.py`
> exists). `merge/bookkeeping_projection.py` is now
> `consolidation/bookkeeping_projection.py`. Current Sonar priorities are the 4.0.0 series in
> the [4.0.0 Milestone Roadmap](../4-0-0-milestone-roadmap.md).

Line-level scoping of the two highest-signal cleanup targets surfaced by the
2026-08-12 SonarCloud snapshot (see [Code Quality index](index.md) for the full
picture). Effort figures are SonarCloud's own remediation estimates; the risk and
sequencing judgement is ours.

The two files tell opposite stories: `walker.py` is a fully safe mechanical sweep that
can land today; `sync.py` mixes cheap safe wins with two genuine refactors that must
ride a degod wave.

## `src/specify_cli/calibration/walker.py` — safe, immediate (~2h)

533 LOC, **14 smells, all `S1192`** (duplicated string literals), ~1h50m Sonar effort.
Zero structural risk: the findings are all inside the module-level `_REQUIRED_SCOPE`
lookup table — a static `dict[tuple[str, str], frozenset[str]]` mapping
`(mission_type, action_urn)` to the doctrine URNs the step directly requires.

### What the findings are

The table hand-lists doctrine URNs, and many are raw duplicated strings:

- action-URN prefixes — `"action:software-dev/..."` (L113, L134, L164)
- directive URNs — `"directive:DIRECTIVE_024"` / `025` / `028` / `029` / `030` / `034`
  (L129, L136-140)
- tactic URNs — `"tactic:acceptance-test-first"`, `"tactic:quality-gate-verification"`,
  `"tactic:stopping-conditions"` (L141, L144, L145)
- agent-profile URNs — `"agent_profile:r..."`, `"agent_profile:c..."` (L300, L308)

### Why it is safe

The module **already** has a partial named-constant set (`DIRECTIVE_003`,
`DIRECTIVE_010`, `TACTIC_ADR_DRAFTING_WORKFLOW`, `TACTIC_REQUIREMENTS_VALIDATION_WORKFLOW`,
`TACTIC_PREMORTEM_RISK_IDENTIFICATION`, ...). The fix simply **completes** that set: the
inconsistency — some URNs named, most inlined — is itself the smell.

### Scope of work

1. Define the missing URN constants next to the existing ones (directives 024/025/028/
   029/030/034/037, the tactic URNs, the agent-profile URNs).
2. Replace the raw duplicated string occurrences in `_REQUIRED_SCOPE` with the constants.
3. No logic change — the frozensets resolve to identical values; existing calibration
   tests are the regression guard.

**Risk: minimal.** Behavior-preserving, single-file, covered by the existing calibration
suite. Good first pickup / campsite PR. Clears all 14 smells.

## `src/specify_cli/cli/commands/sync.py` — split the safe wins from the refactor

6,261 LOC — a **god-module** of `spec-kitty sync` subcommands. **26 smells**, ~4h
Sonar effort. This file is the worst single source file in the project and sits in the
**Wave 4 sync-adapter cluster** of the [degod roadmap](https://github.com/spec-kitty/spec-kitty/blob/main/docs/archive/plans/refactor/degod-unshim-roadmap.md).
Do **not** treat it as one cosmetic pass — separate the mechanical wins from the two
complexity monsters.

### Tier 1 — mechanical wins, safe now (~1h, 15 findings)

Behavior-preserving; drops the file 26 -> 11 smells.

| Rule | Count | Lines | Fix |
|---|---|---|---|
| S7632 | 6 | 1019, 1806, 2002, 2058, 3657, 3869 | Fix malformed issue-suppression comment syntax |
| S3358 | 5 | 189, 2158, 2165, 4693, 5960 | Extract nested ternary into a statement |
| S1192 | 3 | 108, 561, 2146 | Hoist `"bold yellow"`, `":memory:"`, `"[dim]Unavailable"` to constants |
| S5713 | 1 | 2590 | Remove redundant `Exception` subclass |

Note the 6 `S7632` findings are malformed suppression comments — worth fixing on sight,
and a reminder that the file already leans on suppressions (see Tier 2).

### Tier 2 — cognitive complexity, ride Wave 4 (~3h, 10x S3776)

The real debt. Two functions dominate and **already carry `# noqa: C901`** — explicit
complexity suppressions that the campsite/charter policy says to retire, not add to:

| Function | Line | Cognitive complexity | Sonar effort | Notes |
|---|---|---|---|---|
| `status()` | 5299 | **90** | 1h20m | `# noqa: C901`; build-and-emit table + `--check` coherence gate |
| `doctor()` | 5925 | **73** | 1h3m | `# noqa: C901`; diagnostic build-and-emit + gate |
| `routes()` | 2126 | 27 | 17m | |
| `purge()` | 4424 | 26 | 16m | |
| `_enforce_sync_now_exit_from_dispatch()` | 304 | 22 | 12m | |
| `status()`-adjacent | 3737 | 19 | 9m | |
| (subcommand) | 5109 | 19 | 9m | |
| `share()` | 2232 | 18 | 8m | |
| (subcommand) | 5840 | 17 | 7m | |
| (subcommand) | 4348 | 16 | 6m | |

`status()` and `doctor()` are the classic decomposition shape: a long sequence of
conditional `table.add_row(...)` blocks (build), a `--check`/coherence gate (validate),
and rendering (emit). The natural split is `_build_*_rows()` / `_run_coherence_gate()` /
`_render(...)` pure helpers, each independently testable — which also satisfies the
Sonar rule "prefer testable extractions."

**Why this is not a cosmetic pass.** `sync.py` is a 6.3k-line CLI surface. Extracting
helpers under it without a **golden CLI-characterization test first** risks silent
behavior drift, which the degod roadmap calls out as a non-negotiable invariant
("golden-CLI-characterization test first on every command degod"). This work belongs in
the Wave 4 sync-adapter degod slice, where that harness is built, and where the
`# noqa: C901` suppressions come off as the functions drop under complexity 15.

## Effort summary

| Target | Findings | Safe now | Deferred to a wave |
|---|---|---|---|
| `walker.py` | 14 | ~2h (all) | — |
| `sync.py` Tier 1 | 15 | ~1h | — |
| `sync.py` Tier 2 | 10 | — | ~3h (Wave 4, with characterization tests) |

Immediate safe cleanup: **~3h clears 29 findings** (`walker.py` + `sync.py` Tier 1).
The 10 `sync.py` complexity findings ride **Wave 4**. (A prior 11th target,
`sync_workspace()`, was resolved by deletion — issue #424 / PR #500, "Delete dead
GitVCS/VCSProtocol.sync_workspace" — and dropped from this inventory so future
cleanup planning does not chase a non-existent function.) The 3 `S2083` BLOCKER
vulnerabilities in `merge/bookkeeping_projection.py` and `skills/verifier.py` are a
separate ~90-min targeted fix (not on a wave) and should land before the final 3.2.6 tag (3.2.6 shipped 2026-09-03; the S2083 BLOCKERs are now tracked as #2970).
