"""Analysis currency binds validated owned inputs and local read-only governance.

Provenance: the minimal freshness-root repair and paired controls were independently
reported by the memory-safety program (crucible-energy/spec-kitty#146). These
regressions use this repository's real owned-checkout fixture, minter and placement
seam; no ownership fact or current-analysis verdict is fabricated.
"""

from __future__ import annotations

import hashlib
import json

import typer
import shutil
from pathlib import Path

from typer.testing import CliRunner

import pytest

from mission_runtime import ActionContextError, OwnedCheckout
from specify_cli.analysis_report import check_analysis_report_current, write_analysis_report
from specify_cli.cli.commands.next_cmd import analysis_currency_for, next_step
from specify_cli.cli.commands.agent.mission import app as mission_app
from specify_cli.frontmatter import FrontmatterManager
from specify_cli.core.owned_mission import NEXT_OWNED_TOPOLOGIES, resolve_owned_mission
from tests.integration.conftest import OwnedCheckouts, _init_repo, _git

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_BODY = "---\nschema: analysis-findings/v1\nfindings: []\ncounts: {critical: 0, high: 0, medium: 0, low: 0, info: 0}\n---\n# Ready fixture\n"


@pytest.fixture
def currency_case(owned_checkouts: OwnedCheckouts) -> tuple[OwnedCheckouts, OwnedCheckout]:
    checkouts = owned_checkouts
    for root, value in [(checkouts.repository_root, "primary"), (checkouts.owned_root, "owned")]:
        charter = root / ".kittify/charter/charter.yaml"
        charter.parent.mkdir(parents=True, exist_ok=True)
        charter.write_text(f"authority: {value}\n", encoding="utf-8")
    fact = resolve_owned_mission(
        checkouts.repository_root,
        checkouts.owned_root,
        checkouts.mission_slug,
        allowed_topologies=NEXT_OWNED_TOPOLOGIES,
    )
    write_analysis_report(feature_dir=checkouts.mission_dir, repo_root=checkouts.owned_root, body=_BODY, charter_root=checkouts.owned_root)
    return checkouts, fact


def _currency(case: tuple[OwnedCheckouts, OwnedCheckout]):
    checkouts, fact = case
    return analysis_currency_for(checkouts.mission_slug, checkouts.repository_root, owned=fact)()


def test_unchanged_owned_report_is_current(currency_case):
    checkouts, _fact = currency_case
    assert check_analysis_report_current(checkouts.mission_dir, checkouts.owned_root, charter_root=checkouts.owned_root).ok
    assert _currency(currency_case).status == "current"


@pytest.mark.parametrize("name", ["spec.md", "plan.md", "tasks.md"])
def test_changed_material_reports_exact_stale_input(currency_case, name: str):
    checkouts, _fact = currency_case
    path = checkouts.mission_dir / name
    path.write_bytes(path.read_bytes() + b"\nChanged substantive contract.\n")
    verdict = _currency(currency_case)
    assert verdict.status == "stale"
    assert name in verdict.stale_inputs


def test_symlink_escape_remains_refused(currency_case):
    checkouts, _fact = currency_case
    outside = checkouts.repository_root / "outside.md"
    outside.write_text("Outside governing root\n", encoding="utf-8")
    spec = checkouts.mission_dir / "spec.md"
    spec.unlink()
    spec.symlink_to(outside)
    verdict = _currency(currency_case)
    assert verdict.status == "stale"
    assert any(reason.startswith("path_relativization_failed:") for reason in verdict.stale_inputs)


def test_owned_charter_authority_does_not_fall_back_to_repository_root(currency_case):
    checkouts, _fact = currency_case
    primary = checkouts.repository_root / ".kittify/charter/charter.yaml"
    owned_local = checkouts.owned_root / ".kittify/charter/charter.yaml"
    result = write_analysis_report(feature_dir=checkouts.mission_dir, repo_root=checkouts.owned_root, body=_BODY, charter_root=checkouts.owned_root)
    assert result.input_artifacts["charter"]["path"] == ".kittify/charter/charter.yaml"
    assert result.input_artifacts["charter"]["sha256"] == hashlib.sha256(owned_local.read_bytes()).hexdigest()  # noqa: TID251 -- report file-integrity freshness, not semantic charter identity
    primary.write_text("authority: changed-repository-root\n", encoding="utf-8")
    assert _currency(currency_case).status == "current"
    owned_local.write_text("authority: changed-owned-local\n", encoding="utf-8")
    verdict = _currency(currency_case)
    assert verdict.status == "stale"
    assert verdict.stale_inputs == ("charter",)


def test_unowned_currency_retains_primary_behavior(currency_case):
    checkouts, _fact = currency_case
    primary_dir = checkouts.repository_root / "kitty-specs" / checkouts.mission_slug
    shutil.copytree(checkouts.mission_dir, primary_dir)
    write_analysis_report(feature_dir=primary_dir, repo_root=checkouts.repository_root, body=_BODY)
    currency = analysis_currency_for(checkouts.mission_slug, checkouts.repository_root)
    assert currency().status == "current"
    path = primary_dir / "plan.md"
    path.write_bytes(path.read_bytes() + b"\nChanged primary plan.\n")
    assert currency().stale_inputs == ("plan.md",)
    write_analysis_report(feature_dir=primary_dir, repo_root=checkouts.repository_root, body=_BODY)
    charter = checkouts.repository_root / ".kittify/charter/charter.yaml"
    charter.write_bytes(charter.read_bytes() + b"changed: true\n")
    assert currency().stale_inputs == ("charter",)


