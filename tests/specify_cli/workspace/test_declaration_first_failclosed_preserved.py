"""WP03 fail-closed preservation (#6142, Increment 1, FR-007 / C-002 / C-003).

The declaration-first entry FEEDS the existing fail-closed seams; it does not replace or
weaken them. These negative tests assert the refusals still fire unchanged:

* #3128 ``enforce_checkout_identity`` (Seam-B) still raises for a WP-execution write from a
  foreign lane worktree, and still proceeds from the declared lane or the primary.
* #3328 ``resolve_checkout_identity`` (Seam-A) still refuses a WRITE invoked from a
  worktree, and still proceeds for the owning primary checkout.
* ``get_status_read_root``'s worktree-preferring READ contract (C-003) is untouched — the
  entry never collapses a legitimate read to primary.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from mission_runtime import CheckoutIdentityError, enforce_checkout_identity
from specify_cli.core.checkout_identity import Intent, resolve_checkout_identity
from specify_cli.core.paths import get_status_read_root

pytestmark = [pytest.mark.unit]


def test_3128_enforce_checkout_identity_still_refuses_foreign_lane(tmp_path: Path) -> None:
    primary = (tmp_path / "repo").resolve()
    declared_lane = primary / ".worktrees" / "lane-a"
    foreign_lane = primary / ".worktrees" / "lane-b"
    for p in (declared_lane, foreign_lane):
        p.mkdir(parents=True)

    with pytest.raises(CheckoutIdentityError):
        enforce_checkout_identity(
            current_cwd=foreign_lane,
            workspace_path=declared_lane,
            primary_root=primary,
            resolution_kind="lane_workspace",
            mission_slug="m",
            wp_id="WP01",
        )


def test_3128_enforce_checkout_identity_proceeds_from_declared_lane_and_primary(tmp_path: Path) -> None:
    primary = (tmp_path / "repo").resolve()
    declared_lane = primary / ".worktrees" / "lane-a"
    declared_lane.mkdir(parents=True)

    # From the declared lane and from the primary: proceeds (returns None, no raise).
    for cwd in (declared_lane, primary):
        assert (
            enforce_checkout_identity(
                current_cwd=cwd,
                workspace_path=declared_lane,
                primary_root=primary,
                resolution_kind="lane_workspace",
                mission_slug="m",
                wp_id="WP01",
            )
            is None
        )


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True, check=True).stdout.strip()


@pytest.mark.git_repo
def test_3328_resolve_checkout_identity_still_refuses_worktree_write(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "--initial-branch=main")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "T")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / "README.md").write_text("hi\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "init")
    worktree = tmp_path / "wt"
    _git(repo, "worktree", "add", "-b", "lane-x", str(worktree))

    # WRITE from a worktree is refused (not the owner of the primary).
    identity = resolve_checkout_identity(worktree.resolve(), Intent.WRITE)
    assert identity.write_refusal() is not None

    # WRITE from the owning primary checkout proceeds.
    assert resolve_checkout_identity(repo.resolve(), Intent.WRITE).write_refusal() is None


@pytest.mark.git_repo
def test_get_status_read_root_still_prefers_the_worktree(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "--initial-branch=main")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "T")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / "README.md").write_text("hi\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "init")
    worktree = tmp_path / "wt"
    _git(repo, "worktree", "add", "-b", "lane-y", str(worktree))

    # READ root prefers THIS worktree, never collapsing to primary (C-003 untouched).
    assert get_status_read_root(worktree.resolve()) == worktree.resolve()
