"""Regression guard for the fixed #2709 defect (target-newer squash provenance).

Formerly a red-first ``@pytest.mark.regression`` reproduction per ADR
2026-07-17-1
(docs/adr/3.x/2026-07-17-1-red-main-is-honest-ci-is-release-authority.md);
un-marked (landing fold: make ``@pytest.mark.regression`` mean exactly one
thing) once the fix landed and this test started passing. #2709 is fixed —
this is now a permanent guard, not a red-first pin.

Defect (fixed)
--------------
``spec-kitty merge`` folds the mission branch into the target with a squash merge
implemented in ``specify_cli.lanes.consolidation._merge_branch_into`` as::

    git merge --squash -X theirs <mission_branch>

``-X theirs`` resolves every conflicting hunk in favour of the mission branch
(the *source*). When the target branch carries a *newer* ``meta.json`` — because
the mission was accepted on the target, minting acceptance provenance
(``accept_commit``, ``accepted_at``, ``acceptance_history``, ``vcs``,
``vcs_locked_at``) and bumping canonical fields (``mission_number``, ``status``) —
those target-newer values used to be silently overwritten by, or dropped in
favour of, the older mission-branch copies. Acceptance provenance now survives
a squash merge; target-newer canonical state is reconciled, not replaced
wholesale.

This test drives the pre-existing, supported squash-merge entry point
``integrate_mission_into_target(..., strategy=MergeStrategy.SQUASH)`` against a
real git repository where the target is strictly newer than the mission branch,
and asserts the acceptance provenance + canonical fields survive.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from specify_cli.lanes.consolidation import integrate_mission_into_target
from specify_cli.lanes.models import LanesManifest
from specify_cli.consolidation.config import MergeStrategy

pytestmark = [pytest.mark.integration, pytest.mark.git_repo, pytest.mark.non_sandbox]

MISSION_SLUG = "099-target-newer-acceptance"
META_REL = f"kitty-specs/{MISSION_SLUG}/meta.json"
MISSION_BRANCH = "kitty/mission-target-newer-acceptance-01ABCDEF-lane-a"
TARGET_BRANCH = "main"


def _run(cmd: list[str], cwd: Path) -> None:
    subprocess.run(cmd, cwd=str(cwd), check=True, capture_output=True, text=True)


def _write_meta(repo: Path, payload: dict[str, object]) -> None:
    meta_path = repo / META_REL
    meta_path.parent.mkdir(parents=True, exist_ok=True)
    # Match the product's serialization: pretty-printed, sorted keys.
    meta_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def _base_meta() -> dict[str, object]:
    return {
        "accepted_at": None,
        "created_at": "2026-07-01T10:00:00+00:00",
        "friendly_name": "Target Newer Acceptance",
        "mission_id": "01KQ47E81PWNXS80MHWTD903G1",
        "mission_number": None,
        "status": "planned",
    }


def _accepted_target_meta() -> dict[str, object]:
    """Target-newer meta.json: the mission was accepted ON the target branch."""
    meta = _base_meta()
    meta.update(
        {
            "accept_commit": "abc123def4567890abc123def4567890abc123de",
            "accepted_at": "2026-07-15T12:00:00+00:00",
            "acceptance_history": [
                {"at": "2026-07-15T12:00:00+00:00", "mode": "manual"}
            ],
            "mission_number": 42,
            "status": "accepted",
            "vcs": "git",
            "vcs_locked_at": "2026-07-15T12:00:00+00:00",
        }
    )
    return meta


def _older_mission_meta() -> dict[str, object]:
    """Older mission-branch meta.json: still mid-flight, no acceptance provenance."""
    meta = _base_meta()
    meta.update({"friendly_name": "Mission Work In Progress", "status": "in_review"})
    return meta


def _read_target_meta(repo: Path) -> dict[str, object]:
    """Read meta.json as committed on the target branch after the merge."""
    blob = subprocess.run(
        ["git", "show", f"{TARGET_BRANCH}:{META_REL}"],
        cwd=str(repo),
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    loaded: dict[str, object] = json.loads(blob)
    return loaded


def _manifest() -> LanesManifest:
    return LanesManifest(
        version=1,
        mission_slug=MISSION_SLUG,
        mission_id="01KQ47E81PWNXS80MHWTD903G1",
        mission_branch=MISSION_BRANCH,
        target_branch=TARGET_BRANCH,
        lanes=[],
        computed_at="2026-07-16T00:00:00+00:00",
        computed_from="deadbeef",
    )


def test_squash_merge_preserves_target_newer_acceptance_provenance(
    tmp_path: Path,
) -> None:
    """Squash-merging an older mission branch into a target-newer branch must not
    drop acceptance provenance or overwrite canonical fields (#2709)."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _run(["git", "init", "-b", TARGET_BRANCH], repo)
    _run(["git", "config", "user.email", "test@example.com"], repo)
    _run(["git", "config", "user.name", "Spec Kitty"], repo)
    _run(["git", "config", "commit.gpgsign", "false"], repo)

    # Base commit shared by both branches.
    _write_meta(repo, _base_meta())
    _run(["git", "add", "-A"], repo)
    _run(["git", "commit", "-m", "base mission meta"], repo)

    # Mission branch: older mid-flight work, no acceptance provenance.
    _run(["git", "branch", MISSION_BRANCH], repo)
    _run(["git", "checkout", MISSION_BRANCH], repo)
    _write_meta(repo, _older_mission_meta())
    _run(["git", "commit", "-am", "mission work (older, no provenance)"], repo)

    # Target branch (main): mission accepted here — target is strictly newer.
    _run(["git", "checkout", TARGET_BRANCH], repo)
    _write_meta(repo, _accepted_target_meta())
    _run(["git", "commit", "-am", "accept on target (newer canonical state)"], repo)

    # Drive the real, supported squash-merge entry point.
    result = integrate_mission_into_target(
        repo,
        MISSION_SLUG,
        _manifest(),
        strategy=MergeStrategy.SQUASH,
    )
    assert result.success, f"merge failed: {result.errors}"

    merged = _read_target_meta(repo)

    # Acceptance provenance must survive the squash merge.
    assert merged.get("accept_commit") == "abc123def4567890abc123def4567890abc123de", (
        "accept_commit was dropped/overwritten by the mission-branch copy"
    )
    assert merged.get("accepted_at") == "2026-07-15T12:00:00+00:00", (
        "accepted_at was dropped/overwritten by the mission-branch copy"
    )
    assert merged.get("acceptance_history") == [
        {"at": "2026-07-15T12:00:00+00:00", "mode": "manual"}
    ], "acceptance_history was dropped/overwritten by the mission-branch copy"
    assert merged.get("vcs") == "git", (
        "vcs provenance was dropped by the -X theirs squash merge"
    )
    assert merged.get("vcs_locked_at") == "2026-07-15T12:00:00+00:00", (
        "vcs_locked_at provenance was dropped by the -X theirs squash merge"
    )

    # Target-newer canonical fields must be reconciled, not replaced wholesale.
    assert merged.get("mission_number") == 42, (
        "target-newer mission_number was overwritten by the older mission-branch "
        "value via -X theirs"
    )
    assert merged.get("status") == "accepted", (
        "target-newer status was overwritten by the older mission-branch value "
        "via -X theirs"
    )
