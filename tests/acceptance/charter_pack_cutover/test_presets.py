"""Activation presets: FR-001..FR-004, FR-019, US1, SC-001, OD-6 (#3732, T004).

Presets are pack data applied with replace semantics. Every FR-001/FR-004 test
reads the result back through ``charter list --json`` and through the independent
``active_charter`` reader; no test compares the ``default`` preset to an id list.
"""

from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any

import pytest

from ._effective_set import builtin_inventory, effective_set, expand
from ._requirements import REPO_ROOT
from ._support import active_charter, activation_store, covers, describe, load_yaml, output_of, pending_until, read_json_output, run_cli, tree_digest
from .conftest import build_migrated_project
from .legacy_fixtures import (
    ORG_DIRECTIVE_ID,
    ORG_PACK_DIR,
    ORG_PACK_NAME,
    ORG_TACTIC_ID,
    finish,
    project_from_template,
    write_doctrine_pack,
    write_org_tactic,
    write_yaml,
)

BUILTIN_PRESETS = REPO_ROOT / "packs" / "built-in" / "presets"
UNGOVERNED_KEYS = ("activated_skills", "activated_glossary_packs")
PRESET_META_KEYS = ("name", "description")


def preset_governed(path: Path) -> dict[str, Any]:
    """The keys a preset file governs (everything but its name and description)."""
    data = load_yaml(path)
    assert isinstance(data, dict), f"{path} is not a mapping"
    return {k: v for k, v in data.items() if k not in PRESET_META_KEYS}


def list_kind(key: str) -> str:
    """``charter list --json`` kind token of an activation key."""
    if key == "mission_type_activations":
        return "mission-type"
    plural = key.removeprefix("activated_")
    singular = plural[:-1] if plural.endswith("s") else plural
    return singular.replace("_", "-")


def listed_activations(project: Path) -> dict[str, list[str] | None]:
    result = run_cli(["charter", "list", "--json"], project)
    assert result.exit_code == 0, describe(result)
    rows = read_json_output(result)["kinds"]
    return {row["kind"]: (sorted(row["activated"]) if isinstance(row["activated"], list) else None) for row in rows}


def assert_list_agrees(project: Path, governed: dict[str, Any]) -> None:
    listed = listed_activations(project)
    for key, ids in governed.items():
        if key == "activated_kinds":
            continue
        assert listed.get(list_kind(key)) == sorted(ids), (key, listed.get(list_kind(key)))


def activate_preset(project: Path, *extra: str) -> Any:
    return run_cli(["charter", "activate", *extra], project)


# --------------------------------------------------------------------------------------
# FR-001 / US1 / SC-001
# --------------------------------------------------------------------------------------


@covers("FR-001", "US1-1", "SC-001")
@pytest.mark.integration
def test_fr001_activate_minimal_preset_writes_governed_keys(migrated_project: Path) -> None:
    expected = preset_governed(BUILTIN_PRESETS / "minimal.yaml")
    before = active_charter(migrated_project)
    assert {k: before.get(k) for k in expected} != expected, "fixture already equals the preset: the test could not observe the write"
    result = activate_preset(migrated_project, "--preset", "minimal")
    assert result.exit_code == 0, describe(result)
    after = active_charter(migrated_project)
    assert {k: after.get(k) for k in expected} == expected
    assert_list_agrees(migrated_project, expected)


