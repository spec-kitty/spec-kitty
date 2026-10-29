"""#6510 / #4226 -- re-synthesis after a directive activation.

Once ``activated_directives`` is an explicit list it also names the project
directive synthesis itself promoted (stem ``001-project-intent-directive``, id
``PROJECT_001``). Synthesis must treat that directive as its own output, not as
upstream input: it may not refuse its own target as an additive-only collision,
may not demand a companion tactic for it, and must leave activation (and so
delivery through ``charter context``) untouched.

The acceptance tests drive the real ``charter synthesize`` / ``charter
resynthesize`` / ``charter activate`` / ``charter context`` commands. Nothing
patches ``_build_synthesis_request``: that builder is where the defect lived.
"""

from __future__ import annotations

import shutil
import subprocess
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
import yaml
from typer.testing import CliRunner, Result

from charter.activation.synthesizer.errors import SynthesisError
from charter.activation.synthesizer.interview_mapping import resolve_sections
from charter.activation.synthesizer.manifest import MANIFEST_PATH
from charter.activation.synthesizer.targets import build_targets
from specify_cli.cli.commands.charter import app
from specify_cli.cli.commands.charter._synthesis import _build_synthesis_request, _directive_synthesis_inputs
from tests._factories.activation_ledger import seed_activation_ledger
from tests._support.charter_cwd import CHARTER_FIND_REPO_ROOT

runner = CliRunner()

_ACTIVATION = Path(".kittify/charter/activation.yaml")
_GENERATED = Path(".kittify/charter/generated")
_PLURALS = {"directive": "directives", "tactic": "tactics", "styleguide": "styleguides"}

_OWN_STEM = "001-project-intent-directive"
_OWN_ID = "PROJECT_001"
_OWN_URN = f"directive:{_OWN_ID}"
_OWN_COMPANION = "how-we-apply-project-001"
_BUILT_IN_STEM = "003-decision-documentation-requirement"
_BUILT_IN_COMPANION = "how-we-apply-directive-003"
_TEAM_STEM = "050-team-directive"
_TEAM_ID = "TEAM_001"
_TEAM_COMPANION = "how-we-apply-team-001"
#: Distinctive rule text of the project directive; ``charter context`` must deliver it.
_OWN_PHRASE = "Every change names the zebra-quokka outcome it serves."

_ANSWERS = (
    "schema_version: '1'\nmission: software-dev\nprofile: minimal\nanswers:\n"
    "  mission_type: software_dev\n  testing_philosophy: test-driven\n  risk_appetite: moderate\n"
    "selected_paradigms: []\nselected_directives: []\navailable_tools: []\n"
)


# ---------------------------------------------------------------------------
# Fixture: one real "synthesized once" project, copied per test
# ---------------------------------------------------------------------------


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)


def _write_generated(root: Path, kind: str, artifact_id: str, body: dict[str, Any], filename: str | None = None) -> None:
    folder = root / _GENERATED / _PLURALS[kind]
    folder.mkdir(parents=True, exist_ok=True)
    name = filename or f"{artifact_id}.{kind}.yaml"
    (folder / name).write_text(yaml.safe_dump({"id": artifact_id, "schema_version": "1.0", **body}), encoding="utf-8")


def _write_tactic(root: Path, tactic_id: str) -> None:
    _write_generated(root, "tactic", tactic_id, {"name": tactic_id, "purpose": "p", "steps": [{"title": "s", "description": "d"}]})


def _invoke(*args: str) -> Result:
    return runner.invoke(app, list(args), catch_exceptions=False)


def _build_template(root: Path) -> None:
    """Reach a real "synthesized once" project through the real commands.

    ``charter generate`` compiles the bundle from a seeded interview record
    (``charter interview`` itself is interactive-only noise here), then the
    ``generated`` adapter gets one minimal body per target this interview
    names, and ``charter synthesize`` promotes them while the activation key is
    still absent (the first-run state #6510 starts from). Two built-in
    companions are authored up front: ``how-we-apply-directive-003`` for the
    built-in directive the tests activate, and nothing for ``PROJECT_001``.
    """
    _git(root, "init", "--initial-branch=main")
    _git(root, "config", "user.email", "test@example.com")
    _git(root, "config", "user.name", "Test")
    answers = root / ".kittify" / "charter" / "interview" / "answers.yaml"
    answers.parent.mkdir(parents=True, exist_ok=True)
    answers.write_text(_ANSWERS, encoding="utf-8")
    generated = _invoke("generate", "--from-interview")
    assert generated.exit_code == 0, generated.output

    _write_generated(
        root,
        "directive",
        _OWN_ID,
        {"title": "Project Intent Directive", "intent": _OWN_PHRASE, "enforcement": "required"},
        filename=f"{_OWN_STEM}.directive.yaml",
    )
    _write_generated(
        root,
        "directive",
        "PROJECT_002",
        {"title": "Risk Appetite Directive", "intent": "Take moderate risks.", "enforcement": "advisory"},
        filename="002-risk-appetite-directive.directive.yaml",
    )
    _write_tactic(root, "testing-philosophy-tactic")
    _write_tactic(root, _BUILT_IN_COMPANION)
    _write_generated(root, "styleguide", "testing-style-guide", {"title": "Testing", "scope": "code", "principles": ["Be good."]})

    first = _invoke("synthesize", "--json")
    assert first.exit_code == 0, first.output
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "synthesized once")


