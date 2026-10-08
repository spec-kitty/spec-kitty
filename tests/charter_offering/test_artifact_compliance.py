"""Integration checks for in-repo doctrine artifacts.

Validates that directive/styleguide/toolguide files in src/doctrine:
1. Conform to their schemas
2. Resolve key cross-artifact references
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from jsonschema import Draft202012Validator  # type: ignore[import-untyped]

from tests.charter_offering.conftest import DOCTRINE_SOURCE_ROOT, REPO_ROOT

pytestmark = [pytest.mark.doctrine, pytest.mark.fast]

DOCTRINE_DIR = DOCTRINE_SOURCE_ROOT
SCHEMA_DIR = DOCTRINE_DIR / "schemas"


def _load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    assert isinstance(data, dict), f"{path}: expected mapping root"
    return data


def _schema_validator(schema_name: str) -> Draft202012Validator:
    schema_path = SCHEMA_DIR / f"{schema_name}.schema.yaml"
    schema = _load_yaml(schema_path)
    return Draft202012Validator(schema)


def _error_message(file_path: Path, error) -> str:
    pointer = "/" + "/".join(str(part) for part in error.path) if error.path else "/"
    return f"{file_path.relative_to(REPO_ROOT)} path={pointer} message={error.message}"


def _multi_glob(dirs: list[Path], pattern: str) -> list[Path]:
    """Glob across multiple directories."""
    results: list[Path] = []
    for d in dirs:
        if d.exists():
            results.extend(d.rglob(pattern))
    return sorted(set(results))


_BUNDLED_SUBDIRS = ("built-in", "_proposed")

ARTIFACT_GLOBS: dict[str, tuple[list[Path], str]] = {
    "directive": ([DOCTRINE_DIR / "directives" / d for d in _BUNDLED_SUBDIRS], "*.directive.yaml"),
    "styleguide": ([DOCTRINE_DIR / "styleguides" / d for d in _BUNDLED_SUBDIRS], "**/*.styleguide.yaml"),
    "toolguide": ([DOCTRINE_DIR / "toolguides" / d for d in _BUNDLED_SUBDIRS], "*.toolguide.yaml"),
}


def _artifact_cases() -> list[tuple[str, Path]]:
    cases: list[tuple[str, Path]] = []
    for artifact_type, (base_dirs, pattern) in ARTIFACT_GLOBS.items():
        for artifact_path in _multi_glob(base_dirs, pattern):
            cases.append((artifact_type, artifact_path))
    return cases


_ARTIFACT_CASES = _artifact_cases()
_ARTIFACT_IDS = [f"{kind}:{path.relative_to(REPO_ROOT)}" for kind, path in _ARTIFACT_CASES]


@pytest.mark.parametrize(("artifact_type", "artifact_path"), _ARTIFACT_CASES, ids=_ARTIFACT_IDS)
def test_artifact_files_validate_schema(artifact_type: str, artifact_path: Path) -> None:
    validator = _schema_validator(artifact_type)
    payload = _load_yaml(artifact_path)
    errors = sorted(validator.iter_errors(payload), key=str)
    assert not errors, "\n".join(_error_message(artifact_path, error) for error in errors)


@pytest.fixture(scope="module")
def tactic_ids() -> set[str]:
    ids: set[str] = set()
    for tactic_path in _multi_glob(
        [DOCTRINE_DIR / "tactics" / "built-in"], "*.tactic.yaml"
    ):
        tactic = _load_yaml(tactic_path)
        tactic_id = tactic.get("id")
        if isinstance(tactic_id, str) and tactic_id:
            ids.add(tactic_id)
    return ids


@pytest.mark.parametrize(
    "directive_path",
    _multi_glob(
        [DOCTRINE_DIR / "directives" / d for d in _BUNDLED_SUBDIRS], "*.directive.yaml"
    ),
    ids=lambda p: str(p.relative_to(REPO_ROOT)),
)
def test_directive_has_no_inline_tactic_refs(directive_path: Path) -> None:
    """Post-WP02: directives must not carry inline ``tactic_refs``.

    Cross-artifact relationships live exclusively in
    ``src/charter/offering/graph.yaml`` (Phase 1 excision). This test guards
    against regressions that reintroduce inline references.
    """
    directive = _load_yaml(directive_path)
    assert "tactic_refs" not in directive, (
        f"{directive_path.relative_to(REPO_ROOT)} still carries inline "
        f"tactic_refs; relationships must live in graph.yaml instead "
        f"(see WP02 of excise-doctrine-curation-and-inline-references-01KP54J6)."
    )


@pytest.mark.parametrize(
    "toolguide_path",
    _multi_glob(
        [DOCTRINE_DIR / "toolguides" / d for d in _BUNDLED_SUBDIRS], "*.toolguide.yaml"
    ),
    ids=lambda p: str(p.relative_to(REPO_ROOT)),
)
def test_toolguide_guide_path_exists(toolguide_path: Path) -> None:
    toolguide = _load_yaml(toolguide_path)
    guide_path = toolguide["guide_path"]
    assert isinstance(guide_path, str), f"{toolguide_path.relative_to(REPO_ROOT)} guide_path must be a string"

    target = (REPO_ROOT / guide_path).resolve()
    try:
        target.relative_to(REPO_ROOT.resolve())
    except ValueError as exc:
        raise AssertionError(f"{toolguide_path.relative_to(REPO_ROOT)} guide_path escapes repo: {guide_path}") from exc

    assert target.is_file(), f"{toolguide_path.relative_to(REPO_ROOT)} guide_path not found: {guide_path}"
