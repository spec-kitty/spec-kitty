"""#6768 -- resynthesizing a hand-authored project directive is an honest no-op, not a collision.

A `charter resynthesize --topic directive:<PROJECT_xxx>` run refused a directive the project
authored itself with the FR-020 / EC-6 additive-only violation, because the topic's target
reached the check although synthesis writes nothing for it. A bounded run now drops a target
nothing generates, and reports "nothing to regenerate" when none is left.

The check itself keeps refusing a real write over something synthesis did not create: it reads
the shipped DRG plus the activated directives synthesis does not own
(`test_collision_refusal_6510.py` pins the hand-written directive). `drg_snapshot` stays the
narrower reference universe the project's own references resolve against.

These tests drive the real `charter activate` / `charter resynthesize` commands. The fixture
reaches the reported state exactly: a `PROJECT_*` directive the project authored itself and
activated, so it is in `activated_directives` but the synthesis manifest records it as a
`project-direct-write` registration, never as synthesis ownership.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
import yaml
from typer.testing import CliRunner, Result

from charter.activation.synthesizer.errors import ProjectDRGValidationError
from charter.activation.synthesizer.project_drg import emit_project_layer
from charter.activation.synthesizer.request import SynthesisRequest, SynthesisTarget
from charter.activation.synthesizer.targets import build_targets
from charter.offering.drg.loader import DRGLoadError, load_built_in_graph
from specify_cli.cli.commands.charter import app
from specify_cli.cli.commands.charter._synthesis import _build_synthesis_request
from tests._factories.activation_ledger import seed_activation_ledger
from tests._support.charter_cwd import CHARTER_FIND_REPO_ROOT

runner = CliRunner()

_GENERATED = Path(".kittify/charter/generated")
_PROJECT_DIRECTIVES = Path(".kittify/charter-packs/directive")
_PLURALS = {"directive": "directives", "tactic": "tactics", "styleguide": "styleguides"}

#: The project directive the project author wrote and activated itself (issue state).
_AUTHORED_STEM = "007-local-guardrail"
_AUTHORED_ID = "PROJECT_007"
_AUTHORED_URN = f"directive:{_AUTHORED_ID}"
_AUTHORED_COMPANION = "how-we-apply-project-007"
_AUTHORED_PHRASE = "Every change names the guardrail it serves."

#: A synthesis-created directive of the first run (synthesis ownership, #6510's case).
_OWNED_STEM = "001-project-intent-directive"
_OWNED_SLUG = "project-intent-directive"

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


def _write_tactic(root: Path, tactic_id: str, purpose: str = "p") -> None:
    _write_generated(root, "tactic", tactic_id, {"name": tactic_id, "purpose": purpose, "steps": [{"title": "s", "description": "d"}]})


def _invoke(*args: str) -> Result:
    return runner.invoke(app, list(args), catch_exceptions=False)


def _build_template(root: Path) -> None:
    """Reach a real "synthesized once" project through the real commands.

    ``charter generate`` compiles the bundle from a seeded interview record, the
    ``generated`` adapter gets one minimal body per target that interview names, and
    ``charter synthesize`` promotes them while the activation key is still absent (the
    first-run state). Two project directives are synthesized, so the project below starts
    with a populated manifest -- the precondition the issue reports.
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
        "PROJECT_001",
        {"title": "Project Intent Directive", "intent": "Name the outcome.", "enforcement": "required"},
        filename=f"{_OWNED_STEM}.directive.yaml",
    )
    _write_generated(
        root,
        "directive",
        "PROJECT_002",
        {"title": "Risk Appetite Directive", "intent": "Take moderate risks.", "enforcement": "advisory"},
        filename="002-risk-appetite-directive.directive.yaml",
    )
    _write_tactic(root, "testing-philosophy-tactic")
    _write_generated(root, "styleguide", "testing-style-guide", {"title": "Testing", "scope": "code", "principles": ["Be good."]})

    first = _invoke("synthesize", "--json")
    assert first.exit_code == 0, first.output
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "synthesized once")


@pytest.fixture(scope="module")
def synthesized_template(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Path]:
    """Build the synthesized-once project ONCE per module (``charter generate`` costs ~5 s)."""
    root = tmp_path_factory.mktemp("project-directive-6768")
    with pytest.MonkeyPatch.context() as mp:
        mp.chdir(root)
        mp.setattr(CHARTER_FIND_REPO_ROOT, lambda *args, **kwargs: root)
        _build_template(root)
    yield root


