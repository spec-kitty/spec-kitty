"""Global reporting anchors are built from NORMALIZED paths (#6176).

``specify_cli.runtime.asset_preparation.global_asset_root`` derived the global
anchor straight from ``Path.home()`` and fed it to ``os.path.commonpath``,
which collapses neither ``..`` segments nor a relative ``HOME``. The resulting
anchor reached ``OperationRoot.__post_init__``, whose guard rejects any
non-absolute path or any path carrying a ``..`` part — so every command that
runs the runtime bootstrap died with a ``ValueError`` traceback (exit 1) while
``$HOME`` was spelled like ``/work/sub/../home`` or ``../home``, which CI jobs,
test harnesses and sandboxed agent sessions do use.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from specify_cli.runtime.asset_preparation import (
    _GlobalAssetPreparation,
    global_asset_root,
)
from specify_cli.tool_surface.operations import ApplyConsent

pytestmark = [pytest.mark.fast]


def test_global_asset_root_normalizes_a_home_with_dotdot_segment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    home = tmp_path / "work" / "home"
    home.mkdir(parents=True)
    monkeypatch.setenv("HOME", str(tmp_path / "work" / "sub" / ".." / "home"))

    root = global_asset_root("runtime_bootstrap", (Path.home() / ".kittify",))

    assert ".." not in root.path.parts
    assert root.path == tmp_path / "work"


def test_global_asset_root_normalizes_a_relative_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "home").mkdir()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", "home")

    root = global_asset_root("runtime_bootstrap", (Path.home() / ".kittify",))

    assert root.path.is_absolute()
    assert ".." not in root.path.parts
    assert root.path == tmp_path


def test_global_builder_fallback_anchor_is_normalized(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "work" / "sub" / ".." / "home"))

    assessment = _GlobalAssetPreparation(ApplyConsent()).finish(())

    assert assessment.root.path.is_absolute()
    assert ".." not in assessment.root.path.parts
    assert assessment.root.path == tmp_path / "work"
