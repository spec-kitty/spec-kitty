"""Schema-generation integrity (WP05, FR-005, SC-004).

``scripts/generate_schemas.py --check`` verifies the committed schemas under
``src/charter/offering/schemas/`` match what the Pydantic models (the single source of
truth, per the script's own module docstring) actually generate. Measured
before this work package: it exits 1 with 7 stale schemas.

Three divergence classes were found, and only one was safe to accept as-is:

* ``enhances``/``overrides`` removed from the generated schema — **accept**.
  ``paradigms|procedures|styleguides|tactics/models.py`` each retired these
  fields (FR-028 hard cutover) and raise via ``@model_validator`` if either is
  authored; the schemas advertising them as valid properties documented a
  shape the loader rejects.
* ``structural_lint_config`` removed — **generator bug, not accepted**. It is
  a real field (``styleguides/models.py:92``); the standard pipeline just
  cannot derive its rich shape from a bare ``dict[str, Any]``. Fixed in the
  generator (``_styleguide_fixups``), not by accepting the deletion, which
  would have invalidated the shipped ``common-docs.styleguide.yaml``.
* ``point_in_time_marker`` removed — **adjudicated, not accepted**. Declared
  in no Pydantic model (there is nothing to declare it on — the field above it
  is intentionally typed as an opaque ``dict[str, Any]``) but used,
  structurally, by ``common-docs.styleguide.yaml`` and enforced by the
  ``docs_structural_lint.py`` asset. The JSON-Schema layer is the deliberate,
  narrower second source of strictness for this one field; see the
  adjudication comment above ``_STRUCTURAL_LINT_CONFIG_DEF`` in
  ``scripts/generate_schemas.py``.

This module pins the reconciled end state: ``--check`` exits 0, both retired
fields are gone, the restored contract validates the real shipped artefact,
the ``paradigm_reference`` rename resolves, and ``mission_step_template_ref``
is emitted. It is RED against the stale schemas and GREEN once T024-T027 land.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import jsonschema
import pytest
import yaml

from scripts.generate_schemas import generate_schema

# No `fast`: this module shells out to `scripts/generate_schemas.py --check`,
# and Rule 2 of the marker-correctness gate keeps subprocess work out of the
# inner loop's `-m fast` profile. `doctrine` alone is the right tier.
# `doctrine` is a DOMAIN marker — no CI job selects on it. Dropping `fast`
# (correct: this module shells out to generate_schemas.py --check) without
# substituting a TIER marker left all 11 nodes running in no job at all.
# `integration` is the tier for subprocess + real-filesystem work.
pytestmark = [pytest.mark.doctrine, pytest.mark.integration]

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPT = _REPO_ROOT / "scripts" / "generate_schemas.py"
_COMMON_DOCS_STYLEGUIDE = (
    _REPO_ROOT
    / "packs"
    / "built-in"
    / "styleguides"
    / "common-docs.styleguide.yaml"
)


def test_check_exits_zero_on_the_reconciled_tree() -> None:
    """The end-to-end contract: the committed schemas match what the models emit.

    Runs the real CLI entry point (not the in-process function) so this also
    catches drift between ``generate_schema`` and what actually got written to
    disk by the last ``python scripts/generate_schemas.py`` run.
    """
    result = subprocess.run(
        [sys.executable, str(_SCRIPT), "--check"],
        cwd=_REPO_ROOT,
        env={"PYTHONPATH": "src", "PATH": "/usr/bin:/bin"},
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, (
        f"generate_schemas.py --check failed (exit {result.returncode}):\n"
        f"{result.stdout}\n{result.stderr}"
    )


@pytest.mark.parametrize("stem", ["paradigm", "tactic", "procedure", "styleguide"])
def test_retired_relationship_fields_are_not_generated(stem: str) -> None:
    """FR-028: enhances/overrides are gone from every generated schema.

    The models already raise on these; a generated schema still advertising
    them documents a shape the loader rejects.
    """
    schema = generate_schema(stem)
    properties = schema["properties"]

    assert "enhances" not in properties
    assert "overrides" not in properties


def test_structural_lint_config_is_emitted_with_its_full_contract() -> None:
    """T024: the generator bug is fixed — the rich shape survives regeneration.

    A naive default-pipeline render of ``dict[str, Any] | None`` collapses to a
    permissive ``type: object`` with no named properties, which would silently
    widen what ``common-docs.styleguide.yaml`` is allowed to declare. This
    pins the specific contract instead.
    """
    schema = generate_schema("styleguide")
    definitions = schema["definitions"]

    assert "structural_lint_config" in schema["properties"]
    assert schema["properties"]["structural_lint_config"] == {
        "$ref": "#/definitions/structural_lint_config"
    }

    lint_config_def = definitions["structural_lint_config"]
    assert lint_config_def["additionalProperties"] is False
    assert set(lint_config_def["properties"]) == {
        "curated_complete_sections",
        "concern_bucket_to_section",
        "point_in_time_patterns",
        "point_in_time_markers",
        "point_in_time_allowlist",
        "frontmatter_required_fields",
        "frontmatter_in_scope_exclusions",
        "shadow_tree_nav_exemptions",
        "guides_boundary",
        "redirect_stub_description_prefix",
        # T004 invariant fields (common-docs-convergence WP04).
        "sanctioned_content_sections",
        "non_content_dirs",
        "root_allowlist",
        "one_index_per_dir",
    }


def test_point_in_time_marker_adjudication_keeps_its_contract() -> None:
    """T025: declared in no model, but the JSON-Schema layer still enforces it.

    ``point_in_time_marker`` is a $ref target reached only through
    ``structural_lint_config.point_in_time_markers`` — the adjudication kept it
    exactly as strict as the ``docs_structural_lint.py`` asset that parses it
    (``_require_markers``): an object with exactly the two required string
    fields, nothing else.
    """
    schema = generate_schema("styleguide")
    marker_def = schema["definitions"]["point_in_time_marker"]

    assert marker_def["additionalProperties"] is False
    assert marker_def["required"] == ["frontmatter_field", "frontmatter_value"]
    assert set(marker_def["properties"]) == {"frontmatter_field", "frontmatter_value"}


def test_generated_styleguide_schema_validates_the_shipped_common_docs_artefact() -> None:
    """The whole point of restoring the contract: the real artefact must still pass.

    Freshly generated, not the committed file — this is what would have broken
    silently had T024/T025 accepted the naive deletions.
    """
    schema = generate_schema("styleguide")
    with _COMMON_DOCS_STYLEGUIDE.open(encoding="utf-8") as handle:
        artefact = yaml.safe_load(handle)

    validator = jsonschema.Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(artefact), key=lambda error: list(error.path))

    assert errors == [], [error.message for error in errors]


def test_generated_styleguide_schema_rejects_a_malformed_point_in_time_marker() -> None:
    """Non-vacuity: the restored contract must actually reject bad input.

    A marker missing ``frontmatter_value`` (or carrying an extra key) is exactly
    the shape ``docs_structural_lint.py._require_markers`` raises ``ConfigError``
    on at runtime; the schema must catch it too.
    """
    schema = generate_schema("styleguide")
    instance = {
        "id": "x",
        "schema_version": "1.0",
        "title": "X",
        "scope": "docs",
        "principles": ["p"],
        "structural_lint_config": {
            "point_in_time_markers": [{"frontmatter_field": "doc_status"}],
        },
    }

    validator = jsonschema.Draft202012Validator(schema)
    errors = list(validator.iter_errors(instance))

    assert errors, "a point_in_time_marker missing frontmatter_value must be rejected"


def test_paradigm_reference_rename_ref_target_resolves() -> None:
    """T026: the ``reference`` -> ``paradigm_reference`` rename is followed through.

    ``ParadigmReference`` (paradigms/models.py) renamed the shared nested model;
    the generated schema's definition name and every ``$ref`` to it must agree,
    or ``paradigm.schema.yaml`` ships a dangling reference.
    """
    schema = generate_schema("paradigm")

    assert "paradigm_reference" in schema["definitions"]
    assert "reference" not in schema["definitions"]
    assert schema["properties"]["references"]["items"] == {
        "$ref": "#/definitions/paradigm_reference"
    }


def test_mission_step_template_ref_is_emitted() -> None:
    """T026: the mission model's newer ``MissionStepTemplateRef`` is generated.

    ``missions/models.py`` gained ``MissionStep.template: MissionStepTemplateRef
    | None`` in an earlier, already-merged mission; the schema generator must
    catch up and emit a resolvable ``$ref`` for it.
    """
    schema = generate_schema("mission")
    definitions = schema["definitions"]

    assert "mission_step_template_ref" in definitions
    assert definitions["mission_step"]["properties"]["template"] == {
        "$ref": "#/definitions/mission_step_template_ref"
    }
    assert set(definitions["mission_step_template_ref"]["required"]) == {
        "artifact_key",
        "template_file",
    }
