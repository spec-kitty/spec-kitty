"""Coord-topology create must not commit status byte-sets to the target branch.

Permanent guard for #5440: the defect is fixed (the create scaffold commit no
longer carries ``status.events.jsonl`` for a coordination-routed mission) and this
test keeps it fixed. Forcing the status log back into ``scaffold_paths`` turns it red.

DEFECT (#5440, fixed)
---------------------
``create_mission_core`` (``src/specify_cli/core/mission_creation.py``) builds
ONE scaffold commit over ``meta.json`` + ``status.events.jsonl`` +
``tasks/README.md`` + ``tasks/.gitkeep`` (``_scaffold_mission_dir``'s
``scaffold_paths``) and lands it on the create-time write target, which is the
mission's **target branch**. It does so for every topology, including
``coord``. ``status.events.jsonl`` is ``MissionArtifactKind.STATUS_STATE``, a
member of the COORD partition (``mission_runtime.artifacts._PLACEMENT_ARTIFACT_KINDS``):
under a coordination topology its home is the coordination surface, never the
target branch. A later ``spec-kitty consolidate`` then refuses with
``TARGET_BRANCH_CONTENT_CONFLICT`` on ``kitty-specs/<m>/status.events.jsonl``.

INVARIANT
---------
For a ``coord`` mission, no CLI commit on the target branch carries a
status byte-set (``status.events.jsonl`` / ``status.json``). The first such
commit is the create scaffold commit, so the narrowest reproduction is: create
a coord mission through the real entry point, then read the target branch's
tree in git.

Drives the pre-existing production entry point ``create_mission_core`` over a
real temporary git repository (no commit mocks), hence the ``integration`` +
``git_repo`` marks its siblings use. The target is a non-protected topic
branch, as in the issue's evidence, so the scaffold commit really lands
(``main``/``master`` are protected by default and turn it into a disclosed
bootstrap skip).

"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from mission_runtime import MissionTopology
from specify_cli.core.mission_creation import create_mission_core

from tests._factories import provision_test_charter

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_CORE_MODULE = "specify_cli.core.mission_creation"

# A non-protected topic branch as the mission target (issue evidence: "target =
# a non-primary topic branch").
_TARGET_BRANCH = "feat/coord-target"

# The coord-partition status byte-sets (``STATUS_STATE`` basenames).
_STATUS_BYTE_SETS = ("status.events.jsonl", "status.json")


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=True).stdout


def _init_repo(repo: Path) -> None:
    """A provisioned Spec Kitty project with one commit on a non-protected branch."""
    (repo / ".kittify").mkdir(exist_ok=True)
    provision_test_charter(repo)
    (repo / "kitty-specs").mkdir(exist_ok=True)
    (repo / "kitty-specs" / ".gitkeep").touch()
    _git(repo, "init", "-b", _TARGET_BRANCH)
    _git(repo, "config", "user.email", "test@test.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "init")


def _summary(slug: str) -> dict[str, str]:
    title = slug.replace("-", " ").strip() or "test mission"
    return {
        "friendly_name": title.title(),
        "purpose_tldr": f"Deliver {title} cleanly for the team.",
        "purpose_context": (f"This mission delivers {title} so product and engineering can move forward with a clear outcome and shared understanding."),
    }


@pytest.fixture(autouse=True)
def _not_a_worktree(monkeypatch: pytest.MonkeyPatch) -> None:
    """The test process may itself run inside a lane worktree; pin the
    worktree-context guard to the ``tmp_path`` fixture repository instead of
    the process cwd (same pin as the sibling create tests)."""
    monkeypatch.setattr(f"{_CORE_MODULE}.is_worktree_context", lambda cwd: False)


def test_coord_create_scaffold_commit_keeps_status_off_target_branch(tmp_path: Path) -> None:
    """#5440: creating a ``coord`` mission must not commit ``status.events.jsonl``
    (or ``status.json``) onto the mission's target branch.

    #5440 is fixed; this is the permanent guard against its return.
    """
    _init_repo(tmp_path)
    base = _git(tmp_path, "rev-parse", _TARGET_BRANCH).strip()

    result = create_mission_core(
        tmp_path,
        "coord-status-placement",
        topology=MissionTopology.COORD,
        target_branch=_TARGET_BRANCH,
        **_summary("coord-status-placement"),
    )
    slug = result.mission_slug
    mission_rel = f"kitty-specs/{slug}"

    # Preconditions (non-vacuity): this really is a coord mission whose
    # scaffold commit really landed on the target branch.
    meta = json.loads((result.feature_dir / "meta.json").read_text(encoding="utf-8"))
    assert meta["topology"] == MissionTopology.COORD.value
    assert meta.get("coordination_branch"), "a coord create must mint a coordination branch"
    assert meta["target_branch"] == _TARGET_BRANCH
    target_tip = _git(tmp_path, "rev-parse", _TARGET_BRANCH).strip()
    assert target_tip != base, "the create scaffold commit must land on the target branch"
    target_tree = _git(tmp_path, "ls-tree", "-r", "--name-only", _TARGET_BRANCH).splitlines()
    assert f"{mission_rel}/meta.json" in target_tree, "primary-partition meta.json belongs on the target branch"

    # The invariant: no CLI commit on the target branch carries a coord-owned
    # status byte-set.
    status_paths = [f"{mission_rel}/{name}" for name in _STATUS_BYTE_SETS]
    on_target = [path for path in status_paths if path in target_tree]
    touching_commits = _git(tmp_path, "log", "--format=%h %s", f"{base}..{_TARGET_BRANCH}", "--", *status_paths).splitlines()
    assert not on_target, (
        f"coord mission {slug!r}: target branch {_TARGET_BRANCH!r} carries coord-owned status byte-set(s) "
        f"{on_target}, committed by {touching_commits}. STATUS_STATE is a COORD-partition kind; for a coord "
        "mission it lives on the coordination surface, never on the target branch (#5440)."
    )
