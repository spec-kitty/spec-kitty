"""``spec-kitty charter consistency-check`` (#3732, FR-006, OD-8).

The command checks the active charter, so it moved from ``charter pack`` to the
top of the ``charter`` group; ``charter pack consistency-check`` is gone (no
alias, C-001). Flags and the ``--json`` shape are unchanged.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from charter.activation.consistency_check import run_consistency_check
from charter.activation.invocation_context import ProjectContext
from specify_cli.cli.commands.charter._app import charter_app
from tests._factories.activation_ledger import seed_activation_ledger

pytestmark = [pytest.mark.unit]

runner = CliRunner()

_REAL_DIRECTIVE_ID = "001-architectural-integrity-standard"


def _project(tmp_path: Path, directive_id: str) -> Path:
    kittify = tmp_path / ".kittify"
    kittify.mkdir(parents=True, exist_ok=True)
    (kittify / "config.yaml").write_text(
        f"activated_directives:\n  - {directive_id}\nmission_type_activations:\n  - software-dev\n",
        encoding="utf-8",
    )
    return tmp_path


def test_coherent_charter_exits_0(tmp_path: Path) -> None:
    root = _project(tmp_path, _REAL_DIRECTIVE_ID)
    result = runner.invoke(charter_app, ["consistency-check", "--repo-root", str(root)])
    assert result.exit_code == 0, result.output
    assert "Active charter is coherent." in result.output


def test_incoherent_charter_exits_1_naming_the_reference(tmp_path: Path) -> None:
    root = _project(tmp_path, "totally-fake-directive-zzz")
    result = runner.invoke(charter_app, ["consistency-check", "--repo-root", str(root)])
    assert result.exit_code == 1, result.output
    assert "Consistency issues found" in result.output
    assert "totally-fake-directive-zzz" in result.output


def test_json_shape_is_the_report(tmp_path: Path) -> None:
    root = _project(tmp_path, _REAL_DIRECTIVE_ID)
    result = runner.invoke(charter_app, ["consistency-check", "--json", "--repo-root", str(root)])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    expected = json.loads(run_consistency_check(ProjectContext.from_repo(root)).to_json())
    assert sorted(payload) == sorted(expected)
    assert payload["coherent"] is True


def test_pack_spelling_is_not_registered(tmp_path: Path) -> None:
    root = _project(tmp_path, _REAL_DIRECTIVE_ID)
    old = runner.invoke(charter_app, ["pack", "consistency-check", "--repo-root", str(root)])
    assert old.exit_code == 2, old.output
    assert "No such command" in old.output
    # Control: the new spelling runs on the same fixture.
    assert runner.invoke(charter_app, ["consistency-check", "--repo-root", str(root)]).exit_code == 0


# ---------------------------------------------------------------------------
# #6749: the check must honour the project layer the readers resolve.
#
# A project-layer mission type lives at `.kittify/missions/mission_types/<id>.yaml`
# (``mission_type_repository.PROJECT_MISSION_TYPES_RELATIVE``), not under the
# project pack root, so the built-in-flat ``list_available`` scan never sees it.
# The layered roster the runtime, ``charter mission-type list`` and
# ``charter activate``'s preflight use DOES resolve it — so the check must take its
# membership from that same authority, or a charter that is consistent in force is
# reported as broken (fleet: #6749).
# ---------------------------------------------------------------------------

_PROJECT_MISSION_TYPE = 'schema_version: 1\nid: proj-mission\ndisplay_name: "Project Mission"\nextends: software-dev\n'


def _mission_type_project(tmp_path: Path, *, body: str = _PROJECT_MISSION_TYPE, activations: list[str] | None = None) -> Path:
    """A project whose only activated token is a project-layer mission type."""
    mission_types = tmp_path / ".kittify" / "missions" / "mission_types"
    mission_types.mkdir(parents=True, exist_ok=True)
    (mission_types / "proj-mission.yaml").write_text(body, encoding="utf-8")
    seed_activation_ledger(tmp_path, mission_type_activations=["proj-mission"] if activations is None else activations)
    return tmp_path


def _layered_roster_ids(root: Path) -> set[str]:
    """The reader authority: built-in -> org -> project mission-type resolution."""
    from charter.activation.pack_context import PackContext
    from charter.missions import MissionTemplateRepository, resolve_layered_mission_types

    mission_types_dirs = (MissionTemplateRepository.default_missions_root() / "mission_types",)
    return set(resolve_layered_mission_types(mission_types_dirs, PackContext.from_config(root)))


def test_project_layer_mission_type_is_coherent(tmp_path: Path) -> None:
    """#6749: a project-layer activated type the readers resolve is not 'unknown'."""
    root = _mission_type_project(tmp_path)

    # Positive control on the SAME fixture: the reader authority resolves it from
    # the project layer, so exit 0 below is agreement, not a blind probe.
    assert "proj-mission" in _layered_roster_ids(root), "fixture invalid: the layered roster must resolve the project-layer type"

    result = runner.invoke(charter_app, ["consistency-check", "--json", "--repo-root", str(root)])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["coherent"] is True, payload
    flagged = [entry for entry in payload["unknown_references"] if "proj-mission" in entry]
    assert flagged == [], f"project-layer mission type misreported as unknown: {payload['unknown_references']}"