@covers("FR-001", "FR-002", "US1-2", "SC-001")
@pytest.mark.integration
def test_fr001_default_preset_removes_every_governed_key(tmp_path: Path, copied_builtin_pack: Path) -> None:
    project = project_from_template("migrated", tmp_path / "p", build_migrated_project)
    first = activate_preset(project, "--preset", "minimal")
    assert first.exit_code == 0, describe(first)
    assert any(k.startswith("activated_") for k in active_charter(project)), "minimal wrote no key: nothing to remove"
    result = activate_preset(project, "--preset", "default", "--force")
    assert result.exit_code == 0, describe(result)
    charter = active_charter(project)
    leftover = sorted(k for k in charter if k.startswith("activated_") and k not in UNGOVERNED_KEYS)
    assert leftover == [], f"governed keys left behind: {leftover}"
    preset = preset_governed(copied_builtin_pack / "presets" / "default.yaml")
    assert charter.get("mission_type_activations") == preset["mission_type_activations"]
    listed = listed_activations(project)
    assert all(listed[list_kind(f"activated_{k}")] is None for k in ("directives", "tactics", "styleguides", "procedures"))
    # Drift: an artifact added to the copied built-in pack after the preset was written is effective.
    write_org_tactic(copied_builtin_pack, "zz-synthetic-drift-tactic")
    inventory = builtin_inventory()
    assert "zz-synthetic-drift-tactic" in inventory["tactics"], "control: the copied built-in pack is the one read"
    assert "zz-synthetic-drift-tactic" in expand(effective_set(project, inventory), inventory)["tactics"]


@covers("FR-001", "FR-002")
@pytest.mark.integration
def test_fr001_fixture_preset_listing_one_id_writes_that_id(tmp_path: Path, copied_builtin_pack: Path) -> None:
    preset = copied_builtin_pack / "presets" / "default.yaml"
    data = preset_governed(preset)
    write_yaml(preset, {"name": "default", "description": "fixture", **data, "activated_directives": ["001-architectural-integrity-standard"]})
    project = project_from_template("migrated", tmp_path / "p", build_migrated_project)
    result = activate_preset(project, "--preset", "default", "--force")
    assert result.exit_code == 0, describe(result)
    assert active_charter(project)["activated_directives"] == ["001-architectural-integrity-standard"]
    assert listed_activations(project)["directive"] == ["001-architectural-integrity-standard"]


def _org_preset_project(project: Path) -> Path:
    from .legacy_fixtures import build_two_org_packs

    build_two_org_packs(project)
    pack = project / ORG_PACK_DIR
    write_yaml(
        pack / "presets" / "team.yaml",
        {
            "name": "team",
            "description": "Team starting point",
            "activated_directives": ["001-architectural-integrity-standard", ORG_DIRECTIVE_ID],
            "activated_tactics": ["acceptance-test-first"],
        },
    )
    write_yaml(pack / "org-charter.yaml", {"schema_version": "2", "org_name": "acme", "required_tactics": [ORG_TACTIC_ID]})
    finish(project, load_yaml(project / ".kittify" / "config.yaml"))
    return project


@covers("FR-001", "FR-004", "US1-3", "EC:Preset id resolution")
@pytest.mark.integration
def test_fr001_org_pack_preset_unioned_with_required(tmp_path: Path) -> None:
    project = _org_preset_project(tmp_path / "p")
    result = activate_preset(project, "--pack", ORG_PACK_NAME, "--preset", "team")
    assert result.exit_code == 0, describe(result)
    charter: dict[str, Any] = active_charter(project)
    assert sorted(charter["activated_directives"]) == sorted(["001-architectural-integrity-standard", ORG_DIRECTIVE_ID])
    assert sorted(charter["activated_tactics"]) == sorted(["acceptance-test-first", ORG_TACTIC_ID])
    assert_list_agrees(project, {"activated_tactics": charter["activated_tactics"]})


@covers("FR-001", "US1-4")
@pytest.mark.integration
def test_fr001_unknown_preset_names_pack_and_lists_presets(migrated_project: Path) -> None:
    before = tree_digest(migrated_project)
    result = activate_preset(migrated_project, "--preset", "does-not-exist")
    assert result.exit_code == 1, describe(result)
    text = output_of(result)
    assert "PRESET_NOT_FOUND" in text and "built-in" in text, describe(result)
    assert "minimal" in text and "default" in text, describe(result)
    assert tree_digest(migrated_project) == before
    # Control: a known preset applies on the same fixture.
    assert activate_preset(migrated_project, "--preset", "minimal").exit_code == 0


