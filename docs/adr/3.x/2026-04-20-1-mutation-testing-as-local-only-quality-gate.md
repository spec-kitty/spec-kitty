---
title: Mutation Testing as a Local-Only Quality Gate
description: 'Adopts mutmut as a local-only developer quality gate over the source tree, with the methodology captured as doctrine and CI integration deliberately deferred.'
status: Accepted
date: '2026-04-20'
doc_status: active
kind: ADR
updated: '2026-04-20T00:00:00Z'
---

## Context and Problem Statement

Line and branch coverage measure *whether* tests execute code; they do not measure whether tests would
detect real bugs. Several Spec Kitty modules have had high coverage but weak assertions — tests that
run the code path and assert only that nothing raised. When we wanted an objective signal of test
**effectiveness** (not just reach), we needed a different tool.

The question was not *whether* to adopt mutation testing — the value is well-established — but at what
level of overhead, and with what scope.

## Decision

**Adopt `mutmut` 3.5.0 as a local-only developer quality gate.** Capture the methodology as
first-class doctrine. Defer CI integration until the workflow is proven and the contributor-facing
guidance is written.

Concretely:

1. **Tooling:** `mutmut` added under `[project.optional-dependencies.test]`. Configuration lives in
   `[tool.mutmut]` in `pyproject.toml`.
2. **Scope:** `paths_to_mutate = ["src/"]` — the entire first-party source tree is in scope when a
   developer invokes `mutmut run` locally.
3. **Doctrine:** the curated artifact set landed in
   `src/doctrine/tactics/built-in/testing/mutation-testing-workflow.tactic.yaml`,
   `src/doctrine/styleguides/shipped/mutation-aware-test-design.styleguide.yaml`, and language-specific
   toolguides for Python (`mutmut`) and TypeScript (`stryker`). The DRG graph anchors these to
   `DIRECTIVE_034` (Test-First Development).
4. **No CI gate. No release-blocking check. No dashboard.** Mutation score is something a developer
   checks before handing a mission over for review — a local-only signal, not a shared scoreboard.

## Rationale

- **Mutation runs are slow and flaky in constrained environments.** A full `mutmut run` against spec-
  kitty takes hours and needs a roomy sandbox. Putting this behind a CI gate would make CI roughly 20×
  slower and would fight with the `mutmut 3.5.0` trampoline bug that breaks any test spawning
  `python -m specify_cli` as a subprocess.
- **Doctrine beats tooling when you haven't adopted the discipline.** The kill-the-survivor workflow
  requires judgement about which mutants are equivalent vs. which signal weak assertions. Without the
  `mutation-aware-test-design` patterns (Boundary Pair, Non-Identity Inputs, Bi-Directional Logic) in
  muscle memory, a CI gate just teaches contributors to game the score. Ship the doctrine, prove the
  workflow locally, *then* gate.
- **Signal-to-noise is better at the developer's desk.** Contributors triaging their own surviving
  mutants learn the patterns; contributors triaging another team's failing CI run learn to mark
  mutants "equivalent" and move on.

## Current state (As-Is)

- Each mutmut invocation forks a `mutants/` sandbox directory and runs the project's test suite against
  each injected mutant. Baseline-test failures in the sandbox currently prevent `mutmut run` from
  reaching the mutant-testing phase.
- We keep the sandbox baseline green via an explicit `--ignore=` list in
  `pyproject.toml[tool.mutmut].pytest_add_cli_args`. Each entry targets tests that are incompatible
  with the sandbox for one of four reasons:
  - **Subprocess CLI invocation:** tests that shell out to `python -m specify_cli` trip the known
    `mutmut 3.5.0` trampoline bug (`AttributeError: 'NoneType' object has no attribute
    'max_stack_depth'` in `record_trampoline_hit`).
  - **Whole-codebase AST walks:** pytestarch, chokepoint coverage, ownership invariant checks — these
    blow the 30-second per-test timeout.
  - **Wheel builds / multiprocessing spawn:** adversarial distribution tests and concurrency tests
    that conflict with mutmut's `set_start_method('fork')`.
  - **Repo-state dependencies:** tests that read files outside `also_copy`d directories (live
    `kitty-specs/`, `scripts/`, cross-mission fixtures).
- Additionally, marker-based deselection removes `slow`, `e2e`, `distribution`, `adversarial`,
  `windows_ci`, `platform_darwin`, `live_adapter`, and `architectural` tests.
- `type_check_command` is disabled because mutmut's line-based JSON parser cannot handle mypy's
  multi-line `hint` fields. The cost is accepting that mutants producing type errors will be tested
  rather than filtered out; they typically get killed on import failure.

The `--ignore=` list is a brittle external registry — it goes stale when tests move or rename, and the
reason a test is excluded lives in a TOML comment rather than next to the test itself.