@pytest.fixture(scope="module")
def synthesized_template(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Path]:
    """Build the synthesized-once project ONCE per module (``charter generate`` costs ~5 s).

    ``charter_cwd_isolation`` is function-scoped, so the module-scoped build
    applies the same two changes (process working directory and the charter
    package's ``find_repo_root``) through its own ``MonkeyPatch`` context, undone
    when the module finishes. Every test then copies the template and isolates
    onto its copy with ``charter_cwd_isolation``.
    """
    root = tmp_path_factory.mktemp("synthesized-6510")
    with pytest.MonkeyPatch.context() as mp:
        mp.chdir(root)
        mp.setattr(CHARTER_FIND_REPO_ROOT, lambda *args, **kwargs: root)
        _build_template(root)
    yield root


@pytest.fixture
def project(tmp_path: Path, synthesized_template: Path, charter_cwd_isolation: Callable[..., Path]) -> Path:
    root = tmp_path / "project"
    shutil.copytree(synthesized_template, root, symlinks=True)
    return charter_cwd_isolation(root)


def _activate_own_and_built_in(root: Path) -> None:
    """Explicit list that names synthesis's own directive, kept to two entries."""
    seed_activation_ledger(root, activated_directives=[_OWN_STEM, _BUILT_IN_STEM])


def _request(root: Path) -> Any:
    request, _ = _build_synthesis_request(root, "generated")
    return request


def _node_urns(request: Any) -> list[str]:
    return [node["urn"] for node in request.drg_snapshot["nodes"]]


def _target_ids(request: Any) -> list[str]:
    snapshot = request.interview_snapshot
    return [target.artifact_id for target in build_targets(snapshot, resolve_sections(snapshot), request.drg_snapshot)]


# ---------------------------------------------------------------------------
# Acceptance: the real CLI entry points
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.git_repo
def test_resynthesize_after_activation_succeeds(project: Path) -> None:
    """FR-001 / SC-001: synthesize after activating a directive exits 0, no self-collision."""
    _activate_own_and_built_in(project)
    # Authored so a run that still (wrongly) demands it fails on the collision, not on a missing file.
    _write_tactic(project, _OWN_COMPANION)

    result = _invoke("synthesize", "--json")

    assert "colliding_urn" not in result.output, result.output
    assert result.exit_code == 0, result.output


@pytest.mark.integration
@pytest.mark.git_repo
def test_resynthesize_after_activation_via_charter_activate(project: Path) -> None:
    """Same contract when the second directive is activated through ``charter activate``.

    The list is made explicit first (as the activate command's materialisation
    would), so the real command appends to two entries instead of expanding to
    every built-in directive, which would demand ~39 companion tactics.
    """
    seed_activation_ledger(project, activated_directives=[_OWN_STEM])
    activated = _invoke("activate", "directive", _BUILT_IN_STEM, "--no-compile")
    assert activated.exit_code == 0, activated.output
    _write_tactic(project, _OWN_COMPANION)

    result = _invoke("synthesize", "--json")

    assert "colliding_urn" not in result.output, result.output
    assert result.exit_code == 0, result.output


@pytest.mark.integration
@pytest.mark.git_repo
def test_resynthesize_topic_project_directive_succeeds(project: Path) -> None:
    """FR-002: ``charter resynthesize --topic directive:PROJECT_001`` exits 0 after activation."""
    _activate_own_and_built_in(project)
    _write_tactic(project, _OWN_COMPANION)

    result = _invoke("resynthesize", "--topic", _OWN_URN)

    assert "colliding_urn" not in result.output, result.output
    assert result.exit_code == 0, result.output


