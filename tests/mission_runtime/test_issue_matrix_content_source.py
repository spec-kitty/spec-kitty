"""Reader content-source + shared two-partition split helper (IC-01b/IC-shared, WP02).

Mission ``issue-matrix-partition-integrity-01M3H10A`` WP02 (#5171/#4943,
FR-005, NFR-001). Covers:

* A post-consolidation coord fixture (worktree gone, coord branch retained):
  ``load_issue_matrix`` / ``issue_matrix_artifact_present`` /
  ``validate_issue_matrix`` / ``check_issue_matrix`` all resolve the verdict
  via WP01's content source (``#11`` -> ``fixed``), never the stale PRIMARY
  residue.
* The shared helper (:func:`~mission_runtime.issue_matrix_partition.
  resolve_issue_matrix_partition`) dispatches to a materialized coord ``Path``
  when present and to ref-content ``str`` when the coord dir is absent on a
  coord-routing topology.
* A flat-topology fixture is UNCHANGED: the helper resolves the matrix to
  PRIMARY (byte-for-byte parity) and ``check_issue_matrix`` behaves
  identically whether or not ``repo_root``/``mission_slug`` are threaded.

RED-first (T005): on base (before T006-T008), ``mission_runtime.
issue_matrix_partition`` does not exist and the readers do not accept a
``content=`` keyword -- this file fails to collect / every assertion raises
``TypeError``/``ImportError`` until T006-T008 land.

Fixtures build REAL git repos through the actual merge-time bookkeeping entry
point (mirroring ``tests/mission_runtime/test_issue_matrix_ref_read.py``,
WP01).
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from mission_runtime.issue_matrix_partition import resolve_issue_matrix_partition
from specify_cli.cli.commands.review._issue_matrix import IssueMatrixVerdict, validate_issue_matrix
from specify_cli.mission_metadata import load_meta, write_meta
from specify_cli.status.doctor import check_issue_matrix
from specify_cli.tasks.issue_matrix_migration import (
    issue_matrix_artifact_present,
    load_issue_matrix,
)

pytestmark = [pytest.mark.unit, pytest.mark.git_repo]

_ISSUE_NUMBER = "11"
_ISSUE_KEY = f"#{_ISSUE_NUMBER}"
_SPEC_MD_GATING_REFERENCE = f"Fixes {_ISSUE_KEY} in this mission.\n"


# ---------------------------------------------------------------------------
# Real-git plumbing helpers (mirrors test_issue_matrix_ref_read.py, WP01)
# ---------------------------------------------------------------------------


def _run(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=str(cwd), check=True, capture_output=True, text=True)


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return _run(["git", "-C", str(repo), *args], cwd=repo)


def _init_git_repo(repo: Path) -> str:
    repo.mkdir(parents=True, exist_ok=True)
    _run(["git", "init", "-qb", "main", str(repo)], cwd=repo)
    _git(repo, "config", "user.email", "test@test.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / ".kittify").mkdir()
    (repo / ".kittify" / "config.json").write_text("{}\n", encoding="utf-8")
    (repo / "README.md").write_text("# repo\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "init")
    return _git(repo, "rev-parse", "HEAD").stdout.strip()


def _write_meta(
    feature_dir: Path,
    *,
    mission_slug: str,
    mission_id: str,
    mid8: str,
    target_branch: str,
    topology: str,
    coordination_branch: str | None = None,
) -> None:
    meta: dict[str, object] = {
        "mission_slug": mission_slug,
        "mission_id": mission_id,
        "mid8": mid8,
        "mission_number": None,
        "mission_type": "software-dev",
        "target_branch": target_branch,
        "topology": topology,
        "friendly_name": "Issue-matrix content-source fixture",
    }
    if coordination_branch is not None:
        meta["coordination_branch"] = coordination_branch
    feature_dir.mkdir(parents=True, exist_ok=True)
    (feature_dir / "meta.json").write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _matrix_json(verdict: str, *, evidence_ref: str = "PR #123") -> str:
    return json.dumps({"rows": {_ISSUE_KEY: {"verdict": verdict, "evidence_ref": evidence_ref}}})


def _write_mission_scaffold(feature_dir: Path, *, matrix_content: str) -> None:
    feature_dir.mkdir(parents=True, exist_ok=True)
    (feature_dir / "spec.md").write_text(_SPEC_MD_GATING_REFERENCE, encoding="utf-8")
    (feature_dir / "issue-matrix.json").write_text(matrix_content, encoding="utf-8")


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    r = tmp_path / "repo"
    _init_git_repo(r)
    return r


# ---------------------------------------------------------------------------
# Post-consolidation coord fixture: worktree gone, coord branch retained
# ---------------------------------------------------------------------------


def _build_post_consolidation_coord_mission(repo: Path, *, mid8: str) -> tuple[str, Path]:
    """A CONSOLIDATED coord mission whose worktree was never materialized.

    The Target Ref carries a STALE ``in-mission`` verdict for ``#11``; the
    coordination branch (retained, never materialized on disk) carries the
    real ``fixed`` verdict -- proving a read that resolves the coord ref, not
    the primary residue. Mirrors
    ``tests/mission_runtime/test_issue_matrix_ref_read.py::
    _build_consolidated_coord_mission``.
    """
    from specify_cli.merge.baseline import record_baseline_merge_commit

    mission_id = f"{mid8}0000000000000000"
    mission_slug = f"widget-catalog-{mid8}"
    target_branch = f"kitty/mission-{mission_slug}"
    coordination_branch = f"kitty/mission-{mission_slug}-coord"

    _git(repo, "checkout", "-q", "-b", target_branch)
    feature_dir = repo / "kitty-specs" / mission_slug
    _write_meta(
        feature_dir,
        mission_slug=mission_slug,
        mission_id=mission_id,
        mid8=mid8,
        target_branch=target_branch,
        topology="coord",
        coordination_branch=coordination_branch,
    )
    _write_mission_scaffold(feature_dir, matrix_content=_matrix_json("in-mission"))
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", f"chore({mission_slug}): mission scaffold")
    scaffold_sha = _git(repo, "rev-parse", "HEAD").stdout.strip()

    # Branch coordination AFTER the scaffold so it carries the committed
    # (stale) matrix, then overwrite it with the REAL fixed verdict.
    _git(repo, "branch", coordination_branch, target_branch)

    record_baseline_merge_commit(feature_dir, scaffold_sha, mission_id=mission_id)
    meta = load_meta(feature_dir)
    assert meta is not None
    write_meta(feature_dir, meta, validate=False)
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", f"chore({mission_slug}): record baseline_merge_commit (E1 consolidation)")

    _git(repo, "checkout", "-q", coordination_branch)
    (feature_dir / "issue-matrix.json").write_text(_matrix_json("fixed"), encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", f"chore({mission_slug}): author issue-matrix verdict")
    # HEAD returns to the target branch -- the coordination branch is only a
    # retained REF; there is no coord worktree materialized on disk.
    _git(repo, "checkout", "-q", target_branch)

    return mission_slug, feature_dir


def test_shared_helper_dispatches_to_ref_content_post_consolidation(repo: Path) -> None:
    """The shared helper resolves a ``str`` content source, not a ``Path``."""
    mission_slug, feature_dir = _build_post_consolidation_coord_mission(repo, mid8="01KZQ1AA")

    primary_dir, matrix_source = resolve_issue_matrix_partition(repo, mission_slug)

    assert primary_dir == feature_dir
    assert isinstance(matrix_source, str)
    assert json.loads(matrix_source)["rows"][_ISSUE_KEY]["verdict"] == "fixed"


def test_load_issue_matrix_resolves_verdict_via_content_source(repo: Path) -> None:
    mission_slug, _feature_dir = _build_post_consolidation_coord_mission(repo, mid8="01KZQ1BB")
    _primary_dir, matrix_source = resolve_issue_matrix_partition(repo, mission_slug)
    assert isinstance(matrix_source, str)

    rows = load_issue_matrix(_primary_dir, content=matrix_source)

    assert len(rows) == 1
    assert rows[0].issue == _ISSUE_KEY
    assert rows[0].verdict is IssueMatrixVerdict.FIXED


def test_issue_matrix_artifact_present_via_content_source(repo: Path) -> None:
    mission_slug, _feature_dir = _build_post_consolidation_coord_mission(repo, mid8="01KZQ1CC")
    primary_dir, matrix_source = resolve_issue_matrix_partition(repo, mission_slug)
    assert isinstance(matrix_source, str)

    assert issue_matrix_artifact_present(primary_dir, content=matrix_source) is True


def test_validate_issue_matrix_resolves_via_content_source(repo: Path) -> None:
    mission_slug, feature_dir = _build_post_consolidation_coord_mission(repo, mid8="01KZQ1DD")
    _primary_dir, matrix_source = resolve_issue_matrix_partition(repo, mission_slug)
    assert isinstance(matrix_source, str)

    result = validate_issue_matrix(feature_dir / "issue-matrix.md", content=matrix_source)

    assert result.passed
    assert {row.issue for row in result.rows} == {_ISSUE_KEY}
    assert result.rows[0].verdict is IssueMatrixVerdict.FIXED


def test_check_issue_matrix_resolves_via_shared_helper(repo: Path) -> None:
    """``check_issue_matrix`` adopts the shared helper (T008): no missing-matrix
    finding, because the gating ``#11`` reference IS resolved -- via the coord
    ref content, not the stale primary residue (which itself carries ``#11``
    too, just with a different, non-terminal verdict -- proving this is not a
    vacuous pass)."""
    mission_slug, feature_dir = _build_post_consolidation_coord_mission(repo, mid8="01KZQ1EE")

    findings = check_issue_matrix(feature_dir, repo_root=repo, mission_slug=mission_slug)

    assert findings == []


# ---------------------------------------------------------------------------
# Flat topology: UNCHANGED (contract guarantee #2 -- branch-flat parity)
# ---------------------------------------------------------------------------


def _build_flat_mission_missing_matrix(repo: Path, *, mid8: str) -> tuple[str, Path]:
    mission_id = f"{mid8}0000000000000000"
    mission_slug = f"flat-mission-{mid8}"
    target_branch = f"kitty/mission-{mission_slug}"

    _git(repo, "checkout", "-q", "-b", target_branch)
    feature_dir = repo / "kitty-specs" / mission_slug
    _write_meta(
        feature_dir,
        mission_slug=mission_slug,
        mission_id=mission_id,
        mid8=mid8,
        target_branch=target_branch,
        topology="single_branch",
    )
    feature_dir.mkdir(parents=True, exist_ok=True)
    (feature_dir / "spec.md").write_text(_SPEC_MD_GATING_REFERENCE, encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", f"chore({mission_slug}): mission scaffold (no issue-matrix)")

    return mission_slug, feature_dir


def test_shared_helper_flat_topology_resolves_matrix_to_primary(repo: Path) -> None:
    mission_slug, feature_dir = _build_flat_mission_missing_matrix(repo, mid8="01KZQ1FF")

    primary_dir, matrix_source = resolve_issue_matrix_partition(repo, mission_slug)

    assert primary_dir == feature_dir
    assert matrix_source == feature_dir


def test_check_issue_matrix_flat_topology_unchanged_with_and_without_helper(repo: Path) -> None:
    """Threading ``repo_root``/``mission_slug`` on a flat topology must not
    change the result: both call shapes report the SAME missing-matrix
    finding (byte-for-byte parity, contract guarantee #2)."""
    mission_slug, feature_dir = _build_flat_mission_missing_matrix(repo, mid8="01KZQ1GG")

    legacy_findings = check_issue_matrix(feature_dir)
    helper_findings = check_issue_matrix(feature_dir, repo_root=repo, mission_slug=mission_slug)

    assert len(legacy_findings) == 1
    assert f"#{_ISSUE_NUMBER}" in legacy_findings[0].message
    assert legacy_findings[0].message == helper_findings[0].message
    assert legacy_findings[0].severity == helper_findings[0].severity
    assert legacy_findings[0].category == helper_findings[0].category
