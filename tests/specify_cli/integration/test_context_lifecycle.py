"""E2E integration test: full WP lifecycle with context tokens (T070).

Verifies SC-001: agent completes full lifecycle using only --context <token>.
No heuristic detection is triggered at any point.

Covers:
- Context resolution from explicit --wp and --feature args
- Token persistence and round-trip load
- resolve_or_load: load from token vs. resolve from args
- No detect_feature() calls anywhere in the callstack
- Error paths: missing wp, missing feature, missing config
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.lane_test_utils import write_single_lane_manifest

from specify_cli.context import (
    MissionContext,
    resolve_context,
    resolve_or_load,
    load_context,
    MissingArgumentError,
    FeatureNotFoundError,
    MissingIdentityError,
    WorkPackageNotFoundError,
    ContextNotFoundError,
)

pytestmark = pytest.mark.fast


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _setup_project(
    tmp_path: Path,
    *,
    mission_slug: str = "047-lifecycle-test",
    wp_code: str = "WP01",
    execution_mode: str = "code_change",
    owned_files: list[str] | None = None,
    dependencies: list[str] | None = None,
    project_uuid: str = "test-uuid-lifecycle-0001",
    mission_id: str | None = None,
    lane_id: str = "lane-a",
) -> Path:
    """Build a minimal project with .kittify config and one feature+WP."""
    kittify_dir = tmp_path / ".kittify"
    kittify_dir.mkdir(parents=True)
    (kittify_dir / "config.yaml").write_text(
        f"vcs:\n  type: git\nproject:\n  uuid: {project_uuid}\n  slug: test-proj\n",
        encoding="utf-8",
    )

    feature_dir = tmp_path / "kitty-specs" / mission_slug
    feature_dir.mkdir(parents=True)
    meta: dict[str, str] = {
        "mission_slug": mission_slug,
        "mission": "software-dev",
        "target_branch": "main",
        "created_at": "2026-03-27T16:00:00+00:00",
    }
    if mission_id:
        meta["mission_id"] = mission_id
    (feature_dir / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True)
    files = owned_files or ["src/specify_cli/context/**"]
    deps = dependencies or []
    deps_yaml = "[" + ", ".join(f'"{d}"' for d in deps) + "]"
    owned_yaml = "\n".join(f'- "{f}"' for f in files)
    wp_content = (
        f"---\n"
        f"work_package_id: {wp_code}\n"
        f"title: Lifecycle Test WP\n"
        f"lane: planned\n"
        f"dependencies: {deps_yaml}\n"
        f"execution_mode: {execution_mode}\n"
        f"owned_files:\n"
        f"{owned_yaml}\n"
        f"---\n\n"
        f"# Work Package: {wp_code}\n\nContent.\n"
    )
    (tasks_dir / f"{wp_code}-lifecycle-wp.md").write_text(wp_content, encoding="utf-8")
    write_single_lane_manifest(
        feature_dir,
        wp_ids=(wp_code,),
        lane_id=lane_id,
        mission_id=mission_id or mission_slug,
        predicted_surfaces=("context",),
    )
    return tmp_path


# ---------------------------------------------------------------------------
# T070: Context resolution — explicit args only, no heuristics
# ---------------------------------------------------------------------------

class TestContextResolutionNoHeuristics:
    """resolve_context requires explicit wp_code + mission_slug; never scans."""

    def test_resolve_context_returns_mission_context(self, tmp_path: Path) -> None:
        repo = _setup_project(tmp_path)
        ctx = resolve_context("WP01", "047-lifecycle-test", "claude", repo)

        assert isinstance(ctx, MissionContext)
        assert ctx.wp_code == "WP01"
        assert ctx.mission_slug == "047-lifecycle-test"
        assert ctx.project_uuid == "test-uuid-lifecycle-0001"
        assert ctx.target_branch == "main"
        assert ctx.execution_mode == "code_change"
        assert ctx.created_by == "claude"

    def test_resolve_requires_wp_code(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        with pytest.raises(MissingArgumentError, match="wp_code is required"):
            resolve_context("", "047-lifecycle-test", "claude", tmp_path)

    def test_resolve_requires_mission_slug(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        with pytest.raises(MissingArgumentError, match="mission_slug is required"):
            resolve_context("WP01", "", "claude", tmp_path)

    def test_resolve_raises_when_feature_dir_missing(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        with pytest.raises(FeatureNotFoundError):
            resolve_context("WP01", "999-nonexistent-feature", "claude", tmp_path)

    def test_resolve_raises_when_wp_not_found(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        with pytest.raises(WorkPackageNotFoundError):
            resolve_context("WP99", "047-lifecycle-test", "claude", tmp_path)

    def test_resolve_raises_when_config_missing(self, tmp_path: Path) -> None:
        """No .kittify/config.yaml → MissingIdentityError, not a silent fallback."""
        feature_dir = tmp_path / "kitty-specs" / "047-lifecycle-test"
        feature_dir.mkdir(parents=True)
        (feature_dir / "meta.json").write_text(
            json.dumps({"mission_slug": "047-lifecycle-test", "target_branch": "main"}),
            encoding="utf-8",
        )
        (feature_dir / "tasks").mkdir()
        (feature_dir / "tasks" / "WP01-test.md").write_text(
            "---\nwork_package_id: WP01\nlane: planned\n---\nContent\n",
            encoding="utf-8",
        )
        with pytest.raises(MissingIdentityError, match="config.yaml"):
            resolve_context("WP01", "047-lifecycle-test", "claude", tmp_path)

    def test_no_detect_feature_called_during_resolution(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify detection heuristics are not invoked during context resolution.

        The old feature_detection module has been removed (WP02). This test
        confirms that resolve_context succeeds without touching any heuristic
        detection pathway — it is a contract test, not an import blocker.

        We verify by patching the (now-deleted) module to raise if somehow
        re-imported as a sanity check. The test simply completes successfully,
        proving that no heuristic path is needed.
        """
        repo = _setup_project(tmp_path)
        import sys

        # Ensure the deleted module is not importable even if stale .pyc exists.
        # ``monkeypatch.setitem`` records whatever was there before (nothing,
        # in the real-world case, since the module is permanently removed) and
        # restores exactly that on teardown -- absent key stays absent, a
        # stale entry would be restored verbatim.
        monkeypatch.setitem(sys.modules, "specify_cli.core.feature_detection", None)
        # Resolution must succeed even with feature_detection blocked
        ctx = resolve_context("WP01", "047-lifecycle-test", "claude", repo)
        assert ctx.wp_code == "WP01"


