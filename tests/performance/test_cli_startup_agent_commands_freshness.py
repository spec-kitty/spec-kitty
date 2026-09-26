"""FR-005 startup regression guard (two-tier) for lever C: the wall-clock
tier (T022).

This is SC-002's own delivery point (post-tasks analysis findings B2/C3):
"a startup-time regression guard for the lever-C portion exists... a
structural check... plus a wall-clock check, scoped to the
``performance``-marked nightly lane only, never asserted as a hard
wall-clock threshold inside a fast unit-test shard." Ruling 4 makes this
guard responsible for catching a startup regression on CLI-source-only PRs,
because the e2e shard does not run on those PRs.

Modeled directly on the ``#4409``/``#4417`` precedent,
``tests/performance/test_cli_startup_budget_4409.py`` (read in full before
writing this file, per the charter's canonical-sources rule) -- same
two-tier split.

**WP06 review cycle 2 (WP06-C1-001, severity 4):** the two DETERMINISTIC
structural checks (T020, T021) that originally lived in this file were
relocated out of ``tests/performance/`` -- no per-PR CI shard selects this
directory (``.github/ci-module-registry.yml``'s ``tests/performance`` row
records "no per-PR lane selects this directory"; ``ci-nightly.yml`` triggers
only on ``schedule``/``workflow_dispatch``), so a guard living only here
never ran before merge, defeating Ruling 4's "catch startup regressions...
before merge" requirement. T020 now lives in
``tests/specify_cli/runtime/test_agent_commands_freshness_precheck_shape.py``
(selected by the ``specify_cli_runtime`` module's per-PR matrix leaf). T021
now lives in ``tests/cli/test_register_commands_lazy_import_shape.py``
(selected by both ``ci-router.yml``'s hardcoded ``tests-cli`` job and the
``cli`` module's per-PR matrix leaf). THIS file keeps only T022 -- the
wall-clock tier is correctly homed here: ``tests/performance/`` IS the
intended nightly-only lane for a ``@pytest.mark.performance``-marked
wall-clock assertion (C-002's cadence discipline: this guard must never
migrate real wall-clock assertion into a fast per-PR shard).

**Tier 2 (wall-clock, nightly-only).** One real subprocess-timed leaf-command
invocation, ``@pytest.mark.performance``-marked exclusively (never asserted
in a fast/unit-marked test) -- deliberately NOT ``--help``: click's eager
``--help`` handling exits before ``main_callback``'s body runs, so it never
pays (and could never catch a regression in) the
``ensure_global_agent_commands()`` cost this guard exists to police.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import pytest

from tests._perf_helpers import assert_timing_budget

REPO_ROOT = Path(__file__).resolve().parents[2]

#: Generous vs the observed warm (cache-hit) baseline for a leaf command on a
#: loaded dev box (~0.85 s), tight vs the ~11 s a from-scratch full render
#: costs when a fresh ``SPEC_KITTY_HOME`` has never populated the freshness
#: stamp -- exactly the pathology this guard exists to catch if it comes
#: back on a WARM (second) invocation instead of only the first. Mirrors
#: ``_HELP_BUDGET_SECONDS``'s stated design intent from the ``#4409``
#: precedent: absorb CI contention without being vacuous against the
#: regression.
_LEAF_COMMAND_BUDGET_SECONDS = 5.0

# A real leaf command that runs through `main_callback()`'s full
# non-fast-pathed path -- never `next`, `live-work hook`, or `doctor skills`
# (see `_is_next_fast_path` / `_is_live_work_hook_fast_path` /
# `_is_doctor_skills_invocation` in the CLI source), so it pays
# `ensure_global_agent_commands()`'s cost exactly like every ordinary
# command. Cheap and side-effect-light: `context list --json` only reads
# workspace-context state and never mutates the project.
_LEAF_COMMAND: tuple[str, ...] = ("context", "list", "--json")


def _leaf_command_env(tmp_home: Path) -> dict[str, str]:
    """Hermetic subprocess env: isolated HOME/SPEC_KITTY_HOME (never the
    real home directory) and PYTHONPATH forced to THIS checkout's own
    ``src/``.

    spec-kitty's own mission-lane dev layout runs several checkouts
    (worktrees) as siblings sharing one interpreter/venv, whose editable
    install can point at a DIFFERENT checkout's ``src/`` than the one this
    test file lives in. Forcing PYTHONPATH guarantees the measured
    invocation always exercises this worktree's code, not some other one.
    """
    env = dict(os.environ)
    env["PYTHONPATH"] = str(REPO_ROOT / "src")
    env["HOME"] = str(tmp_home)
    env["SPEC_KITTY_HOME"] = str(tmp_home / "kittify-home")
    env["SPEC_KITTY_NO_UPGRADE_CHECK"] = "1"
    for var in ("XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_CACHE_HOME", "XDG_STATE_HOME"):
        env.pop(var, None)
    return env


def _run_leaf_command(env: dict[str, str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "specify_cli.__init__", *_LEAF_COMMAND],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )


@pytest.mark.performance
def test_repeated_leaf_command_invocation_stays_inside_its_startup_budget() -> None:
    """The wall-clock half: a WARM repeated invocation must not re-pay the render.

    WP04's freshness short-circuit exists precisely so that, after the first
    (necessarily slow, cache-cold) invocation populates the on-disk stamp
    under a given ``SPEC_KITTY_HOME``, every subsequent invocation against
    the SAME home returns without rebuilding an ``AssetPreparation`` at all.
    Reintroducing unconditional rendering (dropping WP04's early return, or
    dropping WP05's lazy command-module imports) makes every invocation pay
    a real cost again -- this test's whole point is to distinguish "the
    second call is fast" from "the second call is slow", so it deliberately
    invokes the leaf command TWICE against one isolated, never-real home and
    only times the second (warm) call. `context list --json` runs from an
    isolated tmp cwd with no project markers, so it always resolves to the
    same ``not_in_project`` JSON error (exit 1) regardless of where this
    suite happens to run -- the timing target is `main_callback`'s startup
    cost, not the subcommand's own body.
    """
    with tempfile.TemporaryDirectory() as tmp_home_str:
        tmp_home = Path(tmp_home_str)
        env = _leaf_command_env(tmp_home)

        warmup = _run_leaf_command(env, tmp_home)
        warmup_ok = warmup.returncode in (0, 1)

        started = time.monotonic()
        completed = _run_leaf_command(env, tmp_home)
        elapsed = time.monotonic() - started

    completed_ok = completed.returncode in (0, 1)
    measured = elapsed if (warmup_ok and completed_ok) else float("inf")
    name = "spec-kitty context list --json (warm, repeated-invocation) startup"
    if not warmup_ok:
        name = f"{name}; warm-up exit={warmup.returncode}; stderr={warmup.stderr[-2000:]}"
    elif not completed_ok:
        name = f"{name}; exit={completed.returncode}; stderr={completed.stderr[-2000:]}"
    assert_timing_budget(measured, _LEAF_COMMAND_BUDGET_SECONDS, name=name)
