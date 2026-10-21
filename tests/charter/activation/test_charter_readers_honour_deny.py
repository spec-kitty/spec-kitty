"""Every charter-side reader subtracts the effective deny (WP05: US1.6, FR-006, FR-016, D-21).

One test per reader. Each fixture is ledger-seeded with real built-in ids.
Positive control (F15):
every test first shows the id is served on the same fixture, then denies it
and shows it is gone.
"""

from __future__ import annotations

import json
import textwrap
from pathlib import Path
from typing import Any

import pytest
from click.testing import Result
from typer.testing import CliRunner

from charter.activation.action_governance_bundle import resolve_action_governance_bundle
from charter.activation.active_charter_service_builder import build_active_charter_service
from charter.activation.activation_ledger import ActiveCharterConfigError
from charter.activation._drg_helpers import load_validated_graph
from charter.activation.catalog import load_offering_catalog, resolve_offering_root
from charter.activation.compiler import _resolve_config_activated_roots
from charter.activation.consistency_check import run_consistency_check
from charter.activation.context_renderers.reference_pointers import _load_references
from charter.activation.drg_activation import filter_graph_by_activation
from charter.activation.invocation_context import ProjectContext
from charter.activation.org_pack_discovery import _load_governance_charter_config
from charter.activation.pack_context import PackContext
from charter.activation.profile_resolution import _load_agent_profile, _reset_agent_profile_cache
from charter.activation.resolver import resolve_project_governance
from kernel.activation_ledger_store import activation_ledger_path
from specify_cli.cli.commands.charter import charter_app
from tests._factories.activation_ledger import seed_activation_ledger

pytestmark = [pytest.mark.fast]

_RUNNER = CliRunner()

_A = "001-architectural-integrity-standard"
_A_ID = "DIRECTIVE_001"
_D = "003-decision-documentation-requirement"
_D_ID = "DIRECTIVE_003"
_SEL = "010-specification-fidelity-requirement"
_SEL_ID = "DIRECTIVE_010"
_TACTIC = "acceptance-test-first"
_PROFILE = "python-pedro"
_STEP = "software-dev/implement"
_OTHER_STEP = "software-dev/plan"


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(text).lstrip(), encoding="utf-8")


def _project(tmp_path: Path, *, selected: list[str] | None = None, required: str | None = None, charter_extra: str = "", **ledger: list[str]) -> Path:
    """A ledger-seeded project with an optional ``governance.charter.selected_directives`` and an org pack."""
    lines: list[str] = []
    if required is not None:
        _write(tmp_path / "org-packs" / "acme" / "org-charter.yaml", f"schema_version: 1\norg_name: Acme\n{required}")
        lines = ["charter_packs:", "  org:", "    packs:", "      - name: acme", "        local_path: org-packs/acme"]
    (tmp_path / ".kittify").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".kittify" / "config.yaml").write_text("\n".join(lines) + "\n", encoding="utf-8")
    governance = f"governance:\n  charter:\n    selected_directives: {json.dumps(selected or [])}\ndirectives:\n  directives: []\n"
    _write(tmp_path / ".kittify" / "charter" / "charter.yaml", governance + charter_extra)
    seed_activation_ledger(tmp_path, mission_type_activations=["software-dev"], **ledger)
    return tmp_path


def _deny(root: Path, **deny: list[str]) -> None:
    seed_activation_ledger(root, **deny)


def _ids(entries: Any) -> set[str]:
    return {entry["id"] if isinstance(entry, dict) else str(entry) for entry in entries or []}


def _context_json(root: Path, monkeypatch: pytest.MonkeyPatch, *args: str) -> Result:
    monkeypatch.chdir(root)
    return _RUNNER.invoke(charter_app, ["context", "--mission-type", "software-dev", "--no-mark-loaded", *args])


# --------------------------------------------------------------------------- #
# US1.6: charter context, end to end
# --------------------------------------------------------------------------- #