@covers("FR-001", "EC:Preset id resolution")
@pytest.mark.integration
def test_fr001_unresolvable_preset_id_writes_nothing(tmp_path: Path, copied_builtin_pack: Path) -> None:
    write_yaml(copied_builtin_pack / "presets" / "ghost.yaml", {"name": "ghost", "description": "x", "activated_tactics": ["no-such-tactic-anywhere"]})
    project = project_from_template("migrated", tmp_path / "p", build_migrated_project)
    before = tree_digest(project)
    result = activate_preset(project, "--preset", "ghost")
    assert result.exit_code == 1, describe(result)
    assert "PRESET_ID_UNRESOLVED" in output_of(result) and "no-such-tactic-anywhere" in output_of(result), describe(result)
    assert tree_digest(project) == before
    assert activate_preset(project, "--preset", "minimal").exit_code == 0  # control


@covers("FR-001", "US1-5", "OD-6")
@pytest.mark.integration
def test_fr001_customised_list_refused_without_force(tmp_path: Path) -> None:
    project = project_from_template("migrated", tmp_path / "p", build_migrated_project)
    config = load_yaml(project / ".kittify" / "config.yaml")
    config["activated_directives"] = ["024-locality-of-change"]
    finish(project, config)
    before = tree_digest(project)
    refused = activate_preset(project, "--preset", "minimal")
    assert refused.exit_code == 1, describe(refused)
    assert "PRESET_WOULD_OVERWRITE" in output_of(refused) and "activated_directives" in output_of(refused), describe(refused)
    assert tree_digest(project) == before
    forced = activate_preset(project, "--preset", "minimal", "--force")
    assert forced.exit_code == 0, describe(forced)
    assert active_charter(project)["activated_directives"] != ["024-locality-of-change"]


@covers("FR-001")
@pytest.mark.integration
def test_fr001_preset_with_positional_kind_exits_2(migrated_project: Path) -> None:
    """Regression guard (passes at base): ``--preset`` with a positional kind is a usage error."""
    before = tree_digest(migrated_project)
    result = activate_preset(migrated_project, "directive", "001-architectural-integrity-standard", "--preset", "minimal")
    assert result.exit_code == 2, describe(result)
    assert tree_digest(migrated_project) == before


def _shape_activate(project: Path) -> dict[str, Any]:
    result = activate_preset(project, "--preset", "minimal", "--json")
    assert result.exit_code == 0, describe(result)
    payload = read_json_output(result)
    assert set(payload) == {"pack", "preset", "written", "removed", "target_file"}
    assert isinstance(payload["pack"], str) and isinstance(payload["preset"], str) and isinstance(payload["target_file"], str)
    assert isinstance(payload["written"], dict) and all(isinstance(v, list) for v in payload["written"].values())
    assert isinstance(payload["removed"], list)
    assert isinstance(payload, dict)
    return payload


def _shape_pack_list(project: Path) -> dict[str, Any]:
    result = run_cli(["charter", "pack", "list", "--json"], project)
    assert result.exit_code == 0, describe(result)
    payload = read_json_output(result)
    assert set(payload) == {"packs"}
    for row in payload["packs"]:
        assert set(row) == {"name", "tier", "root", "presets"}
        assert row["tier"] in {"built-in", "org", "project"}
        assert all(set(p) == {"name", "description", "path"} for p in row["presets"])
    org_rows = [r["name"] for r in payload["packs"] if r["tier"] == "org"]
    assert len(org_rows) == 2, org_rows  # control: both org packs of the fixture are listed
    assert isinstance(payload, dict)
    return payload


