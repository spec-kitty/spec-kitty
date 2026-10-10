"""Guards for the owned-checkout create birth write (#5988).

An owned-checkout create must anchor the ``meta.json`` birth write's lock on the owned
checkout (``P``) and must not re-derive the repository root (``R``) from ``P``'s path.
Each guard carries a same-fixture positive control so it cannot pass vacuously.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest

from specify_cli.core.mission_creation_meta import _write_create_meta
from specify_cli.status import mission_write_lock

pytestmark = pytest.mark.fast

_SLUG = "demo-01ABCDEF"


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


@pytest.fixture
def linked_checkout(tmp_path: Path) -> tuple[Path, Path, Path]:
    """``(R, P, P_feature_dir)``: a repository root and a real linked worktree of it."""
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "--initial-branch=main")
    _git(root, "config", "user.email", "t@example.invalid")
    _git(root, "config", "user.name", "T")
    (root / "README.md").write_text("r\n", encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-m", "init")
    owned = tmp_path / "owned"
    _git(root, "worktree", "add", "-b", "owned-branch", str(owned))
    feature_dir = owned / "kitty-specs" / _SLUG
    feature_dir.mkdir(parents=True)
    return root, owned, feature_dir


def test_write_create_meta_plumbs_write_root_into_the_lock(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[dict[str, Any]] = []
    real = mission_write_lock

    def _recording(*args: Any, **kwargs: Any) -> Any:
        seen.append(kwargs)
        return real(*args, **kwargs)

    monkeypatch.setattr("specify_cli.status.mission_write_lock", _recording)
    monkeypatch.setattr("specify_cli.mission_metadata.write_meta", lambda *_a, **_k: None)  # the lock call is under test, not the schema
    feature_dir = tmp_path / "kitty-specs" / _SLUG
    feature_dir.mkdir(parents=True)

    _write_create_meta(feature_dir, {"mission_slug": _SLUG}, None, write_root=tmp_path)
    _write_create_meta(feature_dir, {"mission_slug": _SLUG}, None)

    assert seen[0]["repo_root"] == tmp_path
    assert seen[1]["repo_root"] is None  # positive control: the plumbing is what sets it
    assert all(call["birth"] is True for call in seen)


def test_birth_lock_on_owned_checkout_never_resolves_the_repository_root(linked_checkout: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch) -> None:
    _root, owned, feature_dir = linked_checkout

    def _forbidden(*_a: object, **_k: object) -> Path:
        raise AssertionError("resolved the repository root from the owned checkout")

    monkeypatch.setattr("specify_cli.core.paths.get_main_repo_root", _forbidden)

    with mission_write_lock(feature_dir, repo_root=owned, birth=True):
        pass

    # Positive control (same fixture): without ``birth`` the key read DOES resolve the root,
    # so the guard above fails if the birth path ever regresses to it.
    with pytest.raises(AssertionError, match="resolved the repository root"), mission_write_lock(feature_dir, repo_root=owned):
        pass
