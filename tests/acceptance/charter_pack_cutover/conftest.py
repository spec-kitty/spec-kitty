"""Fixtures for the charter-pack cutover acceptance suite (#3732).

Every fixture builds under ``tmp_path``, never in the repository.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from .legacy_fixtures import (
    MISSION_TYPES,
    finish,
    project_from_template,
    write_text,
)

#: The repository's built-in pack (copied, never edited in place).
BUILT_IN_PACK = Path(__file__).resolve().parents[3] / "packs" / "built-in"

#: A project directive living only in the new project pack root (FR-016).
MIGRATED_PROJECT_DIRECTIVE_ID = "PROJECT_901"
MIGRATED_PROJECT_DIRECTIVE = "directive/901-migrated-project-directive.directive.yaml"


@pytest.fixture
def legacy_project(request: pytest.FixtureRequest, tmp_path: Path) -> Path:
    """Build the legacy fixture named by indirect parametrisation (``BUILDERS`` key)."""
    name = str(request.param)
    return project_from_template(name, tmp_path / name)


def build_migrated_project(project: Path) -> Path:
    """Canonical post-cutover layout: ``charter_packs.org.packs`` and ``.kittify/charter-packs/``."""
    write_text(
        project / ".kittify" / "charter-packs" / MIGRATED_PROJECT_DIRECTIVE,
        f'schema_version: "1.0"\nid: {MIGRATED_PROJECT_DIRECTIVE_ID}\ntitle: Migrated project directive\n'
        "intent: Keep the project layer readable.\nenforcement: advisory\n",
    )
    return finish(project, {"charter_packs": {"org": {"packs": []}}, "mission_type_activations": MISSION_TYPES})


@pytest.fixture
def migrated_project(tmp_path: Path) -> Path:
    return project_from_template("migrated", tmp_path / "migrated", build_migrated_project)


@pytest.fixture
def two_org_packs(tmp_path: Path) -> Path:
    return project_from_template("two_org_packs", tmp_path / "two-org-packs")


@pytest.fixture
def copied_builtin_pack(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A copy of ``packs/built-in`` that the CLI resolves through ``SPEC_KITTY_PACKS_ROOT``.

    Returns the copied ``built-in`` directory; edit it freely.
    """
    packs_root = tmp_path / "packs-root"
    target = packs_root / "built-in"
    shutil.copytree(BUILT_IN_PACK, target)
    monkeypatch.setenv("SPEC_KITTY_PACKS_ROOT", str(packs_root))
    return target