@pytest.mark.integration
@pytest.mark.git_repo
def test_owned_directive_still_delivered(project: Path) -> None:
    """FR-004 / SC-002: right after a successful re-synthesis the project directive is still delivered."""
    _activate_own_and_built_in(project)
    synthesized = _invoke("synthesize", "--json")
    assert synthesized.exit_code == 0, synthesized.output

    context = _invoke("context", "--action", "implement", "--json")

    assert context.exit_code == 0, context.output
    assert _OWN_PHRASE in context.output


@pytest.mark.integration
@pytest.mark.git_repo
def test_activation_files_untouched(project: Path) -> None:
    """FR-005 / SC-004: synthesize and resynthesize never write the activation ledger."""
    _activate_own_and_built_in(project)
    before = (project / _ACTIVATION).read_bytes()

    synthesized = _invoke("synthesize", "--json")
    resynthesized = _invoke("resynthesize", "--topic", _OWN_URN)

    assert synthesized.exit_code == 0, synthesized.output
    assert resynthesized.exit_code == 0, resynthesized.output
    assert (project / _ACTIVATION).read_bytes() == before


@pytest.mark.integration
@pytest.mark.git_repo
def test_no_companion_tactic_for_own_directive(project: Path) -> None:
    """Spec US1 scenario 4: no ``how-we-apply-project-001`` is demanded (it is never authored here)."""
    _activate_own_and_built_in(project)
    assert not (project / _GENERATED / "tactics" / f"{_OWN_COMPANION}.tactic.yaml").exists()

    result = _invoke("synthesize", "--json")

    assert _OWN_COMPANION not in result.output, result.output
    assert result.exit_code == 0, result.output


@pytest.mark.integration
@pytest.mark.git_repo
def test_hand_authored_directive_kept_in_snapshot(project: Path) -> None:
    """FR-008: an activated project directive synthesis does NOT own stays synthesis input."""
    team = project / ".kittify" / "charter-packs" / "directive" / "050-team-directive.directive.yaml"
    team.write_text(
        yaml.safe_dump({"id": "TEAM_001", "schema_version": "1.0", "title": "Team Directive", "intent": "Pair on risky work.", "enforcement": "advisory"}),
        encoding="utf-8",
    )
    seed_activation_ledger(project, activated_directives=[_OWN_STEM, "050-team-directive"])

    request = _request(project)

    assert "TEAM_001" in request.interview_snapshot["selected_directives"]
    assert "directive:TEAM_001" in _node_urns(request)
    assert "how-we-apply-team-001" in _target_ids(request)


def _sidecar_adapters(root: Path, urn: str) -> set[str]:
    """``adapter_id`` of every provenance sidecar the synthesis manifest lists for *urn*."""
    manifest = yaml.safe_load((root / MANIFEST_PATH).read_text(encoding="utf-8"))
    sidecars = [yaml.safe_load((root / entry["provenance_path"]).read_text(encoding="utf-8")) for entry in manifest["artifacts"]]
    return {sidecar["adapter_id"] for sidecar in sidecars if sidecar["artifact_urn"] == urn}


def _write_team_directive(root: Path) -> None:
    team = root / ".kittify" / "charter-packs" / "directive" / f"{_TEAM_STEM}.directive.yaml"
    team.write_text(
        yaml.safe_dump({"id": _TEAM_ID, "schema_version": "1.0", "title": "Team Directive", "intent": "Pair on risky work.", "enforcement": "advisory"}),
        encoding="utf-8",
    )


@pytest.mark.integration
@pytest.mark.git_repo
def test_hand_authored_directive_activated_through_cli_stays_input(project: Path) -> None:
    """FR-008 through the real ``charter activate``: its direct-write registration is not synthesis ownership.

    ``charter activate`` registers every hand-authored project directive in the
    synthesis manifest with a ``project-direct-write`` sidecar. That record says
    the file was registered, not that synthesis created it, so ``TEAM_001``
    stays synthesis input and its companion tactic is still demanded.
    """
    _write_team_directive(project)
    seed_activation_ledger(project, activated_directives=[_OWN_STEM])
    activated = _invoke("activate", "directive", _TEAM_STEM, "--no-compile")
    assert activated.exit_code == 0, activated.output
    assert _TEAM_STEM in (project / _ACTIVATION).read_text(encoding="utf-8")

    request = _request(project)

    assert _TEAM_ID in request.interview_snapshot["selected_directives"]
    assert f"directive:{_TEAM_ID}" in _node_urns(request)
    assert _TEAM_COMPANION in _target_ids(request)
    assert _OWN_ID not in request.interview_snapshot["selected_directives"]


