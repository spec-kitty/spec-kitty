"""``spec-commit`` and the owned checkout keep a symlink as the link (#5671)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from mission_runtime import OwnedCheckout
from mission_runtime.owned_checkout import OwnedCheckoutPathRefused
from tests._owned_fixtures import mint_test_fact

pytestmark = [pytest.mark.git_repo, pytest.mark.non_sandbox, pytest.mark.regression]

SLUG = "m1"
CHECKOUT = Path(__file__).resolve().parents[3]
META = {
    "mission_id": "01KVMBD6HTBP3A9Y5T4EQ80RA9",
    "mission_slug": SLUG,
    "mid8": "01KVMBD6",
    "mission_type": "software-dev",
    "friendly_name": "M1",
    "target_branch": "work",
}


@pytest.fixture
def env(tmp_path: Path) -> dict[str, str]:
    assert (CHECKOUT / "src" / "specify_cli").is_dir()
    e = {k: v for k, v in os.environ.items() if not k.startswith(("GIT_", "SPEC_KITTY_"))}
    home = tmp_path / "home"
    home.mkdir()
    e.update(
        SPEC_KITTY_NO_UPGRADE_CHECK="1",
        HOME=str(home),
        USERPROFILE=str(home),
        XDG_CONFIG_HOME=str(home / "cfg"),
        XDG_CACHE_HOME=str(home / "cache"),
        XDG_DATA_HOME=str(home / "data"),
        XDG_STATE_HOME=str(home / "state"),
        GIT_CONFIG_NOSYSTEM="1",
        GIT_CONFIG_GLOBAL=str(home / ".gitconfig"),
        PYTHONPATH=str(CHECKOUT / "src"),
    )
    return e


def _git(repo: Path, env: dict[str, str], *args: str) -> str:
    r = subprocess.run(["git", *args], cwd=repo, env=env, capture_output=True, text=True, check=False)
    assert r.returncode == 0, f"git {args}: {r.stderr}"
    return r.stdout


def _symlink(link: Path, target: str) -> None:
    try:
        os.symlink(target, link)
    except (OSError, NotImplementedError):
        pytest.skip("os.symlink unavailable (Windows without developer mode)")


@pytest.fixture
def repo(tmp_path: Path, env: dict[str, str]) -> Path:
    r = tmp_path / "repo"
    (r / ".kittify").mkdir(parents=True)
    (r / ".kittify" / "config.json").write_text("{}\n")
    mdir = r / "kitty-specs" / SLUG
    mdir.mkdir(parents=True)
    (mdir / "meta.json").write_text(json.dumps(META))
    (mdir / "notes.md").write_text("n\n")
    (mdir / "assets").mkdir()
    (mdir / "assets" / "a.txt").write_text("a\n")
    (r / "tracked.txt").write_text("t\n")
    _git(r, env, "init", "--template=", "-q", "-b", "work")
    for k, v in (("user.email", "t@example.com"), ("user.name", "T"), ("commit.gpgsign", "false")):
        _git(r, env, "config", k, v)
    _git(r, env, "add", "-A")
    _git(r, env, "commit", "-q", "-m", "init")
    (r / "secret.env").write_text("S=1\n")
    (r / "tracked.txt").write_text("t\nunstaged\n")
    return r


def _spec_commit(repo: Path, env: dict[str, str], arg: str) -> tuple[int, str]:
    r = subprocess.run(
        [sys.executable, "-m", "specify_cli", "spec-commit", arg, "-m", "msg", "--json"],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    return r.returncode, r.stdout + r.stderr


def test_spec_commit_commits_the_link_not_the_target(repo: Path, env: dict[str, str]) -> None:
    mdir = repo / "kitty-specs" / SLUG
    _symlink(mdir / "notes-link.md", "notes.md")
    (mdir / "notes.md").write_text("n\nWIP\n")
    code, out = _spec_commit(repo, env, f"kitty-specs/{SLUG}/notes-link.md")
    assert code == 0, out
    rel = f"kitty-specs/{SLUG}/notes-link.md"
    assert _git(repo, env, "ls-tree", "HEAD", rel).startswith("120000 ")
    assert _git(repo, env, "show", "HEAD", "--name-only", "--format=").split() == [rel]
    assert "+WIP" in _git(repo, env, "diff", "HEAD", "--", f"kitty-specs/{SLUG}/notes.md")
    assert (repo / "secret.env").read_text() == "S=1\n"
    assert (repo / "tracked.txt").read_text() == "t\nunstaged\n"


def test_spec_commit_accepts_a_symlinked_directory_as_one_link(repo: Path, env: dict[str, str]) -> None:
    mdir = repo / "kitty-specs" / SLUG
    _symlink(mdir / "assets-link", "assets")
    (mdir / "assets" / "wip.txt").write_text("w\n")
    code, out = _spec_commit(repo, env, f"kitty-specs/{SLUG}/assets-link")
    assert code == 0, out
    rel = f"kitty-specs/{SLUG}/assets-link"
    assert _git(repo, env, "ls-tree", "HEAD", rel).startswith("120000 ")
    assert _git(repo, env, "show", "HEAD", "--name-only", "--format=").split() == [rel]


def test_spec_commit_refuses_a_real_directory(repo: Path, env: dict[str, str]) -> None:
    head = _git(repo, env, "rev-parse", "HEAD")
    code, out = _spec_commit(repo, env, f"kitty-specs/{SLUG}/assets")
    assert code == 1, out
    assert "not directories" in out
    assert _git(repo, env, "rev-parse", "HEAD") == head


def test_spec_commit_refuses_a_symlink_loop(repo: Path, env: dict[str, str]) -> None:
    mdir = repo / "kitty-specs" / SLUG
    _symlink(mdir / "a", "b")
    _symlink(mdir / "b", "a")
    head = _git(repo, env, "rev-parse", "HEAD")
    code, out = _spec_commit(repo, env, f"kitty-specs/{SLUG}/a")
    assert code != 0, out
    assert _git(repo, env, "rev-parse", "HEAD") == head
    assert _git(repo, env, "ls-files", "--", f"kitty-specs/{SLUG}/a") == ""


@pytest.fixture
def owned(tmp_path: Path) -> tuple[OwnedCheckout, Path]:
    repository = tmp_path / "primary"
    repository.mkdir()
    owned_root = tmp_path / "owned"
    mission_dir = owned_root / "kitty-specs" / SLUG
    mission_dir.mkdir(parents=True)
    (mission_dir / "real.md").write_text("x")
    fact = mint_test_fact(
        repository_root=repository,
        owned_root=owned_root,
        mission_dir=mission_dir,
        mission_slug=SLUG,
        write_branch="work",
    )
    return fact, mission_dir


def test_owned_files_accepts_an_in_mission_link_even_when_it_points_outside(owned: tuple[OwnedCheckout, Path], tmp_path: Path) -> None:
    fact, mission_dir = owned
    (tmp_path / "outside.md").write_text("o")
    _symlink(mission_dir / "out-link.md", str(tmp_path / "outside.md"))
    [got] = fact.files([mission_dir / "out-link.md"])
    assert got.name == "out-link.md"
    assert got.parent == mission_dir.resolve()


def test_owned_files_refuses_a_link_whose_parent_lives_outside_the_mission(owned: tuple[OwnedCheckout, Path], tmp_path: Path) -> None:
    fact, mission_dir = owned
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (elsewhere / "f.md").write_text("f")
    _symlink(mission_dir / "dirlink", str(elsewhere))
    with pytest.raises(OwnedCheckoutPathRefused):
        fact.files([mission_dir / "dirlink" / "f.md"])


def test_owned_files_refuses_a_looping_leaf(owned: tuple[OwnedCheckout, Path]) -> None:
    fact, mission_dir = owned
    _symlink(mission_dir / "a", "b")
    _symlink(mission_dir / "b", "a")
    with pytest.raises(OwnedCheckoutPathRefused):
        fact.files([mission_dir / "a"])
