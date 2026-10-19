"""#6404 -- ``charter synthesize`` / ``resynthesize`` append created tactic ids to an explicit
``activated_tactics`` list, restamp the bundle hash, and never touch an absent key.

Real synthesis against a ``tmp_path`` repo with the canonical ``FixtureAdapter``; only the
interview -> request derivation and evidence collection are patched (same convention as
``tests/specify_cli/cli/commands/charter/test_synthesize_cli_reconcile.py``).
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

import pytest
import yaml
from typer.testing import CliRunner

from charter.activation.synthesizer import FixtureAdapter, SynthesisRequest, SynthesisTarget, synthesize
from charter.activation.synthesizer.manifest import MANIFEST_PATH, load_yaml, verify_manifest_hash
from charter.bundle import compute_bundle_content_hash
from specify_cli.cli.commands.charter import charter_app

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

runner = CliRunner()

_TACTIC = "how-we-apply-directive-003"
_EXISTING = "adversarial-qa-handoff"
_CHARTER_YAML = "schema_version: '2.0.0'\ngovernance: {}\ndirectives: {}\nmetadata:\n  generated_at: '2026-10-19T00:00:00Z'\n  bundle_schema_version: 2\n"


def _request(run_id: str) -> SynthesisRequest:
    target = SynthesisTarget(
        kind="directive",
        slug="mission-type-scope-directive",
        title="Mission Type Scope Directive",
        artifact_id="PROJECT_001",
        source_section="mission_type",
    )
    return SynthesisRequest(
        target=target,
        interview_snapshot={
            "mission_type": "software_dev",
            "language_scope": ["python"],
            "testing_philosophy": "test-driven development with high coverage",
            "neutrality_posture": "balanced",
            "selected_directives": ["DIRECTIVE_003"],
            "risk_appetite": "moderate",
        },
        doctrine_snapshot={
            "directives": {
                "DIRECTIVE_003": {"id": "DIRECTIVE_003", "title": "Decision Documentation", "body": "Document significant architectural decisions via ADRs."}
            },
            "tactics": {},
            "styleguides": {},
        },
        drg_snapshot={"nodes": [{"urn": "directive:DIRECTIVE_003", "kind": "directive"}], "edges": [], "schema_version": "1"},
        run_id=run_id,
        adapter_hints={"language": "python"},
    )


def _seed_project(repo: Path, *, activated_tactics: list[str] | None) -> Path:
    """Migrated-shape project: ``charter:`` pointer, so activation lives in charter.yaml."""
    kittify = repo / ".kittify"
    (kittify / "charter").mkdir(parents=True, exist_ok=True)
    (kittify / "config.yaml").write_text("vcs:\n  type: git\ncharter: .kittify/charter/charter.yaml\n", encoding="utf-8")
    body = _CHARTER_YAML
    if activated_tactics is not None:
        body += yaml.safe_dump({"activated_tactics": activated_tactics})
    path = kittify / "charter" / "charter.yaml"
    path.write_text(body, encoding="utf-8")
    return path


def _activated(charter_yaml: Path) -> Any:
    return (yaml.safe_load(charter_yaml.read_text(encoding="utf-8")) or {}).get("activated_tactics")


def _invoke(isolate: Callable[..., Path], args: list[str], request: SynthesisRequest) -> Any:
    isolate()
    with (
        patch(
            "specify_cli.cli.commands.charter._collect_evidence_result",
            return_value=SimpleNamespace(warnings=[], bundle=SimpleNamespace()),
        ),
        patch(
            "specify_cli.cli.commands.charter._build_synthesis_request",
            return_value=(request, FixtureAdapter()),
        ),
    ):
        return runner.invoke(charter_app, args, catch_exceptions=False)


def _synthesize_cli(isolate: Callable[..., Path], *extra: str) -> Any:
    return _invoke(isolate, ["synthesize", "--adapter", "fixture", "--json", *extra], _request("01BBBBBBBBBBBBBBBBBBBBBBBBB"))


def test_synthesize_appends_created_tactics_to_explicit_list_and_restamps(tmp_path: Path, charter_cwd_isolation: Callable[..., Path]) -> None:
    charter_yaml = _seed_project(tmp_path, activated_tactics=[_EXISTING])

    result = _synthesize_cli(charter_cwd_isolation)

    assert result.exit_code == 0, result.output
    activated = _activated(charter_yaml)
    assert _TACTIC in activated
    assert _EXISTING in activated  # existing entry kept
    manifest = load_yaml(tmp_path / MANIFEST_PATH)
    verify_manifest_hash(manifest)
    assert manifest.bundle_content_hash == compute_bundle_content_hash(tmp_path)  # restamped after the append


def test_synthesize_second_run_does_not_duplicate(tmp_path: Path, charter_cwd_isolation: Callable[..., Path]) -> None:
    charter_yaml = _seed_project(tmp_path, activated_tactics=[_EXISTING])

    assert _synthesize_cli(charter_cwd_isolation).exit_code == 0
    assert _synthesize_cli(charter_cwd_isolation).exit_code == 0

    assert _activated(charter_yaml).count(_TACTIC) == 1


def test_synthesize_leaves_absent_key_absent(tmp_path: Path, charter_cwd_isolation: Callable[..., Path]) -> None:
    charter_yaml = _seed_project(tmp_path, activated_tactics=None)

    result = _synthesize_cli(charter_cwd_isolation)

    assert result.exit_code == 0, result.output
    assert "activated_tactics" not in (yaml.safe_load(charter_yaml.read_text(encoding="utf-8")) or {})
    # control: the run did create the tactic, so the absence is not "nothing was synthesized"
    assert (tmp_path / ".kittify" / "charter-packs" / "tactic" / f"{_TACTIC}.tactic.yaml").is_file()


def test_dry_run_writes_no_activation(tmp_path: Path, charter_cwd_isolation: Callable[..., Path]) -> None:
    charter_yaml = _seed_project(tmp_path, activated_tactics=[_EXISTING])
    before = charter_yaml.read_bytes()

    result = _synthesize_cli(charter_cwd_isolation, "--dry-run")

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["result"] == "dry_run"
    assert charter_yaml.read_bytes() == before


def test_refused_orphan_run_does_not_append(tmp_path: Path, charter_cwd_isolation: Callable[..., Path]) -> None:
    charter_yaml = _seed_project(tmp_path, activated_tactics=[_EXISTING])
    synthesize(_request("01AAAAAAAAAAAAAAAAAAAAAAAAA"), adapter=FixtureAdapter(), repo_root=tmp_path)
    graph_path = tmp_path / ".kittify" / "charter-packs" / "graph.yaml"
    graph = yaml.safe_load(graph_path.read_text(encoding="utf-8"))
    graph["nodes"].append({"urn": "tactic:orphaned-no-backing-artifact", "kind": "tactic", "label": "Orphan"})
    graph_path.write_text(yaml.safe_dump(graph), encoding="utf-8")
    before = charter_yaml.read_bytes()

    result = _synthesize_cli(charter_cwd_isolation)

    assert result.exit_code == 1, result.output
    assert charter_yaml.read_bytes() == before
    assert _TACTIC not in _activated(charter_yaml)


def test_resynthesize_topic_appends_regenerated_tactic(tmp_path: Path, charter_cwd_isolation: Callable[..., Path]) -> None:
    charter_yaml = _seed_project(tmp_path, activated_tactics=[_EXISTING])
    synthesize(_request("01AAAAAAAAAAAAAAAAAAAAAAAAA"), adapter=FixtureAdapter(), repo_root=tmp_path)
    assert _TACTIC not in _activated(charter_yaml)  # library synthesize alone does not append

    result = _invoke(
        charter_cwd_isolation,
        ["resynthesize", "--adapter", "fixture", "--json", "--topic", f"tactic:{_TACTIC}"],
        _request("01CCCCCCCCCCCCCCCCCCCCCCCCC"),
    )

    assert result.exit_code == 0, result.output
    assert _TACTIC in _activated(charter_yaml)
    assert _EXISTING in _activated(charter_yaml)
