"""The preset application engine, ``charter.activation.preset_application`` (FR-001, #3732 WP08).

Fixtures are tmp projects (``config.yaml`` target, and a pointed ``charter.yaml``
target) with an optional org pack ``acme`` that ships its own presets and an
``org-charter.yaml``. Built-in presets are read from the repository's
``packs/built-in``.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

import pytest
from ruamel.yaml import YAML

from charter.activation import preset_application as engine
from charter.activation.preset_application import (
    GOVERNED_KEYS,
    PackNotFoundError,
    PackPresetNotFoundError,
    PresetIdUnresolvedError,
    PresetPlan,
    PresetWouldOverwriteError,
    apply_preset_plan,
    find_offering_pack,
    load_pack_preset,
    plan_preset_application,
)

pytestmark = [pytest.mark.unit]

_REPO_ROOT = Path(__file__).resolve().parents[3]
_BUILT_IN = _REPO_ROOT / "packs" / "built-in"
_MINIMAL = YAML(typ="safe").load((_BUILT_IN / "presets" / "minimal.yaml").read_text(encoding="utf-8"))
_DEFAULT = YAML(typ="safe").load((_BUILT_IN / "presets" / "default.yaml").read_text(encoding="utf-8"))
ORG = "acme"
ORG_DIR = "org-packs/acme"
ORG_TACTIC = "acme-pairing"
ORG_DIRECTIVE_ID = "ACME-001-REVIEW-GATE"
ORG_DIRECTIVE_STEM = "acme-001-review-gate"
KNOWN_ANTI_PATTERN = "big-ball-of-mud"


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


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


def _project(tmp_path: Path, config: dict[str, Any] | None = None) -> Path:
    root = tmp_path / "project"
    _dump(root / ".kittify" / "config.yaml", config or {"vcs": {"type": "git"}})
    return root


def _with_org_pack(
    root: Path, *, presets: dict[str, dict[str, Any]] | None = None, org_charter: dict[str, Any] | None = None, extra: dict[str, Any] | None = None
) -> Path:
    pack = root / ORG_DIR
    _write(
        pack / "directives" / f"{ORG_DIRECTIVE_STEM}.directive.yaml",
        f'schema_version: "1.0"\nid: {ORG_DIRECTIVE_ID}\ntitle: gate\nintent: Apply org policy.\nenforcement: required\n',
    )
    _write(
        pack / "tactics" / f"{ORG_TACTIC}.tactic.yaml",
        f'schema_version: "1.0"\nid: {ORG_TACTIC}\nname: {ORG_TACTIC}\npurpose: Org tactic.\nsteps:\n  - title: Act\n    description: Do it.\n',
    )
    for name, body in (presets or {}).items():
        _dump(pack / "presets" / f"{name}.yaml", {"name": name, "description": f"{name} preset", **body})
    if org_charter is not None:
        _dump(pack / "org-charter.yaml", {"schema_version": "2", "org_name": ORG, **org_charter})
    config = _load(root / ".kittify" / "config.yaml")
    config.update({"charter_packs": {"org": {"packs": [{"name": ORG, "local_path": ORG_DIR}]}}, **(extra or {})})
    _dump(root / ".kittify" / "config.yaml", config)
    return root


def _apply(root: Path, pack: str, preset: str, *, force: bool = False) -> PresetPlan:
    plan = plan_preset_application(root, pack, preset)
    apply_preset_plan(root, plan, force=force)
    return plan


# ---------------------------------------------------------------------------
# Built-in presets on a config.yaml target
# ---------------------------------------------------------------------------


def test_governed_keys_include_anti_patterns_and_exclude_own_contract_kinds() -> None:
    assert "activated_anti_patterns" in GOVERNED_KEYS
    assert "activated_kinds" in GOVERNED_KEYS and "mission_type_activations" in GOVERNED_KEYS
    assert "activated_skills" not in GOVERNED_KEYS and "activated_glossary_packs" not in GOVERNED_KEYS


def test_minimal_on_an_empty_project_writes_exactly_its_keys(tmp_path: Path) -> None:
    root = _project(tmp_path)

    plan = _apply(root, "built-in", "minimal")

    assert plan.target_file == root / ".kittify" / "config.yaml"
    assert plan.written == {key: _MINIMAL[key] for key in ("mission_type_activations", "activated_directives", "activated_tactics")}
    assert plan.removed == []
    assert plan.customised_changes == ()
    config = _load(root / ".kittify" / "config.yaml")
    assert {k: v for k, v in config.items() if k in GOVERNED_KEYS} == plan.written
    assert config["vcs"] == {"type": "git"}


def test_default_after_minimal_removes_every_per_kind_key_and_kind_gate(tmp_path: Path) -> None:
    root = _project(tmp_path, {"activated_kinds": ["directives", "tactics"], "activated_skills": ["triage"], "activated_glossary_packs": []})
    first = _apply(root, "built-in", "minimal", force=True)

    plan = _apply(root, "built-in", "default", force=True)

    config = _load(root / ".kittify" / "config.yaml")
    assert first.removed == ["activated_kinds"]
    assert sorted(plan.removed) == ["activated_directives", "activated_tactics"]
    assert [k for k in config if k.startswith("activated_")] == ["activated_skills", "activated_glossary_packs"]
    assert config["activated_skills"] == ["triage"] and config["activated_glossary_packs"] == []
    assert config["mission_type_activations"] == _DEFAULT["mission_type_activations"]


def test_reapplying_a_preset_is_a_noop_without_a_write(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _project(tmp_path)
    _apply(root, "built-in", "minimal")
    before = (root / ".kittify" / "config.yaml").read_bytes()
    writes: list[object] = []
    monkeypatch.setattr(engine, "apply_yaml_write", writes.append)

    plan = _apply(root, "built-in", "minimal")

    assert plan.is_noop and plan.changes == {}
    assert writes == []
    assert (root / ".kittify" / "config.yaml").read_bytes() == before


def test_one_write_per_application(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _project(tmp_path)
    real = engine.apply_yaml_write
    writes: list[object] = []

    def spy(prepared: Any) -> None:
        writes.append(prepared)
        real(prepared)

    monkeypatch.setattr(engine, "apply_yaml_write", spy)

    _apply(root, "built-in", "minimal")

    assert len(writes) == 1


def test_pointer_target_is_written_and_config_left_alone(tmp_path: Path) -> None:
    root = tmp_path / "project"
    config = _write(root / ".kittify" / "config.yaml", "charter: .kittify/charter/charter.yaml\n")
    charter = _write(root / ".kittify" / "charter" / "charter.yaml", "activated_kinds:\n- directives\nactivated_skills:\n- triage\n")

    plan = _apply(root, "built-in", "default", force=True)

    assert plan.target_file == charter
    assert plan.customised_changes == ("activated_kinds",)
    data = _load(charter)
    assert "activated_kinds" not in data
    assert data["activated_skills"] == ["triage"]
    assert data["mission_type_activations"] == _DEFAULT["mission_type_activations"]
    assert config.read_text(encoding="utf-8") == "charter: .kittify/charter/charter.yaml\n"


# ---------------------------------------------------------------------------
# OD-6: customised keys
# ---------------------------------------------------------------------------


def test_customised_key_refused_without_force_and_file_unchanged(tmp_path: Path) -> None:
    root = _project(tmp_path, {"activated_directives": ["024-locality-of-change"], "mission_type_activations": ["software-dev"]})
    before = (root / ".kittify" / "config.yaml").read_bytes()
    plan = plan_preset_application(root, "built-in", "minimal")

    with pytest.raises(PresetWouldOverwriteError) as caught:
        apply_preset_plan(root, plan)

    assert caught.value.code == "PRESET_WOULD_OVERWRITE"
    assert plan.customised_changes == ("activated_directives",)
    assert "activated_tactics: absent -> [acceptance-test-first]" in "\n".join(caught.value.detail_lines())
    assert caught.value.payload()["diff"]["activated_directives"]["before"] == ["024-locality-of-change"]
    assert caught.value.payload()["diff"]["activated_tactics"]["before"] is None
    assert (root / ".kittify" / "config.yaml").read_bytes() == before

    apply_preset_plan(root, plan, force=True)
    assert _load(root / ".kittify" / "config.yaml")["activated_directives"] == _MINIMAL["activated_directives"]


def test_mission_types_equal_to_default_are_not_customised(tmp_path: Path) -> None:
    root = _project(tmp_path, {"mission_type_activations": list(reversed(_DEFAULT["mission_type_activations"]))})

    plan = plan_preset_application(root, "built-in", "minimal")

    assert "mission_type_activations" in plan.changes
    assert plan.customised_changes == ()


def test_overwrite_diff_renders_scalars_and_absent_values(tmp_path: Path) -> None:
    plan = PresetPlan(
        pack="built-in",
        preset="minimal",
        target_file=tmp_path / "config.yaml",
        written={"activated_directives": ["a"]},
        removed=["activated_kinds"],
        changes={"activated_directives": ("not-a-list", ["a"]), "activated_kinds": (["directives"], None)},
        customised_changes=("activated_directives", "activated_kinds"),
    )

    error = PresetWouldOverwriteError(plan)

    assert error.detail_lines() == ["  activated_directives: 'not-a-list' -> [a]", "  activated_kinds: [directives] -> absent"]
    assert error.payload()["diff"] == {
        "activated_directives": {"before": "not-a-list", "after": ["a"]},
        "activated_kinds": {"before": ["directives"], "after": None},
    }
    assert "--force" in str(error)


def test_missing_default_preset_treats_every_present_key_as_customised(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    packs_root = tmp_path / "packs-root"
    shutil.copytree(_BUILT_IN, packs_root / "built-in")
    (packs_root / "built-in" / "presets" / "default.yaml").unlink()
    monkeypatch.setenv("SPEC_KITTY_PACKS_ROOT", str(packs_root))
    root = _project(tmp_path, {"mission_type_activations": _DEFAULT["mission_type_activations"]})

    plan = plan_preset_application(root, "built-in", "minimal")

    assert plan.customised_changes == ("mission_type_activations",)


# ---------------------------------------------------------------------------
# Lookup errors
# ---------------------------------------------------------------------------


def test_unknown_pack_names_the_available_packs(tmp_path: Path) -> None:
    root = _project(tmp_path)

    with pytest.raises(PackNotFoundError) as caught:
        plan_preset_application(root, "nope", "minimal")

    assert caught.value.code == "PACK_NOT_FOUND"
    assert caught.value.available == ("built-in", "project")
    assert caught.value.payload() == {"pack": "nope", "available": ["built-in", "project"]}


def test_unknown_preset_names_the_pack_and_its_presets(tmp_path: Path) -> None:
    root = _project(tmp_path)

    with pytest.raises(PackPresetNotFoundError) as caught:
        plan_preset_application(root, "built-in", "does-not-exist")

    assert caught.value.code == "PRESET_NOT_FOUND"
    assert set(caught.value.available) >= {"default", "minimal"}
    assert "built-in" in str(caught.value) and "minimal" in str(caught.value)
    assert caught.value.payload()["pack"] == "built-in"


def test_project_pack_ships_no_presets(tmp_path: Path) -> None:
    root = _project(tmp_path)

    with pytest.raises(PackPresetNotFoundError) as caught:
        load_pack_preset(find_offering_pack(root, "project"), "minimal")

    assert caught.value.available == ()
    assert "none" in str(caught.value)


# ---------------------------------------------------------------------------
# Id resolution against the whole offering
# ---------------------------------------------------------------------------


def test_unresolved_ids_are_named_and_nothing_is_written(tmp_path: Path) -> None:
    root = _with_org_pack(
        _project(tmp_path),
        presets={
            "ghost": {
                "activated_tactics": ["acceptance-test-first", "no-such-tactic"],
                "activated_anti_patterns": ["no-such-smell"],
                "mission_type_activations": ["no-such-type"],
            }
        },
    )
    before = (root / ".kittify" / "config.yaml").read_bytes()

    with pytest.raises(PresetIdUnresolvedError) as caught:
        plan_preset_application(root, ORG, "ghost")

    assert caught.value.code == "PRESET_ID_UNRESOLVED"
    assert caught.value.unresolved == {
        "activated_tactics": ["no-such-tactic"],
        "activated_anti_patterns": ["no-such-smell"],
        "mission_type_activations": ["no-such-type"],
    }
    assert caught.value.preset_file.name == "ghost.yaml"
    assert "  activated_tactics: no-such-tactic" in caught.value.detail_lines()
    assert caught.value.payload()["preset_file"].endswith("ghost.yaml")
    assert (root / ".kittify" / "config.yaml").read_bytes() == before


def test_ids_resolve_across_built_in_org_and_declared_spellings(tmp_path: Path) -> None:
    root = _with_org_pack(
        _project(tmp_path),
        presets={
            "team": {
                "activated_directives": ["001-architectural-integrity-standard", ORG_DIRECTIVE_ID, "DIRECTIVE_010"],
                "activated_tactics": [ORG_TACTIC],
                "activated_anti_patterns": [KNOWN_ANTI_PATTERN],
                "activated_paradigms": [],
            }
        },
    )

    plan = _apply(root, ORG, "team")

    assert plan.written["activated_directives"] == ["001-architectural-integrity-standard", ORG_DIRECTIVE_ID, "DIRECTIVE_010"]
    assert plan.written["activated_anti_patterns"] == [KNOWN_ANTI_PATTERN]
    assert plan.written["activated_paradigms"] == []


def test_not_activatable_mission_type_is_reported(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from charter.activation import mission_type_profiles

    def refuse(mission_type: str, *, repo_root: Path) -> None:
        raise ValueError("empty action sequence")

    monkeypatch.setattr(mission_type_profiles, "validate_activatable_mission_type", refuse)
    root = _project(tmp_path)

    with pytest.raises(PresetIdUnresolvedError) as caught:
        plan_preset_application(root, "built-in", "minimal")

    assert caught.value.reasons == {"mission_type_activations": "software-dev: empty action sequence"}
    assert "  mission_type_activations: software-dev: empty action sequence" in caught.value.detail_lines()


# ---------------------------------------------------------------------------
# Org required_<kind> union
# ---------------------------------------------------------------------------


def test_org_required_ids_union_into_listed_keys_only(tmp_path: Path) -> None:
    root = _with_org_pack(
        _project(tmp_path),
        presets={"team": {"activated_directives": ["001-architectural-integrity-standard"], "activated_kinds": ["directives"]}},
        org_charter={"required_tactics": [ORG_TACTIC], "required_directives": ["DIRECTIVE_001", ORG_DIRECTIVE_ID]},
    )

    plan = _apply(root, ORG, "team")

    assert plan.written["activated_directives"] == ["001-architectural-integrity-standard", ORG_DIRECTIVE_ID]
    assert plan.written["activated_kinds"] == ["directives", "tactics"]
    assert "activated_tactics" not in _load(root / ".kittify" / "config.yaml"), "an unrestricted key already admits org-required ids"


def test_preset_without_mission_types_leaves_the_key_untouched(tmp_path: Path) -> None:
    root = _with_org_pack(_project(tmp_path, {"mission_type_activations": ["research"]}), presets={"team": {"activated_tactics": [ORG_TACTIC]}})

    plan = _apply(root, ORG, "team")

    assert "mission_type_activations" not in plan.changes
    assert _load(root / ".kittify" / "config.yaml")["mission_type_activations"] == ["research"]


# ---------------------------------------------------------------------------
# Review cycle 1: fail closed, every reason kept, typed target failures
# ---------------------------------------------------------------------------


def _with_ghost_org_pack(root: Path) -> Path:
    config = _load(root / ".kittify" / "config.yaml")
    config["charter_packs"] = {"org": {"packs": [{"name": "ghost", "local_path": "org-packs/ghost"}]}}
    _dump(root / ".kittify" / "config.yaml", config)
    return root


def test_missing_declared_org_root_refuses_a_preset_listing_ids(tmp_path: Path) -> None:
    root = _with_ghost_org_pack(_project(tmp_path))
    before = (root / ".kittify" / "config.yaml").read_bytes()

    with pytest.raises(PresetIdUnresolvedError) as caught:
        plan_preset_application(root, "built-in", "minimal")

    assert caught.value.unresolved == {}
    assert any("not a directory" in why for why in caught.value.reasons.values()), caught.value.reasons
    assert (root / ".kittify" / "config.yaml").read_bytes() == before


def test_missing_declared_org_root_does_not_block_a_preset_listing_no_ids(tmp_path: Path) -> None:
    root = _with_ghost_org_pack(_project(tmp_path))

    plan = plan_preset_application(root, "built-in", "default")

    assert "mission_type_activations" in plan.written


def test_every_not_activatable_mission_type_is_reported(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from charter.activation import mission_type_profiles

    def refuse(mission_type: str, *, repo_root: Path) -> None:
        raise ValueError(f"{mission_type} has no steps")

    monkeypatch.setattr(mission_type_profiles, "validate_activatable_mission_type", refuse)

    with pytest.raises(PresetIdUnresolvedError) as caught:
        plan_preset_application(_project(tmp_path), "built-in", "default")

    reason = caught.value.reasons["mission_type_activations"]
    for mission_type in _DEFAULT["mission_type_activations"]:
        assert f"{mission_type}: {mission_type} has no steps" in reason


def test_drg_load_failure_while_checking_anti_patterns_is_unresolved(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from charter.offering.drg.loader import DRGLoadError

    def broken(repo_root: Path) -> frozenset[str]:
        raise DRGLoadError("graph.yaml: unreadable")

    monkeypatch.setattr(engine, "_load_anti_pattern_ids", broken)
    root = _with_org_pack(_project(tmp_path), presets={"smells": {"activated_anti_patterns": [KNOWN_ANTI_PATTERN]}})

    with pytest.raises(PresetIdUnresolvedError) as caught:
        plan_preset_application(root, ORG, "smells")

    assert "graph.yaml: unreadable" in caught.value.reasons["activated_anti_patterns"]


def test_concurrent_edit_of_the_target_is_a_config_error_with_a_rerun_hint(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from charter.activation.pack_context import ActiveCharterConfigError

    root = _project(tmp_path)
    plan = plan_preset_application(root, "built-in", "minimal")

    def raced(*_args: Any, **_kwargs: Any) -> None:
        raise ValueError(f"precondition_changed: {plan.target_file}")

    monkeypatch.setattr(engine, "prepare_activation_write", raced)

    with pytest.raises(ActiveCharterConfigError) as caught:
        apply_preset_plan(root, plan)

    assert caught.value.code == "ACTIVE_CHARTER_CONFIG_INVALID"
    assert "re-run" in caught.value.body


def test_a_programming_error_in_the_writer_propagates(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _project(tmp_path)
    plan = plan_preset_application(root, "built-in", "minimal")

    def guard(*_args: Any, **_kwargs: Any) -> None:
        raise ValueError("Activation key(s) both written and removed: ['x']")

    monkeypatch.setattr(engine, "prepare_activation_write", guard)

    with pytest.raises(ValueError, match="both written and removed"):
        apply_preset_plan(root, plan)


def test_unparseable_target_is_a_config_error(tmp_path: Path) -> None:
    from charter.activation.pack_context import ActiveCharterConfigError

    root = tmp_path / "project"
    _write(root / ".kittify" / "config.yaml", "charter: .kittify/charter/charter.yaml\n")
    _write(root / ".kittify" / "charter" / "charter.yaml", "- not\n- a mapping\n")

    with pytest.raises(ActiveCharterConfigError):
        plan_preset_application(root, "built-in", "minimal")


# ---------------------------------------------------------------------------
# WP08 review follow-ups: the three fail-closed branches each get a test
# ---------------------------------------------------------------------------


def test_unreadable_mission_type_roster_is_a_reason_and_nothing_is_written(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def malformed(repo_root: Path, org_roots: Any) -> frozenset[str]:
        raise ValueError("mission_types/broken.yaml: not a mapping")

    monkeypatch.setattr(engine, "_available_mission_types", malformed)
    root = _project(tmp_path)
    before = (root / ".kittify" / "config.yaml").read_bytes()

    with pytest.raises(PresetIdUnresolvedError) as caught:
        plan_preset_application(root, "built-in", "default")

    assert caught.value.reasons == {"mission_type_activations": "the mission-type roster cannot be read: mission_types/broken.yaml: not a mapping"}
    assert caught.value.unresolved == {}
    assert (root / ".kittify" / "config.yaml").read_bytes() == before


def test_unreadable_org_charter_fails_closed_for_a_preset_listing_ids(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def unreadable(repo_root: Path) -> Any:
        raise ValueError("org-charter.yaml: retired field 'doctrine_pack_id'")

    monkeypatch.setattr(engine, "load_org_charter_policies", unreadable)
    root = _with_org_pack(_project(tmp_path), presets={"team": {"activated_tactics": [ORG_TACTIC]}})
    before = (root / ".kittify" / "config.yaml").read_bytes()

    with pytest.raises(PresetIdUnresolvedError) as caught:
        plan_preset_application(root, ORG, "team")

    (reason,) = caught.value.reasons.values()
    assert reason == "the org charter cannot be read: org-charter.yaml: retired field 'doctrine_pack_id'"
    assert (root / ".kittify" / "config.yaml").read_bytes() == before


def test_org_charter_is_not_read_for_a_preset_listing_no_ids(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def unreadable(repo_root: Path) -> Any:
        raise AssertionError("the org charter must not be read for a mission-types-only preset")

    monkeypatch.setattr(engine, "load_org_charter_policies", unreadable)

    plan = plan_preset_application(_project(tmp_path), "built-in", "default")

    assert "mission_type_activations" in plan.written


def test_flow_style_target_root_is_a_config_error_and_unchanged(tmp_path: Path) -> None:
    from charter.activation.pack_context import ActiveCharterConfigError

    root = tmp_path / "project"
    config = _write(root / ".kittify" / "config.yaml", "{vcs: {type: git}, activated_directives: [DIRECTIVE_001]}\n")
    before = config.read_bytes()
    plan = plan_preset_application(root, "built-in", "default")
    assert plan.removed == ["activated_directives"], "control: the default preset removes the per-kind key"

    with pytest.raises(ActiveCharterConfigError) as caught:
        apply_preset_plan(root, plan, force=True)

    assert caught.value.code == "ACTIVE_CHARTER_CONFIG_INVALID"
    assert "cannot take the preset" in caught.value.body and "flow-style" in caught.value.body
    assert config.read_bytes() == before