def _shape_pack_path(project: Path) -> dict[str, Any]:
    result = run_cli(["charter", "pack", "path", "built-in", "--preset", "minimal", "--json"], project)
    assert result.exit_code == 0, describe(result)
    payload = read_json_output(result)
    assert set(payload) == {"pack", "path", "preset"}
    assert Path(payload["path"]).name == "minimal.yaml"
    assert isinstance(payload, dict)
    return payload


_SHAPES = {"activate": _shape_activate, "pack_list": _shape_pack_list, "pack_path": _shape_pack_path}


@covers("FR-001", "FR-004")
@pytest.mark.integration
@pytest.mark.parametrize("shape", list(_SHAPES))
def test_fr001_json_shapes(shape: str, two_org_packs: Path) -> None:
    _SHAPES[shape](two_org_packs)


@covers("OD-6", "FR-001")
@pytest.mark.integration
def test_od6_preset_name_not_persisted(migrated_project: Path) -> None:
    config_path = migrated_project / ".kittify" / "config.yaml"
    keys_before = set(load_yaml(config_path))
    result = activate_preset(migrated_project, "--preset", "minimal")
    assert result.exit_code == 0, describe(result)
    changed = active_charter(migrated_project)
    assert changed, "control: the governed keys changed"
    for store in {config_path, activation_store(migrated_project)}:
        data = load_yaml(store)
        added = set(data) - keys_before
        assert all(k.startswith("activated_") or k == "mission_type_activations" for k in added), added
        non_governed = {k: v for k, v in data.items() if not (k.startswith("activated_") or k == "mission_type_activations")}
        assert "minimal" not in repr(non_governed)


# --------------------------------------------------------------------------------------
# FR-002: built-in presets are pack data
# --------------------------------------------------------------------------------------


@covers("FR-002")
@pytest.mark.corpus
def test_fr002_builtin_presets_are_pack_data() -> None:
    default = load_yaml(BUILTIN_PRESETS / "default.yaml")
    minimal = load_yaml(BUILTIN_PRESETS / "minimal.yaml")
    assert not [k for k in default if k.startswith("activated_")], "default lists artifact ids"
    assert set(default["mission_type_activations"]) >= {"software-dev", "documentation", "research", "plan"}
    listed_kinds = {k.removeprefix("activated_") for k in minimal if k.startswith("activated_") and k != "activated_kinds"}
    if "activated_kinds" in minimal:
        assert listed_kinds <= set(minimal["activated_kinds"])
    assert minimal.get("activated_kinds") != ["directives", "tactics"], "the released minimal kind gate was a defect"


@covers("FR-002")
@pytest.mark.integration
def test_fr002_deleting_preset_file_fails_activation(tmp_path: Path, copied_builtin_pack: Path) -> None:
    project = project_from_template("migrated", tmp_path / "p", build_migrated_project)
    assert activate_preset(project, "--preset", "minimal").exit_code == 0  # control: the intact copy works
    (copied_builtin_pack / "presets" / "minimal.yaml").unlink()
    result = activate_preset(project, "--preset", "minimal", "--force")
    assert result.exit_code == 1, describe(result)
    assert "minimal" in output_of(result)


# --------------------------------------------------------------------------------------
# FR-003: init equals the default preset
# --------------------------------------------------------------------------------------


def _init(parent: Path, name: str) -> Path:
    parent.mkdir(parents=True, exist_ok=True)
    result = run_cli(["init", name, "--ai", "claude", "--non-interactive"], parent)
    assert result.exit_code == 0, describe(result)
    return parent / name


@covers("FR-003", "SC-001")
@pytest.mark.integration
def test_fr003_init_without_activation_equals_default_preset(tmp_path: Path) -> None:
    initialised = _init(tmp_path, "plain")
    second = _init(tmp_path, "preset")
    result = activate_preset(second, "--preset", "default")
    assert result.exit_code == 0, describe(result)
    assert active_charter(initialised) == active_charter(second)
    assert active_charter(initialised).get("mission_type_activations"), "control: init wrote mission types"