@pytest.mark.parametrize("claim", ["primary", "foreign"])
def test_invalid_checkout_cannot_mint_currency_authority(currency_case, tmp_path: Path, claim: str):
    checkouts, _fact = currency_case
    root = checkouts.repository_root
    if claim == "foreign":
        root = tmp_path / "foreign"
        _init_repo(root)
    with pytest.raises(ActionContextError):
        resolve_owned_mission(checkouts.repository_root, root, checkouts.mission_slug, allowed_topologies=NEXT_OWNED_TOPOLOGIES)


@pytest.mark.parametrize("damage", ["missing", "malformed", "wrong-kind", "missing-evidence"])
def test_invalid_report_never_becomes_current(currency_case, damage: str):
    checkouts, _fact = currency_case
    report = checkouts.mission_dir / "analysis-report.md"
    if damage == "missing":
        report.unlink()
    elif damage == "malformed":
        report.write_text("---\n: [broken\n---\n", encoding="utf-8")
    elif damage == "wrong-kind":
        report.write_text(report.read_text(encoding="utf-8").replace("spec-kitty.analysis-report", "wrong-kind"), encoding="utf-8")
    else:
        report.write_text("---\nartifact_type: spec-kitty.analysis-report\ninput_artifacts: {}\n---\n", encoding="utf-8")
    assert _currency(currency_case).status == ("missing" if damage == "missing" else "stale")


def test_normal_recorder_binds_validated_owned_charter(owned_checkouts, monkeypatch, tmp_path: Path):
    checkouts = owned_checkouts
    for root, label in [(checkouts.repository_root, "repository-root"), (checkouts.owned_root, "owned")]:
        path = root / ".kittify/charter/charter.yaml"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"authority: {label}\n", encoding="utf-8")
    _git(checkouts.owned_root, "add", ".")
    _git(checkouts.owned_root, "commit", "-qm", "owned governance fixture")
    original_head = _git(checkouts.repository_root, "rev-parse", "HEAD")
    body = tmp_path / "analysis-body.md"
    body.write_text(_BODY, encoding="utf-8")
    monkeypatch.chdir(checkouts.owned_root)
    monkeypatch.setenv("SPECIFY_REPO_ROOT", str(checkouts.owned_root))
    result = CliRunner().invoke(
        mission_app, ["record-analysis", "--mission", checkouts.mission_slug, "--input-file", str(body), "--owned-checkout", str(checkouts.owned_root), "--json"]
    )
    assert result.exit_code == 0, result.output
    metadata, _body = FrontmatterManager().read(checkouts.mission_dir / "analysis-report.md")
    local = checkouts.owned_root / ".kittify/charter/charter.yaml"
    assert metadata["input_artifacts"]["charter"]["sha256"] == hashlib.sha256(local.read_bytes()).hexdigest()  # noqa: TID251 -- raw file-integrity freshness
    assert check_analysis_report_current(checkouts.mission_dir, checkouts.owned_root, charter_root=checkouts.owned_root).ok
    assert _git(checkouts.repository_root, "rev-parse", "HEAD") == original_head
    assert not (checkouts.repository_root / "kitty-specs" / checkouts.mission_slug).exists()


@pytest.mark.parametrize("damage", ["missing", "escaped"])
def test_owned_charter_cannot_fall_back_or_escape(currency_case, damage: str):
    checkouts, _fact = currency_case
    local = checkouts.owned_root / ".kittify/charter/charter.yaml"
    local.unlink()
    if damage == "escaped":
        local.symlink_to(checkouts.repository_root / ".kittify/charter/charter.yaml")
    verdict = _currency(currency_case)
    assert verdict.status == "stale"
    assert "charter" in verdict.stale_inputs or any(reason.startswith("path_relativization_failed:") for reason in verdict.stale_inputs)


@pytest.mark.parametrize("command", ["next", "record-analysis"])
@pytest.mark.parametrize("claim", ["repository-root", "foreign"])
def test_canonical_leaf_refuses_invalid_ownership_before_report_write(currency_case, monkeypatch, tmp_path: Path, command: str, claim: str):
    checkouts, _fact = currency_case
    claimed = checkouts.repository_root
    expected = "OWNED_CHECKOUT_IS_REPOSITORY_ROOT"
    if claim == "foreign":
        claimed = tmp_path / "foreign-command-root"
        _init_repo(claimed)
        expected = "OWNERSHIP_FOREIGN"
    report = checkouts.mission_dir / "analysis-report.md"
    before = report.read_bytes()
    head = _git(checkouts.owned_root, "rev-parse", "HEAD")
    monkeypatch.chdir(checkouts.owned_root)
    monkeypatch.setenv("SPECIFY_REPO_ROOT", str(checkouts.owned_root))
    args = ["--mission", checkouts.mission_slug, "--owned-checkout", str(claimed), "--json"]
    app = mission_app
    if command == "next":
        app = typer.Typer()
        app.command(name="next")(next_step)
    else:
        args.insert(0, command)
    result = CliRunner().invoke(app, args)
    assert result.exit_code != 0, result.output
    payload = json.JSONDecoder().raw_decode(result.output.lstrip())[0]
    assert payload["error_code"] == expected, payload
    assert report.read_bytes() == before
    assert _git(checkouts.owned_root, "rev-parse", "HEAD") == head
