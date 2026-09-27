"""Unit tests for the additive schema-stamp helper used by ``spec-kitty init``.

WP01 (issue #840): ``spec-kitty init`` must stamp ``schema_version`` and
``schema_capabilities`` into ``.kittify/metadata.yaml`` so downstream commands
work without manual editing. These tests lock in the additive-merge contract:

- A fresh project gets both fields.
- Operator-authored top-level keys are preserved.
- An existing ``schema_version`` is never overwritten.
- Re-running the stamp is idempotent (no file rewrite).

The tests exercise the helper directly so they remain fast and free of the
full init prompt-driven interactive surface, which is covered by the
integration test in ``tests/integration/test_init_fresh_project_chain.py``.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from specify_cli.cli.commands.init import _stamp_schema_metadata
from specify_cli.migration.schema_version import (
    CURRENT_SCHEMA_CAPABILITIES,
    CURRENT_SCHEMA_VERSION,
)

pytestmark = pytest.mark.fast


def _read_metadata(kittify: Path) -> dict[str, object]:
    """Helper: read the on-disk metadata.yaml as a plain dict."""
    raw = (kittify / "metadata.yaml").read_text(encoding="utf-8")
    loaded = yaml.safe_load(raw)
    assert isinstance(loaded, dict), f"metadata.yaml must be a mapping, got: {raw!r}"
    return loaded


def test_fresh_dir_gets_both_schema_fields(tmp_path: Path) -> None:
    """On a fresh project the stamp creates metadata.yaml with both fields."""
    kittify = tmp_path / ".kittify"

    changed = _stamp_schema_metadata(kittify)
    assert changed is True

    data = _read_metadata(kittify)
    spec_kitty = data["spec_kitty"]
    assert isinstance(spec_kitty, dict)
    assert spec_kitty["schema_version"] == CURRENT_SCHEMA_VERSION
    # Stored as a plain dict[str, bool] when round-tripped through safe_load.
    assert dict(spec_kitty["schema_capabilities"]) == CURRENT_SCHEMA_CAPABILITIES


def test_existing_metadata_with_operator_keys_preserved(tmp_path: Path) -> None:
    """Operator-authored top-level keys survive the additive stamp."""
    kittify = tmp_path / ".kittify"
    kittify.mkdir(parents=True)
    metadata_path = kittify / "metadata.yaml"
    # Pre-existing operator-authored content. No spec_kitty section.
    metadata_path.write_text(
        "my_custom_key: custom_value\nanother_section:\n  nested: 42\n",
        encoding="utf-8",
    )

    changed = _stamp_schema_metadata(kittify)
    assert changed is True

    data = _read_metadata(kittify)
    # Operator keys remain intact.
    assert data["my_custom_key"] == "custom_value"
    assert data["another_section"] == {"nested": 42}
    # Schema fields stamped.
    spec_kitty = data["spec_kitty"]
    assert isinstance(spec_kitty, dict)
    assert spec_kitty["schema_version"] == CURRENT_SCHEMA_VERSION
    assert dict(spec_kitty["schema_capabilities"]) == CURRENT_SCHEMA_CAPABILITIES


def test_existing_schema_version_not_overwritten(tmp_path: Path) -> None:
    """An existing schema_version integer must NOT be overwritten."""
    kittify = tmp_path / ".kittify"
    kittify.mkdir(parents=True)
    metadata_path = kittify / "metadata.yaml"
    metadata_path.write_text(
        "spec_kitty:\n  schema_version: 99\n",
        encoding="utf-8",
    )

    changed = _stamp_schema_metadata(kittify)
    # capabilities was missing, so a write happened.
    assert changed is True

    data = _read_metadata(kittify)
    spec_kitty = data["spec_kitty"]
    assert isinstance(spec_kitty, dict)
    # Critical: existing version is preserved.
    assert spec_kitty["schema_version"] == 99
    # Capabilities map was added (was missing).
    assert dict(spec_kitty["schema_capabilities"]) == CURRENT_SCHEMA_CAPABILITIES


def test_existing_schema_capabilities_not_merged_into(tmp_path: Path) -> None:
    """An existing schema_capabilities map must NOT have keys silently merged in.

    Operators who hand-roll a capabilities map own it; init only fills in the
    map when it is entirely absent.
    """
    kittify = tmp_path / ".kittify"
    kittify.mkdir(parents=True)
    metadata_path = kittify / "metadata.yaml"
    metadata_path.write_text(
        "spec_kitty:\n  schema_version: 3\n  schema_capabilities:\n    canonical_context: false\n",
        encoding="utf-8",
    )

    changed = _stamp_schema_metadata(kittify)
    # Both fields already present, even if the capabilities map is sparse.
    assert changed is False

    data = _read_metadata(kittify)
    spec_kitty = data["spec_kitty"]
    assert isinstance(spec_kitty, dict)
    caps = spec_kitty["schema_capabilities"]
    assert dict(caps) == {"canonical_context": False}


def test_idempotent_init(tmp_path: Path) -> None:
    """Running the stamp twice produces a byte-identical file."""
    kittify = tmp_path / ".kittify"
    kittify.mkdir(parents=True)

    # First call creates the file.
    changed_first = _stamp_schema_metadata(kittify)
    assert changed_first is True
    first_bytes = (kittify / "metadata.yaml").read_bytes()

    # Second call must be a no-op for content.
    changed_second = _stamp_schema_metadata(kittify)
    assert changed_second is False
    second_bytes = (kittify / "metadata.yaml").read_bytes()

    assert first_bytes == second_bytes


def test_stamp_preserves_yaml_round_trip_comments(tmp_path: Path) -> None:
    """ruamel round-trip preserves operator comments on adjacent keys."""
    kittify = tmp_path / ".kittify"
    kittify.mkdir(parents=True)
    metadata_path = kittify / "metadata.yaml"
    metadata_path.write_text(
        "# operator comment that must survive\nmy_custom_key: custom_value  # inline comment\n",
        encoding="utf-8",
    )

    changed = _stamp_schema_metadata(kittify)
    assert changed is True

    raw = metadata_path.read_text(encoding="utf-8")
    assert "operator comment that must survive" in raw
    assert "inline comment" in raw
    # Schema fields are present.
    data = yaml.safe_load(raw)
    assert isinstance(data, dict)
    assert data["my_custom_key"] == "custom_value"
    assert data["spec_kitty"]["schema_version"] == CURRENT_SCHEMA_VERSION
