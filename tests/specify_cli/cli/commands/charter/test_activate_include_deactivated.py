"""``charter activate --cascade`` honours exclusions; ``--include-deactivated`` clears them (US3, US1.3).

Ledger-seeded.
A synthetic org pack carries ``directive P -requires-> tactic C -requires->
procedure G`` and ``P -suggests-> styleguide S``; the config stems differ from
the declared ids so a stem/id confusion cannot pass.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import Result
from typer.testing import CliRunner

from specify_cli.cli.commands.charter import charter_app
from tests._factories.activation_ledger import read_activation_ledger, seed_activation_ledger

pytestmark = [pytest.mark.fast]

_RUNNER = CliRunner()
_PACK = "org-packs/acme"
_ARTIFACTS = (
    ("directives", "directive", "p-dir", "DIRECTIVE_P"),
    ("tactics", "tactic", "c-tac", "TACTIC_C"),
    ("procedures", "procedure", "g-proc", "PROCEDURE_G"),
    ("styleguides", "styleguide", "s-style", "STYLEGUIDE_S"),
)
_EDGES = (
    ("directive:DIRECTIVE_P", "tactic:TACTIC_C", "requires"),
    ("tactic:TACTIC_C", "procedure:PROCEDURE_G", "requires"),
    ("directive:DIRECTIVE_P", "styleguide:STYLEGUIDE_S", "suggests"),
)
_IN_SCOPE = "directive,tactic,procedure"


def _project(root: Path, **ledger: list[str]) -> Path:
    pack = root / _PACK
    for plural, kind, stem, declared in _ARTIFACTS:
        (pack / plural).mkdir(parents=True, exist_ok=True)
        (pack / plural / f"{stem}.{kind}.yaml").write_text(f"id: {declared}\ntype: {kind}\ntitle: {stem}\n", encoding="utf-8")
    nodes = "\n".join(f'  - urn: "{kind}:{declared}"\n    kind: {kind}' for _plural, kind, _stem, declared in _ARTIFACTS)
    edges = "\n".join(f'  - source: "{src}"\n    target: "{tgt}"\n    relation: {rel}' for src, tgt, rel in _EDGES)
    (pack / "fixture.graph.yaml").write_text(
        f'schema_version: "1.0"\ngenerated_at: "2026-10-20T00:00:00Z"\ngenerated_by: "test"\nnodes:\n{nodes}\nedges:\n{edges}\n', encoding="utf-8"
    )
    (root / ".kittify").mkdir(parents=True, exist_ok=True)
    (root / ".kittify" / "config.yaml").write_text(f"charter_packs:\n  org:\n    packs:\n      - name: acme\n        local_path: {_PACK}\n", encoding="utf-8")
    seed_activation_ledger(root, mission_type_activations=["software-dev"], **ledger)
    return root


def _activate(root: Path, *args: str) -> Result:
    return _RUNNER.invoke(charter_app, ["activate", "--repo-root", str(root), "--no-compile", *args])


def _flat(result: Result) -> str:
    return " ".join(result.output.split())


def test_the_cascade_reports_the_deactivated_child_and_what_it_hides(tmp_path: Path) -> None:
    root = _project(tmp_path, deactivated_tactics=["c-tac"])

    result = _activate(root, "--cascade", _IN_SCOPE, "directive", "p-dir")

    assert result.exit_code == 0, result.output
    out = _flat(result)
    assert "Skipped (out of scope): styleguide/s-style" in out
    assert "Skipped, deactivated: tactic/c-tac (required by directive:DIRECTIVE_P — the parent no longer has this requirement)" in out
    assert "Unreached (behind a deactivated artifact): procedure/g-proc" in out
    assert "Run with --include-deactivated to activate these and clear their exclusions." in out
    assert "Cascade-activated: tactic/c-tac" not in out
    ledger = read_activation_ledger(root)
    assert ledger["deactivated_tactics"] == ["c-tac"]
    assert "g-proc" not in (ledger.get("activated_procedures") or [])


def test_include_deactivated_activates_the_child_and_clears_its_exclusion(tmp_path: Path) -> None:
    root = _project(tmp_path, deactivated_tactics=["c-tac"])

    result = _activate(root, "--cascade", _IN_SCOPE, "--include-deactivated", "directive", "p-dir")

    assert result.exit_code == 0, result.output
    out = _flat(result)
    assert "Cascade-activated: tactic/c-tac" in out
    assert "Reinstated: tactic/c-tac (exclusion cleared)" in out
    assert "Cascade-activated: procedure/g-proc" in out
    assert "Skipped, deactivated" not in out
    ledger = read_activation_ledger(root)
    assert "deactivated_tactics" not in ledger
    assert "g-proc" in ledger["activated_procedures"]


def test_include_deactivated_without_cascade_is_a_usage_error(tmp_path: Path) -> None:
    root = _project(tmp_path, deactivated_tactics=["c-tac"])
    before = read_activation_ledger(root)

    result = _activate(root, "--include-deactivated", "directive", "p-dir")

    assert result.exit_code == 2
    assert "--include-deactivated only applies with --cascade" in _flat(result)
    assert read_activation_ledger(root) == before


def test_without_a_deny_list_the_cascade_output_is_unchanged(tmp_path: Path) -> None:
    root = _project(tmp_path)

    result = _activate(root, "--cascade", _IN_SCOPE, "directive", "p-dir")

    assert result.exit_code == 0, result.output
    out = _flat(result)
    assert "Cascade-activated: tactic/c-tac" in out
    assert "Cascade-activated: procedure/g-proc" in out
    assert "Skipped, deactivated" not in out
    assert "Unreached" not in out
    assert "--include-deactivated" not in out


def test_the_no_cascade_warning_names_the_deactivated_child(tmp_path: Path) -> None:
    root = _project(tmp_path, deactivated_tactics=["c-tac"])

    result = _activate(root, "directive", "p-dir")

    assert result.exit_code == 0, result.output
    out = _flat(result)
    assert "referenced tactic/c-tac is deactivated and was not activated" in out
    assert "referenced tactic/c-tac was not activated (no --cascade)" not in out


# --------------------------------------------------------------------------- #
# A mission type is a cascade source (FR-022, operator ruling mission_type_cascade_source)
# --------------------------------------------------------------------------- #

_D003 = "003-decision-documentation-requirement"
_D010 = "010-specification-fidelity-requirement"
_D029 = "029-agent-commit-signing-policy"


def _builtin_project(root: Path, **ledger: list[str]) -> Path:
    (root / ".kittify").mkdir(parents=True, exist_ok=True)
    (root / ".kittify" / "config.yaml").write_text("{}\n", encoding="utf-8")
    seed_activation_ledger(root, **{"mission_type_activations": ["software-dev"], "activated_directives": [], **ledger})
    return root


def test_mission_type_seeding_keeps_denied_cli(tmp_path: Path) -> None:
    """US1.3 / FR-022: a mission-type cascade reports the denied child, keeps it excluded and activates the rest."""
    root = _builtin_project(tmp_path, deactivated_directives=[_D003])

    result = _activate(root, "--cascade", "directive", "mission-type", "software-dev")

    assert result.exit_code == 0, result.output
    out = _flat(result)
    assert f"Skipped, deactivated: directive/{_D003}" in out
    assert f"Cascade-activated: directive/{_D010}" in out  # positive control on the same fixture
    assert f"Cascade-activated: directive/{_D003}" not in out
    ledger = read_activation_ledger(root)
    assert ledger["deactivated_directives"] == [_D003]
    assert _D010 in ledger["activated_directives"]
    assert _D003 not in ledger["activated_directives"]
    assert "deactivated_mission_types" not in ledger  # mission types get no deny list


def test_mission_type_cascade_include_deactivated_reinstates(tmp_path: Path) -> None:
    root = _builtin_project(tmp_path, deactivated_directives=[_D003])

    result = _activate(root, "--cascade", "directive", "--include-deactivated", "mission-type", "software-dev")

    assert result.exit_code == 0, result.output
    assert f"Reinstated: directive/{_D003} (exclusion cleared)" in _flat(result)
    ledger = read_activation_ledger(root)
    assert "deactivated_directives" not in ledger
    assert _D003 in ledger["activated_directives"]


def test_mission_type_without_cascade_warns_about_its_references(tmp_path: Path) -> None:
    root = _builtin_project(tmp_path, deactivated_directives=[_D003])

    result = _activate(root, "mission-type", "software-dev")

    assert result.exit_code == 0, result.output
    out = _flat(result)
    assert f"referenced directive/{_D010} was not activated (no --cascade)" in out
    assert f"referenced directive/{_D003} is deactivated and was not activated" in out
    assert read_activation_ledger(root)["activated_directives"] == []


def test_mission_type_cascade_deactivation_keeps_shared_children_and_records_no_child_exclusion(tmp_path: Path) -> None:
    # Every other kind's allow list is empty, so only the two mission types (and the two directives) are sources.
    others = {f"activated_{plural}": [] for plural in ("tactics", "styleguides", "toolguides", "paradigms", "procedures", "agent_profiles")}
    root = _builtin_project(tmp_path, mission_type_activations=["software-dev", "research"], activated_directives=[_D010, _D029], **others)

    result = _RUNNER.invoke(charter_app, ["deactivate", "--repo-root", str(root), "--no-compile", "--cascade", "directive", "mission-type", "software-dev"])

    assert result.exit_code == 0, result.output
    out = _flat(result)
    assert f"Cascade-deactivated: directive/{_D029}" in out  # reached only from software-dev
    assert "Skipped (shared artifact): directive:DIRECTIVE_010 (still referenced by mission_type:research)" in out
    ledger = read_activation_ledger(root)
    assert ledger["mission_type_activations"] == ["research"]
    assert ledger["activated_directives"] == [_D010]
    assert "deactivated_directives" not in ledger


def test_an_out_of_scope_deactivated_node_names_itself_as_the_blocker(tmp_path: Path) -> None:
    root = _project(tmp_path, deactivated_tactics=["c-tac"])

    result = _activate(root, "--cascade", "directive,procedure", "directive", "p-dir")

    assert result.exit_code == 0, result.output
    out = _flat(result)
    assert "Skipped (out of scope): tactic/c-tac (deactivated; nothing behind it was walked)" in out
    assert "Unreached (behind a deactivated artifact): procedure/g-proc" in out


class _StopPreflight(Exception):
    """Raised by the cascade spy once the preflight's cascade call is captured."""


