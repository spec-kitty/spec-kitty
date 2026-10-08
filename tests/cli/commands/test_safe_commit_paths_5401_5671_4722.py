"""``spec-kitty safe-commit`` commits exactly the paths it was given (#5401, #5671, #4722).

Every case plants unrelated operator work (an untracked ``secret.env``, a
staged ``staged.txt``, an unstaged edit to tracked ``tracked.txt``) and asserts
it is byte-identical afterwards (SC-006).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = [pytest.mark.git_repo, pytest.mark.non_sandbox, pytest.mark.regression]

BRANCH = "kitty/mission-test-01ABCDEF"
CHECKOUT = Path(__file__).resolve().parents[3]


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


@pytest.fixture
def repo(tmp_path: Path, env: dict[str, str]) -> Path:
    r = tmp_path / "repo"
    r.mkdir()
    _git(r, env, "init", "--template=", "-q", f"--initial-branch={BRANCH}")
    for k, v in (("user.email", "t@example.com"), ("user.name", "T"), ("commit.gpgsign", "false")):
        _git(r, env, "config", k, v)
    (r / ".kittify").mkdir()
    (r / ".kittify" / "config.json").write_text("{}\n")
    (r / "README.md").write_text("# r\n")
    (r / "tracked.txt").write_text("t\n")
    (r / "real.md").write_text("base\n")
    (r / "docs").mkdir()
    (r / "docs" / "old.md").write_text("old\n")
    (r / "other").mkdir()
    (r / "other" / "b.md").write_text("b\n")
    (r / "gone.md").write_text("g\n")
    _git(r, env, "add", "-A")
    _git(r, env, "commit", "-q", "-m", "init")
    # unrelated operator work
    (r / "secret.env").write_text("S=1\n")
    (r / "staged.txt").write_text("staged\n")
    _git(r, env, "add", "staged.txt")
    (r / "tracked.txt").write_text("t\nunstaged edit\n")
    return r


def _operator_snapshot(repo: Path, env: dict[str, str]) -> tuple[bytes, bytes, bytes, str]:
    return (
        (repo / "secret.env").read_bytes(),
        (repo / "staged.txt").read_bytes(),
        (repo / "tracked.txt").read_bytes(),
        _git(repo, env, "diff", "--cached", "--name-status"),
    )


def _run(repo: Path, env: dict[str, str], *args: str) -> tuple[int, dict[str, object]]:
    r = subprocess.run(
        [sys.executable, "-m", "specify_cli", "safe-commit", "--to-branch", BRANCH, "-m", "msg", "--json", *args],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    try:
        payload = json.loads(r.stdout)
    except json.JSONDecodeError:
        payload = {"raw": r.stdout, "stderr": r.stderr}
    return r.returncode, payload


def _symlink(link: Path, target: str) -> None:
    try:
        os.symlink(target, link)
    except (OSError, NotImplementedError):
        pytest.skip("os.symlink unavailable (Windows without developer mode)")


def _assert_operator_work_untouched(repo: Path, env: dict[str, str], before: tuple[bytes, bytes, bytes, str], *, staged_extra: str = "") -> None:
    after = _operator_snapshot(repo, env)
    assert after[:3] == before[:3]
    assert after[3] == before[3] + staged_extra


def test_directory_argument_commits_a_staged_rename_completely(repo: Path, env: dict[str, str]) -> None:
    _git(repo, env, "mv", "docs/old.md", "docs/new.md")
    before = _operator_snapshot(repo, env)
    # the rename is staged; the operator snapshot now contains it, so compare the
    # unrelated part only
    code, payload = _run(repo, env, "docs/")
    assert code == 0, payload
    assert _git(repo, env, "ls-tree", "HEAD", "docs/old.md") == ""
    assert _git(repo, env, "ls-tree", "HEAD", "docs/new.md") != ""
    assert "docs/" not in _git(repo, env, "diff", "--cached", "--name-only")
    assert "R100\tdocs/old.md\tdocs/new.md" in _git(repo, env, "show", "-M", "--name-status", "--format=", "HEAD")
    assert _git(repo, env, "diff", "--cached", "--name-only").split() == ["staged.txt"]
    assert (repo / "secret.env").read_bytes() == before[0]
    assert (repo / "tracked.txt").read_bytes() == before[2]


@pytest.mark.parametrize("shape", ["relative", "absolute", "tracked_repointed", "via_directory"])
def test_symlink_argument_commits_the_link_not_the_target(repo: Path, env: dict[str, str], shape: str) -> None:
    (repo / "other.md").write_text("o\n")
    if shape == "tracked_repointed":
        _symlink(repo / "link.md", "real.md")
        _git(repo, env, "add", "link.md", "other.md")
        _git(repo, env, "commit", "-q", "-m", "link", "--", "link.md", "other.md")
        (repo / "link.md").unlink()
        _symlink(repo / "link.md", "other.md")
        arg, expected = "link.md", ["link.md"]
    elif shape == "via_directory":
        (repo / "links").mkdir()
        _symlink(repo / "links" / "link.md", "../real.md")
        arg, expected = "links/", ["links/link.md"]
    else:
        _symlink(repo / "link.md", "real.md")
        arg, expected = (str(repo / "link.md") if shape == "absolute" else "link.md"), ["link.md"]
    (repo / "real.md").write_text("base\nWIP\n")
    before = _operator_snapshot(repo, env)
    code, payload = _run(repo, env, arg)
    assert code == 0, payload
    for rel in expected:
        assert _git(repo, env, "ls-tree", "HEAD", rel).startswith("120000 ")
    assert _git(repo, env, "show", "HEAD", "--name-only", "--format=").split() == expected
    assert "+WIP" in _git(repo, env, "diff", "HEAD", "--", "real.md")
    _assert_operator_work_untouched(repo, env, before)


def test_symlinked_directory_argument_is_one_link_never_expanded(repo: Path, env: dict[str, str]) -> None:
    (repo / "realdir").mkdir()
    (repo / "realdir" / "wip.md").write_text("w\n")
    _symlink(repo / "linkdir", "realdir")
    before = _operator_snapshot(repo, env)
    code, payload = _run(repo, env, "linkdir")
    assert code == 0, payload
    assert "expansion" not in payload  # the symlinked-directory guard: the link is never treated as a directory to expand
    assert _git(repo, env, "ls-tree", "HEAD", "linkdir").startswith("120000 ")
    names = _git(repo, env, "ls-tree", "-r", "--name-only", "HEAD").split()
    assert not [n for n in names if n.startswith(("linkdir/", "realdir/"))]
    assert (repo / "realdir" / "wip.md").exists()
    _assert_operator_work_untouched(repo, env, before)


@pytest.mark.parametrize(
    ("setup", "outside"),
    [(("docs/a.md", "other/a.md"), "other/a.md"), (("other/b.md", "docs/b.md"), "other/b.md")],
)
def test_rename_crossing_the_directory_argument_is_refused(repo: Path, env: dict[str, str], setup: tuple[str, str], outside: str) -> None:
    src, dst = setup
    if not (repo / src).exists():
        (repo / src).write_text("a\n")
        _git(repo, env, "add", src)
        _git(repo, env, "commit", "-q", "-m", "add")
    _git(repo, env, "mv", src, dst)
    head = _git(repo, env, "rev-parse", "HEAD")
    index = _git(repo, env, "ls-files", "-s")
    code, payload = _run(repo, env, "docs/")
    assert code == 1, payload
    assert outside in str(payload.get("error"))
    assert _git(repo, env, "rev-parse", "HEAD") == head
    assert _git(repo, env, "ls-files", "-s") == index


def test_docs2_is_not_under_docs(repo: Path, env: dict[str, str]) -> None:
    (repo / "docs2").mkdir()
    (repo / "docs2" / "x.md").write_text("x\n")
    _git(repo, env, "add", "docs2/x.md")
    _git(repo, env, "commit", "-q", "-m", "x")
    _git(repo, env, "mv", "docs2/x.md", "docs/x.md")
    code, payload = _run(repo, env, "docs/")
    assert code == 1, payload
    assert "docs2/x.md" in str(payload.get("error"))


def test_lone_unknown_path_is_an_error(repo: Path, env: dict[str, str]) -> None:
    head = _git(repo, env, "rev-parse", "HEAD")
    code, payload = _run(repo, env, "typo.md")
    assert code == 1, payload
    assert "typo.md" in str(payload.get("error"))
    assert _git(repo, env, "rev-parse", "HEAD") == head


def test_deleted_tracked_file_is_still_a_valid_argument(repo: Path, env: dict[str, str]) -> None:
    (repo / "gone.md").unlink()
    before = _operator_snapshot(repo, env)
    code, payload = _run(repo, env, "gone.md")
    assert code == 0, payload
    assert _git(repo, env, "ls-tree", "HEAD", "gone.md") == ""
    _assert_operator_work_untouched(repo, env, before)


def test_batch_with_one_bad_path_names_it_and_commits_nothing(repo: Path, env: dict[str, str]) -> None:
    (repo / "ok.md").write_text("ok\n")
    head = _git(repo, env, "rev-parse", "HEAD")
    before = _operator_snapshot(repo, env)
    code, payload = _run(repo, env, "ok.md", "typo.md")
    assert code == 1, payload
    err = str(payload.get("error"))
    assert "typo.md" in err
    assert "did not match any files" in err
    assert _git(repo, env, "rev-parse", "HEAD") == head
    assert "ok.md" not in _git(repo, env, "diff", "--cached", "--name-only")
    _assert_operator_work_untouched(repo, env, before)
