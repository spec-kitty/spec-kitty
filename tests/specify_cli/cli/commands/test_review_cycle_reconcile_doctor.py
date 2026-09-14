"""Tests for ``spec-kitty doctor review-cycle-reconcile`` (WP08, FR-008, T035-T039).

Builds REAL fixture corpora for both stranded classes named in the module
docstring of ``_review_cycle_reconcile_doctor.py``:

- ``deleted_coord_branch_absorption`` (T037) -- a REAL git repo whose
  ``meta.json`` declares a ``coordination_branch`` that was never created (the
  measured 45-mission corpus's shape), proving the detector reaches its
  seeded record via :class:`~specify_cli.coordination.surface_resolver
  .CoordinationBranchDeleted` exception-absorption, not a direct read.
- ``live_coord_pre_adr_primary_record`` (T039) -- a coordination worktree
  MATERIALIZED on disk (``probe_coord_state`` only checks path existence for
  this state; no real git worktree is required), proving a pre-ADR record
  still on PRIMARY is reported distinctly from the T037 case.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

import specify_cli.cli.commands.doctor as doctor_module
from specify_cli.cli.commands import _review_cycle_reconcile_doctor as rcr
from specify_cli.missions._read_path_resolver import coord_feature_dir

# PR #3211 landing pass (2026-08-05, F6): re-marked from `fast` to
# `integration, git_repo` -- both fixture classes above build a REAL git
# repo/worktree and drive it via ``subprocess`` (see ``_git``/
# ``_init_git_repo`` below), which `test_pytest_marker_correctness.py`'s
# Rule 1/Rule 2 require: `git_repo` presence, and `fast` exclusion, for any
# file that invokes git via subprocess.
pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

runner = CliRunner()

_MISSION_SLUG = "review-cycle-reconcile-fixture"
# ``resolve_mid8`` derives mid8 from the FIRST 8 CHARS of ``mission_id``
# (``mission_runtime.identity.resolve_mid8``), not from meta.json's ``mid8``
# key, when reached via ``_classify_artifact_surface``'s ``resolve_mid8(...)``
# call -- so ``_MID8`` must actually be ``_MISSION_ID[:8]`` for the coord
# worktree path this fixture composes to match what production code resolves.
_MISSION_ID = ("01RCRTEST1" + "0" * 26)[:26]
_MID8 = _MISSION_ID[:8]
_SLUG_WITH_MID8 = f"{_MISSION_SLUG}-{_MID8}"
_COORD_BRANCH = f"kitty/mission-{_SLUG_WITH_MID8}"


def _git(repo_root: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(repo_root), *args],
        check=True,
        capture_output=True,
        text=True,
    )


def _init_git_repo(repo_root: Path) -> None:
    repo_root.mkdir(parents=True, exist_ok=True)
    _git(repo_root, "init", "-q")
    _git(repo_root, "config", "user.email", "wp08@example.test")
    _git(repo_root, "config", "user.name", "WP08 Fixture")
    _git(repo_root, "commit", "--allow-empty", "-qm", "init")


def _write_meta(
    feature_dir: Path, *, coordination_branch: str | None, topology: str = "coord",
) -> None:
    feature_dir.mkdir(parents=True, exist_ok=True)
    meta: dict[str, object] = {
        "mission_id": _MISSION_ID,
        "mid8": _MID8,
        "mission_slug": _SLUG_WITH_MID8,
        "topology": topology,
    }
    if coordination_branch is not None:
        meta["coordination_branch"] = coordination_branch
    (feature_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")


def _primary_feature_dir(repo_root: Path) -> Path:
    return repo_root / "kitty-specs" / _SLUG_WITH_MID8


def _seed_review_cycle(wp_dir: Path, cycle_n: int = 1) -> Path:
    wp_dir.mkdir(parents=True, exist_ok=True)
    path = wp_dir / f"review-cycle-{cycle_n}.md"
    path.write_text("---\nverdict: rejected\n---\nbody\n", encoding="utf-8")
    return path


def _seed_arbiter_json(wp_dir: Path, n: int = 1) -> Path:
    wp_dir.mkdir(parents=True, exist_ok=True)
    path = wp_dir / f"arbiter-override-{n}.json"
    path.write_text(json.dumps({"category": "waived"}), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# T037 -- deleted coord branch, real git repo, exception-absorption path.
# ---------------------------------------------------------------------------


def _build_deleted_coord_branch_mission(repo_root: Path) -> Path:
    """A REAL git repo whose declared coordination branch was NEVER created --
    the measured 45-mission ``CoordinationBranchDeleted`` shape (ADR
    2026-08-03-1)."""
    _init_git_repo(repo_root)
    feature_dir = _primary_feature_dir(repo_root)
    _write_meta(feature_dir, coordination_branch=_COORD_BRANCH)
    return feature_dir


def test_deleted_coord_branch_mission_finds_seeded_record_via_absorption(
    tmp_path: Path,
) -> None:
    """T035/T037: a record seeded at the retired resolver's PRIMARY output is
    found via exception-absorption -- NOT via a direct read (the mission's
    canonical REVIEW_CYCLE resolution raises CoordinationBranchDeleted first)."""
    repo_root = tmp_path
    feature_dir = _build_deleted_coord_branch_mission(repo_root)
    wp_dir = feature_dir / "tasks" / "WP01-some-title"
    seeded = _seed_review_cycle(wp_dir)

    # Prove the canonical seam genuinely raises for this fixture -- otherwise
    # the detector's own absorption path is untested (it would just be
    # exercising a direct read that happens to succeed).
    from mission_runtime import MissionArtifactKind, placement_seam
    from specify_cli.coordination.surface_resolver import CoordinationBranchDeleted

    with pytest.raises(CoordinationBranchDeleted):
        placement_seam(repo_root, _SLUG_WITH_MID8).read_dir(MissionArtifactKind.REVIEW_CYCLE)

    report = rcr._report_for_mission(repo_root, feature_dir)
    assert report is not None
    assert report.stranded_class == rcr._DELETED_COORD_BRANCH_CLASS
    assert not report.clean
    found_paths = {p for f in report.findings for p in f.record_paths}
    assert str(seeded) in found_paths
    # Every finding names its retired resolver + retiring FR (never a bare count).
    for finding in report.findings:
        assert finding.retired_resolver
        assert finding.retiring_fr.startswith("FR-")
        assert finding.stranded_class == rcr._DELETED_COORD_BRANCH_CLASS


def test_deleted_coord_branch_mission_with_no_records_reports_clean(
    tmp_path: Path,
) -> None:
    """A legitimate clean result: the absorption path itself must not manufacture
    a false positive when nothing is actually stranded."""
    repo_root = tmp_path
    feature_dir = _build_deleted_coord_branch_mission(repo_root)

    report = rcr._report_for_mission(repo_root, feature_dir)

    assert report is not None
    assert report.stranded_class == rcr._DELETED_COORD_BRANCH_CLASS
    assert report.clean
    assert report.findings == []


def test_deleted_coord_branch_mission_already_reconciled_does_not_crash(
    tmp_path: Path,
) -> None:
    """A mission among the 45 that has SINCE been reconciled (or was hand-
    flattened) must not crash -- 'no stranded record found' is a legitimate
    clean result, not a bug (WP prompt T037 edge case)."""
    repo_root = tmp_path
    feature_dir = _build_deleted_coord_branch_mission(repo_root)
    # No tasks/ dir at all.
    report = rcr._report_for_mission(repo_root, feature_dir)
    assert report is not None
    assert report.clean


# ---------------------------------------------------------------------------
# T039 -- live coord branch, materialized coord worktree, pre-ADR PRIMARY record.
# ---------------------------------------------------------------------------


def _build_live_coord_mission(repo_root: Path, *, materialize_coord: bool = True) -> Path:
    """A coord-topology mission whose coordination worktree IS materialized
    on disk. ``probe_coord_state``'s MATERIALIZED arm only checks
    ``Path.exists()`` (see ``_read_path_resolver.py::probe_coord_state``), so
    no real git worktree is required to exercise this state."""
    feature_dir = _primary_feature_dir(repo_root)
    _write_meta(feature_dir, coordination_branch=_COORD_BRANCH)
    if materialize_coord:
        coord_dir = coord_feature_dir(repo_root, _SLUG_WITH_MID8, _MID8)
        coord_dir.mkdir(parents=True, exist_ok=True)
        _write_meta(coord_dir, coordination_branch=_COORD_BRANCH)
    return feature_dir


def test_live_coord_branch_with_pre_adr_primary_record_is_reported_distinctly(
    tmp_path: Path,
) -> None:
    """T039: canonical resolution genuinely lands on COORD (branch alive), but
    a record predating the ADR still sits on PRIMARY -- reported as its OWN
    stranded class, distinct from T037's deleted-branch absorption."""
    repo_root = tmp_path
    feature_dir = _build_live_coord_mission(repo_root)

    from mission_runtime import MissionArtifactKind, placement_seam

    resolved = placement_seam(repo_root, _SLUG_WITH_MID8).read_dir(MissionArtifactKind.REVIEW_CYCLE)
    assert resolved != feature_dir  # canonical resolution IS coord, not primary

    wp_dir = feature_dir / "tasks" / "WP01-some-title"
    seeded = _seed_review_cycle(wp_dir)

    report = rcr._report_for_mission(repo_root, feature_dir)

    assert report is not None
    assert report.stranded_class == rcr._LIVE_COORD_PRE_ADR_CLASS
    assert not report.clean
    found_paths = {p for f in report.findings for p in f.record_paths}
    assert str(seeded) in found_paths
    assert all(f.stranded_class == rcr._LIVE_COORD_PRE_ADR_CLASS for f in report.findings)


