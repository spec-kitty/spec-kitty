---
title: Code Quality — Working Collection
description: 'Standing code-quality surface: the SonarCloud baseline, quality-metric evolution, the smell/vulnerability cluster taxonomy, and how the debt maps onto the degod/unshim waves.'
doc_status: active
updated: '2026-09-30'
audience: docs/context/audience/internal/maintainer.md
related:
- docs/plans/index.md
- docs/plans/4-0-0-milestone-roadmap.md
- docs/plans/3-2-x-milestone-roadmap.md
- docs/archive/plans/refactor/degod-unshim-roadmap.md
- docs/plans/code-quality/targeted-cleanup-scoping.md
- docs/adr/3.x/2026-07-17-1-red-main-is-honest-ci-is-release-authority.md
---
# Code Quality — Working Collection

> **Status (2026-09-30).** The metrics and cluster tables below are the **2026-08-12**
> snapshot, kept as a record. Two things have changed since. First, the live Sonar backlog is
> now tracked as the 4.0.0 series under #1928 (the Sonar/quality debt parent): #4299–#4305
> plus #2969 and #2970; see the "Cross-cutting — Sonar / quality debt" section of the
> [4.0.0 Milestone Roadmap](../4-0-0-milestone-roadmap.md). Second, several files named
> below are gone: `cli/commands/sync.py` was removed with the sync transport, and the
> `merge/` package became `consolidation/`. Those rows are struck through.

