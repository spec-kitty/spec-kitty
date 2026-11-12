"""The commit router on a settled default Mission (#7551, #7607; FR-002/FR-003/FR-004/FR-012).

After settlement the coordination branch IS the Mission topic branch, so ``use_coord`` is
False for every kind (decision ``01M78GRZDX410TZ1V8H1ZVC1EM`` keeps that ref-inequality rule).
These tests pin, in-process, what the router does then: it commits in the checkout the
placement seam names, takes the #5353 status lock when it commits the coordination status
log, and the ``safe_commit`` HEAD-mismatch remedy names the checkout that holds the ref.
"""

from __future__ import annotations

from contextlib import ExitStack
from pathlib import Path

import pytest

from mission_runtime import MissionArtifactKind
from specify_cli.coordination import commit_router
from specify_cli.git.protection_policy import ProtectionPolicy
from tests.specify_cli.cli.commands.agent.test_finalize_topology_settlement import (
    THREE_LANES,
    DefaultMission,
    git,
    make_default_mission,
    run_finalize,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo, pytest.mark.non_sandbox]


@pytest.fixture(autouse=True)
def _quiet_fanout(monkeypatch: pytest.MonkeyPatch) -> None:
    import specify_cli.status.emit as emit_module

    monkeypatch.setattr(emit_module, "_status_fan_out", lambda *a, **k: None)


def _settled(tmp_path: Path, owned: tuple[str, ...] = THREE_LANES) -> DefaultMission:
    mission = make_default_mission(tmp_path, owned)
    code, payload = run_finalize(mission)
    assert code == 0, payload
    return mission


def _spy_status_lock(monkeypatch: pytest.MonkeyPatch) -> list[Path]:
    taken: list[Path] = []
    real = commit_router._hold_coord_status_dir

    def spy(stack: ExitStack, repo_root: Path, coord_feature_dir: Path) -> None:
        taken.append(coord_feature_dir)
        real(stack, repo_root, coord_feature_dir)

    monkeypatch.setattr(commit_router, "_hold_coord_status_dir", spy)
    return taken


def _touch_status(mission_dir: Path) -> Path:
    status = mission_dir / "status.json"
    status.write_text(status.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    return status


# ---------------------------------------------------------------------------
# T008 / #7607: the status lock is taken on the holder checkout
# ---------------------------------------------------------------------------


def test_settled_coordination_status_commit_takes_status_lock(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    mission = _settled(tmp_path)
    taken = _spy_status_lock(monkeypatch)
    status = _touch_status(mission.coord_mission_dir)

    result = commit_router.commit_for_mission(
        mission.root,
        mission.slug,
        (status,),
        "status: settled",
        ProtectionPolicy.resolve(mission.root),
        kind=MissionArtifactKind.STATUS_STATE,
    )

    assert result.status == "committed", result
    assert git(mission.root, "log", "-1", "--format=%s", mission.topic) == "status: settled"
    assert [path.resolve() for path in taken] == [mission.coord_mission_dir.resolve()]


def test_single_branch_status_commit_at_root_takes_no_status_lock(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    mission = _settled(tmp_path, ("src/one.py", "src/two.py"))
    assert git(mission.root, "branch", "--show-current") == mission.topic
    taken = _spy_status_lock(monkeypatch)
    status = _touch_status(mission.root_mission_dir)

    result = commit_router.commit_for_mission(
        mission.root,
        mission.slug,
        (status,),
        "status: single branch",
        ProtectionPolicy.resolve(mission.root),
        kind=MissionArtifactKind.STATUS_STATE,
    )

    assert result.status == "committed", result
    assert taken == []


# ---------------------------------------------------------------------------
# T009: the SafeCommitHeadMismatch remedy names the checkout holding the ref
# ---------------------------------------------------------------------------


def test_head_mismatch_remedy_names_the_holding_worktree(tmp_path: Path) -> None:
    from mission_runtime import CommitTarget
    from specify_cli.git.commit_helpers import SafeCommitHeadMismatch, safe_commit

    mission = _settled(tmp_path)
    holder = mission.coord_mission_dir.parents[1]
    stray = mission.root_mission_dir / "traces" / "x.md"
    stray.parent.mkdir(parents=True, exist_ok=True)
    stray.write_text("# x\n", encoding="utf-8")

    with pytest.raises(SafeCommitHeadMismatch) as caught:
        safe_commit(
            repo_root=mission.root,
            worktree_root=mission.root,
            target=CommitTarget(ref=mission.topic),
            message="x",
            paths=(stray,),
        )

    message = str(caught.value)
    assert caught.value.error_code == "SAFE_COMMIT_HEAD_MISMATCH"
    assert str(holder.resolve()) in message
    assert f"git -C {mission.root} checkout" not in message
