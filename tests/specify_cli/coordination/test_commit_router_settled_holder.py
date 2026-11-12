"""The commit router on a settled default Mission (#7551, #7607; FR-002/FR-003/FR-004/FR-012).

After settlement the coordination branch IS the Mission topic branch, so ``use_coord`` is
False for every kind (decision ``01M78GRZDX410TZ1V8H1ZVC1EM`` keeps that ref-inequality rule).
These tests pin, in-process, what the router does then: it commits in the checkout the
placement seam names, takes the #5353 status lock when it commits the coordination status
log, and the ``safe_commit`` HEAD-mismatch remedy names the checkout that holds the ref.
"""

from __future__ import annotations

from contextlib import ExitStack
from dataclasses import dataclass
from pathlib import Path
from typing import Any

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


# ---------------------------------------------------------------------------
# Squad fold: a differing copy outside the holder is refused, never dropped
# ---------------------------------------------------------------------------


def test_edited_other_worktree_copy_beside_holder_copy_is_refused(tmp_path: Path) -> None:
    mission = _settled(tmp_path)
    holder_copy = mission.coord_mission_dir / "spec.md"
    holder_text = holder_copy.read_text(encoding="utf-8")
    other = mission.root / ".worktrees" / "other-checkout" / "kitty-specs" / mission.slug / "spec.md"
    other.parent.mkdir(parents=True)
    other.write_text("# edited in another checkout\n", encoding="utf-8")
    topic_tip = git(mission.root, "rev-parse", mission.topic)

    result = commit_router.commit_for_mission(
        mission.root,
        mission.slug,
        (other,),
        "spec: other checkout",
        ProtectionPolicy.resolve(mission.root),
        kind=MissionArtifactKind.SPEC,
    )

    assert result.status == "no_op_wrong_surface", result
    assert [fate.reason for surface in result.surfaces for fate in surface.refused] == ["WRONG_SURFACE"]
    assert result.diagnostic is not None
    assert str(other) in result.diagnostic
    assert str(holder_copy) in result.diagnostic
    assert holder_copy.read_text(encoding="utf-8") == holder_text
    assert git(mission.root, "rev-parse", mission.topic) == topic_tip


# ---------------------------------------------------------------------------
# Focused helper tests (T006/T007/T008/T009)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _FakeLocation:
    surface_root: Path


def _identity_main_root(monkeypatch: pytest.MonkeyPatch) -> None:
    import specify_cli.core.paths as core_paths

    monkeypatch.setattr(core_paths, "get_main_repo_root", lambda root: root)


def _holder_layout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    """A repository root with a holder checkout under ``.worktrees/``; translation is ``holder / rel``."""
    _identity_main_root(monkeypatch)
    root = tmp_path / "repo"
    holder = root / ".worktrees" / "m-coord"
    holder.mkdir(parents=True)

    def translate(repo_root: Path, rel: Path, **_: object) -> Path:
        return holder / rel

    monkeypatch.setattr(commit_router, "_translate_to_owning_surface", translate)
    return root, holder


