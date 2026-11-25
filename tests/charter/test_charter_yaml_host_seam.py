"""The charter YAML writer checks the written mode through the host-aware rule (#4927 campsite).

Its written-target check used to skip the mode on Windows through an inline
``os.name`` test, which bypassed ``kernel.paths.is_windows`` and so could not be
emulated in tests. It now uses ``kernel.file_modes.modes_equivalent``: on
Windows only the owner write bit (the read-only attribute NTFS keeps) is
compared; on POSIX the mode compares exactly.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from charter.activation import charter_yaml_io as yaml_io
from kernel import paths as kernel_paths
from tests.specify_cli.tool_surface.ntfs_emulation import emulate_ntfs

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_DESIRED = b"metadata: {owner: writer}\n"


def test_windows_written_target_compares_only_the_write_bit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    target = tmp_path / "charter.yaml"
    emulate_ntfs(monkeypatch)  # the written file will read 0o666, not the requested 0o644
    prepared = yaml_io.prepare_yaml_write(target, _DESIRED, section="metadata")

    assert yaml_io.apply_yaml_write(prepared)
    assert target.read_bytes() == _DESIRED


def test_posix_written_target_still_compares_the_mode(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    target = tmp_path / "charter.yaml"
    emulate_ntfs(monkeypatch)
    monkeypatch.setattr(kernel_paths, "is_windows", lambda: False)
    prepared = yaml_io.prepare_yaml_write(target, _DESIRED, section="metadata")

    with pytest.raises(ValueError, match="precondition_changed: YAML written target"):
        yaml_io.apply_yaml_write(prepared)
