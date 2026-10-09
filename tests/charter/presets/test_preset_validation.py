"""``validate_pack`` validates presets; ``charter org validate`` surfaces it (FR-019, T038/T040)."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from charter.offering.pack_paths import built_in_root
from charter.offering.packs.pack_validator import ValidationIssue, validate_pack
from kernel.charter_pack_paths import pack_presets_dir

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_FRAGMENT = """\
pack_name: team-pack
source_kind: local_path
source_ref: .
layer_index: 1
provenance_marker: org
nodes: []
edges: []
"""

_OWN_TACTIC = """\
schema_version: "1.0"
id: team-only-tactic
name: Team only tactic
steps:
  - title: Do the thing
"""


def _pack(root: Path, presets: dict[str, str], *, own_tactic: bool = False) -> Path:
    (root / "drg").mkdir(parents=True)
    (root / "drg" / "fragment.yaml").write_text(_FRAGMENT, encoding="utf-8")
    if own_tactic:
        (root / "tactics").mkdir()
        (root / "tactics" / "team-only-tactic.tactic.yaml").write_text(_OWN_TACTIC, encoding="utf-8")
    presets_dir = pack_presets_dir(root)
    presets_dir.mkdir()
    for name, text in presets.items():
        (presets_dir / f"{name}.yaml").write_text(text, encoding="utf-8")
    return root


def _preset_issues(pack: Path) -> list[ValidationIssue]:
    result = validate_pack(pack, check_drg_root=False)
    return [issue for issue in result.errors + result.advisories if issue.artifact_type == "preset"]


_CLEAN = """\
name: clean
description: Resolves against built-in and this pack
mission_type_activations: [software-dev]
activated_directives: [010-specification-fidelity-requirement, DIRECTIVE_024]
activated_agent_profiles: [python-pedro]
activated_anti_patterns: [big-ball-of-mud]
activated_kinds: [directives, agent_profiles, anti_patterns]
"""


def test_clean_pack_has_no_preset_issues(tmp_path: Path) -> None:
    assert _preset_issues(_pack(tmp_path / "pack", {"clean": _CLEAN})) == []


def test_pack_own_ids_resolve(tmp_path: Path) -> None:
    pack = _pack(tmp_path / "pack", {"own": "name: own\ndescription: x\nactivated_tactics: [team-only-tactic]\n"}, own_tactic=True)
    assert _preset_issues(pack) == []


def test_three_errors_name_file_and_field_or_id(tmp_path: Path) -> None:
    pack = _pack(
        tmp_path / "pack",
        {
            "clean": _CLEAN,
            "bad": "name: bad\ndescription: x\nunknown_key: 1\n",
            "ghost": "name: ghost\ndescription: x\nactivated_tactics: [no-such-tactic]\nmission_type_activations: [no-such-type]\n",
            "gated": "name: gated\ndescription: x\nactivated_kinds: [directives]\nactivated_tactics: [acceptance-test-first]\n",
        },
    )
    issues = _preset_issues(pack)
    assert all(issue.severity == "error" for issue in issues)
    by_category: dict[tuple[str | None, str], list[str]] = {}
    for issue in issues:
        by_category.setdefault((issue.category, Path(issue.file).name), []).append(issue.message)
    assert set(by_category) == {
        ("preset_format", "bad.yaml"),
        ("preset_unresolved_id", "ghost.yaml"),
        ("preset_kind_gate", "gated.yaml"),
    }
    (format_message,) = by_category[("preset_format", "bad.yaml")]
    assert "unknown_key" in format_message
    ghost = by_category[("preset_unresolved_id", "ghost.yaml")]
    assert len(ghost) == 2
    assert any("no-such-tactic" in message for message in ghost)
    assert any("no-such-type" in message for message in ghost), "mission types resolve too"
    (gate_message,) = by_category[("preset_kind_gate", "gated.yaml")]
    assert "tactics" in gate_message
    assert not validate_pack(pack, check_drg_root=False).ok


def test_builtin_pack_reports_no_preset_issues() -> None:
    assert _preset_issues(built_in_root()) == []


def test_org_validate_surfaces_the_preset_error(tmp_path: Path) -> None:
    from specify_cli.cli.commands.charter._app import charter_app as app

    pack = _pack(tmp_path / "pack", {"ghost": "name: ghost\ndescription: x\nactivated_tactics: [no-such-tactic]\n"})
    result = CliRunner().invoke(app, ["org", "validate", str(pack)])
    assert result.exit_code == 1, result.output
    assert "ghost.yaml" in result.output and "no-such-tactic" in result.output
    clean = _pack(tmp_path / "clean", {"clean": _CLEAN})
    assert CliRunner().invoke(app, ["org", "validate", str(clean)]).exit_code == 0