def _make(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("x\n", encoding="utf-8")
    return path


def test_reanchor_keeps_holder_and_outside_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root, holder = _holder_layout(tmp_path, monkeypatch)
    inside = _make(holder / "kitty-specs" / "m" / "a.md")
    outside = tmp_path / "elsewhere" / "b.md"

    result = commit_router._reanchor_primary_paths(root, holder, (inside, outside), mission_slug="m", write_dirs={})

    assert result == (inside, outside)


def test_reanchor_translates_absent_root_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root, holder = _holder_layout(tmp_path, monkeypatch)
    rel = Path("kitty-specs/m/traces/t.md")

    result = commit_router._reanchor_primary_paths(root, holder, (root / rel,), mission_slug="m", write_dirs={})

    assert result == (holder / rel,)


def test_reanchor_prefers_holder_copy_when_both_exist(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root, holder = _holder_layout(tmp_path, monkeypatch)
    rel = Path("kitty-specs/m/traces/t.md")
    _make(root / rel)
    _make(holder / rel)

    result = commit_router._reanchor_primary_paths(root, holder, (root / rel,), mission_slug="m", write_dirs={})

    assert result == (holder / rel,)


def test_reanchor_refuses_root_only_copy_without_copying(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root, holder = _holder_layout(tmp_path, monkeypatch)
    rel = Path("kitty-specs/m/traces/stray.md")
    _make(root / rel)

    with pytest.raises(commit_router._OwningSurfaceRefused) as caught:
        commit_router._reanchor_primary_paths(root, holder, (root / rel,), mission_slug="m", write_dirs={})

    assert caught.value.reason == "WRONG_SURFACE"
    assert caught.value.path == rel.as_posix()
    assert str(holder / rel) in caught.value.diagnostic
    assert not (holder / rel).exists()


def test_primary_commit_root_returns_callers_root_when_seam_names_main_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _identity_main_root(monkeypatch)
    calls: list[MissionArtifactKind] = []

    def resolve(repo_root: Path, kind: MissionArtifactKind, **_: object) -> _FakeLocation:
        calls.append(kind)
        return _FakeLocation(surface_root=repo_root)

    monkeypatch.setattr(commit_router, "_resolve_owning_write_dir", resolve)
    memo: dict[MissionArtifactKind, Any] = {}

    for _ in range(2):
        checkout = commit_router._primary_commit_root(tmp_path, "m", kind=MissionArtifactKind.SPEC, write_dirs=memo, label=Path("x"))
        assert checkout == (tmp_path, False)
    assert calls == [MissionArtifactKind.SPEC], "one seam lookup per kind per batch"


def test_primary_commit_root_returns_holder_away_from_main_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _identity_main_root(monkeypatch)
    holder = tmp_path / ".worktrees" / "m-coord"
    monkeypatch.setattr(commit_router, "_resolve_owning_write_dir", lambda *a, **k: _FakeLocation(surface_root=holder))

    checkout = commit_router._primary_commit_root(tmp_path, "m", kind=MissionArtifactKind.TRACER_FILE, write_dirs={}, label=Path("x"))

    assert checkout == (holder, True)


def test_primary_commit_paths_without_files_stays_at_root(tmp_path: Path) -> None:
    assert commit_router._primary_commit_paths(tmp_path, "m", (), kind=MissionArtifactKind.SPEC) == (tmp_path, (), False)


@pytest.mark.parametrize(("reason", "status"), [("WRONG_SURFACE", "no_op_wrong_surface"), ("PATH_UNROUTABLE", "error")])
def test_owning_surface_refusal_status(reason: str, status: str) -> None:
    from mission_runtime import CommitTarget

    exc = commit_router._OwningSurfaceRefused(path="kitty-specs/m/x.md", reason=reason, diagnostic="why")

    result = commit_router._owning_surface_refusal(exc, surface_name="primary", placement=CommitTarget(ref="topic"))

    assert result.status == status
    assert result.diagnostic == "why"
    assert [(fate.path, fate.reason) for fate in result.surfaces[0].refused] == [("kitty-specs/m/x.md", reason)]


@pytest.mark.parametrize(("use_coord", "holder_checkout", "locked"), [(False, False, False), (False, True, True), (True, False, True)])
def test_coord_status_locks_engage_for_coord_or_holder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, use_coord: bool, holder_checkout: bool, locked: bool
) -> None:
    taken: list[Path] = []
    monkeypatch.setattr(commit_router, "_hold_coord_status_dir", lambda stack, repo_root, status_dir: taken.append(status_dir))
    status = tmp_path / "kitty-specs" / "m" / "status.json"

    with commit_router._coord_status_locks(tmp_path, tmp_path, (status,), use_coord=use_coord, holder_checkout=holder_checkout):
        pass

    assert taken == ([status.parent] if locked else [])


def test_head_mismatch_message_without_holder_keeps_checkout_remedy() -> None:
    from specify_cli.git.commit_helpers import SafeCommitHeadMismatch

    error = SafeCommitHeadMismatch(destination_ref="topic", observed_head="main", worktree_root=Path("/wt"))

    assert str(error).endswith("Run `git -C /wt checkout topic` first.")


def test_head_mismatch_holder_never_names_the_commit_worktree(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import specify_cli.status.read_surface as read_surface
    from specify_cli.git.commit_helpers import _head_mismatch_holder

    monkeypatch.setattr(read_surface, "non_lane_checkout_holding_branch", lambda repo_root, ref: tmp_path)
    assert _head_mismatch_holder(tmp_path, tmp_path, "topic") is None
    monkeypatch.setattr(read_surface, "non_lane_checkout_holding_branch", lambda repo_root, ref: None)
    assert _head_mismatch_holder(tmp_path, tmp_path / "other", "topic") is None


def test_primary_commit_paths_looks_up_checkout_with_a_primary_kind(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A COORD kind on the PRIMARY arm never asks ``write_dir`` for itself (no seed re-entry)."""
    _identity_main_root(monkeypatch)
    asked: list[MissionArtifactKind] = []

    def resolve(repo_root: Path, kind: MissionArtifactKind, **_: object) -> _FakeLocation:
        asked.append(kind)
        return _FakeLocation(surface_root=repo_root)

    monkeypatch.setattr(commit_router, "_resolve_owning_write_dir", resolve)
    status = tmp_path / "kitty-specs" / "m" / "status.json"

    result = commit_router._primary_commit_paths(tmp_path, "m", (status,), kind=MissionArtifactKind.STATUS_STATE)

    assert result == (tmp_path, (status,), False)
    assert asked == [MissionArtifactKind.SPEC]
