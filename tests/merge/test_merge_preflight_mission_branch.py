"""Regression tests for merge mission branch preflight -- FR-016 through FR-019."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
import typer

import specify_cli.cli.commands.merge as merge_mod
from specify_cli.cli.commands.merge import (
    _check_mission_branch,
    _load_merge_state_for_mission,
    _load_or_create_merge_state,
)
from specify_cli.merge.state import MergeState, get_state_path, load_state, save_state
from specify_cli.merge.workspace import get_merge_workspace_path

pytestmark = pytest.mark.fast


MISSION_SLUG = "stable-320-release-blocker-cleanup-01KQW4DF"


def _blocker(slug: str = MISSION_SLUG) -> dict[str, str | bool]:
    expected_branch = f"kitty/mission-{slug}"
    return {
        "ready": False,
        "blocker": "missing_mission_branch",
        "expected_branch": expected_branch,
        "remediation": f"git branch {expected_branch} abc1234def56",
    }


def _manifest(slug: str = MISSION_SLUG) -> SimpleNamespace:
    lane = SimpleNamespace(
        lane_id="lane-d",
        wp_ids=["WP04"],
        to_dict=lambda: {"lane_id": "lane-d", "wp_ids": ["WP04"]},
    )
    return SimpleNamespace(
        mission_branch=f"kitty/mission-{slug}",
        target_branch="main",
        lanes=[lane],
    )


def _compact_output(output: str) -> str:
    return " ".join(output.split())


def _prepare_dry_run(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *,
    branch_ok: bool,
) -> None:
    monkeypatch.setattr(merge_mod, "show_banner", lambda: None)
    monkeypatch.setattr(merge_mod, "find_repo_root", lambda: tmp_path)
    monkeypatch.setattr(merge_mod, "get_main_repo_root", lambda repo_root: repo_root)
    monkeypatch.setattr(merge_mod, "_enforce_git_preflight", lambda *_args, **_kwargs: None)
    # WP04 (mission-handle-resolution FR-004/FR-005): the fresh not-found gate now
    # probes the mission dir on disk. This dry-run harness mocks the mission's
    # collaborators instead of materializing its ``kitty-specs/`` dir, so neutralize
    # the existence probe alongside the other seams it stubs.
    monkeypatch.setattr(merge_mod, "_resolved_mission_dir_exists", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(merge_mod, "_resolve_target_branch", lambda *_args, **_kwargs: ("main", "flag"))
    monkeypatch.setattr(merge_mod, "_validate_target_branch", lambda *_args, **_kwargs: None)
    # WP06 (#2057): the dry-run preview now runs in the ``forecast`` seam, so the
    # collaborators it consumes must be patched there (the shim no longer binds
    # ``require_lanes_json`` — it moved with the executor/forecast seams).
    monkeypatch.setattr(
        "specify_cli.merge.forecast.get_main_repo_root", lambda repo_root: repo_root
    )
    monkeypatch.setattr(
        "specify_cli.merge.forecast.require_lanes_json", lambda _feature_dir: _manifest()
    )
    monkeypatch.setattr(
        merge_mod,
        "_enforce_target_branch_sync_preflight",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        merge_mod,
        "_check_mission_branch",
        lambda _mission_slug, _repo_root, **_kwargs: (
            branch_ok,
            None if branch_ok else _blocker(),
        ),
    )


def _invoke_merge_dry_run(*, json_output: bool) -> None:
    command = merge_mod.merge.__wrapped__
    command(
        strategy=None,
        delete_branch=True,
        remove_worktree=True,
        push=False,
        target_branch=None,
        dry_run=True,
        json_output=json_output,
        mission=MISSION_SLUG,
        resume=False,
        abort=False,
        context_token=None,
        keep_workspace=False,
        allow_sparse_checkout=False,
        yes=False,
        skip_review_artifact_check=False,
        note=None,
    )


class TestCheckMissionBranch:
    # Modern slug (no NNN- prefix, no embedded mid8) + a declared mission_id:
    # the #1978 seam resolves the canonical <human-slug>-<mid8> branch. The
    # bare slug here ("my-mission") would, with NO mission_id, correctly
    # fail-closed (BranchIdentityUnresolved); these tests assert the resolvable
    # path so the branch-exists / branch-missing-payload intent still has a
    # concrete expected_branch to check against.
    _RESOLVABLE_ID = "01KQTESTBRANCH00000000000A"
    _RESOLVED_BRANCH = "kitty/mission-my-mission-01KQTEST"

    def test_branch_exists_returns_true(self, tmp_path: Path) -> None:
        with patch(
            "specify_cli.merge.preflight._has_branch_ref",
            return_value=True,
        ):
            exists, blocker = _check_mission_branch(
                "my-mission", tmp_path, mission_id=self._RESOLVABLE_ID
            )

        assert exists is True
        assert blocker is None

    def test_branch_missing_returns_false_with_payload(self, tmp_path: Path) -> None:
        with patch(
            "specify_cli.merge.preflight._has_branch_ref",
            return_value=False,
        ), patch(
            "specify_cli.merge.preflight.run_command",
            return_value=(0, "abc1234def5678\n", ""),
        ):
            exists, blocker = _check_mission_branch(
                "my-mission", tmp_path, mission_id=self._RESOLVABLE_ID
            )

        assert exists is False
        assert blocker is not None
        assert blocker["ready"] is False
        assert blocker["blocker"] == "missing_mission_branch"
        assert blocker["expected_branch"] == self._RESOLVED_BRANCH
        assert blocker["remediation"] == f"git branch {self._RESOLVED_BRANCH} abc1234def56"

    def test_branch_missing_fail_closed_for_unresolvable_modern_slug(
        self, tmp_path: Path
    ) -> None:
        """No mission_id + modern slug (no NNN-, no mid8) -> #1978 fail-closed."""
        from specify_cli.lanes.branch_naming import BranchIdentityUnresolved

        with patch(
            "specify_cli.merge.preflight._has_branch_ref",
            return_value=False,
        ), pytest.raises(BranchIdentityUnresolved):
            _check_mission_branch("my-mission", tmp_path)

    def test_branch_missing_uses_manifest_branch_when_supplied(self, tmp_path: Path) -> None:
        manifest_branch = "kitty/mission-my-mission-01KQ-01KQTEST"
        with patch(
            "specify_cli.merge.preflight._has_branch_ref",
            return_value=False,
        ), patch(
            "specify_cli.merge.preflight.run_command",
            return_value=(0, "abc1234def5678\n", ""),
        ):
            exists, blocker = _check_mission_branch(
                "my-mission-01KQ",
                tmp_path,
                expected_branch=manifest_branch,
            )

        assert exists is False
        assert blocker is not None
        assert blocker["expected_branch"] == manifest_branch
        assert blocker["remediation"] == f"git branch {manifest_branch} abc1234def56"


