"""The selected skill-bundle completion recheck accepts NTFS modes (#4927; WP02 review follow-up).

``_finish_selected_stage`` compares every written output and every created
directory with its planned state. On Windows the written file reads 0o666 and
the directory 0o777, never the planned 0o644/0o755, so an exact comparison
would raise "Selected staged output/input changed" after a successful write.
The planned mode is compared host-aware instead; every other field, and POSIX
modes, still compare exactly.
"""

from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

from kernel import paths as kernel_paths
from specify_cli.tool_surface.bundles import projection
from specify_cli.tool_surface.bundles.model import PreparedBundle
from specify_cli.tool_surface.operations import ApplyConsent, FileState, OperationRoot, OwnerAssessment, OwnershipProof, PhysicalEffect
from tests.specify_cli.tool_surface.ntfs_emulation import emulate_ntfs

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_CONTENT = b"staged bytes\n"
_SHA = "24668ae36d3c2448e3dbe456c1d49dc376be2d68c97ac472978c545d1f23fffd"  # sha256 of _CONTENT
_PROOF = OwnershipProof("canonical_content", "test")


def _effect(root: OperationRoot, path: str, after: FileState) -> PhysicalEffect:
    return PhysicalEffect(projection.OWNER, "surface_repair", root, path, "create", FileState("absent"), after, "stage", (_PROOF,), (projection.OWNER,))


def _finish(tmp_path: Path) -> None:
    """Write a plugin directory and one file as staging would, then run the completion recheck."""
    root = OperationRoot("root-id", "project", tmp_path)
    directory, member = tmp_path / "plugin", tmp_path / "plugin" / "a.json"
    directory.mkdir()
    os.chmod(directory, 0o755)
    member.write_bytes(_CONTENT)
    os.chmod(member, 0o644)
    effects = (
        _effect(root, "plugin", FileState("directory", mode=0o755)),
        _effect(root, "plugin/a.json", FileState("file", sha256=_SHA, mode=0o644)),
    )
    observed = (projection.observe_bundle_path(member),)  # the staged output, as prepare_staging observes it
    assessment = OwnerAssessment(projection.OWNER, root, effects, prepared=PreparedBundle(root, ApplyConsent(), (), observed))
    run = projection._SelectedBundleRun(
        inputs=cast(projection.SelectedSkillBundle, SimpleNamespace(assessment=assessment)),  # only .assessment is read
        parents={directory: projection.observe_bundle_path(directory, members=True)},
        written={member: projection.observe_bundle_path(member)},
    )
    token = projection._SELECTED_SKILL_BUNDLE.set(run)
    try:
        projection._finish_selected_stage(assessment)
    finally:
        projection._SELECTED_SKILL_BUNDLE.reset(token)
    assert run.completed is not None and len(run.completed) == 2


def test_selected_bundle_completes_on_windows(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    emulate_ntfs(monkeypatch)  # the file reads 0o666 and the directory 0o777

    _finish(tmp_path)


def test_selected_bundle_completes_on_posix(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(kernel_paths, "is_windows", lambda: False)

    _finish(tmp_path)


def test_selected_bundle_still_refuses_posix_mode_drift(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(kernel_paths, "is_windows", lambda: False)
    real_chmod = os.chmod

    def drifting_chmod(path: str | os.PathLike[str], mode: int, *args: Any, **kwargs: Any) -> None:
        real_chmod(path, 0o600 if str(path).endswith("a.json") else mode, *args, **kwargs)

    monkeypatch.setattr(os, "chmod", drifting_chmod)

    with pytest.raises(ValueError, match="Selected staged output/input changed"):
        _finish(tmp_path)