@pytest.mark.integration
@pytest.mark.git_repo
def test_own_directive_reregistered_by_activate_stays_owned(project: Path) -> None:
    """A synthesized ``PROJECT_001`` that ``charter activate`` re-registers as direct-write is still owned.

    Activation adds a second, ``project-direct-write`` record for the
    synthesized directive; the synthesis record still owns it, so the
    re-synthesis exits 0 without demanding its companion tactic.
    """
    seed_activation_ledger(project, activated_directives=[_BUILT_IN_STEM])
    activated = _invoke("activate", "directive", _OWN_STEM, "--no-compile")
    assert activated.exit_code == 0, activated.output
    assert _sidecar_adapters(project, _OWN_URN) >= {"project-direct-write", "generated"}

    request = _request(project)
    result = _invoke("synthesize", "--json")

    assert _OWN_ID not in request.interview_snapshot["selected_directives"]
    assert _OWN_COMPANION not in _target_ids(request)
    assert "colliding_urn" not in result.output, result.output
    assert result.exit_code == 0, result.output


@pytest.mark.integration
@pytest.mark.git_repo
def test_ownership_read_only_when_list_explicit(project: Path) -> None:
    """NFR-002 / D-3: with the activation key absent the manifest is not read at all."""
    (project / MANIFEST_PATH).write_text("artifacts: [this is: not a manifest\n", encoding="utf-8")

    request = _request(project)

    assert request.interview_snapshot["selected_directives"] == []
    assert request.drg_snapshot["nodes"] == []


# ---------------------------------------------------------------------------
# Request-builder edge cases (no CLI)
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.git_repo
def test_unreadable_manifest_fails_closed_for_explicit_list(project: Path) -> None:
    """NFR-002: an explicit list needs ownership, and an unreadable record refuses (never "nothing owned")."""
    _activate_own_and_built_in(project)
    (project / MANIFEST_PATH).write_text("artifacts: [this is: not a manifest\n", encoding="utf-8")

    with pytest.raises(SynthesisError, match="synthesis-manifest.yaml"):
        _request(project)


@pytest.mark.integration
@pytest.mark.git_repo
def test_every_owned_directive_is_excluded(project: Path) -> None:
    """Several owned directives (PROJECT_001, PROJECT_002) all leave both outputs; built-ins stay."""
    seed_activation_ledger(project, activated_directives=[_OWN_STEM, "002-risk-appetite-directive", _BUILT_IN_STEM])

    request = _request(project)

    assert request.interview_snapshot["selected_directives"] == ["DIRECTIVE_003"]
    assert _node_urns(request) == ["directive:DIRECTIVE_003"]


@pytest.mark.integration
@pytest.mark.git_repo
def test_deactivated_own_directive_leaves_nothing_to_exclude(project: Path) -> None:
    """Control: the project directive is not in the list, the list is used as is."""
    seed_activation_ledger(project, activated_directives=[_BUILT_IN_STEM])

    request = _request(project)

    assert request.interview_snapshot["selected_directives"] == ["DIRECTIVE_003"]
    assert _node_urns(request) == ["directive:DIRECTIVE_003"]
    assert _BUILT_IN_COMPANION in _target_ids(request)


# ---------------------------------------------------------------------------
# Directive synthesis-input derivation (pure helper)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_directive_inputs_empty() -> None:
    assert _directive_synthesis_inputs([]) == ([], [])


@pytest.mark.unit
def test_directive_inputs_preserve_order_and_shape() -> None:
    selected, nodes = _directive_synthesis_inputs(["DIRECTIVE_010", "DIRECTIVE_003", "TEAM_001"])

    assert selected == ["DIRECTIVE_010", "DIRECTIVE_003", "TEAM_001"]
    assert [node["urn"] for node in nodes] == ["directive:DIRECTIVE_010", "directive:DIRECTIVE_003", "directive:TEAM_001"]
    assert all(set(node) == {"urn", "kind"} and node["kind"] == "directive" for node in nodes)


@pytest.mark.unit
def test_directive_inputs_drop_owned_ids_from_both_outputs() -> None:
    selected, nodes = _directive_synthesis_inputs(
        ["DIRECTIVE_003", "PROJECT_001", "TEAM_001", "PROJECT_002"],
        frozenset({"PROJECT_001", "PROJECT_002", "PROJECT_009"}),
    )

    assert selected == ["DIRECTIVE_003", "TEAM_001"]
    assert [node["urn"] for node in nodes] == ["directive:DIRECTIVE_003", "directive:TEAM_001"]
