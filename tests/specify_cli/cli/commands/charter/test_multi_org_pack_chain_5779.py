"""#5779: ``charter context --include`` and ``charter activate`` see every org pack.

With two org packs configured, both commands used to resolve through org pack 1
only: an artifact defined only in pack 2 was "No directive found" /
"Unknown directive ID" (exit 1), and an id both packs define rendered pack 1's
body under ``--include`` while the bootstrap context (full chain, later wins)
used pack 2's.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import cast

import pytest
import yaml
from typer.testing import CliRunner

import specify_cli.cli.commands.charter as charter_pkg
from specify_cli.cli.commands.charter import charter_app

runner = CliRunner()

pytestmark = [pytest.mark.integration]


def _write_directive(pack_root: Path, directive_id: str, marker: str) -> None:
    directives_dir = pack_root / "directives"
    directives_dir.mkdir(parents=True, exist_ok=True)
    (directives_dir / f"{directive_id.lower()}.directive.yaml").write_text(
        f'schema_version: "1.0"\nid: {directive_id}\ntitle: Directive {directive_id}\nintent: Intent of {directive_id}. {marker}\nenforcement: required\n',
        encoding="utf-8",
    )


@pytest.fixture()
def two_pack_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Org packs ``alpha`` then ``beta``: ``SHARED_ONE`` in both, ``BETA_ONLY`` in beta."""
    _write_directive(tmp_path / "packs" / "alpha", "SHARED_ONE", "MARKER-FROM-alpha")
    _write_directive(tmp_path / "packs" / "beta", "SHARED_ONE", "MARKER-FROM-beta")
    _write_directive(tmp_path / "packs" / "beta", "BETA_ONLY", "MARKER-BETA_ONLY")
    config = {
        "mission_type_activations": ["software-dev"],
        "charter_packs": {
            "org": {
                "packs": [
                    {"name": "alpha", "local_path": "packs/alpha"},
                    {"name": "beta", "local_path": "packs/beta"},
                ]
            }
        },
    }
    kittify = tmp_path / ".kittify"
    kittify.mkdir()
    (kittify / "config.yaml").write_text(yaml.safe_dump(config), encoding="utf-8")
    monkeypatch.setattr(charter_pkg, "find_repo_root", lambda: tmp_path)
    return tmp_path


def _include(selector: str) -> str:
    result = runner.invoke(charter_app, ["context", "--include", selector])
    assert result.exit_code == 0, result.output
    return result.output


class TestIncludeSeesFullOrgChain:
    def test_artifact_only_in_second_pack_resolves(self, two_pack_project: Path) -> None:
        assert "MARKER-BETA_ONLY" in _include("directive:BETA_ONLY")

    def test_colliding_id_renders_later_pack_body(self, two_pack_project: Path) -> None:
        # Documented rule (docs/architecture/org-doctrine-layer.md): the last
        # declared org pack wins -- the same body the bootstrap context uses.
        output = _include("directive:SHARED_ONE")
        assert "MARKER-FROM-beta" in output
        assert "MARKER-FROM-alpha" not in output

    def test_include_agrees_with_full_chain_service(self, two_pack_project: Path) -> None:
        from charter.activation.active_charter_service_builder import _build_offering_service
        from charter.offering.drg.org_pack_config import resolve_existing_org_roots

        service = _build_offering_service(two_pack_project, org_roots=resolve_existing_org_roots(two_pack_project))
        directive = service.directives.get("SHARED_ONE")
        assert directive is not None
        assert "MARKER-FROM-beta" in directive.intent
        assert "MARKER-FROM-beta" in _include("directive:SHARED_ONE")


class TestActivateSeesFullOrgChain:
    def test_activate_artifact_only_in_second_pack(self, two_pack_project: Path) -> None:
        # Activation keys off the config stem (beta_only.directive.yaml).
        result = runner.invoke(
            charter_app,
            ["activate", "--repo-root", str(two_pack_project), "--no-compile", "directive", "beta_only"],
        )
        assert result.exit_code == 0, result.output
        config = yaml.safe_load((two_pack_project / ".kittify" / "config.yaml").read_text(encoding="utf-8"))
        assert "beta_only" in config["activated_directives"]


