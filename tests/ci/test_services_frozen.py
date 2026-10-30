"""Freeze gate: ``services/`` in core does not change until the cut-over removes it (ADR 2026-10-29-1 D-9).

The events domain's Java services move to ``spec-kitty/spec-kitty-events``, which imports them with their history.
A change landed here after the freeze would be lost by that import or would need porting by hand, so the committed
``services/`` tree is pinned to the git tree id recorded at the freeze. The gate lives in ``tests/ci`` because a
``services/``-only diff selects the ``ci`` module row (``.github/ci-module-registry.yml``).

Java work on these modules is filed and done in spec-kitty-events. The cut-over PR deletes ``services/`` and this file
together; while ``services/`` is absent the gate passes, so the removal itself is never refused.

Non-vacuity (standing order 5): a floor on the number of files the pinned tree holds, and a planted change in a scratch
repository that the comparison must flag, plus its negative control.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.fast

_REPO_ROOT = Path(__file__).resolve().parents[2]
_FROZEN_PATH = "services"
# `git rev-parse HEAD:services` on origin/main 4eecb12414 + the 2026-10-29 merges (b1ef6847bf), the freeze point.
_FROZEN_TREE_ID = "99c06d1dba366c65c1260342c3e6370c8233953e"
# 743 files were in the frozen tree; a much smaller count means the gate is reading the wrong tree.
_FROZEN_FILE_FLOOR = 700
_REMEDY = (
    "services/ is frozen in core (ADR 2026-10-29-1 D-9): the Java services move to spec-kitty/spec-kitty-events. "
    "Revert the change under services/ and file the Java work in spec-kitty-events."
)


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=False)


def committed_tree_id(repo: Path, path: str) -> str | None:
    """The git tree id of ``path`` at ``HEAD``, or ``None`` when ``HEAD`` has no such path."""
    result = _git(repo, "rev-parse", "--verify", "--quiet", f"HEAD:{path}")
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def frozen_violation(repo: Path, path: str, frozen_tree_id: str) -> str | None:
    """A refusal message when ``path`` at ``HEAD`` differs from the frozen tree, else ``None``."""
    tree_id = committed_tree_id(repo, path)
    if tree_id is None or tree_id == frozen_tree_id:
        return None
    changed = _git(repo, "diff", "--name-only", frozen_tree_id, tree_id).stdout.split()
    listed = "\n".join(f"  {path}/{name}" for name in changed[:20])
    return f"{path}/ changed after the freeze ({len(changed)} file(s)):\n{listed}\n{_REMEDY}"


def test_services_tree_is_frozen() -> None:
    violation = frozen_violation(_REPO_ROOT, _FROZEN_PATH, _FROZEN_TREE_ID)
    assert violation is None, violation


def test_frozen_tree_floor() -> None:
    if committed_tree_id(_REPO_ROOT, _FROZEN_PATH) is None:
        pytest.skip("services/ has been removed by the cut-over; delete this gate with it")
    listing = _git(_REPO_ROOT, "ls-tree", "-r", "--name-only", _FROZEN_TREE_ID)
    assert listing.returncode == 0, f"the frozen tree {_FROZEN_TREE_ID} is not in this clone: {listing.stderr}"
    assert len(listing.stdout.splitlines()) >= _FROZEN_FILE_FLOOR


def _scratch_repo(tmp_path: Path) -> tuple[Path, str]:
    repo = tmp_path / "repo"
    (repo / _FROZEN_PATH / "svc").mkdir(parents=True)
    (repo / _FROZEN_PATH / "svc" / "Main.java").write_text("class Main {}\n", encoding="utf-8")
    (repo / "README.md").write_text("root\n", encoding="utf-8")
    for args in (("init", "-q"), ("add", "-A"), ("-c", "user.name=t", "-c", "user.email=t@e", "commit", "-qm", "seed")):
        assert _git(repo, *args).returncode == 0
    frozen = committed_tree_id(repo, _FROZEN_PATH)
    assert frozen is not None
    return repo, frozen


def _commit_all(repo: Path, message: str) -> None:
    assert _git(repo, "add", "-A").returncode == 0
    assert _git(repo, "-c", "user.name=t", "-c", "user.email=t@e", "commit", "-qm", message).returncode == 0


def test_planted_change_under_services_is_refused(tmp_path: Path) -> None:
    repo, frozen = _scratch_repo(tmp_path)
    (repo / _FROZEN_PATH / "svc" / "Main.java").write_text("class Main { int x; }\n", encoding="utf-8")
    _commit_all(repo, "change the service")
    violation = frozen_violation(repo, _FROZEN_PATH, frozen)
    assert violation is not None
    assert "services/svc/Main.java" in violation
    assert "spec-kitty-events" in violation


def test_change_outside_services_and_removal_pass(tmp_path: Path) -> None:
    repo, frozen = _scratch_repo(tmp_path)
    (repo / "README.md").write_text("root, edited\n", encoding="utf-8")
    _commit_all(repo, "change outside services")
    assert frozen_violation(repo, _FROZEN_PATH, frozen) is None
    assert _git(repo, "rm", "-rq", _FROZEN_PATH).returncode == 0
    _commit_all(repo, "cut-over removes services")
    assert frozen_violation(repo, _FROZEN_PATH, frozen) is None