def test_charter_context_never_serves_a_denied_directive_even_when_selected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _project(tmp_path, selected=[_SEL_ID])

    before = _context_json(root, monkeypatch, "--action", "implement", "--json")
    assert before.exit_code == 0, before.output
    payload = json.loads(before.output)
    assert _SEL_ID in _ids(payload["all_directives"])  # positive control
    assert _SEL_ID in _ids(payload["directives"])

    deactivated = _RUNNER.invoke(charter_app, ["deactivate", "--repo-root", str(root), "--no-compile", "directive", _SEL])
    assert deactivated.exit_code == 0, deactivated.output

    after = _context_json(root, monkeypatch, "--action", "implement", "--json")
    assert after.exit_code == 0, after.output
    payload = json.loads(after.output)
    assert _SEL_ID not in _ids(payload["all_directives"])
    assert _SEL_ID not in _ids(payload["directives"])
    assert _A_ID in _ids(payload["all_directives"])  # only the denied id is gone

    text = _context_json(root, monkeypatch, "--action", "implement")
    assert text.exit_code == 0, text.output
    assert _SEL_ID not in text.output


def test_resolve_project_governance_subtracts_deny_after_the_selection_union(tmp_path: Path) -> None:
    root = _project(tmp_path, selected=[_SEL_ID])
    assert _SEL_ID in resolve_project_governance(root).directives

    _deny(root, deactivated_directives=[_SEL])
    assert _SEL_ID not in resolve_project_governance(root).directives


# --------------------------------------------------------------------------- #
# Action governance bundle (tactic, agent profile)
# --------------------------------------------------------------------------- #


def _bundle(root: Path) -> Any:
    return resolve_action_governance_bundle(root, action="implement", mission_type="software-dev", feature_dir=None)


def test_action_bundle_omits_a_denied_tactic(tmp_path: Path) -> None:
    root = _project(tmp_path)
    assert _TACTIC in _bundle(root).tactic_ids

    _deny(root, deactivated_tactics=[_TACTIC])
    bundle = _bundle(root)
    assert _TACTIC not in bundle.tactic_ids
    assert f"tactic:{_TACTIC}" not in bundle.roots


def test_action_bundle_graph_omits_a_denied_agent_profile(tmp_path: Path) -> None:
    root = _project(tmp_path)
    assert f"agent_profile:{_PROFILE}" in {node.urn for node in _bundle(root).merged.nodes}

    _deny(root, deactivated_agent_profiles=[_PROFILE])
    assert f"agent_profile:{_PROFILE}" not in {node.urn for node in _bundle(root).merged.nodes}


# --------------------------------------------------------------------------- #
# Resolver service and profile resolution
# --------------------------------------------------------------------------- #


def test_resolver_service_omits_denied_ids_under_an_absent_list(tmp_path: Path) -> None:
    root = _project(tmp_path)
    service = build_active_charter_service(root)
    assert _PROFILE in service.agent_profiles
    assert _TACTIC in service.tactics

    _deny(root, deactivated_agent_profiles=[_PROFILE], deactivated_tactics=[_TACTIC])
    service = build_active_charter_service(root)
    assert _PROFILE not in service.agent_profiles
    assert _TACTIC not in service.tactics
    assert service.agent_profiles  # only the denied profile is gone


def test_profile_resolution_omits_a_denied_profile(tmp_path: Path) -> None:
    root = _project(tmp_path)
    _reset_agent_profile_cache()
    assert _load_agent_profile(_PROFILE, root) is not None

    _deny(root, deactivated_agent_profiles=[_PROFILE])
    _reset_agent_profile_cache()
    assert _load_agent_profile(_PROFILE, root) is None
    _reset_agent_profile_cache()


def test_declared_id_allow_with_a_stem_deny_serves_nothing(tmp_path: Path) -> None:
    """R4: the allow list spells the declared id, the deny list the stem."""
    root = _project(tmp_path, activated_directives=[_D_ID])
    assert _D_ID in build_active_charter_service(root).directives
    assert _D_ID in resolve_project_governance(root).directives

    _deny(root, deactivated_directives=[_D])
    assert build_active_charter_service(root).directives == {}
    assert _D_ID not in resolve_project_governance(root).directives


