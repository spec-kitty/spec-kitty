"""``spec-kitty charter pack validate|assemble|regenerate-graph`` (#3732, FR-006).

The pack tooling moved from the ``doctrine`` group to its charter home
(``charter/pack_tooling.py``). Every test here runs on the ``charter`` app and
carries a positive control on the same fixture. The handler-identity test pins
that the transitional ``doctrine`` group re-registers the very same function
objects, so deleting that group (WP16) removes registrations only.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from typer.testing import CliRunner

from specify_cli.cli.commands.charter import pack_tooling
from specify_cli.cli.commands.charter._app import charter_app

pytestmark = [pytest.mark.unit]

runner = CliRunner()

_BUILT_IN = Path(__file__).resolve().parents[5] / "packs" / "built-in"


def _scaffold_pack(tmp_path: Path, name: str = "pack") -> Path:
    """A valid org pack (org-charter, DRG fragment, example preset) via ``charter org init``."""
    target = tmp_path / name
    result = runner.invoke(charter_app, ["org", "init", str(target)])
    assert result.exit_code == 0, result.output
    return target


# --------------------------------------------------------------------------------------
# charter pack validate
# --------------------------------------------------------------------------------------


def test_pack_validate_accepts_a_valid_pack(tmp_path: Path) -> None:
    pack = _scaffold_pack(tmp_path)
    result = runner.invoke(charter_app, ["pack", "validate", str(pack)])
    assert result.exit_code == 0, result.output
    assert "Pack validation: 0 errors" in result.output


def test_pack_validate_names_a_broken_artifact_file(tmp_path: Path) -> None:
    pack = _scaffold_pack(tmp_path)
    assert runner.invoke(charter_app, ["pack", "validate", str(pack)]).exit_code == 0  # control
    broken = pack / "directives" / "broken.directive.yaml"
    broken.parent.mkdir(parents=True, exist_ok=True)
    broken.write_text("id: BROKEN\nnot_a_field: [\n", encoding="utf-8")
    result = runner.invoke(charter_app, ["pack", "validate", str(pack)])
    assert result.exit_code == 1, result.output
    assert "broken.directive.yaml" in "".join(result.output.split())


def test_pack_validate_names_a_malformed_preset(tmp_path: Path) -> None:
    pack = _scaffold_pack(tmp_path)
    assert runner.invoke(charter_app, ["pack", "validate", str(pack)]).exit_code == 0  # control
    (pack / "presets" / "bad.yaml").write_text("name: bad\ndescription: x\nunknown_key: 1\n", encoding="utf-8")
    result = runner.invoke(charter_app, ["pack", "validate", str(pack)])
    assert result.exit_code == 1, result.output
    assert "bad.yaml" in "".join(result.output.split())


def test_pack_validate_json_reports_ok(tmp_path: Path) -> None:
    pack = _scaffold_pack(tmp_path)
    result = runner.invoke(charter_app, ["pack", "validate", str(pack), "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert isinstance(payload, dict) and payload


# --------------------------------------------------------------------------------------
# charter pack assemble
# --------------------------------------------------------------------------------------


def test_pack_assemble_keeps_its_flags() -> None:
    result = runner.invoke(charter_app, ["pack", "assemble", "--help"])
    assert result.exit_code == 0, result.output
    for flag in ("--conflicts-out", "--force", "--json"):
        assert flag in result.output


def test_pack_assemble_writes_one_pack(tmp_path: Path) -> None:
    pack = _scaffold_pack(tmp_path)
    out = tmp_path / "assembled"
    result = runner.invoke(charter_app, ["pack", "assemble", str(out), str(pack)])
    assert result.exit_code == 0, result.output
    assert "Assembled 1 pack" in result.output
    assert out.is_dir()
    # Control: a missing input pack is refused on the same command.
    missing = runner.invoke(charter_app, ["pack", "assemble", str(tmp_path / "out2"), str(tmp_path / "nope")])
    assert missing.exit_code == 1, missing.output


# --------------------------------------------------------------------------------------
# charter pack regenerate-graph
# --------------------------------------------------------------------------------------


def test_built_in_pack_root_is_the_shipped_pack() -> None:
    assert pack_tooling._built_in_pack_root().resolve() == _BUILT_IN.resolve()


def test_regenerate_graph_check_is_fresh_on_the_repo() -> None:
    result = runner.invoke(charter_app, ["pack", "regenerate-graph", "--check", "--json"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["status"] == "fresh"


def test_regenerate_graph_check_reports_a_stale_fragment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    copy = tmp_path / "built-in"
    shutil.copytree(_BUILT_IN, copy)
    monkeypatch.setattr(pack_tooling, "_built_in_pack_root", lambda: copy)
    fresh = runner.invoke(charter_app, ["pack", "regenerate-graph", "--check"])
    assert fresh.exit_code == 0, fresh.output  # control: the copy starts fresh

    fragment = sorted(copy.glob("*.graph.yaml"))[0]
    fragment.write_text(fragment.read_text(encoding="utf-8") + "\n# planted drift\n", encoding="utf-8")
    stale = runner.invoke(charter_app, ["pack", "regenerate-graph", "--check"])
    assert stale.exit_code == 1, stale.output
    flat = " ".join(stale.output.split())
    assert "DRG graph is stale" in flat
    assert "spec-kitty charter pack regenerate-graph" in flat

    written = runner.invoke(charter_app, ["pack", "regenerate-graph", "--json"])
    assert written.exit_code == 0, written.output
    assert json.loads(written.output)["status"] == "written"
    assert runner.invoke(charter_app, ["pack", "regenerate-graph", "--check"]).exit_code == 0


# --------------------------------------------------------------------------------------
# Handler identity: the charter homes register the moved handler objects
# --------------------------------------------------------------------------------------


def _callbacks(app: object, group: str | None = None) -> dict[str, object]:
    import typer

    assert isinstance(app, typer.Typer)
    if group is not None:
        sub = next(g.typer_instance for g in app.registered_groups if g.name == group)
        return _callbacks(sub)
    return {str(c.name): c.callback for c in app.registered_commands}


def test_charter_homes_register_the_moved_handler_objects() -> None:
    from specify_cli.cli.commands.charter import authoring, org
    from specify_cli.cli.commands.charter.pack import charter_pack_app
    from specify_cli.cli.commands.charter.pack_asset import asset_app

    charter = _callbacks(charter_app)
    for name in ("fetch", "new", "validate"):
        assert charter[name] is getattr(authoring, name)
    pack = _callbacks(charter_pack_app)
    assert pack["regenerate-graph"] is pack_tooling.regenerate_graph
    assert pack["validate"] is pack_tooling.pack_validate
    assert pack["assemble"] is pack_tooling.pack_assemble
    assert _callbacks(charter_app, "org") == _callbacks(org.org_app)
    assert _callbacks(charter_pack_app, "asset") == _callbacks(asset_app)
