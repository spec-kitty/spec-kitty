"""Unit tests for :class:`charter.offering.base.DoctrineLayerCollisionWarning`
coverage across artifact kinds (Mission B WP06 T029 / FR-014).

Mission A wired the collision-warning surface for directives, tactics,
and agent profiles.  Mission B WP06 verifies (and where missing,
extends) the same surface for the 5 kinds that became per-artifact
selectable: styleguides, toolguides, paradigms, procedures,
mission_step_contracts.

The base-class implementation (``_record_collision_if_present``) is
shared, so the only thing that can vary is whether a given subclass
calls it on the org-override path.  These tests confirm the warning
fires uniformly and that the message format includes both the artifact
id AND the artifact kind so operators can audit which kind collided.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from charter.offering.base import DoctrineLayerCollisionWarning


pytestmark = [pytest.mark.unit, pytest.mark.fast]


def _write(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(body).lstrip(), encoding="utf-8")


# ---------------------------------------------------------------------------
# Styleguide collision (org pack vs builtin)
# ---------------------------------------------------------------------------


def test_styleguide_org_collision_warning_names_id_and_kind(
    tmp_path: Path,
) -> None:
    from charter.offering.styleguides.repository import StyleguideRepository

    built_in = tmp_path / "shipped"
    org = tmp_path / "org"
    built_in_styleguide = """
        schema_version: "1.0"
        id: collision-id
        title: Shipped baseline
        scope: code
        applies_to_languages: [python]
        principles:
          - "Built-in principle."
    """
    org_styleguide = """
        schema_version: "1.0"
        id: collision-id
        title: Org override
        scope: code
        applies_to_languages: [python]
        principles:
          - "Org principle."
    """
    _write(built_in / "collision-id.styleguide.yaml", built_in_styleguide)
    _write(org / "collision-id.styleguide.yaml", org_styleguide)

    with pytest.warns(DoctrineLayerCollisionWarning) as records:
        StyleguideRepository(built_in_dir=built_in, org_dirs=[org])

    matched = [str(r.message) for r in records if "collision-id" in str(r.message)]
    assert matched, "Styleguide org override MUST raise a collision warning."
    message = matched[0]
    assert "collision-id" in message
    assert "styleguide" in message.lower(), f"Warning message MUST name the artifact kind. Saw: {message!r}"


# ---------------------------------------------------------------------------
# Procedure collision (org pack vs builtin)
# ---------------------------------------------------------------------------


def test_procedure_org_collision_warning_names_id_and_kind(
    tmp_path: Path,
) -> None:
    from charter.offering.procedures.repository import ProcedureRepository

    built_in = tmp_path / "shipped"
    org = tmp_path / "org"
    procedure_body = """
        schema_version: "1.0"
        id: proc-collide
        name: Procedure Collide
        purpose: A test procedure for collision testing.
        entry_condition: Always.
        exit_condition: Never.
        steps:
          - title: First step
            description: Do the thing.
    """
    _write(built_in / "proc-collide.procedure.yaml", procedure_body)
    _write(org / "proc-collide.procedure.yaml", procedure_body)

    with pytest.warns(DoctrineLayerCollisionWarning) as records:
        ProcedureRepository(built_in_dir=built_in, org_dirs=[org])

    matched = [str(r.message) for r in records if "proc-collide" in str(r.message)]
    assert matched, "Procedure org override MUST raise a collision warning."
    message = matched[0]
    assert "proc-collide" in message
    assert "procedure" in message.lower()


# ---------------------------------------------------------------------------
# Toolguide collision (org pack vs builtin)
# ---------------------------------------------------------------------------


def test_toolguide_org_collision_warning_names_id_and_kind(
    tmp_path: Path,
) -> None:
    from charter.offering.toolguides.repository import ToolguideRepository

    built_in = tmp_path / "shipped"
    org = tmp_path / "org"
    tg_body = """
        schema_version: "1.0"
        id: tool-collide
        title: Tool Collide
        tool: ruff
        guide_path: src/charter/offering/toolguides/RUFF.md
        summary: Ruff lint conventions.
        commands:
          - ruff
    """
    _write(built_in / "tool-collide.toolguide.yaml", tg_body)
    _write(org / "tool-collide.toolguide.yaml", tg_body)

    with pytest.warns(DoctrineLayerCollisionWarning) as records:
        ToolguideRepository(built_in_dir=built_in, org_dirs=[org])

    matched = [str(r.message) for r in records if "tool-collide" in str(r.message)]
    assert matched, "Toolguide org override MUST raise a collision warning."
    message = matched[0]
    assert "tool-collide" in message
    assert "toolguide" in message.lower()
