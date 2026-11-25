"""The squash forecast's lane scan does not re-judge commits the squashed tree already judged (#7854, #7855).

Under the default squash strategy the ``--dry-run`` forecast judges the Mission branch through
the squash blob attribution over the staged squash tree, then scans each lane branch commit by
commit, because the preview does not fold the lanes in (#7268). A lane that merged the Mission
branch reaches the Mission branch's own commits, so that scan judged them a second time, commit
by commit, although the squash gate the real run runs never does:

* #7854 (doc-kitty #342): a merge of ``main`` into the Mission branch, which resolved a path, was
  reported as "content commit ... (patch-id ) ... belongs to NO approved WP";
* #7855 (doc-kitty #369/#370): early planning-artifact docs commits on the Mission branch, whose
  content a later commit brought back to the approved content the target already holds, were
  reported the same way.

The contract pinned here: a commit the Mission branch reaches is judged by the squash blob
attribution only (its content is in the squashed tree); a commit only a lane reaches is still
scanned; content the squashed tree carries that no approved WP authored still FAILs.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest

from specify_cli.consolidation.reconciliation import (
    ApprovedWpCommitSet,
    MergeOutcomeVerifier,
    VerifyStatus,
)

pytestmark = [pytest.mark.git_repo]

_MISSION = "kitty/mission-m"
_LANE = "kitty/mission-m-lane-b"
_TARGET = "feat/target"


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=True).stdout.strip()


def _commit(repo: Path, path: str, content: str, message: str) -> str:
    target = repo / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    _git(repo, "add", path)
    _git(repo, "commit", "-qm", message)
    return _git(repo, "rev-parse", "HEAD")


def _blob(repo: Path, ref: str, path: str) -> str:
    return _git(repo, "rev-parse", f"{ref}:{path}")


def _squashed_tree(repo: Path, target: str, mission: str) -> str:
    """The tree a clean squash of *mission* onto *target* stages (what the forecast preview writes)."""
    # ``merge-tree`` exits 1 on a conflict and still prints the tree (with conflict markers) first.
    out = subprocess.run(["git", "merge-tree", "--write-tree", target, mission], cwd=repo, capture_output=True, text=True, check=False).stdout
    return out.splitlines()[0]


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    _git(tmp_path, "init", "-q", "-b", "main")
    _git(tmp_path, "config", "user.email", "t@example.com")
    _git(tmp_path, "config", "user.name", "t")
    _git(tmp_path, "config", "commit.gpgsign", "false")
    _commit(tmp_path, "docs/hub.md", "hub v1\n", "base")
    return tmp_path


def _claim(base: str, **overrides: Any) -> ApprovedWpCommitSet:
    fields: dict[str, Any] = {
        "approved": {"WP01": ("a" * 40,)},
        "manifest_wp_ids": frozenset({"WP01"}),
        "surface_resolved": True,
        "enforce_closed_world": True,
        "excluded_window_base": base,
        "mission_slug": "m",
    }
    fields.update(overrides)
    return ApprovedWpCommitSet(**fields)


# --- #7854: a merge of main into the Mission branch ----------------------------------------------


def _merge_from_main_mission(repo: Path, *, resolution: str) -> tuple[str, str, str, str]:
    """Mission branch cut from ``main``; ``main`` moves; ``main`` is merged into the Mission branch.

    Both sides edit ``docs/hub.md``, so the merge resolves that path by hand with *resolution*.
    The target branch is cut from the new ``main`` (it already holds main's content). lane-b
    merges the Mission branch (so it reaches the merge) and adds its own approved work.
    Returns ``(window_base, merge_sha, lane_own_sha, lane_own_blob)``.
    """
    _git(repo, "checkout", "-q", "-b", _MISSION)
    _commit(repo, "docs/hub.md", "hub v1 mission\n", "mission: planning edit of the hub page")
    _git(repo, "checkout", "-q", "main")
    _commit(repo, "docs/hub.md", "hub v2 from main\n", "main: #426 landed")
    _git(repo, "checkout", "-q", "-b", _TARGET)
    window_base = _git(repo, "rev-parse", "HEAD")
    _git(repo, "checkout", "-q", _MISSION)
    subprocess.run(["git", "merge", "--no-edit", "main"], cwd=repo, check=False, capture_output=True)
    (repo / "docs/hub.md").write_text(resolution, encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "Merge main (#426 landed) into the mission branch")
    merge_sha = _git(repo, "rev-parse", "HEAD")
    _git(repo, "checkout", "-q", "-b", _LANE)
    lane_own = _commit(repo, "src/paged.py", "PAGED = True\n", "WP01: paged hub listing")
    return window_base, merge_sha, lane_own, _blob(repo, lane_own, "src/paged.py")


def test_7854_merge_from_main_reached_by_a_lane_is_not_rejudged(repo: Path) -> None:
    window_base, _merge, lane_own, lane_blob = _merge_from_main_mission(repo, resolution="hub v2 from main\n")
    claim = _claim(window_base, authored_shas=frozenset({lane_own}), authored_blobs=frozenset({("src/paged.py", lane_blob)}))
    tree = _squashed_tree(repo, _TARGET, _MISSION)
    result = MergeOutcomeVerifier(repo).forecast_content_verdict((_MISSION, _LANE, _TARGET), claim, squashed_tree=tree)

    assert result.status is VerifyStatus.PASS, result.recovery_guidance()


def test_7854_merge_resolution_with_new_bytes_still_fails_on_the_squashed_tree(repo: Path) -> None:
    """Negative control: a resolution writing bytes neither parent held ships unreviewed content."""
    window_base, _merge, lane_own, lane_blob = _merge_from_main_mission(repo, resolution="hub v2 from main\nUNREVIEWED\n")
    claim = _claim(window_base, authored_shas=frozenset({lane_own}), authored_blobs=frozenset({("src/paged.py", lane_blob)}))
    tree = _squashed_tree(repo, _TARGET, _MISSION)

    result = MergeOutcomeVerifier(repo).forecast_content_verdict((_MISSION, _LANE, _TARGET), claim, squashed_tree=tree)

    assert result.status is VerifyStatus.FAIL
    assert result.divergence is not None
    assert [path for path, _ in result.divergence.unattributable_blobs] == ["docs/hub.md"]


def test_a_commit_only_a_lane_reaches_is_still_scanned(repo: Path) -> None:
    """Negative control: lane content the squash preview never saw stays judged commit by commit."""
    window_base, _merge, lane_own, lane_blob = _merge_from_main_mission(repo, resolution="hub v2 from main\n")
    smuggled = _commit(repo, "src/smuggled.py", "X = 1\n", "smuggled onto the lane")
    claim = _claim(window_base, authored_shas=frozenset({lane_own}), authored_blobs=frozenset({("src/paged.py", lane_blob)}))
    tree = _squashed_tree(repo, _TARGET, _MISSION)

    result = MergeOutcomeVerifier(repo).forecast_content_verdict((_MISSION, _LANE, _TARGET), claim, squashed_tree=tree)

    assert result.status is VerifyStatus.FAIL
    assert result.divergence is not None
    assert [sha for sha, _ in result.divergence.unattributable_content] == [smuggled]


def test_without_a_squashed_tree_the_mission_branch_is_still_scanned_per_commit(repo: Path) -> None:
    """The merge / rebase forecast still scans the Mission branch: no squash tree judged it."""
    window_base, merge_sha, lane_own, lane_blob = _merge_from_main_mission(repo, resolution="hub v2 from main\nUNREVIEWED\n")
    claim = _claim(window_base, authored_shas=frozenset({lane_own}), authored_blobs=frozenset({("src/paged.py", lane_blob)}))

    result = MergeOutcomeVerifier(repo).forecast_content_verdict((_MISSION, _LANE, _TARGET), claim, squashed_tree=None)

    assert result.status is VerifyStatus.FAIL
    assert result.divergence is not None
    assert merge_sha in {sha for sha, _ in result.divergence.unattributable_content}


# --- #7854: the merge / rebase gate still judges every resolution (operator ruling 2026-11-25) -----


@pytest.mark.parametrize(
    "resolution",
    ["hub v2 from main\n", "hub v1 mission\n", "hub v2 from main\nUNREVIEWED\n", "hub v1 mission\nhub v2 from main\n"],
    ids=["takes-the-target-side", "takes-the-mission-side", "adds-bytes", "combines-both-sides"],
)
def test_7854_a_merge_resolution_stays_content_for_the_per_commit_scan(repo: Path, resolution: str) -> None:
    """Under merge / rebase the closed world still names every resolution of a path both sides
    changed (#7307): keeping one side drops the other side's change, so it is never exempt. The
    squash forecast and gate judge the same Mission by final content instead (tests above).
    """
    window_base, merge_sha, lane_own, lane_blob = _merge_from_main_mission(repo, resolution=resolution)
    claim = _claim(window_base, authored_shas=frozenset({lane_own}), authored_blobs=frozenset({("src/paged.py", lane_blob)}))
    flagged = {sha for sha, _ in MergeOutcomeVerifier(repo)._unattributable_in((_MISSION, _LANE), claim)}
    assert merge_sha in flagged


def test_7854_clean_merge_from_main_carries_no_content(repo: Path) -> None:
    """Control (true since #7307): a merge with no resolution of its own is not content."""
    _git(repo, "checkout", "-q", "-b", _MISSION)
    _commit(repo, "src/own.py", "OWN = 1\n", "mission edit")
    _git(repo, "checkout", "-q", "main")
    _commit(repo, "docs/other.md", "main\n", "main moves")
    window_base = _git(repo, "rev-parse", "HEAD")
    _git(repo, "checkout", "-q", _MISSION)
    _git(repo, "merge", "--no-ff", "--no-edit", "main")
    merge_sha = _git(repo, "rev-parse", "HEAD")
    flagged = {sha for sha, _ in MergeOutcomeVerifier(repo)._unattributable_in((_MISSION,), _claim(window_base))}
    assert merge_sha not in flagged


# --- #7855: superseded planning-artifact docs commits on the Mission branch ----------------------


def _superseded_docs_mission(repo: Path, *, mirror_matches_target: bool) -> tuple[str, list[str], str, str]:
    """WP03's approved docs land on ``main`` (the target); the Mission branch carries two early
    copies and a mirror commit; lane-b merges the Mission branch.

    Returns ``(window_base, early_shas, lane_own_sha, lane_own_blob)``.
    """
    base = _git(repo, "rev-parse", "HEAD")
    _git(repo, "checkout", "-q", "-b", _MISSION)
    early = [
        _commit(repo, "docs/diagrams.md", "label fit, first draft\n", "docs(diagrams): explain label fit and contrast"),
        _commit(repo, "docs/diagrams.md", "label fit, first draft\nfont ruling\n", "docs(diagrams): state the label-font ruling"),
    ]
    _git(repo, "checkout", "-q", "main")
    _commit(repo, "docs/diagrams.md", "label fit, approved WP03\n", "WP03 docs on local main")
    window_base = _git(repo, "rev-parse", "HEAD")
    _git(repo, "checkout", "-q", _MISSION)
    mirror = "label fit, approved WP03\n" if mirror_matches_target else "label fit, approved WP03\nleftover draft\n"
    early.append(_commit(repo, "docs/diagrams.md", mirror, "docs(diagrams): match the WP03 docs committed on local main"))
    _git(repo, "checkout", "-q", "-b", _LANE, base)
    _commit(repo, "src/contrast.py", "CONTRAST = 4.5\n", "WP02: contrast")
    _git(repo, "merge", "--no-ff", "--no-edit", _MISSION)
    lane_own = _commit(repo, "src/clip.py", "CLIP = False\n", "WP02: label clipping")
    return window_base, early, lane_own, _blob(repo, lane_own, "src/clip.py")


def _lane_b_claim(repo: Path, window_base: str, lane_own: str, lane_blob: str) -> ApprovedWpCommitSet:
    contrast = _git(repo, "rev-parse", f"{_LANE}~1^1")
    return _claim(
        window_base,
        authored_shas=frozenset({lane_own, contrast}),
        authored_blobs=frozenset({("src/clip.py", lane_blob), ("src/contrast.py", _blob(repo, contrast, "src/contrast.py"))}),
    )


def test_7855_superseded_mission_branch_docs_commits_are_not_rejudged(repo: Path) -> None:
    window_base, early, lane_own, lane_blob = _superseded_docs_mission(repo, mirror_matches_target=True)
    claim = _lane_b_claim(repo, window_base, lane_own, lane_blob)
    verifier = MergeOutcomeVerifier(repo)
    flagged = {sha for sha, _ in verifier._unattributable_in((_LANE,), claim)}
    assert set(early) <= flagged, "fixture: the plain lane scan flags the early docs commits"

    tree = _squashed_tree(repo, window_base, _MISSION)
    result = verifier.forecast_content_verdict((_MISSION, _LANE, "main"), claim, squashed_tree=tree)

    assert result.status is VerifyStatus.PASS, result.recovery_guidance()


def test_7855_unsuperseded_docs_content_still_fails_on_the_squashed_tree(repo: Path) -> None:
    """Negative control: Mission branch docs that differ from the approved content on the target ship."""
    window_base, _early, lane_own, lane_blob = _superseded_docs_mission(repo, mirror_matches_target=False)
    claim = _lane_b_claim(repo, window_base, lane_own, lane_blob)
    tree = _squashed_tree(repo, window_base, _MISSION)

    result = MergeOutcomeVerifier(repo).forecast_content_verdict((_MISSION, _LANE, "main"), claim, squashed_tree=tree)

    assert result.status is VerifyStatus.FAIL
    assert result.divergence is not None
    assert [path for path, _ in result.divergence.unattributable_blobs] == ["docs/diagrams.md"]
