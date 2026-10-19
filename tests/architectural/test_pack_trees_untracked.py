"""Gate: ``packs/built-in`` and ``packs/internal`` are fetched from open-packs, never tracked (#6451, FR-001).

Both trees are produced by ``make sync-packs`` from the pins ``packs/built-in.source.yaml`` /
``packs/internal.source.yaml``. A tracked copy would be a second source of truth, so
``git ls-files`` must list nothing under either path and both must be gitignored.

Retired drift gate (``tests/architectural/test_built_in_drift_gate.py``, #6421, drift part of #6364).
Each assertion it made has a named replacement in the pin gate:

* ``test_committed_tree_matches_pin`` (unedited tree passes ``vendor --check``) ->
  ``tests/charter_offering/test_pack_vendor.py::test_check_in_sync_exits_zero_offline`` and
  ``tests/charter_offering/test_pack_fetch.py::test_check_pack_ok_stale_missing`` (OK branch);
  runtime form: ``scripts/sync_packs.py --check`` / ``spec-kitty charter pack vendor --check``,
  both built on ``pack_fetch.check_pack``.
* ``test_one_byte_hand_edit_reds_the_gate_with_remedy`` (an edit fails and names the remedy) ->
  ``tests/charter_offering/test_pack_vendor.py::test_check_drift_fails_with_remedy_and_does_not_mutate``
  and ``test_pack_fetch.py::test_check_pack_ok_stale_missing`` (STALE branch).
* The wheel-side digest ratchet stays in
  ``tests/cross_cutting/packaging/test_built_in_release_parity.py``.

``test_trees_are_untracked`` was authored red-first (xfail) and went green when WP09 ran
``git rm -r --cached`` on the pack trees.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.architectural

_REPO_ROOT = Path(__file__).resolve().parents[2]
_PACK_PATHS = ("packs/built-in", "packs/internal")


def _git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, check=False)


def _require_git_checkout(root: Path) -> None:
    probe = _git(root, "rev-parse", "--is-inside-work-tree")
    if probe.returncode != 0 or probe.stdout.strip() != "true":
        pytest.skip("not inside a git checkout (sdist)")


def tracked_pack_files(root: Path) -> list[str]:
    """Return tracked paths under the fetched pack trees."""
    result = _git(root, "ls-files", *_PACK_PATHS)
    assert result.returncode == 0, result.stderr
    return [line for line in result.stdout.splitlines() if line]


def unignored_pack_paths(root: Path) -> list[str]:
    """Return pack paths that .gitignore does not cover (``--no-index`` so tracked files still count)."""
    missing = []
    for path in _PACK_PATHS:
        probe = _git(root, "check-ignore", "--no-index", "-q", f"{path}/pack.yaml")
        if probe.returncode != 0:
            missing.append(path)
    return missing


def test_trees_are_untracked() -> None:
    _require_git_checkout(_REPO_ROOT)
    tracked = tracked_pack_files(_REPO_ROOT)
    assert not tracked, f"{len(tracked)} tracked files under {_PACK_PATHS}; first: {tracked[:3]}"


def test_trees_are_gitignored() -> None:
    _require_git_checkout(_REPO_ROOT)
    assert unignored_pack_paths(_REPO_ROOT) == [], "add /packs/built-in/ and /packs/internal/ to .gitignore"


def test_gate_detects_a_tracked_tree(tmp_path: Path) -> None:
    """Non-vacuity: a planted tracked file under a pack path is reported."""
    _git(tmp_path, "init", "-q")
    planted = tmp_path / "packs" / "built-in" / "pack.yaml"
    planted.parent.mkdir(parents=True)
    planted.write_text("x: 1\n", encoding="utf-8")
    _git(tmp_path, "add", "-f", "packs/built-in/pack.yaml")

    assert tracked_pack_files(tmp_path) == ["packs/built-in/pack.yaml"]
    assert unignored_pack_paths(tmp_path) == list(_PACK_PATHS)
