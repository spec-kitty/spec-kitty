"""#5287: the status read door refuses a remote-only branch with a typed error and the remedy.

A ref-sourced status read (``COORD_BRANCH_REF`` or ``MISSION_BRANCH_REF``) whose
branch has no local head raises ``StatusSurfaceRefRemoteOnly``
(``STATUS_SURFACE_REF_REMOTE_ONLY``), a kind of ``StatusSurfaceRefUnreadable``.
The door never reads the remote-tracking ref instead (operator ruling 1), and a
local ref that names a missing object keeps the plain unreadable error.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import specify_cli.coordination.status_service as status_service
from specify_cli.coordination.status_service import (
    STATUS_SURFACE_REF_REMOTE_ONLY,
    STATUS_SURFACE_REF_UNREADABLE,
    StatusSurfaceRefRemoteOnly,
    StatusSurfaceRefUnreadable,
)
from specify_cli.status.read_surface import StatusReadSource, read_status_events, resolve_status_read
from tests.status.test_status_read_matrix import (
    COORD_BRANCH,
    LANES_WITH_COORD,
    MISSION_BRANCH,
    SINGLE_BRANCH,
    SLUG,
    UNMATERIALIZED,
    MatrixMission,
    build_matrix_mission,
    git,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

REMOTE = "coord-remote"


def _remote_only(repo: Path, base: Path, branch: str) -> None:
    """Push *branch* to a bare remote and delete the local head; the tracking ref stays."""
    bare = base / f"{REMOTE}.git"
    git(base, "init", "-q", "--bare", str(bare))
    git(repo, "remote", "add", REMOTE, str(bare))
    git(repo, "push", "-q", REMOTE, branch)
    git(repo, "fetch", "-q", REMOTE, branch)
    git(repo, "branch", "-D", branch)


def _make_default_off_topic_branch(mission: MatrixMission) -> None:
    """A default-topology Mission whose topic branch no checkout holds (MISSION_BRANCH_REF)."""
    meta_path = mission.root_mission_dir / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta.update({"topology_source": "default", "topology_settled": False, "create_return_branch": "main"})
    meta_path.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    git(mission.repo, "checkout", "-q", "-b", MISSION_BRANCH)
    git(mission.repo, "add", "-A")
    git(mission.repo, "commit", "-q", "-m", "default create")
    git(mission.repo, "checkout", "-q", "-b", "elsewhere")


def test_remote_only_coordination_branch_is_a_typed_refusal_with_the_remedy(tmp_path: Path) -> None:
    mission = build_matrix_mission(tmp_path, LANES_WITH_COORD, UNMATERIALIZED)
    _remote_only(mission.repo, tmp_path, COORD_BRANCH)

    with pytest.raises(StatusSurfaceRefRemoteOnly) as excinfo:
        resolve_status_read(mission.repo, SLUG)

    refusal = excinfo.value
    assert isinstance(refusal, StatusSurfaceRefUnreadable)
    assert refusal.error_code == STATUS_SURFACE_REF_REMOTE_ONLY
    text = str(refusal)
    assert f"branch {COORD_BRANCH} {REMOTE}/{COORD_BRANCH}" in text
    assert f"spec-kitty doctor coordination --mission {SLUG} --fix" in text
    assert text.endswith(f"Error code: {STATUS_SURFACE_REF_REMOTE_ONLY}.")


def test_remote_only_mission_topic_branch_is_a_typed_refusal(tmp_path: Path) -> None:
    mission = build_matrix_mission(tmp_path, SINGLE_BRANCH)
    _make_default_off_topic_branch(mission)
    _remote_only(mission.repo, tmp_path, MISSION_BRANCH)

    surface = resolve_status_read(mission.repo, SLUG)
    assert surface.source is StatusReadSource.MISSION_BRANCH_REF

    with pytest.raises(StatusSurfaceRefRemoteOnly) as excinfo:
        read_status_events(surface)

    text = str(excinfo.value)
    assert f"branch {MISSION_BRANCH} {REMOTE}/{MISSION_BRANCH}" in text
    assert "then re-run the command" in text
    assert "doctor coordination" not in text


def test_a_local_ref_naming_a_missing_object_stays_unreadable(tmp_path: Path) -> None:
    """Negative control: corruption is not remote-only, even with a tracking ref on a remote."""
    mission = build_matrix_mission(tmp_path, LANES_WITH_COORD, UNMATERIALIZED)
    _remote_only(mission.repo, tmp_path, COORD_BRANCH)
    # A local head again, but pointing at an object the repository lacks.
    head = mission.repo / ".git" / "refs" / "heads" / COORD_BRANCH
    head.parent.mkdir(parents=True, exist_ok=True)
    head.write_text("1" * 40 + "\n", encoding="utf-8")

    with pytest.raises(StatusSurfaceRefUnreadable) as excinfo:
        resolve_status_read(mission.repo, SLUG)

    assert not isinstance(excinfo.value, StatusSurfaceRefRemoteOnly)
    assert excinfo.value.error_code == STATUS_SURFACE_REF_UNREADABLE


def test_a_readable_ref_never_pays_for_the_remote_only_probe(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """NFR-001: the classification runs only after a failed read."""
    mission = build_matrix_mission(tmp_path, LANES_WITH_COORD, UNMATERIALIZED)
    calls: list[str] = []
    real = status_service.ref_names_object

    def counting(repo_root: Path, ref: str) -> bool:
        calls.append(ref)
        return real(repo_root, ref)

    monkeypatch.setattr(status_service, "ref_names_object", counting)

    surface = resolve_status_read(mission.repo, SLUG)
    read_status_events(surface)

    assert surface.source is StatusReadSource.COORD_BRANCH_REF
    assert calls == []


def test_a_mission_topic_branch_gone_everywhere_is_not_called_remote_only(tmp_path: Path) -> None:
    """Review fold: nothing proves a remote holds a topic branch with no local head and no tracking ref.

    The coordination arm is different: the coordination probe has already found the branch
    (locally, in a remote-tracking ref or on a remote) before the door reads it. The topic-branch
    arm has no such probe, so without a remote-tracking ref it keeps the plain unreadable error
    instead of printing a fetch that cannot succeed.
    """
    mission = build_matrix_mission(tmp_path, SINGLE_BRANCH)
    _make_default_off_topic_branch(mission)
    git(mission.repo, "branch", "-D", MISSION_BRANCH)

    surface = resolve_status_read(mission.repo, SLUG)
    assert surface.source is StatusReadSource.MISSION_BRANCH_REF

    with pytest.raises(StatusSurfaceRefUnreadable) as excinfo:
        read_status_events(surface)

    assert not isinstance(excinfo.value, StatusSurfaceRefRemoteOnly)
    assert excinfo.value.error_code == STATUS_SURFACE_REF_UNREADABLE
    assert "exists only on a remote" not in str(excinfo.value)
