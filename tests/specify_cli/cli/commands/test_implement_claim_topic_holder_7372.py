"""#7372 / FR-061: the claim commit runs in the checkout holding a default Mission's topic branch.

Until a ``topology_source: default`` Mission lands, the PRIMARY write home of
``WORK_PACKAGE_TASK`` is its topic branch, held by the coordination worktree, while the
repository root checkout is back on ``create_return_branch``. The #5738 up-front HEAD check
and the claim commit must both judge that holder, never the repository root checkout.
The seam, the status read and the FR-061 holder (``primary_partition_checkout``) are stubbed;
the checkouts are a real git repository.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from specify_cli.cli.commands import implement_claim
from specify_cli.git.commit_helpers import SafeCommitHeadMismatch
from tests._support.git_cli import git_out

pytestmark = [pytest.mark.unit, pytest.mark.git_repo]

_SLUG = "probe-01M6XCQ7"
_TOPIC = "kitty/mission-probe-01M6XCQ7"


@pytest.fixture()
def repo_with_topic_holder(tmp_path: Path) -> tuple[Path, Path]:
    repo = tmp_path / "repo"
    repo.mkdir()
    git_out(repo, "init", "-q", "-b", "work")
    git_out(repo, "config", "user.email", "t@example.com")
    git_out(repo, "config", "user.name", "Test")
    git_out(repo, "config", "commit.gpgsign", "false")
    (repo / "README.md").write_text("x\n", encoding="utf-8")
    git_out(repo, "add", "-A")
    git_out(repo, "commit", "-qm", "init")
    holder = repo / ".worktrees" / f"{_SLUG}-coord"
    git_out(repo, "worktree", "add", "-q", "-b", _TOPIC, str(holder))
    (holder / "kitty-specs" / _SLUG).mkdir(parents=True)
    return repo, holder


@pytest.fixture()
def located_holder(repo_with_topic_holder: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    """The FR-061 holder is the topic worktree (a default Mission before its landing)."""
    from specify_cli.coordination import planning_commit

    repo, holder = repo_with_topic_holder
    monkeypatch.setattr(planning_commit, "primary_partition_checkout", lambda *_a, **_k: holder)
    return repo, holder


@pytest.fixture()
def planned_wp_on_topic(monkeypatch: pytest.MonkeyPatch) -> None:
    """The WP is ``planned`` and the seam's PRIMARY write target is the topic branch."""
    import specify_cli.status as status_pkg

    monkeypatch.setattr(status_pkg, "resolve_status_read", lambda *_a, **_k: object())
    monkeypatch.setattr(status_pkg, "materialize_status", lambda *_a, **_k: SimpleNamespace(work_packages={"WP01": {"lane": "planned"}}))
    seam = SimpleNamespace(write_target=lambda _kind: SimpleNamespace(ref=_TOPIC))
    monkeypatch.setattr(implement_claim, "placement_seam", lambda *_a, **_k: seam)


@pytest.mark.usefixtures("planned_wp_on_topic")
def test_head_check_judges_the_topic_holder_not_the_repository_root(located_holder: tuple[Path, Path]) -> None:
    repo, holder = located_holder
    implement_claim._raise_if_claim_commit_head_mismatch(repo, _SLUG, "WP01", True, holder / "kitty-specs" / _SLUG)


@pytest.mark.usefixtures("planned_wp_on_topic")
def test_head_check_without_the_mission_dir_keeps_judging_the_repository_root(located_holder: tuple[Path, Path]) -> None:
    """The pre-#7372 call shape still refuses: the repository root checkout is on ``work``."""
    repo, _holder = located_holder
    with pytest.raises(SafeCommitHeadMismatch) as excinfo:
        implement_claim._raise_if_claim_commit_head_mismatch(repo, _SLUG, "WP01", True)
    assert "HEAD is 'work'" in str(excinfo.value)


@pytest.mark.usefixtures("planned_wp_on_topic")
def test_head_check_with_a_mission_dir_outside_the_holder_judges_the_repository_root(located_holder: tuple[Path, Path]) -> None:
    repo, _holder = located_holder
    with pytest.raises(SafeCommitHeadMismatch):
        implement_claim._raise_if_claim_commit_head_mismatch(repo, _SLUG, "WP01", True, repo / "kitty-specs" / _SLUG)


