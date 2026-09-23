"""Seam test for ``specify_cli.merge.forecast`` (mission #2057, WP06).

Locks the ``merge --dry-run`` forecast contract at the seam: the exact JSON key
set (cli-surface-contract.md §2), the REJECTED_REVIEW_ARTIFACT_CONFLICT gate
preview (human + JSON), unresolved-slug / missing-lanes errors, and the
would_assign_mission_number scan. The one-way-import guard (INV-2) lives in
the consolidated ``tests/merge/test_merge_compat_surface.py`` (WP04,
dev-assist-retire-path-hardening-01KXAVR0 / #2565) — ``forecast`` has no
relocated identity symbols of its own, so this file carries no re-export test.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
import typer

from mission_runtime import MissionArtifactKind, MissionTopology, placement_seam
from specify_cli import __version__ as SPEC_KITTY_VERSION
from specify_cli.merge import forecast
from specify_cli.merge.config import MergeStrategy
from specify_cli.post_merge.review_artifact_consistency import (
    REJECTED_REVIEW_ARTIFACT_CONFLICT,
)
from specify_cli.status.models import Lane, ReviewResult
from tests.reliability.fixtures import (
    WorkPackageSpec,
    append_status_event,
    create_mission_fixture,
    write_work_package,
)

pytestmark = pytest.mark.fast


EXPECTED_DRY_RUN_PAYLOAD_KEYS = frozenset(
    {
        "spec_kitty_version",
        "mission_slug",
        "target_branch",
        "strategy",
        "delete_branch",
        "remove_worktree",
        "push",
        "mission_branch",
        "lanes",
        "would_assign_mission_number",
        "retention",
    }
)


def test_unresolved_slug_raises_exit_1(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(typer.Exit) as exc:
        forecast.run_dry_run_forecast(
            repo_root=Path("/r"),
            resolved_feature=None,
            resolved_target_branch="main",
            resolved_strategy=MergeStrategy.SQUASH,
            delete_branch=True,
            remove_worktree=True,
            push=False,
            json_output=True,
        )
    assert exc.value.exit_code == 1
    payload = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert payload["error"] == "Mission slug could not be resolved. Use --mission <slug>."


def _lanes_json_for(mission: object) -> None:
    (mission.mission_dir / "lanes.json").write_text(  # type: ignore[attr-defined]
        json.dumps(
            {
                "version": 1,
                "mission_slug": mission.mission_slug,  # type: ignore[attr-defined]
                "mission_id": mission.mission_id,  # type: ignore[attr-defined]
                "mission_branch": f"kitty/mission-{mission.mission_slug}",  # type: ignore[attr-defined]
                "target_branch": "main",
                "lanes": [
                    {
                        "lane_id": "lane-a",
                        "wp_ids": ["WP01"],
                        "write_scope": [],
                        "predicted_surfaces": [],
                        "depends_on_lanes": [],
                        "parallel_group": 0,
                    }
                ],
                "computed_at": "2026-05-14T12:00:00+00:00",
                "computed_from": "dependency_graph+ownership",
                "planning_artifact_wps": [],
            }
        )
        + "\n",
        encoding="utf-8",
    )


def test_clean_forecast_json_payload_key_set(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    mission = create_mission_fixture(tmp_path)
    write_work_package(mission, WorkPackageSpec(lane="approved"))
    append_status_event(
        mission, from_lane=Lane.FOR_REVIEW, to_lane=Lane.APPROVED,
        event_id="01KVXHDKFORECAST00000001",
    )
    _lanes_json_for(mission)
    monkeypatch.setattr(
        "specify_cli.merge.forecast.get_main_repo_root", lambda _r: mission.repo_root
    )

    # On a clean mission the forecast prints the payload and returns (no Exit).
    forecast.run_dry_run_forecast(
        repo_root=mission.repo_root,
        resolved_feature=mission.mission_slug,
        resolved_target_branch="main",
        resolved_strategy=MergeStrategy.SQUASH,
        delete_branch=True,
        remove_worktree=True,
        push=False,
        json_output=True,
    )
    payload = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert frozenset(payload) == EXPECTED_DRY_RUN_PAYLOAD_KEYS
    assert payload["spec_kitty_version"] == SPEC_KITTY_VERSION
    assert payload["mission_slug"] == mission.mission_slug
    assert payload["strategy"] == "squash"
    assert payload["push"] is False


def test_squash_conflict_forecast_blocks_with_stable_json(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """#4892: dry-run must forecast the real squash content blocker."""
    mission = create_mission_fixture(tmp_path)
    write_work_package(mission, WorkPackageSpec(lane="approved"))
    append_status_event(
        mission,
        from_lane=Lane.FOR_REVIEW,
        to_lane=Lane.APPROVED,
        event_id="01KVXHDKFORECAST489200001",
    )
    _lanes_json_for(mission)
    monkeypatch.setattr(
        "specify_cli.merge.forecast.get_main_repo_root", lambda _r: mission.repo_root
    )
    preview = SimpleNamespace(conflicting_paths=("src/shared.py",))
    monkeypatch.setattr(
        forecast,
        "preview_mission_target_integration",
        lambda *_args, **_kwargs: preview,
        raising=False,
    )

    with pytest.raises(typer.Exit) as exc:
        forecast.run_dry_run_forecast(
            repo_root=mission.repo_root,
            resolved_feature=mission.mission_slug,
            resolved_target_branch="main",
            resolved_strategy=MergeStrategy.SQUASH,
            delete_branch=True,
            remove_worktree=True,
            push=False,
            json_output=True,
        )

    assert exc.value.exit_code == 1
    payload = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert payload == {
        "spec_kitty_version": SPEC_KITTY_VERSION,
        "mission_slug": mission.mission_slug,
        "mission_branch": f"kitty/mission-{mission.mission_slug}",
        "target_branch": "main",
        "blocked": True,
        "diagnostic_code": "TARGET_BRANCH_CONTENT_CONFLICT",
        "conflicting_paths": ["src/shared.py"],
        "remediation": [
            "Update the mission branch against the current target branch.",
            "Resolve the listed conflicts, then rerun `spec-kitty merge --dry-run`.",
        ],
    }


