"""``assert_pack_tree_current``: stale tree fails, absent tree and missing pin are no-ops."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from charter.offering.packs.pack_pin import full_tree_digest, write_pack_pin
from tests._support.pack_tree_guard import assert_pack_tree_current
from tests.charter_offering.conftest_pack_remote import make_pack_remote, write_pack_tree

pytestmark = [pytest.mark.git_repo]


def _checkout(tmp_path: Path, *, snapshot_ok: bool = True) -> Path:
    (tmp_path / "r").mkdir()
    remote = make_pack_remote(tmp_path / "r")
    root = tmp_path / "checkout"
    (root / "packs").mkdir(parents=True)
    write_pack_tree(root / "packs" / "built-in")
    pin = remote.pin()
    pin = replace(pin, snapshot_sha256=full_tree_digest(root / "packs" / "built-in") if snapshot_ok else "0" * 64)
    from charter.offering.packs.pack_clean_digest import clean_tree_digest
    from charter.offering.packs.pack_pin import TreeDigest

    pin = replace(pin, tree_digest=TreeDigest("clean-tree-sha256", clean_tree_digest(root / "packs" / "built-in", level="built-in"), "built-in"))
    write_pack_pin(pin, root / "packs" / "built-in.source.yaml")
    return root


def test_matching_tree_passes(tmp_path: Path) -> None:
    assert_pack_tree_current(_checkout(tmp_path))


def test_mismatching_digest_fails_naming_make_sync_packs(tmp_path: Path) -> None:
    root = _checkout(tmp_path, snapshot_ok=False)
    with pytest.raises(pytest.UsageError, match="make sync-packs"):
        assert_pack_tree_current(root)


def test_clean_digest_blind_edit_fails(tmp_path: Path) -> None:
    root = _checkout(tmp_path)
    (root / "packs" / "built-in" / "templates").mkdir()
    (root / "packs" / "built-in" / "templates" / "x.md").write_text("x\n", encoding="utf-8")
    with pytest.raises(pytest.UsageError, match="make sync-packs"):
        assert_pack_tree_current(root)


def test_absent_tree_is_a_noop(tmp_path: Path) -> None:
    root = _checkout(tmp_path, snapshot_ok=False)
    import shutil

    shutil.rmtree(root / "packs" / "built-in")
    assert_pack_tree_current(root)


def test_checkout_without_a_pin_is_a_noop(tmp_path: Path) -> None:
    assert_pack_tree_current(tmp_path)


def test_unverifiable_pin_fails(tmp_path: Path) -> None:
    root = _checkout(tmp_path)
    pin_path = root / "packs" / "built-in.source.yaml"
    text = "\n".join(line for line in pin_path.read_text(encoding="utf-8").splitlines() if not line.startswith("snapshot_sha256"))
    pin_path.write_text(text + "\n", encoding="utf-8")
    with pytest.raises(pytest.UsageError, match="snapshot_sha256"):
        assert_pack_tree_current(root)
