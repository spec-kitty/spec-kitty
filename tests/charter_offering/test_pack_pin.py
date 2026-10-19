"""WP01 -- generalised PackPin model (mission built-in-pack-from-open-packs, #6451).

Covers FR-002 / FR-011 / C-005.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from charter.offering.packs.built_in_pin import BuiltInPin, BuiltInPinError, load_built_in_pin
from charter.offering.packs.pack_clean_digest import clean_tree_digest
from charter.offering.packs.pack_pin import (
    PackPin,
    PackPinError,
    TreeDigest,
    full_tree_digest,
    load_pack_pin,
    validate_subtree,
    verify_pack_pin,
    write_pack_pin,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
BUILT_IN_LOCK = REPO_ROOT / "packs" / "built-in.source.yaml"
INTERNAL_LOCK = REPO_ROOT / "packs" / "internal.source.yaml"
SHA = "7f063aecbdede29d05cc4d5fc9a5b13f9c7434d7"
URL = "https://github.com/spec-kitty/spec-kitty-open-packs.git"
_ZERO_SHA = "0" * 40


def _digest(level: str = "built-in") -> TreeDigest:
    return TreeDigest(algorithm="clean-tree-sha256", value="a" * 64, level=level)


def _pin(subtree: str | None = "built-in") -> PackPin:
    return PackPin(repository=URL, commit=SHA, tree_digest=_digest(), subtree=subtree)


def _write(tmp_path: Path, body: str) -> Path:
    target = tmp_path / "pin.yaml"
    target.write_text(body, encoding="utf-8")
    return target


_BASE = f"repository: {URL}\ncommit: {SHA}\n"


def test_load_with_subtree_and_level(tmp_path: Path) -> None:
    path = _write(tmp_path, _BASE + "subtree: packs/internal\ntree_digest: {algorithm: a, value: b, level: org}\n")
    pin = load_pack_pin(path)
    assert pin.subtree == "packs/internal"
    assert pin.tree_digest.level == "org"


def test_absent_level_defaults_to_built_in(tmp_path: Path) -> None:
    path = _write(tmp_path, _BASE + "subtree: built-in\ntree_digest: {algorithm: a, value: b}\n")
    assert load_pack_pin(path).tree_digest.level == "built-in"


def test_absent_subtree_is_refused_naming_the_field(tmp_path: Path) -> None:
    path = _write(tmp_path, _BASE + "tree_digest: {algorithm: a, value: b}\n")
    with pytest.raises(PackPinError, match="subtree"):
        load_pack_pin(path)


def test_legacy_alias_loader_tolerates_absent_subtree(tmp_path: Path) -> None:
    path = _write(tmp_path, _BASE + "tree_digest: {algorithm: a, value: b}\n")
    assert load_built_in_pin(path).subtree is None


@pytest.mark.parametrize("subtree", ["../x", "a/../b", "/abs/path", "a\\b", "", "C:/x"])
def test_bad_subtree_rejected(subtree: str) -> None:
    with pytest.raises(PackPinError):
        _pin(subtree=subtree)


@pytest.mark.parametrize("commit", ["v1.0.0", "main", "ABCDEF" + "0" * 34, "abc123"])
def test_non_40_hex_commit_rejected(commit: str) -> None:
    with pytest.raises(PackPinError):
        PackPin(repository=URL, commit=commit, tree_digest=_digest(), subtree="built-in")


def test_unknown_level_rejected(tmp_path: Path) -> None:
    path = _write(tmp_path, _BASE + "subtree: built-in\ntree_digest: {algorithm: a, value: b, level: bogus}\n")
    with pytest.raises(PackPinError, match="level"):
        load_pack_pin(path)


def test_round_trip_keeps_field_order_and_header(tmp_path: Path) -> None:
    pin = PackPin(
        repository=URL,
        commit=SHA,
        tree_digest=_digest("org"),
        requires_core=">=4,<5",
        subtree="packs/internal",
    )
    target = tmp_path / "pin.yaml"
    write_pack_pin(pin, target)
    text = target.read_text(encoding="utf-8")
    assert text.startswith("# Pin lockfile")
    keys = [line.split(":")[0] for line in text.splitlines() if line and not line.startswith(("#", " "))]
    assert keys == ["repository", "commit", "subtree", "tree_digest", "requires_core"]
    assert load_pack_pin(target) == pin


def test_alias_is_the_same_class() -> None:
    assert BuiltInPin is PackPin
    assert BuiltInPinError is PackPinError


def test_verify_uses_pin_level(tmp_path: Path) -> None:
    pack = tmp_path / "pack"
    pack.mkdir()
    (pack / "pack.yaml").write_text(
        "pack_id: 01ARWG13C000000000000000FG\npack_version: 1.0.0\nparent_pack: null\nname: x\npack_level: org\n",
        encoding="utf-8",
    )
    value = clean_tree_digest(pack, level="org")
    snapshot = full_tree_digest(pack)
    good = PackPin(repository=URL, commit=SHA, tree_digest=TreeDigest("clean-tree-sha256", value, "org"), subtree="x", snapshot_sha256=snapshot)
    assert verify_pack_pin(good, pack) is True
    no_snapshot = PackPin(repository=URL, commit=SHA, tree_digest=TreeDigest("clean-tree-sha256", value, "org"), subtree="x")
    assert verify_pack_pin(no_snapshot, pack) is False
    bad = PackPin(repository=URL, commit=SHA, tree_digest=TreeDigest("clean-tree-sha256", "0" * 64, "org"), subtree="x", snapshot_sha256=snapshot)
    assert verify_pack_pin(bad, pack) is False


# --- C-005: both open-packs layouts -----------------------------------------


@pytest.mark.parametrize("subtree", ["built-in", "packs/built-in"])
def test_both_open_packs_layouts_validate_and_resolve(tmp_path: Path, subtree: str) -> None:
    repo = tmp_path / "open-packs"
    pack = repo / subtree
    pack.mkdir(parents=True)
    (pack / "pack.yaml").write_text("pack_id: x\n", encoding="utf-8")
    pin = _pin(subtree=subtree)
    assert pin.subtree is not None
    assert (repo / pin.subtree / "pack.yaml").is_file()


def test_committed_built_in_pin_is_https_with_subtree() -> None:
    pin = load_pack_pin(BUILT_IN_LOCK)
    assert pin.repository.startswith("https://")
    assert pin.repository == URL
    assert pin.subtree == "packs/built-in"
    assert pin.tree_digest.level == "built-in"
    assert re.fullmatch(r"[0-9a-f]{40}", pin.commit)  # a pin bump must not break this test


def test_committed_internal_pin_shape() -> None:
    pin = load_pack_pin(INTERNAL_LOCK)
    assert pin.repository == URL
    assert pin.subtree == "packs/internal"
    assert pin.tree_digest.level == "org"
    assert pin.requires_core is None


def test_internal_pin_has_real_sha() -> None:
    """PENDING: fails until the orchestrator supplies the merged open-packs SHA (B5)."""
    pin = load_pack_pin(INTERNAL_LOCK)
    assert pin.commit != _ZERO_SHA, "internal pin commit is still the placeholder; supply merged open-packs SHA"
    assert pin.tree_digest.value != "0" * 64, "internal pin digest is still the placeholder"


_SHARED_BAD_SUBTREES = ["", "-x", "-", "a\\b", "/abs", "../x", "a/../b"]


@pytest.mark.parametrize("repository", ["--upload-pack=evil", "-oProxyCommand=x", "ssh://host/repo", "git@host:o/r.git", "/local/path", ""])
def test_pack_pin_refuses_unsafe_repository(repository: str) -> None:
    with pytest.raises(PackPinError, match="repository"):
        PackPin(repository=repository, commit=SHA, tree_digest=_digest(), subtree="built-in")


@pytest.mark.parametrize("repository", [URL, "file:///srv/packs/remote.git"])
def test_pack_pin_accepts_https_and_file_repository(repository: str) -> None:
    assert PackPin(repository=repository, commit=SHA, tree_digest=_digest(), subtree="built-in").repository == repository


def test_validate_subtree_refuses_leading_dash() -> None:
    with pytest.raises(PackPinError, match="'-'"):
        validate_subtree("-built-in")


@pytest.mark.parametrize("subtree", _SHARED_BAD_SUBTREES)
def test_subtree_validation_parity_with_kernel_fetch(subtree: str, tmp_path: Path) -> None:
    """Whatever the pin model refuses, the kernel fetch check refuses too (and vice versa for these inputs)."""
    from kernel.git.remote import fetch_commit_subtree

    with pytest.raises(PackPinError):
        validate_subtree(subtree)
    with pytest.raises(ValueError, match="subtree"):
        fetch_commit_subtree(URL, SHA, subtree, tmp_path / "dest")
    assert not (tmp_path / "dest").exists()


def test_pin_filename_is_pack_dot_source_yaml() -> None:
    from kernel.pack_tiers import pin_filename

    assert pin_filename("built-in") == BUILT_IN_LOCK.name
    assert pin_filename("internal") == INTERNAL_LOCK.name
