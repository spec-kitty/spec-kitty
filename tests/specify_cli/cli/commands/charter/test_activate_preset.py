"""``spec-kitty charter activate [--pack] --preset`` (FR-001, SC-001, contracts/cli.md; #3732 WP08).

Covers every row of the contracts/cli.md ``--preset`` outcome table, the
``--json`` shape, the flag rules (usage errors, exit 2, nothing written), the
SC-001 round trip read back through ``charter list --json`` and the US1 AS-2
drift case (an artifact added to a copied built-in pack after the preset was
written is effective).
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import pytest
from ruamel.yaml import YAML
from typer.testing import CliRunner

from charter.activation.pack_context import PackContext
from specify_cli.cli.commands.charter import activate as activate_module
from specify_cli.cli.commands.charter import charter_app

pytestmark = [pytest.mark.fast]

runner = CliRunner()

_REPO_ROOT = Path(__file__).resolve().parents[5]
_BUILT_IN = _REPO_ROOT / "packs" / "built-in"
_MINIMAL = YAML(typ="safe").load((_BUILT_IN / "presets" / "minimal.yaml").read_text(encoding="utf-8"))
ORG = "acme"
ORG_DIR = "org-packs/acme"


def _dump(path: Path, data: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    yaml = YAML()
    yaml.default_flow_style = False
    with path.open("w", encoding="utf-8") as fh:
        yaml.dump(data, fh)
    return path


def _load(path: Path) -> dict[str, Any]:
    data = YAML(typ="safe").load(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


@pytest.fixture()
def project_root(tmp_path: Path) -> Path:
    _dump(tmp_path / ".kittify" / "config.yaml", {"mission_type_activations": ["software-dev"]})
    return tmp_path


def _config(root: Path) -> Path:
    return root / ".kittify" / "config.yaml"


def _activate(root: Path, *args: str) -> Any:
    return runner.invoke(charter_app, ["activate", "--repo-root", str(root), *args], catch_exceptions=False)


def _listed(root: Path) -> dict[str, Any]:
    result = runner.invoke(charter_app, ["list", "--json", "--repo-root", str(root)], catch_exceptions=False)
    assert result.exit_code == 0, result.output
    return {row["kind"]: row["activated"] for row in json.loads(result.output)["kinds"]}


# ---------------------------------------------------------------------------
# Outcome table: applied (0)
# ---------------------------------------------------------------------------


def test_applied_text_lists_written_keys_and_target(project_root: Path) -> None:
    result = _activate(project_root, "--preset", "minimal", "--no-compile")

    assert result.exit_code == 0, result.output
    assert "Applied preset 'minimal' of pack 'built-in'" in result.output
    assert "Wrote activated_directives" in result.output
    assert _load(_config(project_root))["activated_tactics"] == _MINIMAL["activated_tactics"]


def test_applied_json_payload_shape(project_root: Path) -> None:
    result = _activate(project_root, "--preset", "minimal", "--json")

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert set(payload) == {"pack", "preset", "written", "removed", "target_file"}
    assert payload["pack"] == "built-in" and payload["preset"] == "minimal"
    assert payload["written"] == {"activated_directives": _MINIMAL["activated_directives"], "activated_tactics": _MINIMAL["activated_tactics"]}
    assert payload["removed"] == []
    assert payload["target_file"] == str(_config(project_root.resolve()))


def test_reapply_reports_nothing_changed(project_root: Path) -> None:
    assert _activate(project_root, "--preset", "minimal", "--no-compile").exit_code == 0
    before = _config(project_root).read_bytes()

    result = _activate(project_root, "--preset", "minimal", "--no-compile")

    assert result.exit_code == 0, result.output
    assert "already in force" in result.output
    assert _config(project_root).read_bytes() == before


def test_removed_keys_are_reported(project_root: Path) -> None:
    _dump(_config(project_root), {"mission_type_activations": ["software-dev"], "activated_kinds": ["directives"]})

    result = _activate(project_root, "--preset", "minimal", "--no-compile", "--force")

    assert result.exit_code == 0, result.output
    assert "Removed activated_kinds" in result.output


def test_resynthesize_runs_the_full_pipeline_after_the_write(project_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[Path] = []
    monkeypatch.setattr(activate_module, "run_full_synthesize", calls.append)

    result = _activate(project_root, "--preset", "minimal", "--resynthesize")

    assert result.exit_code == 0, result.output
    assert calls == [project_root.resolve()]
    assert "activated_directives" in _load(_config(project_root))


# ---------------------------------------------------------------------------
# Outcome table: refusals (1), nothing written
# ---------------------------------------------------------------------------


def test_unknown_pack_exit_1_lists_available_packs(project_root: Path) -> None:
    before = _config(project_root).read_bytes()

    result = _activate(project_root, "--pack", "nope", "--preset", "minimal")

    assert result.exit_code == 1
    assert "Error (PACK_NOT_FOUND)" in result.output and "built-in" in result.output
    assert _config(project_root).read_bytes() == before


def test_unknown_preset_exit_1_lists_the_pack_presets_json(project_root: Path) -> None:
    before = _config(project_root).read_bytes()

    result = _activate(project_root, "--preset", "nope", "--json")

    assert result.exit_code == 1
    error = json.loads(result.output)["error"]
    assert error["code"] == "PRESET_NOT_FOUND"
    assert error["pack"] == "built-in" and {"default", "minimal"} <= set(error["available"])
    assert _config(project_root).read_bytes() == before


def test_unresolvable_id_exit_1_names_file_and_id(project_root: Path) -> None:
    _dump(project_root / ORG_DIR / "presets" / "ghost.yaml", {"name": "ghost", "description": "x", "activated_tactics": ["no-such-tactic"]})
    _dump(_config(project_root), {"mission_type_activations": ["software-dev"], "charter_packs": {"org": {"packs": [{"name": ORG, "local_path": ORG_DIR}]}}})
    before = _config(project_root).read_bytes()

    result = _activate(project_root, "--pack", ORG, "--preset", "ghost")

    assert result.exit_code == 1
    assert "Error (PRESET_ID_UNRESOLVED)" in result.output
    assert "ghost.yaml" in result.output and "no-such-tactic" in result.output
    assert _config(project_root).read_bytes() == before


def test_customised_key_exit_1_prints_diff_then_force_applies(project_root: Path) -> None:
    _dump(_config(project_root), {"mission_type_activations": ["software-dev"], "activated_directives": ["024-locality-of-change"]})
    before = _config(project_root).read_bytes()

    refused = _activate(project_root, "--preset", "minimal", "--no-compile")

    assert refused.exit_code == 1
    assert "Error (PRESET_WOULD_OVERWRITE)" in refused.output
    assert "activated_directives: [024-locality-of-change] -> [" in refused.output
    assert "activated_tactics: absent -> [acceptance-test-first]" in refused.output
    assert _config(project_root).read_bytes() == before

    forced = _activate(project_root, "--preset", "minimal", "--no-compile", "--force")
    assert forced.exit_code == 0, forced.output
    assert _load(_config(project_root))["activated_directives"] == _MINIMAL["activated_directives"]


def test_invalid_pack_config_fails_closed(tmp_path: Path) -> None:
    _dump(_config(tmp_path), {"charter": ".kittify/charter/missing.yaml"})
    before = _config(tmp_path).read_bytes()

    result = _activate(tmp_path, "--preset", "minimal", "--json")

    assert result.exit_code == 1
    assert json.loads(result.output)["error"]["code"] == "ACTIVE_CHARTER_CONFIG_INVALID"
    assert _config(tmp_path).read_bytes() == before


def test_malformed_preset_file_fails_with_preset_invalid(project_root: Path) -> None:
    _dump(project_root / ORG_DIR / "presets" / "bad.yaml", {"name": "bad", "description": "x", "unknown_key": 1})
    _dump(_config(project_root), {"mission_type_activations": ["software-dev"], "charter_packs": {"org": {"packs": [{"name": ORG, "local_path": ORG_DIR}]}}})

    result = _activate(project_root, "--pack", ORG, "--preset", "bad")

    assert result.exit_code == 1
    assert "Error (PRESET_INVALID)" in result.output and "unknown_key" in result.output


# ---------------------------------------------------------------------------
# Flag rules: usage errors (2), before any I/O
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("args", "named"),
    [
        (("directive", "001-architectural-integrity-standard", "--preset", "minimal"), "--preset"),
        (("--preset", "minimal", "--cascade", "all"), "--cascade"),
        (("--pack", "built-in"), "--pack"),
        (("--force",), "--force"),
        (("--json",), "--json"),
        (("directive", "001-architectural-integrity-standard", "--json"), "--json"),
    ],
    ids=["positional", "cascade", "explicit-default-pack", "force", "json", "json-on-positional-path"],
)
def test_flag_combination_is_a_usage_error(project_root: Path, args: tuple[str, ...], named: str) -> None:
    before = _config(project_root).read_bytes()

    result = _activate(project_root, *args)

    assert result.exit_code == 2, result.output
    assert named in result.output
    assert "No such option" not in result.output
    assert _config(project_root).read_bytes() == before


def test_help_shows_both_forms() -> None:
    result = runner.invoke(charter_app, ["activate", "--help"], catch_exceptions=False)

    assert result.exit_code == 0
    assert "--preset" in result.output and "--pack" in result.output


# ---------------------------------------------------------------------------
# SC-001 round trip and US1 AS-2 drift
# ---------------------------------------------------------------------------


def test_sc001_minimal_default_minimal_round_trip_matches_charter_list(project_root: Path) -> None:
    assert _activate(project_root, "--preset", "minimal", "--no-compile").exit_code == 0
    listed = _listed(project_root)
    assert sorted(listed["directive"]) == sorted(_MINIMAL["activated_directives"])
    assert listed["tactic"] == _MINIMAL["activated_tactics"]

    assert _activate(project_root, "--preset", "default", "--force", "--no-compile").exit_code == 0
    config = _load(_config(project_root))
    assert not [key for key in config if key.startswith("activated_")]
    listed = _listed(project_root)
    assert listed["directive"] is None and listed["tactic"] is None

    assert _activate(project_root, "--preset", "minimal", "--force", "--no-compile").exit_code == 0
    assert sorted(_listed(project_root)["directive"]) == sorted(_MINIMAL["activated_directives"])


def test_us1_as2_drift_artifact_is_effective_after_default(project_root: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    packs_root = tmp_path / "packs-root"
    shutil.copytree(_BUILT_IN, packs_root / "built-in")
    monkeypatch.setenv("SPEC_KITTY_PACKS_ROOT", str(packs_root))
    assert _activate(project_root, "--preset", "minimal", "--no-compile").exit_code == 0

    result = _activate(project_root, "--preset", "default", "--force", "--no-compile")
    assert result.exit_code == 0, result.output
    _dump(
        packs_root / "built-in" / "directives" / "999-drift-directive.directive.yaml",
        {"schema_version": "1.0", "id": "DIRECTIVE_999", "title": "Drift", "intent": "Added after the preset.", "enforcement": "advisory"},
    )

    assert PackContext.from_config(project_root).activated_directives is None, "absent key: unrestricted"
    from charter.activation.doctrine_service_builder import build_activation_aware_doctrine_service

    effective = build_activation_aware_doctrine_service(project_root).directives
    assert "DIRECTIVE_999" in effective, "the directive added after the preset was written is effective"


# ---------------------------------------------------------------------------
# Review cycle 1
# ---------------------------------------------------------------------------


def test_missing_declared_org_root_refuses_and_writes_nothing(project_root: Path) -> None:
    _dump(
        _config(project_root),
        {"mission_type_activations": ["software-dev"], "charter_packs": {"org": {"packs": [{"name": "ghost", "local_path": "org-packs/ghost"}]}}},
    )
    before = _config(project_root).read_bytes()

    result = _activate(project_root, "--preset", "minimal", "--json")

    assert result.exit_code == 1, result.output
    error = json.loads(result.output)["error"]
    assert error["code"] == "PRESET_ID_UNRESOLVED"
    assert "not a directory" in json.dumps(error["reasons"])
    assert _config(project_root).read_bytes() == before


def test_json_resynthesize_failure_emits_json_error(project_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import typer

    def fail(_root: Path) -> None:
        raise typer.Exit(1)

    monkeypatch.setattr(activate_module, "run_full_synthesize", fail)

    result = _activate(project_root, "--preset", "minimal", "--resynthesize", "--json")

    assert result.exit_code == 1
    error = json.loads(result.output)["error"]
    assert error["code"] == "RESYNTHESIS_FAILED"
    assert "applied" in error["message"] and error["preset"] == "minimal"
    assert "activated_directives" in _load(_config(project_root)), "the preset write stands"


def test_positional_activate_resolves_the_default_repo_root_per_invocation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import subprocess

    roots = []
    for name in ("one", "two"):
        root = tmp_path / name
        _dump(root / ".kittify" / "config.yaml", {"mission_type_activations": ["software-dev"]})
        subprocess.run(["git", "init", "-q", str(root)], check=True)
        roots.append(root)

    for root in roots:
        monkeypatch.chdir(root)
        result = runner.invoke(charter_app, ["activate", "directive", "001-architectural-integrity-standard", "--no-compile"], catch_exceptions=False)
        assert result.exit_code == 0, result.output

    for root in roots:
        assert "001-architectural-integrity-standard" in _load(_config(root)).get("activated_directives", []), root