# --------------------------------------------------------------------------- #
# DRG activation filter (incl. mission-step contracts, P6)
# --------------------------------------------------------------------------- #


def _filtered_urns(root: Path) -> set[str]:
    return {node.urn for node in filter_graph_by_activation(load_validated_graph(root), PackContext.from_config(root)).nodes}


def test_drg_filter_drops_a_denied_directive_node(tmp_path: Path) -> None:
    root = _project(tmp_path)
    assert f"directive:{_SEL_ID}" in _filtered_urns(root)

    _deny(root, deactivated_directives=[_SEL])
    assert f"directive:{_SEL_ID}" not in _filtered_urns(root)


def test_a_denied_mission_step_contract_is_filtered_before_the_mission_type_return(tmp_path: Path) -> None:
    root = _project(tmp_path)
    assert f"mission_step_contract:{_STEP}" in _filtered_urns(root)

    _deny(root, deactivated_mission_step_contracts=[_STEP])
    urns = _filtered_urns(root)
    assert f"mission_step_contract:{_STEP}" not in urns
    assert f"mission_step_contract:{_OTHER_STEP}" in urns  # the owning mission type is still active


# --------------------------------------------------------------------------- #
# Compiler roots
# --------------------------------------------------------------------------- #


def test_compiler_roots_omit_a_denied_directive(tmp_path: Path) -> None:
    root = _project(tmp_path)

    def roots() -> list[str]:
        ctx = PackContext.from_config(root)
        return _resolve_config_activated_roots(pack_context=ctx, catalog=load_offering_catalog(), offering_root=resolve_offering_root()).directives

    assert _SEL_ID in roots()
    _deny(root, deactivated_directives=[_SEL])
    assert _SEL_ID not in roots()
    assert _A_ID in roots()


# --------------------------------------------------------------------------- #
# Governance selection overlay (Sel = (selected | R) - D*)
# --------------------------------------------------------------------------- #


def test_selection_overlay_subtracts_deny_after_the_required_union(tmp_path: Path) -> None:
    root = _project(tmp_path, selected=[_SEL_ID], required=f"required_directives:\n  - {_A_ID}\n")
    selected = _load_governance_charter_config(root).selected_directives
    assert {_SEL_ID, _A_ID} <= set(selected)

    _deny(root, deactivated_directives=[_SEL, _A])
    selected = _load_governance_charter_config(root).selected_directives
    assert _SEL_ID not in selected
    assert _A_ID in selected  # the required floor is never subtracted


# --------------------------------------------------------------------------- #
# Consistency check
# --------------------------------------------------------------------------- #


def test_consistency_check_treats_a_denied_id_as_inactive(tmp_path: Path) -> None:
    root = _project(tmp_path, activated_directives=[_A, "hand-edited-unknown"])
    assert "directive/hand-edited-unknown" in run_consistency_check(ProjectContext.from_repo(root)).unknown_references

    _deny(root, deactivated_directives=["hand-edited-unknown"])
    assert "directive/hand-edited-unknown" not in run_consistency_check(ProjectContext.from_repo(root)).unknown_references


# --------------------------------------------------------------------------- #
# --include selectors and rendered references
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("selector", "kind", "identifier", "stem"),
    [(f"directive:{_SEL_ID}", "directive", _SEL_ID, _SEL), (f"tactic:{_TACTIC}", "tactic", _TACTIC, _TACTIC)],
)
def test_include_selector_on_a_denied_id_renders_the_deactivated_note(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, selector: str, kind: str, identifier: str, stem: str
) -> None:
    root = _project(tmp_path)
    before = _context_json(root, monkeypatch, "--include", selector)
    assert before.exit_code == 0, before.output
    assert "is deactivated" not in before.output

    _deny(root, **{f"deactivated_{kind}s": [stem]})
    after = _context_json(root, monkeypatch, "--include", selector)
    assert after.exit_code == 0, after.output
    note = f"{selector} is deactivated in this project (charter activate {kind} {identifier} restores it)"
    assert note in " ".join(after.output.split())


