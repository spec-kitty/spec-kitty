"""An org asset sidecar whose ``path`` escapes its pack's ``assets/`` root is a finding (#6418, FR-007).

``spec-kitty doctor charter-packs`` reported an org pack healthy (RC=0) when one
of its ``assets/*.asset.yaml`` sidecars named ``path: ../../../../etc/hostname``,
although :meth:`AssetRepository.resolve_path` refuses that sidecar with
:class:`AssetPathEscapeError`. The predicate under test,
:func:`find_asset_path_escapes`, resolves every org-provenance asset of ONE pack
through that repository; :func:`find_org_asset_path_escapes` pairs every loaded
fragment with its pack's effective root from the registry.

RED before the fix: neither name existed, so this module failed to import.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
import yaml

from charter.activation.drg_activation import find_org_asset_path_escapes, load_org_drg
from charter.offering.assets import AssetPathEscape, AssetRepository, find_asset_path_escapes

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_PACK_ID = "01ARZ3NDEKTSV4RRFFQ69G5FAV"
_ESCAPING = "../../../../etc/hostname"


def _write_sidecar(assets_dir: Path, asset_id: str, blob_path: str) -> None:
    assets_dir.mkdir(parents=True, exist_ok=True)
    (assets_dir / f"{asset_id}.asset.yaml").write_text(yaml.safe_dump({"id": asset_id, "mime": "text/plain", "path": blob_path}), encoding="utf-8")


def _make_pack(pack_root: Path, assets: dict[str, str], name: str = "acme") -> Path:
    """Write a minimal org pack (``pack.yaml``, empty fragment, one sidecar per *assets* entry)."""
    (pack_root / "drg").mkdir(parents=True, exist_ok=True)
    (pack_root / "pack.yaml").write_text(f"pack_id: {_PACK_ID}\nname: {name}\npack_level: org\n", encoding="utf-8")
    (pack_root / "drg" / "fragment.yaml").write_text(yaml.safe_dump({"nodes": [], "edges": []}), encoding="utf-8")
    for asset_id, blob_path in assets.items():
        _write_sidecar(pack_root / "assets", asset_id, blob_path)
    return pack_root


def test_dot_dot_asset_path_is_an_escape(tmp_path: Path) -> None:
    pack_root = _make_pack(tmp_path / "pack", {"team-logo": _ESCAPING})

    escapes = find_asset_path_escapes("acme", pack_root)

    assert len(escapes) == 1
    escape = escapes[0]
    assert (escape.code, escape.pack, escape.asset, escape.path) == ("ORG_ASSET_PATH_ESCAPE", "acme", "team-logo", _ESCAPING)
    assert ".." in escape.reason
    assert escape.message == (f"org pack 'acme': asset 'team-logo' path '{_ESCAPING}' is not contained in the pack's assets/ root: {escape.reason}")
    assert escape.as_dict() == {
        "code": "ORG_ASSET_PATH_ESCAPE",
        "pack": "acme",
        "asset": "team-logo",
        "path": _ESCAPING,
        "reason": escape.reason,
    }


def test_absolute_asset_path_is_an_escape(tmp_path: Path) -> None:
    pack_root = _make_pack(tmp_path / "pack", {"team-logo": "/etc/hostname"})

    escapes = find_asset_path_escapes("acme", pack_root)

    assert [(e.asset, e.path) for e in escapes] == [("team-logo", "/etc/hostname")]
    assert "absolute" in escapes[0].reason


@pytest.mark.parametrize("materialise", [False, True], ids=["missing-blob", "present-blob"])
def test_contained_asset_path_is_not_an_escape(tmp_path: Path, materialise: bool) -> None:
    pack_root = _make_pack(tmp_path / "pack", {"team-logo": "img/logo.png", "bad": _ESCAPING})
    if materialise:
        (pack_root / "assets" / "img").mkdir(parents=True)
        (pack_root / "assets" / "img" / "logo.png").write_bytes(b"\x89PNG")

    # Same fixture, positive control: the escaping sibling IS reported, the contained one is not.
    assert [e.asset for e in find_asset_path_escapes("acme", pack_root)] == ["bad"]


@pytest.mark.skipif(not hasattr(os, "symlink"), reason="os.symlink unavailable")
def test_symlink_resolving_outside_the_assets_root_is_an_escape(tmp_path: Path) -> None:
    pack_root = _make_pack(tmp_path / "pack", {"team-logo": "link.png", "plain": "plain.png"})
    # Inside the pack root, outside its assets/ root: the anchor is assets/, not the pack.
    (pack_root / "elsewhere.png").write_bytes(b"x")
    try:
        (pack_root / "assets" / "link.png").symlink_to(pack_root / "elsewhere.png")
    except OSError as exc:  # pragma: no cover - platform without symlink privilege
        pytest.skip(f"cannot create symlink: {exc}")

    escapes = find_asset_path_escapes("acme", pack_root)

    assert [e.asset for e in escapes] == ["team-logo"]
    assert "outside" in escapes[0].reason


def test_built_in_asset_is_never_reported(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Only org-provenance items are judged, even when a built-in item would not resolve."""
    built_in = tmp_path / "shipped" / "assets" / "built-in"
    _write_sidecar(built_in, "shipped-bad", "../../../escape.txt")
    monkeypatch.setattr(AssetRepository, "_default_built_in_dir", staticmethod(lambda: built_in))
    # Guard the premise: the built-in item is loaded and really does not resolve.
    repo = AssetRepository()
    assert repo.get_provenance("shipped-bad") == "built-in"
    with pytest.raises(Exception, match="escapes"):
        repo.resolve_path("shipped-bad")
    pack_root = _make_pack(tmp_path / "pack", {"team-logo": _ESCAPING})

    assert [e.asset for e in find_asset_path_escapes("acme", pack_root)] == ["team-logo"]


