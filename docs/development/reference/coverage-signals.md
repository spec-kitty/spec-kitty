---
title: Coverage signals — reconciling the three "coverage" numbers
description: 'Why SonarCloud coverage, new_coverage, and the internal diff-coverage CI gate disagree — and how to tell an expected scope difference from a real coverage regression.'
doc_status: active
updated: '2026-09-14'
audience: docs/context/audience/internal/lead-developer.md
type: explanation
related:
- docs/development/testing/testing-flakiness.md
- docs/development/testing/testing-parallel.md
- docs/development/how-to/review-gates.md
- .github/workflows/ci-aggregate.yml
- .github/workflows/sonar.yml
- .github/workflows/module-tests.yml
- sonar-project.properties
- scripts/ci/sonarcloud_branch_review.sh
---
# Coverage signals — reconciling the three "coverage" numbers

Three different measurements are all colloquially called "coverage" on a Spec
Kitty pull request, and they routinely disagree by tens of percentage points.
That disagreement is **expected and by design** — it is not, on its own, a bug
or a regression. This guide explains what each number measures, why they differ,
and gives you a decision aid for the moment they seem to contradict each other:
*is this a real regression, or an expected scope difference?*

If you only remember one thing: **the internal `diff-coverage` gate and the
SonarCloud numbers measure different files, different lines, and against
different baselines. A passing internal gate next to a low SonarCloud number is
the normal, healthy state — not a contradiction.**

## The three signals at a glance

| Signal | Where it runs | Which files it scores | Which lines it counts | Threshold |
|---|---|---|---|---|
| **Internal `diff-cover` gate** | The `diff-cover` job in `.github/workflows/ci-aggregate.yml`, which runs on `workflow_run` after **CI Modules** completes | A deliberate **critical-path subset** of `src/` (see list below) | **Only the lines your change touched**, as the statement-level diff `scripts/ci/validate_diff_coverage.py` derives | **90%**, blocking |
| **SonarCloud `coverage`** | Nightly Sonar analysis (`.github/workflows/sonar.yml`, cron `0 3 * * *`) / manual dispatch | The **whole `src/` tree** (`sonar.sources=src`) | **Every** executable line in the tree, cumulative | No blocking floor on the overall number (the gate uses the `new_*` metrics) |
| **SonarCloud `new_coverage`** | Same nightly analysis | The whole `src/` tree | Lines in the **New Code Period** (since the `projectVersion` baseline) | **80%**, blocking Sonar's own gate |

**One measurement, several readers.** Every number above is computed from the
*same* per-module coverage reports: `module-tests.yml`'s shards each run pytest
with dotted `--cov=` targets and upload a `coverage-<tier>-<module>-shard<n>.xml`;
`ci-aggregate.yml`'s `collect` job reconciles that set for one change, and both
the `diff-cover` gate and the per-change Sonar report read the reconciliation.
Nothing re-runs the suite to obtain a coverage number.

