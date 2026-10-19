"""NFR-003: one IdentityIndex (one scan per kind) per ``build_charter_context*`` call (#6406)."""

from __future__ import annotations

import shutil
from collections import Counter
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from charter.activation import context as context_module
from charter.activation.identity_index import IdentityIndex
from charter.offering.artifact_kinds import ArtifactKind

pytestmark = [pytest.mark.fast, pytest.mark.unit]


def _checkout_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / ".kittify" / "charter").is_dir() and (parent / "pyproject.toml").is_file():
            return parent
    raise RuntimeError("could not locate repo root with .kittify/charter")


@pytest.fixture
def project(tmp_path: Path) -> Path:
    src = _checkout_root()
    kittify = tmp_path / ".kittify"
    kittify.mkdir()
    shutil.copytree(src / ".kittify" / "charter", kittify / "charter", ignore=shutil.ignore_patterns("context-state.json"))
    shutil.copy(src / ".kittify" / "config.yaml", kittify / "config.yaml")
    return tmp_path


@pytest.fixture
def probe(monkeypatch: pytest.MonkeyPatch) -> Iterator[tuple[Counter[ArtifactKind], list[IdentityIndex]]]:
    scans: Counter[ArtifactKind] = Counter()
    built: list[IdentityIndex] = []
    original_scan = IdentityIndex._scan
    original_build = IdentityIndex.build

    def _counted_scan(self: IdentityIndex, kind: ArtifactKind) -> Any:
        scans[kind] += 1
        return original_scan(self, kind)

    def _counted_build(cls: type[IdentityIndex], *args: Any, **kwargs: Any) -> IdentityIndex:
        index = original_build(*args, **kwargs)
        built.append(index)
        return index

    monkeypatch.setattr(IdentityIndex, "_scan", _counted_scan)
    monkeypatch.setattr(IdentityIndex, "build", classmethod(_counted_build))
    yield scans, built


def test_build_charter_context_scans_each_kind_once(project: Path, probe: tuple[Counter[ArtifactKind], list[IdentityIndex]]) -> None:
    scans, built = probe
    result = context_module.build_charter_context(project, action="implement", mission_type="software-dev", mark_loaded=False, depth=2)
    assert result.mode == "bootstrap"
    assert len(built) == 1, f"expected one IdentityIndex.build per invocation, got {len(built)}"
    assert scans, "positive control: the probe saw at least one scan"
    assert max(scans.values()) == 1, dict(scans)


def test_build_charter_context_json_scans_each_kind_once(project: Path, probe: tuple[Counter[ArtifactKind], list[IdentityIndex]]) -> None:
    scans, built = probe
    payload = context_module.build_charter_context_json(project, action="implement", mission_type="software-dev")
    assert payload["mode"] == "bootstrap"
    assert len(built) == 1
    assert scans
    assert max(scans.values()) == 1, dict(scans)
