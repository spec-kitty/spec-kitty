"""The one host-aware mode equivalence (#4927, #4810; operator ruling 2026-11-20).

POSIX compares modes exactly. Windows (NTFS) can represent only a file's
read-only attribute, so a directory or symlink compares kind only and a file
compares only its owner write bit.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from kernel import paths as kernel_paths
from specify_cli.tool_surface.operations import (
    FileState,
    OperationRoot,
    OwnershipProof,
    PhysicalEffect,
    effect_action,
    mode_equivalent,
    state_equivalent,
)

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_SHA_A = "a" * 64
_SHA_B = "b" * 64


@pytest.fixture(params=[True, False], ids=["windows", "posix"])
def windows(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> bool:
    value = bool(request.param)
    monkeypatch.setattr(kernel_paths, "is_windows", lambda: value)
    return value


def _file(mode: int, sha: str = _SHA_A, mtime: int | None = None) -> FileState:
    return FileState("file", sha256=sha, mode=mode, mtime_ns=mtime)


def _dir(mode: int, mtime: int | None = None) -> FileState:
    return FileState("directory", mode=mode, mtime_ns=mtime)


def _link(mode: int, target: str = "t") -> FileState:
    return FileState("symlink", target=target, mode=mode)


def test_mode_equivalent_requires_same_kind(windows: bool) -> None:
    assert mode_equivalent(_dir(0o755), _file(0o755)) is False
    assert mode_equivalent(FileState("absent"), FileState("absent")) is True


def test_mode_equivalent_is_symmetric(windows: bool) -> None:
    pairs = [(_dir(0o777), _dir(0o755)), (_file(0o444), _file(0o644)), (_file(0o666), _file(0o644))]
    for left, right in pairs:
        assert mode_equivalent(left, right) is mode_equivalent(right, left)


def test_state_equivalent_compares_content_and_target(windows: bool) -> None:
    assert state_equivalent(_file(0o644, _SHA_A), _file(0o644, _SHA_B)) is False
    assert state_equivalent(_link(0o777, "a"), _link(0o777, "b")) is False
    assert state_equivalent(_file(0o666), _file(0o644)) is windows


def test_state_equivalent_mtime(windows: bool) -> None:
    observed, planned = _dir(0o755, mtime=1), _dir(0o755, mtime=2)
    assert state_equivalent(observed, planned) is True
    assert state_equivalent(observed, planned, ignore_mtime=False) is False


_ACTION_CASES = [
    (FileState("absent"), _file(0o644), "create"),
    (FileState("absent"), FileState("absent"), None),
    (_file(0o644), FileState("absent"), "delete"),
    (_file(0o644), _dir(0o755), "replace"),
    (_file(0o644, _SHA_A), _file(0o644, _SHA_B), "update"),
    (_link(0o777, "a"), _link(0o777, "b"), "retarget"),
    (_file(0o644), _file(0o644), None),
]


@pytest.mark.parametrize(("before", "after", "expected"), _ACTION_CASES)
def test_effect_action_non_mode_rungs_are_host_independent(windows: bool, before: FileState, after: FileState, expected: str | None) -> None:
    assert effect_action(before, after) == expected


@pytest.mark.parametrize(
    ("before", "after", "on_windows"),
    [
        (_dir(0o777), _dir(0o755), None),
        (_file(0o666), _file(0o644), None),
        (_file(0o444), _file(0o644), "chmod"),
        (_file(0o666), _file(0o444), "chmod"),
        (_link(0o777), _link(0o755), None),
    ],
)
def test_effect_action_chmod_rung(windows: bool, before: FileState, after: FileState, on_windows: str | None) -> None:
    expected = on_windows if windows else "chmod"
    assert effect_action(before, after) == expected


def _chmod_effect(before: FileState, after: FileState) -> PhysicalEffect:
    return PhysicalEffect(
        "global_skills",
        "global_bootstrap",
        OperationRoot("home", "global", Path("/nonexistent/home")),
        "skills/x",
        "chmod",
        before,
        after,
        "Refresh canonical global asset",
        (OwnershipProof("managed_path", "skills/x"),),
        ("global_skills",),
    )


def test_validator_refuses_a_chmod_the_host_cannot_represent(windows: bool) -> None:
    if windows:
        with pytest.raises(ValueError, match="does not match"):
            _chmod_effect(_dir(0o777), _dir(0o755))
    else:
        assert _chmod_effect(_dir(0o777), _dir(0o755)).action == "chmod"


def test_validator_accepts_a_representable_windows_chmod(windows: bool) -> None:
    assert _chmod_effect(_file(0o444), _file(0o644)).action == "chmod"
