"""Shared builders for pack-skill tests."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from ruamel.yaml import YAML


def prompt_skill(skill_id: str = "land-pr", **overrides: Any) -> dict[str, Any]:
    """Return a minimal valid prompt-form skill record."""
    data: dict[str, Any] = {
        "schema_version": "1.0",
        "id": skill_id,
        "title": "Land a PR",
        "description": "Maintainer landing pass.",
        "form": "prompt",
        "body_path": f"{skill_id}.skill.md",
    }
    data.update(overrides)
    return data


def wrapper_skill(skill_id: str = "ship", **overrides: Any) -> dict[str, Any]:
    """Return a minimal valid wrapper-form skill record."""
    data: dict[str, Any] = {
        "schema_version": "1.0",
        "id": skill_id,
        "title": "Ship",
        "description": "Shorthand for merge.",
        "form": "wrapper",
        "expands_to": {"target": "builtin:spec-kitty.merge", "args": "$ARGUMENTS"},
    }
    data.update(overrides)
    return data


def write_skill(directory: Path, data: dict[str, Any], *, body: str | None = "Do the thing: $ARGUMENTS\n") -> Path:
    """Write ``<id>.skill.yaml`` (and its body file for prompt-form data)."""
    directory.mkdir(parents=True, exist_ok=True)
    skill_file = directory / f"{data['id']}.skill.yaml"
    with skill_file.open("w", encoding="utf-8") as handle:
        YAML(typ="safe").dump(data, handle)
    body_path = data.get("body_path")
    if body is not None and body_path:
        (directory / body_path).write_text(body, encoding="utf-8")
    return skill_file


@pytest.fixture
def skill_dirs(tmp_path: Path) -> dict[str, Path]:
    """Empty built-in / two org / project skill directories."""
    dirs = {
        "builtin": tmp_path / "builtin" / "skills",
        "org_a": tmp_path / "org-a" / "skills",
        "org_b": tmp_path / "org-b" / "skills",
        "project": tmp_path / "project" / "skills",
    }
    for path in dirs.values():
        path.mkdir(parents=True)
    return dirs
