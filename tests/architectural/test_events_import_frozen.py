"""Freeze gate: the paths the events import takes do not change in core until the cut-over removes them (ADR 2026-10-29-1 D-9).

The events domain's Java services, its contract modules and tools, and the event-ledger architecture page move to
``spec-kitty/spec-kitty-events``, which imports them with their history. A change landed here after the freeze would
be lost by that import or would need porting by hand, so each imported path is pinned to the git object id it had at
the freeze. The frozen paths belong to different CI routing groups (``ci``, ``corpus``, ``docs``), so the gate is on
the always-on ``architectural-fast`` roster (``special_tiers.architectural.fast_gate`` in
``.github/ci-module-registry.yml``): it runs on every PR shape, whatever paths the diff touches.

Java work on these modules is filed and done in spec-kitty-events. The cut-over PR deletes ``services/`` and this file
together; while ``services/`` is absent the gate passes, so the removal itself is never refused. Every other frozen path must
still exist: renaming or moving one out of the frozen set is refused.

Non-vacuity (standing order 5): a floor on the number of files the pinned tree holds, and a planted change in a scratch
repository that the comparison must flag, plus its negative control.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.architectural

_REPO_ROOT = Path(__file__).resolve().parents[2]
_FROZEN_PATH = "services"
# `git rev-parse HEAD:services` on origin/main 4eecb12414 + the 2026-10-29 merges (b1ef6847bf), the freeze point.
_FROZEN_TREE_ID = "99c06d1dba366c65c1260342c3e6370c8233953e"
# Every other path the events import takes, with its git object id (tree or blob) at the same freeze point.
# contracts/fixtures/ stays in core and is not frozen.
_FROZEN_OBJECTS: dict[str, str] = {
    _FROZEN_PATH: _FROZEN_TREE_ID,
    "contracts/mission-status": "a09d96532581d244b5dd0f295a23cf3705d0cd00",
    "contracts/mission-write": "3f52fa137ee62aa48469c3e0cdbea4efb0f65be3",
    "contracts/_shared": "fa7cc44678491c5b0d87eb4b1441f0945a375ed4",
    "contracts/tools": "6235043e87c4ba3b77f7708e80052b843dcb14c5",
    "contracts/lint": "afea11080e3f206cddf9212e472ac56b047224c7",
    "contracts/gradle": "4a5e2c489b274718b7c0bdd9bc2a2ef009474e93",
    "contracts/README.md": "79436249bde4a84af4467d0b2fb180104e6417c4",
    "contracts/build.gradle": "2ebf317f01cdce199eaef571c7a6c1febb3be3be",
    "contracts/settings.gradle": "c4b8720e271103c957b5a02253b99f6e815f155b",
    "docs/architecture/event-ledger-writers-and-readers.md": "c2943d4997a19d10ffd1289e70220ec602f4e3ac",
}
# 743 files were in the frozen tree; a much smaller count means the gate is reading the wrong tree.
_FROZEN_FILE_FLOOR = 700
_REMEDY = (
    "This path is frozen in core (ADR 2026-10-29-1 D-9): it moves to spec-kitty/spec-kitty-events with its history. "
    "Revert the change and make it in spec-kitty-events. An operator-approved change may instead re-pin "
    "_FROZEN_OBJECTS in the same PR, and is then ported to spec-kitty-events."
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
    """A refusal message when ``path`` at ``HEAD`` differs from its frozen object, else ``None``."""
    tree_id = committed_tree_id(repo, path)
    if tree_id is None:
        if path == _FROZEN_PATH:
            return None  # the cut-over removes services/ together with this gate
        return f"{path} is missing after the freeze: it moves with the events domain and may not be renamed or removed.\n{_REMEDY}"
    if tree_id == frozen_tree_id:
        return None
    if _git(repo, "cat-file", "-t", tree_id).stdout.strip() != "tree":
        return f"{path} changed after the freeze.\n{_REMEDY}"
    changed = _git(repo, "diff", "--name-only", frozen_tree_id, tree_id).stdout.split()
    if not changed:  # the frozen tree object is absent from this shallow clone
        return f"{path}/ changed after the freeze.\n{_REMEDY}"
    listed = "\n".join(f"  {path}/{name}" for name in changed[:20])
    return f"{path}/ changed after the freeze ({len(changed)} file(s)):\n{listed}\n{_REMEDY}"


@pytest.mark.parametrize(("path", "object_id"), sorted(_FROZEN_OBJECTS.items()))
def test_imported_path_is_frozen(path: str, object_id: str) -> None:
    violation = frozen_violation(_REPO_ROOT, path, object_id)
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


def test_planted_blob_change_is_refused(tmp_path: Path) -> None:
    repo, _ = _scratch_repo(tmp_path)
    frozen_blob = committed_tree_id(repo, "README.md")
    assert frozen_blob is not None
    (repo / "README.md").write_text("root, edited\n", encoding="utf-8")
    _commit_all(repo, "edit a frozen file")
    violation = frozen_violation(repo, "README.md", frozen_blob)
    assert violation is not None
    assert "README.md changed after the freeze" in violation


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
    # A frozen path other than services/ may not disappear (rename or move out of the frozen set).
    readme = committed_tree_id(repo, "README.md")
    assert readme is not None
    assert _git(repo, "mv", "README.md", "MOVED.md").returncode == 0
    _commit_all(repo, "move a frozen file")
    missing = frozen_violation(repo, "README.md", readme)
    assert missing is not None
    assert "README.md is missing after the freeze" in missing
