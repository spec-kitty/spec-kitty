"""``doctor charter-packs`` reports a file-name collision across the configured chain (#6743).

Decision ``file_name_collision``: a file name that files in more than one layer
bind to different declared ids is a pack-content error, and every activation
writer refuses such an id (#6527). ``charter pack validate`` sees a pack against
the built-in layer; only the repository-wide diagnostic can see an org pack and
the project pack colliding with each other, which is the gap this test pins.

The finding is folded into the existing health report (``org_drg``): a structured
``file_name_collisions`` list for ``--json`` and one ``errors`` entry that flips
the honest ``healthy`` flag, so the command exits 1 instead of printing
``Collisions: none``.
"""

from __future__ import annotations

import contextlib
import json
import textwrap
from pathlib import Path

import pytest
from typer.testing import CliRunner

from specify_cli.cli.commands._charter_pack_collect import (
    _collect_file_name_collisions,
    _run_file_name_collision_check,
)
from specify_cli.cli.commands.doctor import app as doctor_app

pytestmark = [pytest.mark.unit, pytest.mark.fast]

runner = CliRunner()

SHARED_FILE_NAME = "shared-collision-tactic"


def _write_tactic(path: Path, declared: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        textwrap.dedent(
            f"""\
            schema_version: "1.0"
            id: {declared}
            name: Shared tactic
            purpose: Proves a file-name collision.
            steps:
              - title: Do
                description: Do it.
            """
        ),
        encoding="utf-8",
    )


def _write_config(repo_root: Path, org_pack: Path) -> None:
    config_dir = repo_root / ".kittify"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "config.yaml").write_text(
        textwrap.dedent(
            f"""\
            charter_packs:
              org:
                packs:
                  - name: acme
                    local_path: {org_pack}
            """
        ).lstrip(),
        encoding="utf-8",
    )


def _colliding_repo(tmp_path: Path, *, project_declared: str = "proj-shared") -> Path:
    """An org pack and a project pack that share a tactic file name, declaring different ids."""
    org_pack = tmp_path / "acme"
    _write_tactic(org_pack / "tactics" / f"{SHARED_FILE_NAME}.tactic.yaml", "org-shared")
    _write_tactic(tmp_path / ".kittify" / "charter-packs" / "tactic" / f"{SHARED_FILE_NAME}.tactic.yaml", project_declared)
    _write_config(tmp_path, org_pack)
    return tmp_path


def _findings(repo_root: Path) -> list[dict[str, object]]:
    return [finding for finding in _collect_file_name_collisions(repo_root) if finding["file_name"] == SHARED_FILE_NAME]


def test_collect_reports_an_org_and_project_file_name_collision(tmp_path: Path) -> None:
    """The chain case validate cannot see: org and project reuse one file name for different ids."""
    repo = _colliding_repo(tmp_path)

    findings = _findings(repo)

    assert len(findings) == 1
    finding = findings[0]
    assert finding["kind"] == "tactic"
    declarations = finding["declarations"]
    assert [(entry["layer"], entry["declared_id"]) for entry in declarations] == [("project", "proj-shared"), ("org", "org-shared")]
    assert all(entry["path"].endswith(f"{SHARED_FILE_NAME}.tactic.yaml") for entry in declarations)


def test_collect_is_silent_for_a_same_id_override_and_for_distinct_file_names(tmp_path: Path) -> None:
    """FR-006 control on the same fixture family."""
    same_id = _colliding_repo(tmp_path / "same-id", project_declared="org-shared")

    distinct = tmp_path / "distinct"
    org_pack = distinct / "acme"
    _write_tactic(org_pack / "tactics" / "org-owned-tactic.tactic.yaml", "org-shared")
    _write_tactic(distinct / ".kittify" / "charter-packs" / "tactic" / "project-owned-tactic.tactic.yaml", "proj-shared")
    _write_config(distinct, org_pack)

    for repo in (same_id, distinct):
        assert _findings(repo) == []


def test_doctor_charter_packs_text_names_the_file_name_both_layers_and_both_ids(tmp_path: Path) -> None:
    repo = _colliding_repo(tmp_path)

    with contextlib.chdir(repo):
        result = runner.invoke(doctor_app, ["charter-packs"], catch_exceptions=False)

    assert result.exit_code == 1, result.stdout
    output = " ".join(result.stdout.split())  # rich wraps at the runner's console width
    assert "File-name collisions" in output
    assert SHARED_FILE_NAME in output
    assert "org-shared" in output and "proj-shared" in output


def test_doctor_charter_packs_json_carries_the_structured_finding(tmp_path: Path) -> None:
    repo = _colliding_repo(tmp_path)

    with contextlib.chdir(repo):
        result = runner.invoke(doctor_app, ["charter-packs", "--json"], catch_exceptions=False)

    assert result.exit_code == 1, result.stdout
    payload = json.loads(result.stdout)
    findings = payload["org_drg"]["file_name_collisions"]
    assert isinstance(findings, list) and findings
    match = next(finding for finding in findings if finding["file_name"] == SHARED_FILE_NAME)
    assert match["kind"] == "tactic"
    assert {entry["layer"] for entry in match["declarations"]} == {"org", "project"}


def test_doctor_json_reports_an_empty_list_when_the_chain_is_clean(tmp_path: Path) -> None:
    """The key is always present, so "checked and clean" is distinguishable from "not checked"."""
    repo = _colliding_repo(tmp_path, project_declared="org-shared")

    with contextlib.chdir(repo):
        result = runner.invoke(doctor_app, ["charter-packs", "--json"], catch_exceptions=False)

    payload = json.loads(result.stdout)
    assert payload["org_drg"]["file_name_collisions"] == []


def test_the_check_leg_records_a_failure_instead_of_raising(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """NFR-003: a scan that cannot run is an error entry, never a traceback out of doctor."""
    from specify_cli.cli.commands._charter_pack_health import CharterPackHealthReport

    report = CharterPackHealthReport(packs=[], org_drg={"errors": []})

    def _explode(_repo_root: Path) -> list[dict[str, object]]:
        raise RuntimeError("chain is unreadable")

    monkeypatch.setattr("specify_cli.cli.commands._charter_pack_collect._collect_file_name_collisions", _explode)

    _run_file_name_collision_check(report, tmp_path)

    assert any("file-name collision scan error" in str(entry) for entry in report.org_drg["errors"])


def test_two_runs_report_the_same_findings(tmp_path: Path) -> None:
    """NFR-002: deterministic order, so repeated runs on one tree are identical."""
    repo = _colliding_repo(tmp_path)

    assert _collect_file_name_collisions(repo) == _collect_file_name_collisions(repo)
