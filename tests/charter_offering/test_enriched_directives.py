"""Validation checks for enriched directive content."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ruamel.yaml import YAML
import pytest

from tests.charter_offering.conftest import DOCTRINE_SOURCE_ROOT

pytestmark = [pytest.mark.fast, pytest.mark.doctrine, pytest.mark.corpus]

_DOCTRINE_ROOT = DOCTRINE_SOURCE_ROOT
# DOCTRINE_SOURCE_ROOT is src/charter/offering/ (mission
# charter-code-topology-01M152G1 relocated the former src/charter/offering/), so the
# repo root is two parents up, not one: parents[0]=src/charter,
# parents[1]=src, parents[2]=<repo root>.
_PACKS_BUILT_IN = _DOCTRINE_ROOT.parents[2] / "packs" / "built-in"
_DIRECTIVES_DIRS = [_PACKS_BUILT_IN / "directives"]


def _multi_glob(dirs: list[Path], pattern: str) -> list[Path]:
    results: list[Path] = []
    for d in dirs:
        if d.exists():
            results.extend(d.glob(pattern))
    return sorted(set(results))


def _load_yaml(path: Path) -> dict[str, Any]:
    yaml = YAML(typ="safe")
    with path.open("r", encoding="utf-8") as fh:
        return yaml.load(fh) or {}


def _looks_like_placeholder_intent(intent: str, title: str) -> bool:
    normalized_intent = " ".join(intent.split()).strip().lower()
    normalized_title = " ".join(title.split()).strip().lower()
    return normalized_intent == f"ensure compliance with {normalized_title}."


def test_shipped_directives_have_non_placeholder_intent_and_scope() -> None:
    directive_files = _multi_glob(_DIRECTIVES_DIRS, "*.directive.yaml")
    assert directive_files, "No directive files found"

    missing_scope: list[str] = []
    placeholder_intent: list[str] = []

    for path in directive_files:
        data = _load_yaml(path)
        title = str(data.get("title", "")).strip()
        intent = str(data.get("intent", "")).strip()
        scope = str(data.get("scope", "")).strip()

        if not scope:
            missing_scope.append(path.name)

        if _looks_like_placeholder_intent(intent, title):
            placeholder_intent.append(path.name)

    assert not missing_scope, "Directives missing scope:\n" + "\n".join(missing_scope)
    assert not placeholder_intent, (
        "Directives with placeholder one-sentence intent:\n"
        + "\n".join(placeholder_intent)
    )