_REFERENCES = f"""
catalog:
  references:
    - id: "DIRECTIVE:{_SEL_ID}"
      title: Specification fidelity
      local_path: _LIBRARY/directive-{_SEL}.md
      kind: directive
      summary: fidelity
    - id: "DIRECTIVE:{_A_ID}"
      title: Architectural integrity
      local_path: _LIBRARY/directive-{_A}.md
      kind: directive
      summary: integrity
"""


def test_rendered_references_drop_a_denied_target(tmp_path: Path) -> None:
    root = _project(tmp_path, charter_extra=_REFERENCES)
    assert {ref["id"] for ref in _load_references(root)} == {f"DIRECTIVE:{_SEL_ID}", f"DIRECTIVE:{_A_ID}"}

    _deny(root, deactivated_directives=[_SEL])
    assert {ref["id"] for ref in _load_references(root)} == {f"DIRECTIVE:{_A_ID}"}


# --------------------------------------------------------------------------- #
# Fail closed
# --------------------------------------------------------------------------- #


def test_a_reader_that_cannot_load_activation_fails_closed(tmp_path: Path) -> None:
    root = _project(tmp_path)
    assert resolve_project_governance(root).directives  # positive control

    activation_ledger_path(root).write_text("deactivated_directives: {not: a-list}\n", encoding="utf-8")
    with pytest.raises(ActiveCharterConfigError):
        resolve_project_governance(root)
    with pytest.raises(ActiveCharterConfigError):
        _load_references(root)


# --------------------------------------------------------------------------- #
# Review cycle 1: --include resolves the selector in identity space, every kind
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("spelling", ["DIRECTIVE_003", "directive_003", "3", "003", _D])
def test_include_deny_matches_every_spelling_of_the_directive(tmp_path: Path, spelling: str) -> None:
    from charter.activation.context import build_charter_context_include

    root = _project(tmp_path)
    assert "is deactivated" not in build_charter_context_include(root, f"directive:{spelling}")  # positive control

    _deny(root, deactivated_directives=[_D])
    note = build_charter_context_include(root, f"directive:{spelling}")
    assert note == f"directive:{spelling} is deactivated in this project (charter activate directive {spelling} restores it)"


@pytest.mark.parametrize(
    ("identifier", "deny_key", "stem", "kind_token"),
    [(_D_ID, "deactivated_directives", _D, "directive"), (_PROFILE, "deactivated_agent_profiles", _PROFILE, "agent-profile")],
)
def test_include_artifact_selector_honours_deny(tmp_path: Path, identifier: str, deny_key: str, stem: str, kind_token: str) -> None:
    from charter.activation.context import build_charter_context_include

    root = _project(tmp_path)
    assert "is deactivated" not in build_charter_context_include(root, f"artifact:{identifier}")  # positive control

    _deny(root, **{deny_key: [stem]})
    note = build_charter_context_include(root, f"artifact:{identifier}")
    assert note == f"artifact:{identifier} is deactivated in this project (charter activate {kind_token} {identifier} restores it)"


# --------------------------------------------------------------------------- #
# Review cycle 1: promotion subtracts the one identity-space deny
# --------------------------------------------------------------------------- #


def test_promotion_never_seeds_a_declared_id_denied_directive(tmp_path: Path) -> None:
    """Reviewer reproduction: ``deactivated_directives: [DIRECTIVE_003]`` with an absent allow list."""
    from charter.activation.org_charter import OrgCharterPolicy, _promote_org_required_to_config
    from tests._factories.activation_ledger import read_activation_ledger

    control = _project(tmp_path / "control")
    _promote_org_required_to_config(OrgCharterPolicy(required_directives=[_A_ID]), control)
    assert _D in read_activation_ledger(control)["activated_directives"]  # positive control: seeded without a deny

    root = _project(tmp_path / "denied", deactivated_directives=[_D_ID])
    messages = _promote_org_required_to_config(OrgCharterPolicy(required_directives=[_A_ID]), root)
    written = read_activation_ledger(root)["activated_directives"]
    assert _D not in written
    assert _D_ID not in written
    assert _A in written
    assert any(_D in message for message in messages)
