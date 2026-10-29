"""``charter status --json`` reports activation state in a local ``activation`` block (#6526, local slice).

The block is local to core (``schema_version: "1.0.0"``, snake_case; the
camelCase contract mapping is #6520, held) and is read only through
``charter.activation.api``. ``selected[<plural>]`` is ``null`` for an absent
allow list and a list otherwise; ``deactivated`` lists only present deny keys;
``required`` is the org-required floor with ``in_force`` decided by
``required_not_in_force``. An activation read error degrades the block to
``{"schema_version", "error": {"code", "message"}}`` while status still
succeeds. Text mode does not render the block (FR-011).
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from click.testing import Result
from typer.testing import CliRunner

import specify_cli.cli.commands.charter as charter_pkg
from specify_cli.cli.commands.charter import charter_app
from tests._factories.activation_ledger import legacy_seed, seed_activation_ledger

pytestmark = [pytest.mark.fast]

_RUNNER = CliRunner()
_SNAPSHOT_DIR = Path(__file__).parent / "snapshots" / "status_activation"
_SCHEMA_VERSION = "1.0.0"
_BLOCK_KEYS = {"schema_version", "source", "path", "exists", "selected", "deactivated", "mission_types", "activated_kinds", "required"}
#: Every charter-activatable kind's plural, in ``ArtifactKind`` order.
_PLURALS = [
    "directives",
    "tactics",
    "styleguides",
    "toolguides",
    "paradigms",
    "procedures",
    "agent_profiles",
    "mission_step_contracts",
    "glossary_packs",
    "anti_patterns",
    "skills",
]
_REQUIRED_STEM = "001-architectural-integrity-standard"
_OTHER = "003-decision-documentation-requirement"
_DENIED_TACTIC = "premortem-risk-identification"
_LEDGER_REL = ".kittify/charter/activation.yaml"


def _with_org_pack(root: Path) -> Path:
    """An org pack ``acme`` requiring ``DIRECTIVE_001`` (normalised to its stem)."""
    pack = root / "org-packs" / "acme"
    pack.mkdir(parents=True)
    (pack / "org-charter.yaml").write_text("schema_version: 1\nrequired_directives: [DIRECTIVE_001]\n", encoding="utf-8")
    (root / ".kittify").mkdir(exist_ok=True)
    (root / ".kittify" / "config.yaml").write_text("charter_packs:\n  org:\n    packs:\n      - name: acme\n        local_path: org-packs/acme\n", encoding="utf-8")
    return root


def _ledger_project(root: Path) -> Path:
    _with_org_pack(root)
    seed_activation_ledger(
        root,
        mission_type_activations=["software-dev"],
        activated_directives=[_OTHER],
        deactivated_tactics=[_DENIED_TACTIC],
    )
    return root


def _status(root: Path, *args: str) -> Result:
    """``charter status`` against *root* with the collectors unrelated to activation stubbed."""
    with (
        patch.object(charter_pkg, "find_repo_root", return_value=root),
        patch.object(charter_pkg, "_collect_charter_sync_status", return_value={"available": False, "error": "no charter (test stub)"}),
        patch.object(charter_pkg, "_collect_synthesis_status", return_value=_SYNTHESIS_STUB),
        patch("specify_cli.cli.commands.charter.status._collect_org_layer_status", return_value={"packs": [], "has_built_in": True}),
        patch("specify_cli.cli.commands.charter.status._collect_governance_reference_status", return_value={"available": True, "references": [], "warnings": []}),
        patch("specify_cli.charter_runtime.freshness.compute_freshness") as compute_freshness,
    ):
        compute_freshness.return_value.to_dict.return_value = _FRESHNESS_STUB
        return _RUNNER.invoke(charter_app, ["status", *args], catch_exceptions=False)


_LAYER_STUB = {"state": "missing", "last_change": None, "detail": None, "remediation": None}
_FRESHNESS_STUB = {"charter_source": _LAYER_STUB, "synced_bundle": _LAYER_STUB, "synthesized_drg": _LAYER_STUB}
_SYNTHESIS_STUB: dict[str, Any] = {
    "generation_state": "not_started",
    "generated_inputs": {"path": ".kittify/charter/generated", "counts": {"directive": 0, "tactic": 0, "styleguide": 0}},
    "manifest": {
        "path": ".kittify/charter/synthesis-manifest.yaml",
        "exists": False,
        "state": "missing",
        "artifact_count": 0,
        "live_artifact_count": 0,
        "run_id": None,
        "adapter_id": None,
        "adapter_version": None,
        "missing_provenance_paths": [],
        "error": None,
    },
    "evidence": {"code": None, "configured_url_count": 0, "corpus_snapshot_id": None, "warnings": []},
    "provenance": {"parsed_count": 0, "manifest_artifact_count": 0, "missing_for_manifest_count": 0, "corpus_snapshot_ids": [], "warnings": [], "entries": []},
}


def _block(root: Path) -> dict[str, Any]:
    result = _status(root, "--json")
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["result"] == "success", payload
    block: dict[str, Any] = payload["activation"]
    return block


def test_ledger_block_has_the_local_shape(tmp_path: Path) -> None:
    block = _block(_ledger_project(tmp_path))

    assert set(block) == _BLOCK_KEYS
    assert block["schema_version"] == _SCHEMA_VERSION
    assert block["source"] == "ledger"
    assert block["path"] == _LEDGER_REL
    assert block["exists"] is True
    assert list(block["selected"]) == _PLURALS
    assert block["selected"]["directives"] == [_OTHER]
    assert all(block["selected"][plural] is None for plural in _PLURALS if plural != "directives")
    assert block["deactivated"] == {"tactics": [_DENIED_TACTIC]}
    assert block["mission_types"] == ["software-dev"]
    assert block["activated_kinds"] is None


def test_required_entry_is_out_of_force_when_an_allow_list_omits_it(tmp_path: Path) -> None:
    block = _block(_ledger_project(tmp_path))

    assert block["required"] == [{"kind": "directive", "id": _REQUIRED_STEM, "in_force": False, "packs": ["acme"]}]


@pytest.mark.parametrize("ledger", [{}, {"activated_directives": ["DIRECTIVE_001", _OTHER]}], ids=["absent-allow-list", "allow-list-names-it"])
def test_required_entry_is_in_force_otherwise(tmp_path: Path, ledger: dict[str, list[str]]) -> None:
    _with_org_pack(tmp_path)
    seed_activation_ledger(tmp_path, mission_type_activations=["software-dev"], **ledger)

    block = _block(tmp_path)

    assert block["required"] == [{"kind": "directive", "id": _REQUIRED_STEM, "in_force": True, "packs": ["acme"]}]


def test_absent_ledger_reports_no_allow_lists(tmp_path: Path) -> None:
    (tmp_path / ".kittify").mkdir()

    block = _block(tmp_path)

    assert block["source"] == "ledger"
    assert block["path"] == _LEDGER_REL
    assert block["exists"] is False
    assert block["selected"] == dict.fromkeys(_PLURALS)
    assert block["deactivated"] == {}
    assert block["mission_types"] is None
    assert block["activated_kinds"] is None
    assert block["required"] == []


def test_unmigrated_project_reports_the_legacy_source(tmp_path: Path) -> None:
    (tmp_path / ".kittify").mkdir()
    legacy_seed(tmp_path, surface="config_yaml", mission_type_activations=["software-dev"], activated_directives=[_OTHER])

    block = _block(tmp_path)

    assert block["source"] == "legacy"
    assert block["path"] == ".kittify/config.yaml"
    assert block["selected"]["directives"] == [_OTHER]
    assert block["mission_types"] == ["software-dev"]
    assert block["deactivated"] == {}


def test_unreadable_ledger_degrades_the_block_not_the_command(tmp_path: Path) -> None:
    ledger = tmp_path / _LEDGER_REL
    ledger.parent.mkdir(parents=True)
    ledger.write_text("not_an_activation_key: [x]\n", encoding="utf-8")

    block = _block(tmp_path)

    assert set(block) == {"schema_version", "error"}
    assert block["schema_version"] == _SCHEMA_VERSION
    assert set(block["error"]) == {"code", "message"}
    assert block["error"]["code"] == "ACTIVE_CHARTER_CONFIG_INVALID"
    assert "not_an_activation_key" in block["error"]["message"]


def test_block_uses_snake_case_local_fields_only(tmp_path: Path) -> None:
    """C-001: no camelCase contract fields and no contract ``revision``."""
    block = _block(_ledger_project(tmp_path))

    keys = set(block) | {key for entry in block["required"] for key in entry}
    assert all(re.fullmatch(r"[a-z_]+", key) for key in keys), keys
    assert "revision" not in block


def test_ledger_block_matches_snapshot(tmp_path: Path) -> None:
    block = _block(_ledger_project(tmp_path))

    expected = json.loads((_SNAPSHOT_DIR / "ledger.json").read_text(encoding="utf-8"))
    assert block == expected


def test_text_output_does_not_render_the_block(tmp_path: Path) -> None:
    """FR-011: the text view is unchanged; it equals the golden captured on the base (pre-#6526 code)."""
    result = _status(_ledger_project(tmp_path))

    assert result.exit_code == 0, result.output
    assert "activation" not in result.output.lower()
    golden = (_SNAPSHOT_DIR / "ledger_text.txt").read_text(encoding="utf-8")
    # Whitespace-normalised: rich wraps at the terminal width the runner reports.
    assert result.output.split() == golden.split()


# --------------------------------------------------------------------------- #
# The required floor covers every org-requirable kind; a malformed org charter
# is reported, not read as "no floor"; an unreadable ledger degrades the block.
# --------------------------------------------------------------------------- #


def _with_org_charter(root: Path, org_charter: str) -> Path:
    """The org pack ``acme`` with *org_charter* as its ``org-charter.yaml`` text."""
    _with_org_pack(root)
    (root / "org-packs" / "acme" / "org-charter.yaml").write_text(org_charter, encoding="utf-8")
    return root


def test_required_lists_every_org_requirable_kind(tmp_path: Path) -> None:
    """An org-required asset (requirable, not activatable) is reported and always in force."""
    _with_org_charter(
        tmp_path,
        f"schema_version: 1\nrequired_tactics: [{_DENIED_TACTIC}]\nrequired_assets: [common-docs-structural-lint]\nrequired_glossary_packs: [spec-kitty-core]\n",
    )
    seed_activation_ledger(tmp_path, mission_type_activations=["software-dev"], activated_tactics=[], activated_glossary_packs=["spec-kitty-core"])

    block = _block(tmp_path)

    assert "required_error" not in block
    assert block["required"] == [
        # The declared asset id is normalised to its activation stem.
        {"kind": "asset", "id": "docs_structural_lint", "in_force": True, "packs": ["acme"]},
        {"kind": "glossary-pack", "id": "spec-kitty-core", "in_force": True, "packs": ["acme"]},
        {"kind": "tactic", "id": _DENIED_TACTIC, "in_force": False, "packs": ["acme"]},
    ]


@pytest.mark.parametrize(
    "org_charter",
    [
        "schema_version: 1\nrequired_directives: [DIRECTIVE_001]\nrequired_tactics: 5\n",
        "schema_version: 1\nrequired_tactics: [unclosed\n",
        "- required_tactics\n- 5\n",
    ],
    ids=["not-a-list", "unparseable", "list-root"],
)
def test_a_malformed_org_charter_is_reported_beside_the_lenient_floor(tmp_path: Path, org_charter: str) -> None:
    _with_org_charter(tmp_path, org_charter)
    seed_activation_ledger(tmp_path, mission_type_activations=["software-dev"])

    block = _block(tmp_path)

    error = block["required_error"]
    assert set(error) == {"code", "message"}
    assert error["code"] == "ACTIVE_CHARTER_CONFIG_INVALID"
    assert "acme" in error["message"] or "org-charter.yaml" in error["message"], error["message"]
    # The lenient read is kept: what it could read is still reported.
    expected = [{"kind": "directive", "id": _REQUIRED_STEM, "in_force": True, "packs": ["acme"]}] if "DIRECTIVE_001" in org_charter else []
    assert block["required"] == expected
    assert block["source"] == "ledger"


def test_an_unreadable_ledger_file_degrades_the_block(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """An OSError reading activation.yaml is this block's error, not an INTERNAL_ERROR of status."""
    import os

    seed_activation_ledger(tmp_path, mission_type_activations=["software-dev"])
    ledger = tmp_path / _LEDGER_REL
    ledger.chmod(0)
    try:
        readable = os.access(ledger, os.R_OK)
        if readable:
            # Running as root: the mode bits do not stop the read, so fail the
            # lowest real read (the kernel's YAML load of the ledger file).
            def unreadable(path: Path) -> object:
                raise PermissionError(13, "Permission denied", str(path))

            monkeypatch.setattr("kernel.activation_ledger_store._safe_load_mapping", unreadable)

        block = _block(tmp_path)
    finally:
        ledger.chmod(0o644)

    assert set(block) == {"schema_version", "error"}
    assert block["error"]["code"] == "ACTIVATION_STATE_UNREADABLE"
    assert "Permission denied" in block["error"]["message"]