class TestMergeDryRunMissingBranch:
    """Integration tests for merge --dry-run with missing mission branch."""

    def test_resume_loads_ulid_keyed_state_when_invoked_with_slug(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """--resume canonicalizes slug handles to mission_id before load_state."""
        mission_slug = "resume-state-key-regression-01KV4X00"
        mission_id = "01KV4X00ULIDKEYEDSTATE0000"
        feature_dir = tmp_path / "kitty-specs" / mission_slug
        feature_dir.mkdir(parents=True)
        (feature_dir / "meta.json").write_text(
            json.dumps(
                {
                    "mission_id": mission_id,
                    "mission_slug": mission_slug,
                    "slug": mission_slug,
                    "target_branch": "main",
                }
            ),
            encoding="utf-8",
        )
        save_state(
            MergeState(
                mission_id=mission_id,
                mission_slug=mission_slug,
                target_branch="main",
                wp_order=["WP01", "WP02"],
                completed_wps=["WP01"],
            ),
            tmp_path,
        )

        class StopAfterResume(Exception):
            pass

        monkeypatch.setattr(merge_mod, "show_banner", lambda: None)
        monkeypatch.setattr(merge_mod, "find_repo_root", lambda: tmp_path)
        monkeypatch.setattr(merge_mod, "get_main_repo_root", lambda repo_root: repo_root)
        monkeypatch.setattr(
            merge_mod,
            "_enforce_git_preflight",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(StopAfterResume()),
        )

        command = merge_mod.merge.__wrapped__
        with pytest.raises(StopAfterResume):
            command(
                strategy=None,
                delete_branch=True,
                remove_worktree=True,
                push=False,
                target_branch=None,
                dry_run=False,
                json_output=False,
                mission=mission_slug,
                        resume=True,
                abort=False,
                context_token=None,
                keep_workspace=False,
                allow_sparse_checkout=False,
                yes=False,
                skip_review_artifact_check=False,
                note=None,
            )

        output = _compact_output(capsys.readouterr().out)
        assert f"Resume requested for {mission_slug} (1/2 done)" in output

    def test_resume_falls_back_to_legacy_slug_keyed_state_when_meta_has_ulid(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """--resume remains compatible with pre-ULID slug-keyed state files."""
        mission_slug = "legacy-state-key-regression-01KV4X10"
        mission_id = "01KV4X10ULIDKEYEDSTATE0000"
        feature_dir = tmp_path / "kitty-specs" / mission_slug
        feature_dir.mkdir(parents=True)
        (feature_dir / "meta.json").write_text(
            json.dumps(
                {
                    "mission_id": mission_id,
                    "mission_slug": mission_slug,
                    "slug": mission_slug,
                    "target_branch": "main",
                }
            ),
            encoding="utf-8",
        )
        save_state(
            MergeState(
                mission_id=mission_slug,
                mission_slug=mission_slug,
                target_branch="main",
                wp_order=["WP01", "WP02"],
                completed_wps=["WP01"],
            ),
            tmp_path,
        )

        class StopAfterResume(Exception):
            pass

        monkeypatch.setattr(merge_mod, "show_banner", lambda: None)
        monkeypatch.setattr(merge_mod, "find_repo_root", lambda: tmp_path)
        monkeypatch.setattr(merge_mod, "get_main_repo_root", lambda repo_root: repo_root)
        monkeypatch.setattr(
            merge_mod,
            "_enforce_git_preflight",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(StopAfterResume()),
        )

        command = merge_mod.merge.__wrapped__
        with pytest.raises(StopAfterResume):
            command(
                strategy=None,
                delete_branch=True,
                remove_worktree=True,
                push=False,
                target_branch=None,
                dry_run=False,
                json_output=False,
                mission=mission_slug,
                        resume=True,
                abort=False,
                context_token=None,
                keep_workspace=False,
                allow_sparse_checkout=False,
                yes=False,
                skip_review_artifact_check=False,
                note=None,
            )

        output = _compact_output(capsys.readouterr().out)
        assert f"Resume requested for {mission_slug} (1/2 done)" in output

    def test_resume_without_handle_adopts_unambiguous_state_slug(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """--resume with one active state must use that state's mission_slug."""
        mission_slug = "resume-adoption-01KV51B0"
        mission_id = "01KV51B0ULIDKEYEDSTATE0000"
        save_state(
            MergeState(
                mission_id=mission_id,
                mission_slug=mission_slug,
                target_branch="main",
                wp_order=["WP01"],
            ),
            tmp_path,
        )

        run_merge = Mock()
        monkeypatch.setattr(merge_mod, "show_banner", lambda: None)
        monkeypatch.setattr(merge_mod, "find_repo_root", lambda: tmp_path)
        monkeypatch.setattr(merge_mod, "get_main_repo_root", lambda repo_root: repo_root)
        monkeypatch.setattr(merge_mod, "_enforce_git_preflight", lambda *_args, **_kwargs: None)
        monkeypatch.setattr(merge_mod, "_resolve_target_branch", lambda *_args, **_kwargs: ("main", "flag"))
        monkeypatch.setattr(merge_mod, "_validate_target_branch", lambda *_args, **_kwargs: None)
        monkeypatch.setattr(merge_mod, "_run_lane_based_merge", run_merge)
        monkeypatch.setattr(merge_mod, "run_retrospective_postcondition", lambda *_args, **_kwargs: None)

        command = merge_mod.merge.__wrapped__
        command(
            strategy=None,
            delete_branch=True,
            remove_worktree=True,
            push=False,
            target_branch=None,
            dry_run=False,
            json_output=False,
            mission=None,
                resume=True,
            abort=False,
            context_token=None,
            keep_workspace=False,
            allow_sparse_checkout=False,
            yes=False,
            skip_review_artifact_check=False,
            note=None,
        )

        run_merge.assert_called_once()
        assert run_merge.call_args.kwargs["mission_slug"] == mission_slug
        output = _compact_output(capsys.readouterr().out)
        assert f"Resume requested for {mission_slug} (0/1 done)" in output

    def test_abort_clears_legacy_slug_keyed_state_when_meta_has_ulid(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """--abort clears legacy slug-keyed state even after ULID identity resolves."""
        mission_slug = "abort-state-key-regression-01KV4X20"
        mission_id = "01KV4X20ULIDKEYEDSTATE0000"
        feature_dir = tmp_path / "kitty-specs" / mission_slug
        feature_dir.mkdir(parents=True)
        (feature_dir / "meta.json").write_text(
            json.dumps(
                {
                    "mission_id": mission_id,
                    "mission_slug": mission_slug,
                    "slug": mission_slug,
                    "target_branch": "main",
                }
            ),
            encoding="utf-8",
        )
        save_state(
            MergeState(
                mission_id=mission_slug,
                mission_slug=mission_slug,
                target_branch="main",
                wp_order=["WP01"],
            ),
            tmp_path,
        )

        monkeypatch.setattr(merge_mod, "show_banner", lambda: None)
        monkeypatch.setattr(merge_mod, "find_repo_root", lambda: tmp_path)
        monkeypatch.setattr(merge_mod, "get_main_repo_root", lambda repo_root: repo_root)
        # WP04/WP10 (#2057): --abort cleans workspaces via the resolve seam's
        # _cleanup_merge_workspaces_for_state -> cleanup_merge_workspace binding.
        monkeypatch.setattr("specify_cli.merge.resolve.cleanup_merge_workspace", Mock())
        monkeypatch.setattr(merge_mod, "abort_git_merge", lambda _repo_root: False)

        command = merge_mod.merge.__wrapped__
        command(
            strategy=None,
            delete_branch=True,
            remove_worktree=True,
            push=False,
            target_branch=None,
            dry_run=False,
            json_output=False,
            mission=mission_slug,
                resume=False,
            abort=True,
            context_token=None,
            keep_workspace=False,
            allow_sparse_checkout=False,
            yes=False,
            skip_review_artifact_check=False,
            note=None,
        )

        assert load_state(tmp_path, mission_slug) is None
        assert not get_state_path(tmp_path, mission_slug).exists()
        output = _compact_output(capsys.readouterr().out)
        assert f"Aborted merge for {mission_slug}" in output

    def test_abort_without_handle_cleans_unambiguous_state_workspace(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """--abort with one active state must clean that mission's workspace."""
        mission_slug = "abort-adoption-01KV51B1"
        mission_id = "01KV51B1ULIDKEYEDSTATE0000"
        save_state(
            MergeState(
                mission_id=mission_id,
                mission_slug=mission_slug,
                target_branch="main",
                wp_order=["WP01"],
            ),
            tmp_path,
        )
        workspace_path = get_merge_workspace_path(mission_id, tmp_path)
        (workspace_path / "scratch").mkdir(parents=True)

        monkeypatch.setattr(merge_mod, "show_banner", lambda: None)
        monkeypatch.setattr(merge_mod, "find_repo_root", lambda: tmp_path)
        monkeypatch.setattr(merge_mod, "get_main_repo_root", lambda repo_root: repo_root)
        monkeypatch.setattr(merge_mod, "_resolve_mission_slug", lambda *_args, **_kwargs: None)
        monkeypatch.setattr(merge_mod, "abort_git_merge", lambda _repo_root: False)

        command = merge_mod.merge.__wrapped__
        command(
            strategy=None,
            delete_branch=True,
            remove_worktree=True,
            push=False,
            target_branch=None,
            dry_run=False,
            json_output=False,
            mission=None,
                resume=False,
            abort=True,
            context_token=None,
            keep_workspace=False,
            allow_sparse_checkout=False,
            yes=False,
            skip_review_artifact_check=False,
            note=None,
        )

        assert load_state(tmp_path, mission_id) is None
        assert not workspace_path.exists()
        output = _compact_output(capsys.readouterr().out)
        assert f"Aborted merge for {mission_slug}" in output

    def test_abort_with_slug_cleans_canonical_mission_id_workspace(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """--abort --mission <slug> must clean runtime workspace keyed by ULID."""
        mission_slug = "abort-canonical-workspace-01KV51B2"
        mission_id = "01KV51B2ULIDKEYEDSTATE0000"
        feature_dir = tmp_path / "kitty-specs" / mission_slug
        feature_dir.mkdir(parents=True)
        (feature_dir / "meta.json").write_text(
            json.dumps(
                {
                    "mission_id": mission_id,
                    "mission_slug": mission_slug,
                    "slug": mission_slug,
                    "target_branch": "main",
                }
            ),
            encoding="utf-8",
        )
        save_state(
            MergeState(
                mission_id=mission_id,
                mission_slug=mission_slug,
                target_branch="main",
                wp_order=["WP01"],
            ),
            tmp_path,
        )
        workspace_path = get_merge_workspace_path(mission_id, tmp_path)
        (workspace_path / "scratch").mkdir(parents=True)

        monkeypatch.setattr(merge_mod, "show_banner", lambda: None)
        monkeypatch.setattr(merge_mod, "find_repo_root", lambda: tmp_path)
        monkeypatch.setattr(merge_mod, "get_main_repo_root", lambda repo_root: repo_root)
        monkeypatch.setattr(merge_mod, "abort_git_merge", lambda _repo_root: False)

        command = merge_mod.merge.__wrapped__
        command(
            strategy=None,
            delete_branch=True,
            remove_worktree=True,
            push=False,
            target_branch=None,
            dry_run=False,
            json_output=False,
            mission=mission_slug,
                resume=False,
            abort=True,
            context_token=None,
            keep_workspace=False,
            allow_sparse_checkout=False,
            yes=False,
            skip_review_artifact_check=False,
            note=None,
        )

        assert load_state(tmp_path, mission_id) is None
        assert not workspace_path.exists()

    def test_resume_state_lookup_scans_by_slug_when_metadata_is_corrupt(
        self,
        tmp_path: Path,
    ) -> None:
        """Metadata failures do not hide a valid ULID-keyed state for the slug."""
        mission_slug = "corrupt-meta-state-key-regression-01KV4X30"
        mission_id = "01KV4X30ULIDKEYEDSTATE0000"
        feature_dir = tmp_path / "kitty-specs" / mission_slug
        feature_dir.mkdir(parents=True)
        (feature_dir / "meta.json").write_text("{not-json", encoding="utf-8")
        save_state(
            MergeState(
                mission_id=mission_id,
                mission_slug=mission_slug,
                target_branch="main",
                wp_order=["WP01"],
            ),
            tmp_path,
        )

        state = _load_merge_state_for_mission(tmp_path, mission_slug)

        assert state is not None
        assert state.mission_id == mission_id

    def test_inner_merge_adopts_legacy_slug_keyed_state_for_canonical_id(
        self,
        tmp_path: Path,
    ) -> None:
        """Locked merge must not restart after outer --resume finds legacy state."""
        mission_slug = "inner-legacy-state-key-regression-01KV4X40"
        mission_id = "01KV4X40ULIDKEYEDSTATE0000"
        feature_dir = tmp_path / "kitty-specs" / mission_slug
        feature_dir.mkdir(parents=True)
        (feature_dir / "meta.json").write_text(
            json.dumps(
                {
                    "mission_id": mission_id,
                    "mission_slug": mission_slug,
                    "slug": mission_slug,
                    "target_branch": "main",
                }
            ),
            encoding="utf-8",
        )
        save_state(
            MergeState(
                mission_id=mission_slug,
                mission_slug=mission_slug,
                target_branch="main",
                wp_order=["WP01", "WP02"],
                completed_wps=["WP01"],
            ),
            tmp_path,
        )

        state, is_resume = _load_or_create_merge_state(
            main_repo=tmp_path,
            mission_slug=mission_slug,
            canonical_id=mission_id,
            target_branch="main",
            wp_order=["WP01", "WP02"],
            push_requested=False,
        )

        assert is_resume is True
        assert state.mission_id == mission_id
        assert state.completed_wps == ["WP01"]
        assert load_state(tmp_path, mission_id) is not None
        assert load_state(tmp_path, mission_slug) is None

    def test_dry_run_json_missing_branch_still_previews(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """merge --dry-run --json does not require a local mission branch."""
        _prepare_dry_run(monkeypatch, tmp_path, branch_ok=False)
        monkeypatch.setattr("specify_cli.merge.forecast.needs_number_assignment", lambda _feature_dir: False)

        _invoke_merge_dry_run(json_output=True)

        payload = json.loads(capsys.readouterr().out)
        assert payload["mission_slug"] == MISSION_SLUG
        assert payload["mission_branch"] == f"kitty/mission-{MISSION_SLUG}"
        assert payload["target_branch"] == "main"
        assert payload["would_assign_mission_number"] is None

    def test_dry_run_human_missing_branch_still_previews(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """merge --dry-run (no --json) still emits the preview payload."""
        _prepare_dry_run(monkeypatch, tmp_path, branch_ok=False)
        monkeypatch.setattr("specify_cli.merge.forecast.needs_number_assignment", lambda _feature_dir: False)

        _invoke_merge_dry_run(json_output=False)

        payload = json.loads(capsys.readouterr().out)
        assert payload["mission_slug"] == MISSION_SLUG
        assert payload["mission_branch"] == f"kitty/mission-{MISSION_SLUG}"
        assert payload["target_branch"] == "main"
        assert payload["would_assign_mission_number"] is None

    def test_real_merge_blocked_missing_branch(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Real merge is blocked before irreversible git operations."""
        monkeypatch.setattr("specify_cli.merge.executor.get_main_repo_root", lambda repo_root: repo_root)
        monkeypatch.setattr("specify_cli.merge.executor.require_no_sparse_checkout", lambda *_args, **_kwargs: None)
        monkeypatch.setattr("specify_cli.merge.executor.require_lanes_json", lambda _feature_dir: _manifest())
        # WP10 (#2057): the wrapper reads these collaborators from the executor seam.
        monkeypatch.setattr(
            "specify_cli.merge.executor._enforce_target_branch_sync_preflight",
            lambda *_args, **_kwargs: None,
        )
        monkeypatch.setattr(
            "specify_cli.merge.executor._check_mission_branch",
            lambda _mission_slug, _repo_root, **_kwargs: (False, _blocker()),
        )
        acquire_lock = Mock(return_value=True)
        monkeypatch.setattr("specify_cli.merge.executor.acquire_merge_lock", acquire_lock)

        with pytest.raises(typer.Exit) as exc_info:
            merge_mod._run_lane_based_merge(
                repo_root=tmp_path,
                mission_slug=MISSION_SLUG,
                push=False,
                delete_branch=True,
                remove_worktree=True,
            )

        assert exc_info.value.exit_code == 1
        acquire_lock.assert_not_called()
        output = _compact_output(capsys.readouterr().out)
        assert f"Missing mission branch: kitty/mission-{MISSION_SLUG}" in output
        assert f"git branch kitty/mission-{MISSION_SLUG} abc1234def56" in output

    def test_resume_preserves_original_push_request_for_preflight(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Retrying an interrupted --push merge must still run push preflight."""
        state = SimpleNamespace(push_requested=True)
        preflight_calls: list[dict[str, object]] = []

        monkeypatch.setattr("specify_cli.merge.executor.get_main_repo_root", lambda repo_root: repo_root)
        monkeypatch.setattr("specify_cli.merge.executor._resolve_merge_actor", lambda _repo_root: "tester")
        monkeypatch.setattr("specify_cli.merge.executor.require_no_sparse_checkout", lambda *_args, **_kwargs: None)
        monkeypatch.setattr("specify_cli.merge.executor.require_lanes_json", lambda _feature_dir: _manifest())
        monkeypatch.setattr(
            "specify_cli.merge.executor.resolve_mission_identity",
            lambda _feature_dir: SimpleNamespace(mission_id="01TESTPUSHREQUESTED"),
        )
        monkeypatch.setattr(merge_mod, "load_state", lambda _repo_root, _mission_id=None: state)
        # WP05 (#2057): _effective_push_requested now reads load_state from
        # the preflight seam, so patch it there too.
        monkeypatch.setattr(
            "specify_cli.merge.preflight.load_state",
            lambda _repo_root, _mission_id=None: state,
        )

        def fail_preflight(*_args: object, **kwargs: object) -> None:
            preflight_calls.append(kwargs)
            raise typer.Exit(1)

        monkeypatch.setattr("specify_cli.merge.executor._enforce_target_branch_sync_preflight", fail_preflight)
        acquire_lock = Mock(return_value=True)
        monkeypatch.setattr("specify_cli.merge.executor.acquire_merge_lock", acquire_lock)

        with pytest.raises(typer.Exit):
            merge_mod._run_lane_based_merge(
                repo_root=tmp_path,
                mission_slug=MISSION_SLUG,
                push=False,
                delete_branch=True,
                remove_worktree=True,
            )

        assert preflight_calls == [
            {
                "target_branch": "main",
                "mission_slug": MISSION_SLUG,
                "mission_branch": f"kitty/mission-{MISSION_SLUG}",
                # #1978: mission_id is now threaded through to the preflight so
                # remediation composes the canonical <slug>-<mid8> branch via
                # the fail-closed seam instead of a bare kitty/mission-<slug>.
                "mission_id": "01TESTPUSHREQUESTED",
            }
        ]
        acquire_lock.assert_not_called()

    def test_resume_preserves_original_no_push_request(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Retrying an interrupted local-only merge must not add --push."""
        state = SimpleNamespace(push_requested=False)
        preflight = Mock()

        monkeypatch.setattr("specify_cli.merge.executor.get_main_repo_root", lambda repo_root: repo_root)
        monkeypatch.setattr("specify_cli.merge.executor._resolve_merge_actor", lambda _repo_root: "tester")
        monkeypatch.setattr("specify_cli.merge.executor.require_no_sparse_checkout", lambda *_args, **_kwargs: None)
        monkeypatch.setattr("specify_cli.merge.executor.require_lanes_json", lambda _feature_dir: _manifest())
        monkeypatch.setattr(
            "specify_cli.merge.executor.resolve_mission_identity",
            lambda _feature_dir: SimpleNamespace(mission_id="01TESTNOPUSHREQUEST"),
        )
        monkeypatch.setattr(merge_mod, "load_state", lambda _repo_root, _mission_id=None: state)
        # WP05 (#2057): _effective_push_requested now reads load_state from
        # the preflight seam, so patch it there too.
        monkeypatch.setattr(
            "specify_cli.merge.preflight.load_state",
            lambda _repo_root, _mission_id=None: state,
        )
        monkeypatch.setattr("specify_cli.merge.executor._enforce_target_branch_sync_preflight", preflight)
        monkeypatch.setattr(
            merge_mod,
            "_check_mission_branch",
            lambda _mission_slug, _repo_root, **_kwargs: (False, _blocker()),
        )

        with pytest.raises(typer.Exit):
            merge_mod._run_lane_based_merge(
                repo_root=tmp_path,
                mission_slug=MISSION_SLUG,
                push=True,
                delete_branch=True,
                remove_worktree=True,
            )

        preflight.assert_not_called()


class TestMergeDryRunHappyPath:
    def test_dry_run_ready_with_branch_present(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Existing happy-path preflight behavior is unaffected."""
        _prepare_dry_run(monkeypatch, tmp_path, branch_ok=True)
        monkeypatch.setattr(
            "specify_cli.merge.forecast.needs_number_assignment", lambda _feature_dir: False
        )

        _invoke_merge_dry_run(json_output=True)

        payload = json.loads(capsys.readouterr().out)
        assert payload["mission_slug"] == MISSION_SLUG
        assert payload["mission_branch"] == f"kitty/mission-{MISSION_SLUG}"
        assert payload["target_branch"] == "main"
        assert payload["lanes"] == [{"lane_id": "lane-d", "wp_ids": ["WP04"]}]
        assert payload["would_assign_mission_number"] is None
