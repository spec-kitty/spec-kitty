"""Clock-free signal that an owned-checkout command started doing more work (FR-011).

Mission ``nightly-suites-green-01M44FEP``, WP06.

The wall-clock budgets in ``tests/performance/test_owned_checkout_perf.py`` measure the
runner as much as the product (#5419, #5614). This module pins something a runner cannot
move: the number of ``git`` child processes one invocation of ``agent tasks status``,
``agent mission setup-plan`` and ``agent context resolve`` spawns against a finalized owned
checkout. A new git call on the command path turns the pin red on the pull request that
adds it; there is no clock, no sample median and no tolerance.

What is counted
---------------
Every ``subprocess.Popen`` whose ``argv[0]`` basename is ``git`` or ``git.exe``
(``subprocess.run`` and friends all construct a ``Popen``), recorded while one
``CliRunner`` invocation of the REAL application object (``specify_cli.app``, the object
``python -m specify_cli`` runs) is in flight. Fixture work (building the repository, the
owned checkout and finalizing the Mission) happens before the counter is installed.

What is pinned
--------------
The COLD-cache count of one invocation on the Mission shared by this module's tests, with the
process-global resolution caches dropped first (``clear_workspace_resolution_caches`` and
``git_topology.clear_caches``, the reset ``tests/integration/test_owned_lifecycle_acceptance_e2e.py``
already uses), so the number does not depend on which test ran earlier in the process or on how
many invocations the shared Mission has already served.

Where it runs on a pull request, and the residual gap
-----------------------------------------------------
This file lives in ``tests/cli/commands``, which the ``cli`` module shard runs
(``.github/ci-module-registry.yml`` row ``cli`` has no ``test_dirs``, so it runs the
``tests/cli`` mirror). The job-selection dry run (``scripts/ci/gate_selection.py``
``select_modules``) selects ``cli`` for a change to the files that implement the three commands
(``cli/commands/agent/{tasks,tasks_status_cmd,context,mission,mission_setup_plan}.py``,
``cli/commands/_owned_checkout.py``) and also for ``workspace/context.py`` and
``specify_cli/__init__.py``. It does NOT select ``cli`` for a change only under
``core/owned_mission.py``, ``core/git_ops.py``, ``kernel/git_topology.py``, ``status/*`` or
``mission_runtime/context.py``; such a change reaches this pin in the nightly run only.

Pinned counts and the evidence behind them (C-003: no pin without measured data)
-------------------------------------------------------------------------------
``agent tasks status`` 7, ``agent mission setup-plan`` 14, ``agent context resolve`` 7.

These equal the out-of-process figures: the same three commands run through
``python -m specify_cli`` under ``GIT_TRACE2_EVENT`` spawn 7 / 14 / 7 git processes, call for
call. Hosted drain is switched OFF on purpose (the ``drain_off`` fixture). The root conftest
forces it ON for every test, and with it on ``setup-plan`` also broadcasts a lifecycle envelope,
which resolves credentials and runs four extra ``git config`` / ``git remote get-url origin``
probes under a 2 second deadline in a daemon thread. Forced-on drain is not a default posture
and not what a user runs, and a slow runner could cut the count short (17 instead of 18): a
runner-bound count is the flake class this pin exists to remove.

Five samples each, all identical: three separate pytest processes running this file alone, one
``-n0`` process with the sibling files ``test_doctor_topology``, ``test_implement_base_flag``,
``test_agent_mission_commit_to_branch``, ``test_resolve_lanes_dir`` and
``test_doctor_mission_state`` run BEFORE this file, and one with them run AFTER it.

The Mission and its home are built once per module (about 5 s each when built per test, 31 s
for the file against 6 s). Every count stays the COLD one, because the process-global caches are
dropped before each measured invocation, and the counts are identical with the pin tests alone,
the planted tests alone, the whole file, and the file before and after its siblings, so no test
depends on state another left behind.

The count is exact by intent: it is not a ratchet and has no allowlist. When a command gets
cheaper, lowering its pin is a deliberate one-line edit.
"""

from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from tests._factories import provision_test_charter
from tests.integration.conftest import _git, _init_repo, _write_mission, _write_single_lane_manifest

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

REPO_ROOT = Path(__file__).resolve().parents[3]

_SLUG = "owned-gitcalls-01M44FEP"
_MISSION_ID = "01M44FEP000000000000000001"
_TARGET = "codex/owned-gitcalls"
_GIT_BASENAMES = frozenset({"git", "git.exe"})
_GIT_ARGV_PREFIX_LENGTH = 6


@dataclass(frozen=True)
class _OwnedMission:
    repository_root: Path
    owned_root: Path
    home: Path


