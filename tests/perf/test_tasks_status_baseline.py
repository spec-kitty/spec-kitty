"""NFR-005 perf regression harness: ``spec-kitty agent tasks status`` p95 latency.

Mission ``charter-sole-door-bypass-closure-01KZ3WAA`` WP02 migrates the two
direct ``AgentProfileRepository()`` construction sites in
``tasks_status_cmd.py`` (the dashboard status-icon renderer at lines 712/823)
onto the charter-mediated factory. Those two sites carried a "boundary
ratchet" comment naming construction cost as the reason they bypassed the
factory; R3 (``research.md``) confirms the ratchet concern itself is a red
herring against the existing import-scanning gate (both old and new
construction are function-local), but leaves construction *cost* as the real,
previously-unmeasured risk. This file is the falsifiable measurement NFR-005
requires.

**Verdict**: a controlled, back-to-back A/B (old vs. new ``tasks_status_cmd.py``,
same process/session, no other work interleaved) puts the migrated code
within ~2% of the pre-migration baseline on both p95 and mean — well inside
the 10% NFR-005 budget. An earlier, less-controlled before/after attempt
(measurements taken ~20 minutes apart, with unrelated work and concurrent
sibling-lane test runs in between) showed an apparent ~70% regression that
did NOT reproduce under a clean A/B; that was OS-disk-cache coldness plus
system-wide CPU contention from other agents' concurrent test runs, not the
code change. Both the confounded attempt and the clean, controlling series
are recorded raw (not just derived p95 constants) in
``kitty-specs/charter-sole-door-bypass-closure-01KZ3WAA/traces/
tooling-friction.md`` so a reviewer can recompute independently and see why
the first signal was discarded rather than hidden.

Run locally::

    UV_PYTHON=3.13.9 uv run --no-sync pytest tests/perf/test_tasks_status_baseline.py -q

Outside the default CI pytest selectors (like ``test_loader_perf.py``'s NFR
tests) — this is a developer-runnable regression guard, not a CI gate.
"""

from __future__ import annotations

import json
import os
import statistics
import textwrap
import time
from pathlib import Path
from types import SimpleNamespace

import pytest
from click.testing import Result
from typer.testing import CliRunner

from specify_cli.cli.commands.agent.tasks import app
from specify_cli.status.models import Lane, StatusEvent
from tests._support.status_seed import seed_status_events
from tests.mocked_env import setup_mocked_env

pytestmark = [pytest.mark.slow, pytest.mark.timing]

runner = CliRunner()

_WP_COUNT = 120

# Real profile ids (shipped built-ins) so the dashboard's HiC-marker lookup
# (tasks_status_cmd.py:712/823's construction feeds ``_get_hic_marker``) does
# real, non-trivial profile-repository work on every rendered row, not just a
# guaranteed-empty lookup.
_PROFILE_CYCLE = ("python-pedro", "human-in-charge", "debugger-debbie", "")

# Cycled across the fixture's WPs so every rendered lane (board + review
# queues + active + planned) is non-empty -- the render path this NFR guards
# calls all four ``_st_render_*`` helpers, each threading the same
# ``profile_repo``/``agent_profiles`` lookup through every visible row.
_LANE_CYCLE = (
    Lane.PLANNED,
    Lane.CLAIMED,
    Lane.IN_PROGRESS,
    Lane.FOR_REVIEW,
    Lane.IN_REVIEW,
    Lane.APPROVED,
    Lane.DONE,
)


def _build_large_mission(tmp_path: Path, mission_slug: str, wp_count: int) -> Path:
    """Build a synthetic mission with ``wp_count`` WPs across every lane.

    Mirrors ``test_tasks_status_progress.py::_create_project`` (the existing,
    proven ``CliRunner`` + ``setup_mocked_env`` status-command fixture shape),
    scaled up and diversified: each WP gets a distinct lane (cycled) and
    ``agent_profile`` (cycled, including the ``human-in-charge`` sentinel) so
    the render path exercises the profile-repository lookup on a realistic,
    non-degenerate row set instead of a fixture that trivially skips it.
    """
    (tmp_path / ".kittify").mkdir(exist_ok=True)
    feature_dir = tmp_path / "kitty-specs" / mission_slug
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True)
    (feature_dir / "meta.json").write_text(
        json.dumps(
            {
                "mission_slug": mission_slug,
                "mission_number": "999",
                "mission_type": "software-dev",
            }
        ),
        encoding="utf-8",
    )

    events: list[StatusEvent] = []
    for i in range(wp_count):
        wp_id = f"WP{i + 1:03d}"
        lane = _LANE_CYCLE[i % len(_LANE_CYCLE)]
        profile = _PROFILE_CYCLE[i % len(_PROFILE_CYCLE)]
        task_file = tasks_dir / f"{wp_id}-perf-fixture.md"
        task_file.write_text(
            textwrap.dedent(
                f"""\
                ---
                work_package_id: {wp_id}
                title: Perf fixture work package {i + 1}
                phase: Phase 1
                execution_mode: code_change
                agent_profile: {profile or '""'}
                dependencies: []
                ---
                # {wp_id}
                """
            ),
            encoding="utf-8",
        )
        events.append(
            StatusEvent(
                event_id=f"perf-{wp_id}-{lane.value}",
                mission_slug=mission_slug,
                wp_id=wp_id,
                from_lane=Lane.PLANNED,
                to_lane=lane,
                at="2026-01-01T00:00:00+00:00",
                actor="perf-fixture",
                force=True,
                execution_mode="worktree",
            )
        )

    seed_status_events(feature_dir, events)
    return feature_dir