## Target state (landed 2026-04-20)

**The explicit per-file `--ignore=` list has been replaced with two pytest markers:
`non_sandbox` and `flaky`.** The two categories capture different exclusion intents and must
not be conflated.

1. **Register both markers** in `[tool.pytest.ini_options].markers`:
   - `non_sandbox: test is structurally incompatible with mutmut's forked sandbox — subprocess CLI
     calls, whole-codebase AST walks, wheel builds, or repo-state fixtures that fall outside
     mutmut's also_copy tree. Exclusion is deterministic: the test will never pass in the sandbox
     until the underlying sandbox constraint changes.`
   - `flaky: test passes reliably in the main test suite but produces non-deterministic results
     under mutmut (or other mutation/forking pipelines) — e.g., race conditions in target-branch
     detection, time-sensitive assertions, implicit reliance on process-wide state. Re-evaluate on
     every pipeline tooling upgrade; aim to fix root causes and remove the marker.`
2. At the top of each currently-ignored test file, add `pytestmark = pytest.mark.<marker>` with a
   one-line comment stating *why*. For wholesale-ignored directories, use a directory-level
   `conftest.py` that applies the marker collectively.
3. Collapse the long `--ignore=` block in `pyproject.toml` into two deselection clauses:
   `"-m", "... and not non_sandbox and not flaky"`.

Why the distinction matters:

- `non_sandbox` tests are **accepted losses** — we've decided the coverage trade-off is worth the
  stability. No follow-up is planned unless the upstream trampoline bug is fixed.
- `flaky` tests are **debt** — they indicate real test-suite weaknesses (hidden global state,
  timing dependencies, missing fixture isolation). Each `flaky` marker should have a TODO comment
  pointing to the root cause; they should shrink over time, not accumulate.

Benefits:

- **Co-located intent.** The "why" sits next to the test, not in a separate config file.
- **Rename-safe.** Moving or renaming a test no longer silently removes it from the ignore list.
- **Individually re-enableable.** When the upstream mutmut trampoline bug is fixed, we remove the
  `non_sandbox` marker from subprocess tests without touching the TOML.
- **Discoverable.** `pytest -m non_sandbox --collect-only` and `pytest -m flaky --collect-only`
  list exactly which tests are excluded and for which reason — replacing `grep` archaeology on
  `pyproject.toml`.
- **Signals tech debt.** The `flaky` bucket surfaces tests that may be lying to us in CI; the
  `non_sandbox` bucket does not.

## Required follow-up work

- **Contributor guidance document.** Landed 2026-04-20 at `docs/how-to/run-mutation-tests.md`.
  Covers running `mutmut run`, reading results, the kill-the-survivor workflow, equivalent-mutant
  suppression, and how to add the `non_sandbox`/`flaky` markers to new tests that won't run in
  the mutant sandbox.
- **User-facing rationale.** A short section in the main `README.md` or a dedicated explanation doc
  describing *why* mutation score matters and how it differs from coverage — enough to prevent a
  contributor from treating the two as interchangeable.
- **Re-evaluate CI integration** once (a) the `mutmut 3.5.0` trampoline bug is fixed upstream or
  worked around at the project level, and (b) the doctrine is known to be internalised — likely
  measured by contributors citing the `mutation-aware-test-design` patterns in code review.

## Consequences

**Positive:**

- Developers have a real tool to answer "if I introduced a bug here, would my tests fail?" rather
  than the proxy question "did my tests run this line?".
- Doctrine artifacts travel with the project: any contributor who picks up a mission inherits the
  mutation-aware test design patterns.
- No CI slowdown. No review-board arguments about mutation score thresholds.

**Negative:**

- The `--ignore=` list will drift until the `non_sandbox` marker migration lands.
- Contributors who never run `mutmut run` locally get no mutation signal at all. Without CI this is a
  soft policy, not an enforced gate.
- Mutmut's subprocess-unfriendly trampoline forces ignores around spec-kitty's CLI integration tests.
  That's a real coverage blind spot for CLI behaviour, mitigated (not eliminated) by the unit tests
  that cover the same code paths in-process.

## Related

- Tactic: `src/doctrine/tactics/built-in/testing/mutation-testing-workflow.tactic.yaml`
- Styleguide: `src/doctrine/styleguides/shipped/mutation-aware-test-design.styleguide.yaml`
- Toolguide: `src/doctrine/toolguides/shipped/PYTHON_MUTATION_TOOLS.md`
- Toolguide: `src/doctrine/toolguides/shipped/TYPESCRIPT_MUTATION_TOOLS.md`
- Import candidate: `src/doctrine/_reference/craft-guidelines-library/candidates/mutation-testing-skillpack.import.yaml`
- Directive: `DIRECTIVE_034` (Test-First Development)
