"""#5229 -- the schema-3 migration stamps the same shape ``init`` stamps, atomically and without losing keys.

This file pins the runner's wiring only (it stamps the canonical map through the shared rule, writes atomically,
keeps other keys, refuses corrupt input). The capability-map rule itself (legacy list, operator-owned map,
malformed value) is pinned once, in ``test_metadata_writers_5229.py``.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from specify_cli.migration import runner as migration_runner
from specify_cli.migration.runner import _update_schema_version
from specify_cli.migration.schema_version import CURRENT_SCHEMA_CAPABILITIES, CURRENT_SCHEMA_VERSION

pytestmark = [pytest.mark.unit, pytest.mark.fast]


def _project(tmp_path: Path, text: str) -> Path:
    kittify = tmp_path / ".kittify"
    kittify.mkdir()
    (kittify / "metadata.yaml").write_text(text, encoding="utf-8")
    return tmp_path


def _spec_kitty(root: Path) -> dict[str, object]:
    data = yaml.safe_load((root / ".kittify" / "metadata.yaml").read_text(encoding="utf-8"))
    return data["spec_kitty"]


def test_stamps_the_current_schema_version_and_the_canonical_map(tmp_path: Path) -> None:
    """Kills: writing the legacy list, or a literal version."""
    root = _project(tmp_path, yaml.dump({"spec_kitty": {"version": "2.1.0"}}))

    _update_schema_version(root)

    block = _spec_kitty(root)
    assert block["schema_version"] == CURRENT_SCHEMA_VERSION
    assert block["schema_capabilities"] == CURRENT_SCHEMA_CAPABILITIES
    assert block["last_upgraded_at"]


def test_the_value_on_disk_reaches_the_rule(tmp_path: Path) -> None:
    """Kills: the runner passing None (not the on-disk map) to the capability rule."""
    first = next(iter(CURRENT_SCHEMA_CAPABILITIES))
    owned = {first: True, "my_flag": False}
    root = _project(tmp_path, yaml.dump({"spec_kitty": {"schema_capabilities": owned}}))

    _update_schema_version(root)

    assert _spec_kitty(root)["schema_capabilities"] == owned


def test_every_other_key_survives(tmp_path: Path) -> None:
    text = "# operator comment\nproject:\n  uuid: x\nspec_kitty:\n  project_uuid: 01HZZZZZZZZZZZZZZZZZZZZZZZ\n  custom_flag: true\n"
    root = _project(tmp_path, text)

    _update_schema_version(root)

    data = yaml.safe_load((root / ".kittify" / "metadata.yaml").read_text(encoding="utf-8"))
    assert data["project"] == {"uuid": "x"}
    assert data["spec_kitty"]["project_uuid"] == "01HZZZZZZZZZZZZZZZZZZZZZZZ"
    assert data["spec_kitty"]["custom_flag"] is True


def test_writes_through_the_atomic_seam_once(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Kills: the in-place ``open('w')`` that truncates the file on a crash."""
    root = _project(tmp_path, yaml.dump({"spec_kitty": {"version": "2.1.0"}}))
    calls: list[Path] = []
    real = migration_runner.atomic_write

    def spy(target: Path, content: str, **kwargs: object) -> None:
        calls.append(Path(target))
        real(target, content, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(migration_runner, "atomic_write", spy)

    _update_schema_version(root)

    assert calls == [root / ".kittify" / "metadata.yaml"]
    assert _spec_kitty(root)["schema_version"] == CURRENT_SCHEMA_VERSION


def test_a_missing_metadata_file_is_a_named_error(tmp_path: Path) -> None:
    (tmp_path / ".kittify").mkdir()
    with pytest.raises(FileNotFoundError, match="metadata.yaml"):
        _update_schema_version(tmp_path)


def test_an_unparseable_metadata_file_is_a_named_error_and_is_not_overwritten(tmp_path: Path) -> None:
    """Corrupt input is refused with a named error, never a traceback or a silent rewrite."""
    root = _project(tmp_path, "spec_kitty: [unclosed\n")

    with pytest.raises(ValueError, match="metadata.yaml"):
        _update_schema_version(root)

    assert (root / ".kittify" / "metadata.yaml").read_text(encoding="utf-8") == "spec_kitty: [unclosed\n"


def test_a_non_mapping_spec_kitty_block_is_refused(tmp_path: Path) -> None:
    root = _project(tmp_path, "spec_kitty: just-a-string\n")

    with pytest.raises(ValueError, match="spec_kitty"):
        _update_schema_version(root)