def _invoke_status(tmp_path: Path, mission_slug: str) -> Result:
    workspace = SimpleNamespace(execution_mode="code_change", resolution_kind="lane_workspace")
    with setup_mocked_env(tmp_path, workspace_resolution=workspace):
        return runner.invoke(app, ["status", "--mission", mission_slug])


@pytest.fixture
def _large_mission_project(tmp_path: Path) -> tuple[Path, str]:
    mission_slug = "perf-fixture-mission"
    _build_large_mission(tmp_path, mission_slug, _WP_COUNT)
    return tmp_path, mission_slug


def test_tasks_status_p95_within_nfr005_budget(
    _large_mission_project: tuple[Path, str],
) -> None:
    """NFR-005: p95 latency for ``status`` on a 100+-WP fixture stays bounded.

    Absolute-ceiling regression guard (not a before/after comparison — that
    one-time comparison is recorded in the mission tracer file, since a
    committed single p95 constant alone would be author-written and
    unfalsifiable per the post-tasks squad's finding). The ceiling here is
    calibrated with headroom above the raw post-migration series recorded in
    ``tooling-friction.md`` so this test catches a REGRESSION beyond that
    measured reality, not a tautological restatement of it.
    """
    tmp_path, mission_slug = _large_mission_project

    # Warm-up: absorb one-time import + doctrine-catalog cold-start costs so
    # the sample reflects steady-state repeated-invocation latency.
    warmup = _invoke_status(tmp_path, mission_slug)
    assert warmup.exit_code == 0, warmup.output

    times: list[float] = []
    for _ in range(10):
        t0 = time.perf_counter()
        result = _invoke_status(tmp_path, mission_slug)
        times.append(time.perf_counter() - t0)
        assert result.exit_code == 0, result.output

    times.sort()
    p95 = times[int(0.95 * len(times))] if len(times) > 1 else times[0]

    # Local budget: 3s per invocation at p95 for a 120-WP fixture (CLI-runner
    # in-process invocation, not a subprocess spawn). CI gets 2x slack for
    # runner noise/variance, matching test_loader_perf.py's convention.
    threshold = 3.0 if os.environ.get("CI") != "true" else 6.0
    assert p95 < threshold, (
        f"p95={p95 * 1000:.1f}ms exceeds {threshold * 1000:.0f}ms "
        f"(samples ms: {[round(t * 1000, 1) for t in times]})"
    )


def test_capture_raw_timing_series(
    _large_mission_project: tuple[Path, str],
) -> None:
    """Developer utility: print a fresh raw timing series for manual recording.

    Not a pass/fail regression gate (unlike the test above) -- this exists so
    a reviewer can independently reproduce the raw series this WP's tracer
    file cites, on their own machine, without hand-rolling the fixture. Run
    with ``-s`` to see the printed series.
    """
    tmp_path, mission_slug = _large_mission_project
    warmup = _invoke_status(tmp_path, mission_slug)
    assert warmup.exit_code == 0, warmup.output

    times: list[float] = []
    for _ in range(10):
        t0 = time.perf_counter()
        result = _invoke_status(tmp_path, mission_slug)
        times.append(time.perf_counter() - t0)
        assert result.exit_code == 0, result.output

    p95 = sorted(times)[int(0.95 * len(times))]
    print(f"\nraw series (s): {[round(t, 4) for t in times]}")
    print(f"p95 (s): {p95:.4f}")
    print(f"mean (s): {statistics.mean(times):.4f}")