def _author_and_activate_project_directive(root: Path) -> None:
    """Author a project directive and register it the way a project operator does.

    ``charter activate`` records the file as a ``project-direct-write`` registration, which
    is deliberately *not* synthesis ownership -- the state #6768 reports. The activation
    list is made explicit first so the ledger stays small and the companion-tactic
    expansion stays predictable.
    """
    seed_activation_ledger(root, activated_directives=[_OWNED_STEM])
    folder = root / _PROJECT_DIRECTIVES
    folder.mkdir(parents=True, exist_ok=True)
    body = {
        "id": _AUTHORED_ID,
        "schema_version": "1.0",
        "title": "Local Guardrail",
        "intent": _AUTHORED_PHRASE,
        "enforcement": "advisory",
    }
    (folder / f"{_AUTHORED_STEM}.directive.yaml").write_text(yaml.safe_dump(body), encoding="utf-8")

    activated = _invoke("activate", "directive", _AUTHORED_STEM, "--no-compile")
    assert activated.exit_code == 0, activated.output
    # `charter activate` makes synthesis expect the companion tactic; author it so a run
    # that still demanded it fails on the collision, never on a missing file.
    _write_tactic(root, _AUTHORED_COMPANION, purpose="Apply the local guardrail.")


@pytest.fixture
def project(
    tmp_path: Path,
    synthesized_template: Path,
    charter_cwd_isolation: Callable[..., Path],
) -> Path:
    root = tmp_path / "project"
    shutil.copytree(synthesized_template, root, symlinks=True)
    isolated = charter_cwd_isolation(root)
    _author_and_activate_project_directive(isolated)
    return isolated


# ---------------------------------------------------------------------------
# FR-001 / SC-001 -- the reported refusal
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.git_repo
def test_resynthesize_hand_authored_directive_reports_nothing_to_regenerate(project: Path) -> None:
    """Exit 0 and an honest report: no refusal, no false "regenerated", and the file is untouched."""
    directive = project / _PROJECT_DIRECTIVES / f"{_AUTHORED_STEM}.directive.yaml"
    before = directive.read_bytes()

    result = _invoke("resynthesize", "--topic", _AUTHORED_URN, "--json")

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["result"] == "noop"
    assert "Nothing to regenerate" in payload["diagnostic"]
    assert "regenerated" not in payload
    assert directive.read_bytes() == before


@pytest.mark.integration
@pytest.mark.git_repo
@pytest.mark.parametrize(
    "args",
    [("synthesize", "--json"), ("synthesize", "--dry-run", "--json"), ("resynthesize", "--topic", f"directive:{_OWNED_SLUG}", "--json")],
    ids=["synthesize", "dry-run", "resynthesize"],
)
def test_project_profile_shadowing_a_shipped_profile_refuses_with_its_remedy(project: Path, args: tuple[str, ...]) -> None:
    """Each write path reads the shipped graph, including nodes no one activated, and prints the remedy."""
    profile_id = next(node.urn for node in load_built_in_graph().nodes if node.kind.value == "agent_profile").partition(":")[2]
    profiles = project / ".kittify" / "charter-packs" / "agent_profiles"
    profiles.mkdir(parents=True, exist_ok=True)
    (profiles / f"{profile_id}.agent.yaml").write_text(f"profile-id: {profile_id}\nname: Shadow\n", encoding="utf-8")

    result = _invoke(*args)

    assert result.exit_code == 1, result.output
    assert f"agent_profile:{profile_id}" in result.output
    assert "Give the project profile a profile-id" in result.output


# ---------------------------------------------------------------------------
# FR-002 / SC-002 -- the additive-only positive control
# ---------------------------------------------------------------------------


def _target(urn: str) -> SynthesisTarget:
    kind, _, identifier = urn.partition(":")
    return SynthesisTarget(
        kind=kind,
        slug=identifier.lower().replace("_", "-"),
        title="collision probe",
        artifact_id=identifier,
        source_section="manual",
    )


@pytest.mark.integration
def test_built_in_urn_still_refuses_and_project_urn_does_not(project: Path) -> None:
    """The gate still fires for shipped doctrine, and demonstrably not for a project node.

    Both cases run on the same shipped graph and the same project root, so the probe can
    see the difference: a control that only asserted "no collision" would also pass if the
    check had been disabled outright.
    """
    shipped = load_built_in_graph()
    built_in_urn = next(node.urn for node in shipped.nodes if node.kind.value == "directive")

    with pytest.raises(ProjectDRGValidationError) as raised:
        emit_project_layer([_target(built_in_urn)], "4.0.0", shipped, project)

    assert raised.value.colliding_urn == built_in_urn

    # Positive control on the same graph and root: a project-layer URN is not a collision.
    overlay = emit_project_layer([_target(_AUTHORED_URN)], "4.0.0", shipped, project)

    assert [node.urn for node in overlay.nodes if node.urn == _AUTHORED_URN] == [_AUTHORED_URN]


