---
title: 'ADR 2026-05-28-1: CI Dependency Resolution and Test Surface Consistency'
description: 'CI installs from the frozen lockfile so the pipeline environment matches local development, closing four failure modes that were invisible outside CI.'
status: Accepted
doc_status: active
kind: ADR
date: '2026-05-28'
---

  for `feat/pre-doctrine-stabilization-remediation` (GitHub Actions run 26558837157).
  Root causes identified via full CI run retrospective.

---

## Context and Problem Statement

During a full CI pipeline run (run 26558837157) on the
`feat/pre-doctrine-stabilization-remediation` branch, 27 tests failed across four
distinct failure modes. All failures were silent in local development but visible in CI.
The root cause in every case was the same structural gap: the test environment in CI was
not equivalent to the local development environment, and the test surface did not enforce
the production contracts it claimed to verify.

### Discovery Process

The failures were traced through the following chain:

1. **Observation:** `integration-tests-agent` and `fast-tests-agent` jobs showed 23
   tests failing with empty output — "No JSON envelope found in output."
2. **Hypothesis:** Reproduced locally using typer 0.26.2 (installed in an isolated venv).
   The local `uv.lock` pins typer to 0.24.2; CI installs via `pip install -e .[test]`
   against the loose `pyproject.toml` bound `typer>=0.24.1`, resolving to 0.26.2.
3. **Root cause:** Typer 0.26 vendors click internally as `typer._click`. Exceptions
   raised by typer internals (`UsageError`, `Abort`, `Exit`) now come from that vendored
   module and are unrelated to the standalone `click` package's exception hierarchy.
   `_JSONErrorGroup`'s `except click.UsageError` clause silently missed every exception
   raised by typer 0.26+.
4. **Secondary failures:** `pytest.raises(click.exceptions.Exit)` in four test files
   matched the wrong class for the same reason. `test_quickstart_end_to_end.py` used a
   hand-rolled SHA-256 hash instead of the canonical `charter.hasher.hash_content()`,
   diverging silently. E2e tests failed because `.kittify/charter/metadata.yaml` is
   gitignored and absent in CI clones, but the e2e conftest did not synthesize it.

### Why These Were Invisible Locally

- Local development uses `uv sync --locked`, which installs exactly what `uv.lock`
  specifies (typer 0.24.2).
- CI used `pip install -e .[test]`, which resolves `typer>=0.24.1` to the latest
  available version at install time — currently 0.26.2.
- No CI matrix exercised more than one typer version.
- No lint rule prevented direct `click.exceptions.*` imports in test files.
- No shared fixture synthesized CI-absent runtime state files.
- No lint rule required tests to import production helpers rather than re-implement them.

---

## Decision Drivers

- Local development and CI must run against the same resolved dependency graph.
- The version drift that exposed these failures was not user error — it was a structural
  gap in how the project manages its environment contract.
- Linting and fixture discipline should enforce correct patterns before review, not
  after a CI failure.
- Tests that re-implement production algorithms test their own copy, not the system under
  test. Any deviation between the two silently breaks the test's validity as a contract
  check.
- E2e test infrastructure must be self-contained; it must not inherit implicit
  preconditions from the developer's machine state or gitignored runtime files.

---

## Considered Options

### Gap 1: CI vs. local dependency resolver mismatch

- **Option A (chosen):** Run CI via `uv sync --frozen`, making the lockfile the single
  contract for both local and CI environments.
- **Option B:** Add upper-bound pins in `pyproject.toml` for sensitive transitive deps.
- **Option C:** Keep `pip install`, add a scheduled "latest-deps" shadow CI job.

### Gap 2: No version-compatibility test for the typer/click interface

- **Option A (chosen):** Add a targeted smoke test that exercises `_JSONErrorGroup`'s
  JSON envelope output end-to-end, parameterized by importing `typer.Exit` through the
  stable public surface.
- **Option B:** Add a full CI matrix axis `typer: [pinned, latest]`.
- **Option C:** No test; rely on lockfile pinning from Gap 1.

### Gap 3: Test helpers re-implement production algorithms

