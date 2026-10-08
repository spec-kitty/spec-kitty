"""``.kittify/config.yaml`` org-pack registry: ``charter_packs.org.packs`` is the only shape read.

Mission ``charter-pack-cutover-01M491G6`` (#3732, FR-011) deleted the read-side
shims for the retired ``doctrine.org`` and ``organisation_packs`` keys: the
upgrade migration rewrites them and the CLI-root ``LEGACY_CHARTER_STATE`` gate
refuses a project that still has them. The registry reader therefore ignores
them (an empty registry, never an error, so ``PackContext.from_config`` stays
total) and never warns.
"""

from __future__ import annotations

import warnings
from pathlib import Path

import pytest

from charter.offering.drg.org_pack_config import load_pack_registry, require_declared_org_roots

pytestmark = [pytest.mark.fast, pytest.mark.doctrine]


def _write_config(repo_root: Path, text: str) -> Path:
    config_dir = repo_root / ".kittify"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / "config.yaml"
    config_path.write_text(text, encoding="utf-8")
    return config_path


def _packs_block(top_key: str, name: str, root: Path) -> str:
    return f"{top_key}:\n  org:\n    packs:\n      - name: {name}\n        local_path: {root}\n"


def test_charter_packs_org_packs_reads_without_warning(tmp_path: Path) -> None:
    org_root = tmp_path / "org-pack"
    org_root.mkdir()
    _write_config(tmp_path, _packs_block("charter_packs", "example-org", org_root))

    with warnings.catch_warnings():
        warnings.simplefilter("error")
        registry = load_pack_registry(tmp_path)

    assert registry.names() == ["example-org"]


@pytest.mark.parametrize("strict", [False, True], ids=["lenient", "strict"])
@pytest.mark.parametrize(
    "legacy_text",
    [
        "doctrine:\n  org:\n    packs:\n      - name: legacy-org\n        local_path: {root}\n",
        "doctrine:\n  org:\n    local_path: {root}\n",
        "organisation_packs:\n  - name: legacy-org\n    path: {root}\n",
    ],
    ids=["doctrine-org-packs", "doctrine-org-single-pack", "organisation-packs"],
)
def test_a_retired_key_is_not_read_and_not_rejected(tmp_path: Path, legacy_text: str, strict: bool) -> None:
    """A legacy-only config yields an empty registry, silently, in both modes (the CLI gate owns refusal)."""
    org_root = tmp_path / "org-pack"
    org_root.mkdir()
    _write_config(tmp_path, legacy_text.format(root=org_root))

    with warnings.catch_warnings():
        warnings.simplefilter("error")
        registry = load_pack_registry(tmp_path, strict=strict)

    assert registry.names() == []


def test_canonical_block_is_read_beside_a_stale_retired_key(tmp_path: Path) -> None:
    canonical_root = tmp_path / "canonical-pack"
    canonical_root.mkdir()
    legacy_root = tmp_path / "legacy-pack"
    legacy_root.mkdir()
    _write_config(tmp_path, _packs_block("charter_packs", "canonical-org", canonical_root) + _packs_block("doctrine", "legacy-org", legacy_root))

    assert load_pack_registry(tmp_path).names() == ["canonical-org"]


def test_unnamed_single_pack_block_is_a_config_error(tmp_path: Path) -> None:
    """``charter_packs.org.local_path`` is no second pack shape: lenient warns and reads nothing, strict raises."""
    org_root = tmp_path / "org-pack"
    org_root.mkdir()
    _write_config(tmp_path, f"charter_packs:\n  org:\n    local_path: {org_root}\n")

    with pytest.warns(UserWarning, match=r"charter_packs\.org\.packs\[\]"):
        assert load_pack_registry(tmp_path).names() == []
    with pytest.raises(ValueError, match=r"charter_packs\.org\.local_path"):
        load_pack_registry(tmp_path, strict=True)
    with pytest.raises(ValueError, match="cannot be read"):
        require_declared_org_roots(tmp_path)


def test_org_block_without_packs_is_an_empty_registry(tmp_path: Path) -> None:
    _write_config(tmp_path, "charter_packs:\n  org: {}\n")

    assert load_pack_registry(tmp_path, strict=True).names() == []
