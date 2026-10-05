---
title: Test-flakiness handling policy
description: "Spec Kitty's suite-wide flaky-test policy: how to detect a flake, what is and isn't allowed (never retry-to-green), and the disposition of each known flake surface."
doc_status: active
updated: '2026-10-05'
audience: docs/context/audience/internal/lead-developer.md
type: explanation
related:
- docs/development/testing/testing-parallel.md
---
# Test-flakiness handling policy

A *flaky* test is one whose pass/fail outcome changes between runs **without any
change to the code under test** — it sometimes goes red on CI for reasons
unrelated to the diff under review. Flakes waste review cycles and, left
unmanaged, normalise a red CI that everyone learns to ignore.

This page is the suite-wide policy for handling them: how we **detect** a flake,
what we are allowed to do about it (and explicitly *not* allowed to do), and the
current disposition of every known flake surface in this repo.

> **The one rule that governs everything below:** we never make a test pass by
> *retrying it until it goes green*. A green-after-retry is the
> "fixed because it looks fixed" trap — it hides genuine regressions and is
> incompatible with this repo's live-evidence / anti-laziness discipline. Retry
> plugins (`pytest-rerunfailures`, the PyPI `flaky` plugin) are therefore **not
> adopted**, and are not present in the dependency set.

## ⚠️ Naming: `flaky` the marker is *not* "flaky" the concept

This repo already registers a `flaky` pytest marker, and it means something
**narrow and unrelated** to this policy. Per
[ADR 2026-04-20-1](../../adr/3.x/2026-04-20-1-mutation-testing-as-local-only-quality-gate.md),
`@pytest.mark.flaky` means *"passes reliably in the main suite but is
non-deterministic **under `mutmut` / forking pipelines**"* — it is a deselection
bucket for the mutation-testing sandbox, **not** a CI-quarantine mechanism.

Do not reach for the `flaky` marker to deal with a CI flake. If a genuine
quarantine mechanism is ever needed, it must use a **different** name
(`quarantine`, see below) so the two never get conflated.

## The three tiers

Every flake in this suite falls into one of three tiers, and each tier has a
single sanctioned response.

