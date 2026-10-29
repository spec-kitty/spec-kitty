"""#6510 / #4226 -- a remaining synthesis URN collision names its origin and the remedy (FR-007).

After WP01 synthesis no longer collides with its own directives, so a collision
that remains is a real clash. The refusal used to say the node was "built-in"
and that synthesized artifacts "must carry new URNs", which sent operators to
rename the tool's own identifiers. ``collision_remedy`` classifies the colliding
node (unowned project directive, synthesis-owned project directive, built-in or
org node, or an unreadable ownership record) and the ``synthesize`` /
``resynthesize`` commands print that remedy in human and ``--json`` output.

The CLI cases drive the real commands on a real "synthesized once" project
(the fixture approach of ``test_resynthesis_after_activation_6510.py``; the
small seed is duplicated here rather than imported from that test module).
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

from charter.activation.synthesizer.errors import DuplicateTargetError, ProjectDRGValidationError
from charter.activation.synthesizer.manifest import MANIFEST_PATH
from specify_cli.cli.commands.charter import app
from tests._factories.activation_ledger import seed_activation_ledger
from tests._support.charter_cwd import CHARTER_FIND_REPO_ROOT

runner = CliRunner()

_GENERATED = Path(".kittify/charter/generated")
_PROJECT_DIRECTIVES = Path(".kittify/charter-packs/directive")
_PLURALS = {"directive": "directives", "tactic": "tactics", "styleguide": "styleguides"}

_OWN_STEM = "001-project-intent-directive"
_OWN_ID = "PROJECT_001"
_OWN_URN = f"directive:{_OWN_ID}"
_BUILT_IN_STEM = "003-decision-documentation-requirement"
_MANIFEST = MANIFEST_PATH.as_posix()
_NO_DEACTIVATE = "Do not deactivate it"

_ANSWERS = (
    "schema_version: '1'\nmission: software-dev\nprofile: minimal\nanswers:\n"
    "  mission_type: software_dev\n  testing_philosophy: test-driven\n  risk_appetite: moderate\n"
    "selected_paradigms: []\nselected_directives: []\navailable_tools: []\n"
)


def _error(urn: str | None) -> ProjectDRGValidationError:
    return ProjectDRGValidationError(errors=("collision",), merged_graph_summary="s", colliding_urn=urn)


def _write_directive(folder: Path, stem: str, directive_id: str) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    body = {"id": directive_id, "schema_version": "1.0", "title": "Hand Directive", "intent": "Pair on risky work.", "enforcement": "advisory"}
    (folder / f"{stem}.directive.yaml").write_text(yaml.safe_dump(body), encoding="utf-8")


def _assert_never_advises_deactivation_or_renaming_urns(text: str) -> None:
    assert "new URNs" not in text
    # The only mention of deactivation is the warning against it.
    assert text.lower().count("deactivate") == text.count(_NO_DEACTIVATE)


def collision_remedy(repo_root: Path, error: Any) -> str | None:
    """Import at call time, so the CLI cases go red on their assertions before the module exists."""
    from specify_cli.cli.commands.charter._collision_remedy import collision_remedy as _remedy

    return _remedy(repo_root, error)


# ---------------------------------------------------------------------------
# Classifier (pure, real files)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_unowned_project_directive_names_manifest_and_hand_authored_remedy(tmp_path: Path) -> None:
    _write_directive(tmp_path / _PROJECT_DIRECTIVES, _OWN_STEM, _OWN_ID)

    text = collision_remedy(tmp_path, _error(_OWN_URN))

    assert text is not None
    assert _OWN_ID in text
    assert "synthesis did not create" in text
    assert _MANIFEST in text
    assert "provenance sidecar" in text
    assert "id synthesis does not generate" in text
    assert _NO_DEACTIVATE in text
    assert "built-in" not in text
    _assert_never_advises_deactivation_or_renaming_urns(text)


@pytest.mark.unit
def test_upstream_node_says_built_in_or_org(tmp_path: Path) -> None:
    text = collision_remedy(tmp_path, _error("directive:DIRECTIVE_003"))

    assert text is not None
    assert "DIRECTIVE_003" in text
    assert "built-in or org" in text
    assert "never overwrites" in text
    assert _MANIFEST not in text
    _assert_never_advises_deactivation_or_renaming_urns(text)


@pytest.mark.unit
def test_non_directive_urn_is_upstream(tmp_path: Path) -> None:
    text = collision_remedy(tmp_path, _error("agent_profile:researcher-ryan"))

    assert text is not None
    assert "built-in or org" in text


@pytest.mark.unit
def test_unreadable_ownership_record_is_named_never_guessed(tmp_path: Path) -> None:
    _write_directive(tmp_path / _PROJECT_DIRECTIVES, _OWN_STEM, _OWN_ID)
    manifest = tmp_path / MANIFEST_PATH
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text("artifacts: [this is: not a manifest\n", encoding="utf-8")

    text = collision_remedy(tmp_path, _error(_OWN_URN))

    assert text is not None
    assert "unreadable" in text
    assert _MANIFEST in text
    assert "synthesis did not create" not in text
    assert "built-in or org" not in text
    assert _NO_DEACTIVATE in text


@pytest.mark.unit
def test_unreadable_project_directive_files_are_named(tmp_path: Path) -> None:
    folder = tmp_path / _PROJECT_DIRECTIVES
    folder.mkdir(parents=True)
    (folder / "broken.directive.yaml").write_text("id: [unterminated\n", encoding="utf-8")

    text = collision_remedy(tmp_path, _error(_OWN_URN))

    assert text is not None
    assert "could not be read" in text
    assert _PROJECT_DIRECTIVES.as_posix() in text
    assert "built-in or org" not in text


@pytest.mark.unit
def test_no_colliding_urn_gives_no_remedy(tmp_path: Path) -> None:
    assert collision_remedy(tmp_path, _error(None)) is None


@pytest.mark.unit
def test_other_synthesis_error_gives_no_remedy(tmp_path: Path) -> None:
    assert collision_remedy(tmp_path, DuplicateTargetError(kind="directive", slug="x", occurrences=2)) is None


# ---------------------------------------------------------------------------
# Real CLI: a "synthesized once" project whose ownership record was lost
# ---------------------------------------------------------------------------


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)


def _invoke(*args: str) -> Result:
    return runner.invoke(app, list(args), catch_exceptions=False)


def _write_generated(root: Path, kind: str, artifact_id: str, body: dict[str, Any], filename: str | None = None) -> None:
    folder = root / _GENERATED / _PLURALS[kind]
    folder.mkdir(parents=True, exist_ok=True)
    name = filename or f"{artifact_id}.{kind}.yaml"
    (folder / name).write_text(yaml.safe_dump({"id": artifact_id, "schema_version": "1.0", **body}), encoding="utf-8")


def _write_tactic(root: Path, tactic_id: str) -> None:
    _write_generated(root, "tactic", tactic_id, {"name": tactic_id, "purpose": "p", "steps": [{"title": "s", "description": "d"}]})


def _build_template(root: Path) -> None:
    _git(root, "init", "--initial-branch=main")
    _git(root, "config", "user.email", "test@example.com")
    _git(root, "config", "user.name", "Test")
    answers = root / ".kittify" / "charter" / "interview" / "answers.yaml"
    answers.parent.mkdir(parents=True, exist_ok=True)
    answers.write_text(_ANSWERS, encoding="utf-8")
    generated = _invoke("generate", "--from-interview")
    assert generated.exit_code == 0, generated.output
    own = {"title": "Project Intent Directive", "intent": "Serve the outcome.", "enforcement": "required"}
    _write_generated(root, "directive", _OWN_ID, own, filename=f"{_OWN_STEM}.directive.yaml")
    risk = {"title": "Risk Appetite Directive", "intent": "Take moderate risks.", "enforcement": "advisory"}
    _write_generated(root, "directive", "PROJECT_002", risk, filename="002-risk-appetite-directive.directive.yaml")
    _write_tactic(root, "testing-philosophy-tactic")
    _write_tactic(root, "how-we-apply-directive-003")
    _write_tactic(root, "how-we-apply-project-001")
    _write_generated(root, "styleguide", "testing-style-guide", {"title": "Testing", "scope": "code", "principles": ["Be good."]})
    first = _invoke("synthesize", "--json")
    assert first.exit_code == 0, first.output
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "synthesized once")


@pytest.fixture(scope="module")
def synthesized_template(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Path]:
    root = tmp_path_factory.mktemp("collision-6510")
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


def _lose_ownership_record(root: Path) -> None:
    """The synthesized PROJECT_001 stays activated, but the manifest no longer records that synthesis owns it."""
    seed_activation_ledger(root, activated_directives=[_OWN_STEM, _BUILT_IN_STEM])
    manifest_file = root / MANIFEST_PATH
    manifest = yaml.safe_load(manifest_file.read_text(encoding="utf-8"))
    kept = [entry for entry in manifest["artifacts"] if _OWN_STEM not in entry["path"]]
    assert len(kept) == len(manifest["artifacts"]) - 1, manifest["artifacts"]
    manifest["artifacts"] = kept
    manifest_file.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")


@pytest.mark.integration
@pytest.mark.git_repo
def test_synthesis_owned_directive_is_not_called_unowned(project: Path) -> None:
    """Never guess: a recorded, synthesis-owned directive is not reported as hand-authored or upstream."""
    text = collision_remedy(project, _error(_OWN_URN))

    assert text is not None
    assert "synthesis created" in text
    assert "synthesis did not create" not in text
    assert "built-in or org" not in text
    _assert_never_advises_deactivation_or_renaming_urns(text)


@pytest.mark.integration
@pytest.mark.git_repo
def test_synthesize_json_refusal_carries_remedy(project: Path) -> None:
    _lose_ownership_record(project)

    result = _invoke("synthesize", "--json")

    assert result.exit_code == 1, result.output
    payload = json.loads(result.stdout)
    warnings = payload["warnings"]
    assert any("built-in DRG layer" not in w and _OWN_URN in w for w in warnings if w.startswith("SynthesisError"))
    remedy = [w for w in warnings if _MANIFEST in w and "synthesis did not create" in w]
    assert remedy, warnings
    assert _NO_DEACTIVATE in remedy[0]


@pytest.mark.integration
@pytest.mark.git_repo
def test_synthesize_human_refusal_prints_hint(project: Path) -> None:
    _lose_ownership_record(project)

    result = _invoke("synthesize")

    assert result.exit_code == 1, result.output
    flat = " ".join(result.output.split())
    assert "Hint:" in flat
    assert "synthesis did not create" in flat
    assert _MANIFEST in flat
    assert "built-in DRG layer" not in flat


@pytest.mark.integration
@pytest.mark.git_repo
def test_resynthesize_json_refusal_carries_remedy(project: Path) -> None:
    _lose_ownership_record(project)

    result = _invoke("resynthesize", "--topic", _OWN_URN, "--json")

    assert result.exit_code == 1, result.output
    payload = json.loads(result.stdout)
    assert _OWN_URN in payload["error"]
    assert "synthesis did not create" in payload["error"]
    assert _MANIFEST in payload["error"]


@pytest.mark.integration
@pytest.mark.git_repo
def test_resynthesize_human_refusal_prints_hint(project: Path) -> None:
    _lose_ownership_record(project)

    result = _invoke("resynthesize", "--topic", _OWN_URN)

    assert result.exit_code == 1, result.output
    flat = " ".join(result.output.split())
    assert "Hint:" in flat
    assert "synthesis did not create" in flat
