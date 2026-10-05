"""A mission broken by a pre-fix upgrade consolidates through the real CLI (#5457, WP04).

Story 4 (AS-1/AS-2/AS-3) and Story 2 drive ``spec-kitty consolidate`` (the
pre-existing entry point) over the WP01 broken-state fixture: every lane branch
and the target carry their own divergent ``.kittify/metadata.yaml`` and the
identical ``.gitattributes`` line. The Story 5 controls run the same fixture
shapes with a genuine conflict and pin that it is still refused.

Each red assertion names the defect's exact text (``Merge of ... failed`` for
the lane, the stale refusal, or ``TARGET_BRANCH_CONTENT_CONFLICT`` naming
``.kittify/metadata.yaml``) before it checks the exit code.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pytest

from tests.integration.target_owned_fixtures import (
    DECISION_INDEX_GITATTRIBUTES_LINE,
    GITATTRIBUTES_PATH,
    LanesProject,
    build_older_version_lanes_project,
    commit_broken_upgrade_state,
    commit_file_on_branch,
    gitattributes_blob,
    metadata_blob,
    output_names_merge_failed,
    output_names_stale_metadata_refusal,
    output_names_target_content_conflict,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo, pytest.mark.slow]

_SHARED_SOURCE = "src/shared.py"

#: The stale refusal the CLI rendered for the Story 5 AS-1 control on the WP04
#: base (whitespace-normalised: the console wraps at its width).
_GITATTRIBUTES_STALE_REFUSAL = (
    "✗ lane-b: Lane lane-b is stale: overlapping files ['.gitattributes']. "
    "Lane lane-b must incorporate mission changes before merging. "
    "Run: cd .worktrees/*-lane-b && git merge kitty/mission-target-owned-01M5457A"
)


def _output(result: subprocess.CompletedProcess[str]) -> str:
    return (result.stdout or "") + (result.stderr or "")


def _normalised(text: str) -> str:
    return " ".join(text.split())


def _show(repo: Path, ref: str, path: str) -> str | None:
    result = subprocess.run(["git", "-C", str(repo), "show", f"{ref}:{path}"], capture_output=True, text=True, check=False)
    return result.stdout if result.returncode == 0 else None


def _broken_project(tmp_path: Path, *, lanes: int, status_json_divergence: bool = False) -> LanesProject:
    project = build_older_version_lanes_project(tmp_path, topology="lanes", lanes=lanes, status_json_divergence=status_json_divergence)
    commit_broken_upgrade_state(project)
    return project


def _diverge_target_status_json(project: LanesProject) -> None:
    """Make the target's ``status.json`` differ too, so the squash sees a mixed conflict set."""
    commit_file_on_branch(
        project.repo,
        project.target_branch,
        f"kitty-specs/{project.slug}/status.json",
        json.dumps({"side": "target"}, sort_keys=True) + "\n",
        "chore: status snapshot (target side)",
    )


def _add_source_conflict(project: LanesProject) -> None:
    """Story 5 AS-2: the lane and the target both add ``src/shared.py`` differently."""
    commit_file_on_branch(project.repo, project.target_branch, _SHARED_SOURCE, "target = 1\n", "feat: target shared")
    commit_file_on_branch(project.repo, project.lane_branches["lane-a"], _SHARED_SOURCE, "lane = 1\n", "feat: lane shared")


def _consolidate(project: LanesProject, *extra: str) -> subprocess.CompletedProcess[str]:
    return project.run("consolidate", "--mission", project.slug, *extra)


def _assert_landed(project: LanesProject, result: subprocess.CompletedProcess[str], target_metadata: str | None) -> None:
    output = _output(result)
    assert result.returncode == 0, output
    for lane_id in project.lane_ids:
        lane_file = f"src/{lane_id.replace('-', '_')}/m.py"
        assert _show(project.repo, project.target_branch, lane_file) is not None, lane_file
    assert metadata_blob(project.repo, project.target_branch) == target_metadata
    attributes = gitattributes_blob(project.repo, project.target_branch)
    assert attributes is not None
    assert attributes.count(DECISION_INDEX_GITATTRIBUTES_LINE) == 1


# ---------------------------------------------------------------------------
# Story 4: the broken state recovers
# ---------------------------------------------------------------------------