def test_live_coord_branch_with_no_stranded_record_reports_clean(tmp_path: Path) -> None:
    repo_root = tmp_path
    feature_dir = _build_live_coord_mission(repo_root)

    report = rcr._report_for_mission(repo_root, feature_dir)

    assert report is not None
    assert report.stranded_class == rcr._LIVE_COORD_PRE_ADR_CLASS
    assert report.clean


def test_both_stranded_classes_are_never_conflated_across_missions(tmp_path: Path) -> None:
    """A repo carrying BOTH classes at once (different missions) must classify
    each mission's findings independently."""
    deleted_root = tmp_path / "deleted"
    live_root = tmp_path / "live"
    deleted_feature_dir = _build_deleted_coord_branch_mission(deleted_root)
    _seed_review_cycle(deleted_feature_dir / "tasks" / "WP01-some-title")
    live_feature_dir = _build_live_coord_mission(live_root)
    _seed_review_cycle(live_feature_dir / "tasks" / "WP01-some-title")

    deleted_report = rcr._report_for_mission(deleted_root, deleted_feature_dir)
    live_report = rcr._report_for_mission(live_root, live_feature_dir)

    assert deleted_report is not None and live_report is not None
    assert deleted_report.stranded_class == rcr._DELETED_COORD_BRANCH_CLASS
    assert live_report.stranded_class == rcr._LIVE_COORD_PRE_ADR_CLASS
    assert {f.stranded_class for f in deleted_report.findings} == {rcr._DELETED_COORD_BRANCH_CLASS}
    assert {f.stranded_class for f in live_report.findings} == {rcr._LIVE_COORD_PRE_ADR_CLASS}


