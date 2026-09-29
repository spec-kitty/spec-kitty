"""End-to-end consolidate of a protected single_branch mission (WP08 review cycle 1, blocker 4).

Drives the REAL executor entry point (``_run_lane_based_consolidation``, what
``spec-kitty consolidate`` calls) -- phases, reconciliation gate (with the
``authorship_window`` blob source), switch-back and retention are all decided by
production code, not by the test. Mission built through create -> finalize ->
implement -> commit -> approve.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from specify_cli.consolidation.config import MergeStrategy
from specify_cli.consolidation.executor import _run_lane_based_consolidation
from specify_cli.status.emit import emit_status_transition
from typer.testing import CliRunner

from specify_cli import app as root_app
from tests.core.test_mission_create_protected_single_branch import _finalized_protected_mission

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

runner = CliRunner()


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True).stdout.strip()


def _branch_exists(repo: Path, branch: str) -> bool:
    return subprocess.run(["git", "-C", str(repo), "rev-parse", "--verify", f"refs/heads/{branch}"], capture_output=True).returncode == 0


def _approved_mission(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, name: str, **create_overrides: object) -> tuple[Path, str, str]:
    repo, slug, minted, feature_dir = _finalized_protected_mission(tmp_path, monkeypatch, name, **create_overrides)
    implement = runner.invoke(root_app, ["implement", "WP01", "--mission", slug, "--json"])
    assert implement.exit_code == 0, implement.output
    (repo / "src" / "wp01.py").write_text("VALUE = 100\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "feat(WP01): deliverable")
    for lane in ("for_review", "in_review", "approved"):
        emit_status_transition(feature_dir=feature_dir, mission_slug=slug, wp_id="WP01", to_lane=lane, actor="wp08-e2e", force=True, reason="e2e seed")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "chore: approve WP01")
    assert _git(repo, "branch", "--show-current") == minted
    return repo, slug, minted


def _consolidate(repo: Path, slug: str, *, delete_branch: bool | None = None) -> None:
    _run_lane_based_consolidation(
        repo,
        slug,
        push=False,
        delete_branch=delete_branch,
        remove_worktree=None,
        strategy=MergeStrategy.SQUASH,
        assume_yes=True,
        skip_review_artifact_check=True,
        skip_note="wp08 e2e",
    )


def test_protected_single_branch_consolidate_lands_and_cleans_up(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo, slug, minted = _approved_mission(tmp_path, monkeypatch, "cons-e2e")
    main_before = _git(repo, "rev-parse", "main")

    _consolidate(repo, slug)  # a reconciliation refusal (no authored content) would raise typer.Exit

    assert _git(repo, "rev-parse", "main") != main_before, "the target must have advanced"
    assert "VALUE = 100" in _git(repo, "show", "main:src/wp01.py"), "the target contains the work"
    assert _git(repo, "branch", "--show-current") == "main", "write checkout switched back to the target"
    assert not _branch_exists(repo, minted), "mission_branch deleted"
    assert (repo / ".git").is_dir() and (repo / "README.md").exists(), "repo root checkout intact"


def test_protected_single_branch_consolidate_honours_retain_branches(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """meta.json retain_branches: true (decided by resolve_merge_retention, not the test)."""
    repo, slug, minted = _approved_mission(tmp_path, monkeypatch, "cons-retain", retain_branches=True)

    _consolidate(repo, slug)

    assert "VALUE = 100" in _git(repo, "show", "main:src/wp01.py")
    assert _git(repo, "branch", "--show-current") == "main"
    assert _branch_exists(repo, minted), "retain_branches keeps the mission branch"
    _assert_landed_mission_branch_cleared(repo, slug)


def _assert_landed_mission_branch_cleared(repo: Path, slug: str) -> None:
    """The branch is landed: post-merge writes target ``target_branch``, the tree is clean."""
    import json

    meta = json.loads((repo / "kitty-specs" / slug / "meta.json").read_text(encoding="utf-8"))
    assert "mission_branch" not in meta, "a landed (even if retained) mission branch must not stay the write target"
    assert _git(repo, "status", "--porcelain") == "", "no post-merge write may be left uncommitted"


def test_protected_single_branch_consolidate_keep_branch_clears_write_target(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """``--keep-branch`` (delete_branch=False): landed branch kept, but meta stops routing writes to it."""
    repo, slug, minted = _approved_mission(tmp_path, monkeypatch, "cons-keep")

    _consolidate(repo, slug, delete_branch=False)

    assert "VALUE = 100" in _git(repo, "show", "main:src/wp01.py")
    assert _git(repo, "branch", "--show-current") == "main"
    assert _branch_exists(repo, minted), "--keep-branch keeps the mission branch"
    _assert_landed_mission_branch_cleared(repo, slug)


def _legacy_repo(tmp_path: Path, meta: dict[str, object]) -> tuple[Path, object]:
    """Real repo + legacy planning-only mission whose manifest carries a derived ``mission_branch``."""
    import json
    from types import SimpleNamespace

    slug = "legacy-plan-only-01ABCDEF"
    _git(tmp_path, "init", "-q", "-b", "main")
    _git(tmp_path, "config", "user.email", "t@example.com")
    _git(tmp_path, "config", "user.name", "T")
    feature_dir = tmp_path / "kitty-specs" / slug
    feature_dir.mkdir(parents=True)
    (feature_dir / "meta.json").write_text(json.dumps({"mission_slug": slug, "target_branch": "main", **meta}), encoding="utf-8")
    (tmp_path / "README.md").write_text("x\n", encoding="utf-8")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "init")
    manifest = SimpleNamespace(
        mission_slug=slug,
        target_branch="main",
        mission_branch=f"kitty/mission-{slug}",
        lanes=[SimpleNamespace(lane_id="lane-planning", wp_ids=["WP01"])],
    )
    return tmp_path, manifest


@pytest.mark.parametrize(
    "meta",
    [
        {},  # unstamped legacy planning-only: topology would only be DERIVED
        {"mission_branch": "kitty/mission-legacy-plan-only-01ABCDEF"},  # marker without a stored topology
        {"topology": "single_branch"},  # stored topology without the create-time mint marker
        {"topology": "lanes", "mission_branch": "kitty/mission-legacy-plan-only-01ABCDEF"},
    ],
)
def test_legacy_planning_only_mission_is_never_landed(tmp_path: Path, meta: dict[str, object]) -> None:
    """LEGACY CONTROL: only STORED single_branch + a minted ``mission_branch`` lands.

    A legacy manifest always has ``mission_branch != target_branch``; that must not
    flip planning_artifact_only, the preflight checkout, done-ordering or coord teardown.
    """
    from specify_cli.lanes.single_branch_landing import authorship_window, expected_consolidate_checkout, lands_mission_branch

    repo, manifest = _legacy_repo(tmp_path, meta)
    assert lands_mission_branch(repo, manifest) is False
    assert expected_consolidate_checkout(repo, manifest, "main") == "main"
    assert authorship_window(repo, manifest.mission_slug, manifest.mission_branch, "main") is None


def test_protected_meta_is_landed_positive_control(tmp_path: Path) -> None:
    from specify_cli.lanes.single_branch_landing import lands_mission_branch

    repo, manifest = _legacy_repo(tmp_path, {"topology": "single_branch", "mission_branch": "kitty/mission-legacy-plan-only-01ABCDEF"})
    assert lands_mission_branch(repo, manifest) is True
