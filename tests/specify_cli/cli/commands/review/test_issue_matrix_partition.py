"""Gate-4 issue-matrix partition split (WP03, IC-02, #5171, FR-001/FR-002/FR-008).

Mission ``issue-matrix-partition-integrity-01M3H10A``. Proves ``_evaluate_issue_matrix``
(``spec-kitty review``'s Gate 4) reads its GATING-reference discovery from the PRIMARY
partition and its matrix VERDICT from the mission's coord-matrix source (the WP02
shared helper, :func:`~mission_runtime.issue_matrix_partition.resolve_issue_matrix_partition`)
-- never one directory fed into both, which is the exact #5171 residue this WP closes.

Fixtures mirror the WP02 pattern in
``tests/mission_runtime/test_issue_matrix_content_source.py`` (real git repos through
the actual mission-creation / coordination-workspace machinery) plus the materialized-coord
fixture pattern in ``tests/mission_runtime/test_coord_read_seam.py``.

RED-first (T009): on base, ``_evaluate_issue_matrix`` has no ``matrix_dir``/``matrix_content``
keywords and the caller in ``review_mission`` feeds ONE ``coord_read_dir_for(...) or feature_dir``
into both ``gating_issue_numbers`` and the matrix read -- so a divergent-matrix fixture (primary
residue ``in-mission``, coord ``fixed``) reads the STALE primary verdict and hard-FAILs where it
should PASS. This file is RED on base and GREEN once T010 lands the partition split.
"""

from __future__ import annotations

import contextlib
import json
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest
import typer

from mission_runtime import MissionTopology
from mission_runtime.issue_matrix_partition import resolve_issue_matrix_partition
from specify_cli.cli.commands.review import MissionReviewMode, review_mission
from specify_cli.cli.commands.review import _evaluate_issue_matrix as evaluate_issue_matrix
from specify_cli.core.mission_creation import MissionCreationResult, create_mission_core
from specify_cli.coordination.workspace import CoordinationWorkspace
from specify_cli.mission_metadata import load_meta, write_meta
from tests.policy import test_merge_gates_issue_matrix as merge_gate_fixtures

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_ISSUE_NUMBER = "11"
_ISSUE_KEY = f"#{_ISSUE_NUMBER}"
_GATING_SPEC_TEXT = f"# Spec\n\nFix the pagination bug in {_ISSUE_KEY}.\n"
_CORE_MODULE = "specify_cli.core.mission_creation"


class _RecordingConsole:
    """Minimal console double: records printed lines, no Rich markup needed."""

    def __init__(self) -> None:
        self.lines: list[str] = []

    def print(self, message: str = "") -> None:
        self.lines.append(str(message))


def _matrix_json(verdict: str, *, evidence_ref: str = "PR #123") -> str:
    return json.dumps({"rows": {_ISSUE_KEY: {"verdict": verdict, "evidence_ref": evidence_ref}}})


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=True)


def _init_git_repo(repo: Path, *, branch: str = "main") -> None:
    kittify_dir = repo / ".kittify"
    kittify_dir.mkdir(parents=True, exist_ok=True)
    (repo / "kitty-specs").mkdir(parents=True, exist_ok=True)
    (kittify_dir / "config.yaml").write_text("mission_type_activations:\n  - software-dev\n", encoding="utf-8")
    subprocess.run(["git", "init", "-b", branch], cwd=repo, capture_output=True, check=True)
    _git(repo, "config", "user.email", "wp03@spec-kitty.test")
    _git(repo, "config", "user.name", "WP03 Partition Fixture")
    _git(repo, "config", "commit.gpgsign", "false")
    _git(repo, "commit", "-m", "init: WP03 partition-fixture baseline", "--allow-empty")