# ---------------------------------------------------------------------------
# Non-coord topology: nothing to reconcile, no false positives.
# ---------------------------------------------------------------------------


def test_non_coord_topology_mission_has_nothing_to_reconcile(tmp_path: Path) -> None:
    repo_root = tmp_path
    feature_dir = _primary_feature_dir(repo_root)
    _write_meta(feature_dir, coordination_branch=None, topology="single_branch")
    _seed_review_cycle(feature_dir / "tasks" / "WP01-some-title")

    report = rcr._report_for_mission(repo_root, feature_dir)

    assert report is None


def test_missing_meta_json_is_skipped_not_crashed(tmp_path: Path) -> None:
    repo_root = tmp_path
    feature_dir = repo_root / "kitty-specs" / "no-meta-mission"
    feature_dir.mkdir(parents=True)

    assert rcr._report_for_mission(repo_root, feature_dir) is None


# ---------------------------------------------------------------------------
# Per-retired-resolver shapes (T035) -- each shape is independently exercised.
# ---------------------------------------------------------------------------


def test_arbiter_json_sidecar_is_detected_via_bare_wp_id_shape(tmp_path: Path) -> None:
    """The arbiter's JSON sidecar fallback (retired under FR-009, WP12) is
    keyed on the BARE wp_id, distinct from the wp_slug-keyed shapes."""
    repo_root = tmp_path
    feature_dir = _build_deleted_coord_branch_mission(repo_root)
    bare_wp_dir = feature_dir / "tasks" / "WP01"
    seeded = _seed_arbiter_json(bare_wp_dir)

    report = rcr._report_for_mission(repo_root, feature_dir)

    assert report is not None
    assert not report.clean
    arbiter_findings = [f for f in report.findings if f.retiring_fr == "FR-009"]
    assert arbiter_findings
    assert any(str(seeded) in f.record_paths for f in arbiter_findings)


