"""A non-mapping YAML sidecar is skipped, not crashed (#6735).

``BaseArtifactRepository`` loads each sidecar raw, then used the parsed
document without a type guard, so a present-but-non-mapping document (a
top-level list or scalar) crashed the whole repository load with
``AttributeError: 'list' object has no attribute 'get'`` — in the overlay
tier at ``data.get("id")`` / inside ``_pre_validate`` (via
``reject_inline_refs``), and in the built-in tier inside ``_pre_validate``
for the six kinds whose hook reads ``data``.

These tests pin the fixed contract per repository kind sharing the base
class: a non-mapping document is malformed — skipped with the usual
``Skipping invalid <layer> <kind> <file>: <reason>`` ``UserWarning`` — while
every valid sibling artifact still loads.
"""

from __future__ import annotations

import re
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from ruamel.yaml import YAML

from charter.activation.mission_type_profile_repository import (
    MissionTypeProfileRepository,
)
from charter.offering.assets.repository import AssetRepository
from charter.offering.base import BaseArtifactRepository
from charter.offering.directives.repository import DirectiveRepository
from charter.offering.glossary_packs.repository import GlossaryPackRepository
from charter.offering.missions.step_contracts import (
    MissionStepContractRepository,
)
from charter.offering.pack_skills.repository import PackSkillRepository
from charter.offering.paradigms.repository import ParadigmRepository
from charter.offering.procedures.repository import ProcedureRepository
from charter.offering.styleguides.repository import StyleguideRepository
from charter.offering.tactics.repository import TacticRepository
from charter.offering.toolguides.repository import ToolguideRepository

pytestmark = [pytest.mark.fast, pytest.mark.doctrine]

#: YAML documents that parse cleanly but are not a mapping at the top level,
#: paired with the Python type name the skip warning must report.
NON_MAPPING_DOCUMENTS: list[tuple[str, str]] = [
    ("list", "- a\n"),
    ("str", "just a scalar\n"),
    ("int", "42\n"),
    ("bool", "true\n"),
]


@dataclass(frozen=True)
class KindCase:
    """One repository kind of the ``BaseArtifactRepository`` matrix."""

    repository: type[BaseArtifactRepository[Any]]
    kind: str
    valid_filename: str
    bad_filename: str
    valid_id: str
    valid: dict[str, Any]


