"""Repair-failure reporting for plugin bundles (#6273).

The provider already returns findings_after; the repair service used to drop
them, so a failed ``--fix`` printed nothing and exited 0.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from specify_cli.tool_surface.bundles.model import BundleSources
from specify_cli.tool_surface.operations import ApplyConsent, AssessmentInputs, OperationRoot
from specify_cli.tool_surface.providers.plugin_bundle import (
    PLUGIN_BUNDLE_TOOL_KEY,
    PluginBundleProvider,
    plugin_manifest_definition,
)
from specify_cli.tool_surface.repair import SurfaceRepairService

from tests.specify_cli.tool_surface.bundles._support import full_plans

pytestmark = [pytest.mark.unit, pytest.mark.fast]


def _bundle_provider(project: Path, monkeypatch: pytest.MonkeyPatch) -> PluginBundleProvider:
    plans = full_plans(project)
    provider = PluginBundleProvider()
    monkeypatch.setattr(provider, "_plans_for_projection", lambda root: plans)
    return provider


def test_incomplete_bundle_repair_keeps_its_cause_through_the_service(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = _bundle_provider(tmp_path, monkeypatch)
    # A malformed required skill member makes the whole prepared batch incomplete.
    skill = tmp_path / ".agents/skills/spec-kitty-plan/SKILL.md"
    skill.write_bytes(b"---\ninvalid: [\n---\n")
    statuses = tuple(
        provider.probe(instance)
        for instance in provider.expand(plugin_manifest_definition(), PLUGIN_BUNDLE_TOOL_KEY, tmp_path)
    )
    assert statuses and all(not status.findings for status in statuses)

    result = SurfaceRepairService([provider]).repair(tmp_path, statuses)

    assert result.failed
    assert result.findings_after, "the repair service dropped the provider's cause"
    assert any("Malformed required skill frontmatter" in finding.message for finding in result.findings_after)


def test_successful_bundle_repair_reports_no_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    provider = _bundle_provider(tmp_path, monkeypatch)
    statuses = tuple(
        provider.probe(instance)
        for instance in provider.expand(plugin_manifest_definition(), PLUGIN_BUNDLE_TOOL_KEY, tmp_path)
    )
    result = SurfaceRepairService([provider]).repair(tmp_path, statuses)

    assert result.repaired and not result.failed and not result.findings_after


def test_probe_keeps_the_prepared_batch_cause(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    provider = _bundle_provider(tmp_path, monkeypatch)
    instance = provider.expand(plugin_manifest_definition(), PLUGIN_BUNDLE_TOOL_KEY, tmp_path)[0]
    first = provider.assess(
        AssessmentInputs(
            OperationRoot("project", "project", tmp_path.resolve()),
            projected=BundleSources(selected_targets=(instance.owner,)),
            consent=ApplyConsent(automatic=True),
        ),
        (),
        selections=(),
    )
    assert first.complete, first.diagnostics
    provider.apply(first, first.consent)
    skill = tmp_path / ".agents/skills/spec-kitty-plan/SKILL.md"
    skill.write_bytes(b"---\ninvalid: [\n---\n")

    status = provider.probe(instance)

    assert status.findings
    assert any("Malformed required skill frontmatter" in finding.message for finding in status.findings)
