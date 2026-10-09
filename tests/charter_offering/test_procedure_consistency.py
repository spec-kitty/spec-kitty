"""Consistency checks for doctrine procedure artifacts.

Cross-reference / linking checks apply to **shipped** procedures only.
_proposed procedures are work-in-progress and may reference artifacts that do not
yet exist.  Only schema-syntactic checks run across both shipped and _proposed.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import jsonschema
from ruamel.yaml import YAML
import pytest

from tests.charter_offering.conftest import OFFERING_SOURCE_ROOT

pytestmark = [pytest.mark.fast, pytest.mark.doctrine]

OFFERING_ROOT = OFFERING_SOURCE_ROOT
SCHEMA_PATH = OFFERING_ROOT / "schemas" / "procedure.schema.yaml"

_SCAN_SUBDIRS = ("built-in", "_proposed")
_PROCEDURE_DIRS = [OFFERING_ROOT / "procedures" / subdir for subdir in _SCAN_SUBDIRS]
# Cross-reference checks only apply to shipped artifacts.
_SHIPPED_PROCEDURE_DIRS = [OFFERING_ROOT / "procedures" / "built-in"]
_TEMPLATES_DIR = OFFERING_ROOT / "templates"


def _multi_glob(dirs: list[Path], pattern: str) -> list[Path]:
    results: list[Path] = []
    for directory in dirs:
        if directory.exists():
            results.extend(directory.glob(pattern))
    return sorted(set(results))


def _load_yaml(path: Path) -> dict[str, Any]:
    yaml = YAML(typ="safe")
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.load(handle) or {}
    assert isinstance(data, dict), f"{path}: expected mapping root"
    return data


def _shipped_ids(artifact_type: str, pattern: str) -> set[str]:
    base = OFFERING_ROOT / artifact_type / "built-in"
    ids: set[str] = set()
    if not base.exists():
        return ids

    for path in base.glob(pattern):
        payload = _load_yaml(path)
        artifact_id = str(payload.get("id", "")).strip()
        if artifact_id:
            ids.add(artifact_id)
    return ids


def _shipped_template_ids() -> set[str]:
    ids: set[str] = set()
    if not _TEMPLATES_DIR.exists():
        return ids

    for path in _TEMPLATES_DIR.glob("**/*.md"):
        if path.is_dir():
            continue
        if any(part.startswith(".") for part in path.relative_to(_TEMPLATES_DIR).parts):
            continue
        ids.add(path.stem.replace(".", "-"))
    return ids


def test_procedure_files_validate_against_schema() -> None:
    schema = _load_yaml(SCHEMA_PATH)
    validator = jsonschema.Draft202012Validator(schema)

    for path in _multi_glob(_PROCEDURE_DIRS, "*.procedure.yaml"):
        payload = _load_yaml(path)
        errors = sorted(validator.iter_errors(payload), key=lambda err: err.path)
        assert not errors, f"Schema validation failed for {path.name}: {[err.message for err in errors]}"


def test_procedure_references_resolve_to_shipped_artifacts() -> None:
    """All references in shipped procedures must resolve to shipped artifacts.

    _proposed procedures are excluded — they may reference artifacts not yet shipped.
    """
    id_map = {
        "directive": _shipped_ids("directives", "*.directive.yaml"),
        "tactic": _shipped_ids("tactics", "**/*.tactic.yaml"),
        "styleguide": _shipped_ids("styleguides", "**/*.styleguide.yaml"),
        "toolguide": _shipped_ids("toolguides", "*.toolguide.yaml"),
        "paradigm": _shipped_ids("paradigms", "*.paradigm.yaml"),
        "procedure": _shipped_ids("procedures", "*.procedure.yaml"),
        "template": _shipped_template_ids(),
    }

    unresolved: list[str] = []
    for path in _multi_glob(_SHIPPED_PROCEDURE_DIRS, "*.procedure.yaml"):
        payload = _load_yaml(path)
        procedure_id = str(payload.get("id", "")).strip() or path.name
        for ref in payload.get("references", []) or []:
            ref_type = str(ref.get("type", "")).strip()
            ref_id = str(ref.get("id", "")).strip()
            if ref_type not in id_map:
                unresolved.append(f"{procedure_id}: unknown reference type '{ref_type}'")
                continue
            if ref_id and ref_id not in id_map[ref_type]:
                unresolved.append(f"{procedure_id}: unresolved {ref_type} reference '{ref_id}'")

    assert not unresolved, "Unresolved procedure references:\n" + "\n".join(unresolved)


def test_no_procedure_step_carries_inline_tactic_refs() -> None:
    """Post-WP02: shipped procedure steps must not carry inline ``tactic_refs``.

    Step → tactic relationships live as edges in ``packs/built-in/procedure.graph.yaml``
    after Phase 1 excision. This test guards against regressions that
    reintroduce step-level inline references.
    """
    offenders: list[str] = []
    for path in _multi_glob(_SHIPPED_PROCEDURE_DIRS, "*.procedure.yaml"):
        payload = _load_yaml(path)
        procedure_id = str(payload.get("id", "")).strip() or path.name
        for step in payload.get("steps", []) or []:
            step_title = str(step.get("title", "?")).strip()
            if "tactic_refs" in step:
                offenders.append(
                    f"{procedure_id} step '{step_title}': still declares inline `tactic_refs`"
                )

    assert not offenders, (
        "Inline step-level `tactic_refs` reintroduced on shipped procedures — "
        "all relationships must live in packs/built-in/procedure.graph.yaml (see WP02 of "
        "excise-doctrine-curation-and-inline-references-01KP54J6):\n"
        + "\n".join(offenders)
    )