@pytest.fixture(scope="module")
def built_mission(tmp_path_factory: pytest.TempPathFactory) -> Iterator[_OwnedMission]:
    """R + P + a finalized one-WP ``single_branch`` Mission, built once for the module (fixture work is never counted)."""
    root = tmp_path_factory.mktemp("owned-gitcalls")
    repository_root = root / "repository-root"
    _init_repo(repository_root)
    owned_root = root / "owned"
    _git(repository_root, "worktree", "add", "-qb", _TARGET, str(owned_root))
    mission_dir = owned_root / "kitty-specs" / _SLUG
    _write_mission(mission_dir, mission_id=_MISSION_ID, slug=_SLUG, topology="single_branch", target_branch=_TARGET, wp_ids=("WP01",))
    _write_single_lane_manifest(mission_dir, mission_slug=_SLUG, mission_id=_MISSION_ID, target_branch=_TARGET, wp_ids=("WP01",))
    wp_file = mission_dir / "tasks" / "WP01-owned.md"
    wp_file.write_text(
        wp_file.read_text(encoding="utf-8").replace("owned_files: []", "owned_files: [wp01.py]").replace("app.py", "wp01.py"),
        encoding="utf-8",
    )
    (mission_dir / "tasks.md").write_text("# Tasks\n\n## Work Package WP01\n\n**Dependencies**: None\n", encoding="utf-8")
    (owned_root / "wp01.py").write_text("# WP01\n", encoding="utf-8")
    provision_test_charter(repository_root)
    provision_test_charter(owned_root)
    for checkout in (repository_root, owned_root):
        _git(checkout, "add", "-A")
        _git(checkout, "commit", "-qm", "owned gitcalls mission")

    home = root / "home"
    home.mkdir()
    # Finalize the Mission in a child interpreter so the module-scoped fixture carries no
    # in-process ``SPEC_KITTY_HOME`` pin (``test_home_pin_scan_limbs`` bans that shape inside an
    # explicit-scope fixture; it is the leak-prone pattern the sibling
    # ``tests/performance/test_owned_checkout_perf.py`` avoids the same way). The home is pinned in
    # the child ``env`` instead, and the counted invocations below still run in-process under the
    # function-scoped ``owned_mission`` home.
    finalized = _finalize_tasks_subprocess(owned_root, cwd=repository_root, home=home)
    assert finalized.returncode == 0, f"fixture finalize-tasks failed: exit={finalized.returncode}\n{finalized.stdout}\n{finalized.stderr}"
    _import_warm_the_application()
    yield _OwnedMission(repository_root=repository_root, owned_root=owned_root, home=home)


def _import_warm_the_application() -> None:
    """Build the application object once while the real ``subprocess.Popen`` is in place.

    ``_build_app`` imports the whole command tree, and ``review/pre_review_gate.py`` subscripts
    ``subprocess.Popen[str]`` at import time. A counted invocation installs a plain-function
    ``Popen`` replacement, under which that subscript raises ``TypeError``; warming the import here
    (fixture work, never counted) caches the command tree so the counted invocations below never
    import it under the replaced ``Popen``. The in-process fixture ``finalize-tasks`` did this
    implicitly before it moved to a child interpreter.
    """
    from specify_cli import app as _app

    assert _app is not None


def _finalize_tasks_subprocess(owned_root: Path, *, cwd: Path, home: Path) -> subprocess.CompletedProcess[str]:
    """Finalize the fixture Mission through the real entry point in a fresh interpreter (never counted)."""
    env = {
        **os.environ,
        "PYTHONPATH": str(REPO_ROOT / "src"),
        "SPEC_KITTY_HOME": str(home),
        "SPEC_KITTY_ENABLE_SAAS_SYNC": "0",
        "PWHEADLESS": "1",
    }
    env.pop("SPECIFY_REPO_ROOT", None)
    return subprocess.run(
        [sys.executable, "-m", "specify_cli", "agent", "mission", "finalize-tasks", *_owned_flags(owned_root), "--json"],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=120,
        env=env,
        check=False,
    )


@pytest.fixture
def owned_mission(built_mission: _OwnedMission, drain_off: None, monkeypatch: pytest.MonkeyPatch) -> _OwnedMission:
    """The module's finalized Mission under an isolated home, hosted drain off, working directory P."""
    monkeypatch.setenv("SPEC_KITTY_HOME", str(built_mission.home))
    monkeypatch.delenv("SPECIFY_REPO_ROOT", raising=False)
    monkeypatch.setenv("SPEC_KITTY_ENABLE_SAAS_SYNC", "0")
    monkeypatch.chdir(built_mission.owned_root)
    return built_mission


def _owned_flags(owned_root: Path) -> list[str]:
    return ["--owned-checkout", str(owned_root), "--mission", _SLUG]


