"""Every ``.git``/``.kittify`` root walk stops at ``GIT_CEILING_DIRECTORIES`` (#7056).

#7022 taught three walks to honour the git ceiling; the rest kept climbing, so a
hermetic tree inside an enclosing repository resolved into that repository. Each case
here builds an ambient repository/service *above* a ceiling and starts a walk *below* it:
the walk must behave exactly as it would with no ambient repository at all. The second
half of each test proves the ceiling does not blind the walk to a marker inside its own
tree.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import typer

from specify_cli.bootstrap.env_file import _find_repo_root as env_file_repo_root
from specify_cli.context import middleware as context_middleware
from specify_cli.coordination import legacy_resolution
from specify_cli.core.checkout_identity import Intent, resolve_checkout_identity
from specify_cli.core.ledger_posture import _walk_up_to_kittify_marker
from specify_cli.core.paths import (
    WorkspaceRootNotFound,
    get_status_read_root,
    is_worktree_context,
    resolve_canonical_root,
)
from specify_cli.gitignore_manager import _has_git_control_path
from specify_cli.migration.legacy_charter_gate import find_checkout_root
from specify_cli.mission_metadata import _has_no_git_anchor
from specify_cli.task_utils.support import find_repo_root

CEILING_ENV = "GIT_CEILING_DIRECTORIES"


@pytest.fixture(autouse=True)
def _no_ambient_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SPECIFY_REPO_ROOT", raising=False)


@pytest.fixture
def ambient_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    """``(<tmp>/outer``, ``<tmp>/outer/ceiling/work)`` with the ceiling at ``…/ceiling``.

    ``outer`` is a real repository boundary (``.git`` directory with a ``HEAD``) *and* a
    Spec Kitty project (``.kittify``), so every marker shape the walks look for exists
    above the ceiling, which sits between it and the start directory.
    """
    outer = (tmp_path / "outer").resolve()
    (outer / ".git").mkdir(parents=True)
    (outer / ".git" / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    (outer / ".kittify").mkdir()
    ceiling = (outer / "ceiling").resolve()
    work = (ceiling / "work").resolve()
    work.mkdir(parents=True)
    monkeypatch.setenv(CEILING_ENV, str(ceiling))
    return outer, work


def test_resolve_canonical_root_does_not_adopt_a_repo_above_the_ceiling(ambient_repo: tuple[Path, Path]) -> None:
    _outer, work = ambient_repo

    with pytest.raises(WorkspaceRootNotFound):
        resolve_canonical_root(work)


def test_resolve_canonical_root_still_finds_a_repo_below_the_ceiling(ambient_repo: tuple[Path, Path]) -> None:
    _outer, work = ambient_repo
    (work / ".git").mkdir()

    assert resolve_canonical_root(work) == work


def test_get_status_read_root_does_not_adopt_a_repo_above_the_ceiling(ambient_repo: tuple[Path, Path]) -> None:
    _outer, work = ambient_repo

    assert get_status_read_root(work) == work


def test_find_repo_root_does_not_adopt_a_repo_above_the_ceiling(ambient_repo: tuple[Path, Path]) -> None:
    from specify_cli.task_utils.support import TaskCliError

    _outer, work = ambient_repo

    with pytest.raises(TaskCliError):
        find_repo_root(work)


def test_find_repo_root_still_finds_a_plain_git_repo_below_the_ceiling(ambient_repo: tuple[Path, Path]) -> None:
    _outer, work = ambient_repo
    (work / ".git").mkdir()
    (work / ".git" / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")

    assert find_repo_root(work) == work


def test_is_worktree_context_does_not_follow_a_pointer_above_the_ceiling(ambient_repo: tuple[Path, Path]) -> None:
    outer, work = ambient_repo
    # Turn the ambient marker into a linked-worktree pointer: the shape that made the
    # old walk answer "yes, this is a worktree" from inside a hermetic tree.
    (outer / ".git" / "worktrees" / "lane").mkdir(parents=True)
    (outer / ".git" / "HEAD").unlink()
    (outer / ".git").rename(outer / ".git-real")
    (outer / ".git").write_text(f"gitdir: {outer / '.git-real' / 'worktrees' / 'lane'}\n", encoding="utf-8")

    assert is_worktree_context(work) is False


def test_checkout_identity_does_not_adopt_a_repo_above_the_ceiling(ambient_repo: tuple[Path, Path]) -> None:
    _outer, work = ambient_repo

    identity = resolve_checkout_identity(work, Intent.WRITE)

    assert identity.invoking_root == work
    assert identity.canonical_target == work


def test_mission_metadata_has_no_git_anchor_above_the_ceiling(ambient_repo: tuple[Path, Path]) -> None:
    _outer, work = ambient_repo

    assert _has_no_git_anchor(work) is True


def test_mission_metadata_sees_a_git_anchor_below_the_ceiling(ambient_repo: tuple[Path, Path]) -> None:
    _outer, work = ambient_repo
    (work / ".git").mkdir()

    assert _has_no_git_anchor(work) is False


def test_mission_metadata_treats_an_unreadable_ancestor_as_an_anchor(ambient_repo: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch) -> None:
    """Fail-closed: a ``.git`` probe that raises still refuses instead of minting."""
    _outer, work = ambient_repo
    real_exists = Path.exists

    def _raising_exists(self: Path) -> bool:
        if self.name == ".git":
            raise OSError("unreadable ancestor")
        return real_exists(self)

    monkeypatch.setattr(Path, "exists", _raising_exists)

    assert _has_no_git_anchor(work) is False


def test_legacy_charter_gate_does_not_adopt_a_checkout_above_the_ceiling(ambient_repo: tuple[Path, Path]) -> None:
    _outer, work = ambient_repo

    assert find_checkout_root(work) is None


def test_legacy_charter_gate_still_finds_a_checkout_below_the_ceiling(ambient_repo: tuple[Path, Path]) -> None:
    _outer, work = ambient_repo
    (work / ".git").mkdir()

    assert find_checkout_root(work) == work


def test_gitignore_manager_does_not_adopt_control_metadata_above_the_ceiling(ambient_repo: tuple[Path, Path]) -> None:
    _outer, work = ambient_repo

    assert _has_git_control_path(work) is False


def test_gitignore_manager_sees_control_metadata_below_the_ceiling(ambient_repo: tuple[Path, Path]) -> None:
    _outer, work = ambient_repo
    (work / ".git").mkdir()
    (work / ".git" / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")

    assert _has_git_control_path(work) is True


def test_env_file_loader_does_not_adopt_a_repo_above_the_ceiling(ambient_repo: tuple[Path, Path]) -> None:
    _outer, work = ambient_repo

    assert env_file_repo_root(work) is None


def test_env_file_loader_still_finds_a_repo_below_the_ceiling(ambient_repo: tuple[Path, Path]) -> None:
    _outer, work = ambient_repo
    (work / ".kittify").mkdir()

    assert env_file_repo_root(work) == work


def test_coordination_legacy_resolution_does_not_adopt_a_worktree_above_the_ceiling(ambient_repo: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch) -> None:
    _outer, work = ambient_repo
    monkeypatch.chdir(work)

    def _fail(*_args: object, **_kwargs: object) -> bytes:
        raise AssertionError("the walk must not reach git for a worktree above the ceiling")

    monkeypatch.setattr(legacy_resolution.subprocess, "check_output", _fail)

    with pytest.raises(legacy_resolution.BookkeepingLegacyResolutionFailed):
        legacy_resolution._resolve_legacy_lane_destination(work)


# --- the marker-only walks -------------------------------------------------


def test_ledger_posture_does_not_adopt_a_project_above_the_ceiling(ambient_repo: tuple[Path, Path]) -> None:
    _outer, work = ambient_repo

    assert _walk_up_to_kittify_marker(work) is None


def test_ledger_posture_still_finds_a_project_below_the_ceiling(ambient_repo: tuple[Path, Path]) -> None:
    _outer, work = ambient_repo
    (work / ".kittify").mkdir()

    assert _walk_up_to_kittify_marker(work) == work


def test_context_middleware_does_not_adopt_a_project_above_the_ceiling(ambient_repo: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch) -> None:
    _outer, work = ambient_repo
    monkeypatch.chdir(work)

    with pytest.raises(typer.BadParameter, match=r"no \.kittify/"):
        context_middleware._find_repo_root()


def test_context_middleware_still_finds_a_project_below_the_ceiling(ambient_repo: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch) -> None:
    _outer, work = ambient_repo
    (work / ".kittify").mkdir()
    monkeypatch.chdir(work)

    assert context_middleware._find_repo_root() == work


def test_org_layer_does_not_adopt_a_project_above_the_ceiling(ambient_repo: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch) -> None:
    from specify_cli.charter_runtime.lint.checks import org_layer

    _outer, work = ambient_repo
    monkeypatch.chdir(work)

    assert org_layer._find_repo_root_from_drg(object()) is None


def test_org_layer_still_finds_a_project_below_the_ceiling(ambient_repo: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch) -> None:
    from specify_cli.charter_runtime.lint.checks import org_layer

    _outer, work = ambient_repo
    (work / ".kittify").mkdir()
    monkeypatch.chdir(work)

    assert org_layer._find_repo_root_from_drg(object()) == work