@pytest.mark.parametrize("include", [False, True])
def test_the_resynthesis_preflight_walks_the_cascade_as_the_activation_does(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, include: bool) -> None:
    from charter.activation.cascade import CascadeScope
    from charter.offering.drg.models import DRGGraph
    from specify_cli.cli.commands.charter import _resynthesis_preflight as preflight

    root = _project(tmp_path, deactivated_tactics=["c-tac"])
    captured: dict[str, object] = {}

    def spy(_graph: object, source: str, _scope: object, **kwargs: object) -> object:
        captured.update(source=source, **kwargs)
        raise _StopPreflight

    monkeypatch.setattr(preflight, "_is_inside_git_worktree", lambda _root: True)
    monkeypatch.setattr(preflight, "_load_interview_for_generate", lambda **_kwargs: None)
    monkeypatch.setattr(preflight, "cascade_activation_targets", spy)

    with pytest.raises(_StopPreflight):
        preflight.preflight_resynthesis(root, "directive", "p-dir", CascadeScope.all(), DRGGraph.model_construct(), include_deactivated=include)

    assert captured == {"source": "directive:DIRECTIVE_P", "deactivated_urns": frozenset({"tactic:TACTIC_C"}), "include_deactivated": include}


# --------------------------------------------------------------------------- #
# Focused helper tests
# --------------------------------------------------------------------------- #