- **Option A (chosen):** Ruff `noqa` allowlist ban — add a custom or per-file linter
  rule that flags inline re-implementations of known production helpers (detected by
  pattern, e.g., `hashlib.sha256` inside `tests/`).
- **Option B:** Code review checklist only (no automated enforcement).
- **Option C:** Extract a shared test-utilities module and require all tests to import
  from it.

### Gap 4: E2e fixtures depend on gitignored runtime state

- **Option A (chosen):** E2e conftest synthesizes all required runtime state files
  explicitly after `copytree`, using the production helpers to produce valid content.
- **Option B:** Disable preflight globally for test contexts (ad-hoc, per-conftest).
- **Option C:** Commit a minimal `metadata.yaml` fixture file for tests only.

### Gap 5: Direct `click.exceptions.*` imports in test files

- **Option A (chosen):** Ruff banned-import rule covering `click.exceptions` in the
  `tests/` tree. Any test that needs to assert on CLI exit/error types must import
  through `typer`'s public surface.
- **Option B:** Code review checklist only.
- **Option C:** Test-only compatibility shim (mirrors the production shim).

---

## Decision Outcome

**All five options A are accepted.** They are the minimal set of changes that directly
address the structural root cause in each gap with automated enforcement rather than
convention.

### Decision

1. **CI runs `uv sync --frozen`.** Every test job in `ci-quality.yml` replaces its
   `pip install -e .[test]` block with `astral-sh/setup-uv` + `uv sync --frozen`.
   The lockfile is the environment contract for both local and CI.

2. **A typer-surface smoke test is added.** A single parameterized test in the
   `fast-tests-agent` group verifies that invoking the CLI without a subcommand (the
   `_JSONErrorGroup` trigger path) returns a JSON envelope with `"ok": false`, using
   `typer.Exit` (not `click.exceptions.Exit`) as the expected exit-code exception class.
   This test is the canary for the specific regression mode we observed.

3. **`hashlib.sha256` usage inside `tests/` is banned by ruff.** Tests that need to
   compute a production-format hash must import and call the canonical helper. The rule
   prevents future test helpers from diverging silently from the algorithm they are
   supposed to exercise.

4. **E2e conftest is self-contained.** The conftest synthesizes `metadata.yaml` using
   the production `charter.hasher.hash_content()` helper immediately after `copytree`,
   rather than disabling preflight. This closes the "fixture inherits machine state"
   gap; any future preflight precondition must also be synthesized in the fixture.

5. **`click.exceptions` is a banned import in `tests/`.** Ruff `banned-api` rule covers
   `click.exceptions.Exit`, `click.exceptions.UsageError`, and `click.exceptions.Abort`.
   The allowed public surface for assertion is `typer.Exit`, `typer.BadParameter`, etc.

### Consequences

#### Positive

- Local and CI environments are now described by the same lockfile contract. Any
  dependency upgrade is visible, deliberate, and reviewed in a PR via `uv.lock` diff.
- The `_JSONErrorGroup` regression mode now has a test that would have caught it at the
  time it was introduced (i.e., at the first `uv.lock` update that bumped typer).
- Lint rules enforce both bans (re-implemented algorithms, direct click imports) without
  requiring human attention in review.
- The e2e fixture is reproducible across any fresh clone, eliminating a class of
  "works on my machine" CI failures.

#### Negative

- CI install time increases slightly (uv resolves and installs from lockfile rather than
  just latest-compatible). Measured impact is expected to be under 5 seconds per job
  given uv's speed.
- `uv.lock` must be kept current; PRs that add or change dependencies must also update
  the lockfile. `uv lock --check` already enforces this (NFR-005 gate, job
  `uv-lock-check`).
- The `hashlib.sha256` ban in `tests/` may produce false positives for tests that
  legitimately compute a raw SHA-256 (e.g., testing a hashing utility's output, PKCE
  challenges, body/file-integrity checksums). Those tests must carry an inline
  `# noqa: TID251 — <justification>` suppression (the configured rule is `TID251`,
  flake8-tidy-imports banned-api — there is no `SC001` rule). The ban is enforced
  per-call across the whole `tests/` tree by the dedicated
  `[ENFORCED] banned-API lint gate (TID251)` step in `ci-quality.yml`; there are no
  whole-directory exemptions that could silently disarm it.

