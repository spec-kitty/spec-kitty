---
title: Code-grounding — CI uv-sync resilience for test-shard jobs (#6191)
description: "Read-only code-grounding for the uv-sync resilience mission: every uv sync job in ci-router.yml, the router-gate needs cascade, the tests/ci wiring tests that pin the step shape, the setup-uv cache/pin state, the flakiness-policy carve-out, in-flight CI PR interactions, and ci-router.yml churn."
doc_status: active
updated: '2026-10-13'
type: explanation
mission: ci-uv-sync-resilience-01M4VDBW
issue: 6191
---

# Code-grounding: CI uv-sync resilience (#6191)

Read-only grounding written before specify, per the mission brief. No source was
edited while writing this note. All line numbers are against
`.github/workflows/ci-router.yml` at `origin/main` tip `8c89aa90`.

## 1. Every `uv sync` invocation in `ci-router.yml`

The CI Router workflow has 15 jobs; the ones that install the environment with
`uv sync` are below (job name → step line → exact flags). The `tests (docs)`
job (#6191's subject) is one instance of the **module-test-shard pattern**:
`actions/checkout` → `astral-sh/setup-uv` (`python-version: '3.12'`, no cache) →
a single `run:` block whose first line is the `uv sync` and whose remaining
lines run pytest.

| Job (`name:`) | `uv sync` line | Flags | Family |
|---|---|---|---|
| `ruff` | 689 | `--frozen --extra lint` | shift-left lint |
| `uv-lock` | 723 | *(no sync; `uv lock --check`)* | shift-left lint |
| `import-linter` | 738 | `--frozen --extra lint` | shift-left lint |
| `regen-check` | 752 | `--frozen --all-extras` | shift-left regen |
| `terminology` | 772 | `--frozen --all-extras` | fast always-on gate |
| `docs-lint` | 790 | `--frozen` | fast always-on gate |
| `layer-rules` | 805 | `--frozen --all-extras` | fast always-on gate |
| `archive-freeze` | 830 | `--frozen --all-extras` | fast always-on gate |
| `architectural-fast` | 859 | `--frozen --all-extras` | architectural battery (has memory sampler) |
| `architectural-heavy` | 956 | `--frozen --all-extras` | architectural battery (named step "Sync dev environment"; has memory sampler) |
| **`tests-docs`** (`tests (docs)`) | **1074** | **`--frozen --all-extras`** | **module-test shard — SUBJECT** |
| `tests-e2e` (`tests (e2e)`) | 1093 | `--frozen --all-extras` | module-test shard |
| `tests-corpus-blocking` (`tests (corpus-blocking)`) | 1137 | `--frozen --all-extras` | module-test shard |
| `tests-contract-tools` (`tests (contract tools)`) | 1177 | `--frozen --no-install-project` | contract-tool shard (different flags; `--no-sync` pytest) |
| `mission-state-audit` | 1214 | `--frozen` | audit shard (`--no-sync` pytest) |

**The ~8 sibling jobs that succeed on the same runner/setup** cited in the issue
are the shift-left + fast-gate family (`ruff`, `import-linter`, `docs-lint`,
`regen-check`, `terminology`, `layer-rules`, `archive-freeze`,
`architectural-fast`). They run the identical `setup-uv@v10.0.1` +
`uv sync --frozen [--all-extras]` block and were green in the same run where
`tests (docs)` failed — corroborating an isolated, per-runner transient download
failure rather than a lock/dependency/code defect.

### Scope decision (smallest-viable-diff + locality)

The **module-test-shard pattern** — `setup-uv` then `uv sync --frozen --all-extras`
then `pytest`, with no memory sampler and no extra choreography — is exactly
**`tests-docs` (1074), `tests-e2e` (1093), `tests-corpus-blocking` (1137)**. These
three are the consistent target of the fix ("applied consistently to the
test-shard job(s)").

Deliberately **out of scope**, with rationale recorded here so a reviewer can see
the boundary was a choice:

- `architectural-fast` / `architectural-heavy`: these are the *architectural
  battery*, not module-test shards. They carry a memory sampler whose
  start-before-`uv sync` ordering is pinned by `tests/ci/test_ci_module_wiring.py`
  (see §3), so touching their step shape has a larger blast radius against the
  wiring tests, and the issue did not report them flaking. Keeping them out
  respects locality of change.
- `tests-contract-tools` (`--no-install-project`) and `mission-state-audit`
  (`--frozen`, no `--all-extras`): different install shape, not the
  `--all-extras` module-test-shard pattern the issue names; not reported flaking.
- The shift-left/fast-gate family: green in the same run; not the "module-shard".

The retrofit mechanism itself (a single shared helper, see the Plan) is written
**once** and invoked identically from the three module-test shards, satisfying
"prefer applying the resilient pattern once … rather than hand-editing one job".

## 2. How `router gate` depends on the shard (cascade)

`router-gate` (`name: router gate`, job key `router-gate`, lines 1247–1301) is the
terminal aggregator. Its `needs:` set (lines 1256–1275) lists every upstream job,
including `tests-docs`, `tests-e2e`, `tests-corpus-blocking`:

```
needs:
  - changes
  - prose-scan
  - ruff
  - commit-msg
  - markdownlint
  - uv-lock
  - import-linter
  - regen-check
  - terminology
  - docs-lint
  - layer-rules
  - archive-freeze
  - architectural-fast
  - architectural-heavy
  - tests-docs            # line 1271
  - tests-e2e             # line 1272
  - tests-corpus-blocking # line 1273
  - tests-contract-tools
  - mission-state-audit
```

Its gate runs `if: always() && !cancelled()` (line 1276) and reads each
dependency's **real** conclusion from the Actions jobs API, handing the rows to
`scripts/ci/router_gate.py` (lines 1298–1301). The blocking policy is
`{failure, cancelled} block, {success, skipped} pass`. So a `tests (docs)`
**failure** (its `uv sync` step exiting non-zero) makes `router-gate` fail — the
exact cascade #6191 describes. A `uv sync` that succeeds (first try or after a
bounded retry) leaves the job green and the gate unaffected. This fix changes
**nothing** about `router-gate`'s `needs:` set or its classifier.

## 3. The `tests/ci/` wiring / invariant tests that pin the job shape

Grounded by a read-only sweep of `tests/ci/**` and `tests/architectural/**`. The
load-bearing result for this mission:

> **No step-shape test inspects the `uv sync` / `setup-uv` steps of `tests-docs`,
> `tests-e2e`, or `tests-corpus-blocking`.** Those three (my scope) can gain
> `enable-cache: true` and a bounded-retry install step with **zero re-pointing**
> of any existing test.

What each relevant guard pins, and the honest-keep rule:

- **`tests/ci/test_workflow_run_shell_syntax.py`** — the ONE active guard on any
  new `run:` block. It extracts every workflow `run:` script and (a) runs
  `bash -n` over it (`test_every_run_step_parses_as_bash`), and (b) rejects a
  line ending in an even (≥2) run of trailing backslashes (`doubled_continuations`).
  Non-vacuity (`test_run_steps_were_found`) asserts `tests-corpus-blocking` still
  has a `run:` step. **Keep honest:** write valid bash with single `\`
  continuations; do not rename/remove the corpus-blocking run step. No re-point.
- **`tests/ci/test_ci_module_wiring.py`** — its `uv sync` / `setup-uv` checks
  (`_SETUP_UV_PREFIX`, `_step_index(run_contains="uv sync")`, the memory-sampler
  `start < setup_uv and start < uv_sync` ordering) apply to `architectural-fast`
  and `architectural-heavy` **only** — jobs I am not touching. Its golden tests
  pin `tests-docs.needs == [changes, prose-scan]`, `tests-e2e.needs == [changes]`,
  and the prose-only `if:` — all about `needs`/`if`, none about step text/count;
  **adding a step or input does not touch them.** The setup-uv `with:` block
  (python-version, and therefore `enable-cache`) is never inspected.
- **`tests/ci/test_ci_workflow_prestep_shape.py`** — its `uv sync` check
  (`"uv sync" in run`, must precede `select`/`key`/pytest, must NOT also contain
  `-m pytest`) applies to `architectural-heavy` (and `module-tests.yml::test`)
  **only** — not my scope.
- **`tests/ci/test_xdist_worker_policy.py`** — covers the 4 battery-class jobs'
  **pytest** command lines only (`-n 4`, no `-q`, `--dist loadfile`); reads
  nothing about `setup-uv`/`uv sync`. My test-shards are not in its set; a retry
  step creates no pytest line. Unaffected.
- **`tests/ci/test_docs_lint_job.py`** — the `docs-lint` job only (not a
  test-shard). It forbids `|| true` / `set +e` / `exit 0` / step-level `if:` /
  `continue-on-error` in that job. I am not touching `docs-lint`, but I will
  avoid those soft-fail idioms in my retry wrapper anyway (correct behaviour: the
  install step must exit non-zero when all attempts fail, so the shard still reds
  on a genuine, deterministic failure).
- **`tests/architectural/test_no_duplicate_suite_execution.py`** (suite ledger) —
  a step counts as a "suite gate" only if it reaches a **pytest** invocation; a
  live negative-control fixture (`SETUP_ACTION`, a composite whose only `run` is
  `uv sync --frozen --all-extras`) proves a `uv sync`-only step adds **no** gate.
  So a new retry install step (or a helper invocation) is invisible to the
  ledger. `("ci-router.yml","tests-docs"|"tests-e2e"|"tests-corpus-blocking")` are
  each authorized for exactly one pytest invocation — I add none.
- **`tests/ci/test_ci_router_transcription_guards.py`, `test_gate_selection_authority.py`,
  `test_ci_quality_path_filters.py`** — pin the two routing authorities (dorny
  `filter:` path→group, job `if:` group→job). They do not read step text; adding
  the helper file matches the existing `ci` / `ci_config` filter groups
  (`scripts/ci/**`), which is correct routing and changes no gate.
- **Out-of-scope lookalikes (do NOT re-point for this change):**
  `test_interpreter_matrix_env_pinning.py` (pins the exact
  `uv sync --frozen --all-extras --python "3.13"` string for **ci-nightly**),
  `test_nightly_architectural_backstop.py`, `test_contracts_workflows.py`
  (`uv sync --frozen --no-install-project` for `contracts/tools/` jobs only),
  `test_performance_marker_guard.py`, `test_module_tests_matrix.py` (forbids
  `uv sync` in `module-tests.yml` — it reuses the `warmup` composite).

### Composite-action note

`.github/actions/` holds exactly one composite — `warmup/action.yml` ("Warmup /
test-env creation"), used by `module-tests.yml` / `ci-modules.yml`, **not** wired
into `ci-router.yml`. It already does cache-keyed `.venv` reuse. Converting the
router test-shards' inline `uv sync` into a `uses:` of a composite is NOT chosen:
it buys nothing for these three jobs over an inline change and, if ever applied to
the architectural jobs, would break the two step-shape finders above
(`run_contains="uv sync"`). The chosen mechanism (cache input + a small
by-path-invoked helper) keeps the inline `run:` shape the finders expect for the
untouched jobs and needs no test re-point.

### What slice 3 adds (new focused assertion)

Because no existing test pins the test-shard sync step, slice 3's "add a focused
assertion that the resilience is present" is a **new** `tests/ci/` wiring test
that parses `ci-router.yml` and asserts each of `tests-docs`/`tests-e2e`/
`tests-corpus-blocking`: (a) its `setup-uv` step sets `enable-cache: true`, and
(b) its install step routes `uv sync` through the bounded-retry helper. Removing
either resilience mechanism reds this test (the slice-3 done-when). A second,
helper-level unit test proves the retry actually retries a transient failure and
still propagates a deterministic final failure (so it cannot green-wash a real
install error). Helper convention: `scripts/ci/` is a namespace package (tests
`from scripts.ci import …`; CI invokes `python3 scripts/ci/<x>.py …`), mirroring
`green_match.py`; no `__all__` is required (that gate covers only
`src/charter`/`src/kernel`).

## 4. `astral-sh/setup-uv` cache + pin state

- **Action pin:** every `setup-uv` use in `ci-router.yml` is pinned to
  `astral-sh/setup-uv@20cfd1bf945f4377ade1205e4dbc17946fc9a30d # v10.0.1`
  (first occurrence line 682; identical SHA on every other use).
- **Cache:** `enable-cache` is **not set anywhere** in `ci-router.yml` — no job
  currently enables the uv cache. The only caches in the workflow are the
  `actions/cache` steps for the *test-universe collection store* in
  `architectural-heavy` (lines 995–1014), unrelated to wheel downloads.
- Implication: every job cold-downloads its wheels on every run; a transient
  download failure has no cache to fall back on. `enable-cache: true` reduces the
  download volume/frequency on warm runs but a cold cache still downloads, so it
  is a *reducer*, not a guarantee — the bounded install retry is what closes the
  residual transient-failure window.

## 5. Flakiness-policy carve-out (why a network-install retry is NOT "retry-to-green")

`docs/development/testing/testing-flakiness.md` (updated 2026-10-05) states the
governing rule: *"we never make a test pass by retrying it until it goes green"*
and refuses the retry plugins `pytest-rerunfailures` / PyPI `flaky`. Crucially,
that rule and all three flake **tiers** are about **tests** — a test's pass/fail
outcome. Its concern is that a green-after-retry hides a genuine code/logic
regression (the "fixed because it looks fixed" trap).

A bounded retry on `uv sync --frozen --all-extras` is categorically different:

- It wraps a **network dependency-install step that runs before any test is
  collected**. It cannot mask a test outcome, a code regression, or a logic bug —
  there is no test result in scope at that point.
- `--frozen` means the install is pinned to `uv.lock`; a retry re-attempts the
  *same* pinned download, it does not relax, reselect, or change what is
  installed. A genuine dependency/lock defect fails *deterministically* on every
  attempt (and is independently gated by the always-on `uv-lock` job,
  `uv lock --check`), so a bounded retry cannot green-wash it.
- This is the Tier-3 "genuinely environmental" shape (an OS/network resource that
  cannot be fully isolated), but at the **setup layer**, where the sanctioned
  response is surgical handling — not a test rerun. No `pytest-rerunfailures` / no
  `flaky` plugin / no `--reruns` is added; the lockfile, `pyproject.toml`, and the
  gate's test selection/semantics are untouched.

This matches the issue's explicit non-goal note and the mission brief's carve-out.

## 6. In-flight CI work (collision check)

`git log --since=90.days -- .github/workflows/ci-router.yml` returns **3**
commits, all within the last few days:

- `5908cbbe` fix(landing): route every consumed mission-pack sub-tree to its consumer modules
- `23db9453` fix(ci): fan mission pack content and lifecycle.py out to their consumer test modules (#6166)
- `e95ed51d` fix(landing): refuse moments on/off cleanly and treat non-UTF-8 as unreadable

The two `#6166` commits edited the **`changes` path-routing filter block** (the
`mission_pack_content` / `cli_lifecycle` groups, lines ~130–262), NOT the
`uv sync` / `setup-uv` steps of any shard. No overlap with this mission's region.

Open PRs that touch CI-adjacent areas:

- **#6190** (`issue-6173-derived-consumer-census`, draft) — "CI routing: durable
  derived consumer census for CI fan-out" (#6173). This is about the
  `changes`/`select_modules` fan-out authority, a different region of
  `ci-router.yml` (the `changes` job's filter/outputs) than the shard `uv sync`
  steps I touch. Low conflict risk; **I will rebase on the latest `main` before
  pushing** and keep edits scoped to the module-test shards' `uv sync`/`setup-uv`.
- #6166 is already landed on `main` (its commits are in the churn above).

No open PR edits the `tests-docs` / `tests-e2e` / `tests-corpus-blocking` step
bodies, so the fix's blast radius does not overlap current in-flight work.

## 7. ci-router.yml churn history (90 days)

3 commits (listed in §6), all 2026-10 landing/CI-fan-out fixes. The file is
stable; the last structural reinstatement was `#3995` (lean modular CI). No prior
change in the window touched the shard `uv sync` steps — consistent with the
transient failure being environmental rather than a regression introduced by a
recent edit.
