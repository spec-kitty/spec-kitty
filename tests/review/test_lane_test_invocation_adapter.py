"""The lane test invocation adapter (mission lane-code-verification #7547, WP02, FR-001 / FR-005).

``specify_cli.review.lane_test_invocation`` joins the project's declared ``review.test_command`` (the
one command authority, C-002) to the lane invocation builder and probe of
``specify_cli.lanes.lane_invocation``, and renders the plain-text block that the implement banner and the
implement and review prompts share. These tests drive it over real git checkouts.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from specify_cli.lanes.lane_invocation import LaneTestInvocation, ProbeResult, ProbeStatus
from specify_cli.review.lane_test_invocation import (
    LANE_TEST_INVOCATION_HEADER,
    lane_test_invocation_for,
    render_lane_test_invocation_failure_lines,
    render_lane_test_invocation_lines,
    workspace_lane_test_invocation,
)

pytestmark = [pytest.mark.unit, pytest.mark.git_repo]

_COMMAND = 'PYTEST_ADDOPTS="--junitxml={output_file}" make test-fast'
_DB_KEY = "SPEC_KITTY_TEST_DB_NAME"


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True, text=True)


def _checkout(root: Path, *, packages: tuple[str, ...] = ("pkg",)) -> Path:
    """A git checkout with tracked regular packages under ``src/``."""
    root.mkdir(parents=True)
    _git(root, "init", "-q", "-b", "main")
    for name in packages:
        (root / "src" / name).mkdir(parents=True)
        (root / "src" / name / "__init__.py").write_text("V = 1\n", encoding="utf-8")
    (root / "README.md").write_text("seed\n", encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "-c", "user.email=t@example.com", "-c", "user.name=T", "commit", "-q", "-m", "seed")
    return root


def _declare(config_root: Path, command: str) -> None:
    (config_root / ".kittify").mkdir(parents=True, exist_ok=True)
    (config_root / ".kittify" / "config.yaml").write_text(f"review:\n  test_command: '{command}'\n", encoding="utf-8")


def _probe(status: ProbeStatus, *, origins: tuple[tuple[str, str | None], ...] = (), foreign: tuple[str, ...] = (), reason: str | None = None) -> ProbeResult:
    return ProbeResult(status=status, origins=origins, foreign=foreign, reason=reason, interpreter="/usr/bin/python3")


# ---------------------------------------------------------------------------
# lane_test_invocation_for: command authority + probe
# ---------------------------------------------------------------------------


def test_declared_command_is_carried_verbatim_and_the_probe_verifies_the_lane(tmp_path: Path) -> None:
    lane = _checkout(tmp_path / "lane")
    config_root = tmp_path / "root"
    _declare(config_root, _COMMAND)

    invocation = lane_test_invocation_for(lane, config_root=config_root, mission_slug="demo", lane_id="lane-a")

    assert invocation.cwd == lane
    assert invocation.command == _COMMAND
    assert invocation.env_set[_DB_KEY] == "test_demo_lane_a"
    assert invocation.env_set["PYTHONPATH"] == str(lane / "src")
    assert invocation.probe is not None
    assert invocation.probe.status is ProbeStatus.VERIFIED


def test_the_command_comes_from_the_config_root_never_the_lane(tmp_path: Path) -> None:
    lane = _checkout(tmp_path / "lane")
    _declare(lane, "lane-only-command")
    config_root = tmp_path / "root"
    _declare(config_root, _COMMAND)

    invocation = lane_test_invocation_for(lane, config_root=config_root, mission_slug=None, lane_id=None, probe=False)

    assert invocation.command == _COMMAND


def test_unset_test_command_yields_none_and_the_probe_still_runs(tmp_path: Path) -> None:
    lane = _checkout(tmp_path / "lane")

    invocation = lane_test_invocation_for(lane, config_root=tmp_path / "no-config", mission_slug=None, lane_id=None)

    assert invocation.command is None
    assert invocation.probe is not None
    assert invocation.probe.status is ProbeStatus.VERIFIED


def test_a_non_string_test_command_is_treated_as_unset(tmp_path: Path) -> None:
    lane = _checkout(tmp_path / "lane")
    config_root = tmp_path / "root"
    (config_root / ".kittify").mkdir(parents=True)
    (config_root / ".kittify" / "config.yaml").write_text("review:\n  test_command: [make, test]\n", encoding="utf-8")

    invocation = lane_test_invocation_for(lane, config_root=config_root, mission_slug=None, lane_id=None, probe=False)

    assert invocation.command is None


def test_probe_false_attaches_no_probe(tmp_path: Path) -> None:
    lane = _checkout(tmp_path / "lane")

    invocation = lane_test_invocation_for(lane, config_root=tmp_path, mission_slug=None, lane_id=None, probe=False)

    assert invocation.probe is None


# ---------------------------------------------------------------------------
# workspace_lane_test_invocation: which workspaces get one
# ---------------------------------------------------------------------------


def test_planning_artifact_work_gets_no_invocation(tmp_path: Path) -> None:
    root = _checkout(tmp_path / "root")

    invocation = workspace_lane_test_invocation(
        root,
        config_root=root,
        mission_slug="demo",
        lane_id="lane-planning",
        resolution_kind="repo_root",
        execution_mode="planning_artifact",
    )

    assert invocation is None


def test_a_lane_workspace_carries_the_lane_test_database(tmp_path: Path) -> None:
    lane = _checkout(tmp_path / "lane")

    invocation = workspace_lane_test_invocation(
        lane,
        config_root=tmp_path,
        mission_slug="demo",
        lane_id="lane-a",
        resolution_kind="lane_workspace",
        execution_mode="code_change",
    )

    assert invocation is not None
    assert invocation.env_set[_DB_KEY] == "test_demo_lane_a"
    assert invocation.probe is not None


def test_a_write_checkout_gets_an_invocation_without_a_lane_test_database(tmp_path: Path) -> None:
    """``single_branch`` code work runs in the write checkout: rooted there, no per-lane test database."""
    root = _checkout(tmp_path / "root")

    invocation = workspace_lane_test_invocation(
        root,
        config_root=root,
        mission_slug="demo",
        lane_id="lane-planning",
        resolution_kind="repo_root",
        execution_mode="code_change",
    )

    assert invocation is not None
    assert invocation.cwd == root
    assert _DB_KEY not in invocation.env_set
    assert invocation.env_set["PYTHONPATH"] == str(root / "src")


# ---------------------------------------------------------------------------
# render_lane_test_invocation_lines: the shared wording
# ---------------------------------------------------------------------------


def test_render_states_cd_unset_exports_command_and_verified_probe(tmp_path: Path) -> None:
    lane = tmp_path / "lane"
    invocation = LaneTestInvocation(
        cwd=lane,
        command=_COMMAND,
        env_set={"PYTHONPATH": str(lane / "src"), _DB_KEY: "test_demo_lane_a"},
        probe=_probe(ProbeStatus.VERIFIED, origins=(("pkg", str(lane / "src" / "pkg" / "__init__.py")),)),
    )

    lines = render_lane_test_invocation_lines(invocation)

    assert lines == [
        LANE_TEST_INVOCATION_HEADER,
        f"   cd {lane}",
        "   unset PYTHONPATH UV_PROJECT_ENVIRONMENT VIRTUAL_ENV",
        f"   export PYTHONPATH={lane / 'src'}",
        f"   export {_DB_KEY}=test_demo_lane_a",
        f"   {_COMMAND}",
        "   probe: verified — pkg → src/pkg/__init__.py",
    ]


def test_render_without_a_declared_command_says_so(tmp_path: Path) -> None:
    invocation = LaneTestInvocation(cwd=tmp_path, command=None, probe=_probe(ProbeStatus.UNVERIFIED, reason="no tracked source-layout packages to probe"))

    lines = render_lane_test_invocation_lines(invocation)

    assert "   (no review.test_command configured)" in lines
    assert lines[-1] == "   probe: unverified — no tracked source-layout packages to probe"


def test_render_flags_a_foreign_probe_as_untrustworthy(tmp_path: Path) -> None:
    origin = "/elsewhere/src/pkg/__init__.py"
    invocation = LaneTestInvocation(
        cwd=tmp_path,
        command=None,
        probe=_probe(ProbeStatus.FOREIGN, origins=(("pkg", origin),), foreign=("pkg",), reason="pkg loads from elsewhere"),
    )

    lines = render_lane_test_invocation_lines(invocation)

    # Worded for any workspace: a single_branch write checkout is not a lane (review cycle 1, item 3).
    assert lines[-1] == f"   probe: FOREIGN — pkg loads from {origin}, outside this workspace. Fix its environment before trusting any test result."


def test_render_keeps_an_origin_outside_the_lane_absolute(tmp_path: Path) -> None:
    origin = "/elsewhere/src/pkg/__init__.py"
    invocation = LaneTestInvocation(cwd=tmp_path / "lane", command=None, probe=_probe(ProbeStatus.VERIFIED, origins=(("pkg", origin),)))

    assert render_lane_test_invocation_lines(invocation)[-1] == f"   probe: verified — pkg → {origin}"


def test_render_without_a_probe_says_it_was_not_run(tmp_path: Path) -> None:
    invocation = LaneTestInvocation(cwd=tmp_path, command=None)

    assert render_lane_test_invocation_lines(invocation)[-1] == "   probe: not run"


def test_render_quotes_an_export_value_for_the_shell(tmp_path: Path) -> None:
    invocation = LaneTestInvocation(cwd=tmp_path, command=None, env_set={"NAME": "has space"})

    assert "   export NAME='has space'" in render_lane_test_invocation_lines(invocation)


def test_render_puts_the_lane_venv_in_front_of_path(tmp_path: Path) -> None:
    bin_dir = tmp_path / "lane" / ".venv" / "bin"
    with_venv = LaneTestInvocation(cwd=tmp_path / "lane", command=None, path_prepend=(str(bin_dir),))

    assert f'   export PATH={bin_dir}{os.pathsep}"$PATH"' in render_lane_test_invocation_lines(with_venv)
    # Positive control: no lane venv, no PATH line.
    bare = LaneTestInvocation(cwd=tmp_path / "lane", command=None)
    assert not any("export PATH=" in line for line in render_lane_test_invocation_lines(bare))


def test_failure_lines_report_an_unverified_probe_with_the_error() -> None:
    lines = render_lane_test_invocation_failure_lines(RuntimeError("boom"))

    assert lines == [LANE_TEST_INVOCATION_HEADER, "   probe: unverified — could not build the lane test invocation: boom"]