#: One case per repository kind sharing ``BaseArtifactRepository`` (#6735).
#: ``kind`` is the ``_kind`` token the loader puts in its skip warnings
#: (``PackSkillRepository`` overrides it to ``pack-skill``); the filenames
#: are the sidecar names the kind's glob actually matches (an exact-name
#: glob like ``governance-profile.yaml`` cannot take a ``bad``/``valid``
#: prefix).
KINDS: list[KindCase] = [
    KindCase(
        AssetRepository,
        "asset",
        "valid-asset.asset.yaml",
        "bad.asset.yaml",
        "valid-asset",
        {"id": "valid-asset", "mime": "text/plain", "path": "blob.txt"},
    ),
    KindCase(
        DirectiveRepository,
        "directive",
        "valid.directive.yaml",
        "bad.directive.yaml",
        "DIRECTIVE_001",
        {
            "schema_version": "1.0",
            "id": "DIRECTIVE_001",
            "title": "Valid directive",
            "intent": "Loads beside the malformed sidecar.",
            "enforcement": "required",
        },
    ),
    KindCase(
        TacticRepository,
        "tactic",
        "valid.tactic.yaml",
        "bad.tactic.yaml",
        "valid-tactic",
        {
            "schema_version": "1.0",
            "id": "valid-tactic",
            "name": "Valid tactic",
            "steps": [{"title": "Step"}],
        },
    ),
    KindCase(
        ToolguideRepository,
        "toolguide",
        "valid.toolguide.yaml",
        "bad.toolguide.yaml",
        "valid-toolguide",
        {
            "schema_version": "1.0",
            "id": "valid-toolguide",
            "title": "Valid toolguide",
            "summary": "Loads beside the malformed sidecar.",
            "tool": "pytest",
            "guide_path": "docs/valid.md",
        },
    ),
    KindCase(
        GlossaryPackRepository,
        "glossarypack",
        "valid.glossary-pack.yaml",
        "bad.glossary-pack.yaml",
        "valid-pack",
        {
            "id": "valid-pack",
            "provenance": "org",
            "terms": [
                {
                    "surface": "Mission",
                    "definition": "A governed delivery unit.",
                    "confidence": 0.9,
                    "status": "canonical",
                }
            ],
        },
    ),
    KindCase(
        PackSkillRepository,
        "pack-skill",
        "valid.skill.yaml",
        "bad.skill.yaml",
        "valid-skill",
        {
            "schema_version": "1.0",
            "id": "valid-skill",
            "title": "Valid skill",
            "description": "Loads beside the malformed sidecar.",
            "form": "wrapper",
            "expands_to": {"target": "builtin:spec-kitty"},
        },
    ),
    KindCase(
        StyleguideRepository,
        "styleguide",
        "valid.styleguide.yaml",
        "bad.styleguide.yaml",
        "valid-style",
        {
            "schema_version": "1.0",
            "id": "valid-style",
            "title": "Valid styleguide",
            "scope": "code",
            "principles": ["Small diffs"],
        },
    ),
    KindCase(
        ParadigmRepository,
        "paradigm",
        "valid.paradigm.yaml",
        "bad.paradigm.yaml",
        "valid-paradigm",
        {
            "schema_version": "1.0",
            "id": "valid-paradigm",
            "name": "Valid paradigm",
            "summary": "Loads beside the malformed sidecar.",
        },
    ),
    KindCase(
        ProcedureRepository,
        "procedure",
        "valid.procedure.yaml",
        "bad.procedure.yaml",
        "valid-procedure",
        {
            "schema_version": "1.0",
            "id": "valid-procedure",
            "name": "Valid procedure",
            "purpose": "Loads beside the malformed sidecar.",
            "steps": [{"title": "Step"}],
            "entry_condition": "Start",
            "exit_condition": "Done",
        },
    ),
    KindCase(
        MissionStepContractRepository,
        "missionstepcontract",
        "valid.step-contract.yaml",
        "bad.step-contract.yaml",
        "valid-contract",
        {
            "schema_version": "1.0",
            "id": "valid-contract",
            "mission": "software-dev",
            "action": "implement",
            "steps": [{"id": "s1", "description": "Step"}],
        },
    ),
    KindCase(
        MissionTypeProfileRepository,
        "missiontypeprofile",
        "governance-profile.yaml",
        "governance-profile.yaml",
        "documentation",
        {"mission_type": "documentation"},
    ),
]


def _write_yaml(path: Path, data: dict[str, Any]) -> None:
    """Write one valid artifact manifest for its kind."""
    path.parent.mkdir(parents=True, exist_ok=True)
    yaml = YAML()
    yaml.default_flow_style = False
    with path.open("w", encoding="utf-8") as handle:
        yaml.dump(data, handle)