There is also a **per-change SonarCloud report** — the `sonar-pr` job in
`ci-aggregate.yml` (spec-kitty#4334) — which analyses the same reconciled
measurement. It is informational and **can never block a merge**: it carries
`continue-on-error` and is excluded from the terminal verdict's `needs:`. Until
spec-kitty#4350 clears, it may refuse to publish; see [Known
caveats](#known-caveats-and-follow-ups). Before that mission, the per-PR Sonar
surface was a `sonarcloud` job in `ci-quality.yml` that re-ran the fast tier
under `pytest --cov` purely to produce a report the shards had already produced
for the same commit — a second measurement of the same tests, discarded.

### The internal gate's critical-path allowlist

The enforced internal gate restricts itself (`diff-cover ... --include`) to these
paths — the kernel, doctrine, charter, status, merge, and mission-runtime
surfaces where a coverage miss is highest-risk:

```
src/kernel/*
src/charter/*
src/specify_cli/status/*
src/specify_cli/lanes/branch_naming.py
src/specify_cli/dashboard/handlers/*
src/specify_cli/dashboard/scanner.py
src/specify_cli/merge/*
src/runtime/next/*
src/mission_runtime/*
```

That is roughly **247 Python files** — a strict subset of the **~969 tracked
`.py` files** SonarCloud scores across the whole `src/` tree (SonarCloud indexes
**1305 files** in total under `src/`, spanning all seven top-level packages:
`specify_cli`, `doctrine`, `charter`, `runtime`, `glossary`, `kernel`,
`mission_runtime`).

### Remedy: `git mv` into a critical-path dir needs `fast`-marked coverage

Moving (`git mv`) a module *into* one of the critical-path directories above
subjects its relocated lines to the enforced 90% diff-coverage floor — but the
coverage numerator that floor is judged against does not come from "however
the module is tested somewhere in the suite." The numerator comes from the
per-module shards `module-tests.yml` runs, each scoped by the module registry's
tier marker filter and measuring the full top-level package set derived from `src/` (#4334)
(`.github/ci-module-registry.yml`). `ci-aggregate.yml`'s `collect` job
reconciles every shard's `coverage-*.xml` for the change, and `diff-cover`
scores the critical-path statement diff over that combined set.

If the moved module's real tests carry a marker its shard's filter excludes,
they never execute inside that shard, so the module's lines are effectively
absent from — or
reported near-0% in — the aggregated XML, and `diff-cover` fails the
critical-path move even though the module is well-tested elsewhere in the
suite by its non-fast parity tests.

**Fix:** add a test module in `tests/<critical-path-dir>/` carrying a marker
the covering shard *does* select, exercising the moved module with
mocked/stubbed dependencies (no real subprocess/filesystem/git calls), so its
lines reach the reconciled set. Keep the original real-integration tests
(`git_repo`/`non_sandbox`/`integration`-marked) where they already are — the
new fast module is additive, not a replacement.

This is a fresh trap (PR #3437, mission `write-path-integrity`): moving
`git_topology` into `src/kernel/` to fix a layer inversion left it at 34%
diff-coverage because `kernel-tests` (`-m fast`) could not run the module's
real-git `git_repo`-marked parity tests in `tests/git/test_git_topology.py`.
Adding `tests/kernel/test_git_topology_fast.py` — `pytest.mark.fast`, with
`subprocess.run` mocked — brought the module to 100% line coverage in
`coverage-kernel.xml`, which satisfied both the `diff-coverage` gate and
`kernel-tests`' own 90% floor over `--cov=src/kernel`.

## Why the numbers differ (the evidence)

The reconciliation below was produced against SonarCloud's **public read API**
(no token) using the read-only tool `scripts/ci/sonarcloud_branch_review.sh`.
You can reproduce every figure yourself:

```bash
scripts/ci/sonarcloud_branch_review.sh coverage       # overall + new_coverage
scripts/ci/sonarcloud_branch_review.sh quality-gate   # gate conditions + thresholds
scripts/ci/sonarcloud_branch_review.sh version        # projectVersion / baseline history
```

Three independent axes make the numbers diverge:

1. **File set (scope of files).** SonarCloud scores *all* of `src/`; the enforced
   internal gate scores only the critical-path subset above. So SonarCloud will
   surface uncovered lines in packages (for example `src/specify_cli/cli/`,
   `.../missions/`, `.../doctor/`) that the *enforced* internal gate never looks
   at. This is intentional — coverage effort is kept proportional to risk — and
   the full-diff advisory step exists precisely so the wider diff is still
   visible without blocking.

2. **Line basis (which lines, over what history).** This is the dominant driver.
   - SonarCloud `coverage` (**47.3%**) is a **cumulative average over the entire
     codebase**: `lines_to_cover = 95,111`, `uncovered_lines = 50,090`. It counts
     every executable line ever written, covered or not.
   - The internal gate (**90%**) counts **only the handful of lines the current
     PR changed**. A ten-line PR is judged on ten lines.

   These two can never be close: one is a whole-history denominator of ~95k
   lines, the other is your diff.

3. **Baseline (what "new" means).** SonarCloud `new_coverage` (**50.06%**)
   *sounds* like it should match the internal per-PR gate — both mention "new"
   code — but it does not, for a concrete reason: `new_lines_to_cover = 80,038`.
   About **84% of the whole tree** is currently counted as "new code," because
   every recent nightly analysis reports `projectVersion = "not provided"` and
   the New Code Period baseline is therefore frozen. So today `new_coverage`
   (~50%) is effectively *another whole-repo number*, not a per-PR one — which is
   why it sits right next to the overall `coverage`, nowhere near 90%. (See
   [Known caveats](#known-caveats-and-follow-ups) — resetting this baseline
   per release cycle is part of the pending Sonar decision. Even after such a
   fix, `new_coverage` becomes a *per-release-cycle* number, still not a
   *per-PR* one.)

## The verdict: file-set **and** philosophy differ — but nothing is misconfigured

Investigation finding, stated plainly:

- **The file sets do differ.** SonarCloud scores the entire `src/` tree; the
  enforced internal gate scores only a critical-path subset of the PR diff.
- **The measurement philosophy also differs**, and more decisively: whole-repo
  cumulative average (and a baseline-anchored "new code" number) versus per-PR
  changed-lines-only.
- **Neither difference is a `sources`/`exclusions` misconfiguration.**
  `sonar.sources=src` with `sonar.exclusions=**/__pycache__/**,**/*.pyc,**/migrations/**`
  is correct and standard: tests are registered separately as `sonar.tests`
  (so they are not counted as production lines to cover), and no generated or
  vendored code is wrongly swept in (the agent directories live at the repo
  root, outside `src/`). The internal allowlist is a deliberate,
  risk-proportional choice, not an accident.

Because the divergence is a philosophy-and-baseline difference rather than a
genuine file-set misconfiguration, it is **discharged by this document, not by a
config change** (research-first, per the mission constraint C-002). In
particular, this guide deliberately does **not** recommend narrowing Sonar's
scope to flatter the number — doing so would mask genuinely untested code, which
the project's no-ratchet standing order forbids.

## Decision aid: real regression, or expected scope difference?

When a SonarCloud number looks alarming next to the internal gate, walk these
questions in order:

1. **Did the internal `diff-coverage` (critical-path, enforced) gate pass on
   your PR?**
   - **Yes** → the lines you changed in critical-path modules are ≥90% covered.
     A low SonarCloud *overall* `coverage` or *current* `new_coverage` is **not a
     regression you introduced** — it is the whole-repo / frozen-baseline scope.
     Stop here for those two numbers.
   - **No** → you have a real gap in changed critical-path lines. Add tests
     before merge. This is a real signal, not a scope artifact.

2. **Is the number you are worried about SonarCloud's whole-repo `coverage`
   (~47%)?** Judge it against the **previous nightly analysis's `coverage`**, not
   against the 90% per-PR gate. A *drop* versus the previous analysis is worth
   investigating; a low *absolute* value is expected and structural.

3. **Is it SonarCloud `new_coverage`?** Until the `projectVersion` baseline is
   wired (see caveats), "new code" ≈ the whole repo, so read it like the overall
   number. After that fix it becomes a per-release-cycle figure — still not the
   per-PR diff the internal gate reports.

4. **Did your PR change files *outside* the critical-path allowlist?** The
   *enforced* internal gate does not measure them (only the advisory full-diff
   step does); SonarCloud does. So SonarCloud can legitimately show uncovered
   new lines that the enforced gate stayed silent on — an **expected scope
   difference, not a gate bug**. If those lines carry real logic, add focused
   tests anyway (the charter's rule: every new branch/helper ships with tests).

If after these steps a real coverage gap remains in code you changed, treat it
as a regression and add tests. If every "gap" resolves to whole-repo scope or a
frozen baseline, it is an expected scope difference — record that reasoning in
the PR so the next reader does not re-litigate it.

## Where each signal is configured

- **Internal `diff-cover` gate** — the `diff-cover` job in
  [`.github/workflows/ci-aggregate.yml`](../../../.github/workflows/ci-aggregate.yml)
  (`--fail-under=90` over the statement diff produced by
  `scripts/ci/validate_diff_coverage.py`). The critical-path list itself is
  single-sourced as `CRITICAL_PATHS` in
  [`scripts/ci/aggregate_source.py`](../../../scripts/ci/aggregate_source.py),
  which materialises the diff the gate scores.
  *(An earlier revision of this page said this job "used to live in
  ci-quality.yml … this repo runs no GitHub Actions". That was wrong on both
  counts and is what spec-kitty#4011 was filed for: the repository runs the lean
  modular CI reinstated in spec-kitty#3995.)*
- **Per-change SonarCloud report** — the `sonar-pr` job in the same file,
  driven by `scripts/ci/sonar_pr_analysis.py`. Informational only.
- **Nightly SonarCloud analysis** —
  [`.github/workflows/sonar.yml`](../../../.github/workflows/sonar.yml)
  (cron `0 3 * * *`), which aggregates the same shard coverage artefacts.
- **The measurement itself** —
  [`.github/workflows/module-tests.yml`](../../../.github/workflows/module-tests.yml)
  and the module registry `.github/ci-module-registry.yml`.
- **SonarCloud scope and exclusions** —
  [`sonar-project.properties`](../../../sonar-project.properties)
  (`sonar.sources=src`, `sonar.tests=tests`, `sonar.exclusions=...`).
- **Read-only query tool** —
  [`scripts/ci/sonarcloud_branch_review.sh`](../../../scripts/ci/sonarcloud_branch_review.sh),
  which reproduces every number above against the public API with no
  `SONAR_TOKEN`.
- **Related testing guides** — [Test-flakiness handling policy](../testing/testing-flakiness.md),
  [Running the test suite in parallel](../testing/testing-parallel.md),
  [Review gates](../how-to/review-gates.md).

## Known caveats and follow-ups

- **`projectVersion` baseline is frozen, and the cause is upstream.** Recent
  analyses report `projectVersion = "not provided"`, so SonarCloud's New Code
  Period never resets and `new_coverage` behaves like a whole-repo metric. The
  `projectVersion` wiring is **not** missing — `scripts/ci/sonar_project_version.py`
  derives it from `pyproject.toml` and both `sonar.yml` and `ci-aggregate.yml`'s
  `sonar-pr` job stamp it. What blocks it is **spec-kitty#4350**: SonarCloud's
  server-side *Automatic Analysis* is enabled on the `spec-kitty_spec-kitty`
  project, and an Automatic Analysis result cannot be replaced by a pipeline
  upload — so a correctly-wired upload is refused and is indistinguishable, from
  the pipeline side, from a broken one. Disabling Automatic Analysis is an
  action inside the vendor's interface; until it is taken, **do not read a green
  CI run as evidence that a report was published**. Any fix also takes effect on
  the **next analysis after it merges**, not on merge itself.
  *(An earlier revision said this wiring "has been retired"; it had not — it was
  reinstated by spec-kitty#3993, and spec-kitty#4334 moved its caller from the
  retired `sonarcloud` job to `sonar-pr`.)*
- **Internal allowlist entry repointed.** The critical-path `--include` list
  references `src/specify_cli/lanes/branch_naming.py`
  (`parse_mission_slug_from_branch`) — the real defining home of the
  branch-based mission-slug detection. An earlier draft pointed this entry at a
  path that had since been removed/superseded; #2443 repointed it to this
  defining home in **both** authorities (the workflow `--include` array and
  `tests/release/test_diff_coverage_policy.py`). This was always an incidental
  staleness nit in the internal gate's config, **not** a SonarCloud
  misconfiguration.
