"""Tests for :class:`charter.offering.assets.repository.AssetRepository` (WP04).

An asset identifier must resolve to a filesystem path across the built-in,
organisation and project tiers, fail-closed. These tests pin the three traps
called out by the plan: built-in anchor asymmetry (no doubled
``built-in/built-in``), recursive overlay discovery (``rglob``, not ``glob``),
and containment enforced through the doctrine-layer
``resolve_relative_path_within_root`` primitive (traversal + symlink escapes
refused with a typed error).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from ruamel.yaml import YAML

from charter.offering.assets.repository import (
    AssetNotFoundError,
    AssetPathEscapeError,
    AssetRepository,
)
from charter.offering.base import ArtifactLayerCollisionWarning

pytestmark = [pytest.mark.fast, pytest.mark.doctrine, pytest.mark.corpus]

_SHIPPED_ASSET_ID = "common-docs-structural-lint"


def _write_asset(path: Path, *, asset_id: str, mime: str, blob_path: str) -> None:
    """Write one ``*.asset.yaml`` sidecar manifest."""
    path.parent.mkdir(parents=True, exist_ok=True)
    yaml = YAML()
    yaml.default_flow_style = False
    with path.open("w", encoding="utf-8") as handle:
        yaml.dump({"id": asset_id, "mime": mime, "path": blob_path}, handle)


def _write_blob(path: Path, content: str = "x") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


# ---------------------------------------------------------------------------
# T019 / T020 — repository loading, recursive discovery, source-path tracking
# ---------------------------------------------------------------------------


def test_loads_shipped_builtin_asset_from_package_data() -> None:
    """The one shipped asset is discovered from package data, builtin-tagged."""
    repo = AssetRepository()
    assert repo.get(_SHIPPED_ASSET_ID) is not None
    assert repo.get_provenance(_SHIPPED_ASSET_ID) == "builtin"


def test_source_path_tracks_the_declaring_manifest(tmp_path: Path) -> None:
    """T020: the source manifest file is tracked per id (not just a layer label)."""
    built_in = tmp_path / "shipped" / "assets" / "built-in"
    _write_asset(
        built_in / "a.asset.yaml", asset_id="a", mime="text/plain", blob_path="built-in/a.txt"
    )
    repo = AssetRepository(built_in_dir=built_in)
    assert repo.source_path("a") == built_in / "a.asset.yaml"


def test_source_path_missing_id_raises_typed_error(tmp_path: Path) -> None:
    built_in = tmp_path / "assets" / "built-in"
    built_in.mkdir(parents=True)
    repo = AssetRepository(built_in_dir=built_in)
    with pytest.raises(AssetNotFoundError) as exc:
        repo.source_path("nope")
    assert "nope" in str(exc.value)
    assert exc.value.asset_id == "nope"


def test_source_path_absent_for_a_project_layer_manifest_that_fails_validation(
    tmp_path: Path,
) -> None:
    """T025 regression: a manifest that fails validation must not be tracked.

    Before the ``_post_validate`` fix, ``_pre_validate`` recorded
    ``_source_paths[id]`` from the raw YAML *before* ``AssetManifest.model_
    validate`` ran, so a manifest failing validation still left a stale
    ``source_path`` entry even though ``get(id)`` returns ``None`` — a
    split-brain a caller could observe. ``path`` is a required field
    (``min_length=1``); omitting it fails validation.
    """
    built_in = tmp_path / "shipped" / "assets" / "built-in"
    built_in.mkdir(parents=True)
    project_assets = tmp_path / "proj" / "assets"
    project_assets.mkdir(parents=True)
    yaml = YAML()
    yaml.default_flow_style = False
    with (project_assets / "broken.asset.yaml").open("w", encoding="utf-8") as handle:
        yaml.dump({"id": "broken", "mime": "text/plain"}, handle)  # no "path"

    with pytest.warns(UserWarning, match="Skipping invalid project"):
        repo = AssetRepository(built_in_dir=built_in, project_dir=project_assets)

    assert repo.get("broken") is None
    with pytest.raises(AssetNotFoundError):
        repo.source_path("broken")


def test_org_tier_overrides_builtin_and_reports_the_shadow(tmp_path: Path) -> None:
    """T025: more-specific tier wins; the shadowed tier is *reported*, not silent."""
    built_in = tmp_path / "shipped" / "assets" / "built-in"
    _write_asset(
        built_in / "icon.asset.yaml", asset_id="icon", mime="image/png", blob_path="built-in/icon.png"
    )
    org_assets = tmp_path / "org" / "assets"
    _write_asset(
        org_assets / "icon.asset.yaml", asset_id="icon", mime="image/svg+xml", blob_path="icon.svg"
    )
    with pytest.warns(ArtifactLayerCollisionWarning):
        repo = AssetRepository(built_in_dir=built_in, org_dirs=[org_assets])
    assert repo.get_provenance("icon") == "org"
    assert repo.source_path("icon") == org_assets / "icon.asset.yaml"


def test_rglob_discovers_a_nested_org_pack_manifest(tmp_path: Path) -> None:
    """A-3: overlay discovery recurses — a manifest one dir deep is found.

    The base ``_project_scan`` is a non-recursive ``glob``; without the
    ``rglob`` override this manifest at ``assets/<pack>/deep.asset.yaml`` is
    never discovered.
    """
    built_in = tmp_path / "shipped" / "assets" / "built-in"
    built_in.mkdir(parents=True)
    org_assets = tmp_path / "org" / "assets"
    _write_asset(
        org_assets / "mypack" / "deep.asset.yaml",
        asset_id="deep",
        mime="text/plain",
        blob_path="mypack/deep.txt",
    )
    repo = AssetRepository(built_in_dir=built_in, org_dirs=[org_assets])
    assert repo.get("deep") is not None
    assert repo.get_provenance("deep") == "org"


# ---------------------------------------------------------------------------
# T021 / T022 — resolve_path with anchor asymmetry and fail-closed containment
# ---------------------------------------------------------------------------


def test_resolves_shipped_builtin_asset_without_doubling() -> None:
    """T022: the shipped built-in asset resolves to the real file, no doubling.

    Post-relocation the shipped blob lives at ``packs/built-in/assets/`` (the
    per-kind ``built-in/`` subdir was flattened out). ``built_in_dir`` is now
    ``packs/built-in/assets`` and the built-in anchor is its parent
    ``packs/built-in``, so the manifest ``path`` is ``assets/…`` — anchoring at
    the directory itself would produce ``.../assets/assets/…``. There is no
    longer a ``built-in/built-in`` doubling surface, and the resolved parent dir
    is ``assets`` (the pack root's per-kind dir), not ``built-in``.
    """
    repo = AssetRepository()
    resolved = repo.resolve_path(_SHIPPED_ASSET_ID)
    assert resolved.exists()
    assert resolved.name == "docs_structural_lint.py"
    assert resolved.parent.name == "assets"
    assert resolved.parent.parent.name == "built-in"
    assert "built-in/built-in" not in resolved.as_posix()


def test_builtin_anchor_asymmetry_synthetic(tmp_path: Path) -> None:
    """T022: explicit built-in anchoring at ``built_in_dir.parent``."""
    root_assets = tmp_path / "shipped" / "assets"
    built_in = root_assets / "built-in"
    _write_asset(
        built_in / "logo.asset.yaml", asset_id="logo", mime="image/png", blob_path="built-in/logo.png"
    )
    _write_blob(built_in / "logo.png")
    repo = AssetRepository(built_in_dir=built_in)
    resolved = repo.resolve_path("logo")
    assert resolved == (built_in / "logo.png").resolve(strict=False)
    assert "built-in/built-in" not in resolved.as_posix()


def test_resolves_org_tier_blob(tmp_path: Path) -> None:
    """A-2: org blobs anchor at the org ``assets/`` directory itself."""
    built_in = tmp_path / "shipped" / "assets" / "built-in"
    built_in.mkdir(parents=True)
    org_assets = tmp_path / "org" / "assets"
    _write_asset(
        org_assets / "mypack" / "deep.asset.yaml",
        asset_id="deep",
        mime="text/plain",
        blob_path="mypack/deep.txt",
    )
    _write_blob(org_assets / "mypack" / "deep.txt")
    repo = AssetRepository(built_in_dir=built_in, org_dirs=[org_assets])
    resolved = repo.resolve_path("deep")
    assert resolved == (org_assets / "mypack" / "deep.txt").resolve(strict=False)


def test_resolves_project_tier_blob(tmp_path: Path) -> None:
    """A-2: project blobs anchor at the project ``assets/`` directory itself."""
    built_in = tmp_path / "shipped" / "assets" / "built-in"
    built_in.mkdir(parents=True)
    project_assets = tmp_path / "proj" / "assets"
    _write_asset(
        project_assets / "p.asset.yaml", asset_id="p", mime="text/plain", blob_path="p.txt"
    )
    _write_blob(project_assets / "p.txt")
    repo = AssetRepository(built_in_dir=built_in, project_dir=project_assets)
    assert repo.get_provenance("p") == "project"
    resolved = repo.resolve_path("p")
    assert resolved == (project_assets / "p.txt").resolve(strict=False)


def test_org_override_resolves_via_winning_tier_anchor(tmp_path: Path) -> None:
    """T025/A-1: when org shadows built-in, resolution uses the org anchor."""
    built_in = tmp_path / "shipped" / "assets" / "built-in"
    _write_asset(
        built_in / "icon.asset.yaml", asset_id="icon", mime="image/png", blob_path="built-in/icon.png"
    )
    _write_blob(built_in / "icon.png")
    org_assets = tmp_path / "org" / "assets"
    _write_asset(
        org_assets / "icon.asset.yaml", asset_id="icon", mime="image/svg+xml", blob_path="icon.svg"
    )
    _write_blob(org_assets / "icon.svg")
    with pytest.warns(ArtifactLayerCollisionWarning):
        repo = AssetRepository(built_in_dir=built_in, org_dirs=[org_assets])
    resolved = repo.resolve_path("icon")
    assert resolved == (org_assets / "icon.svg").resolve(strict=False)


def test_missing_id_raises_typed_error(tmp_path: Path) -> None:
    """T021: a missing id raises a typed error naming the id."""
    built_in = tmp_path / "assets" / "built-in"
    built_in.mkdir(parents=True)
    repo = AssetRepository(built_in_dir=built_in)
    with pytest.raises(AssetNotFoundError) as exc:
        repo.resolve_path("ghost")
    assert "ghost" in str(exc.value)
    assert exc.value.asset_id == "ghost"


def test_traversal_escape_is_refused(tmp_path: Path) -> None:
    """T021/NFR-006: a ``..`` traversal path is refused with a typed error."""
    built_in = tmp_path / "shipped" / "assets" / "built-in"
    _write_asset(
        built_in / "evil.asset.yaml",
        asset_id="evil",
        mime="text/plain",
        blob_path="../../../../etc/passwd",
    )
    repo = AssetRepository(built_in_dir=built_in)
    with pytest.raises(AssetPathEscapeError) as exc:
        repo.resolve_path("evil")
    assert exc.value.asset_id == "evil"


def test_symlink_escape_is_refused(tmp_path: Path) -> None:
    """T021/NFR-006: a symlink that escapes the anchor is refused."""
    outside = tmp_path / "outside"
    _write_blob(outside / "secret.txt", "top secret")
    root_assets = tmp_path / "shipped" / "assets"
    built_in = root_assets / "built-in"
    built_in.mkdir(parents=True)
    # Symlink inside the anchor (<root>/assets) pointing outside it.
    (root_assets / "link").symlink_to(outside, target_is_directory=True)
    _write_asset(
        built_in / "s.asset.yaml",
        asset_id="s",
        mime="text/plain",
        blob_path="link/secret.txt",
    )
    repo = AssetRepository(built_in_dir=built_in)
    with pytest.raises(AssetPathEscapeError) as exc:
        repo.resolve_path("s")
    assert exc.value.asset_id == "s"