def _write_raw(path: Path, document: str) -> None:
    """Write one raw (deliberately non-mapping) YAML document."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(document, encoding="utf-8")


# ---------------------------------------------------------------------------
# Org overlay tier — the reported crash (#6735), one case per repository kind
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(("document_id", "document"), NON_MAPPING_DOCUMENTS)
@pytest.mark.parametrize("case", KINDS, ids=lambda case: case.repository.__name__)
def test_org_overlay_non_mapping_sidecar_is_skipped(tmp_path: Path, case: KindCase, document_id: str, document: str) -> None:
    """A non-mapping org sidecar warns and skips; valid siblings still load."""
    built_in = tmp_path / "built-in"
    org = tmp_path / "org"
    _write_yaml(built_in / case.valid_filename, case.valid)
    _write_raw(org / case.bad_filename, document)

    with pytest.warns(
        UserWarning,
        match=(
            rf"Skipping invalid org {case.kind} {re.escape(case.bad_filename)}: "
            rf"expected a YAML mapping, got {document_id}"
        ),
    ):
        repository = case.repository(built_in_dir=built_in, org_dirs=[org])

    assert repository.get(case.valid_id) is not None


# ---------------------------------------------------------------------------
# Project overlay tier — same seam (``_apply_overlay_layer``), spec scenario 3
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(("document_id", "document"), NON_MAPPING_DOCUMENTS)
def test_project_overlay_non_mapping_sidecar_is_skipped(tmp_path: Path, document_id: str, document: str) -> None:
    """A non-mapping project sidecar is skipped exactly like an org one."""
    case = KINDS[0]  # the asset kind named by #6735
    built_in = tmp_path / "built-in"
    project = tmp_path / "project"
    _write_yaml(built_in / case.valid_filename, case.valid)
    _write_raw(project / case.bad_filename, document)

    with pytest.warns(
        UserWarning,
        match=(
            rf"Skipping invalid project {case.kind} {re.escape(case.bad_filename)}: "
            rf"expected a YAML mapping, got {document_id}"
        ),
    ):
        repository = case.repository(built_in_dir=built_in, project_dir=project)

    assert repository.get(case.valid_id) is not None


# ---------------------------------------------------------------------------
# Built-in tier — the guard must precede ``_pre_validate``
# ---------------------------------------------------------------------------


def test_built_in_non_mapping_directive_is_skipped(tmp_path: Path) -> None:
    """A non-mapping built-in file cannot crash a ``_pre_validate`` hook.

    ``DirectiveRepository._pre_validate`` reads ``data`` (inline-ref
    rejection), so a non-mapping built-in document crashes before Pydantic
    can reject it on pre-fix main.
    """
    case = next(c for c in KINDS if c.repository is DirectiveRepository)
    built_in = tmp_path / "built-in"
    _write_raw(built_in / case.bad_filename, "- a\n")

    with pytest.warns(
        UserWarning,
        match=(
            rf"Skipping invalid built-in {case.kind} {re.escape(case.bad_filename)}: "
            r"expected a YAML mapping, got list"
        ),
    ):
        DirectiveRepository(built_in_dir=built_in)


def test_built_in_non_mapping_asset_is_skipped(tmp_path: Path) -> None:
    """A non-mapping built-in asset file skips with the same reason wording.

    Pre-fix this already skipped (Pydantic rejects the document with a
    ``ValidationError``); the pinned reason wording keeps the two tiers
    symmetric under the base-loader guard.
    """
    case = next(c for c in KINDS if c.repository is AssetRepository)
    built_in = tmp_path / "built-in"
    _write_raw(built_in / case.bad_filename, "- a\n")

    with pytest.warns(
        UserWarning,
        match=(
            rf"Skipping invalid built-in {case.kind} {re.escape(case.bad_filename)}: "
            r"expected a YAML mapping, got list"
        ),
    ):
        AssetRepository(built_in_dir=built_in)


def test_empty_overlay_file_stays_absence(tmp_path: Path) -> None:
    """An empty sidecar (``None`` document) stays absence, with no warning.

    Pins the ``data is None`` early return ahead of the non-mapping guard:
    emptiness is absence, not a malformed document, so the repository loads
    with no skip warning and nothing registers under the file's id.
    """
    case = next(c for c in KINDS if c.repository is DirectiveRepository)
    org = tmp_path / "org"
    _write_raw(org / case.bad_filename, "")

    with warnings.catch_warnings():
        warnings.simplefilter("error")
        repository = DirectiveRepository(org_dirs=[org], built_in_dir=tmp_path / "built-in")

    assert repository.get(case.valid_id) is None
