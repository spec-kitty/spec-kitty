"""Real-engine end-to-end acceptance test (WP03 T015).

The mission's acceptance gate (SC-001/SC-002/SC-003): a SCREAMING-filename
directive plus an activated project agent profile, registered through the
REAL engine -- ``author_guidance()`` (reusing the seam already exercised by
``tests/charter/test_project_registration.py``) followed by
``plan_project_registration()`` / ``commit_project_registration()``, never a
hand-written provenance sidecar -- must validate green via
``validate_synthesis_state`` (``charter bundle validate``): no "unknown
kind" (#4833), no "has no provenance sidecar" / "references non-existent
artifact" (#4832), and every authored source file left byte-for-byte
unmodified (C-004, no rename -- the migration was dropped, go-forward only).

Before the fix this scenario produced 2 errors for the directive (#4832,
filename-reparse mismatch) plus 1 "unknown kind 'agent_profile'" error
(#4833); see ``quickstart.md``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from charter.activation.project_registration import (
    commit_project_registration,
    plan_project_registration,
)
from charter.bundle import validate_synthesis_state

from tests.charter.test_project_registration import author_guidance

pytestmark = pytest.mark.unit


def test_screaming_directive_and_project_profile_validate_green_via_real_engine(
    tmp_path: Path,
) -> None:
    """Field-report scenario: real engine, SCREAMING directive filename, no rename."""
    paths = author_guidance(tmp_path)
    before = {key: path.read_bytes() for key, path in paths.items()}

    # author_guidance() authors the directive under its raw (SCREAMING)
    # identifier -- exactly the pre-fix field-report shape, never a
    # hand-written sidecar.
    assert paths["directive"].name == "CHANGE_FREEZE.directive.yaml"
    assert paths["agent_profile"].name == "ops-responder.agent.yaml"

    plan = plan_project_registration(tmp_path)
    commit_project_registration(plan)

    result = validate_synthesis_state(tmp_path)
    assert result.errors == []
    assert result.passed
    assert not any("unknown kind" in error.lower() for error in result.errors)
    assert not any("has no provenance sidecar" in error.lower() for error in result.errors)
    assert not any("references non-existent artifact" in error.lower() for error in result.errors)

    # No rename anywhere: every authored source file is byte-for-byte
    # unmodified, including the directive's still-SCREAMING filename.
    assert {key: path.read_bytes() for key, path in paths.items()} == before
    assert paths["directive"].name == "CHANGE_FREEZE.directive.yaml"

    # Breadth (analyze C1): a green bundle alone does not prove the engine
    # registered the non-directive kinds -- assert their provenance sidecars
    # were actually written, so this gate covers #4833's twins (agent_profile
    # AND procedure), not just the directive that green errors[] would satisfy.
    prov_dir = tmp_path / ".kittify" / "charter" / "provenance"
    written_kinds = {p.name.split("-", 1)[0] for p in prov_dir.glob("*.yaml")}
    assert {"directive", "agent_profile", "procedure"} <= written_kinds


def test_replan_after_commit_is_idempotent_and_stays_green(tmp_path: Path) -> None:
    """A second registration pass over an unmodified fixture is a true no-op.

    Idempotency is the other half of the acceptance gate: replanning must not
    perpetually rewrite the manifest/sidecars once everything is already
    canonical, and the bundle must remain green.
    """
    paths = author_guidance(tmp_path)
    before = {key: path.read_bytes() for key, path in paths.items()}
    commit_project_registration(plan_project_registration(tmp_path))
    assert validate_synthesis_state(tmp_path).passed

    again = plan_project_registration(tmp_path)
    assert again.writes == ()
    assert again.deletes == ()
    commit_project_registration(again)

    assert validate_synthesis_state(tmp_path).passed
    assert {key: path.read_bytes() for key, path in paths.items()} == before