def test_retaining_mission_forecast_reports_resolved_retention(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """FR-008 (#3131): a mission with ``retain_branches``/``retain_worktrees``
    in meta.json and NO explicit CLI flags reports the RESOLVED cleanup
    decision (both False) plus ``retention`` provenance, not raw flag echo.
    """
    mission = create_mission_fixture(tmp_path)
    meta_path = mission.mission_dir / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["retain_branches"] = True
    meta["retain_worktrees"] = True
    meta_path.write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    write_work_package(mission, WorkPackageSpec(lane="approved"))
    append_status_event(
        mission, from_lane=Lane.FOR_REVIEW, to_lane=Lane.APPROVED,
        event_id="01KVXHDKFORECAST00000004",
    )
    _lanes_json_for(mission)
    monkeypatch.setattr(
        "specify_cli.merge.forecast.get_main_repo_root", lambda _r: mission.repo_root
    )

    forecast.run_dry_run_forecast(
        repo_root=mission.repo_root,
        resolved_feature=mission.mission_slug,
        resolved_target_branch="main",
        resolved_strategy=MergeStrategy.SQUASH,
        delete_branch=None,
        remove_worktree=None,
        push=False,
        json_output=True,
    )
    payload = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert frozenset(payload) == EXPECTED_DRY_RUN_PAYLOAD_KEYS
    assert payload["delete_branch"] is False
    assert payload["remove_worktree"] is False
    assert payload["retention"]["branch_source"] == "meta"
    assert payload["retention"]["worktree_source"] == "meta"
    assert payload["retention"]["warnings"]


@pytest.mark.parametrize("topology", list(MissionTopology))
def test_forecast_retention_reads_primary_metadata_surface_across_topologies(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    topology: MissionTopology,
) -> None:
    """#3833: dry-run retention == executor retention, for every topology.

    The forecast must read the retention decision off the mission's
    ``PRIMARY_METADATA`` surface -- the SAME ``placement_seam(...).read_dir``
    derivation the merge executor's retention leg uses -- never off
    ``feature_dir_for_preview`` (the ``WORK_PACKAGE_TASK`` surface, which only
    happens to resolve to the same ``kitty-specs/<slug>/`` dir today). The
    decoy WORK_PACKAGE_TASK dir below (no ``meta.json``) makes the two
    derivations DISAGREE: reading retention off it would report the default
    delete/remove, while the real primary meta (``retain_branches``/
    ``retain_worktrees: true``) retains. Asserts both the resolved decision
    equality with the executor derivation and the exact dir handed to
    ``resolve_merge_retention``.
    """
    mission = create_mission_fixture(tmp_path)
    meta_path = mission.mission_dir / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["retain_branches"] = True
    meta["retain_worktrees"] = True
    meta["topology"] = topology.value
    meta_path.write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    write_work_package(mission, WorkPackageSpec(lane="approved"))
    append_status_event(
        mission, from_lane=Lane.FOR_REVIEW, to_lane=Lane.APPROVED,
        event_id="01KVXHDKFORECAST00000005",
    )
    _lanes_json_for(mission)

    # Decoy WORK_PACKAGE_TASK surface: same mission slug name, NO meta.json —
    # a retention read off this dir resolves (None, None) → default delete.
    decoy_wp_surface = tmp_path / "decoy-wp-surface" / mission.mission_slug
    decoy_wp_surface.mkdir(parents=True)

    real_resolve_artifact_surface = forecast.resolve_artifact_surface

    def _decoy_work_package_surface(repo_root: Path, slug: str, kind: MissionArtifactKind):
        if kind is MissionArtifactKind.WORK_PACKAGE_TASK:
            return SimpleNamespace(path=decoy_wp_surface)
        return real_resolve_artifact_surface(repo_root, slug, kind)

    monkeypatch.setattr(forecast, "resolve_artifact_surface", _decoy_work_package_surface)
    monkeypatch.setattr(
        "specify_cli.merge.forecast.get_main_repo_root", lambda _r: mission.repo_root
    )

    # Spy on the resolver the forecast calls, recording the dir it is handed.
    recorded_dirs: list[Path] = []
    real_resolve_merge_retention = forecast.resolve_merge_retention

    def _recording_resolver(primary_meta_dir: Path, **kwargs: object):
        recorded_dirs.append(primary_meta_dir)
        return real_resolve_merge_retention(primary_meta_dir, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(forecast, "resolve_merge_retention", _recording_resolver)

    forecast.run_dry_run_forecast(
        repo_root=mission.repo_root,
        resolved_feature=mission.mission_slug,
        resolved_target_branch="main",
        resolved_strategy=MergeStrategy.SQUASH,
        delete_branch=None,
        remove_worktree=None,
        push=False,
        json_output=True,
    )
    payload = json.loads(capsys.readouterr().out.strip().splitlines()[-1])

    # Executor-side derivation, exactly as ``_run_lane_based_merge`` performs
    # it (contracts/retention-resolver-contract.md, consumption item 1).
    executor_meta_dir = placement_seam(mission.repo_root, mission.mission_slug).read_dir(
        MissionArtifactKind.PRIMARY_METADATA
    )
    executor_decision = real_resolve_merge_retention(
        executor_meta_dir, explicit_delete_branch=None, explicit_remove_worktree=None
    )

    # The forecast handed the resolver the executor's PRIMARY_METADATA dir,
    # not the WORK_PACKAGE_TASK preview dir.
    assert recorded_dirs == [executor_meta_dir]
    assert executor_meta_dir != decoy_wp_surface

    # Dry-run retention == executor retention, for this topology.
    assert payload["delete_branch"] == executor_decision.delete_branch is False
    assert payload["remove_worktree"] == executor_decision.remove_worktree is False
    assert payload["retention"]["branch_source"] == executor_decision.branch_source == "meta"
    assert payload["retention"]["worktree_source"] == executor_decision.worktree_source == "meta"
    assert payload["retention"]["warnings"] == list(executor_decision.warnings)


def test_review_artifact_conflict_blocks_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """WP06 repoint: ``find_rejected_review_artifact_conflicts`` is pure-event
    post-WP05 (verdict-seam-write-unification-01KZ9Q35, FR-013) -- it no
    longer reads ``review-cycle-N.md`` frontmatter at all. The on-disk
    artifact below is written only as realistic surrounding state; the
    ``review_result`` event on the SAME transition is what the gate
    actually consults.
    """
    from specify_cli.review.artifacts import ReviewCycleArtifact

    mission = create_mission_fixture(tmp_path)
    write_work_package(mission, WorkPackageSpec(lane="approved"))
    append_status_event(
        mission, from_lane=Lane.FOR_REVIEW, to_lane=Lane.APPROVED,
        event_id="01KVXHDKFORECAST00000002",
        review_result=ReviewResult(
            reviewer="reviewer-renata",
            verdict="changes_requested",
            reference=f"review-cycle://{mission.mission_slug}/WP01-regression-harness/review-cycle-1.md",
        ),
    )
    artifact = ReviewCycleArtifact(
        cycle_number=1, wp_id="WP01", mission_slug=mission.mission_slug,
        reviewer_agent="reviewer-renata",
        reviewed_at="2026-05-14T12:00:00+00:00", body="# Review\n\nVerdict: rejected\n",
    )
    artifact.write(mission.tasks_dir / "WP01-regression-harness" / "review-cycle-1.md")
    _lanes_json_for(mission)
    monkeypatch.setattr(
        "specify_cli.merge.forecast.get_main_repo_root", lambda _r: mission.repo_root
    )

    with pytest.raises(typer.Exit) as exc:
        forecast.run_dry_run_forecast(
            repo_root=mission.repo_root,
            resolved_feature=mission.mission_slug,
            resolved_target_branch="main",
            resolved_strategy=MergeStrategy.SQUASH,
            delete_branch=True,
            remove_worktree=True,
            push=False,
            json_output=True,
        )
    assert exc.value.exit_code == 1
    payload = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert payload["blocked"] is True
    assert payload["diagnostic_code"] == REJECTED_REVIEW_ARTIFACT_CONFLICT


def test_missing_lanes_raises_exit_1(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    mission = create_mission_fixture(tmp_path)
    monkeypatch.setattr(
        "specify_cli.merge.forecast.get_main_repo_root", lambda _r: mission.repo_root
    )
    with pytest.raises(typer.Exit) as exc:
        forecast.run_dry_run_forecast(
            repo_root=mission.repo_root,
            resolved_feature=mission.mission_slug,
            resolved_target_branch="main",
            resolved_strategy=MergeStrategy.SQUASH,
            delete_branch=True,
            remove_worktree=True,
            push=False,
            json_output=True,
        )
    assert exc.value.exit_code == 1
    payload = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert "lanes.json is required" in payload["error"]


def test_scan_would_assign_mission_number_handles_failure(tmp_path: Path) -> None:
    with (
        patch.object(forecast, "needs_number_assignment", return_value=True),
        patch.object(forecast, "assign_next_mission_number", side_effect=RuntimeError("boom")),
        patch.object(forecast, "get_main_repo_root", lambda _r: tmp_path),
    ):
        assert forecast._scan_would_assign_mission_number(tmp_path, tmp_path) is None

    with patch.object(forecast, "needs_number_assignment", return_value=False):
        assert forecast._scan_would_assign_mission_number(tmp_path, tmp_path) is None


def test_scan_would_assign_mission_number_returns_value(tmp_path: Path) -> None:
    with (
        patch.object(forecast, "needs_number_assignment", return_value=True),
        patch.object(forecast, "assign_next_mission_number", return_value=7),
        patch.object(forecast, "get_main_repo_root", lambda _r: tmp_path),
    ):
        assert forecast._scan_would_assign_mission_number(tmp_path, tmp_path) == 7


# --- human-output (non-JSON) branches: NFR-002 coverage of console paths -----


def test_emit_dry_run_error_human_channel(capsys: pytest.CaptureFixture[str]) -> None:
    forecast._emit_dry_run_error(error_msg="boom happened", json_output=False)
    out = capsys.readouterr().out
    assert "Error:" in out
    assert "boom happened" in out


def test_unresolved_slug_human_channel_prints_error(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(typer.Exit) as exc:
        forecast.run_dry_run_forecast(
            repo_root=Path("/r"),
            resolved_feature=None,
            resolved_target_branch="main",
            resolved_strategy=MergeStrategy.SQUASH,
            delete_branch=True,
            remove_worktree=True,
            push=False,
            json_output=False,
        )
    assert exc.value.exit_code == 1
    out = capsys.readouterr().out
    assert "Mission slug could not be resolved" in out


def test_review_artifact_block_human_channel(capsys: pytest.CaptureFixture[str]) -> None:
    """Drive the human-output review-artifact gate printing (lines 84-108)."""
    from specify_cli.post_merge.review_artifact_consistency import (
        RejectedReviewArtifactFinding,
        ReviewArtifactPreflightResult,
    )

    finding = RejectedReviewArtifactFinding(
        wp_id="WP01",
        lane="approved",
        artifact_path=Path("/repo/kitty-specs/m/tasks/WP01/review-cycle-1.md"),
        cycle_number=1,
        verdict="rejected",
    )
    preflight = ReviewArtifactPreflightResult(findings=(finding,))

    forecast._emit_review_artifact_block(
        preflight,
        main_repo_for_diag=Path("/repo"),
        resolved_feature="m",
        resolved_target_branch="main",
        json_output=False,
    )
    out = capsys.readouterr().out
    assert "Review artifact consistency gate failed" in out
    assert "diagnostic_code:" in out
    assert "latest_review_cycle_verdict:" in out
    assert "Mission: m" in out


def test_clean_forecast_human_channel_prints_would_assign(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Human-output clean forecast with a would-assign number (line 201 + 207)."""
    mission = create_mission_fixture(tmp_path)
    write_work_package(mission, WorkPackageSpec(lane="approved"))
    append_status_event(
        mission, from_lane=Lane.FOR_REVIEW, to_lane=Lane.APPROVED,
        event_id="01KVXHDKFORECAST00000003",
    )
    _lanes_json_for(mission)
    monkeypatch.setattr(
        "specify_cli.merge.forecast.get_main_repo_root", lambda _r: mission.repo_root
    )
    with patch.object(forecast, "_scan_would_assign_mission_number", return_value=42):
        forecast.run_dry_run_forecast(
            repo_root=mission.repo_root,
            resolved_feature=mission.mission_slug,
            resolved_target_branch="main",
            resolved_strategy=MergeStrategy.SQUASH,
            delete_branch=True,
            remove_worktree=True,
            push=False,
            json_output=False,
        )
    out = capsys.readouterr().out
    assert "would assign" in out
    assert "mission_number=42" in out


def test_squash_conflict_forecast_human_channel(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """#4892: the human (non-JSON) rendering of the target-content conflict.

    Covers the console branch of ``_emit_target_content_conflict`` (the JSON
    branch is covered by ``test_squash_conflict_forecast_blocks_with_stable_json``).
    """
    mission = create_mission_fixture(tmp_path)
    write_work_package(mission, WorkPackageSpec(lane="approved"))
    append_status_event(
        mission,
        from_lane=Lane.FOR_REVIEW,
        to_lane=Lane.APPROVED,
        event_id="01KVXHDKFORECAST489200002",
    )
    _lanes_json_for(mission)
    monkeypatch.setattr(
        "specify_cli.merge.forecast.get_main_repo_root", lambda _r: mission.repo_root
    )
    preview = SimpleNamespace(conflicting_paths=("src/shared.py",))
    monkeypatch.setattr(
        forecast,
        "preview_mission_target_integration",
        lambda *_args, **_kwargs: preview,
        raising=False,
    )

    with pytest.raises(typer.Exit) as exc:
        forecast.run_dry_run_forecast(
            repo_root=mission.repo_root,
            resolved_feature=mission.mission_slug,
            resolved_target_branch="main",
            resolved_strategy=MergeStrategy.SQUASH,
            delete_branch=True,
            remove_worktree=True,
            push=False,
            json_output=False,
        )
    assert exc.value.exit_code == 1
    out = capsys.readouterr().out
    assert "would conflict with" in out
    assert "diagnostic_code: TARGET_BRANCH_CONTENT_CONFLICT" in out
    assert "conflicting_path: src/shared.py" in out
    assert "remediation:" in out


def test_preview_runtime_error_routes_through_dry_run_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A non-conflict preview failure must not crash --dry-run with a traceback.

    #4892 review: an unrelated-histories / worktree-add failure raises a plain
    ``RuntimeError`` from the preview. It must be routed through
    ``_emit_dry_run_error`` so ``--json`` output stays valid JSON and the path
    exits 1, rather than surfacing a traceback that corrupts the JSON stream.
    """
    mission = create_mission_fixture(tmp_path)
    write_work_package(mission, WorkPackageSpec(lane="approved"))
    append_status_event(
        mission,
        from_lane=Lane.FOR_REVIEW,
        to_lane=Lane.APPROVED,
        event_id="01KVXHDKFORECAST489200003",
    )
    _lanes_json_for(mission)
    monkeypatch.setattr(
        "specify_cli.merge.forecast.get_main_repo_root", lambda _r: mission.repo_root
    )

    def _boom(*_args: object, **_kwargs: object) -> object:
        raise RuntimeError("Failed to create merge preview worktree: fatal: ...")

    monkeypatch.setattr(
        forecast, "preview_mission_target_integration", _boom, raising=False
    )

    with pytest.raises(typer.Exit) as exc:
        forecast.run_dry_run_forecast(
            repo_root=mission.repo_root,
            resolved_feature=mission.mission_slug,
            resolved_target_branch="main",
            resolved_strategy=MergeStrategy.SQUASH,
            delete_branch=True,
            remove_worktree=True,
            push=False,
            json_output=True,
        )
    assert exc.value.exit_code == 1
    # --json output must remain valid JSON, carrying the error — never a traceback.
    payload = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert "Failed to create merge preview worktree" in payload["error"]
