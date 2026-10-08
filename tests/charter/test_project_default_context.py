"""An activated project directive is visible on the first default context load."""

from pathlib import Path

import pytest

from charter.activation.context import build_charter_context
from charter.activation.project_registration import commit_project_registration, plan_project_registration

pytestmark = pytest.mark.unit


@pytest.mark.parametrize("active", [True, False])
def test_first_default_context_delivers_registered_project_directive(tmp_path: Path, active: bool) -> None:
    kittify = tmp_path / ".kittify"
    doctrine = kittify / "charter-packs/directive"
    doctrine.mkdir(parents=True)
    (doctrine / "LOCAL_RULE.directive.yaml").write_text(
        'schema_version: "1.0"\nid: LOCAL_RULE\ntitle: Local rule\nintent: Project operational discipline\nenforcement: advisory\n'
    )
    charter = kittify / "charter"
    charter.mkdir()
    (kittify / "config.yaml").write_text("charter: .kittify/charter/charter.yaml\n")
    activated = ["010-specification-fidelity-requirement"] + (["LOCAL_RULE"] if active else [])
    (charter / "charter.yaml").write_text(f'schema_version: "2.0.0"\nactivated_directives: {activated}\ngovernance:\n  charter:\n    selected_directives: []\n')
    (charter / "charter.md").write_text("# Project Charter\n")
    commit_project_registration(plan_project_registration(tmp_path))
    result = build_charter_context(tmp_path, action="implement", mission_type="software-dev", mark_loaded=False)
    assert result.first_load
    assert ("LOCAL_RULE" in result.text) is active
    assert "DIRECTIVE_010" in result.text
