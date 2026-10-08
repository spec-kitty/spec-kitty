"""Public CLI contract: authored org fragments use the runtime loader's schema."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from typer.testing import CliRunner

from specify_cli.cli.commands.doctrine import app

pytestmark = [pytest.mark.unit, pytest.mark.fast]


def test_pack_cli_rejects_graph_node_in_org_fragment(tmp_path: Path) -> None:
    fragment = tmp_path / "drg" / "fragment.yaml"
    fragment.parent.mkdir()
    fragment.write_text(
        "nodes:\n  - urn: directive:ACME-001-FOO\n    kind: directive\nedges: []\n",
        encoding="utf-8",
    )
    result = CliRunner().invoke(app, ["pack", "validate", str(tmp_path), "--json"])
    assert result.exit_code == 1, result.output
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert len(payload["errors"]) == 1
    finding = payload["errors"][0]
    assert finding["category"] == "schema_invalid"
    assert finding["artifact_type"] == "drg"
    assert finding["file"] == str(fragment)
    # Coarse message assertions only: "unknown kind" is this repo's own
    # binding wording, but pydantic loc substrings like ``nodes.0.id`` drift
    # across pydantic versions and must not be pinned (#4200 nit c).
    assert "unknown kind 'directive'" in finding["message"]


@pytest.mark.parametrize("command", ["pack", "org"])
def test_cli_accepts_minimal_authored_fragment(tmp_path: Path, command: str) -> None:
    fragment = tmp_path / "drg" / "fragment.yaml"
    fragment.parent.mkdir()
    fragment.write_text("nodes:\n  - id: ACME-001-FOO\n    kind: directives\nedges: []\n", encoding="utf-8")
    result = CliRunner().invoke(app, [command, "validate", str(tmp_path)])
    assert result.exit_code == 0, result.output
    from charter.offering.drg.org_pack_loader import load_org_pack

    loaded = load_org_pack(pack_name="test", pack_root=tmp_path, layer_index=1)
    assert [(node.id, node.kind) for node in loaded.nodes] == [("ACME-001-FOO", "directives")]


@pytest.mark.parametrize(
    ("content", "category", "diagnostic"),
    [
        ("nodes: [", "parse_error", "YAML parse error"),
        ("a scalar", "schema_invalid", "mapping"),
        ("[a, list]", "schema_invalid", "mapping"),
        ("[]", "schema_invalid", "mapping"),
        ("false", "schema_invalid", "mapping"),
        ("nodes: null", "schema_invalid", "nodes"),
        ("surprise: true", "schema_invalid", "surprise"),
        ("nodes: [{id: foo, kind: directives, surprise: true}]", "schema_invalid", "surprise"),
        ("nodes: [{id: foo, kind: unknown}]", "schema_invalid", "unknown kind"),
        ("edges: 3", "schema_invalid", "edges"),
        ("edges: {}", "schema_invalid", "edges"),
        ("edges: false", "schema_invalid", "edges"),
        ("edges: ''", "schema_invalid", "edges"),
        ("edges: [{source: foo, target: bar, relation: requires, surprise: true}]", "schema_invalid", "surprise"),
        ("edges: [{source: foo, target: bar, relation: []}]", "schema_invalid", "relation"),
    ],
)
def test_malformed_fragments_have_actionable_findings(tmp_path: Path, content: str, category: str, diagnostic: str) -> None:
    from charter.offering.drg.org_pack_loader import OrgPackParseError, OrgPackSchemaError, load_org_pack
    from charter.offering.packs.pack_validator import validate_pack

    fragment = tmp_path / "drg" / "fragment.yaml"
    fragment.parent.mkdir()
    fragment.write_text(content, encoding="utf-8")
    expected_error = OrgPackParseError if category == "parse_error" else OrgPackSchemaError
    with pytest.raises(expected_error, match=diagnostic):
        load_org_pack(pack_name="test", pack_root=tmp_path, layer_index=1)
    result = validate_pack(tmp_path, check_drg_root=False)
    assert not result.ok
    assert len(result.errors) == 1
    finding = result.errors[0]
    assert finding.category == category
    assert finding.file == str(fragment)
    assert diagnostic in finding.message
    for command in ("pack", "org"):
        cli = CliRunner().invoke(app, [command, "validate", str(tmp_path)])
        assert cli.exit_code == 1, cli.output
        assert "1 error" in cli.output
        assert diagnostic in cli.output


@pytest.mark.parametrize(
    "content", ["", "{}", "edges: null", "nodes: []\nedges: []", "pack_name: []\nsource_kind: invalid\nsource_ref: null\nlayer_index: invalid"]
)
def test_runtime_normalization_matches_pack_validation(tmp_path: Path, content: str) -> None:
    from charter.offering.drg.org_pack_loader import load_org_pack
    from charter.offering.packs.pack_validator import validate_pack

    fragment = tmp_path / "drg" / "fragment.yaml"
    fragment.parent.mkdir()
    fragment.write_text(content, encoding="utf-8")
    loaded = load_org_pack(pack_name="authoritative", pack_root=tmp_path, layer_index=2)
    assert loaded.pack_name == "authoritative"
    assert loaded.layer_index == 2
    assert loaded.source_ref == str(tmp_path)
    assert loaded.source_kind == "local_path"
    assert loaded.nodes == []
    assert loaded.edges == []
    assert validate_pack(tmp_path).ok
    for command in ("pack", "org"):
        cli = CliRunner().invoke(app, [command, "validate", str(tmp_path)])
        assert cli.exit_code == 0, cli.output


def test_fragment_is_optional(tmp_path: Path) -> None:
    from charter.offering.packs.pack_validator import validate_pack

    assert validate_pack(tmp_path).ok


@pytest.mark.parametrize("selection", ["3", "[ACME-001-FOO]"])
def test_governance_projection_validation(tmp_path: Path, selection: str) -> None:
    import yaml

    from charter.offering.drg.org_pack_loader import OrgPackSchemaError, load_org_pack
    from charter.offering.packs.pack_validator import validate_pack

    fragment = tmp_path / "drg" / "fragment.yaml"
    fragment.parent.mkdir()
    fragment.write_text("nodes: []\nedges: []\n", encoding="utf-8")
    profile = tmp_path / "mission_types" / "example" / "governance-profile.yaml"
    profile.parent.mkdir(parents=True)
    profile.write_text(f"selected_directives: {selection}\n", encoding="utf-8")
    source = Path(__file__).resolve().parents[3] / "packs/built-in/directives/001-architectural-integrity-standard.directive.yaml"
    directive = yaml.safe_load(source.read_text(encoding="utf-8"))
    directive["id"] = "ACME_001_FOO"
    artifact = tmp_path / "directives" / "acme.directive.yaml"
    artifact.parent.mkdir()
    artifact.write_text(yaml.safe_dump(directive), encoding="utf-8")
    valid = selection.startswith("[")
    result = validate_pack(tmp_path)
    assert result.ok is valid
    if valid:
        loaded = load_org_pack(pack_name="test", pack_root=tmp_path, layer_index=1)
        assert [(node.id, node.kind) for node in loaded.nodes] == [("ACME_001_FOO", "directives")]
        assert len(loaded.edges) == 1
        edge = loaded.edges[0]
        assert (edge.source, edge.target, edge.relation) == ("mission_type:example", "directive:ACME_001_FOO", "scope")
        assert edge.reason is None
        assert edge.generated_reason == "declared via governance-profile.yaml selected_directives selection"
    else:
        assert len(result.errors) == 1
        assert result.errors[0].category == "schema_invalid"
        # The fault lives in the governance profile, not the fragment: the
        # finding names the real source file (#4200 defect 1).
        assert result.errors[0].file == str(profile)
        assert str(profile) in result.errors[0].message
        assert "selected_directives" in result.errors[0].message
        with pytest.raises(OrgPackSchemaError, match="selected_directives"):
            load_org_pack(pack_name="test", pack_root=tmp_path, layer_index=1)
    for command in ("pack", "org"):
        cli = CliRunner().invoke(app, [command, "validate", str(tmp_path)])
        assert cli.exit_code == (0 if valid else 1), cli.output
        # ``CliRunner`` swallows an uncaught crash into ``exception`` with
        # exit_code 1 and no "Traceback" in output, so the exit-code assert
        # alone cannot pin "no traceback": the only exception a clean exit
        # may carry is the ``SystemExit`` signal itself (pass-2 squad MINOR).
        assert cli.exception is None or isinstance(cli.exception, SystemExit), cli.exception
        assert "Traceback" not in cli.output
        if not valid:
            assert "selected_directives" in cli.output


# ---------------------------------------------------------------------------
# #4200: authority gap — governance-profile validation must not be gated on
# drg/fragment.yaml existing.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("selection", ["3", "[ACME-001-FOO]"])
def test_governance_validation_not_gated_on_fragment(tmp_path: Path, selection: str) -> None:
    """A governance-profile fault is a CLI finding even with NO fragment.

    The profile is read by ``load_org_pack`` the moment any fragment exists,
    so a pack that ships ``mission_types/*/governance-profile.yaml`` without
    ``drg/fragment.yaml`` previously passed CLI validation green while the
    same loader raised at runtime (#4200 defect 3).
    """
    from charter.offering.packs.pack_validator import validate_pack

    profile = tmp_path / "mission_types" / "example" / "governance-profile.yaml"
    profile.parent.mkdir(parents=True)
    profile.write_text(f"selected_directives: {selection}\n", encoding="utf-8")
    valid = selection.startswith("[")
    result = validate_pack(tmp_path, check_drg_root=False)
    assert result.ok is valid
    if not valid:
        assert len(result.errors) == 1
        finding = result.errors[0]
        assert finding.category == "schema_invalid"
        assert finding.file == str(profile)
        assert "selected_directives" in finding.message
    for command in ("pack", "org"):
        cli = CliRunner().invoke(app, [command, "validate", str(tmp_path)])
        assert cli.exit_code == (0 if valid else 1), cli.output
        # Same ``CliRunner``-swallows-crashes guard as above (pass-2 squad MINOR).
        assert cli.exception is None or isinstance(cli.exception, SystemExit), cli.exception
        assert "Traceback" not in cli.output


def test_non_utf8_governance_profile_is_skipped_not_a_traceback(tmp_path: Path) -> None:
    """A non-UTF-8 governance profile cannot crash ``validate`` with no fragment.

    ``UnicodeDecodeError`` subclasses ``ValueError``, not ``OSError``, so a
    ``governance-profile.yaml`` written in a non-UTF-8 encoding escaped the
    fragment-less branch's ``(OrgPackSchemaError, OSError)`` catch and crashed
    ``pack validate`` / ``org validate`` with an uncaught traceback — #4200
    defect 2's own failure mode reintroduced on the defect-3 branch (pass-2
    squad MAJOR). The profile's own loader now names the encoding fault
    alongside ``yaml.YAMLError`` and skips the profile, so the validator and
    the runtime loader agree on both the fragment-less and the
    fragment-present path — where the same fault previously surfaced as a
    ``schema_invalid`` finding misattributed to ``drg/fragment.yaml`` by the
    loader's broad backstop.
    """
    from charter.offering.drg.org_governance import collect_org_governance_scope_edges
    from charter.offering.packs.pack_validator import validate_pack

    profile = tmp_path / "mission_types" / "example" / "governance-profile.yaml"
    profile.parent.mkdir(parents=True)
    profile.write_bytes(b"mission_type: example\nselected_directives: [caf\xe9-d]\n")
    # Runtime seam: the collector skips the unreadable profile, never raises.
    assert collect_org_governance_scope_edges(tmp_path) == []
    result = validate_pack(tmp_path, check_drg_root=False)
    assert result.ok, result.errors
    # Fragment-present sibling: the same profile is skipped there too, so
    # the CLI verdict and the runtime loader cannot diverge.
    fragment = tmp_path / "drg" / "fragment.yaml"
    fragment.parent.mkdir()
    fragment.write_text("nodes: []\nedges: []\n", encoding="utf-8")
    assert validate_pack(tmp_path, check_drg_root=False).ok
    for command in ("pack", "org"):
        cli = CliRunner().invoke(app, [command, "validate", str(tmp_path)])
        assert cli.exit_code == 0, cli.output
        assert cli.exception is None or isinstance(cli.exception, SystemExit), cli.exception
        assert "Traceback" not in cli.output


# ---------------------------------------------------------------------------
# #4200: an unreadable fragment is an I/O finding, never a traceback and
# never a masked "YAML parse error".
# ---------------------------------------------------------------------------


def test_unreadable_fragment_is_a_finding_not_a_traceback(tmp_path: Path) -> None:
    """A directory where ``drg/fragment.yaml`` should be cannot be read.

    ``read_text`` on a directory raises ``OSError`` on every platform, so
    this exercises the unreadable-file channel without chmod (which is a
    no-op for root) — the exact fault that previously aborted the whole
    ``validate`` command with a traceback once it stopped being masked as a
    YAML parse error (#4200 defect 2).
    """
    from charter.offering.packs.pack_validator import validate_pack

    fragment = tmp_path / "drg" / "fragment.yaml"
    fragment.parent.mkdir()
    fragment.mkdir()
    result = validate_pack(tmp_path, check_drg_root=False)
    assert not result.ok
    assert len(result.errors) == 1
    finding = result.errors[0]
    assert finding.category == "unreadable_file"
    assert finding.file == str(fragment)
    for command in ("pack", "org"):
        cli = CliRunner().invoke(app, [command, "validate", str(tmp_path)])
        assert cli.exit_code == 1, cli.output
        # Same ``CliRunner``-swallows-crashes guard as above (pass-2 squad MINOR).
        assert cli.exception is None or isinstance(cli.exception, SystemExit), cli.exception
        assert "Traceback" not in cli.output


@pytest.mark.skipif(
    os.name != "posix" or os.geteuid() == 0,
    reason="chmod-based unreadability needs POSIX and a non-root user",
)
def test_permission_denied_fragment_is_a_finding(tmp_path: Path) -> None:
    """A permission-denied fragment surfaces as ``unreadable_file``, not a crash."""
    from charter.offering.packs.pack_validator import validate_pack

    fragment = tmp_path / "drg" / "fragment.yaml"
    fragment.parent.mkdir()
    fragment.write_text("nodes: []\nedges: []\n", encoding="utf-8")
    fragment.chmod(0)
    try:
        result = validate_pack(tmp_path, check_drg_root=False)
    finally:
        fragment.chmod(0o644)
    assert not result.ok
    assert len(result.errors) == 1
    finding = result.errors[0]
    assert finding.category == "unreadable_file"
    assert finding.file == str(fragment)


def test_missing_pack_fault_has_its_own_category(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """``OrgPackMissingError`` maps to ``org_pack_missing``, not ``parse_error``.

    A missing referenced artifact is not a parse failure (#4200 nit a). The
    loader only raises it mid-validation in a delete race, so the mapping is
    pinned by simulating the raise at the seam the validator calls.
    """
    from charter.offering.drg.org_pack_loader import OrgPackMissingError
    from charter.offering.packs import pack_validator
    from charter.offering.packs.pack_validator import validate_pack

    fragment = tmp_path / "drg" / "fragment.yaml"
    fragment.parent.mkdir()
    fragment.write_text("nodes: []\nedges: []\n", encoding="utf-8")

    def _vanished(pack_name: str, pack_root: Path, layer_index: int) -> None:
        raise OrgPackMissingError(pack_name, pack_root / "drg" / "fragment.yaml")

    monkeypatch.setattr(pack_validator, "load_org_pack", _vanished)
    result = validate_pack(tmp_path, check_drg_root=False)
    assert not result.ok
    assert len(result.errors) == 1
    finding = result.errors[0]
    assert finding.category == "org_pack_missing"
    assert finding.file == str(fragment)