# ---------------------------------------------------------------------------
# FR-004 / SC-001 -- the request carries two distinguishable layers
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_request_additive_layer_is_the_shipped_graph_plus_the_reference_universe(project: Path) -> None:
    """The additive layer refuses over shipped and activated nodes; references stay narrower."""
    request, _ = _build_synthesis_request(project, "generated")

    additive = frozenset(node["urn"] for node in request.additive_drg_snapshot["nodes"])
    reference = frozenset(node["urn"] for node in request.drg_snapshot["nodes"])
    shipped = frozenset(node.urn for node in load_built_in_graph().nodes)

    assert _AUTHORED_URN in reference
    assert additive == shipped | reference
    assert shipped - reference, "the reference universe must stay narrower than the shipped graph"


# ---------------------------------------------------------------------------
# FR-005 / NFR-002 -- the fallback rules
# ---------------------------------------------------------------------------


def test_additive_snapshot_falls_back_to_the_reference_universe() -> None:
    """A request without the new field behaves exactly as before (every existing caller)."""
    from charter.activation.synthesizer.request import additive_snapshot

    snapshot = {"nodes": [{"urn": "directive:DIRECTIVE_003", "kind": "directive"}], "edges": []}
    request = SynthesisRequest(
        target=_target("directive:PROJECT_001"),
        interview_snapshot={},
        doctrine_snapshot={},
        drg_snapshot=snapshot,
        run_id="01M00000000000000000000000",
    )

    assert request.additive_drg_snapshot is None
    assert additive_snapshot(request) is snapshot


@pytest.mark.integration
def test_unloadable_built_in_graph_keeps_the_previous_behaviour(project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A shipped graph that fails to load falls back to the reference snapshot."""

    def _explode() -> Any:
        raise DRGLoadError("built-in graph unreadable")

    # The builder imports through the charter proxy (`charter.drg`), which the
    # runtime doctrine-boundary ratchet enforces; patch that seam.
    monkeypatch.setattr("charter.drg.load_built_in_graph", _explode)

    request, _ = _build_synthesis_request(project, "generated")

    assert request.additive_drg_snapshot is None
    assert request.drg_snapshot["nodes"]


# ---------------------------------------------------------------------------
# FR-003 / SC-003 -- the reference universe still resolves, and still fails closed
# ---------------------------------------------------------------------------


def _selected_directive_mapping(directive_id: str) -> list[tuple[str, dict[str, Any]]]:
    """The companion-tactic mapping `resolve_sections` produces for a selected directive."""
    return [
        (
            "selected_directives",
            {
                "answer": directive_id,
                "kinds": ["tactic"],
                "source_section": "selected_directives",
                "source_urns": (f"directive:{directive_id}",),
                "directive_id": directive_id,
            },
        )
    ]


@pytest.mark.integration
def test_reference_universe_accepts_the_project_urn_and_refuses_an_undeclared_one(project: Path) -> None:
    """EC-2 resolves a project reference and still fails closed on one no layer declares.

    The two assertions read the SAME reference snapshot, so the passing half cannot be
    satisfied by a universe that stopped checking anything.
    """
    request, _ = _build_synthesis_request(project, "generated")
    snapshot = dict(request.drg_snapshot)

    resolved = build_targets(
        interview_snapshot={},
        mappings=_selected_directive_mapping("PROJECT_007"),
        drg_snapshot=snapshot,
    )
    assert [target.urn for target in resolved] == [f"tactic:{_AUTHORED_COMPANION}"]
    assert resolved[0].source_urns == ("directive:PROJECT_007",)

    with pytest.raises(ProjectDRGValidationError) as raised:
        build_targets(
            interview_snapshot={},
            mappings=_selected_directive_mapping("PROJECT_999"),
            drg_snapshot=snapshot,
        )

    assert "directive:PROJECT_999" in str(raised.value)


@pytest.mark.integration
@pytest.mark.git_repo
def test_synthesize_promotes_the_companion_tactic(project: Path) -> None:
    """A full synthesis run keeps the project reference edge it needs (production path)."""
    result = _invoke("synthesize", "--json")

    assert "colliding_urn" not in result.output, result.output
    assert result.exit_code == 0, result.output
    graph = (project / ".kittify" / "charter-packs" / "graph.yaml").read_text(encoding="utf-8")
    assert _AUTHORED_URN in graph
    assert f"tactic:{_AUTHORED_COMPANION}" in graph
