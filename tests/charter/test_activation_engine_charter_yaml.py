"""Unit tests for the activation relocation onto ``charter.yaml`` (WP02, T010).

Covers the write seam after activation moves from ``.kittify/config.yaml``
into ``charter.yaml``:

* :func:`charter.activation.pack_manager.resolve_activation_write_target` — the shared
  pointer-resolution primitive used by ``CharterPackManager.activate`` /
  ``deactivate`` / ``merge_defaults`` and by the two other activation
  writers (``specify_cli.cli.commands.charter.interview``,
  ``charter.activation.org_charter``).
* ``activation_engine.commit_plan`` writing into ``charter.yaml`` via that
  target, preserving the OTHER sections (``governance``/``catalog``/
  ``directives``/``metadata``) byte-for-byte (data-model.md Landmine 3 /
  INV-9 — the #2772 clobber, one level down, on a tracked file).
* ``CharterPackManager.activate`` / ``deactivate`` / ``merge_defaults``
  end-to-end against a migrated project (a ``charter:`` pointer resolves to
  a real ``charter.yaml``).

The legacy/un-migrated path (no ``charter:`` pointer -> config.yaml is the
target, unchanged) is pinned by the EXISTING ``tests/charter/test_pack_manager.py``
and ``tests/charter/test_activation_engine.py`` suites, which never set a
pointer and MUST stay green (reference, verified at aggregate — WP04).
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml as pyyaml

from charter.activation.activation_engine import ActivationPlan, commit_plan
from charter.activation.invocation_context import ProjectContext
from charter.activation.pack_context import CharterPackConfigError
from charter.activation.pack_manager import CharterPackManager, resolve_activation_write_target

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

_GOVERNANCE_BLOCK = """\
governance:
  testing:
    coverage_threshold: 80
  quality:
    max_complexity: 15
"""

_MIGRATED_CHARTER_YAML = f"""\
schema_version: "2.0.0"
{_GOVERNANCE_BLOCK}directives:
  - id: "001-architectural-integrity-standard"
    title: "Architectural integrity"
    description: "Keep boundaries clean."
    severity: "binding"
    references: []
catalog:
  mission: software-dev
  template_set: software-dev-default
  languages: []
  references: []
activated_directives:
  - 001-architectural-integrity-standard
metadata:
  generated_at: "2026-07-15T00:00:00Z"
  bundle_schema_version: 2
