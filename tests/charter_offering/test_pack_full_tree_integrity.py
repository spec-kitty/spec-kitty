"""Whole-tree pack integrity (#6451): the pin's ``snapshot_sha256`` covers files ``clean_tree_digest`` skips.

``clean_tree_digest`` ignores ``missions/``, ``templates/``, ``presets/``, ``pack-manifest.yaml``
and dotfiles. Every verification point must also compare the full-tree digest.
"""

from __future__ import annotations

import importlib.util
import shutil
from dataclasses import replace
from pathlib import Path
from types import ModuleType

import pytest

from charter.offering.packs.pack_fetch import (
    PACK_PIN_INVALID,
    PackSyncError,
    PackTreeStatus,
    check_pack,
    fetch_to_cache,
    place_pack,
)
from charter.offering.packs.pack_pin import TreeDigest, full_tree_digest, load_pack_pin, verify_pack_pin, write_pack_pin
from tests.charter_offering.conftest_pack_remote import PackRemote, git, write_pack_tree

pytestmark = [pytest.mark.git_repo]

_PROMPT = Path("missions") / "mission-steps" / "software-dev" / "research" / "prompt.md"
_REPO_ROOT = Path(__file__).resolve().parents[2]


def _with_missions(tmp_path: Path) -> PackRemote:
    """A remote whose pack carries a ``missions/`` prompt that the clean digest does not see."""
    work = tmp_path / "remote-work"
    work.mkdir()
    git(work, "init", "-q", "-b", "main")
    write_pack_tree(work / "built-in")
    prompt = work / "built-in" / _PROMPT
    prompt.parent.mkdir(parents=True)
    prompt.write_text("research prompt\n", encoding="utf-8")
    (work / "built-in" / "pack-manifest.yaml").write_text("schema: 1\n", encoding="utf-8")
    git(work, "add", "-A")
    git(work, "commit", "-q", "-m", "pack")
    sha = git(work, "rev-parse", "HEAD")
    bare = tmp_path / "remote.git"
    git(tmp_path, "clone", "-q", "--bare", str(work), str(bare))
    git(bare, "config", "uploadpack.allowAnySHA1InWant", "true")
    from charter.offering.packs.pack_clean_digest import clean_tree_digest
    from kernel.pack_tiers import BUILT_IN

    root = work / "built-in"
    return PackRemote(
        bare=bare,
        url=bare.as_uri(),
        sha=sha,
        digest=clean_tree_digest(root, level=BUILT_IN),
        subtree="built-in",
        snapshot=full_tree_digest(root),
    )


def _placed(tmp_path: Path) -> tuple[PackRemote, Path]:
    remote = _with_missions(tmp_path)
    pin = remote.pin()
    dest = tmp_path / "packs" / "built-in"
    place_pack(fetch_to_cache(pin, cache_root=tmp_path / "cache"), dest, pin)
    assert check_pack(pin, dest) is PackTreeStatus.OK
    return remote, dest


def _edit_prompt(root: Path) -> None:
    (root / _PROMPT).write_text("poisoned\n", encoding="utf-8")


def _add_template(root: Path) -> None:
    (root / "templates").mkdir(exist_ok=True)
    (root / "templates" / "evil.md").write_text("evil\n", encoding="utf-8")


def _add_dotfile(root: Path) -> None:
    (root / ".hidden").write_text("x\n", encoding="utf-8")


def _edit_manifest(root: Path) -> None:
    (root / "pack-manifest.yaml").write_text("schema: 2\n", encoding="utf-8")


def _delete_missions(root: Path) -> None:
    shutil.rmtree(root / "missions")


_TAMPERS = [_edit_prompt, _add_template, _add_dotfile, _edit_manifest, _delete_missions]


@pytest.mark.parametrize("tamper", _TAMPERS)
def test_check_pack_is_stale_when_a_clean_digest_blind_file_changes(tmp_path: Path, tamper) -> None:  # type: ignore[no-untyped-def]  # noqa: ANN001
    remote, dest = _placed(tmp_path)
    tamper(dest)
    assert check_pack(remote.pin(), dest) is PackTreeStatus.STALE


@pytest.mark.parametrize("tamper", _TAMPERS)
def test_tampered_cache_entry_is_refetched_not_placed(tmp_path: Path, tamper) -> None:  # type: ignore[no-untyped-def]  # noqa: ANN001
    remote = _with_missions(tmp_path)
    pin = remote.pin()
    cache = tmp_path / "cache"
    cached = fetch_to_cache(pin, cache_root=cache)
    tamper(cached)
    again = fetch_to_cache(pin, cache_root=cache)
    assert check_pack(pin, again) is PackTreeStatus.OK
    assert full_tree_digest(again) == pin.snapshot_sha256, "the poisoned entry must have been replaced by a fresh fetch"