def test_artifact_dirs_for_wp_shape_matches_prefix_fan_out(tmp_path: Path) -> None:
    """``_shape_artifact_dirs_for_wp`` (FR-007) mirrors
    ``post_merge/review_artifact_consistency.py::_artifact_dirs_for_wp``'s
    fan-out: the exact ``tasks/<wp_id>`` dir plus every ``tasks/<wp_id>-*``
    sibling."""
    primary_feature_dir = tmp_path / "kitty-specs" / _SLUG_WITH_MID8
    wp_slug_dir = primary_feature_dir / "tasks" / "WP01-some-title"
    wp_slug_dir.mkdir(parents=True)

    candidates = rcr._shape_artifact_dirs_for_wp(primary_feature_dir, "WP01", "WP01-some-title")

    assert wp_slug_dir in candidates


def test_review_cycle_wp_dir_shape_is_wp_slug_keyed(tmp_path: Path) -> None:
    """``_shape_review_cycle_wp_dir`` (FR-003) is keyed on ``wp_slug`` (matching
    ``review/cycle.py::_review_cycle_wp_dir``'s own WORK_PACKAGE_TASK-anchored
    join), not the bare ``wp_id``."""
    primary_feature_dir = tmp_path / "kitty-specs" / _SLUG_WITH_MID8
    wp_slug_dir = primary_feature_dir / "tasks" / "WP01-some-title"
    wp_slug_dir.mkdir(parents=True)

    candidates = rcr._shape_review_cycle_wp_dir(primary_feature_dir, "WP01", "WP01-some-title")

    assert candidates == [wp_slug_dir]
    assert rcr._shape_review_cycle_wp_dir(primary_feature_dir, "WP01", "WP01") == []


# ---------------------------------------------------------------------------
# CLI surface (human + --json + --mission), mirroring test_cutover_doctor.py.
# ---------------------------------------------------------------------------


