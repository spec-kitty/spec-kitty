"""The lane test invocation with the project's declared test command (mission lane-code-verification, #7547).

One adapter between the single ``review.test_command`` authority (read through
:func:`specify_cli.review.baseline._get_test_command` from the repository root
checkout, C-002) and the lane invocation builder and probe of
:mod:`specify_cli.lanes.lane_invocation`. The implement banner, ``implement --json``,
the implement and review prompts and the pre-review gate hook all obtain the
invocation here, and the banner and prompts share :func:`render_lane_test_invocation_lines`
so they state it in the same words. The invocation is never persisted: every
surface re-derives and re-probes it.
"""

from __future__ import annotations

import os
import shlex
from pathlib import Path, PurePath
from typing import Final

from specify_cli.lanes.lane_invocation import (
    LaneTestInvocation,
    ProbeResult,
    ProbeStatus,
    build_lane_test_invocation,
    origin_inside,
    probe_lane_imports,
)
from specify_cli.ownership.models import WorkProductKind
from specify_cli.review.baseline import _get_test_command

__all__ = [
    "lane_test_invocation_for",
    "render_lane_test_invocation_failure_lines",
    "render_lane_test_invocation_lines",
    "workspace_lane_test_invocation",
]

LANE_TEST_INVOCATION_HEADER: Final[str] = "🧪 LANE TEST INVOCATION (run tests exactly like this):"

_INDENT: Final[str] = "   "
_NO_COMMAND: Final[str] = "(no review.test_command configured)"
_LANE_WORKSPACE: Final[str] = "lane_workspace"
# Worded for any workspace: a lane worktree or a write checkout (single_branch, owned checkout).
_FOREIGN_ADVICE: Final[str] = "outside this workspace. Fix its environment before trusting any test result."


def lane_test_invocation_for(
    root: Path,
    *,
    config_root: Path,
    mission_slug: str | None,
    lane_id: str | None,
    probe: bool = True,
) -> LaneTestInvocation:
    """The invocation a lane's (or write checkout's) tests run under, probed unless *probe* is false.

    Args:
        root: The lane or write checkout; the invocation's working directory.
        config_root: The repository root checkout, the config authority for
            ``review.test_command`` (never the lane).
        mission_slug: With *lane_id*, adds the lane test database name.
        lane_id: The lane identity for the test database; ``None`` for a write checkout.
        probe: Attach :func:`probe_lane_imports`' result (never raises).
    """
    template, _output_format = _get_test_command(config_root)
    command = template if isinstance(template, str) and template.strip() else None
    invocation = build_lane_test_invocation(root, command=command, mission_slug=mission_slug, lane_id=lane_id)
    return invocation.with_probe(probe_lane_imports(invocation)) if probe else invocation


def workspace_lane_test_invocation(
    root: Path,
    *,
    config_root: Path,
    mission_slug: str,
    lane_id: str | None,
    resolution_kind: str | None,
    execution_mode: str | None,
) -> LaneTestInvocation | None:
    """The probed invocation for a resolved workspace, or ``None`` for planning-artifact work.

    Code work in a lane worktree carries the lane's test database; code work in a
    write checkout (``single_branch``, owned checkout) is rooted there without one.
    """
    if execution_mode == WorkProductKind.PLANNING_ARTIFACT.value:
        return None
    identity_lane = lane_id if resolution_kind == _LANE_WORKSPACE else None
    return lane_test_invocation_for(root, config_root=config_root, mission_slug=mission_slug, lane_id=identity_lane)


def _shown(origin: str, cwd: Path) -> str:
    """*origin* relative to *cwd* (posix form) when inside it, else verbatim."""
    if not origin_inside(origin, cwd):
        return origin
    relative = os.path.relpath(os.path.realpath(origin), os.path.realpath(cwd))
    return PurePath(relative).as_posix()


def _probe_line(probe: ProbeResult | None, cwd: Path) -> str:
    if probe is None:
        return "probe: not run"
    if probe.status is ProbeStatus.VERIFIED:
        located = ", ".join(f"{name} → {_shown(origin, cwd)}" for name, origin in probe.origins if origin is not None)
        return f"probe: verified — {located}"
    if probe.status is ProbeStatus.FOREIGN:
        origins = dict(probe.origins)
        detail = ", ".join(f"{name} loads from {origins.get(name)}" for name in probe.foreign)
        return f"probe: FOREIGN — {detail}, {_FOREIGN_ADVICE}"
    return f"probe: unverified — {probe.reason or 'no reason recorded'}"


def render_lane_test_invocation_lines(invocation: LaneTestInvocation) -> list[str]:
    """The plain-text block (no Rich markup) the implement banner and prompts print.

    The first line is :data:`LANE_TEST_INVOCATION_HEADER`; the last is always the probe line.
    """
    lines = [LANE_TEST_INVOCATION_HEADER, f"{_INDENT}cd {shlex.quote(str(invocation.cwd))}"]
    if invocation.env_unset:
        lines.append(f"{_INDENT}unset {' '.join(invocation.env_unset)}")
    lines.extend(f"{_INDENT}export {key}={shlex.quote(value)}" for key, value in sorted(invocation.env_set.items()))
    lines.append(f"{_INDENT}{invocation.command or _NO_COMMAND}")
    lines.append(f"{_INDENT}{_probe_line(invocation.probe, invocation.cwd)}")
    return lines


def render_lane_test_invocation_failure_lines(error: BaseException) -> list[str]:
    """The block printed when the invocation could not be built: a fail-open, unverified probe."""
    return [LANE_TEST_INVOCATION_HEADER, f"{_INDENT}probe: unverified — could not build the lane test invocation: {error}"]