def test_tampered_cache_offline_is_refused(tmp_path: Path) -> None:
    remote = _with_missions(tmp_path)
    cache = tmp_path / "cache"
    cached = fetch_to_cache(remote.pin(), cache_root=cache)
    _edit_prompt(cached)
    with pytest.raises(PackSyncError):
        fetch_to_cache(remote.pin(), offline=True, cache_root=cache)


def test_place_pack_refuses_a_cache_poisoned_in_a_blind_file(tmp_path: Path) -> None:
    remote = _with_missions(tmp_path)
    pin = remote.pin()
    cached = fetch_to_cache(pin, cache_root=tmp_path / "cache")
    _add_template(cached)
    dest = tmp_path / "packs" / "built-in"
    with pytest.raises(PackSyncError):
        place_pack(cached, dest, pin)
    assert not dest.exists()


def test_pin_without_snapshot_sha256_is_pack_pin_invalid(tmp_path: Path) -> None:
    remote = _with_missions(tmp_path)
    pin = replace(remote.pin(), snapshot_sha256=None)
    dest = tmp_path / "packs" / "built-in"
    for call in (
        lambda: check_pack(pin, dest),
        lambda: fetch_to_cache(pin, cache_root=tmp_path / "cache"),
        lambda: place_pack(tmp_path, dest, pin),
    ):
        with pytest.raises(PackSyncError) as info:
            call()
        assert info.value.code == PACK_PIN_INVALID
    assert verify_pack_pin(pin, tmp_path) is False


def test_unknown_digest_algorithm_is_pack_pin_invalid(tmp_path: Path) -> None:
    remote = _with_missions(tmp_path)
    pin = remote.pin()
    other = replace(pin, tree_digest=TreeDigest(algorithm="sha1", value=pin.tree_digest.value, level=pin.tree_digest.level))
    with pytest.raises(PackSyncError) as info:
        check_pack(other, tmp_path / "x")
    assert info.value.code == PACK_PIN_INVALID


def test_bytecode_is_exempt_from_the_full_tree_digest(tmp_path: Path) -> None:
    _, dest = _placed(tmp_path)
    before = full_tree_digest(dest)
    (dest / "__pycache__").mkdir()
    (dest / "__pycache__" / "x.cpython-311.pyc").write_bytes(b"\0")
    (dest / "missions" / "y.pyc").write_bytes(b"\0")
    assert full_tree_digest(dest) == before


def test_symlink_is_refused_by_the_full_tree_digest(tmp_path: Path) -> None:
    remote, dest = _placed(tmp_path)
    (dest / "link").symlink_to("missions")
    assert check_pack(remote.pin(), dest) is PackTreeStatus.STALE
    with pytest.raises(OSError, match="symlink"):
        full_tree_digest(dest)


def test_check_pack_is_read_only_and_leaves_an_interrupted_swap_alone(tmp_path: Path) -> None:
    remote, dest = _placed(tmp_path)
    aside = dest.parent / f".{dest.name}.aside"
    dest.rename(aside)
    assert check_pack(remote.pin(), dest) is PackTreeStatus.MISSING
    assert aside.is_dir() and not dest.exists()


def _hatch_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("hatch_build_under_test", _REPO_ROOT / "hatch_build.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_build_hook_refuses_a_tampered_prompt_in_an_sdist_layout(tmp_path: Path) -> None:
    pytest.importorskip("hatchling")
    remote, dest = _placed(tmp_path)
    root = tmp_path / "sdist"
    (root / "packs").mkdir(parents=True)
    shutil.copytree(dest, root / "packs" / "built-in")
    write_pack_pin(remote.pin(), root / "packs" / "built-in.source.yaml")
    hatch = _hatch_module()
    assert hatch.ensure_built_in_tree(root) == root / "packs" / "built-in"
    _edit_prompt(root / "packs" / "built-in")
    with pytest.raises(PackSyncError):
        hatch.ensure_built_in_tree(root)


def test_committed_pins_carry_a_snapshot_digest() -> None:
    for name in ("built-in", "internal"):
        pin = load_pack_pin(_REPO_ROOT / "packs" / f"{name}.source.yaml")
        assert pin.snapshot_sha256 is not None and len(pin.snapshot_sha256) == 64