# ---------------------------------------------------------------------------
# T070: Token round-trip (persist + load)
# ---------------------------------------------------------------------------

class TestContextTokenRoundTrip:
    """A resolved context can be persisted and reloaded by token."""

    def test_save_then_load_by_token(self, tmp_path: Path) -> None:
        repo = _setup_project(tmp_path)
        ctx = resolve_context("WP01", "047-lifecycle-test", "claude", repo)

        # reload by token
        loaded = load_context(ctx.token, repo)
        assert loaded.token == ctx.token
        assert loaded.wp_code == ctx.wp_code
        assert loaded.mission_slug == ctx.mission_slug
        assert loaded.project_uuid == ctx.project_uuid

    def test_load_raises_for_unknown_token(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        with pytest.raises(ContextNotFoundError):
            load_context("ctx-DOESNOTEXIST", tmp_path)

    def test_two_resolves_produce_unique_tokens(self, tmp_path: Path) -> None:
        repo = _setup_project(tmp_path)
        ctx1 = resolve_context("WP01", "047-lifecycle-test", "claude", repo)
        ctx2 = resolve_context("WP01", "047-lifecycle-test", "claude", repo)
        assert ctx1.token != ctx2.token


# ---------------------------------------------------------------------------
# T070: resolve_or_load — token path vs. fresh resolve
# ---------------------------------------------------------------------------

class TestResolveOrLoad:
    """resolve_or_load dispatches to load or resolve depending on inputs."""

    def test_load_from_token(self, tmp_path: Path) -> None:
        repo = _setup_project(tmp_path)
        ctx = resolve_context("WP01", "047-lifecycle-test", "claude", repo)

        loaded = resolve_or_load(
            token=ctx.token,
            wp_code=None,
            mission_slug=None,
            agent="claude",
            repo_root=repo,
        )
        assert loaded.token == ctx.token

    def test_resolve_from_args(self, tmp_path: Path) -> None:
        repo = _setup_project(tmp_path)
        ctx = resolve_or_load(
            token=None,
            wp_code="WP01",
            mission_slug="047-lifecycle-test",
            agent="claude",
            repo_root=repo,
        )
        assert isinstance(ctx, MissionContext)
        assert ctx.wp_code == "WP01"

    def test_raises_when_neither_token_nor_args(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        with pytest.raises(MissingArgumentError, match="Missing required argument"):
            resolve_or_load(
                token=None,
                wp_code=None,
                mission_slug=None,
                agent="claude",
                repo_root=tmp_path,
            )

    def test_raises_when_only_wp_code_missing(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        with pytest.raises(MissingArgumentError, match="--wp"):
            resolve_or_load(
                token=None,
                wp_code=None,
                mission_slug="047-lifecycle-test",
                agent="claude",
                repo_root=tmp_path,
            )

    def test_raises_when_only_mission_slug_missing(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        with pytest.raises(MissingArgumentError, match="--mission"):
            resolve_or_load(
                token=None,
                wp_code="WP01",
                mission_slug=None,
                agent="claude",
                repo_root=tmp_path,
            )

    def test_token_takes_precedence_over_args(self, tmp_path: Path) -> None:
        """When token is provided, wp_code/mission_slug args are ignored."""
        repo = _setup_project(tmp_path)
        ctx = resolve_context("WP01", "047-lifecycle-test", "claude", repo)

        # Pass mismatching wp_code — should load by token, not re-resolve
        loaded = resolve_or_load(
            token=ctx.token,
            wp_code="WP99",  # wrong — should be ignored
            mission_slug="999-wrong-feature",  # wrong — should be ignored
            agent="claude",
            repo_root=repo,
        )
        assert loaded.wp_code == "WP01"


# ---------------------------------------------------------------------------
# T070: Context field correctness
# ---------------------------------------------------------------------------

class TestContextFieldCorrectness:
    """Context fields are correctly populated from metadata."""

    def test_authoritative_ref_set_for_code_change(self, tmp_path: Path) -> None:
        repo = _setup_project(tmp_path, execution_mode="code_change")
        ctx = resolve_context("WP01", "047-lifecycle-test", "claude", repo)
        assert ctx.authoritative_ref == "kitty/mission-047-lifecycle-test-lane-a"

    def test_authoritative_ref_none_for_planning_artifact(self, tmp_path: Path) -> None:
        # planning_artifact WPs are assigned to lane-planning; lane_branch_name returns
        # target_branch ("main") for lane-planning (FR-102, FR-103).
        repo = _setup_project(tmp_path, execution_mode="planning_artifact", lane_id="lane-planning")
        ctx = resolve_context("WP01", "047-lifecycle-test", "claude", repo)
        assert ctx.authoritative_ref == "main"

    def test_dependency_mode_independent_when_no_deps(self, tmp_path: Path) -> None:
        repo = _setup_project(tmp_path, dependencies=[])
        ctx = resolve_context("WP01", "047-lifecycle-test", "claude", repo)
        assert ctx.dependency_mode == "independent"

    def test_dependency_mode_chained_when_deps_present(self, tmp_path: Path) -> None:
        repo = _setup_project(tmp_path, dependencies=["WP00"])
        ctx = resolve_context("WP01", "047-lifecycle-test", "claude", repo)
        assert ctx.dependency_mode == "chained"

    def test_owned_files_populated(self, tmp_path: Path) -> None:
        repo = _setup_project(tmp_path, owned_files=["src/a.py", "src/b.py"])
        ctx = resolve_context("WP01", "047-lifecycle-test", "claude", repo)
        assert "src/a.py" in ctx.owned_files
        assert "src/b.py" in ctx.owned_files

    def test_mission_id_falls_back_to_mission_slug(self, tmp_path: Path) -> None:
        """When meta.json has no mission_id, mission_slug is used as mission_id."""
        repo = _setup_project(tmp_path, mission_id=None)  # no explicit mission_id
        ctx = resolve_context("WP01", "047-lifecycle-test", "claude", repo)
        # mission_id resolves to mission_slug when absent
        assert ctx.mission_id == "047-lifecycle-test"

    def test_mission_id_explicit_when_set(self, tmp_path: Path) -> None:
        repo = _setup_project(tmp_path, mission_id="mission-uuid-abc123")
        ctx = resolve_context("WP01", "047-lifecycle-test", "claude", repo)
        assert ctx.mission_id == "mission-uuid-abc123"