def test_nul_byte_path_is_reported_and_does_not_hide_another_escape(tmp_path: Path) -> None:
    """A path ``Path.resolve`` cannot handle (ValueError) is a finding of that asset only."""
    pack_root = _make_pack(tmp_path / "pack", {"a-nul": "img/a\x00b.png", "b-escape": _ESCAPING, "c-fine": "img/c.png"})
    # Guard the premise: the sidecar loaded with the NUL byte intact.
    assert AssetRepository(org_dirs=[pack_root / "assets"]).get("a-nul") is not None

    escapes = find_asset_path_escapes("acme", pack_root)

    assert sorted(e.asset for e in escapes) == ["a-nul", "b-escape"]
    nul = next(e for e in escapes if e.asset == "a-nul")
    assert "null" in nul.reason


def test_pack_without_assets_dir_has_no_escape(tmp_path: Path) -> None:
    pack_root = _make_pack(tmp_path / "pack", {})

    assert find_asset_path_escapes("acme", pack_root) == []


def _write_registry(repo: Path, packs: list[dict[str, str]]) -> None:
    (repo / ".kittify").mkdir(parents=True, exist_ok=True)
    (repo / ".kittify" / "config.yaml").write_text(yaml.safe_dump({"charter_packs": {"org": {"packs": packs}}}), encoding="utf-8")


def test_registry_aware_check_names_only_the_escaping_pack(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    bad = _make_pack(tmp_path / "bad", {"team-logo": _ESCAPING}, name="bad")
    good = _make_pack(tmp_path / "good", {"fine-logo": "fine.png"}, name="good")
    _write_registry(repo, [{"name": "bad", "local_path": str(bad)}, {"name": "good", "local_path": str(good)}])

    escapes = find_org_asset_path_escapes(repo, load_org_drg(repo))

    assert [(e.pack, e.asset) for e in escapes] == [("bad", "team-logo")]
    assert all(isinstance(e, AssetPathEscape) for e in escapes)


def test_registry_aware_check_uses_the_subdir_effective_root(tmp_path: Path) -> None:
    """With ``subdir`` set, the anchor is ``<checkout>/<subdir>/assets``, not the checkout's."""
    repo = tmp_path / "repo"
    checkout = tmp_path / "checkout"
    _make_pack(checkout / "inner", {"team-logo": "logo.png"})
    # A sidecar in the checkout's own assets/ is not part of the effective pack.
    _write_sidecar(checkout / "assets", "outer-bad", _ESCAPING)
    _write_sidecar(checkout / "inner" / "assets", "inner-bad", "/etc/hostname")
    _write_registry(repo, [{"name": "acme", "local_path": str(checkout), "subdir": "inner"}])

    escapes = find_org_asset_path_escapes(repo, load_org_drg(repo))

    assert [(e.pack, e.asset) for e in escapes] == [("acme", "inner-bad")]
