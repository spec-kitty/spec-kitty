"""Tests for ``resolve_pack_chain``, the single org-pack chain authority (#6006)."""

from __future__ import annotations

from pathlib import Path

import pytest

from charter.activation.layer_roots import resolve_pack_chain

pytestmark = [pytest.mark.fast, pytest.mark.doctrine]

_FETCH_REMEDY = "spec-kitty charter fetch"


def _write_config(repo_root: Path, packs: list[tuple[str, Path]]) -> None:
    config_dir = repo_root / ".kittify"
    config_dir.mkdir(parents=True, exist_ok=True)
    lines = ["charter_packs:", "  org:", "    packs:" if packs else "    packs: []"]
    for name, local_path in packs:
        lines.append(f"      - name: {name}")
        lines.append(f"        local_path: {local_path}")
    (config_dir / "config.yaml").write_text("\n".join(lines) + "\n", encoding="utf-8")


@pytest.mark.regression
def test_two_pack_chain_lenient_ordered_then_strict_names_missing_pack(tmp_path: Path) -> None:
    """#6006: one authority serves both postures from the same fixture."""
    pack1 = tmp_path / "pack1"
    pack2 = tmp_path / "pack2"
    pack1.mkdir()
    pack2.mkdir()
    _write_config(tmp_path, [("pack1", pack1), ("pack2", pack2)])

    expected = [pack1.resolve(strict=False), pack2.resolve(strict=False)]
    assert resolve_pack_chain(tmp_path, strict=False) == expected
    assert resolve_pack_chain(tmp_path, strict=True) == expected

    pack2.rmdir()

    assert resolve_pack_chain(tmp_path, strict=False) == [pack1.resolve(strict=False)]
    with pytest.raises(ValueError, match=r"'pack2'.*" + _FETCH_REMEDY):
        resolve_pack_chain(tmp_path, strict=True)


@pytest.mark.parametrize("strict", [False, True])
def test_zero_declared_packs_returns_empty_without_raising(tmp_path: Path, strict: bool) -> None:
    _write_config(tmp_path, [])
    assert resolve_pack_chain(tmp_path, strict=strict) == []


@pytest.mark.parametrize("strict", [False, True])
def test_absent_config_returns_empty_without_raising(tmp_path: Path, strict: bool) -> None:
    assert resolve_pack_chain(tmp_path, strict=strict) == []
