"""Latent Windows mode sites accept host-equivalent modes (#4927, #4810).

Not reported yet, but the same defect class as #4927: each site compared an
observed mode with a planned POSIX mode exactly, so on Windows (NTFS) it
would refuse, raise, or plan a permission repair the host cannot represent.
Every case runs on an emulated NTFS host and has a POSIX twin that keeps the
exact comparison.
"""

from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest

from kernel import paths as kernel_paths
from specify_cli.tool_surface.bundles.model import StagedFile
from specify_cli.tool_surface.bundles.projection import (
    OWNER,
    _finalize_staged_directories,
    _stage_effect,
    observe_confined,
)
from specify_cli.tool_surface.operations import (
    Diagnostic,
    Disposition,
    FileState,
    OperationRoot,
    OwnershipProof,
    PhysicalEffect,
    expected_with_mode,
)
from specify_cli.tool_surface.providers import agent_profiles, native_config
from tests.specify_cli.tool_surface.ntfs_emulation import emulate_ntfs

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_CONTENT = b"staged bytes\n"
_SHA = "24668ae36d3c2448e3dbe456c1d49dc376be2d68c97ac472978c545d1f23fffd"  # sha256 of _CONTENT: the digest the stage planner computes
_PROOF = OwnershipProof("canonical_content", "test")


def _root(tmp_path: Path) -> OperationRoot:
    return OperationRoot("root-id", "project", tmp_path)


def _create_dir_effect(tmp_path: Path, name: str, mode: int, owner: str = OWNER) -> PhysicalEffect:
    return PhysicalEffect(
        owner,
        "surface_repair",
        _root(tmp_path),
        name,
        "create",
        FileState("absent"),
        FileState("directory", mode=mode),
        "create a directory",
        (_PROOF,),
        (owner,),
    )


def _stage(tmp_path: Path, observed_mode: int, planned_mode: int) -> tuple[list[PhysicalEffect], list[Disposition]]:
    effects: list[PhysicalEffect] = []
    dispositions: list[Disposition] = []
    before = FileState("file", sha256=_SHA, mode=observed_mode)
    _stage_effect(_root(tmp_path), StagedFile("plugin/a.json", _CONTENT, planned_mode), before, _PROOF, effects, dispositions)
    return effects, dispositions


# ── bundles: _stage_effect ──────────────────────────────────────────────────


def test_stage_effect_plans_no_unrepresentable_chmod_on_windows(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(kernel_paths, "is_windows", lambda: True)

    effects, dispositions = _stage(tmp_path, observed_mode=0o666, planned_mode=0o644)

    assert effects == []
    assert [d.state for d in dispositions] == ["unchanged"]


def test_stage_effect_still_repairs_windows_read_only_drift(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(kernel_paths, "is_windows", lambda: True)

    effects, _ = _stage(tmp_path, observed_mode=0o444, planned_mode=0o644)

    assert [e.action for e in effects] == ["chmod"]


def test_stage_effect_posix_twin_still_plans_chmod(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(kernel_paths, "is_windows", lambda: False)

    effects, _ = _stage(tmp_path, observed_mode=0o666, planned_mode=0o644)

    assert [e.action for e in effects] == ["chmod"]


# ── operations.expected_with_mode (the bundle recheck/finalize stamp) ───────


@pytest.mark.parametrize(
    ("windows", "observed", "expected_mode"),
    [
        (True, FileState("directory", mode=0o777, mtime_ns=5), 0o777),  # equivalent: observed mode kept
        (False, FileState("directory", mode=0o777, mtime_ns=5), 0o755),  # POSIX: planned mode, exact compare
        (True, FileState("file", sha256=_SHA, mode=0o777), 0o755),  # kind mismatch: planned mode
    ],
)
def test_expected_with_mode(monkeypatch: pytest.MonkeyPatch, windows: bool, observed: FileState, expected_mode: int) -> None:
    monkeypatch.setattr(kernel_paths, "is_windows", lambda: windows)
    expected = FileState("directory", mode=0o700, mtime_ns=9)

    stamped = expected_with_mode(expected, 0o755, observed)

    assert stamped == FileState("directory", mode=expected_mode, mtime_ns=9)


# ── bundles: finalize of a created directory with a deferred mode ───────────


def _finalize(tmp_path: Path) -> tuple[list[str], list[str], list[Diagnostic], PhysicalEffect]:
    dest = tmp_path / "created_dir"
    dest.mkdir(mode=0o700)
    effect = _create_dir_effect(tmp_path, "created_dir", 0o555)
    created = observe_confined(tmp_path, dest)[-1]
    succeeded: list[str] = []
    failed: list[str] = []
    diagnostics: list[Diagnostic] = []
    _finalize_staged_directories([(effect, created)], succeeded, failed, diagnostics)
    return succeeded, failed, diagnostics, effect


def test_finalize_accepts_an_unrepresentable_directory_mode_on_windows(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    emulate_ntfs(monkeypatch)

    succeeded, failed, diagnostics, effect = _finalize(tmp_path)

    assert (failed, [d.message for d in diagnostics]) == ([], [])
    assert succeeded == [effect.id]


def test_finalize_posix_twin_applies_the_exact_mode(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(kernel_paths, "is_windows", lambda: False)

    succeeded, failed, _, effect = _finalize(tmp_path)

    assert (succeeded, failed) == ([effect.id], [])
    assert stat.S_IMODE((tmp_path / "created_dir").stat().st_mode) == 0o555


# ── agent profiles: a sibling owner created the shared directory first ──────


def test_sibling_created_directory_is_host_equivalent(monkeypatch: pytest.MonkeyPatch) -> None:
    absent, observed, planned = FileState("absent"), FileState("directory", mode=0o777, mtime_ns=1), FileState("directory", mode=0o755)

    monkeypatch.setattr(kernel_paths, "is_windows", lambda: True)
    assert agent_profiles._sibling_created_planned_dir(absent, observed, planned) is True
    monkeypatch.setattr(kernel_paths, "is_windows", lambda: False)
    assert agent_profiles._sibling_created_planned_dir(absent, observed, planned) is False


def test_profile_write_accepts_a_sibling_created_directory_on_windows(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "agents").mkdir()
    effect = _create_dir_effect(tmp_path, "agents", 0o755, owner="agent_profiles")
    emulate_ntfs(monkeypatch)

    agent_profiles._write_profile_effect(effect, None)  # must not raise FileExistsError

    assert (tmp_path / "agents").is_dir()


def test_profile_write_posix_twin_refuses_a_different_mode(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "agents").mkdir()
    os.chmod(tmp_path / "agents", 0o700)
    effect = _create_dir_effect(tmp_path, "agents", 0o755, owner="agent_profiles")
    monkeypatch.setattr(kernel_paths, "is_windows", lambda: False)

    with pytest.raises(FileExistsError):
        agent_profiles._write_profile_effect(effect, None)


# ── native config: directory creation postcondition ─────────────────────────


def test_native_config_directory_postcondition_holds_on_windows(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / ".vibe").mkdir()
    effect = _create_dir_effect(tmp_path, ".vibe", 0o755, owner="native_config")
    emulate_ntfs(monkeypatch)

    assert native_config._directory_postcondition_holds(effect) is True


def test_native_config_directory_postcondition_posix_twin(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / ".vibe").mkdir()
    os.chmod(tmp_path / ".vibe", 0o700)
    effect = _create_dir_effect(tmp_path, ".vibe", 0o755, owner="native_config")
    monkeypatch.setattr(kernel_paths, "is_windows", lambda: False)

    assert native_config._directory_postcondition_holds(effect) is False