The standing code-quality surface for Spec Kitty: what the SonarCloud analysis of
`main` actually says, how the metrics have moved, where the debt clusters, and how
that debt lines up with work the roadmap has already scoped. This is a
**distil-then-retire** working collection (see [Plans](../index.md)) — the durable
"why" lives in the [degod/unshim roadmap](https://github.com/spec-kitty/spec-kitty/blob/main/docs/archive/plans/refactor/degod-unshim-roadmap.md) and the
[4.0.0 Milestone Roadmap](../4-0-0-milestone-roadmap.md) (the
[3.2.x milestone roadmap](../3-2-x-milestone-roadmap.md) is the prior-cycle record); this
collection holds the measurement and the targeted cleanup scoping.

Analysis source: the 2026-08-12 CI Quality run on `f6b90d34e`, branch `main`, then under
the SonarCloud project key `Priivacy-ai_spec-kitty` (now `spec-kitty_spec-kitty`, see
`sonar-project.properties`). At the time Sonar ran only on the nightly/manual schedule.
Today it runs on two surfaces: the per-PR `sonar-pr` job in `ci-aggregate.yml` (reported,
not required) and the nightly/manual `sonar.yml` scan of `main`. The `main` quality gate
still reflects the accumulated project-wide backlog rather than any single change.

## Snapshot (`main`, 2026-08-12)

| Domain | Metric | Value | Rating |
|---|---|---|---|
| Coverage | line coverage | 84.1% | A |
| Duplication | duplicated lines | 0.5% (48 blocks) | A |
| Complexity | cyclomatic / cognitive | 34,535 / 36,285 | — |
| Reliability | bugs | 0 | A |
| Maintainability | code smells / SQALE debt | 1,807 / 12,959 min | A |
| Security | vulnerabilities | 21 | E |
| Security review | hotspots to review | 2 | E |

Size: 205,734 ncloc across 1,158 files.

## Quality-metric evolution

Per-analysis history on `main`. The July trough and August recovery are the story:
the large `next/` + execution-lanes merge landed under-tested, then the
test-sanitation work pulled coverage back to a project high.

```text
date          ncloc   cov%   dup%   cognitive  smells  vulns  bugs
2026-05-03   118105   53.7   1.3     21938      664      0     0
2026-06-07   164071   64.6   1.2     30599      846      0     0
2026-07-07   192086   47.3   0.7     32798      879     17     1   <- vulns appear (lanes/next merge)
2026-07-19   201184   48.2   0.6     33446     1116     20    29   <- bug spike
2026-07-26   212904   48.2   0.6     34824     1225     23    32
2026-08-02   204754   69.9   0.5     36247     1865     21    33
2026-08-06   204161   73.8   0.5     36508     1903     21    34
2026-08-11   204992   83.7   0.5     36470     1935     21     0   <- bugs cleared
2026-08-12   205734   84.1   0.5     36285     1807     21     0   <- last snapshot recorded here
```

Reading the trends:

- **Coverage — strongly positive.** Recovered from a July trough of ~47% to a
  project-high **84.1%**. The +10pt step on 08-11 → 08-12 is the recent
  test-backfill work landing.
- **Duplication — excellent and improving.** 1.3% → **0.5%**, monotonic, well under
  the 3% ceiling.
- **Complexity — grows with size, density flat.** Cognitive complexity nearly
  doubled while ncloc nearly doubled; per-kloc density actually ticked down
  (0.186 → 0.176). Growth is proportional, not degrading.
- **Bugs — a clean win.** A mid-July reliability spike (0 → 34) was fully burned down
  to **0** by 08-11. Reliability is A.
- **Code smells — the one watch item.** 664 → 1,807 (~3x) while code grew ~1.75x, so
  smell *density* rose. Still A-rated, but debt is accreting slightly faster than the
  codebase. See the taxonomy below — roughly half is test-idiom nits.
- **Vulnerabilities — flat, unresolved backlog.** Appeared as a block of 17 on
  2026-07-07 (the subprocess-heavy lanes/`next` merge), peaked at 23, sits at **21**.
  This is the sole thing keeping security at **E** and failing the dispatch gate.

## The quality gate

The `workflow_dispatch` CI Quality run fails on exactly one condition:

| Condition | Actual | Required | |
|---|---|---|---|
| `new_security_rating` | C (3) | A (1) | FAIL |
| `new_coverage` | 90.4% | >=80% | pass |
| `new_reliability_rating` | A | A | pass |
| `new_maintainability_rating` | A | A | pass |
| `new_duplicated_lines_density` | 0.1% | <=3% | pass |
| `new_security_hotspots_reviewed` | 100% | 100% | pass |

Per [ADR 2026-07-17-1](../../adr/3.x/2026-07-17-1-red-main-is-honest-ci-is-release-authority.md),
this is an honest standing red, not a release regression: all 21 vulnerabilities
predate any current release candidate (created 2026-06-24 → 2026-07-30), and the
2026-08-12 head commit contributed none of them.

## Cluster taxonomy

The headline "1,807 smells" splits cleanly into low-value test-idiom nits and real
source debt. About **half** the backlog is pytest-style rules in test files.

### Cluster A — test-idiom modernization (~940 smells, ~52%, test files)

Mechanical, low real-risk, bulk-fixable; ideal for a single sweep. Not release-relevant.

| Rule | Count | Meaning |
|---|---|---|
| S9073 | 342 | Composite assertions should be split |
| S9083 | 252 | Pytest fixture/mark decorator parentheses style |
| S5778 | 245 | Only one call expected inside `pytest.raises` |
| S8714 | 61 | Use dedicated exception assertions vs `try/except` + `fail()` |
| S8997 | 42 | Use the `monkeypatch` fixture |

### Cluster B — cognitive complexity (S3776, 339, all in `src`)

The real maintainability cluster and the target of the complexity-ceiling-15 policy.
Concentrated in the CLI command layer and doctrine:

```text
11  cli/commands/sync.py
10  cli/commands/agent/mission_finalize.py
 7  cli/commands/glossary.py
 6  doctrine/pack_validator.py
 5  cli/commands/migrate_cmd.py · agent/config.py · doctrine/pack_assembler.py
 5  migration/backfill_runtime_state.py · status/reducer.py
```

### Cluster C — duplicated string literals (S1192, 117, all in `src`)

The "hoist to a constant at >=3x" cluster. One clear standout:

```text
14  calibration/walker.py
 5  cli/commands/decision.py · doctrine/drg/migration/hand_authored_overlay.py
 4  cli/commands/migrate_cmd.py
```

### Location hotspot

`cli/commands/` is the worst neighborhood in `src` — 128 smells in the directory plus
53 in `agent/` (~181). The worst single file across all rules is
`cli/commands/sync.py` (26). After that the tail is thin.

## How the debt maps onto the roadmap

The reds are not surprise debt — they map almost 1:1 onto named, sequenced-but-not-yet
-executed [degod/unshim waves](https://github.com/spec-kitty/spec-kitty/blob/main/docs/archive/plans/refactor/degod-unshim-roadmap.md) and the subsystems
the 3.x execution model built out. The vulnerabilities all appeared on 2026-07-07,
exactly when the lanes/`next` execution-model merge landed.

| Sonar cluster | Files | Cleanup owner | Wave status |
|---|---|---|---|
| S6350 subprocess vulns (17, -> security E) | `lanes/_git`, `lanes/recovery`, `worktree_allocator`, `coordination/surface_resolver`, `core/git_ops`, ~~`merge/push_preflight`~~ (`merge/` renamed to `consolidation/`), `git/ref_advance` | Wave 2 (coord-authority); ~~Wave 4 (sync adapters)~~ removed with sync | Now #4304 |
| S3776 complexity (339) | ~~`cli/commands/sync.py`~~ (removed with sync), `agent/mission_finalize`, `glossary`, `migrate_cmd` | coord trio -> Wave 2 | Now #4299 |
| S2083 path-traversal (3, BLOCKER) | `merge/bookkeeping_projection` x2 (now `consolidation/bookkeeping_projection`), `skills/verifier` | targeted fix (not on a wave) | Now #2970 |
| S1192 dup literals (117) | `calibration/walker` (14), `decision`, `migrate_cmd` | campsite | Now #4300 |

## Recommended sequence

*As written on 2026-08-12. Items 2 and 4 are void: `sync.py` was removed with the sync
transport. For current priorities, use the 4.0.0 Sonar series in the
[4.0.0 Milestone Roadmap](../4-0-0-milestone-roadmap.md).*

1. **`calibration/walker.py`** dup-literal cleanup — fully safe, ~2h, immediate
   campsite PR. Clears 14 smells and improves URN-constant consistency. See
   [targeted cleanup scoping](targeted-cleanup-scoping.md).
2. ~~**`cli/commands/sync.py` cheap wins** — the 15 mechanical findings (~1h,
   behavior-preserving), dropping the file 26 -> 11 smells.~~ *Void: file removed.*
3. **The 3 S2083 BLOCKERs** — targeted ~90-min fix; not on a degod wave. (Originally
   scheduled before the 3.2.6 tag, which shipped 2026-09-03; now tracked as #2970.)
4. ~~**`sync.py` complexity monsters** (`status()` CC 90, `doctor()` CC 73)~~ *(void: file
   removed)* and the S6350 subprocess-hardening (now #4304) — ride the degod slices with
   golden-CLI-characterization tests first, per the degod invariant. Not a cosmetic
   Sonar pass.

Full per-finding detail and effort estimates: [Targeted Cleanup Scoping](targeted-cleanup-scoping.md).
