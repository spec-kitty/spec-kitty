"""NFR-003: owned-checkout commands stay inside a runner-relative start-up ratio.

Mission ``owned-checkout-lifecycle-authority-01M3M2ZB``, closing WP18 (T099);
re-measured by mission ``nightly-suites-green-01M44FEP`` (#5419, #5614).

``agent tasks status``, ``agent mission setup-plan`` and ``agent context resolve``
run against a finalized owned checkout ``P`` through the REAL entry point
(``python -m specify_cli``, a fresh interpreter per run, so import cost is part of
the measure). Each test samples the command and a **start-up floor** (a bare
``python -m specify_cli`` start-up command, see ``tests/_perf_helpers.py``)
*interleaved in the same run*, five spawns of each, and asserts the **ratio of the
two medians** against ``OWNED_CHECKOUT_RATIO_LIMIT``. A non-zero exit of either
counts as ``inf`` with the stderr tail in the name.

The measure is relative because the shared nightly runner is not a constant: the
same bare ``--help`` moved between 1.14 s and 1.95 s across nightly runs with no
product change, which turned an absolute 2.5 s budget red on four of six runs
(#5419). The ratio of an owned command to a floor taken in the same run stayed
between 1.35 and 1.51 over the same runs. The limit, the sample counts and the
figures behind them live in ``tests/_perf_helpers.py`` and
``docs/adr/4.x/2026-10-05-2-runner-relative-performance-budgets.md``.

``test_planted_cpu_work_turns_the_ratio_assertion_red`` is the control: a
CPU-bound loop written into a ``sitecustomize.py`` on the child's ``PYTHONPATH``
(test side only, no product hook) slows exactly one ``agent`` command by about
half the floor, and the same assertion against the same limit must fail.

Wall-clock measures are environment-sensitive, so this lives in the ``performance``
lane (nightly): the tests are collected but skipped unless
``SPEC_KITTY_RUN_PERFORMANCE=1``. The functional half of NFR-002 (exactly one
ownership validation per command, no extra git subprocess per status read) runs per
PR in ``tests/integration/test_owned_lifecycle_acceptance_e2e.py``;
``tests/architectural/test_performance_marker_guard.py`` polices that no functional
assertion hides in this file.
"""

from __future__ import annotations

import os
import subprocess
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest

from tests._perf_helpers import (
    OWNED_CHECKOUT_RATIO_LIMIT,
    OWNED_PLANT_ITERATIONS,
    OWNED_PLANT_MAX_FRACTION_OF_FLOOR,
    OWNED_PLANT_MIN_FRACTION_OF_FLOOR,
    STARTUP_FLOOR_ARGV,
    Measurement,
    Sample,
    assert_timing_budget,
    cli_argv,
    expect_budget_exceeded,
    measure_group,
    measure_interleaved,
    with_plant,
    write_cpu_plant,
)

REPO_ROOT = Path(__file__).resolve().parents[2]

_SLUG = "owned-perf-01M2D903"
_MISSION_ID = "01M2D903000000000000000001"
_TARGET = "codex/owned-perf"


@dataclass(frozen=True)
class _OwnedMission:
    repository_root: Path
    owned_root: Path
    home: Path


def _cli(args: list[str], *, cwd: Path, home: Path, plant: Path | None = None) -> subprocess.CompletedProcess[str]:
    env = {
        **os.environ,
        "PYTHONPATH": str(REPO_ROOT / "src"),
        "SPEC_KITTY_HOME": str(home),
        "SPEC_KITTY_ENABLE_SAAS_SYNC": "0",
        "PWHEADLESS": "1",
    }
    env.pop("SPECIFY_REPO_ROOT", None)
    if plant is not None:
        env = with_plant(env, plant)
    return subprocess.run(cli_argv(*args), cwd=cwd, capture_output=True, text=True, timeout=60, env=env, check=False)


def _timed(args: list[str], *, cwd: Path, home: Path, plant: Path | None = None) -> Callable[[], Sample]:
    """A sample source: one timed fresh-interpreter run of the CLI; a non-zero exit fails the sample."""

    def spawn() -> Sample:
        started = time.monotonic()
        completed = _cli(args, cwd=cwd, home=home, plant=plant)
        seconds = time.monotonic() - started
        if completed.returncode == 0:
            return Sample(seconds)
        return Sample(seconds, ok=False, detail=f"exit={completed.returncode}; stderr={completed.stderr[-1500:]}")

    return spawn


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


def _floor(mission: _OwnedMission) -> Callable[[], Sample]:
    return _timed(list(STARTUP_FLOOR_ARGV), cwd=mission.owned_root, home=mission.home)