#### Neutral

- The typer version-compatibility smoke test does not replace the full envelope contract
  test suite; it is additive. Existing tests continue to run unchanged.
- No production code changes are required by this ADR; all changes are in CI
  configuration, test infrastructure, and lint configuration.

### Confirmation

This ADR is considered fully implemented when:

1. All `pip install -e .[test]` blocks in `ci-quality.yml` are replaced with
   `uv sync --frozen` and CI continues to pass.
2. A failing test exists in `fast-tests-agent` that would have caught the
   `_JSONErrorGroup` / typer 0.26 regression.
3. `ruff check tests/` flags any new introduction of `hashlib.sha256` or
   `click.exceptions.*` in the test tree.
4. `tests/e2e/conftest.py` synthesizes `metadata.yaml` using the production helper and
   does not rely on `preflight.enabled: false` as the solution.
5. The full CI pipeline passes on a clean clone with no gitignored files present.

---

## Assessment: Does This Remediate the Problem?

The five changes directly address the five structural gaps identified in the retrospective.

**Gap 1 (resolver mismatch):** Switching to `uv sync --frozen` eliminates the
divergence entirely. There is no longer a path where CI resolves a different version of
any dependency than local development. Future version upgrades are explicit lockfile
changes that go through PR review.

> **Implementation note (second-pass fix, CI run 26565789745):** The initial
> implementation of `uv sync --frozen` omitted the `--all-extras` flag. Since pytest,
> pytest-cov, ruff, and mypy live in `[project.optional-dependencies.test]` and
> `[project.optional-dependencies.lint]`, `uv sync --frozen` without `--all-extras`
> produced a venv that was missing pytest entirely, causing every test job to fail with
> `No module named pytest`. All 37 non-infrastructure `uv sync --frozen` invocations in
> `ci-quality.yml` were corrected to `uv sync --frozen --all-extras`. The three exempt
> infrastructure jobs (`uv-lock-check`, `build-wheel`, `clean-install-verification`) had
> no `uv sync` calls and were unaffected.

**Gap 2 (no version-compatibility test):** The smoke test is narrow by design — it
covers the exact trigger path (`_JSONErrorGroup` with no subcommand) that silently broke
in production. A broader matrix test would provide more coverage but is out of scope for
this ADR; the single test is the canary that was missing.

**Gap 3 (re-implemented algorithms):** The ruff ban is permanent and automated.
Copy-pasted algorithm implementations will be caught on the next `ruff check` run before
they are committed. The rule does not fix existing divergence in other tests; that
requires a separate audit.

**Gap 4 (gitignored state in e2e):** The conftest change makes the fixture
self-describing. This is a point fix for `metadata.yaml`; it does not generalize to
every possible gitignored file that might be needed in future. The design principle
established here — conftest synthesizes all required state — is the convention for
future e2e fixtures.

**Gap 5 (direct click imports):** The ruff rule catches the symptom (direct use of
`click.exceptions.*` in tests) but does not prevent future production code from using
the wrong exception class. The production-side fix (the `_CLICK_USAGE_ERRORS` shim in
`_JSONErrorGroup`) is already in place. Together, both layers are required: the
production shim handles version drift in runtime behavior; the lint rule prevents tests
from silently depending on the wrong class for assertions.

---

## More Information

- GitHub Actions run 26558837157 — full CI run that surfaced all four failure modes.
- `src/specify_cli/orchestrator_api/commands.py` — `_JSONErrorGroup` and the
  `_CLICK_USAGE_ERRORS` / `_CLICK_ABORTS` compatibility shim.
- `tests/e2e/conftest.py` — e2e fixture and the `preflight.enabled: false` workaround
  being replaced by this ADR.
- `tests/integration/test_quickstart_end_to_end.py` — charter hash fix.
- `architecture/adrs/2026-02-21-1-consistent-code-style-enforcement-via-git-hooks.md`
  — related ADR on automated style enforcement.
- `pyproject.toml` `[tool.ruff]` section — location of banned-api rules.
