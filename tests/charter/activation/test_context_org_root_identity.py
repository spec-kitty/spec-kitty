"""An explicit ``org_root`` builds the invocation IdentityIndex from that root (#6406)."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

import pytest

from charter.activation import context as context_module
from charter.activation.identity_index import IdentityIndex

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


def test_explicit_org_root_builds_index_from_that_root(project: Path, monkeypatch: pytest.MonkeyPatch, tmp_path_factory: pytest.TempPathFactory) -> None:
    org = tmp_path_factory.mktemp("explicit-org")
    seen: list[list[Path]] = []
    original_build = IdentityIndex.build

    def _spy(cls: type[IdentityIndex], repo_root: Path, *args: Any, **kwargs: Any) -> IdentityIndex:
        index = original_build(repo_root, *args, **kwargs)
        seen.append(list(index.org_roots))
        return index

    monkeypatch.setattr(IdentityIndex, "build", classmethod(_spy))
    context_module.build_charter_context_json(project, action="implement", mission_type="software-dev", org_root=org)
    assert seen == [[org]]


def test_no_explicit_org_root_uses_configured_chain(project: Path) -> None:
    index = context_module._invocation_identity(project, None)
    assert index.org_roots == IdentityIndex.build(project).org_roots
