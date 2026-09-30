"""NFR-003: owned-checkout commands stay inside a 2 s median-of-5 wall-clock budget.

Mission ``owned-checkout-lifecycle-authority-01M3M2ZB``, closing WP18 (T099).

``agent tasks status``, ``agent mission setup-plan`` and ``agent context resolve``
run against a finalized owned checkout ``P`` through the REAL entry point
(``python -m specify_cli``, a fresh interpreter per run, so import cost is part of
the budget and is absorbed by the median of five rather than by an excluded
warm-up). A non-zero exit counts as ``inf`` with the stderr tail in the name.

Wall-clock budgets are environment-sensitive, so this lives in the ``performance``
lane (nightly): the tests are collected but skipped unless
``SPEC_KITTY_RUN_PERFORMANCE=1``. The functional half of NFR-002 (exactly one
ownership validation per command, no extra git subprocess per status read) runs per
PR in ``tests/integration/test_owned_lifecycle_acceptance_e2e.py``;
``tests/architectural/test_performance_marker_guard.py`` polices that no functional
assertion hides in this file.
"""

from __future__ import annotations

import os
import statistics
import subprocess
import sys
import time
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest

from tests._perf_helpers import assert_timing_budget

REPO_ROOT = Path(__file__).resolve().parents[2]

_RUNS = 5
_BUDGET_SECONDS = 2.0
_SLUG = "owned-perf-01M2D903"
_MISSION_ID = "01M2D903000000000000000001"
_TARGET = "codex/owned-perf"


@dataclass(frozen=True)
class _OwnedMission:
    repository_root: Path
    owned_root: Path
    home: Path


def _cli(args: list[str], *, cwd: Path, home: Path) -> subprocess.CompletedProcess[str]:
    env = {
        **os.environ,
        "PYTHONPATH": str(REPO_ROOT / "src"),
        "SPEC_KITTY_HOME": str(home),
        "SPEC_KITTY_ENABLE_SAAS_SYNC": "0",
        "PWHEADLESS": "1",
    }
    env.pop("SPECIFY_REPO_ROOT", None)
    return subprocess.run([sys.executable, "-m", "specify_cli", *args], cwd=cwd, capture_output=True, text=True, timeout=60, env=env, check=False)


def _median_wall_clock(args: list[str], *, cwd: Path, home: Path) -> tuple[float, str]:
    """Median-of-``_RUNS`` seconds for one command; ``inf`` (with the stderr tail) on any non-zero exit."""
    durations: list[float] = []
    for _ in range(_RUNS):
        started = time.monotonic()
        completed = _cli(args, cwd=cwd, home=home)
        durations.append(time.monotonic() - started)
        if completed.returncode != 0:
            return float("inf"), f"exit={completed.returncode}; stderr={completed.stderr[-1500:]}"
    return statistics.median(durations), ""


@pytest.fixture(scope="module")
def owned_mission(tmp_path_factory: pytest.TempPathFactory) -> Iterator[_OwnedMission]:
    """R + P + a finalized one-WP owned mission (built once, module-scoped)."""
    from tests._factories import provision_test_charter
    from tests.integration.conftest import _git, _init_repo, _write_mission, _write_single_lane_manifest

    root = tmp_path_factory.mktemp("owned-perf")
    home = root / "home"
    home.mkdir()
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
        _git(checkout, "commit", "-qm", "owned perf mission")
    finalized = _cli(["agent", "mission", "finalize-tasks", "--owned-checkout", str(owned_root), "--mission", _SLUG, "--json"], cwd=repository_root, home=home)
    if finalized.returncode != 0:
        pytest.fail(f"fixture finalize-tasks failed: exit={finalized.returncode}\n{finalized.stdout}\n{finalized.stderr}")
    yield _OwnedMission(repository_root=repository_root, owned_root=owned_root, home=home)


def _owned_args(mission: _OwnedMission, *command: str) -> list[str]:
    return ["agent", *command, "--owned-checkout", str(mission.owned_root), "--mission", _SLUG, "--json"]


@pytest.mark.performance
def test_owned_tasks_status_median_stays_inside_its_budget(owned_mission: _OwnedMission) -> None:
    measured, detail = _median_wall_clock(_owned_args(owned_mission, "tasks", "status"), cwd=owned_mission.owned_root, home=owned_mission.home)
    assert_timing_budget(measured, _BUDGET_SECONDS, name=f"agent tasks status owned median-of-{_RUNS}; {detail}")


@pytest.mark.performance
def test_owned_setup_plan_median_stays_inside_its_budget(owned_mission: _OwnedMission) -> None:
    measured, detail = _median_wall_clock(_owned_args(owned_mission, "mission", "setup-plan"), cwd=owned_mission.owned_root, home=owned_mission.home)
    assert_timing_budget(measured, _BUDGET_SECONDS, name=f"agent mission setup-plan owned median-of-{_RUNS}; {detail}")


@pytest.mark.performance
def test_owned_context_resolve_median_stays_inside_its_budget(owned_mission: _OwnedMission) -> None:
    args = [*_owned_args(owned_mission, "context", "resolve"), "--action", "implement", "--wp-id", "WP01"]
    measured, detail = _median_wall_clock(args, cwd=owned_mission.owned_root, home=owned_mission.home)
    assert_timing_budget(measured, _BUDGET_SECONDS, name=f"agent context resolve owned median-of-{_RUNS}; {detail}")