def _assert_ratio(measurement: Measurement, label: str, title: str, record_property: Callable[[str, object], None] | None = None) -> None:
    if record_property is not None:
        # Recorded in the xunit report on PASS too, so a nightly run can be read for calibration.
        record_property("ratio", round(measurement.ratio(label), 4))
        record_property("floor_median_seconds", round(measurement.floor.median, 4))
        record_property("command_median_seconds", round(measurement.variants[label].median, 4))
    name = measurement.describe(label, OWNED_CHECKOUT_RATIO_LIMIT, title=title)
    assert_timing_budget(measurement.ratio(label), OWNED_CHECKOUT_RATIO_LIMIT, name=name)


@pytest.mark.performance
def test_owned_tasks_status_median_stays_inside_its_budget(owned_mission: _OwnedMission, record_property: Callable[[str, object], None]) -> None:
    command = _timed(_owned_args(owned_mission, "tasks", "status"), cwd=owned_mission.owned_root, home=owned_mission.home)
    _assert_ratio(measure_interleaved(command, _floor(owned_mission)), "command", "agent tasks status owned", record_property)


@pytest.mark.performance
def test_owned_setup_plan_median_stays_inside_its_budget(owned_mission: _OwnedMission, record_property: Callable[[str, object], None]) -> None:
    command = _timed(_owned_args(owned_mission, "mission", "setup-plan"), cwd=owned_mission.owned_root, home=owned_mission.home)
    _assert_ratio(measure_interleaved(command, _floor(owned_mission)), "command", "agent mission setup-plan owned", record_property)


@pytest.mark.performance
def test_owned_context_resolve_median_stays_inside_its_budget(owned_mission: _OwnedMission, record_property: Callable[[str, object], None]) -> None:
    args = [*_owned_args(owned_mission, "context", "resolve"), "--action", "implement", "--wp-id", "WP01"]
    command = _timed(args, cwd=owned_mission.owned_root, home=owned_mission.home)
    _assert_ratio(measure_interleaved(command, _floor(owned_mission)), "command", "agent context resolve owned", record_property)


@pytest.mark.performance
def test_planted_cpu_work_turns_the_ratio_assertion_red(owned_mission: _OwnedMission, tmp_path: Path, record_property: Callable[[str, object], None]) -> None:
    """FR-009 / NFR-002: CPU-bound work planted in one ``agent`` command, test side only, must fail the ratio.

    The plant is a fixed-iteration loop in a ``sitecustomize.py`` first on the
    child's ``PYTHONPATH``; it runs only when ``agent`` is on the command line, so
    the start-up floor is untouched. The loop is CPU-bound, so its cost scales with
    the runner. Its realised cost (planted median minus clean median, interleaved
    with the floor in the same run) must lie between ``OWNED_PLANT_MIN_FRACTION_OF_FLOOR``
    and ``OWNED_PLANT_MAX_FRACTION_OF_FLOOR`` of the floor median: an oversized plant would
    fail under any limit. The same limit constant as the clean tests then has to
    reject the planted ratio, so widening the limit turns this test red. The
    figures are recorded in the xunit report (``planted_ratio``, ``clean_ratio``,
    ``plant_cost_fraction`` and the medians) before any assertion, and the
    did-not-detect failure message carries them too.
    """
    plant = write_cpu_plant(tmp_path / "plant", OWNED_PLANT_ITERATIONS, argv_token="agent")
    args = _owned_args(owned_mission, "tasks", "status")
    measurement = measure_group(
        _floor(owned_mission),
        {
            "clean": _timed(args, cwd=owned_mission.owned_root, home=owned_mission.home),
            "planted": _timed(args, cwd=owned_mission.owned_root, home=owned_mission.home, plant=plant),
        },
    )
    floor_seconds = measurement.floor.median
    cost_seconds = measurement.cost("planted", "clean")
    record_property("planted_ratio", round(measurement.ratio("planted"), 4))
    record_property("clean_ratio", round(measurement.ratio("clean"), 4))
    record_property("plant_cost_fraction", round(cost_seconds / floor_seconds, 4))
    record_property("floor_median_seconds", round(floor_seconds, 4))
    record_property("clean_median_seconds", round(measurement.variants["clean"].median, 4))
    record_property("planted_median_seconds", round(measurement.variants["planted"].median, 4))
    where = measurement.describe("planted", OWNED_CHECKOUT_RATIO_LIMIT, title="agent tasks status owned, planted")
    figures = f"clean ratio {measurement.ratio('clean'):.3f}; plant cost {cost_seconds / floor_seconds:.3f} of the floor; {where}"
    upper, lower = OWNED_PLANT_MAX_FRACTION_OF_FLOOR, OWNED_PLANT_MIN_FRACTION_OF_FLOOR
    assert_timing_budget(cost_seconds, upper * floor_seconds, name=f"plant cost above {upper} of the floor; {figures}")
    assert_timing_budget(lower * floor_seconds, cost_seconds, name=f"plant cost below {lower} of the floor; {figures}")
    expect_budget_exceeded(measurement.ratio("planted"), OWNED_CHECKOUT_RATIO_LIMIT, name=figures)