"""


def _write_config(tmp_path: Path, content: str) -> Path:
    kittify = tmp_path / ".kittify"
    kittify.mkdir(parents=True, exist_ok=True)
    config_path = kittify / "config.yaml"
    config_path.write_text(content, encoding="utf-8")
    return config_path


def _write_charter_yaml(tmp_path: Path, content: str) -> Path:
    charter_dir = tmp_path / ".kittify" / "charter"
    charter_dir.mkdir(parents=True, exist_ok=True)
    charter_path = charter_dir / "charter.yaml"
    charter_path.write_text(content, encoding="utf-8")
    return charter_path


def _migrated_project(tmp_path: Path) -> Path:
    """A migrated project: config.yaml carries the pointer, charter.yaml exists."""
    _write_config(tmp_path, "vcs:\n  type: git\ncharter: .kittify/charter/charter.yaml\n")
    _write_charter_yaml(tmp_path, _MIGRATED_CHARTER_YAML)
    return tmp_path


# ---------------------------------------------------------------------------
# resolve_activation_write_target — legacy branch (no pointer)
# ---------------------------------------------------------------------------


class TestResolveActivationWriteTargetLegacy:
    def test_no_pointer_targets_config_yaml(self, tmp_path: Path) -> None:
        config_path = _write_config(tmp_path, "vcs:\n  type: git\n")

        target_path, data, save = resolve_activation_write_target(tmp_path)

        assert target_path == config_path
        assert isinstance(data, dict)
        assert "charter" not in data

    def test_no_config_yaml_at_all_targets_config_yaml_empty_dict(
        self, tmp_path: Path
    ) -> None:
        target_path, data, _save = resolve_activation_write_target(tmp_path)

        assert target_path == tmp_path / ".kittify" / "config.yaml"
        assert data == {}

    def test_legacy_save_writes_full_config_document(self, tmp_path: Path) -> None:
        config_path = _write_config(
            tmp_path, "vcs:\n  type: git\nactivated_directives:\n  - existing\n"
        )
        target_path, data, save = resolve_activation_write_target(tmp_path)

        data["activated_directives"] = ["existing", "new-one"]
        save(target_path, data)

        reloaded = pyyaml.safe_load(config_path.read_text(encoding="utf-8"))
        assert reloaded["activated_directives"] == ["existing", "new-one"]
        assert reloaded["vcs"] == {"type": "git"}


# ---------------------------------------------------------------------------
# resolve_activation_write_target — migrated branch (pointer present)
# ---------------------------------------------------------------------------


class TestResolveActivationWriteTargetMigrated:
    def test_pointer_present_targets_charter_yaml(self, tmp_path: Path) -> None:
        _migrated_project(tmp_path)

        target_path, data, _save = resolve_activation_write_target(tmp_path)

        assert target_path == tmp_path / ".kittify" / "charter" / "charter.yaml"
        assert data["activated_directives"] == ["001-architectural-integrity-standard"]
        assert "governance" in data  # full document loaded, not just activation

    def test_dangling_pointer_raises(self, tmp_path: Path) -> None:
        _write_config(
            tmp_path, "vcs:\n  type: git\ncharter: .kittify/charter/charter.yaml\n"
        )
        # charter.yaml deliberately not created.

        with pytest.raises(CharterPackConfigError, match="CHARTER_PACK_CONFIG_INVALID"):
            resolve_activation_write_target(tmp_path)


# ---------------------------------------------------------------------------
# commit_plan through the migrated target — INV-9 section preservation
# (Landmine 3 / the #2772 clobber, one level down)
# ---------------------------------------------------------------------------


class TestCommitPlanChartersYamlSectionPreservation:
    def test_commit_plan_writes_activation_and_preserves_governance_and_catalog(
        self, tmp_path: Path
    ) -> None:
        _migrated_project(tmp_path)
        charter_path = tmp_path / ".kittify" / "charter" / "charter.yaml"
        before_text = charter_path.read_text(encoding="utf-8")

        target_path, data, save = resolve_activation_write_target(tmp_path)
        plan = ActivationPlan(
            yaml_key="activated_directives",
            new_list=["001-architectural-integrity-standard", "010-specification-fidelity-requirement"],
            activated=["010-specification-fidelity-requirement"],
        )
        commit_plan(target_path, data, plan, save=save)

        after = pyyaml.safe_load(charter_path.read_text(encoding="utf-8"))
        assert after["activated_directives"] == [
            "001-architectural-integrity-standard",
            "010-specification-fidelity-requirement",
        ]
        # Other sections structurally unchanged (INV-9).
        before = pyyaml.safe_load(before_text)
        assert after["governance"] == before["governance"]
        assert after["catalog"] == before["catalog"]
        assert after["directives"] == before["directives"]
        assert after["metadata"] == before["metadata"]

    def test_commit_plan_does_not_create_an_activation_subsection(
        self, tmp_path: Path
    ) -> None:
        """Activation keys are FLAT root keys (paula BLOCKER-1) — commit_plan
        must never nest them under an ``activation:`` mapping key."""
        _migrated_project(tmp_path)
        target_path, data, save = resolve_activation_write_target(tmp_path)
        plan = ActivationPlan(
            yaml_key="activated_tactics",
            new_list=["acceptance-test-first"],
            activated=["acceptance-test-first"],
        )
        commit_plan(target_path, data, plan, save=save)

        after = pyyaml.safe_load(target_path.read_text(encoding="utf-8"))
        assert "activation" not in after
        assert after["activated_tactics"] == ["acceptance-test-first"]


# ---------------------------------------------------------------------------
# CharterPackManager end-to-end against a migrated project
#
# NOTE: these tests build ``ProjectContext(repo_root=tmp_path)`` via the bare
# dataclass constructor rather than ``ProjectContext.from_repo(tmp_path)``.
# ``CharterPackManager.activate``/``deactivate``/``list_activated``/
# ``merge_defaults`` only ever call ``ctx.require_repo_root()`` -- they never
# touch ``ctx.pack_context`` -- whereas ``from_repo`` eagerly resolves
# ``PackContext.from_config()``, which now hard-fails (WP04, C-A1) when
# ``mission_type_activations`` is absent from ``_MIGRATED_CHARTER_YAML``
# (an unrelated key to what these tests exercise). See
# ``tests/charter/test_pack_manager.py``'s ``ctx`` fixture for the same
# rationale spelled out in full.
# ---------------------------------------------------------------------------


@pytest.fixture()
def manager() -> CharterPackManager:
    return CharterPackManager()


class TestActivateAgainstMigratedProject:
    def test_activate_writes_into_charter_yaml_not_config_yaml(
        self, manager: CharterPackManager, tmp_path: Path
    ) -> None:
        _migrated_project(tmp_path)
        ctx = ProjectContext(repo_root=tmp_path)

        manager.activate(
            ctx, kind="directive", artifact_id="010-specification-fidelity-requirement"
        )

        charter_path = tmp_path / ".kittify" / "charter" / "charter.yaml"
        charter_data = pyyaml.safe_load(charter_path.read_text(encoding="utf-8"))
        assert "010-specification-fidelity-requirement" in charter_data["activated_directives"]

        config_data = pyyaml.safe_load(
            (tmp_path / ".kittify" / "config.yaml").read_text(encoding="utf-8")
        )
        assert "activated_directives" not in config_data

    def test_activate_preserves_governance_section(
        self, manager: CharterPackManager, tmp_path: Path
    ) -> None:
        _migrated_project(tmp_path)
        ctx = ProjectContext(repo_root=tmp_path)

        manager.activate(
            ctx, kind="directive", artifact_id="010-specification-fidelity-requirement"
        )

        charter_path = tmp_path / ".kittify" / "charter" / "charter.yaml"
        charter_data = pyyaml.safe_load(charter_path.read_text(encoding="utf-8"))
        assert charter_data["governance"]["testing"]["coverage_threshold"] == 80


class TestDeactivateAgainstMigratedProject:
    def test_deactivate_removes_from_charter_yaml(
        self, manager: CharterPackManager, tmp_path: Path
    ) -> None:
        _migrated_project(tmp_path)
        ctx = ProjectContext(repo_root=tmp_path)

        result = manager.deactivate(
            ctx, kind="directive", artifact_id="001-architectural-integrity-standard"
        )

        assert result.deactivated == ["001-architectural-integrity-standard"]
        charter_path = tmp_path / ".kittify" / "charter" / "charter.yaml"
        charter_data = pyyaml.safe_load(charter_path.read_text(encoding="utf-8"))
        assert charter_data["activated_directives"] == []


class TestListActivatedAgainstMigratedProject:
    def test_list_activated_reads_from_charter_yaml(
        self, manager: CharterPackManager, tmp_path: Path
    ) -> None:
        _migrated_project(tmp_path)
        ctx = ProjectContext(repo_root=tmp_path)

        result = manager.list_activated(ctx)

        assert result["directive"] == frozenset({"001-architectural-integrity-standard"})


class TestMergeDefaultsAgainstMigratedProject:
    def test_merge_defaults_seeds_absent_keys_into_charter_yaml_single_write(
        self, manager: CharterPackManager, tmp_path: Path
    ) -> None:
        _migrated_project(tmp_path)
        ctx = ProjectContext(repo_root=tmp_path)

        result = manager.merge_defaults(ctx)

        assert "tactic" in result.kinds_written
        assert "directive" not in result.kinds_written  # already present, not overwritten

        charter_path = tmp_path / ".kittify" / "charter" / "charter.yaml"
        charter_data = pyyaml.safe_load(charter_path.read_text(encoding="utf-8"))
        assert charter_data["activated_directives"] == ["001-architectural-integrity-standard"]
        assert isinstance(charter_data["activated_tactics"], list)
        assert charter_data["governance"]["testing"]["coverage_threshold"] == 80