def test_claim_commit_checkout_is_the_topic_holder(located_holder: tuple[Path, Path]) -> None:
    repo, holder = located_holder
    assert implement_claim._claim_commit_checkout(repo, holder / "kitty-specs" / _SLUG, _SLUG) == holder
    assert implement_claim._claim_commit_checkout(repo, repo / "kitty-specs" / _SLUG, _SLUG) == repo


def _claim(repo: Path, feature_dir: Path, *, auto_commit: bool) -> None:
    implement_claim._commit_wp_claim_status(
        repo_root=repo,
        feature_dir=feature_dir,
        mission_slug=_SLUG,
        wp_id="WP01",
        auto_commit=auto_commit,
        status_result=SimpleNamespace(status_changed=True),
        meta_written=True,
    )


@pytest.fixture()
def coord_topology_status(monkeypatch: pytest.MonkeyPatch) -> None:
    """Coordination topology: the claim's status pair is the emitter's, only ``meta.json`` is claim-written."""
    import specify_cli.cli.commands.agent.tasks as tasks_module

    monkeypatch.setattr(tasks_module, "_collect_status_artifacts", lambda _dir: [])
    monkeypatch.setattr(implement_claim, "resolve_topology", lambda *_a, **_k: object())
    monkeypatch.setattr(implement_claim, "routes_through_coordination", lambda _t: True)


@pytest.mark.usefixtures("coord_topology_status")
def test_no_auto_commit_claim_stages_meta_in_the_topic_holder(located_holder: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch) -> None:
    """Driven through ``_commit_wp_claim_status``: the holder's index gets ``meta.json``, the root's index nothing."""
    repo, holder = located_holder
    monkeypatch.setattr(implement_claim, "placement_seam", lambda *_a, **_k: pytest.fail("no-auto-commit must not ask the seam"))
    mission_dir = holder / "kitty-specs" / _SLUG
    (mission_dir / "meta.json").write_text("{}\n", encoding="utf-8")
    _claim(repo, mission_dir, auto_commit=False)
    assert git_out(holder, "diff", "--cached", "--name-only").strip() == f"kitty-specs/{_SLUG}/meta.json"
    assert git_out(repo, "diff", "--cached", "--name-only").strip() == ""


@pytest.mark.usefixtures("coord_topology_status")
def test_no_auto_commit_claim_survives_an_unresolvable_checkout(
    repo_with_topic_holder: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The status write already landed: a locator failure is a staging warning, never a traceback (#3471)."""
    from specify_cli.coordination import planning_commit

    repo, holder = repo_with_topic_holder

    def _broken(*_a: object, **_k: object) -> Path:
        raise RuntimeError("meta.json unreadable")

    monkeypatch.setattr(planning_commit, "primary_partition_checkout", _broken)
    mission_dir = holder / "kitty-specs" / _SLUG
    (mission_dir / "meta.json").write_text("{}\n", encoding="utf-8")
    _claim(repo, mission_dir, auto_commit=False)
    out = capsys.readouterr().out
    assert "Could not stage the claim's changes" in out and "meta.json unreadable" in out


@pytest.mark.usefixtures("coord_topology_status")
def test_no_auto_commit_claim_never_stages_a_worktrees_path_in_the_root(
    repo_with_topic_holder: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """#2155: a Mission dir inside another checkout, with no FR-061 holder, is named and left unstaged."""
    from specify_cli.coordination import planning_commit

    repo, holder = repo_with_topic_holder
    monkeypatch.setattr(planning_commit, "primary_partition_checkout", lambda *_a, **_k: None)
    mission_dir = holder / "kitty-specs" / _SLUG
    (mission_dir / "meta.json").write_text("{}\n", encoding="utf-8")
    _claim(repo, mission_dir, auto_commit=False)
    assert git_out(repo, "diff", "--cached", "--name-only").strip() == ""
    assert "Not staging paths inside another checkout" in capsys.readouterr().out
