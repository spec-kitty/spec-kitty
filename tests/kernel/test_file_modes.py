"""``kernel.file_modes.modes_equivalent``: the one host-aware mode rule (#4927, #4810).

POSIX compares exactly. On Windows (NTFS) a directory or symlink compares its
kind only, and a file compares only its owner write bit (the read-only
attribute); any other kind, or an unknown mode, compares exactly.
"""

from __future__ import annotations

import pytest

from kernel import file_modes
from kernel import paths as kernel_paths

pytestmark = [pytest.mark.unit, pytest.mark.fast]


def _host(monkeypatch: pytest.MonkeyPatch, *, windows: bool) -> None:
    monkeypatch.setattr(kernel_paths, "is_windows", lambda: windows)


@pytest.mark.parametrize(
    ("kind", "observed", "planned", "on_windows"),
    [
        ("directory", 0o777, 0o755, True),
        ("directory", 0o555, 0o755, True),
        ("symlink", 0o777, 0o644, True),
        ("file", 0o666, 0o644, True),
        ("file", 0o666, 0o755, True),  # the exec bit is not representable on NTFS
        ("file", 0o444, 0o444, True),
        ("file", 0o444, 0o644, False),
        ("file", 0o666, 0o444, False),
        ("absent", 0o777, 0o755, False),
    ],
)
def test_windows_rule(monkeypatch: pytest.MonkeyPatch, kind: str, observed: int, planned: int, on_windows: bool) -> None:
    _host(monkeypatch, windows=True)

    assert file_modes.modes_equivalent(kind, observed, planned) is on_windows


@pytest.mark.parametrize("kind", ["directory", "symlink", "file", "absent"])
def test_posix_compares_exactly(monkeypatch: pytest.MonkeyPatch, kind: str) -> None:
    _host(monkeypatch, windows=False)

    assert file_modes.modes_equivalent(kind, 0o755, 0o755) is True
    assert file_modes.modes_equivalent(kind, 0o777, 0o755) is False


@pytest.mark.parametrize("windows", [True, False])
def test_unknown_mode_compares_exactly(monkeypatch: pytest.MonkeyPatch, windows: bool) -> None:
    _host(monkeypatch, windows=windows)

    assert file_modes.modes_equivalent("directory", None, None) is True
    assert file_modes.modes_equivalent("directory", None, 0o755) is False
    assert file_modes.modes_equivalent("file", 0o644, None) is False


def test_host_is_read_at_call_time(monkeypatch: pytest.MonkeyPatch) -> None:
    _host(monkeypatch, windows=False)
    assert file_modes.modes_equivalent("directory", 0o777, 0o755) is False

    _host(monkeypatch, windows=True)
    assert file_modes.modes_equivalent("directory", 0o777, 0o755) is True