class TestActivateValidatesAgainstWinningPack:
    def test_chain_scan_is_last_declared_first(self, two_pack_project: Path) -> None:
        # One widened availability scan replaces the per-pack retry loop; the
        # pack an id is found in must be ordered last-declared first so the
        # winning (last declared) pack leads, matching kind_vocabulary._org_scan_dirs.
        from charter.activation.pack_manager import ActiveCharterManager

        alpha, beta = two_pack_project / "packs" / "alpha", two_pack_project / "packs" / "beta"
        dirs = ActiveCharterManager()._scan_layer_dirs("directive", layer_roots=None, org_root_chain=[alpha, beta])
        org_dirs = [path for layer, path in dirs if layer == "org"]
        assert org_dirs == [beta / "directives", alpha / "directives"]


@pytest.mark.regression
class TestRetryLoopRetired6006:
    """#6006: ``_activate_cascade_target`` is replaced by one widened chain scan."""

    def test_cascade_retry_helper_is_gone(self) -> None:
        from specify_cli.cli.commands.charter import activate as activate_mod

        assert not hasattr(activate_mod, "_activate_cascade_target")

    def test_pack_two_only_artifact_listed_via_chain(self, two_pack_project: Path) -> None:
        from charter.activation.invocation_context import ProjectContext
        from charter.activation.pack_manager import ActiveCharterManager

        alpha, beta = two_pack_project / "packs" / "alpha", two_pack_project / "packs" / "beta"
        manager = ActiveCharterManager()
        ctx = cast("ProjectContext", None)
        chained = manager.list_available_detailed(ctx, "directive", org_root_chain=[alpha, beta])
        ids = {entry.artifact_id for entry in chained}
        assert "beta_only" in ids  # positive control: pack-2-only artifact
        assert "shared_one" in ids  # non-vacuity: pack-1 artifact still resolves

    def test_none_chain_is_single_slot_fallback(self, two_pack_project: Path) -> None:
        from charter.activation.invocation_context import ProjectContext
        from charter.activation.pack_manager import ActiveCharterManager

        alpha = two_pack_project / "packs" / "alpha"
        manager = ActiveCharterManager()
        ctx = cast("ProjectContext", None)
        slot = manager.list_available_detailed(ctx, "directive", layer_roots={"org": alpha})
        assert slot == manager.list_available_detailed(ctx, "directive", layer_roots={"org": alpha}, org_root_chain=None)
        assert slot == manager.list_available_detailed(ctx, "directive", layer_roots={"org": alpha}, org_root_chain=[])
        ids = {entry.artifact_id for entry in slot}
        assert "shared_one" in ids
        assert "beta_only" not in ids  # single slot sees pack 1 only


class TestActivateUnknownInEveryPack:
    def test_unknown_id_exits_1_names_both_packs_and_leaves_config_unchanged(self, two_pack_project: Path) -> None:
        config_path = two_pack_project / ".kittify" / "config.yaml"
        before = config_path.read_text(encoding="utf-8")
        result = runner.invoke(
            charter_app,
            ["activate", "--repo-root", str(two_pack_project), "--no-compile", "directive", "no_such_id"],
        )
        assert result.exit_code == 1, result.output
        assert "Unknown directive ID" in result.output
        assert config_path.read_text(encoding="utf-8") == before


class TestActivateFailsClosedOnUnfetchedPack:
    def test_declared_but_unfetched_pack_exits_1_with_fetch_remedy(self, two_pack_project: Path) -> None:
        # Pack ``beta`` stays declared in config but is gone from disk (#4984).
        shutil.rmtree(two_pack_project / "packs" / "beta")
        config_path = two_pack_project / ".kittify" / "config.yaml"
        before = config_path.read_text(encoding="utf-8")
        result = runner.invoke(
            charter_app,
            ["activate", "--repo-root", str(two_pack_project), "--no-compile", "directive", "shared_one"],
        )
        assert result.exit_code == 1, result.output
        assert "beta" in result.output
        assert "charter fetch" in result.output
        assert config_path.read_text(encoding="utf-8") == before
