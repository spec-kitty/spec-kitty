"""#6404 -- ``charter synthesize`` / ``resynthesize`` append created tactic ids to an explicit
``activated_tactics`` list, restamp the bundle hash, and never touch an absent key.

Real synthesis against a ``tmp_path`` repo with the canonical ``FixtureAdapter``; only the
interview -> request derivation and evidence collection are patched (same convention as
``tests/specify_cli/cli/commands/charter/test_synthesize_cli_reconcile.py``).
"""

from __future__ import annotations

import json
import shutil
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


def test_synthesize_does_not_readd_a_tactic_the_operator_removed(tmp_path: Path, charter_cwd_isolation: Callable[..., Path]) -> None:
    """Full synthesize appends only tactics THIS run created, not every manifest tactic (#6404)."""
    charter_yaml = _seed_project(tmp_path, activated_tactics=[_EXISTING])
    assert _synthesize_cli(charter_cwd_isolation).exit_code == 0
    assert _TACTIC in _activated(charter_yaml)  # control: the first run created and appended it

    charter_yaml.write_text(charter_yaml.read_text(encoding="utf-8").replace(_TACTIC, "operator-kept-other"), encoding="utf-8")
    assert _TACTIC not in _activated(charter_yaml)

    assert _synthesize_cli(charter_cwd_isolation).exit_code == 0

    assert _TACTIC not in _activated(charter_yaml)  # the manifest still lists it, but this run did not create it
    assert "operator-kept-other" in _activated(charter_yaml)


def test_synthesize_appends_a_tactic_created_by_the_rerun(tmp_path: Path, charter_cwd_isolation: Callable[..., Path]) -> None:
    """Control for the test above: when the rerun creates the tactic afresh, it is appended."""
    charter_yaml = _seed_project(tmp_path, activated_tactics=[_EXISTING])
    assert _synthesize_cli(charter_cwd_isolation).exit_code == 0
    charter_yaml.write_text(charter_yaml.read_text(encoding="utf-8").replace(_TACTIC, "operator-kept-other"), encoding="utf-8")
    (tmp_path / MANIFEST_PATH).unlink()
    shutil.rmtree(tmp_path / ".kittify" / "charter-packs")

    result = _synthesize_cli(charter_cwd_isolation)

    assert result.exit_code == 0, result.output
    assert _TACTIC in _activated(charter_yaml)  # new to the manifest this run -> appended


def test_created_tactic_slugs_takes_only_added_tactic_entries() -> None:
    from charter.activation.synthesizer.reach_only import created_tactic_slugs
    from charter.activation.synthesizer.reconcile import ManifestDelta, ManifestEntryRef, ReconciliationDelta

    delta = ReconciliationDelta(
        manifest_delta=ManifestDelta(
            retained=(ManifestEntryRef(kind="tactic", slug="kept-old", backing_artifact="p"),),
            added=(
                ManifestEntryRef(kind="tactic", slug="brand-new", backing_artifact="p"),
                ManifestEntryRef(kind="directive", slug="new-directive", backing_artifact="p"),
            ),
        )
    )

    assert created_tactic_slugs(delta) == ["brand-new"]
    assert created_tactic_slugs(None) == []
    assert created_tactic_slugs(SimpleNamespace(manifest_delta=delta.manifest_delta)) == []


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


def _resynthesize_tactic_cli(isolate: Callable[..., Path]) -> Any:
    return _invoke(
        isolate,
        ["resynthesize", "--adapter", "fixture", "--json", "--topic", f"tactic:{_TACTIC}"],
        _request("01CCCCCCCCCCCCCCCCCCCCCCCCC"),
    )


def test_resynthesize_does_not_readd_a_tactic_the_operator_removed(tmp_path: Path, charter_cwd_isolation: Callable[..., Path]) -> None:
    """Resynthesize appends only manifest-new tactics: a regenerated, operator-removed one stays removed (#6404)."""
    charter_yaml = _seed_project(tmp_path, activated_tactics=[_EXISTING])
    synthesize(_request("01AAAAAAAAAAAAAAAAAAAAAAAAA"), adapter=FixtureAdapter(), repo_root=tmp_path)
    assert _TACTIC in [e.slug for e in load_yaml(tmp_path / MANIFEST_PATH).artifacts]  # control: tactic is in the manifest
    assert _TACTIC not in _activated(charter_yaml)  # operator never activated / removed it

    result = _resynthesize_tactic_cli(charter_cwd_isolation)

    assert result.exit_code == 0, result.output
    assert _TACTIC not in _activated(charter_yaml)
    assert _EXISTING in _activated(charter_yaml)


def test_resynthesize_with_nothing_new_does_not_rewrite_config_or_restamp(tmp_path: Path, charter_cwd_isolation: Callable[..., Path]) -> None:
    charter_yaml = _seed_project(tmp_path, activated_tactics=[_EXISTING, _TACTIC])
    synthesize(_request("01AAAAAAAAAAAAAAAAAAAAAAAAA"), adapter=FixtureAdapter(), repo_root=tmp_path)
    before = charter_yaml.read_bytes()

    with patch("charter.activation.bundle_restamp.restamp_bundle_hash") as restamp:
        result = _resynthesize_tactic_cli(charter_cwd_isolation)

    assert result.exit_code == 0, result.output
    assert charter_yaml.read_bytes() == before
    restamp.assert_not_called()


def test_append_skips_slugs_already_activated(tmp_path: Path) -> None:
    from charter.activation.synthesizer.reach_only import append_synthesized_tactic_activations

    charter_yaml = _seed_project(tmp_path, activated_tactics=[_EXISTING])
    before = charter_yaml.read_bytes()

    assert append_synthesized_tactic_activations(tmp_path, [_EXISTING]) == []
    assert charter_yaml.read_bytes() == before
