"""A declared id whose file name another layer uses for a different id is refused; mandatory policy prevents generation."""

import json
from pathlib import Path
import subprocess

import pytest
from ruamel.yaml import YAML
from typer.testing import CliRunner

from charter.activation.active_charter_service_builder import build_active_charter_service
from charter.activation.kind_vocabulary import ArtifactKind
from charter.offering.pack_paths import built_in_dir
from specify_cli.cli.commands.charter import app

pytestmark = [pytest.mark.unit, pytest.mark.git_repo]


@pytest.mark.parametrize("required", [False, True])
def test_colliding_directive_selection_refuses_the_interview(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, required: bool) -> None:
    """a8dd1812 (Decision ``file_name_collision``): the interview refuses a colliding declared id.

    History: this test pinned the older warn-and-skip flow (exit 0, a ``promotion_warnings`` entry,
    the resolvable siblings kept). A declared id whose file name another layer uses for a different
    id is now a pack-content error and every writer, the interview included, refuses it: exit 1,
    naming both files. Only UNKNOWN selection ids are still warned and skipped. The sibling-preserving
    promotion is pinned by ``tests/specify_cli/upgrade/test_unify_charter_activation_migration.py::
    test_ambiguous_answer_is_reported_without_dropping_resolvable_sibling`` and the collision refusal
    end to end by ``tests/charter/activation/test_stored_spelling_6527.py``.

    The ``generate`` legs of the old test stay reachable and are kept: with the refused interview's
    saved answers generate succeeds (``required=False``), and with no answers it refuses the same
    collision (``required=True``).

    The interview's ``--json`` error keeps its own ``{result, success, error}`` shape (``_emit_error``);
    #6557's typed ``{ok, error:{code, message}}`` envelope belongs to ``charter status`` only.
    """
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / ".kittify").mkdir()
    packs = [tmp_path / "company", tmp_path / "team"]
    for pack, identity in zip(packs, ["COMPANY-SEC", "TEAM-SEC"], strict=True):
        (pack / "directives").mkdir(parents=True)
        (pack / "directives/security.directive.yaml").write_text(
            f'schema_version: "1.0"\nid: {identity}\ntitle: {identity}\nintent: Require security review.\nenforcement: required\n'
        )
    # Also collide with the raw ID: persisting it as a sentinel would activate
    # COMPANY-SEC under the guise of TEAM-SEC instead of rejecting ambiguity.
    (packs[0] / "directives/TEAM-SEC.directive.yaml").write_text(
        'schema_version: "1.0"\nid: COMPANY-SEC\ntitle: Company security\nintent: Require company review.\nenforcement: required\n'
    )
    paradigm = sorted(built_in_dir(ArtifactKind.PARADIGM).glob("*.paradigm.yaml"))[0].name.removesuffix(".paradigm.yaml")
    tactic = sorted(built_in_dir(ArtifactKind.TACTIC).glob("*.tactic.yaml"))[0].name.removesuffix(".tactic.yaml")
    if required:
        (packs[1] / "org-charter.yaml").write_text(
            f"org_name: Team\nrequired_directives: [TEAM-SEC, DIRECTIVE_001]\nrequired_tactics: [{tactic}]\nrequired_paradigms: [{paradigm}]\n"
        )
    yaml = YAML()
    config = {
        "charter_packs": {"org": {"packs": [{"name": pack.name, "local_path": str(pack)} for pack in packs]}},
        "activated_directives": [],
        "activated_tactics": [],
        "activated_paradigms": [],
    }
    with (tmp_path / ".kittify/config.yaml").open("w") as stream:
        yaml.dump(config, stream)
    monkeypatch.setenv("SPECIFY_REPO_ROOT", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    args = ["interview", "--mission-type", "software-dev", "--profile", "minimal", "--defaults", "--json"]
    if not required:
        args += ["--selected-directives", "TEAM-SEC,DIRECTIVE_001", "--selected-paradigms", paradigm]
    config_before = (tmp_path / ".kittify/config.yaml").read_bytes()
    result = CliRunner().invoke(app, args)
    assert result.exit_code == 1, result.output
    payload = json.loads(result.stdout)
    assert payload["result"] == "error"
    assert payload["success"] is False
    error = " ".join(payload["error"].split())
    assert "Cannot store directive 'TEAM-SEC'" in error
    assert "used by files in more than one layer that declare different IDs" in error
    assert "team/directives/security.directive.yaml declares 'TEAM-SEC'" in error
    assert "company/directives/security.directive.yaml declares 'COMPANY-SEC'" in error
    if required:
        # The org-required pre-fill refuses before the answers are saved.
        assert "The interview answers were saved" not in error
    else:
        # Selection-driven: the answers are saved, nothing is activated.
        assert "The interview answers were saved; no activation list was written." in error
    # The refusal activated nothing: not the id, and not the other layer's id under its guise.
    assert (tmp_path / ".kittify/config.yaml").read_bytes() == config_before
    delivered = build_active_charter_service(tmp_path).directives
    assert "TEAM-SEC" not in delivered
    assert "COMPANY-SEC" not in delivered
    # The generate leg of the same fixture.
    charter_yaml = tmp_path / ".kittify/charter/charter.yaml"
    if required:
        # No answers exist (the pre-fill refused first), so generate runs without an interview and
        # refuses the same collision: nothing is stored and no charter.yaml is written.
        generated = CliRunner().invoke(app, ["generate", "--no-from-interview", "--mission-type", "software-dev", "--json"])
        assert generated.exit_code == 1, generated.output
        assert "Cannot store directive 'TEAM-SEC'" in " ".join(generated.output.split())
        assert (tmp_path / ".kittify/config.yaml").read_bytes() == config_before
        assert not charter_yaml.exists()
    else:
        # The refused interview kept its answers, so generate can read them and succeeds.
        generated = CliRunner().invoke(app, ["generate", "--from-interview", "--json"])
        assert generated.exit_code == 0, generated.output
        generated_payload = json.loads(generated.stdout)
        assert charter_yaml.exists()
        # Neither colliding id is selected or delivered by generate either.
        assert "TEAM-SEC" not in generated_payload["selected_directives"]
        assert "COMPANY-SEC" not in generated_payload["selected_directives"]
        # Characterization of today's behavior, not an endorsement: after the refused interview
        # generate reports NO selections at all, dropping even the resolvable DIRECTIVE_001 and the
        # paradigm that the interview saved. Re-pin if that silent drop is ever fixed.
        assert generated_payload["selected_directives"] == []
        assert generated_payload["selected_paradigms"] == []
        # generate records its own charter.yaml tracking in config.yaml, so compare the activation
        # lists (still the empty seeds), not the raw bytes.
        saved = yaml.load((tmp_path / ".kittify/config.yaml").read_text())
        assert saved["activated_directives"] == []
        assert saved["activated_paradigms"] == []
        delivered_after = build_active_charter_service(tmp_path).directives
        assert "TEAM-SEC" not in delivered_after
        assert "COMPANY-SEC" not in delivered_after


def test_generate_rejects_ambiguous_required_directive_without_interview(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    directory = tmp_path / ".kittify/charter-packs/directive"
    directory.mkdir(parents=True)
    (directory / "025-boy-scout-rule.directive.yaml").write_text(
        'schema_version: "1.0"\nid: REQUIRED-POLICY\ntitle: Required\nintent: Require review.\nenforcement: required\n'
    )
    org = tmp_path / "org"
    org.mkdir()
    (org / "org-charter.yaml").write_text("org_name: Org\nrequired_directives: [REQUIRED-POLICY]\n")
    config = tmp_path / ".kittify/config.yaml"
    config.write_text(f"charter_packs:\n  org:\n    packs:\n      - name: org\n        local_path: '{org}'\nactivated_directives: []\n")
    before = config.read_bytes()
    monkeypatch.setenv("SPECIFY_REPO_ROOT", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    result = CliRunner().invoke(app, ["generate", "--no-from-interview", "--mission-type", "software-dev", "--json"])
    assert result.exit_code != 0, result.output
    assert "REQUIRED-POLICY" in result.output
    assert config.read_bytes() == before
    assert not (tmp_path / ".kittify/charter/charter.yaml").exists()
