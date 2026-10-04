---
title: Running the test suite in parallel
description: 'How to run the Spec Kitty test suite in parallel locally and in CI: the one correct command, why it is shaped that way, and reproducing the coverage-neutrality gates.'
doc_status: active
updated: '2026-10-04'
audience: docs/context/audience/internal/lead-developer.md
type: how-to
related:
- docs/development/testing/testing-flakiness.md
- docs/archive/plans/testing/test-suite-acceleration-plan.md
- docs/archive/plans/testing/ci-job-timings.md
- docs/archive/plans/testing/ci-coverage-union-audit.md
- docs/archive/plans/engineering-notes/testing-parallel-ci-topology-status.md
---
# Running the test suite in parallel

The Spec Kitty test suite runs safely in parallel locally and in CI, typically
at least 2× faster on a machine with four or more cores. This page explains the
one correct local command, why it is shaped the way it is, and how to reproduce
the coverage-neutrality gates CI uses.

For what to do when a test goes red on CI *unrelated to your diff* — budget gates
vs. correctness flakes vs. environmental flakes, and why we never retry-to-green —
see the [test-flakiness handling policy](testing-flakiness.md).

## The local command

Do not hand-roll a broad pytest invocation — `make test-fast` and `make test-full`
already encode the parallel/serial split below, and a hand-rolled command drifts
out of date the moment that split changes:

```bash
make test-fast    # fast tier of the typical blast-radius directories (target <2 min)
make test-full    # everything, parallel + serial passes — CI's target, not PR validation
```

