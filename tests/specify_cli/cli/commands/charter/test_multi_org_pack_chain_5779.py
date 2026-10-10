"""#5779: ``charter context --include`` and ``charter activate`` see every org pack.

With two org packs configured, both commands used to resolve through org pack 1
only: an artifact defined only in pack 2 was "No directive found" /
"Unknown directive ID" (exit 1), and an id both packs define rendered pack 1's
body under ``--include`` while the bootstrap context (full chain, later wins)
used pack 2's.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

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
        f'schema_version: "1.0"\n'
        f"id: {directive_id}\n"
        f"title: Directive {directive_id}\n"
        f"intent: Intent of {directive_id}. {marker}\n"
        "enforcement: required\n",
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

        service = _build_offering_service(
            two_pack_project, org_roots=resolve_existing_org_roots(two_pack_project)
        )
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
    def test_colliding_id_is_validated_against_last_declared_pack(self, two_pack_project: Path) -> None:
        # Direct and cascade targets share one helper; the pack an id is
        # validated against must be the one that wins the chain (the last
        # declared), not the first that happens to accept it.
        from specify_cli.cli.commands.charter import activate as activate_mod

        seen_org_roots: list[Path] = []

        class _RecordingManager:
            def activate(self, ctx_project, kind_token, config_id, *, cascade, layer_roots):
                seen_org_roots.append(layer_roots["org"])
                return object()

        alpha, beta = two_pack_project / "packs" / "alpha", two_pack_project / "packs" / "beta"
        activate_mod._activate_cascade_target(
            cast("Any", _RecordingManager()),
            cast("Any", None),
            "directive",
            "shared_one",
            None,
            [alpha, beta],
            cascade=True,
        )
        assert seen_org_roots == [beta]
