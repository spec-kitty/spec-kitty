"""#5287: the status read door refuses a remote-only branch with a typed error and the remedy.

A ref-sourced status read (``COORD_BRANCH_REF`` or ``MISSION_BRANCH_REF``) whose
branch has no local head raises ``StatusSurfaceRefRemoteOnly``
(``STATUS_SURFACE_REF_REMOTE_ONLY``), a kind of ``StatusSurfaceRefUnreadable``.
The door never reads the remote-tracking ref instead (operator ruling 1), and a
local ref that names a missing object keeps the plain unreadable error.
"""

from __future__ import annotations

import json
import re
import shlex
import subprocess
from pathlib import Path

import pytest

from mission_runtime import MissionTopology
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
    assert f"branch {COORD_BRANCH} refs/remotes/{REMOTE}/{COORD_BRANCH}" in text
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
    assert f"branch {MISSION_BRANCH} refs/remotes/{REMOTE}/{MISSION_BRANCH}" in text
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


def test_an_unproven_topic_branch_gets_a_hedged_hint_that_works_when_a_remote_holds_it(tmp_path: Path) -> None:
    """Review fold (LOW): a single-branch clone has the topic branch on a remote but no tracking ref.

    Nothing local proves a remote holds the branch, so the error stays the plain unreadable one,
    but it carries a hedged hint built by the canonical builder: if the branch still exists on a
    remote, the printed git steps recover it, and the read then succeeds.
    """
    mission = build_matrix_mission(tmp_path, SINGLE_BRANCH)
    _make_default_off_topic_branch(mission)
    _remote_only(mission.repo, tmp_path, MISSION_BRANCH)
    git(mission.repo, "update-ref", "-d", f"refs/remotes/{REMOTE}/{MISSION_BRANCH}")

    surface = resolve_status_read(mission.repo, SLUG)
    with pytest.raises(StatusSurfaceRefUnreadable) as excinfo:
        read_status_events(surface)

    assert not isinstance(excinfo.value, StatusSurfaceRefRemoteOnly)
    assert excinfo.value.error_code == STATUS_SURFACE_REF_UNREADABLE
    text = str(excinfo.value)
    assert "If the branch still exists on a remote: run in order: " in text
    git_steps = [step for step in re.findall(r"`([^`]+)`", text) if step.startswith("git ")]
    assert [shlex.split(step)[3] for step in git_steps] == ["fetch", "branch"], git_steps
    for step in git_steps:
        subprocess.run(shlex.split(step), check=True, capture_output=True)

    assert read_status_events(resolve_status_read(mission.repo, SLUG))


def test_an_unproven_coordination_branch_is_not_called_remote_only(tmp_path: Path) -> None:
    """Squad fold (MEDIUM): the coordination probe can answer "present" on an inconclusive remote.

    With no local head and no remote-tracking ref nothing local proves a remote holds the branch, so
    the read keeps the plain unreadable error with the hedged hint, the same rule as the topic branch.
    """
    mission = build_matrix_mission(tmp_path, LANES_WITH_COORD, UNMATERIALIZED)
    _remote_only(mission.repo, tmp_path, COORD_BRANCH)
    git(mission.repo, "update-ref", "-d", f"refs/remotes/{REMOTE}/{COORD_BRANCH}")

    with pytest.raises(StatusSurfaceRefUnreadable) as excinfo:
        resolve_status_read(mission.repo, SLUG)

    assert not isinstance(excinfo.value, StatusSurfaceRefRemoteOnly)
    text = str(excinfo.value)
    assert "If the branch still exists on a remote: run in order: " in text
    assert f"spec-kitty doctor coordination --mission {SLUG} --fix`. A status history" in text


def test_the_refusal_carries_its_facts(tmp_path: Path) -> None:
    mission = build_matrix_mission(tmp_path, LANES_WITH_COORD, UNMATERIALIZED)
    _remote_only(mission.repo, tmp_path, COORD_BRANCH)

    with pytest.raises(StatusSurfaceRefRemoteOnly) as excinfo:
        resolve_status_read(mission.repo, SLUG)

    refusal = excinfo.value
    assert refusal.branch == COORD_BRANCH
    assert refusal.ref == f"refs/heads/{COORD_BRANCH}"
    assert refusal.remedy.startswith("Run in order: ")
    assert refusal.remedy in str(refusal)
    assert refusal.detail == "no local branch"


def test_a_coordination_surface_read_later_gets_the_doctor_follow_up(tmp_path: Path) -> None:
    """A COORD_BRANCH_REF surface without a prefetched read (e.g. a write-side decision) reads later."""
    from specify_cli.status.read_surface import StatusReadSurface

    mission = build_matrix_mission(tmp_path, LANES_WITH_COORD, UNMATERIALIZED)
    _remote_only(mission.repo, tmp_path, COORD_BRANCH)
    surface = StatusReadSurface(
        topology=MissionTopology.LANES_WITH_COORD,
        source=StatusReadSource.COORD_BRANCH_REF,
        mission_dir_name=SLUG,
        path=None,
        repo_root=mission.repo,
        ref=f"refs/heads/{COORD_BRANCH}",
    )

    with pytest.raises(StatusSurfaceRefRemoteOnly) as excinfo:
        read_status_events(surface)

    assert f"spec-kitty doctor coordination --mission {SLUG} --fix" in str(excinfo.value)


def test_a_failed_read_of_a_non_branch_ref_is_never_remote_only(tmp_path: Path) -> None:
    from specify_cli.status.read_surface import _read_ref_or_refuse

    mission = build_matrix_mission(tmp_path, SINGLE_BRANCH)

    with pytest.raises(StatusSurfaceRefUnreadable) as excinfo:
        _read_ref_or_refuse(mission.repo, "refs/remotes/nowhere/branch", "kitty-specs/x/status.events.jsonl", follow_up="re-run the command")

    assert not isinstance(excinfo.value, StatusSurfaceRefRemoteOnly)
    assert "If the branch still exists" not in str(excinfo.value)


def test_the_topic_branch_checkout_remedy_uses_the_canonical_steps_when_the_branch_is_not_local(tmp_path: Path) -> None:
    """Squad fold (LOW): ``ref_source_remedy`` no longer relies on ``git switch`` DWIM for a remote-only topic branch."""
    from specify_cli.status.read_surface import ref_source_remedy

    mission = build_matrix_mission(tmp_path, SINGLE_BRANCH)
    _make_default_off_topic_branch(mission)
    surface = resolve_status_read(mission.repo, SLUG)
    assert "git switch" in ref_source_remedy(surface, SLUG)

    _remote_only(mission.repo, tmp_path, MISSION_BRANCH)
    remedy = ref_source_remedy(surface, SLUG)

    assert f"branch {MISSION_BRANCH} refs/remotes/{REMOTE}/{MISSION_BRANCH}" in remedy
    assert "git switch" not in remedy
