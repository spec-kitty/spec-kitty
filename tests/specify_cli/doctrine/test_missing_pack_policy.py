"""Unit tests for the FR-015 strict missing-pack policy.

Mission B WP06 (T030) replaces the silent-skip behaviour of Mission A's
pack registry loader with a hard-fail: when a configured pack's
``local_path`` does not exist on disk,
:func:`specify_cli.doctrine.config.assert_pack_local_paths_exist` raises
:class:`specify_cli.doctrine.org_charter.MissingDoctrinePackError` naming
both the pack and the missing path so the operator can either fetch the
pack or remove the entry from ``.kittify/config.yaml``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from specify_cli.doctrine.config import assert_pack_local_paths_exist
from specify_cli.doctrine.org_charter import MissingDoctrinePackError


pytestmark = [pytest.mark.unit, pytest.mark.fast]


def _write_kittify_config(repo_root: Path, packs: list[tuple[str, Path]]) -> None:
    config_dir = repo_root / ".kittify"
    config_dir.mkdir(parents=True, exist_ok=True)
    lines = ["doctrine:", "  org:", "    packs:"]
    for name, path in packs:
        lines.append(f"      - name: {name}")
        lines.append(f"        local_path: {path}")
    (config_dir / "config.yaml").write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_missing_pack_raises_named_error_with_pack_name(tmp_path: Path) -> None:
    consumer = tmp_path / "consumer"
    consumer.mkdir()
    missing = tmp_path / "never-fetched"
    _write_kittify_config(consumer, [("very-serious-developers", missing)])

    with pytest.raises(MissingDoctrinePackError) as excinfo:
        assert_pack_local_paths_exist(consumer)

    assert excinfo.value.pack_name == "very-serious-developers"
    assert excinfo.value.local_path == missing
    assert "very-serious-developers" in str(excinfo.value)
    assert str(missing) in str(excinfo.value)


def test_missing_pack_error_message_is_actionable(tmp_path: Path) -> None:
    consumer = tmp_path / "consumer"
    consumer.mkdir()
    missing = tmp_path / "missing-pack-dir"
    _write_kittify_config(consumer, [("security-pack", missing)])

    with pytest.raises(MissingDoctrinePackError) as excinfo:
        assert_pack_local_paths_exist(consumer)

    message = str(excinfo.value)
    # The error MUST tell the operator how to recover.
    assert "spec-kitty charter fetch --pack security-pack" in message
    assert ".kittify/config.yaml" in message


def test_no_packs_configured_is_a_noop(tmp_path: Path) -> None:
    consumer = tmp_path / "consumer"
    consumer.mkdir()
    # No config.yaml at all.
    assert_pack_local_paths_exist(consumer)  # must not raise


def test_existing_pack_passes_without_raising(tmp_path: Path) -> None:
    consumer = tmp_path / "consumer"
    consumer.mkdir()
    pack = tmp_path / "real-pack"
    pack.mkdir()
    _write_kittify_config(consumer, [("real-pack", pack)])

    assert_pack_local_paths_exist(consumer)  # must not raise


def test_first_missing_pack_is_reported_when_multiple_configured(
    tmp_path: Path,
) -> None:
    consumer = tmp_path / "consumer"
    consumer.mkdir()
    existing = tmp_path / "existing"
    existing.mkdir()
    missing = tmp_path / "missing"
    _write_kittify_config(
        consumer, [("existing", existing), ("missing", missing)]
    )

    with pytest.raises(MissingDoctrinePackError) as excinfo:
        assert_pack_local_paths_exist(consumer)

    assert excinfo.value.pack_name == "missing"