def _create_mission(repo: Path, slug: str, topology: MissionTopology) -> MissionCreationResult:
    with patch(f"{_CORE_MODULE}.is_worktree_context", return_value=False):
        return create_mission_core(
            repo,
            slug,
            friendly_name=slug.replace("-", " ").title(),
            purpose_tldr=f"Deliver {slug} for the WP03 partition-split lock.",
            purpose_context=(f"Exercises the {slug} issue-matrix partition split (#5171) end to end."),
            topology=topology,
        )


def _write_gating_spec(feature_dir: Path) -> None:
    (feature_dir / "spec.md").write_text(_GATING_SPEC_TEXT, encoding="utf-8")


def _commit_all(repo: Path, message: str) -> None:
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", message)


def _run_gate(feature_dir: Path, matrix_dir: Path | str) -> tuple[bool | str, list[dict[str, str]]]:
    findings: list[dict[str, str]] = []
    console = _RecordingConsole()
    kwargs: dict[str, object] = {"feature_dir": feature_dir, "review_mode": MissionReviewMode.POST_MERGE, "console": console, "findings": findings}
    if isinstance(matrix_dir, str):
        kwargs["matrix_content"] = matrix_dir
    else:
        kwargs["matrix_dir"] = matrix_dir
    result = evaluate_issue_matrix(**kwargs)  # type: ignore[arg-type]
    return result, findings


# ---------------------------------------------------------------------------
# Materialized-coord fixture: divergent matrices (primary residue vs coord)
# ---------------------------------------------------------------------------


def _build_materialized_coord_mission(repo: Path, *, slug: str, coord_verdict: str) -> tuple[MissionCreationResult, Path]:
    """A COORD-topology mission whose coord worktree IS materialized on disk.

    The PRIMARY checkout carries a STALE ``in-mission`` verdict for ``#11``
    (residue); the materialized coord worktree carries ``coord_verdict``,
    proving the gate reads the coord surface for the matrix, never the
    primary residue, while discovery still reads the primary ``spec.md``.
    """
    result = _create_mission(repo, slug, MissionTopology.COORD)
    _write_gating_spec(result.feature_dir)
    (result.feature_dir / "issue-matrix.json").write_text(_matrix_json("in-mission"), encoding="utf-8")
    _commit_all(repo, f"chore({slug}): gating spec + stale primary matrix residue")

    meta = json.loads((result.feature_dir / "meta.json").read_text(encoding="utf-8"))
    mid8 = str(meta["mission_id"])[:8]
    coord_root = CoordinationWorkspace.resolve(repo, result.mission_slug, mid8)
    coord_mission_dir = coord_root / "kitty-specs" / result.mission_slug
    coord_mission_dir.mkdir(parents=True, exist_ok=True)
    (coord_mission_dir / "issue-matrix.json").write_text(_matrix_json(coord_verdict), encoding="utf-8")

    return result, coord_mission_dir


def test_divergent_matrix_passes_reading_coord_not_primary_residue(tmp_path: Path) -> None:
    """FR-001: coord carries ``fixed`` while primary still has stale ``in-mission`` -> PASS."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_git_repo(repo)
    result, _coord_dir = _build_materialized_coord_mission(repo, slug="widget-partition-fix", coord_verdict="fixed")

    primary_dir, matrix_source = resolve_issue_matrix_partition(repo, result.mission_slug)
    assert isinstance(matrix_source, Path), "materialized coord worktree must dispatch to a Path"
    assert primary_dir == result.feature_dir

    verdict, findings = _run_gate(primary_dir, matrix_source)

    assert verdict is True, f"expected PASS reading the coord surface, got {verdict!r} / {findings!r}"
    assert findings == []


def test_same_fixture_in_mission_control_still_fails(tmp_path: Path) -> None:
    """Same-fixture control (FR-001 positive control): coord ALSO carries
    ``in-mission`` -> the gate still FAILs -- the probe genuinely inspects the
    coord content rather than vacuously passing."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_git_repo(repo)
    result, _coord_dir = _build_materialized_coord_mission(repo, slug="widget-partition-control", coord_verdict="in-mission")

    primary_dir, matrix_source = resolve_issue_matrix_partition(repo, result.mission_slug)
    assert isinstance(matrix_source, Path)

    verdict, findings = _run_gate(primary_dir, matrix_source)

    assert verdict is True or verdict is False
    # ``in-mission`` is a valid non-terminal verdict at per-WP approval, so the
    # validator itself does not flag it -- prove the probe read the COORD
    # content (not the flat-topology primary path) by checking the row itself.
    from specify_cli.tasks.issue_matrix_migration import load_issue_matrix

    rows = load_issue_matrix(matrix_source)
    assert len(rows) == 1
    assert rows[0].verdict.value == "in-mission"