def test_as1_two_lanes_with_worktrees_consolidate(tmp_path: Path) -> None:
    """AS-1 (FR-012): the lane -> mission merge keeps the mission side's metadata."""
    project = _broken_project(tmp_path, lanes=2)
    target_metadata = metadata_blob(project.repo, project.target_branch)

    result = _consolidate(project)

    output = _output(result)
    assert not output_names_merge_failed(output), output
    assert not output_names_stale_metadata_refusal(output), output
    _assert_landed(project, result, target_metadata)


def test_as2_two_lanes_without_worktrees_consolidate(tmp_path: Path) -> None:
    """AS-2 (FR-005/006/012): no auto-rebase can heal, so the stale rules and the
    lane -> mission merge are exercised directly."""
    project = _broken_project(tmp_path, lanes=2)
    project.remove_lane_worktrees()
    target_metadata = metadata_blob(project.repo, project.target_branch)

    result = _consolidate(project)

    output = _output(result)
    assert not output_names_stale_metadata_refusal(output), output
    assert "is stale" not in output, output
    assert not output_names_merge_failed(output), output
    _assert_landed(project, result, target_metadata)


def test_as3_squash_into_work_with_mixed_status_conflict(tmp_path: Path) -> None:
    """AS-3 / Story 2 (FR-007): the squash keeps the target's metadata even when a
    derived ``status.json`` conflicts in the same squash."""
    project = _broken_project(tmp_path, lanes=1, status_json_divergence=True)
    _diverge_target_status_json(project)
    target_metadata = metadata_blob(project.repo, project.target_branch)

    result = _consolidate(project)

    output = _output(result)
    assert not output_names_target_content_conflict(output), output
    assert "TARGET_BRANCH_CONTENT_CONFLICT" not in output, output
    _assert_landed(project, result, target_metadata)


def test_as3_dry_run_no_longer_forecasts_the_metadata_conflict(tmp_path: Path) -> None:
    """The dry-run preview shares ``_run_squash_merge``; a mission branch carrying
    its own divergent metadata (and a mixed ``status.json`` divergence) is not
    forecast as blocked."""
    project = build_older_version_lanes_project(tmp_path, topology="lanes", lanes=1, status_json_divergence=True)
    broken = [*project.branches(), project.mission_branch]
    commit_broken_upgrade_state(project, branches=broken)
    _diverge_target_status_json(project)

    result = _consolidate(project, "--dry-run", "--json")

    output = _output(result)
    assert not output_names_target_content_conflict(output), output
    assert result.returncode == 0, output
    payload = json.loads(result.stdout)
    assert not payload.get("blocked", False), payload


# ---------------------------------------------------------------------------
# Story 5: genuine conflicts are still refused, byte-identically
# ---------------------------------------------------------------------------


def test_source_conflict_in_a_broken_mission_is_refused_naming_only_the_source_path(tmp_path: Path) -> None:
    """Story 5 AS-2: a genuine source conflict in the AS-3 fixture is still refused,
    names only the source path, and leaves the target untouched."""
    project = _broken_project(tmp_path, lanes=1, status_json_divergence=True)
    _add_source_conflict(project)
    target_tip = _show(project.repo, project.target_branch, _SHARED_SOURCE)

    result = _consolidate(project)

    output = _output(result)
    assert result.returncode != 0, output
    assert "TARGET_BRANCH_CONTENT_CONFLICT" in output, output
    assert re.findall(r"conflicting_path:\s*(\S+)", output) == [_SHARED_SOURCE], output
    assert _show(project.repo, project.target_branch, _SHARED_SOURCE) == target_tip


def test_story5_as1_different_gitattributes_still_stale(tmp_path: Path) -> None:
    """Two lanes that change ``.gitattributes`` differently are still refused as stale."""
    project = _broken_project(tmp_path, lanes=2)
    for index, branch in enumerate(project.lane_branches.values()):
        commit_file_on_branch(
            project.repo,
            branch,
            GITATTRIBUTES_PATH,
            DECISION_INDEX_GITATTRIBUTES_LINE + f"*.lane{index} text\n",
            "chore: lane attributes",
        )
    project.remove_lane_worktrees()

    result = _consolidate(project)

    output = _output(result)
    assert result.returncode != 0, output
    assert _GITATTRIBUTES_STALE_REFUSAL in _normalised(output), output
