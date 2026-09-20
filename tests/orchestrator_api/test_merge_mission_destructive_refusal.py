"""Regression: ``merge_mission`` must envelope ``DestructiveOpRefused``, not
leak it as a raw traceback (#4753 finding B).

Pre-fix, ``merge_mission`` wrapped ``_execute_lane_merge`` in
``except RuntimeError`` only. ``_apply_lane_merge_cleanup`` ->
``guarded_worktree_remove`` raises ``DestructiveOpRefused``, a plain
``Exception`` subclass (C-002: deliberately NOT a ``RuntimeError``, so it is
never conflated with ``SafeCommitHeadMismatch``) -- so a dirty lane/coord
worktree at merge time escaped ``merge_mission`` as an unhandled exception:
empty/broken stdout and a raw traceback, breaking this module's JSON-first
machine contract (every command emits exactly one structured envelope).

This test drives the real ``merge_mission`` entry point with
``_execute_lane_merge`` mocked to raise the exact exception the real
preflight raises, and asserts the command still emits exactly one valid
JSON failure envelope with a non-zero exit -- never a traceback.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
import typer

from specify_cli.git.destructive_guard import DestructiveOpRefused
from specify_cli.orchestrator_api.commands import _MergePreflightResult, merge_mission

pytestmark = pytest.mark.git_repo


def _refusal() -> DestructiveOpRefused:
    return DestructiveOpRefused(
        error_code="MERGE_UNSAFE_WORKTREE_DIRTY",
        worktree_path=Path("/tmp/example-lane-worktree"),
        dirty_entries=["?? scratch.txt (untracked local file would be discarded by worktree removal)"],
        remediation="Commit, stash, or revert the local changes in /tmp/example-lane-worktree, then resume the operation (e.g. `spec-kitty merge --resume`).",
    )


def test_merge_mission_envelopes_destructive_op_refused(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    mission_dir = tmp_path / "kitty-specs" / "some-mission"
    mission_dir.mkdir(parents=True)

    with (
        patch("specify_cli.orchestrator_api.commands._get_main_repo_root", return_value=tmp_path),
        patch("specify_cli.orchestrator_api.commands._resolve_mission_dir_or_fail", return_value=mission_dir),
        patch(
            "specify_cli.orchestrator_api.commands._build_merge_preflight",
            return_value=_MergePreflightResult(target_branch="main", errors=[]),
        ),
        patch("specify_cli.orchestrator_api.commands._execute_lane_merge", side_effect=_refusal()),
        patch(
            "specify_cli.orchestrator_api.commands._mission_identity_payload",
            return_value={
                "mission_slug": "some-mission",
                "mission_number": None,
                "mission_type": "software-dev",
            },
        ),
        pytest.raises(typer.Exit) as excinfo,
    ):
        merge_mission(mission="some-mission", target=None, strategy="merge", push=False)

    assert excinfo.value.exit_code == 1

    out_lines = [line for line in capsys.readouterr().out.splitlines() if line.strip()]
    assert len(out_lines) == 1, f"expected exactly one JSON envelope line, got: {out_lines!r}"
    envelope = json.loads(out_lines[0])

    assert envelope["success"] is False
    # #4753 finding B: the real refusal reason survives (either as the top-
    # level code, if it were ever contract-registered, or preserved verbatim
    # as diagnostic data) -- the caller can always recover WHY the merge was
    # refused, never just "it crashed".
    assert envelope["error_code"]
    payload = json.dumps(envelope)
    assert "MERGE_UNSAFE_WORKTREE_DIRTY" in payload
    assert "scratch.txt" in payload


def test_merge_mission_destructive_refusal_is_not_a_runtime_error_leak(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Control: confirms ``DestructiveOpRefused`` is not itself a
    ``RuntimeError`` -- the exact reason the pre-fix ``except RuntimeError``
    clause never caught it. If this assertion ever fails, the dedicated
    ``except DestructiveOpRefused`` clause in ``merge_mission`` would become
    unreachable dead code and this whole regression pin would silently stop
    testing what it claims to."""
    assert not isinstance(_refusal(), RuntimeError)