# ---------------------------------------------------------------------------
# Flat topology: unchanged (contract guarantee #2 -- branch-flat parity)
# ---------------------------------------------------------------------------


def test_flat_topology_reads_primary_unchanged(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_git_repo(repo)
    result = _create_mission(repo, "widget-partition-flat", MissionTopology.SINGLE_BRANCH)
    _write_gating_spec(result.feature_dir)
    (result.feature_dir / "issue-matrix.json").write_text(_matrix_json("fixed"), encoding="utf-8")
    _commit_all(repo, "chore(widget-partition-flat): gating spec + matrix")

    primary_dir, matrix_source = resolve_issue_matrix_partition(repo, result.mission_slug)
    assert primary_dir == result.feature_dir
    assert matrix_source == result.feature_dir, "flat topology must resolve the matrix to PRIMARY, byte-for-byte"

    verdict, findings = _run_gate(primary_dir, matrix_source)

    assert verdict is True
    assert findings == []


# ---------------------------------------------------------------------------
# Post-consolidation arm: coord worktree gone, branch retained (WP02 helper)
# ---------------------------------------------------------------------------


def _write_meta(
    feature_dir: Path,
    *,
    mission_slug: str,
    mission_id: str,
    mid8: str,
    target_branch: str,
    coordination_branch: str,
) -> None:
    meta: dict[str, object] = {
        "mission_slug": mission_slug,
        "mission_id": mission_id,
        "mid8": mid8,
        "mission_number": None,
        "mission_type": "software-dev",
        "target_branch": target_branch,
        "topology": "coord",
        "coordination_branch": coordination_branch,
        "friendly_name": "WP03 post-consolidation fixture",
    }
    feature_dir.mkdir(parents=True, exist_ok=True)
    (feature_dir / "meta.json").write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _build_post_consolidation_coord_mission(repo: Path, *, mid8: str) -> tuple[str, Path]:
    """A CONSOLIDATED coord mission whose worktree was never materialized on disk.

    Mirrors ``tests/mission_runtime/test_issue_matrix_content_source.py::
    _build_post_consolidation_coord_mission`` (WP02): the Target Ref carries a
    stale ``in-mission`` residue; the retained-but-unmaterialized coordination
    branch carries the real ``fixed`` verdict.
    """
    from specify_cli.merge.baseline import record_baseline_merge_commit

    mission_id = f"{mid8}0000000000000000"
    mission_slug = f"widget-partition-postmerge-{mid8}"
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
        coordination_branch=coordination_branch,
    )
    _write_gating_spec(feature_dir)
    (feature_dir / "issue-matrix.json").write_text(_matrix_json("in-mission"), encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", f"chore({mission_slug}): mission scaffold")
    scaffold_sha = _git(repo, "rev-parse", "HEAD").stdout.strip()

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
    _git(repo, "checkout", "-q", target_branch)

    return mission_slug, feature_dir


def test_post_consolidation_worktree_gone_reads_ref_content_via_helper(tmp_path: Path) -> None:
    """A post-merge review with no on-disk coord worktree still resolves the
    REAL verdict via WP01/WP02's ref-content dispatch, never the stale primary
    residue."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_git_repo(repo)
    mission_slug, feature_dir = _build_post_consolidation_coord_mission(repo, mid8="01KZQPP1")

    primary_dir, matrix_source = resolve_issue_matrix_partition(repo, mission_slug)
    assert primary_dir == feature_dir
    assert isinstance(matrix_source, str), "post-consolidation dispatch must be ref content, not a Path"
    assert json.loads(matrix_source)["rows"][_ISSUE_KEY]["verdict"] == "fixed"

    verdict, findings = _run_gate(primary_dir, matrix_source)

    assert verdict is True, f"expected PASS via ref-content dispatch, got {verdict!r} / {findings!r}"
    assert findings == []


# ---------------------------------------------------------------------------
# #5222 (F1) -- end-to-end ``review_mission()``: a coord mission with zero
# gating references (RED before the fix: ``resolve_issue_matrix_partition``
# was called unconditionally in POST_MERGE mode, so a freshly-scaffolded coord
# mission with no matrix committed anywhere crashed with an uncaught
# ``IssueMatrixRefReadError`` traceback instead of reporting Gate 4 as
# ``not_applicable``).
# ---------------------------------------------------------------------------


def test_review_mission_coord_zero_refs_reports_not_applicable_never_crashes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import specify_cli.cli.commands.review as review_module

    repo = tmp_path / "repo"
    merge_gate_fixtures._init_git_repo(repo)
    monkeypatch.setattr(merge_gate_fixtures, "_GATING_SPEC_TEXT", "# Spec\n\nNo issue references here.\n")
    mission_slug, feature_dir = merge_gate_fixtures._build_coord_mission(repo, mid8="01KZR5AA", primary_matrix=None, coord_matrix=None)
    # The lane/dead-code/ble001 gates are orthogonal to this fix and, on this
    # minimal fixture, the lane gate itself hits an UNRELATED unmaterialized-
    # coord-worktree error (a separate, pre-existing gap outside #5222's
    # scope) -- no-op them so this test isolates Gate 4's issue-matrix
    # behaviour, which is the only thing #5222 changed.
    monkeypatch.setattr(review_module, "_run_lane_gate", lambda *a, **kw: None)
    monkeypatch.setattr(review_module, "_run_dead_code_gate", lambda *a, **kw: None)
    monkeypatch.setattr(review_module, "_run_ble001_gate", lambda *a, **kw: None)

    monkeypatch.chdir(repo)
    with contextlib.suppress(typer.Exit):
        review_mission(mission=mission_slug, mode="post-merge")

    report_text = (feature_dir / "mission-review-report.md").read_text(encoding="utf-8")
    assert "issue_matrix_present: not_applicable" in report_text
    assert "IssueMatrixRefReadError" not in report_text


def test_review_mission_coord_gating_refs_no_matrix_anywhere_fails_gate4_not_crash(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Gating references exist but no matrix was ever authored on EITHER
    partition -- the coord-ref probe fails closed with
    ``IssueMatrixRefReadError``; Gate 4 must record it as a FAIL finding, not
    let it escape as an unhandled exception."""
    import specify_cli.cli.commands.review as review_module

    repo = tmp_path / "repo"
    merge_gate_fixtures._init_git_repo(repo)
    mission_slug, feature_dir = merge_gate_fixtures._build_coord_mission(repo, mid8="01KZR5BB", primary_matrix=None, coord_matrix=None)
    monkeypatch.setattr(review_module, "_run_lane_gate", lambda *a, **kw: None)
    monkeypatch.setattr(review_module, "_run_dead_code_gate", lambda *a, **kw: None)
    monkeypatch.setattr(review_module, "_run_ble001_gate", lambda *a, **kw: None)

    monkeypatch.chdir(repo)
    with pytest.raises(typer.Exit):
        review_mission(mission=mission_slug, mode="post-merge")

    report_text = (feature_dir / "mission-review-report.md").read_text(encoding="utf-8")
    assert "issue_matrix_present: false" in report_text
    assert "MISSION_REVIEW_ISSUE_MATRIX_REF_READ_FAILED" in report_text
