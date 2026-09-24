"""Regression coverage for #4972: idempotent worktree metadata reconciliation.

An idempotent / already-current ``spec-kitty upgrade`` used to mint a FRESH
per-worktree ``last_upgraded_at = now_utc()`` while advancing a live
worktree's ``version`` to the target -- even though the main checkout's own
``last_upgraded_at`` never changed (main was already current). That made
main, coord, and lane branches diverge on this one bookkeeping line of
``.kittify/metadata.yaml``, wedging every in-flight coord mission
(``implement``'s dependency-lane auto-merge conflict; ``merge``'s stale-lane
refusal), both exiting 0 "already up to date".

The fix lives at the shared mint site, ``MigrationRunner._upgrade_worktrees``
(``src/specify_cli/upgrade/runner.py``): when a worktree's dirty state is
driven *solely* by the ``version != target`` bookkeeping bump -- not by a
migration that applied real content, nor by freshly synthesized metadata --
its ``last_upgraded_at`` must align to the main checkout's already-stored
value instead of minting a new one.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
import yaml

from specify_cli.migration.schema_version import REQUIRED_SCHEMA_VERSION
from specify_cli.upgrade.runner import MigrationRunner

pytestmark = [pytest.mark.integration, pytest.mark.git_repo, pytest.mark.regression]

_MAIN_STAMP = "2026-01-01T00:00:00+00:00"
_STALE_VERSION = "3.2.0"
_TARGET_VERSION = "3.2.9"

# Main's fixture already carries REQUIRED_SCHEMA_VERSION (a real upgrade run
# would have stamped it there in the same command invocation, before ever
# reaching `_upgrade_worktrees`) so the byte-identical assertion below is a
# fair like-for-like comparison rather than an artifact of this test calling
# `_upgrade_worktrees` directly instead of the full `upgrade()`/CLI path.
_SCHEMA_VERSION_LINE = f"  schema_version: {REQUIRED_SCHEMA_VERSION}\n" if REQUIRED_SCHEMA_VERSION is not None else ""
_MAIN_METADATA_YAML = (
    "spec_kitty:\n"
    f"  version: '{_TARGET_VERSION}'\n"
    "  initialized_at: '2026-01-01T00:00:00'\n"
    f"  last_upgraded_at: '{_MAIN_STAMP}'\n"
    f"{_SCHEMA_VERSION_LINE}"
    "environment:\n"
    "  python_version: '3.12'\n"
    "  platform: linux\n"
    "  platform_version: ''\n"
    "migrations:\n"
    "  applied: []\n"
)

# The worktree's own copy is behind main's -- the real-world trigger
# (tracer-root-cause.md): a live coord/lane worktree forked before main's
# most recent upgrade, so its local metadata.yaml still shows the stale
# version, while main's own `last_upgraded_at` has not moved since.
_WT_METADATA_YAML = (
    "spec_kitty:\n"
    f"  version: '{_STALE_VERSION}'\n"
    "  initialized_at: '2026-01-01T00:00:00'\n"
    "environment:\n"
    "  python_version: '3.12'\n"
    "  platform: linux\n"
    "  platform_version: ''\n"
    "migrations:\n"
    "  applied: []\n"
)


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True)


def _git_out(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(cwd), *args],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _dirty(wt: Path) -> list[str]:
    out = subprocess.run(
        ["git", "-C", str(wt), "status", "--porcelain"],
        check=True,
        capture_output=True,
        text=True,
    )
    return [ln for ln in out.stdout.splitlines() if ln.strip()]


def _init_repo(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "t")
    (root / "README.md").write_text("# repo\n", encoding="utf-8")
    (root / ".gitignore").write_text(".worktrees/\n", encoding="utf-8")
    (root / ".kittify").mkdir()
    (root / ".kittify" / "metadata.yaml").write_text(_MAIN_METADATA_YAML, encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "init")


def _add_lagging_worktree(root: Path, name: str, branch: str) -> Path:
    wt = root / ".worktrees" / name
    _git(root, "worktree", "add", "-q", "-b", branch, str(wt))
    (wt / ".kittify" / "metadata.yaml").write_text(_WT_METADATA_YAML, encoding="utf-8")
    _git(wt, "commit", "-q", "-am", "stale worktree metadata fixture")
    return wt


def _load_metadata_yaml(kittify_dir: Path) -> dict:
    return yaml.safe_load((kittify_dir / "metadata.yaml").read_text(encoding="utf-8-sig"))


def test_bookkeeping_only_worktree_bump_aligns_to_main_stamp_not_fresh_now(
    tmp_path: Path,
) -> None:
    """#4972: a version-only worktree catch-up must share main's stamp.

    The worktree needs nothing but its ``version`` bumped to catch up with
    ``target_version`` -- no migration applied real content, no metadata was
    synthesized fresh. Its resulting ``last_upgraded_at`` must equal main's
    already-stored stamp (``_MAIN_STAMP``), never a freshly minted
    ``now_utc()``, and the two checkouts' ``.kittify/metadata.yaml`` must end
    byte-identical.
    """
    root = tmp_path / "repo"
    _init_repo(root)
    wt = _add_lagging_worktree(root, "m-lane-a", "kitty/mission-m-lane-a")

    result = MigrationRunner(root)._upgrade_worktrees(_TARGET_VERSION, [], dry_run=False, auto_commit=True)

    assert result["errors"] == []

    main_data = _load_metadata_yaml(root / ".kittify")
    wt_data = _load_metadata_yaml(wt / ".kittify")

    wt_stamp = wt_data["spec_kitty"].get("last_upgraded_at")
    assert wt_stamp == _MAIN_STAMP, (
        f"worktree last_upgraded_at ({wt_stamp!r}) must align to the main checkout's already-stored stamp ({_MAIN_STAMP!r}), not mint a fresh now_utc() (#4972)"
    )
    assert wt_data["spec_kitty"]["version"] == _TARGET_VERSION

    # The whole file must end byte-identical to main's -- the divergence the
    # issue describes is exactly this file drifting between checkouts.
    assert wt_data == main_data

    # The version bump is still real churn: it is still committed on the
    # worktree's own branch (no regression to #2385's per-worktree commit).
    assert _dirty(wt) == [], "worktree must be clean (churn committed) after upgrade"
    assert _git_out(wt, "branch", "--show-current") == "kitty/mission-m-lane-a"
    assert "spec-kitty upgrade" in _git_out(wt, "log", "-1", "--pretty=%s")
    # And main's branch did NOT receive the worktree commit.
    assert "spec-kitty upgrade" not in _git_out(root, "log", "-1", "--pretty=%s")


def test_repeat_upgrade_is_a_true_no_op_once_worktree_has_caught_up(
    tmp_path: Path,
) -> None:
    """A second, truly idempotent run over an already-reconciled worktree
    must not touch its metadata again (or produce a second commit)."""
    root = tmp_path / "repo"
    _init_repo(root)
    wt = _add_lagging_worktree(root, "m-lane-b", "kitty/mission-m-lane-b")

    runner = MigrationRunner(root)
    first = runner._upgrade_worktrees(_TARGET_VERSION, [], dry_run=False, auto_commit=True)
    assert first["errors"] == []

    head_after_first = _git_out(wt, "rev-parse", "HEAD")

    second = runner._upgrade_worktrees(_TARGET_VERSION, [], dry_run=False, auto_commit=True)
    assert second["errors"] == []

    assert _git_out(wt, "rev-parse", "HEAD") == head_after_first, (
        "a repeat upgrade over an already-reconciled worktree must not create a second commit (#4972 no-op-must-stay-no-op)"
    )
    assert _dirty(wt) == []