@covers("FR-003")
@pytest.mark.integration
@pending_until("WP09", "init fails closed when the default preset is missing")
def test_fr003_default_preset_missing_fails_closed(tmp_path: Path, copied_builtin_pack: Path) -> None:
    intact = _init(tmp_path / "intact", "p")
    assert active_charter(intact).get("mission_type_activations"), "control: the intact copied pack provisions"
    (copied_builtin_pack / "presets" / "default.yaml").unlink()
    (tmp_path / "broken").mkdir()
    result = run_cli(["init", "p", "--ai", "claude", "--non-interactive"], tmp_path / "broken")
    assert result.exit_code == 1, describe(result)
    assert "DEFAULT_PRESET_MISSING" in output_of(result), describe(result)
    config = tmp_path / "broken" / "p" / ".kittify" / "config.yaml"
    assert not config.exists() or "mission_type_activations" not in (load_yaml(config) or {})


@covers("FR-003")
@pytest.mark.integration
@pending_until("WP09", "init reads the default preset's mission types")
def test_fr003_copied_pack_default_preset_drives_init(tmp_path: Path, copied_builtin_pack: Path) -> None:
    write_yaml(copied_builtin_pack / "presets" / "default.yaml", {"name": "default", "description": "fixture", "mission_type_activations": ["software-dev"]})
    project = _init(tmp_path, "p")
    assert active_charter(project)["mission_type_activations"] == ["software-dev"]


# --------------------------------------------------------------------------------------
# FR-004: presets from any pack, listed by `charter pack list`
# --------------------------------------------------------------------------------------


@covers("FR-004", "US3-3", "EC:Pack without presets")
@pytest.mark.integration
def test_fr004_pack_list_shows_packs_presets_and_project(tmp_path: Path) -> None:
    project = _org_preset_project(tmp_path / "p")
    result = run_cli(["charter", "pack", "list", "--json"], project)
    assert result.exit_code == 0, describe(result)
    rows = {row["name"]: row for row in read_json_output(result)["packs"]}
    assert {p["name"] for p in rows["built-in"]["presets"]} >= {"default", "minimal"}
    assert [p["name"] for p in rows[ORG_PACK_NAME]["presets"]] == ["team"]
    assert rows["acme-two"]["presets"] == [], "negative control: a pack without presets lists none"
    assert rows["project"]["presets"] == [] and rows["project"]["tier"] == "project"


# --------------------------------------------------------------------------------------
# FR-019: preset format, validated and scaffolded
# --------------------------------------------------------------------------------------


def _pack_with_presets(root: Path, presets: dict[str, dict[str, Any]]) -> Path:
    pack = write_doctrine_pack(root)
    for name, body in presets.items():
        write_yaml(pack / "presets" / f"{name}.yaml", body)
    return pack


VALID_PRESET = {"name": "valid", "description": "A valid preset", "activated_tactics": ["acceptance-test-first"]}


@covers("FR-019")
@pytest.mark.integration
@pending_until("WP15", "`charter pack validate` validates presets")
def test_fr019_validate_names_malformed_file_and_unresolved_id(tmp_path: Path) -> None:
    good = _pack_with_presets(tmp_path / "good", {"valid": VALID_PRESET})
    ok = run_cli(["charter", "pack", "validate", str(good)], tmp_path)
    assert ok.exit_code == 0, describe(ok)
    bad = _pack_with_presets(
        tmp_path / "bad",
        {
            "valid": VALID_PRESET,
            "bad": {"name": "bad", "description": "x", "unknown_key": 1},
            "ghost": {"name": "ghost", "description": "x", "activated_tactics": ["no-such-tactic"]},
        },
    )
    refused = run_cli(["charter", "pack", "validate", str(bad)], tmp_path)
    assert refused.exit_code != 0, describe(refused)
    text = output_of(refused)
    assert "bad.yaml" in text and "ghost.yaml" in text and "no-such-tactic" in text, describe(refused)