`make test-full` runs the bulk of the suite across worker processes, then gives
each of the two parallel-unsafe families (`stress` and `timing`) its own
dedicated serial pass — see [AGENTS.md](../../../AGENTS.md#commands) for the
exact pass breakdown and the PR-validation test policy.

## Why `--dist loadfile` (never bare `--dist load`)

`pytest-xdist` supports several distribution modes. We always use `loadfile`:

- **`loadfile`** keeps every test that lives in the same file on a single
  worker. File-scoped fixtures (`scope="module"`, file-level collection
  ordering, shared module state) keep working exactly as they do serially.
- **`load`** (the bare default) scatters a single file's tests across multiple
  workers. That breaks file-scoped fixtures and any test that relies on
  collection order within a file.

For that reason: **always pass `--dist loadfile`; never use bare `--dist
load`.** CI uses `loadfile` for the same reason.

`-p no:cacheprovider` disables pytest's cache plugin so a parallel run never
races on the shared `.pytest_cache` directory.

## Per-worker HOME isolation (the master enabler)

A parallel run **never touches the real `~/.spec-kitty`**. Each `pytest-xdist`
worker — and the serial "master" run when you omit `-n auto` — gets its own
isolated home directory. The isolation is set up in `tests/conftest.py`:

- `pytest_configure` points `HOME` / `USERPROFILE` and the XDG dirs
  (`XDG_CONFIG_HOME`, `XDG_DATA_HOME`, `XDG_STATE_HOME`) at a per-worker base
  **before collection**, so modules that bind a home-derived path at import time
  (for example paths derived from `get_runtime_root()`) resolve into the
  isolated home.
- An autouse, function-scoped fixture re-asserts the `HOME` / `USERPROFILE` / XDG
  env vars for every test, keyed by worker id, so call-time `Path.home()` reads
  are isolated too. It does **not** monkeypatch `Path.home` (that approach was the
  cycle-1 regression that broke ~16 `tests/sync` cases — the fixture relies on
  `Path.home()` natively resolving `HOME` via `expanduser`), so a test that sets
  up its own tmp home via `setenv('HOME', ...)` cleanly overrides the per-worker
  baseline.

The per-worker base is keyed by the xdist test-run UID and the worker id, so two
workers in the same run get distinct homes (no collision) and successive runs do
not reuse stale state. The regression guard
`tests/architectural/test_real_home_isolation_guard.py` (SC-006) and
`tests/test_worker_home_isolation.py` prove this invariant.

Because the real `~/.spec-kitty` is never bound, you do not need to back it up or
worry about a parallel run overwriting your real auth tokens or config.

## Per-run pytest temp root

Every pytest invocation also gets its **own private basetemp** instead of the
shared `/tmp/pytest-of-<user>` numbered tree: `<temproot>/spec-kitty-pytest-tmp/run-<pid>`
(`temproot` honors `PYTEST_DEBUG_TEMPROOT`, then `TMPDIR`). This is a
housekeeping fix, not a #63 fix: pytest's default tree only ever shrinks
through its own locked, timeout-gated pruning, so a long-lived box accumulates
stale `pytest-<N>` roots (some with live `.lock` files) that nobody notices
until someone clears them by hand. A controller-qa audit falsified the
original claim that this also fixed #63's `OSError: could not create numbered
dir … after 10 tries` crash — that crash names a *worker* basetemp, which
takes a code path with no locking or pruning to race in the first place;
#63's actual driver is `tmp_path_retention_policy` (see below), and it remains
open pending a full-suite run that reports a summary.

`tests/conftest.py` wires this in `pytest_configure` via
`tests/_support/run_basetemp.py`; xdist workers nest under the controller's
choice as usual (`…/run-<pid>/popen-gwN`). Consequences worth knowing:

- An explicit `--basetemp` still wins untouched — whoever passes one owns its
  lifecycle.
- Retention is outcome-gated (#76): a healthy run (`ExitCode.OK`) leaves
  nothing behind — it removes the run's dir at interpreter exit. A run with
  failures, errors, or an interruption keeps its private basetemp tree instead,
  so `tmp_path` contents from that run ARE available for post-mortem inspection,
  bounded by the 24 h stale-crash sweep the next run performs at controller
  startup (`STALE_RUN_MAX_AGE_S`, swept from `install_run_basetemp`; it also
  catches a run that never reaches `pytest_sessionfinish`, e.g. a SIGKILL,
  since the exit-gated reap never runs for it either). This differs from
  pytest's own default 3-session retention, which keeps the last three
  sessions' trees regardless of outcome.

## `tmp_path` retention policy

`pytest.ini` sets `tmp_path_retention_policy = failed`: a passing test's
`tmp_path` is removed in the `tmp_path` fixture's own teardown, right after
that test runs, instead of staying alive for the whole session (pytest's
`all` default). Across the ~40k tests `make test-full` collects, retaining
every one's `tmp_path` for the full session is enough on its own to exhaust a
runner's temp filesystem — the diagnosed driver behind #63's pre-summary
crashes. Unlike the *session-end* basetemp wipe (which pytest only does when
`--basetemp` was never given explicitly), this per-test teardown removal is
unconditional — it fires exactly the same whether the run's basetemp came
from `--basetemp`, from this repo's per-run private root above, or from
neither, which is why it still drains the pressure under this repo's scheme
even though a basetemp is effectively always "given" here.

The *other* retention knob, `tmp_path_retention_count` ("how many past
sessions' worth of numbered `tmp_path` dirs to keep"), is a no-op in this
repo: it only ever applies to the code path that prunes pytest's own
default numbered basetemp tree, which never runs once a basetemp is given —
so it is not a lever worth reaching for here.

## The serial marker passes

Per-worker HOME isolation protects per-user state, but it does **not** protect
wall-clock timing or real multi-process/subprocess concurrency. Two marker
families are corrupted by co-scheduled `pytest-xdist` workers and get their
own dedicated serial pass instead of running in the main parallel pool:
`stress` (spawns real multi-process/subprocess concurrency) and `timing`
(measures wall-clock). `make test-full` deselects both from the parallel pass
(`-m "not stress and not timing"`, `pytest.ini`'s parallel-unsafe marker set)
and then runs each family on its own:

```bash
PWHEADLESS=1 pytest tests/ -m "stress and not windows_ci" -n0 -q
PWHEADLESS=1 pytest tests/ -m timing -n0 -q
```

`-n0` forces serial execution even when xdist is installed. The per-test
timeout that guards a hung fork/process from stalling the pass indefinitely is
no longer passed on these commands: since #3143 it comes from the single
per-test timeout authority in `pytest.ini` (`timeout = 240`), which applies to
every pass — parallel and serial alike. See
[The per-test timeout](#the-per-test-timeout) below. These mirror the
`Makefile`'s `test-full` target's serial marker passes.

(The former fourth pass ran the deleted sync daemon's fixed-port suites — five
files bound to the reserved 9400–9449 port range, keyed off
`tests/_real_port_suites.py`'s `FIXED_RANGE_SUITES` registry, isolated so two
workers never contended for the same fixed port. Both the registry and the
sync daemon it protected died with the sync transport, issue #5; there is no
fixed-daemon-port family left to isolate.)

## The per-test timeout

Every test has a **240-second per-test timeout**, set once in `pytest.ini`:

```ini
[pytest]
timeout = 240
```

This is the single per-test timeout authority (#3143). Because it lives in
`pytest.ini`, it applies uniformly wherever pytest reads that file — the Linux
module shards, the Windows job (`ci-windows.yml`), a bare local `pytest`, and
the `make test-fast` / `make test-full` targets — so no surface is left without
one. Before #3143 the flags lived only in CI job definitions (and, briefly, only
in the Makefile serial passes), so Windows CI and every local run had no
per-test timeout at all.

**What a hang looks like now.** When a test runs longer than 240s, pytest-timeout
fails **that one test by name** and the run continues to its summary:

```
+++++++++++++++++++++++++++++++++++ Timeout ++++++++++++++++++++++++++++++++++++
...
FAILED tests/some/module/test_thing.py::test_that_hung - Failed: Timeout >240.0s
```

Contrast the old failure mode: a hang was killed by a job-level
`timeout-minutes`, ending the run with **no summary, no counter, and no named
test** — you could not tell which test wedged.

**Method is per platform, by design.** `pytest.ini` deliberately leaves
`timeout_method` unset. pytest-timeout then uses:

- **`signal`** (SIGALRM) on POSIX — the Linux shards and local macOS/Linux runs.
  This interrupts the running test at the timeout and prints the counted,
  test-named `Failed: Timeout >240.0s` line above.
- **`thread`** on Windows, which has no SIGALRM. A hung `windows_ci` test still
  fails by name with a thread-stack dump. The thread watchdog cannot interrupt a
  wedged native (C) call, so a genuinely stuck native call may still fall through
  to the job-level `timeout-minutes: 20`; re-run such a hang on Linux to get the
  signal-method, counted failure. `ci-windows.yml` carries this note inline.

**240s is a runaway backstop, not a budget.** It sits far above the longest
observed test (~30s on recent shard timing). A legitimately long test should
carry its own `@pytest.mark.timeout(<seconds>)` marker rather than raising this
floor; that marker (and any explicit command-line `--timeout=`, e.g. the
mutation-testing args) overrides the ini default. The default is pinned by
`tests/architectural/test_pytest_ini_timeout_default.py` so it cannot silently
drift back out.

## Volume env gates (`SPEC_KITTY_ULID_VOLUME_FULL`)

Some tests exercise large-volume ULID generation. By default they run at a
**reduced** scale so the local default stays fast; the full scale is reachable
via an env gate (and is exercised on the nightly/full path). The assertion logic
is identical across scales — only the volume changes.

```bash
pytest <ulid_test> -q                               # reduced (fast, default)
SPEC_KITTY_ULID_VOLUME_FULL=1 pytest <ulid_test> -q  # full (nightly parity)
```

## Running the stability ratchet locally

Before any shard is flipped to parallel, it must pass the stability ratchet
(C-RATCHET): N consecutive green parallel runs with no new flakes. The same
entrypoint CI uses is available locally (the WP02 coverage-safety harness):

```bash
python -m tests._support.coverage_safety.ratchet -n 3 -- tests/agent -m "not slow"
```

Exit code `0` means all N runs were green and the flip is accepted; `1` means it
was rejected and the summary names any new or flaky failures. The Python API is
`run_ratchet(...)` from `tests._support.coverage_safety`. See
`tests/_support/coverage_safety/README.md` for the full harness (collection
equivalence and anti-vacuity mutation checks).

## Validate the acceleration (copy-pasteable)

These are the mission's reproducible validation steps. Run them from the repo
root to confirm the parallel run is coverage-neutral and at least 2× faster than
serial. (`.venv/bin/pytest` is the synced project interpreter; substitute
`pytest` if you run it directly.)

```bash
# 1. Serial baseline (whole-suite wall clock) and a per-shard nodeid reference.
time .venv/bin/pytest tests/ -q -p no:cacheprovider     # serial baseline
.venv/bin/pytest tests/charter --collect-only -q | sort > /tmp/charter-serial.nodeids

# 2. Collection equivalence: serial vs parallel must collect identical nodeids.
.venv/bin/pytest tests/charter -n auto --dist loadfile --collect-only -q \
  | sort > /tmp/charter-par.nodeids
diff /tmp/charter-serial.nodeids /tmp/charter-par.nodeids   # must be empty

# 3. Stability ratchet: 3 consecutive green parallel runs (the same gate CI uses).
python -m tests._support.coverage_safety.ratchet -n 3 -- \
  tests/charter -m "fast and not windows_ci"

# 4. Parallel-vs-serial timing: target ≥2× faster on a ≥4-core machine.
time PWHEADLESS=1 .venv/bin/pytest tests/ -n auto --dist loadfile -p no:cacheprovider \
  -m "not stress and not timing"
time PWHEADLESS=1 .venv/bin/pytest tests/ -m "stress and not windows_ci" -n0 -q
time PWHEADLESS=1 .venv/bin/pytest tests/ -m timing -n0 -q

# 5. Real home untouched: mtime/inode unchanged (or path still absent) after the run.
ls -la ~/.spec-kitty 2>/dev/null
```

## CI worker policy and the nightly architectural backstop

This section is for maintainers and CI operators who read a battery job log or edit a
battery command. It records what mission `ci-runtime-stabilisation`
([#5510](https://github.com/spec-kitty/spec-kitty/issues/5510)) changed; the local recipes
above are unchanged.

- **CI passes a literal `-n 4`.** On the 4-vCPU hosted runner `-n auto` resolved to the
  physical core count (2), so the battery ran on half of the available parallelism. Four
  battery-class commands now pass `-n 4 --dist loadfile`: the always-on
  `architectural-fast` job, each leg of `architectural-heavy`, the nightly
  `architectural-backstop`, and the Packs corpus suite. The value equals
  `special_tiers.architectural.workers` in `.github/ci-module-registry.yml`.
- **`-q` is not passed to those commands.** With `-q`, xdist does not print its worker
  banner. Without it, the job log carries the line `created: 4/4 workers`, which is the
  evidence that four workers started. If you add `-q` back, that evidence disappears.
- **A static guard holds both rules.** `tests/ci/test_xdist_worker_policy.py` fails on
  `-n auto`, on a worker count that differs from the registry, and on `-q` in those
  commands. It reads the workflow files, so it needs no CI run.
- **Local targets keep `-n auto`.** `make test-fast` and `make test-full` run on machines
  with an unknown core count, so the literal is a CI-runner fact and not a local
  recommendation. The `-n auto` recipes in this page stay correct.
- **The test list is collected once per job, before pytest.** The heavy battery legs
  and the `ci` module shard that holds the `live_universe` test run a pre-test step
  that collects the full list of tests and stores it, so no test collects inside its
  own setup while four workers compete for the CPUs. A first run still collects once
  per consuming job; a re-run restores the stored list. The step, the cache key, the
  conditions that bypass the store and the `check` that fails a silent fallback are in
  [Stored test-universe collection](../reference/ci-gate-mechanics.md#stored-test-universe-collection).
- **The nightly backstop.** `ci-nightly.yml` job `architectural-backstop` runs the full
  battery base selection (`tests/architectural` with the base marker expression and the same
  deselects) in one plain pytest invocation, with no partition plugin, on Python 3.12 with a
  40-minute timeout. It exists so that a green nightly means the whole battery ran, which was
  not true when the nightly reached the battery only through the `fast or unit` interpreter
  shard. It is part of `nightly-summary`. A red run fails the nightly conclusion that the
  release gate reads, and it escalates to a deduplicated, triaged P0 issue under the suite
  key `architectural`. The decision is recorded in the amendment to
  [ADR 2026-09-26-1](../../adr/3.x/2026-09-26-1-ci-coverage-honesty.md).

## CI shard-topology mission status

Point-in-time mission-status snapshots (named mission IDs, CI-confirmation state, and
per-job PENDING wall-clock records for the `ci-test-topology-performance-01KXBJRT`
shard-topology re-flip) have moved to
[`testing-parallel-ci-topology-status.md`](https://github.com/spec-kitty/spec-kitty/blob/main/docs/archive/plans/engineering-notes/testing-parallel-ci-topology-status.md)
in engineering notes — this how-to page stays focused on the durable local workflow above.

## Reproducing #3115 (the folded-uuid render-width defect)

> **Historical recipe.** The `sync` surface this section reproduces a defect on was retired
> with the local sync transport (Convergence #3881); `src/specify_cli/cli/commands/sync.py`
> no longer exists. The recipe is retained as the record of how #3115 was isolated — the
> `rich` dumb-terminal 80-column fold behavior it demonstrates is still the general lesson.

`sync status` / `sync doctor` render a `Project` column with `overflow="fold"`
(`src/specify_cli/cli/commands/sync.py:1440`, deliberate). At an 80-column
console width a 36-character project uuid folds across two lines and stops
being a contiguous substring of the captured output, so a plain `uuid in out`
assertion fails even though the journal is fully populated. The 80-column
width comes from `rich.console.Console.size`'s `if self.is_dumb_terminal:`
branch, which returns the hardcoded `ConsoleDimensions(80, 25)` **above** the
`COLUMNS` read — so `COLUMNS`, which the affected tests' isolation fixture
already sets, is never consulted. `is_terminal` is true whenever `FORCE_COLOR`
is set to a non-empty value, and `is_dumb_terminal` additionally requires
`TERM` to be `dumb` or `unknown`.

This is reproduced with two environment variables, one victim file, one
process — no `pytest-xdist`, because `--dist loadfile`'s worker assignment is
dynamic and work-stealing, so a reproducer that depends on a particular
assignment would not be reproducible by construction.

```bash
TERM=dumb FORCE_COLOR=1 ./scripts/repro_3115_render_width.sh
```

This runs `tests/cli/commands/test_sync_status_per_project_3030.py` (4
collected tests) alone, in one process, and reds with:

```
FAILED tests/cli/commands/test_sync_status_per_project_3030.py::test_status_names_every_project_with_count_age_and_consent
AssertionError: aaaaaaaa-0000-0000-0000-000000000001 is in the journal but `status` did not name it
1 failed, 3 passed in ~46-56s
```

The sibling victim file reproduces the same defect independently:

```bash
TERM=dumb FORCE_COLOR=1 ./scripts/repro_3115_render_width.sh doctor
```

`tests/cli/commands/test_sync_doctor_per_project_3030.py` collects **12**
tests and reds `1 failed, 11 passed`, with assertion text
`aaaaaaaa-0000-0000-0000-000000000001 is in the journal but doctor did not
name it` (no backticks around `doctor` — the two victim files' f-strings are
not identical, so quote each one's text verbatim rather than assuming they
match).

Only the first of the three seeded projects (`CONSENTED`,
`aaaaaaaa-0000-0000-0000-000000000001`) demonstrates the defect: the other two
(`SILENT`, `OPTED_OUT`) pass at width 80 anyway, via an un-tabled warning
paragraph that reprints their identity outside the folding table.
`Queue 0 event(s)` / `Queue size 0 / 100,000` appear in the captured output
regardless of outcome (`OfflineQueue().size()`, `sync.py:5182-5185`) — they
are **not** a signature of this defect and must not be read as one.

Both counted lines are collected-count-relative: `test_sync_status_per_project_3030.py`
collects 4 (red is `1 failed, 3 passed`), `test_sync_doctor_per_project_3030.py`
collects 12 (red is `1 failed, 11 passed`). A count line that does not
reconcile against its file's own `--collect-only -q` count is not evidence.

**Control** — the same command plus `TTY_COMPATIBLE=0` must PASS. This is what
distinguishes "the width is the cause" from "this file is just broken":

```bash
TERM=dumb FORCE_COLOR=1 TTY_COMPATIBLE=0 ./scripts/repro_3115_render_width.sh
# 4 passed
TERM=dumb FORCE_COLOR=1 TTY_COMPATIBLE=0 ./scripts/repro_3115_render_width.sh doctor
# 12 passed
```

**Determinism** is not established by repetition alone: `pytest-randomly` is
not installed on this tree, so nothing randomises order and "the same node-id
comes up red three times in a row" is trivially true regardless of whether the
red is order-dependent. The clause that can actually fail is running the
failing case **alone, by node-id**, with no file-siblings collected first:

```bash
TERM=dumb FORCE_COLOR=1 python3 -m pytest \
  "tests/cli/commands/test_sync_status_per_project_3030.py::test_status_names_every_project_with_count_age_and_consent"
# 1 failed, collected count 1, identical assertion text
```

A red that needs its file-siblings to run first would be order-dependent and
would not be reproducible by construction (C-004).

`./scripts/repro_3115_render_width.sh` computes its own repo root from its own
location and sets `PYTHONPATH` to that repo's `src/` before invoking pytest.
This matters in a `git worktree`: the shared `.venv`'s
`_editable_impl_spec_kitty_cli.pth` holds the **main checkout's** absolute
`src` path, so a bare `pytest` run inside a worktree using that `.venv`
silently imports the main checkout's live tree instead of the worktree's own
source. The script's `PYTHONPATH` line exists specifically to defeat that.

The same start-directory trap applies to tests that drive a charter write
command. `generate`, `synthesize`, `resynthesize`, `activate` and `deactivate`
ask the charter write guard whether the working directory is a linked worktree,
and a test that aims one of them at a temporary project without moving the
process working directory there passes from a repository root checkout and fails
from a linked worktree. Such a test must request the `charter_cwd_isolation`
fixture and call it with that project root. A suite-wide check enforces this: a
test that reaches the write guard with its working directory inside the checkout
fails at teardown in every checkout, not only in a worktree.

The whole reproducer (one victim file, one process) completes in well under 2
minutes (measured around 46-59s per file on this codebase's base commit,
`bb2020fea9`) — cheap enough that nothing downstream needs to take the defect
on faith.