def _invoke(args: list[str]) -> Any:
    """Run *args* through the application object the real entry point uses."""
    from specify_cli import app

    return CliRunner().invoke(app, args)


def _install_git_call_counter(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Record every ``git`` child process started from now on (an argv prefix per call)."""
    calls: list[str] = []
    real_popen = subprocess.Popen

    def _counting_popen(args: Any, *popen_args: Any, **popen_kwargs: Any) -> Any:
        argv = list(args) if isinstance(args, (list, tuple)) else [args]
        if argv and os.path.basename(str(argv[0])) in _GIT_BASENAMES:
            calls.append(" ".join(str(part) for part in argv[:_GIT_ARGV_PREFIX_LENGTH]))
        return real_popen(args, *popen_args, **popen_kwargs)

    monkeypatch.setattr(subprocess, "Popen", _counting_popen)
    return calls


def _drop_process_caches() -> None:
    """Drop the process-global caches so the measured invocation pays every git probe from scratch."""
    from kernel import git_topology
    from specify_cli.workspace.context import clear_workspace_resolution_caches

    clear_workspace_resolution_caches()
    git_topology.clear_caches()


def _count_git_calls(monkeypatch: pytest.MonkeyPatch, args: list[str]) -> list[str]:
    """The git calls one cold invocation of *args* spawns; the invocation must exit 0."""
    _drop_process_caches()
    calls = _install_git_call_counter(monkeypatch)
    result = _invoke(args)
    assert result.exit_code == 0, f"{args}\n{result.output}"
    return calls


# Exact git-subprocess counts per command (see the module docstring for the samples).
_PINNED_GIT_CALLS: dict[str, int] = {
    "tasks-status": 7,
    "setup-plan": 14,
    "context-resolve": 7,
}

_COMMANDS: dict[str, Callable[[Path], list[str]]] = {
    "tasks-status": lambda owned: ["agent", "tasks", "status", *_owned_flags(owned), "--json"],
    "setup-plan": lambda owned: ["agent", "mission", "setup-plan", *_owned_flags(owned), "--json"],
    "context-resolve": lambda owned: [
        "agent",
        "context",
        "resolve",
        *_owned_flags(owned),
        "--json",
        "--action",
        "implement",
        "--wp-id",
        "WP01",
    ],
}


def _assert_git_calls_pinned(command: str, calls: list[str]) -> None:
    """Fail with the recorded calls when *calls* differs from the pinned count (exact, never a bound)."""
    pinned = _PINNED_GIT_CALLS[command]
    listing = "\n".join(f"  {index + 1:>2}. {call}" for index, call in enumerate(calls))
    assert len(calls) == pinned, (
        f"{command}: {len(calls)} git subprocesses, pinned {pinned}. A new call on the command path "
        f"is a regression to fix; a removed one is a deliberate edit of _PINNED_GIT_CALLS.\n{listing}"
    )


def test_every_command_has_a_pin_and_the_pins_cover_nothing_else() -> None:
    assert set(_COMMANDS) == set(_PINNED_GIT_CALLS)


@pytest.mark.parametrize("command", sorted(_COMMANDS))
def test_owned_command_spawns_exactly_the_pinned_number_of_git_processes(command: str, owned_mission: _OwnedMission, monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _count_git_calls(monkeypatch, _COMMANDS[command](owned_mission.owned_root))
    _assert_git_calls_pinned(command, calls)


@pytest.mark.parametrize("command", sorted(_COMMANDS))
def test_one_planted_extra_git_call_turns_the_pin_red(command: str, owned_mission: _OwnedMission, monkeypatch: pytest.MonkeyPatch) -> None:
    """Non-vacuity control: the validation every owned command runs once spawns one more git process."""
    from specify_cli.core import owned_mission as owned_mission_module

    real_resolve = owned_mission_module.resolve_owned_mission
    planted_runs: list[str] = []

    def _resolve_then_spawn_git(*args: Any, **kwargs: Any) -> Any:
        planted_runs.append("ran")
        subprocess.run(["git", "--version"], check=True, capture_output=True)
        return real_resolve(*args, **kwargs)

    monkeypatch.setattr(owned_mission_module, "resolve_owned_mission", _resolve_then_spawn_git)

    calls = _count_git_calls(monkeypatch, _COMMANDS[command](owned_mission.owned_root))

    assert planted_runs, f"{command}: the planted wrapper was never reached, so this control proves nothing"
    assert len(calls) == _PINNED_GIT_CALLS[command] + 1
    assert calls.count("git --version") == 1
    with pytest.raises(AssertionError, match=r"pinned .*\n\s+1\. "):
        _assert_git_calls_pinned(command, calls)
