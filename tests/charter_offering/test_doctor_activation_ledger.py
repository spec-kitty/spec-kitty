"""``spec-kitty doctor charter-packs`` reports activation drift (FR-005, FR-023, data-model.md §9; WP09 T053).

One test per finding code, through ``doctor charter-packs --json``. Findings
live under ``org_drg["activation_ledger"] = {"errors": [...], "warnings": [...]}``,
each ``{code, file, key, ids, message}``. An error turns the report unhealthy
(exit 1); a warning alone does not.

One mode (operator ruling ``mission_pivot_option_b``): an unmigrated project
reads its legacy allow keys, so ``ACTIVATION_UNMIGRATED`` is a warning only and
the report stays healthy. ``LEGACY_KEYS_PRESENT`` (keys beside a ledger) is
computed from the resolver's data, never through a raising read (M2).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from kernel.activation_ledger_store import ACTIVATION_LEDGER, activation_ledger_path
from specify_cli.cli.commands.doctor import app as doctor_app
from tests._factories.activation_ledger import seed_activation_ledger

pytestmark = [pytest.mark.fast]

_RUNNER = CliRunner()
_REQUIRED_STEM = "001-architectural-integrity-standard"
_OTHER = "003-decision-documentation-requirement"
_THIRD = "010-specification-fidelity-requirement"


def _project(root: Path, *, org_required: str | None = None, config_extra: str = "") -> Path:
    """A bare project; with *org_required*, one org pack ``acme`` whose org-charter.yaml body it is."""
    lines = ["agents:", "  available:", "    - claude"]
    if org_required is not None:
        pack = root / "org-packs" / "acme"
        pack.mkdir(parents=True)
        (pack / "org-charter.yaml").write_text(f"schema_version: 1\n{org_required}", encoding="utf-8")
        lines += ["charter_packs:", "  org:", "    packs:", "      - name: acme", "        local_path: org-packs/acme"]
    (root / ".kittify" / "charter").mkdir(parents=True)
    (root / ".kittify" / "config.yaml").write_text("\n".join(lines) + "\n" + config_extra, encoding="utf-8")
    return root


def _doctor(root: Path) -> tuple[int, dict[str, Any]]:
    with patch("specify_cli.cli.commands.doctor.locate_project_root", return_value=root):
        result = _RUNNER.invoke(doctor_app, ["charter-packs", "--json"])
    return result.exit_code, json.loads(result.stdout)


def _findings(payload: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    block = payload["org_drg"]["activation_ledger"]
    assert set(block) == {"errors", "warnings"}
    for finding in block["errors"] + block["warnings"]:
        assert set(finding) == {"code", "file", "key", "ids", "message"}, finding
    return block


def _codes(findings: list[dict[str, Any]]) -> list[str]:
    return [finding["code"] for finding in findings]


def _flagged(findings: list[dict[str, Any]], code: str) -> set[str]:
    """Every id any *code* finding names (negative controls: what must NOT be flagged)."""
    return {item for finding in findings if finding["code"] == code for item in finding["ids"]}


def _one(findings: list[dict[str, Any]], code: str) -> dict[str, Any]:
    matching = [finding for finding in findings if finding["code"] == code]
    assert len(matching) == 1, findings
    return matching[0]


# --------------------------------------------------------------------------- #
# Clean baseline
# --------------------------------------------------------------------------- #


def test_a_clean_ledger_reports_nothing_and_stays_healthy(tmp_path: Path) -> None:
    root = _project(tmp_path)
    seed_activation_ledger(root, mission_type_activations=["software-dev"])

    code, payload = _doctor(root)

    assert _findings(payload) == {"errors": [], "warnings": []}
    assert code == 0, payload


# --------------------------------------------------------------------------- #
# Errors
# --------------------------------------------------------------------------- #


def test_malformed_ledger_is_an_activation_store_error(tmp_path: Path) -> None:
    root = _project(tmp_path)
    activation_ledger_path(root).write_text("activated_directives: [\n", encoding="utf-8")

    code, payload = _doctor(root)

    finding = _one(_findings(payload)["errors"], "ACTIVATION_STORE_ERROR")
    assert ACTIVATION_LEDGER.as_posix() in finding["message"]
    assert finding["message"] in payload["org_drg"]["errors"]
    assert code == 1


def test_unreadable_required_floor_is_an_activation_store_error(tmp_path: Path) -> None:
    root = _project(tmp_path, org_required="required_directives: DIRECTIVE_001\n")
    seed_activation_ledger(root, mission_type_activations=["software-dev"])

    code, payload = _doctor(root)

    finding = _one(_findings(payload)["errors"], "ACTIVATION_STORE_ERROR")
    assert "required_directives" in finding["message"]
    assert code == 1


def test_legacy_keys_beside_a_ledger_are_an_error_and_the_ledger_wins(tmp_path: Path) -> None:
    root = _project(tmp_path, config_extra=f"activated_directives:\n  - {_OTHER}\n")
    seed_activation_ledger(root, activated_directives=[_REQUIRED_STEM])

    code, payload = _doctor(root)

    finding = _one(_findings(payload)["errors"], "LEGACY_KEYS_PRESENT")
    assert finding["key"] == "activated_directives"
    assert finding["file"].endswith(".kittify/config.yaml")
    assert "activation ledger (activation.yaml) wins" in finding["message"]
    assert code == 1


def test_a_legacy_deny_key_is_an_error_naming_the_hand_removal(tmp_path: Path) -> None:
    root = _project(tmp_path, config_extra=f"deactivated_directives:\n  - {_OTHER}\n")

    code, payload = _doctor(root)

    findings = _findings(payload)
    finding = _one(findings["errors"], "LEGACY_DENY_KEY")
    assert finding["key"] == "deactivated_directives"
    assert finding["ids"] == [_OTHER]
    assert "by hand" in finding["message"] and "migrate activation-ledger" in finding["message"]
    assert code == 1


# --------------------------------------------------------------------------- #
# Warnings
# --------------------------------------------------------------------------- #


def test_an_unmigrated_project_is_a_warning_only_and_healthy(tmp_path: Path) -> None:
    root = _project(tmp_path, config_extra=f"activated_directives:\n  - {_OTHER}\n")

    code, payload = _doctor(root)

    findings = _findings(payload)
    finding = _one(findings["warnings"], "ACTIVATION_UNMIGRATED")
    assert finding["key"] == "activated_directives"
    assert "spec-kitty upgrade" in finding["message"] and "spec-kitty migrate activation-ledger" in finding["message"]
    assert findings["errors"] == []
    assert code == 0, payload


def test_required_id_omitted_by_an_explicit_allow_list_is_a_warning(tmp_path: Path) -> None:
    root = _project(tmp_path, org_required="required_directives: [DIRECTIVE_001]\n")
    seed_activation_ledger(root, activated_directives=[_OTHER])

    _code, payload = _doctor(root)

    findings = _findings(payload)
    finding = _one(findings["warnings"], "REQUIRED_OMITTED_BY_ALLOW_LIST")
    assert finding["key"] == "activated_directives"
    assert finding["ids"] == [_REQUIRED_STEM]
    assert "'acme'" in finding["message"]
    assert findings["errors"] == []


@pytest.mark.parametrize("ledger", [{"mission_type_activations": ["software-dev"]}, {"activated_directives": ["DIRECTIVE_001", _OTHER]}])
def test_required_id_in_force_gives_no_omission_warning(tmp_path: Path, ledger: dict[str, list[str]]) -> None:
    """Positive control: an absent allow list, or one naming the id in another spelling, omits nothing."""
    root = _project(tmp_path, org_required="required_directives: [DIRECTIVE_001]\n")
    seed_activation_ledger(root, **ledger)

    _code, payload = _doctor(root)

    assert "REQUIRED_OMITTED_BY_ALLOW_LIST" not in _codes(_findings(payload)["warnings"])


def test_deny_of_an_unknown_id_is_a_warning_and_healthy(tmp_path: Path) -> None:
    root = _project(tmp_path)
    seed_activation_ledger(root, deactivated_directives=["no-such-directive", _OTHER])

    code, payload = _doctor(root)

    findings = _findings(payload)
    finding = _one(findings["warnings"], "DENY_UNKNOWN_ID")
    assert finding["key"] == "deactivated_directives" and finding["ids"] == ["no-such-directive"]
    # Negative control, same fixture: a known id's exclusion is not stale.
    assert _OTHER not in _flagged(findings["warnings"], "DENY_UNKNOWN_ID")
    assert "by hand" in finding["message"]
    assert findings["errors"] == []
    assert code == 0, payload


def test_deny_of_a_required_id_is_a_warning_naming_the_pack(tmp_path: Path) -> None:
    root = _project(tmp_path, org_required="required_directives: [DIRECTIVE_001]\n")
    seed_activation_ledger(root, deactivated_directives=[_REQUIRED_STEM, _OTHER])

    _code, payload = _doctor(root)

    findings = _findings(payload)
    finding = _one(findings["warnings"], "DENY_REQUIRED_ID")
    assert finding["ids"] == [_REQUIRED_STEM]
    # Negative control, same fixture and floor: a non-required id's exclusion is not reported.
    assert _flagged(findings["warnings"], "DENY_REQUIRED_ID") == {_REQUIRED_STEM}
    assert _OTHER not in _flagged(findings["warnings"], "DENY_UNKNOWN_ID")
    assert "'acme'" in finding["message"]
    assert findings["errors"] == []


def test_a_selected_id_that_is_denied_is_a_warning_and_healthy(tmp_path: Path) -> None:
    root = _project(tmp_path)
    answers = root / ".kittify" / "charter" / "interview" / "answers.yaml"
    answers.parent.mkdir(parents=True)
    answers.write_text("mission: software-dev\nprofile: minimal\nanswers: {}\nselected_directives:\n  - DIRECTIVE_003\n", encoding="utf-8")
    seed_activation_ledger(root, deactivated_directives=[_OTHER, _THIRD])

    code, payload = _doctor(root)

    findings = _findings(payload)
    finding = _one(findings["warnings"], "DENY_SELECTED_ID")
    # Two ids denied, one selected: only the selected one is reported.
    assert finding["key"] == "deactivated_directives" and finding["ids"] == [_OTHER]
    assert _flagged(findings["warnings"], "DENY_SELECTED_ID") == {_OTHER}
    assert "answers.yaml" in finding["file"]
    assert findings["errors"] == []
    assert code == 0, payload


def test_an_unknown_deny_key_is_a_warning_and_healthy(tmp_path: Path) -> None:
    root = _project(tmp_path)
    activation_ledger_path(root).write_text("deactivated_widgets:\n- gizmo\n", encoding="utf-8")

    code, payload = _doctor(root)

    findings = _findings(payload)
    finding = _one(findings["warnings"], "UNKNOWN_DENY_KEY")
    assert finding["key"] == "deactivated_widgets" and finding["ids"] == ["gizmo"]
    assert findings["errors"] == []
    assert code == 0, payload


def test_human_output_renders_errors_and_warnings(tmp_path: Path) -> None:
    root = _project(tmp_path, config_extra=f"activated_tactics: []\ndeactivated_directives:\n  - {_OTHER}\n")

    with patch("specify_cli.cli.commands.doctor.locate_project_root", return_value=root):
        result = _RUNNER.invoke(doctor_app, ["charter-packs"])

    assert result.exit_code == 1
    assert "LEGACY_DENY_KEY" in result.output
    assert "ACTIVATION_UNMIGRATED" in result.output


# --------------------------------------------------------------------------- #
# Seam helpers, mode-independent (every branch of ledger_findings' readers)
# --------------------------------------------------------------------------- #


def test_legacy_keys_are_probed_on_config_and_the_pointed_charter_yaml(tmp_path: Path) -> None:
    """The probe branch (a LEGACY answer without ``unmigrated_keys``) reads both legacy surfaces."""
    from charter.activation.activation_ledger import _legacy_keys_by_file
    from kernel.activation_ledger_store import ActivationSource, ResolvedActivationSource

    root = _project(tmp_path, config_extra="charter: .kittify/charter/charter.yaml\nactivated_kinds: [directives]\n")
    pointer = root / ".kittify" / "charter" / "charter.yaml"
    pointer.write_text("schema_version: '2.0.0'\nactivated_tactics: []\ndeactivated_directives: [x]\n", encoding="utf-8")
    resolved = ResolvedActivationSource(ActivationSource.LEGACY, pointer, True)

    found = _legacy_keys_by_file(root, resolved)

    assert found == ((root / ".kittify" / "config.yaml", ("activated_kinds",)), (pointer, ("activated_tactics", "deactivated_directives")))


def test_required_omission_names_packs_and_via() -> None:
    from charter.activation.activation_ledger import RequiredOmission
    from charter.activation.org_pack_discovery import RequiringPack
    from charter.offering.artifact_kinds import ArtifactKind

    omission = RequiredOmission(ArtifactKind.DIRECTIVE, _REQUIRED_STEM, (RequiringPack("base", "overlay"), RequiringPack("acme")))

    assert omission.pack_names == ("base", "acme")
    assert omission.describe_packs() == "'base' (via 'overlay'), 'acme'"


def test_findings_serialise_to_the_doctor_block() -> None:
    from charter.activation.activation_ledger import LedgerFinding, LedgerFindings

    finding = LedgerFinding("DENY_UNKNOWN_ID", "f", "deactivated_tactics", ("a",), "m")

    assert LedgerFindings(warnings=(finding,)).to_dict() == {
        "errors": [],
        "warnings": [{"code": "DENY_UNKNOWN_ID", "file": "f", "key": "deactivated_tactics", "ids": ["a"], "message": "m"}],
    }


def test_kernel_legacy_key_scan_is_the_resolver_scan(tmp_path: Path) -> None:
    """``legacy_keys_present`` exposes the resolver's own candidate scan (one rule, review cycle 1 F3)."""
    from kernel.activation_ledger_store import legacy_keys_present

    root = _project(tmp_path, config_extra="charter: .kittify/charter/charter.yaml\nactivated_kinds: [directives]\n")
    pointer = root / ".kittify" / "charter" / "charter.yaml"
    pointer.write_text("activated_tactics: []\nunrelated: 1\n", encoding="utf-8")

    found = legacy_keys_present(root, legacy_keys=frozenset({"activated_kinds", "activated_tactics"}), pointer_key="charter")

    assert found == ((root / ".kittify" / "config.yaml", ("activated_kinds",)), (pointer, ("activated_tactics",)))


def test_each_required_floor_is_read_once(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """``ledger_findings`` reads every org-requirable kind's floor exactly once (review cycle 1 F2)."""
    from charter.activation import org_pack_discovery
    from charter.activation.activation_ledger import ledger_findings

    root = _project(tmp_path, org_required="required_directives: [DIRECTIVE_001]\n")
    seed_activation_ledger(root, activated_directives=[_OTHER], deactivated_directives=[_REQUIRED_STEM])
    reads: list[str] = []
    real = org_pack_discovery.read_org_required_provenance

    def counting(repo_root: Path, kind: Any, *, strict: bool) -> Any:
        reads.append(kind.value)
        return real(repo_root, kind, strict=strict)

    monkeypatch.setattr(org_pack_discovery, "read_org_required_provenance", counting)

    findings = ledger_findings(root)

    assert {"REQUIRED_OMITTED_BY_ALLOW_LIST", "DENY_REQUIRED_ID"} <= {finding.code for finding in findings.warnings}
    assert len(reads) == len(set(reads)), reads
    assert "directive" in reads