def test_doctor_review_cycle_reconcile_json_reports_finding(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_root = tmp_path
    feature_dir = _build_deleted_coord_branch_mission(repo_root)
    _seed_review_cycle(feature_dir / "tasks" / "WP01-some-title")
    monkeypatch.setattr(doctor_module, "locate_project_root", lambda *a, **k: repo_root)

    result = runner.invoke(doctor_module.app, ["review-cycle-reconcile", "--json"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert len(payload) == 1  # one mission in this fixture
    assert payload[0]["mission_slug"] == _SLUG_WITH_MID8
    assert payload[0]["clean"] is False
    assert payload[0]["findings"]
    for finding in payload[0]["findings"]:
        assert finding["mission_slug"] == _SLUG_WITH_MID8
        assert finding["wp_id"] == "WP01"
        assert finding["retired_resolver"]
        assert finding["retiring_fr"]
        assert finding["stranded_class"] == rcr._DELETED_COORD_BRANCH_CLASS
        assert finding["resolved_directory"]
        assert finding["record_paths"]


def test_doctor_review_cycle_reconcile_reports_clean_for_mission_with_nothing_stranded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_root = tmp_path
    _build_deleted_coord_branch_mission(repo_root)
    monkeypatch.setattr(doctor_module, "locate_project_root", lambda *a, **k: repo_root)

    result = runner.invoke(doctor_module.app, ["review-cycle-reconcile", "--json"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert len(payload) == 1  # one mission in this fixture
    assert payload[0]["clean"] is True
    assert payload[0]["findings"] == []


def test_doctor_review_cycle_reconcile_human_output_names_every_finding(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_root = tmp_path
    feature_dir = _build_deleted_coord_branch_mission(repo_root)
    _seed_review_cycle(feature_dir / "tasks" / "WP01-some-title")
    monkeypatch.setattr(doctor_module, "locate_project_root", lambda *a, **k: repo_root)

    result = runner.invoke(doctor_module.app, ["review-cycle-reconcile"])

    assert result.exit_code == 0, result.output
    assert _SLUG_WITH_MID8 in result.output
    assert "WP01" in result.output
    assert rcr._DELETED_COORD_BRANCH_CLASS in result.output


def test_doctor_review_cycle_reconcile_mission_scope_excludes_other_missions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``--mission`` scopes the sweep to one mission only."""
    repo_root = tmp_path
    _init_git_repo(repo_root)
    feature_dir = _primary_feature_dir(repo_root)
    _write_meta(feature_dir, coordination_branch=_COORD_BRANCH)
    _seed_review_cycle(feature_dir / "tasks" / "WP01-some-title")

    other_dir = repo_root / "kitty-specs" / "another-mission-DEADBEEF"
    other_dir.mkdir(parents=True)
    (other_dir / "meta.json").write_text(
        json.dumps({"mission_id": "0" * 26, "mid8": "DEADBEEF", "topology": "single_branch"}),
        encoding="utf-8",
    )

    monkeypatch.setattr(doctor_module, "locate_project_root", lambda *a, **k: repo_root)

    result = runner.invoke(
        doctor_module.app, ["review-cycle-reconcile", "--json", "--mission", _SLUG_WITH_MID8],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert {entry["mission_slug"] for entry in payload} == {_SLUG_WITH_MID8}


def test_doctor_review_cycle_reconcile_not_in_project_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(doctor_module, "locate_project_root", lambda *a, **k: None)

    result = runner.invoke(doctor_module.app, ["review-cycle-reconcile"])

    assert result.exit_code == 1


# ---------------------------------------------------------------------------
# T036 -- structural constraint: doctor.py's diff is a thin shim only.
# ---------------------------------------------------------------------------


def test_doctor_py_review_cycle_reconcile_shell_is_a_thin_delegator() -> None:
    """The ``@app.command`` shell in ``doctor.py`` must contain ZERO
    detection/reconciliation/reporting logic -- only ``repo_root`` resolution
    and a single delegated call (T036 binding structural constraint)."""
    import inspect

    source = inspect.getsource(doctor_module.review_cycle_reconcile)
    # The shell may resolve repo_root and call the sibling's entry point --
    # nothing else. It must not itself glob, open, or classify a stranded
    # record.
    assert "glob(" not in source
    assert "review-cycle-*.md" not in source
    assert "CoordinationBranchDeleted" not in source
    assert "run_review_cycle_reconciliation(repo_root" in source
