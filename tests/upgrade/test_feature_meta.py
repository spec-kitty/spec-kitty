"""Scope: feature meta unit tests — no real git or subprocesses."""

from __future__ import annotations

from pathlib import Path

import pytest

from specify_cli.upgrade.feature_meta import build_baseline_feature_meta, infer_target_branch

pytestmark = pytest.mark.fast

def test_build_baseline_feature_meta_replaces_blank_fields(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Blank metadata values are repaired, not preserved."""
    repo_root = tmp_path / "repo"
    feature_dir = repo_root / "kitty-specs" / "023-repair-me"
    feature_dir.mkdir(parents=True)
    (feature_dir / "spec.md").write_text("# Spec\n", encoding="utf-8")

    monkeypatch.setattr(
        "specify_cli.upgrade.feature_meta.resolve_primary_branch",
        lambda _repo_root: "2.x",
    )

    meta = build_baseline_feature_meta(
        feature_dir,
        repo_root,
        existing_meta={
            "mission_number": "",
            "slug": "",
            "mission_slug": "",
            "friendly_name": "",
            "mission_type": "",
            "target_branch": "",
            "created_at": "",
        },
    )

    assert meta["mission_number"] == "023"
    assert meta["slug"] == "023-repair-me"
    assert meta["mission_slug"] == "023-repair-me"
    assert meta["friendly_name"] == "repair me"
    assert meta["mission_type"] == "software-dev"
    assert meta["target_branch"] == "2.x"
    assert meta["created_at"]


# ---------------------------------------------------------------------------
# infer_target_branch
# ---------------------------------------------------------------------------

_MONKEYPATCH_TARGET = "specify_cli.upgrade.feature_meta.resolve_primary_branch"


def _setup_feature(tmp_path: Path, doc_name: str, content: str) -> tuple[Path, Path]:
    """Create a minimal feature dir with a single doc file."""
    repo_root = tmp_path / "repo"
    feature_dir = repo_root / "kitty-specs" / "099-test"
    feature_dir.mkdir(parents=True)
    (feature_dir / doc_name).write_text(content, encoding="utf-8")
    return feature_dir, repo_root


class TestInferTargetBranch:
    """Tests for infer_target_branch covering all regex patterns and edge cases."""

    def test_no_doc_files_returns_fallback(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        repo_root = tmp_path / "repo"
        feature_dir = repo_root / "kitty-specs" / "099-empty"
        feature_dir.mkdir(parents=True)
        monkeypatch.setattr(_MONKEYPATCH_TARGET, lambda _r: "main")
        assert infer_target_branch(feature_dir, repo_root) == "main"

    def test_explicit_fallback_kwarg(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        repo_root = tmp_path / "repo"
        feature_dir = repo_root / "kitty-specs" / "099-empty"
        feature_dir.mkdir(parents=True)
        monkeypatch.setattr(_MONKEYPATCH_TARGET, lambda _r: "main")
        assert infer_target_branch(feature_dir, repo_root, fallback="develop") == "develop"

    def test_pattern_target_branch(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        feature_dir, repo_root = _setup_feature(
            tmp_path, "spec.md", "**Target Branch**: release/1.0\n"
        )
        monkeypatch.setattr(_MONKEYPATCH_TARGET, lambda _r: "main")
        assert infer_target_branch(feature_dir, repo_root) == "release/1.0"

    def test_pattern_base_branch(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        feature_dir, repo_root = _setup_feature(
            tmp_path, "spec.md", "**Base Branch**: develop\n"
        )
        monkeypatch.setattr(_MONKEYPATCH_TARGET, lambda _r: "main")
        assert infer_target_branch(feature_dir, repo_root) == "develop"

    def test_pattern_target_repo_branch(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        feature_dir, repo_root = _setup_feature(
            tmp_path, "spec.md", "target repo branch: staging\n"
        )
        monkeypatch.setattr(_MONKEYPATCH_TARGET, lambda _r: "main")
        assert infer_target_branch(feature_dir, repo_root) == "staging"

    def test_pattern_branch_colon(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        feature_dir, repo_root = _setup_feature(
            tmp_path, "spec.md", "branch: 2.x\n"
        )
        monkeypatch.setattr(_MONKEYPATCH_TARGET, lambda _r: "main")
        assert infer_target_branch(feature_dir, repo_root) == "2.x"

    def test_pattern_must_be_done_on_branch(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        feature_dir, repo_root = _setup_feature(
            tmp_path, "spec.md", "All work must be done on the `feature/v3` branch.\n"
        )
        monkeypatch.setattr(_MONKEYPATCH_TARGET, lambda _r: "main")
        assert infer_target_branch(feature_dir, repo_root) == "feature/v3"

    def test_pattern_merge_back_to(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        feature_dir, repo_root = _setup_feature(
            tmp_path, "spec.md", "merge back to `develop`\n"
        )
        monkeypatch.setattr(_MONKEYPATCH_TARGET, lambda _r: "main")
        assert infer_target_branch(feature_dir, repo_root) == "develop"

    def test_pattern_repository_branch(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        feature_dir, repo_root = _setup_feature(
            tmp_path, "spec.md", "repository https://github.com/org/repo branch `2.x`\n"
        )
        monkeypatch.setattr(_MONKEYPATCH_TARGET, lambda _r: "main")
        assert infer_target_branch(feature_dir, repo_root) == "2.x"

    def test_backtick_wrapped_branch_name(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        feature_dir, repo_root = _setup_feature(
            tmp_path, "spec.md", "**Target Branch**: `hotfix/urgent`\n"
        )
        monkeypatch.setattr(_MONKEYPATCH_TARGET, lambda _r: "main")
        assert infer_target_branch(feature_dir, repo_root) == "hotfix/urgent"

    def test_multiple_candidates_fallback_among_them(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        content = (
            "**Target Branch**: develop\n"
            "branch: main\n"
        )
        feature_dir, repo_root = _setup_feature(tmp_path, "spec.md", content)
        monkeypatch.setattr(_MONKEYPATCH_TARGET, lambda _r: "main")
        assert infer_target_branch(feature_dir, repo_root) == "main"

    def test_multiple_candidates_fallback_not_among_them(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        content = (
            "**Target Branch**: release/1.0\n"
            "branch: staging\n"
        )
        feature_dir, repo_root = _setup_feature(tmp_path, "spec.md", content)
        monkeypatch.setattr(_MONKEYPATCH_TARGET, lambda _r: "main")
        assert infer_target_branch(feature_dir, repo_root) == "main"

    def test_branch_found_in_tasks_md(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        feature_dir, repo_root = _setup_feature(
            tmp_path, "tasks.md", "**Target Branch**: release/2.0\n"
        )
        monkeypatch.setattr(_MONKEYPATCH_TARGET, lambda _r: "main")
        assert infer_target_branch(feature_dir, repo_root) == "release/2.0"

    def test_or_in_value_rejected(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        feature_dir, repo_root = _setup_feature(
            tmp_path, "spec.md", "**Target Branch**: main or develop\n"
        )
        monkeypatch.setattr(_MONKEYPATCH_TARGET, lambda _r: "main")
        assert infer_target_branch(feature_dir, repo_root) == "main"

    def test_deduplication_same_branch_two_files(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        repo_root = tmp_path / "repo"
        feature_dir = repo_root / "kitty-specs" / "099-dedup"
        feature_dir.mkdir(parents=True)
        (feature_dir / "spec.md").write_text("branch: release/3.0\n", encoding="utf-8")
        (feature_dir / "tasks.md").write_text("branch: release/3.0\n", encoding="utf-8")
        monkeypatch.setattr(_MONKEYPATCH_TARGET, lambda _r: "main")
        assert infer_target_branch(feature_dir, repo_root) == "release/3.0"

    def test_all_work_packages_branch_from_pattern(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        feature_dir, repo_root = _setup_feature(
            tmp_path, "spec.md",
            "all work packages branch from and merge back to `2.x`\n"
        )
        monkeypatch.setattr(_MONKEYPATCH_TARGET, lambda _r: "main")
        assert infer_target_branch(feature_dir, repo_root) == "2.x"


@pytest.mark.parametrize("slug", ["042-x", "my-mission-01M5JYRC", "single"])
def test_baseline_builder_slug_fields_equal_the_shared_helper(tmp_path: Path, slug: str) -> None:
    """The builder's slug-derived fields come from the one owner, ``baseline_slug_fields`` (FR-012)."""
    from specify_cli.mission_metadata import baseline_slug_fields

    feature_dir = tmp_path / "kitty-specs" / slug
    feature_dir.mkdir(parents=True)
    (feature_dir / "spec.md").write_text("# Spec\n", encoding="utf-8")

    meta = build_baseline_feature_meta(feature_dir, tmp_path)

    assert meta is not None
    expected = baseline_slug_fields(slug)
    assert {key: meta[key] for key in expected} == expected


def test_baseline_slug_fields_values() -> None:
    from specify_cli.mission_metadata import baseline_slug_fields

    assert baseline_slug_fields("042-x") == {"mission_number": "042", "slug": "042-x", "mission_slug": "042-x", "friendly_name": "x"}
    assert baseline_slug_fields("my-mission-01M5JYRC")["mission_number"] == ""
    assert baseline_slug_fields("my-mission-01M5JYRC")["friendly_name"] == "mission 01M5JYRC"
    assert baseline_slug_fields("single")["friendly_name"] == "single"