def test_unknown_mission_type_is_still_reported(tmp_path: Path) -> None:
    """Same fixture construction: a token no layer knows still refuses (no false green)."""
    root = _mission_type_project(tmp_path, activations=["ghost-type"])

    assert "ghost-type" not in _layered_roster_ids(root)

    result = runner.invoke(charter_app, ["consistency-check", "--json", "--repo-root", str(root)])

    assert result.exit_code == 1, result.output
    payload = json.loads(result.output)
    assert payload["coherent"] is False
    assert "mission-type/ghost-type" in payload["unknown_references"]


def test_malformed_project_mission_type_fails_closed(tmp_path: Path) -> None:
    """An unreadable project-layer roster fails closed as 'could not verify', never a silent pass."""
    root = _mission_type_project(tmp_path, body="schema_version: 1\nid: [unclosed\n")

    result = runner.invoke(charter_app, ["consistency-check", "--json", "--repo-root", str(root)])

    assert result.exit_code == 1, result.output
    payload = json.loads(result.output)
    assert payload["coherent"] is False
    assert payload["verification_errors"], "an unreadable mission-type layer must surface a verification error"
    assert any("mission-type" in entry for entry in payload["verification_errors"]), payload["verification_errors"]


def test_project_layer_directive_and_styleguide_are_coherent(tmp_path: Path) -> None:
    """#6749 ratchet: the directive/styleguide instance stays fixed (it was closed by #6433).

    Pinned at the CLI because this mission changes the same membership path: a
    project-layer directive and styleguide activated in the ledger must stay known.
    """
    from charter.activation.identity_index import IdentityIndex
    from charter.offering.artifact_kinds import PROJECT_KIND_DIRS, ArtifactKind
    from kernel.charter_pack_paths import project_pack_root

    pack = project_pack_root(tmp_path)
    (pack / PROJECT_KIND_DIRS[ArtifactKind.DIRECTIVE]).mkdir(parents=True)
    (pack / PROJECT_KIND_DIRS[ArtifactKind.DIRECTIVE] / "proj-dir.directive.yaml").write_text(
        'schema_version: "1.0"\nid: PROJ_DIR_900\ntitle: Project directive\nintent: local rule\nenforcement: advisory\n',
        encoding="utf-8",
    )
    (pack / PROJECT_KIND_DIRS[ArtifactKind.STYLEGUIDE]).mkdir(parents=True)
    (pack / PROJECT_KIND_DIRS[ArtifactKind.STYLEGUIDE] / "proj-style.styleguide.yaml").write_text(
        'schema_version: "1.0"\nid: proj-style-900\ntitle: Project styleguide\nscope: code\nprinciples: [p]\napplies_to_languages: []\n',
        encoding="utf-8",
    )
    # The project registration `charter activate` performs writes this overlay; the
    # fixture mirrors its shape (nodes only, no edges) so the DRG parity check sees the
    # same nodes a real project has, instead of manufacturing a graph gap.
    (pack / "graph.yaml").write_text(
        "edges: []\ngenerated_at: '2026-10-30T00:00:00+00:00'\ngenerated_by: spec-kitty project registration\nnodes:\n"
        "- kind: directive\n  label: Project directive\n  urn: directive:PROJ_DIR_900\n"
        "- kind: styleguide\n  label: Project styleguide\n  urn: styleguide:proj-style-900\n"
        "schema_version: '1.0'\n",
        encoding="utf-8",
    )
    seed_activation_ledger(tmp_path, activated_directives=["proj-dir"], activated_styleguides=["proj-style"])

    # Positive control on the SAME fixture: both project-layer artifacts are real and
    # resolvable, so a coherent report below is agreement, not an empty-project pass.
    index = IdentityIndex.build(tmp_path)
    assert index.knows(ArtifactKind.DIRECTIVE, "proj-dir")
    assert index.knows(ArtifactKind.STYLEGUIDE, "proj-style")

    result = runner.invoke(charter_app, ["consistency-check", "--json", "--repo-root", str(tmp_path)])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["coherent"] is True, payload
    assert payload["unknown_references"] == [], payload["unknown_references"]