| Tier | What it is | Example | Sanctioned response |
|---|---|---|---|
| **1. Threshold / budget gate** | A test that asserts a measurement stays under a wall-clock / size budget. CI runners are shared and noisy, so a generous gate occasionally trips with no real regression. | Timing-budget tests (`tests/architectural/test_spec_kitty_home_pin_budget.py`), the `-m timing` gate. | **Tune the budget — never retry.** Tune a budget only with evidence: a real regression adds time **consistently** and still trips a calibrated gate; a retry would mask exactly that. A test that pays interpreter cold start (a fresh `python -m specify_cli` per run) does not take an absolute number of seconds at all: it asserts a **runner-relative measure**, the ratio of its median to a start-up floor median sampled interleaved in the same run, with the limit in `tests/_perf_helpers.py` and calibrated from recorded data (see the audit row and [the decision record](../../adr/4.x/2026-10-05-2-runner-relative-performance-budgets.md)). Widening an absolute budget to absorb a slow runner is not accepted for these tests. |
| **2. Correctness test** | A test of logical behaviour that should be 100% deterministic. If it flakes, the test (or the code) has a hidden nondeterminism — shared global state, ordering assumptions, fixture-teardown races, monkeypatch leakage, import-time side effects. | `tests/specify_cli/shims/test_registry.py` (parallel-collection nondeterminism). | **Fix the root cause — never retry.** A correctness test that needs a retry is lying. Find the nondeterminism and remove it. |
| **3. Genuinely environmental** | A test that depends on an OS-global resource — real TCP ports, singleton daemons, the real filesystem — that cannot be fully isolated per worker. | Historical real-port / daemon suites, deleted with the sync transport (issue #5). | **Surgical handling only.** First serialise (`-n0`) and isolate (per-worker HOME) — see [testing-parallel.md](testing-parallel.md). Only if a residual, irreducible environmental flake remains do we **quarantine** (below) — never a blanket retry. |

## Detection: confirm a flake before you treat it

One red run is a single data point — pytest alone cannot tell *flaky* from
*broken*. Before declaring a test "flaky" and applying any of the responses
above, **reproduce the nondeterminism**:

- Re-run the test in isolation, and under the parallel runner it failed on:
  ```bash
  PWHEADLESS=1 pytest <path> -n auto --dist loadfile -p no:cacheprovider
  ```
- For ordering / hash-seed flakes, re-run under different `PYTHONHASHSEED`
  values and diff the collected node IDs.
- For a confidence signal, use the existing **stability ratchet** — N consecutive
  green parallel runs, the same gate CI uses for shard flips. The authoritative
  invocation lives in
  [testing-parallel.md → Running the stability ratchet locally](testing-parallel.md#running-the-stability-ratchet-locally);
  point it at the suspect `<path>` instead of fabricating a new command.
  (Full harness: `tests/_support/coverage_safety/README.md`.)

A test that cannot be made to fail again under these probes is **not** confirmed
flaky — do not annotate it.

## Tooling decision

**No retry tooling — ever.** `pytest-rerunfailures` / PyPI `flaky` are
deliberately not in the dependency set (see the rule at the top). Detection and
isolation reuse what the repo already has; the only thing built specifically for
this policy is the `quarantine` marker.

- **No retry plugin.** See the rule at the top.
- **Detection** uses the existing stability ratchet
  (`tests._support.coverage_safety.ratchet`), not a new confidence tool.
- **Isolation** (the first line of defence for Tier 3) is the existing
  per-worker HOME isolation + serial `-n0` pass documented in
  [testing-parallel.md](testing-parallel.md).

### `quarantine` — built, env-gated, non-blocking

The sanctioned mechanism for an irreducible Tier-3 flake is a dedicated
`quarantine` marker — **not** a retry, and **not** the existing `flaky` marker.
It is implemented as a single, un-bypassable chokepoint:

1. **Registered** canonically in `pytest.ini`'s `markers` block — the single
   source of truth for the marker registry (#2034) — sufficient for
   `--strict-markers`.
2. **Held out of every normal run.** `tests/conftest.py`'s
   `pytest_collection_modifyitems` skips any `@pytest.mark.quarantine` test
   **unless `SPEC_KITTY_RUN_QUARANTINE=1`**. Because this is collection-time and
   global, no `-m` selector in any CI job (present or future) can accidentally
   run a quarantined test — the gate cannot be forgotten. The opt-in is strict
   (only the literal `"1"`); the pure decision lives in
   `tests/_support/quarantine.py` and is unit-tested.
3. **Visible only by explicit opt-in; not currently scheduled in CI.** Setting
   `SPEC_KITTY_RUN_QUARANTINE=1` and selecting `-m quarantine` runs a
   quarantined test for real locally. The current hosted CI topology has one
   `suite` job and no `quarantine-visibility` lane, so quarantine visibility is
   **not enforced there**. A PR that adds the first quarantined test must also
   add a non-blocking visibility lane (or explicitly change this policy); it
   must not rely on the normal suite, which skips quarantined tests.

**To quarantine a test:** mark it `@pytest.mark.quarantine` with a one-line
reason **and a tracking-issue link** — every quarantined test is tech debt with
an owner. The wiring above (`test_quarantine_marker.py`) is enforced.

As of this writing **no test is quarantined** (see the disposition table — every
known surface is fixed, correctly handled, or retired). The mechanism exists so the first
irreducible flake has a sanctioned home instead of a retry.

## Audit + disposition of known flake surfaces

| Surface | Tier | Disposition |
|---|---|---|
| Historical `tests/architectural/test_wp_prompt_build_latency.py` NFR-002 latency surface | 1 | **Retired — this surface no longer exists.** The low-signal suite cleanup in PR #3285 removed the file. The current timing policy is carried by the live `-m timing` lane and its current budget tests; a future latency flake gets a new, separately evidenced row. |
| `doctor restart-daemon` issue #1153 / NFR-002 wall-clock gate | 3 | **Retired as a portable CI performance claim in PR #3285.** The original ≤10-second end-to-end requirement depended on OS-global daemon and port state and repeatedly failed during hosted-macOS control-plane bootstrap without a corresponding product regression. The controlled Linux lane now enforces the replacement functional contract: the old daemon stops, a distinct PID starts, and the control plane becomes healthy within bounded subprocess and readiness timeouts. macOS remains supported through platform-independent tests and local smoke evidence; a future cross-platform restart performance SLO requires a controlled developer/canary harness because shared-runner wall clock is not accepted as evidence. |
| `tests/sync/test_orphan_sweep.py` and `tests/_real_port_suites.py`'s `FIXED_RANGE_SUITES` (real fixed ports 9400–9449, daemons) | 3 | **Retired — this surface no longer exists.** The sync transport that owned it was deleted (issue #5): `tests/sync/` and `tests/_real_port_suites.py` are gone from the repo, so there is nothing left to serialise or quarantine here. `make test-full`'s current topology (one parallel pass plus dedicated `-n0` serial passes for `stress`/`timing`) is described in `CLAUDE.md`'s Commands section. |
| `tests/performance/test_owned_checkout_perf.py` (three owned-checkout commands), `test_cli_startup_budget_4409.py` (`--help` start-up) and `test_cli_startup_agent_commands_freshness.py` (warm repeated leaf command), nightly `performance` job, #5419 / #5614 | 1 | **Fixed by a runner-relative measure.** The three owned-checkout tests compared a median with an absolute 2.5 s and went red on four of six nightly runs with no product change: the same bare `--help` moved from 1.14 s to 1.95 s between runs. They now assert the ratio of the command median to a start-up floor median (`--version`), five spawns of each interleaved in the same run, against `OWNED_CHECKOUT_RATIO_LIMIT`; the two start-up tests assert the ratio of the start-up median to a fixed interpreter workload measured in the same run (`STARTUP_RATIO_LIMIT`, `WARM_LEAF_RATIO_LIMIT`). No absolute number of seconds remains. Every limit lives in `tests/_perf_helpers.py` and `tests/architectural/test_perf_limit_authority.py` fails when another test file defines one. The limits come from recorded clean and planted ratios (idle and CPU-throttled), with their headroom, in the [decision record](../../adr/4.x/2026-10-05-2-runner-relative-performance-budgets.md); committed planted-work tests prove each relative assertion can fail. No retry was added. |
| `tests/specify_cli/shims/test_registry.py` (parallel-collection nondeterminism) | 2 | **Fixed at root cause.** Parametrising over `list(<frozenset>)` produced a `PYTHONHASHSEED`-dependent case order, so xdist workers collected different orders ("Different tests were collected between gw0 and gwN"). Changed to `sorted(<frozenset>)`, making collection order deterministic across workers. Verified: identical node-id order under different hash seeds. |
| `tests/sync/tracker/test_egress_single_authority.py`, `tests/sync/test_transport_revocation_matrix.py`, `tests/sync/tracker/test_saas_client*.py` and siblings (module-level accumulator / thread-identity state under bare `-n <N>`) | 2 | **Retired — this surface no longer exists.** The sync transport that owned it was deleted (issue #5): `tests/sync/` is gone from the repo, so there is nothing left here to fix or re-flake. The root-cause fix this row used to describe (`tests/conftest.py`'s default `--dist loadfile` promotion for xdist) is unaffected — it applies to any file, not specifically to the deleted `tests/sync/` tree. |
| Historical `tests/sync/test_daemon_self_retirement.py` daemon-self-retirement reports | 2 | **Retired — this surface no longer exists.** The sync transport that owned it was deleted (issue #5); `tests/sync/test_daemon_self_retirement.py` and its old integration receipt are gone from the repo. |

## Adding a new test? Avoid the common root causes

When a correctness (Tier 2) test flakes, it is almost always one of these — fix
the cause, do not retry:

- **Unordered data used where order matters.** Iterating a `set`/`frozenset`/`dict`
  for parametrize IDs or assertion sequences → `PYTHONHASHSEED`-dependent order.
  Wrap in `sorted(...)`.
- **Fixture-teardown races / leaked global state** between tests sharing a module
  or process.
- **`monkeypatch` / env-var leakage** across tests (rely on the per-worker HOME
  isolation; don't mutate process-global state without restoring it).
- **Import-time side effects** that bind a path or singleton before fixtures run.
- **Time-sensitive assertions** in a non-timing test — move the timing concern to
  a Tier-1 budget gate with a generous threshold, or remove the wall-clock
  dependency.
- **`patch.dict(sys.modules, ...)`** — snapshot-restores the whole dict on exit,
  evicting any module first-imported inside the patched window (spec-kitty#89/#99;
  ratcheted by `tests/architectural/test_no_sys_modules_patch_dict.py`). Use
  `monkeypatch.setitem(sys.modules, key, value)` per key instead — it is the only
  accepted `sys.modules` seam.

## Test-run baseline-red gotcha

A red test is not automatically *your* red. A local or backgrounded `pytest` run over
anything broad (the full suite, `tests/merge/`, `tests/architectural/`, the regression job)
will surface failures you did not cause. **Classify every failure before you act on it** —
misattribution wastes effort and, worse, tempts an agent to green-wash a signal the project
deliberately keeps red.

Five baseline-red categories that are **not yours to fix**:

1. **Pre-existing known-P0 reds.** Per [ADR 2026-07-17-1](../../adr/3.x/2026-07-17-1-red-main-is-honest-ci-is-release-authority.md),
   an open P0 bug is *expected* to red mainline. Its reproduction carries
   `@pytest.mark.p0_repro(issue=N)` and runs only in the nightly `p0-repro` lane, so it
   never reds a PR. You will see it only in a nightly run or in an explicit
   `SPEC_KITTY_RUN_P0_REPRO=1` run, where each failure names its `[OPEN P0 #N]` issue.
   **Leave it red.** Do not unmark it, quarantine it, or "fix" it in an unrelated change
   (the fold-first policy in [pr-landing.md](../how-to/pr-landing.md)).
2. **CI-environment failures.** Auth state (`logged_out_on_connected_teamspace` during
   `upgrade`) and the gate opt-out `SPEC_KITTY_SKIP_PRE_REVIEW_GATE` (the pre-review
   gate's own name since #3980 — it no longer reads the sync-disable vocabulary) make
   some CI jobs red while the same tests pass locally. These are configuration, not
   your diff.
3. **Stale-install false reds.** Product code that shells out to `spec-kitty` (e.g. the
   `merge-driver-meta`/`-traces` commands) only fires when an up-to-date `spec-kitty` is
   installed. Between landing a change and `pip install -e .`, coverage/gate jobs report
   false reds for lines that are actually exercised via subprocess.
4. **Stale-venv false reds.** A `ModuleNotFoundError` (or other import failure) for a package
   that *is* declared and pinned (`pyproject.toml` / `uv.lock`) usually means the local
   `.venv` was never (re)synced to that pin, not a real regression. Run
   `uv sync --frozen --all-extras` and retry the failing test before recording it as
   pre-existing or unrelated — a stale venv is indistinguishable from real breakage in raw
   pytest output (#648: a PR's `## Tests run` section excluded a whole
   test file over exactly this `ModuleNotFoundError`, when a clean `uv sync --frozen
   --all-extras` reproduced 1621/1621 passing with no exclusion needed).
5. **Ambient read-only `.git` above basetemp.** When pytest's basetemp has an ancestor
   that is itself a git checkout — true of every exe.dev VM, and reproducible with a
   read-only `/tmp/.git` mount when basetemp lives under `/tmp` — status and lifecycle
   writers that resolve their lock root by climbing to the nearest `.git`
   (`resolve_canonical_root`) land the lock inside *that* ancestor checkout. If that
   `.git` is read-only, `append_lifecycle_event` swallows the resulting `PermissionError`
   as a best-effort `OSError` and silently persists nothing, reddening every
   event-recording assertion (130 nodes red in the #142 repro). This is host setup, not
   your diff. The guard is the autouse `_hermetic_canonical_root` fixture in
   `tests/status/conftest.py`, exercised end-to-end by
   `tests/status/test_hermetic_ambient_git.py` (#142); the identity-resolution variant of
   the same ancestor leak is pinned by the `no_git_ancestry_inside_tmp_path` fixture in
   `tests/zeitgeist_client/conftest.py` (hoisting tracked at #614). Run inside the sandbox
   those guards establish rather than "fixing" the read-only ancestor mount.

**The attribution test:** a failure is yours to fold only if it is **red on your branch and
green on the base**. Confirm the base state by running the same node id against
`upstream/main` — e.g. from a throwaway worktree with
`PYTHONPATH="$(pwd)/src" python -m pytest <nodeid>` — or by checking the tracker for a P0
label. When you *do* add a red-first P0 reproduction on purpose (per the ADR), mark it
`p0_repro(issue=N)`, docstring the issue, and make sure it fails for the product reason,
not because of setup. It runs only in the nightly; see
[Red Main and Release Readiness](../reference/red-main-and-release-readiness.md#where-the-reproduction-runs-the-nightly-p0-repro-lane).

This applies to **dispatched subagents** as much as the orchestrator: an implementer that runs
the suite in its worktree must not report the baseline reds as regressions or try to fix them.

## See also

- [Running the test suite in parallel](testing-parallel.md) — per-worker HOME
  isolation, the serial marker passes, and the stability ratchet.
- [ADR 2026-04-20-1](../../adr/3.x/2026-04-20-1-mutation-testing-as-local-only-quality-gate.md)
  — the `flaky` / `non_sandbox` markers (mutmut deselection; distinct from this
  policy).
- [How-to: run mutation tests](run-mutation-tests.md).
