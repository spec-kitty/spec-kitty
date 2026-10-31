"""Bind prompt content and context reads to the validated owned charter.

Provenance: the memory-safety program's original paired prompt-scope cases
identified this cross-service boundary defect. These native regressions reuse
the repository's actual owned-checkout fixture and canonical minter.
"""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

import pytest

from charter.activation.context import build_charter_context, build_charter_context_include, build_charter_context_json
from charter.activation.pack_context import ActiveCharterConfigError
from charter.activation.scope import CharterScope
from mission_runtime import ActionContextError
from runtime.next.prompt_builder import build_prompt
from specify_cli.cli.commands.charter._fresh_project_layer import _synthesize_project_layer
from specify_cli.core.owned_mission import NEXT_OWNED_TOPOLOGIES, resolve_owned_mission
from tests.integration.conftest import OwnedCheckouts

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]


def _snapshot(root: Path) -> dict[str, str]:
    return {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest() for path in (root / ".kittify").rglob("*") if path.is_file()}  # noqa: TID251 -- exact protected-file integrity


class TestOwnedPromptCharterScope:
    @pytest.fixture(autouse=True)
    def setup(self, owned_checkouts: OwnedCheckouts, monkeypatch, tmp_path: Path) -> None:
        self.case = owned_checkouts
        self.owned = self.case.owned_root
        self.primary = self.case.repository_root
        fixture = Path(__file__).parents[1] / "fixtures/owned-charter-scope"
        shutil.copytree(fixture, self.owned / ".kittify", dirs_exist_ok=True)
        (self.owned / ".kittify/config.yaml").write_text("charter: .kittify/charter/charter.yaml\n", encoding="utf-8")
        companion = self.owned / ".kittify/charter/charter.md"
        companion.write_text("# Owned governing policy\n\nOWNED_SOURCE_POLICY\n", encoding="utf-8")
        result = _synthesize_project_layer(self.owned, dry_run=False)
        assert result is not None and result["success"], result
        primary_dir = self.primary / ".kittify/charter"
        primary_dir.mkdir(exist_ok=True)
        self.primary_charter = primary_dir / "charter.yaml"
        self.primary_charter.write_text("schema_version: 2.0.0\ngovernance:\n  doctrine:\n    selected_directives: [PRIMARY_RETIRED_POLICY]\n", encoding="utf-8")
        (primary_dir / "charter.md").write_text("# Protected primary\n\nPRIMARY_ONLY_POLICY\n", encoding="utf-8")
        self.before = _snapshot(self.primary)
        self.fact = resolve_owned_mission(self.primary, self.owned, self.case.mission_slug, allowed_topologies=NEXT_OWNED_TOPOLOGIES)
        monkeypatch.setenv("SPEC_KITTY_HOME", str(tmp_path / "runtime-state"))

    def prompt(self, feature_dir: Path | None = None) -> str:
        text, path = build_prompt(
            "implement", feature_dir or self.case.mission_dir, self.case.mission_slug, "WP01", "codex", self.primary, "software-dev", owned=self.fact
        )
        assert path.is_file()
        return text

    def test_actual_prompt_contains_owned_constraints_and_source(self) -> None:
        from ruamel.yaml import YAML

        text = self.prompt()
        for path in (self.owned / ".kittify/charter-packs/directive").glob("mant-*.directive.yaml"):
            intent = YAML(typ="safe").load(path.read_text(encoding="utf-8"))["intent"]
            assert " ".join(intent.split()) in " ".join(text.split())
        for code in ["MANT_001", "MANT_002", "MANT_003", "MANT_004", "MANT_005"]:
            assert code in text
        assert str(self.owned / ".kittify/charter/charter.md") in text
        assert "PRIMARY_ONLY_POLICY" not in text
        assert _snapshot(self.primary) == self.before

    def test_primary_drift_does_not_change_owned_prompt_or_scoped_fetch(self) -> None:
        self.prompt()
        self.primary_charter.write_text("schema_version: 2.0.0\ngovernance:\n  doctrine:\n    selected_directives: [CHANGED_PRIMARY_POLICY]\n", encoding="utf-8")
        expected = _snapshot(self.primary)
        assert "MANT_003" in self.prompt()
        context = build_charter_context_include(self.owned, "directive:MANT_003", action="implement", scope=CharterScope.default(self.owned))
        assert "Manual-memory surfaces must preserve memory safety" in context
        assert _snapshot(self.primary) == expected

    def test_scoped_context_keeps_default_primary_behavior(self) -> None:
        context = build_charter_context(self.owned, action="implement", mark_loaded=False, mission_type="software-dev", scope=CharterScope.default(self.owned))
        assert "MANT_003" in context.text
        with pytest.raises(ActiveCharterConfigError):
            build_charter_context(self.owned, action="implement", mark_loaded=False, mission_type="software-dev")
        assert _snapshot(self.primary) == self.before

    def test_scoped_json_uses_owned_metadata_and_directive_inventory(self) -> None:
        payload = build_charter_context_json(
            self.owned, action="implement", mission_type="software-dev", feature_dir=self.case.mission_dir, scope=CharterScope.default(self.owned)
        )
        assert payload["project_charter"]["bytes"] == (self.owned / ".kittify/charter/charter.yaml").stat().st_size
        assert any(row["id"] == "MANT-003" for row in payload["all_directives"])
        assert any(row["id"] == "MANT_003" for row in payload["directives"])
        assert _snapshot(self.primary) == self.before

    def test_mission_outside_owned_fact_remains_refused(self, tmp_path: Path) -> None:
        other = tmp_path / "outside-mission"
        other.mkdir()
        with pytest.raises(ActionContextError):
            self.prompt(other)
        assert _snapshot(self.primary) == self.before

    def test_equal_yaml_cannot_hide_wrong_companion_or_state_writes(self) -> None:
        self.primary_charter.write_bytes((self.owned / ".kittify/charter/charter.yaml").read_bytes())
        expected = _snapshot(self.primary)
        text = self.prompt()
        assert str(self.owned / ".kittify/charter/charter.md") in text
        assert "PRIMARY_ONLY_POLICY" not in text
        assert _snapshot(self.primary) == expected
        assert not (self.primary / ".kittify/charter/context-state.json").exists()

    @pytest.mark.parametrize("loader", ["activations", "selection"])
    def test_default_loader_keeps_keyword_absence_and_explicit_scope(self, monkeypatch, loader: str) -> None:
        from charter.activation.context_renderers.activation_block import _load_governance_activations
        from charter.activation.org_pack_discovery import _load_governance_charter_config
        from charter.activation.schemas import GovernanceConfig

        calls = []

        def load(root: Path, **kwargs):
            calls.append((root, kwargs))
            return GovernanceConfig()

        monkeypatch.setattr("charter.activation.sync.load_governance_config", load)
        operation = _load_governance_activations if loader == "activations" else _load_governance_charter_config
        operation(self.primary)
        assert calls == [(self.primary, {})]
        scope = CharterScope.default(self.owned)
        operation(self.primary, scope=scope)
        assert calls[-1] == (self.primary, {"scope": scope})
        assert _snapshot(self.primary) == self.before

    @pytest.mark.parametrize("loader", ["activations", "selection"])
    def test_scoped_loader_propagates_actual_retired_owned_governance(self, loader: str) -> None:
        from charter.activation.context_renderers.activation_block import _load_governance_activations
        from charter.activation.org_pack_discovery import _load_governance_charter_config

        self.primary_charter.write_text("schema_version: 2.0.0\ngovernance: {}\n", encoding="utf-8")
        expected = _snapshot(self.primary)
        (self.owned / ".kittify/charter/charter.yaml").write_text(
            "schema_version: 2.0.0\ngovernance:\n  doctrine:\n    selected_directives: []\n", encoding="utf-8"
        )
        operation = _load_governance_activations if loader == "activations" else _load_governance_charter_config
        with pytest.raises(ActiveCharterConfigError):
            operation(self.primary, scope=CharterScope.default(self.owned))
        assert _snapshot(self.primary) == expected
