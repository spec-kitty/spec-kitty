"""A missing built-in pack tree fails loudly and names the fix (WP03 / T014, T045)."""

from __future__ import annotations

from pathlib import Path, PurePosixPath

import pytest

from charter.offering import pack_paths
from charter.offering.pack_paths import BuiltInPackMissing, PackRootNotFound, built_in_root
from kernel.sibling_paths import SiblingPathNotFound
from tests.charter_offering.conftest import ensure_built_in_pack_present

pytestmark = [pytest.mark.fast, pytest.mark.unit]

_HINT = "make sync-packs"


def _raise_not_found() -> Path:
    raise SiblingPathNotFound(PurePosixPath("packs", "built-in"), Path(__file__))


@pytest.fixture
def tree_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    """The kernel resolver finds no built-in tree (only for the no-pin wheel case)."""
    monkeypatch.setattr(pack_paths, "get_built_in_pack_root", _raise_not_found)


@pytest.fixture
def empty_packs_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A real ``SPEC_KITTY_PACKS_ROOT`` whose ``built-in`` holds only pollution, no ``pack.yaml``.

    The sibling pin marks it as a synced-pack location, exactly like a source checkout.
    """
    (tmp_path / "built-in" / "__pycache__").mkdir(parents=True)
    (tmp_path / "built-in.source.yaml").write_text("# pin present\n", encoding="utf-8")
    monkeypatch.setenv("SPEC_KITTY_PACKS_ROOT", str(tmp_path))
    return tmp_path


def test_source_checkout_with_pin_but_no_tree_raises_built_in_pack_missing(empty_packs_root: Path) -> None:
    with pytest.raises(BuiltInPackMissing) as excinfo:
        built_in_root()
    assert _HINT in str(excinfo.value)


def test_built_in_pack_missing_is_a_pack_root_not_found(empty_packs_root: Path) -> None:
    with pytest.raises(PackRootNotFound):
        built_in_root()


def test_resolver_miss_with_pin_raises_built_in_pack_missing(tree_absent: None) -> None:
    with pytest.raises(BuiltInPackMissing, match=_HINT):
        built_in_root()


def test_partial_tree_without_pack_yaml_raises_from_default_missions_root(empty_packs_root: Path) -> None:
    from charter.offering.missions.repository import MissionTemplateRepository

    with pytest.raises(BuiltInPackMissing, match=_HINT):
        MissionTemplateRepository.default_missions_root()


def test_partial_tree_in_installed_wheel_without_pin_is_not_flagged(empty_packs_root: Path) -> None:
    (empty_packs_root / "built-in.source.yaml").unlink()
    assert built_in_root() == empty_packs_root / "built-in"


def test_installed_wheel_without_pin_keeps_plain_pack_root_not_found(tree_absent: None, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pack_paths, "_source_checkout_pin_present", lambda: False)
    with pytest.raises(PackRootNotFound) as excinfo:
        built_in_root()
    assert not isinstance(excinfo.value, BuiltInPackMissing)


def test_session_guard_raises_instead_of_skipping_when_tree_absent(empty_packs_root: Path) -> None:
    with pytest.raises(BuiltInPackMissing, match=_HINT):
        ensure_built_in_pack_present()


def test_session_guard_passes_when_tree_present() -> None:
    ensure_built_in_pack_present()