#: case -> (file stem, preset body). Each case breaks exactly one rule: the stem equals the
#: ``name`` everywhere except ``name_not_stem``, so ``name_grammar`` is refused only by the
#: name grammar, never by the name == stem rule.
MALFORMED_PRESETS: dict[str, tuple[str, dict[str, Any]]] = {
    "name_grammar": ("Bad_Name", {"name": "Bad_Name", "description": "x"}),
    "name_not_stem": ("name-not-stem", {"name": "other", "description": "x"}),
    "kinds_omit_listed": (
        "kinds-omit-listed",
        {"name": "kinds-omit-listed", "description": "x", "activated_kinds": ["directives"], "activated_tactics": ["acceptance-test-first"]},
    ),
    "context_scoped": (
        "context-scoped",
        {"name": "context-scoped", "description": "x", "activations": [{"activation_context": {}, "artifact_id": "x"}]},
    ),
    "skills_key": ("skills-key", {"name": "skills-key", "description": "x", "activated_skills": ["x"]}),
}


@covers("FR-019")
@pytest.mark.integration
@pytest.mark.parametrize("case", [pytest.param(c, marks=pending_until("WP15", "malformed preset named by `charter pack validate`")) for c in MALFORMED_PRESETS])
def test_fr019_malformed_preset_cases(case: str, tmp_path: Path) -> None:
    file_stem, body = MALFORMED_PRESETS[case]
    assert (body["name"] == file_stem) is (case != "name_not_stem"), "each case breaks exactly one rule"
    good = _pack_with_presets(tmp_path / "good", {"valid": VALID_PRESET})
    assert run_cli(["charter", "pack", "validate", str(good)], tmp_path).exit_code == 0  # control
    bad = _pack_with_presets(tmp_path / "bad", {"valid": VALID_PRESET, file_stem: dict(body)})
    refused = run_cli(["charter", "pack", "validate", str(bad)], tmp_path)
    assert refused.exit_code != 0, describe(refused)
    assert f"{file_stem}.yaml" in output_of(refused), describe(refused)


@covers("FR-019")
@pytest.mark.integration
def test_fr019_org_validate_validates_presets(tmp_path: Path) -> None:
    good = _pack_with_presets(tmp_path / "good", {"valid": VALID_PRESET})
    assert run_cli(["charter", "org", "validate", str(good)], tmp_path).exit_code == 0
    bad = _pack_with_presets(tmp_path / "bad", {"bad": {"name": "bad", "description": "x", "unknown_key": 1}})
    refused = run_cli(["charter", "org", "validate", str(bad)], tmp_path)
    assert refused.exit_code != 0 and "bad.yaml" in output_of(refused), describe(refused)


@covers("FR-019")
@pytest.mark.integration
def test_fr019_org_init_scaffolds_example_preset(tmp_path: Path) -> None:
    result = run_cli(["charter", "org", "init", "scaffold"], tmp_path)
    assert result.exit_code == 0, describe(result)
    presets = sorted((tmp_path / "scaffold" / "presets").glob("*.yaml"))
    assert presets, "no preset scaffolded"
    validated = run_cli(["charter", "org", "validate", "scaffold"], tmp_path)
    assert validated.exit_code == 0, describe(validated)


@covers("FR-019")
@pytest.mark.corpus
def test_fr019_manifest_hashes_presets_not_an_artifact_kind() -> None:
    manifest = (REPO_ROOT / "packs" / "built-in" / "pack-manifest.yaml").read_text(encoding="utf-8")
    assert "presets/default.yaml" in manifest and "presets/minimal.yaml" in manifest
    kinds = importlib.import_module("charter.offering.artifact_kinds").ArtifactKind
    assert not any("preset" in member.value for member in kinds)
    assert any(member.value == "directive" for member in kinds)  # control: the enum is the real one