def test_the_required_note_names_every_requiring_parent() -> None:
    from charter.activation.cascade import ReferencedArtifact
    from charter.offering.artifact_kinds import ArtifactKind
    from specify_cli.cli.commands.charter.activate import _required_note

    required = ReferencedArtifact(ArtifactKind.TACTIC, "c", "tactic:c", via_requires=True, required_by=("directive:A", "directive:B"))

    assert _required_note(required) == " (required by directive:A, directive:B — the parent no longer has this requirement)"
    assert _required_note(ReferencedArtifact(ArtifactKind.TACTIC, "c", "tactic:c")) == ""


def test_the_zero_target_summary_is_withheld_when_a_node_was_deactivated() -> None:
    from charter.activation.cascade import CascadeActivationResult, ReferencedArtifact
    from charter.offering.artifact_kinds import ArtifactKind
    from specify_cli.cli.commands.charter.activate import _zero_activatable_targets

    filtered = {"asset": ["a"]}
    deactivated = {"tactic": [ReferencedArtifact(ArtifactKind.TACTIC, "c", "tactic:c")]}

    assert _zero_activatable_targets(CascadeActivationResult(not_cascaded_kind_filtered=filtered))
    assert not _zero_activatable_targets(CascadeActivationResult(not_cascaded_kind_filtered=filtered, skipped_deactivated=deactivated))
    assert not _zero_activatable_targets(CascadeActivationResult(not_cascaded_kind_filtered=filtered, unreached_behind_deactivated={"tactic": ["g"]}))


def test_force_clears_a_stored_stem_listed_by_its_declared_id(tmp_path: Path) -> None:
    from charter.activation.identity_index import IdentityIndex
    from charter.activation.preset_application import _cleared_deny
    from charter.offering.artifact_kinds import ArtifactKind

    root = _project(tmp_path)
    identity = IdentityIndex.build(root)

    assert _cleared_deny(["003-decision-documentation-requirement", "keep-me"], ["DIRECTIVE_003"], ArtifactKind.DIRECTIVE, identity) == ["keep-me"]


def test_the_interview_message_names_the_kind_token() -> None:
    from specify_cli.cli.commands.charter.interview import _kept_deactivated_messages

    assert _kept_deactivated_messages({"activated_agent_profiles": ["a", "b"]}) == ["kept deactivated: agent-profile a, b"]


def test_the_resynthesis_preflight_walks_from_the_mission_type_node(tmp_path: Path) -> None:
    from specify_cli.cli.commands.charter._resynthesis_preflight import _cascade_source

    assert _cascade_source("mission-type", "software-dev", {}, []) == "mission_type:software-dev"
    root = _project(tmp_path)
    assert _cascade_source("directive", "p-dir", {"project": root / ".kittify" / "charter-packs"}, [root / _PACK]) == "directive:DIRECTIVE_P"
