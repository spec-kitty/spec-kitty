"""Retired pack fields are rejected with ``RETIRED_PACK_FIELD`` (#3732, OD-1, contracts/errors.md)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from pydantic import BaseModel, ConfigDict, ValidationError, model_validator

from charter.activation.activations import ActivationEntry
from charter.activation.org_charter import (
    ORG_CHARTER_SCHEMA_VERSION,
    OrgCharterPolicy,
    load_org_charter_policies,
    load_org_charter_policy,
    validate_org_charter_file,
)
from charter.activation.org_charter_loader import load_org_charter_json_block
from charter.activation.pack_context import PackContext
from charter.activation.schemas import GovernanceConfig
from charter.activation.sync import load_governance_config
from charter.offering.packs import retired_fields
from charter.offering.packs.retired_fields import (
    _MIGRATION_RUNBOOK,
    RETIRED_PACK_FIELD,
    RETIRED_PACK_FIELDS,
    SCOPE_ACTIVATION_ENTRY,
    SCOPE_ORG_CHARTER,
    RetiredField,
    RetiredPackFieldError,
    raise_retired_field_at,
    reject_retired_fields,
    retired_field_errors,
    _retired_field_message,
)

pytestmark = pytest.mark.fast

OLD = "doctrine_pack_id"
NEW = "charter_pack_id"
CONTEXT = {"mission_type": "software-dev"}


def _entry(**extra: str) -> dict[str, object]:
    return {"activation_context": CONTEXT, "artifact_id": "acceptance-test-first", "artifact_kind": "tactics", **extra}


def _retired_from(exc: ValidationError) -> RetiredPackFieldError:
    found = retired_field_errors(exc)
    assert len(found) == 1, exc
    return found[0]


# --------------------------------------------------------------------------------------
# The table and its helpers
# --------------------------------------------------------------------------------------


def test_table_holds_the_charter_pack_id_rename() -> None:
    assert RetiredField(scope=SCOPE_ACTIVATION_ENTRY, field=OLD, replacement=NEW) in RETIRED_PACK_FIELDS
    assert RETIRED_PACK_FIELD == "RETIRED_PACK_FIELD"


def test_message_names_location_field_replacement_and_runbook() -> None:
    message = _retired_field_message("org-charter.yaml", OLD, NEW)
    assert message == f"org-charter.yaml: field '{OLD}' was removed. Replacement: {NEW}. See {_MIGRATION_RUNBOOK}."


def test_reject_raises_typed_error_with_code_file_field_replacement(tmp_path: Path) -> None:
    path = tmp_path / "org-charter.yaml"
    with pytest.raises(RetiredPackFieldError) as info:
        reject_retired_fields({OLD: "built-in"}, scope=SCOPE_ACTIVATION_ENTRY, path=path)
    err = info.value
    assert (err.code, err.scope, err.file, err.field, err.replacement, err.path) == (
        RETIRED_PACK_FIELD,
        SCOPE_ACTIVATION_ENTRY,
        str(path),
        OLD,
        NEW,
        path,
    )
    assert str(err).startswith(f"{path}: field '{OLD}' was removed.")


def test_reject_without_path_locates_by_scope() -> None:
    with pytest.raises(RetiredPackFieldError, match=r"^activation entry: field") as info:
        reject_retired_fields({OLD: "x"}, scope=SCOPE_ACTIVATION_ENTRY, path=None)
    assert info.value.file == SCOPE_ACTIVATION_ENTRY


@pytest.mark.parametrize("raw", [{NEW: "x"}, {}, ["not", "a", "mapping"], None, "text"])
def test_reject_leaves_clean_or_non_mapping_input_alone(raw: object) -> None:
    reject_retired_fields(raw, scope=SCOPE_ACTIVATION_ENTRY, path=None)


def test_reject_is_scoped() -> None:
    """The activation-entry row does not bind the ``org-charter.yaml`` top level."""
    reject_retired_fields({OLD: "x"}, scope=SCOPE_ORG_CHARTER, path=None)


def test_raise_retired_field_at_relocates_the_wrapped_error(tmp_path: Path) -> None:
    path = tmp_path / "org-charter.yaml"
    with pytest.raises(ValidationError) as wrapped:
        ActivationEntry.model_validate(_entry(**{OLD: "built-in"}))
    with pytest.raises(RetiredPackFieldError) as info:
        raise_retired_field_at(wrapped.value, path)
    assert (info.value.path, info.value.field) == (path, OLD)
    assert info.value.__cause__ is wrapped.value


def test_raise_retired_field_at_returns_for_a_generic_failure(tmp_path: Path) -> None:
    with pytest.raises(ValidationError) as wrapped:
        ActivationEntry.model_validate(_entry(**{NEW: "x", "unrelated_field": "y"}))
    assert raise_retired_field_at(wrapped.value, tmp_path / "x.yaml") is None


def test_at_relocates_the_same_rejection(tmp_path: Path) -> None:
    err = RetiredPackFieldError(RETIRED_PACK_FIELDS[0])
    moved = err.at(tmp_path / "x.yaml")
    assert moved.retired == err.retired
    assert str(moved).startswith(f"{tmp_path / 'x.yaml'}: field '{OLD}'")


def test_retired_field_errors_recovers_errors_wrapped_by_pydantic() -> None:
    class _Model(BaseModel):
        model_config = ConfigDict(extra="forbid")
        keep: int = 0

        @model_validator(mode="before")
        @classmethod
        def _check(cls, data: object) -> object:
            reject_retired_fields(data, scope=SCOPE_ACTIVATION_ENTRY, path="planted")
            return data

    with pytest.raises(ValidationError) as info:
        _Model.model_validate({OLD: "x"})
    assert _retired_from(info.value).field == OLD


def test_retired_field_errors_is_empty_for_a_generic_failure() -> None:
    with pytest.raises(ValidationError) as info:
        ActivationEntry.model_validate(_entry(**{NEW: "x", "unrelated_field": "y"}))
    assert retired_field_errors(info.value) == []
    assert "extra" in str(info.value).lower()


# --------------------------------------------------------------------------------------
# The activation entry: project charter.yaml and org-charter.yaml
# --------------------------------------------------------------------------------------


def test_activation_entry_accepts_charter_pack_id() -> None:
    assert ActivationEntry.model_validate(_entry(**{NEW: "built-in"})).charter_pack_id == "built-in"


def test_activation_entry_has_no_alias_for_the_old_name() -> None:
    assert OLD not in ActivationEntry.model_fields
    assert not ActivationEntry.model_config.get("populate_by_name")


def test_activation_entry_rejects_old_name_naming_both_names() -> None:
    with pytest.raises(ValidationError) as info:
        ActivationEntry.model_validate(_entry(**{OLD: "built-in"}))
    err = _retired_from(info.value)
    assert (err.code, err.field, err.replacement) == (RETIRED_PACK_FIELD, OLD, NEW)
    assert OLD in str(info.value) and NEW in str(info.value)


def test_project_charter_activations_reject_old_name() -> None:
    with pytest.raises(ValidationError) as info:
        GovernanceConfig.model_validate({"activations": [_entry(**{OLD: "built-in"})]})
    assert _retired_from(info.value).replacement == NEW


def test_org_charter_activations_reject_old_name() -> None:
    with pytest.raises(ValidationError) as info:
        OrgCharterPolicy.model_validate({"activations": [_entry(**{OLD: "built-in"})]})
    assert _retired_from(info.value).field == OLD


# --------------------------------------------------------------------------------------
# org-charter schema_version 2 (data-model.md "Enforced activations")
# --------------------------------------------------------------------------------------


def test_new_org_charter_defaults_to_schema_version_2() -> None:
    assert ORG_CHARTER_SCHEMA_VERSION == 2
    assert OrgCharterPolicy().schema_version == 2


def test_schema_version_1_without_retired_field_still_validates() -> None:
    policy = OrgCharterPolicy.model_validate({"schema_version": 1, "org_name": "acme", "required_directives": ["d"]})
    assert policy.schema_version == 1


def test_schema_version_1_with_retired_field_is_rejected() -> None:
    with pytest.raises(ValidationError) as info:
        OrgCharterPolicy.model_validate({"schema_version": "1", "activations": [_entry(**{OLD: "built-in"})]})
    assert _retired_from(info.value).code == RETIRED_PACK_FIELD


# --------------------------------------------------------------------------------------
# The validator surfaces a named issue
# --------------------------------------------------------------------------------------


def _write(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


def test_validator_names_retired_field_and_replacement(tmp_path: Path) -> None:
    path = _write(
        tmp_path / "org-charter.yaml",
        f"schema_version: 2\nactivations:\n  - activation_context: {{mission_type: software-dev}}\n    {OLD}: built-in\n    artifact_id: a\n",
    )
    issues = validate_org_charter_file(path)
    assert len(issues) == 1
    issue = issues[0]
    assert (issue.severity, issue.category, issue.artifact_id, issue.file) == ("error", RETIRED_PACK_FIELD, OLD, str(path))
    assert issue.message == f"{RETIRED_PACK_FIELD}: {_retired_field_message(str(path), OLD, NEW)}"


def test_validator_keeps_generic_message_for_other_schema_failures(tmp_path: Path) -> None:
    path = _write(tmp_path / "org-charter.yaml", "schema_version: 2\nunknown_key: 1\n")
    issues = validate_org_charter_file(path)
    assert len(issues) == 1
    assert issues[0].category is None
    assert issues[0].message.startswith("org-charter schema validation failed:")


def test_validator_accepts_charter_pack_id(tmp_path: Path) -> None:
    path = _write(
        tmp_path / "org-charter.yaml",
        f"schema_version: 2\nactivations:\n  - activation_context: {{mission_type: software-dev}}\n    {NEW}: built-in\n    artifact_id: a\n",
    )
    assert [i for i in validate_org_charter_file(path) if i.severity == "error"] == []


# --------------------------------------------------------------------------------------
# Loading: every org-charter loader and the project charter.yaml fail closed
# --------------------------------------------------------------------------------------

_RETIRED_ORG_CHARTER = (
    "schema_version: 2\n"
    "required_directives: [DIRECTIVE_001]\n"
    "activations:\n"
    "  - activation_context: {mission_type: software-dev}\n"
    f"    {OLD}: built-in\n"
    "    artifact_id: a\n"
)
_CLEAN_ORG_CHARTER = _RETIRED_ORG_CHARTER.replace(OLD, NEW)


def _pack(root: Path, name: str, body: str) -> Path:
    pack = root / name
    pack.mkdir(parents=True, exist_ok=True)
    _write(pack / "org-charter.yaml", body)
    return pack


def _pack_context(*roots: Path) -> PackContext:
    return PackContext(
        activated_kinds=frozenset({"directives"}),
        activated_mission_types=frozenset({"software-dev"}),
        pack_roots=roots,
        org_pack_names=tuple(r.name for r in roots),
        repo_root=Path("/nonexistent"),
    )


def _configure_packs(repo_root: Path, *packs: Path) -> None:
    lines = ["charter_packs:", "  org:", "    packs:"]
    for pack in packs:
        lines += [f"      - name: {pack.name}", f"        local_path: {pack}"]
    (repo_root / ".kittify").mkdir(parents=True, exist_ok=True)
    _write(repo_root / ".kittify" / "config.yaml", "\n".join(lines) + "\n")


def _assert_located(err: RetiredPackFieldError, path: Path) -> None:
    assert (err.code, err.field, err.replacement, err.path, err.file) == (RETIRED_PACK_FIELD, OLD, NEW, path, str(path))
    assert str(err) == _retired_field_message(str(path), OLD, NEW)


def test_load_org_charter_policy_raises_located_error(tmp_path: Path) -> None:
    pack = _pack(tmp_path, "acme", _RETIRED_ORG_CHARTER)
    with pytest.raises(RetiredPackFieldError) as info:
        load_org_charter_policy(pack)
    _assert_located(info.value, pack / "org-charter.yaml")


def test_load_org_charter_policy_loads_clean_pack(tmp_path: Path) -> None:
    policy = load_org_charter_policy(_pack(tmp_path, "acme", _CLEAN_ORG_CHARTER))
    assert policy is not None and policy.required_directives == ["DIRECTIVE_001"]


def test_load_org_charter_policy_keeps_generic_failures_generic(tmp_path: Path) -> None:
    with pytest.raises(ValidationError):
        load_org_charter_policy(_pack(tmp_path, "acme", "schema_version: 2\nunknown_key: 1\n"))


def test_pack_context_loader_does_not_drop_a_retired_field_pack(tmp_path: Path) -> None:
    """``_build_pack_set``: the pack is refused, never silently skipped."""
    clean = _pack(tmp_path, "clean", _CLEAN_ORG_CHARTER.replace("DIRECTIVE_001", "DIRECTIVE_002"))
    bad = _pack(tmp_path, "bad", _RETIRED_ORG_CHARTER)
    assert load_org_charter_policies(tmp_path, pack_context=_pack_context(clean)).required_directives == ["DIRECTIVE_002"]
    with pytest.raises(RetiredPackFieldError) as info:
        load_org_charter_policies(tmp_path, pack_context=_pack_context(clean, bad))
    _assert_located(info.value, bad / "org-charter.yaml")


def test_registry_loader_does_not_drop_a_retired_field_pack(tmp_path: Path) -> None:
    """The ``.kittify/config.yaml`` registry loop of ``load_org_charter_policies``."""
    clean = _pack(tmp_path / "packs", "clean", _CLEAN_ORG_CHARTER)
    bad = _pack(tmp_path / "packs", "bad", _RETIRED_ORG_CHARTER)
    _configure_packs(tmp_path, clean)
    assert load_org_charter_policies(tmp_path).required_directives == ["DIRECTIVE_001"]
    _configure_packs(tmp_path, clean, bad)
    with pytest.raises(RetiredPackFieldError) as info:
        load_org_charter_policies(tmp_path)
    _assert_located(info.value, bad / "org-charter.yaml")


def test_org_charter_json_block_does_not_drop_a_retired_field_pack(tmp_path: Path) -> None:
    clean = _pack(tmp_path, "clean", _CLEAN_ORG_CHARTER)
    bad = _pack(tmp_path, "bad", _RETIRED_ORG_CHARTER)
    block = load_org_charter_json_block([clean])
    assert block["present"] and block["packs"][0]["required_directives"] == ["DIRECTIVE_001"]
    with pytest.raises(RetiredPackFieldError) as info:
        load_org_charter_json_block([clean, bad])
    _assert_located(info.value, bad / "org-charter.yaml")


def _git_repo(root: Path, charter_yaml: str) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    charter = root / ".kittify" / "charter" / "charter.yaml"
    charter.parent.mkdir(parents=True, exist_ok=True)
    _write(charter, charter_yaml)
    return charter


_PROJECT_CHARTER = f"governance:\n  activations:\n    - activation_context: {{mission_type: software-dev}}\n      {OLD}: built-in\n      artifact_id: a\n"


def test_load_governance_config_raises_located_error(tmp_path: Path) -> None:
    charter = _git_repo(tmp_path / "repo", _PROJECT_CHARTER)
    with pytest.raises(RetiredPackFieldError) as info:
        load_governance_config(tmp_path / "repo")
    _assert_located(info.value, charter)


def test_load_governance_config_loads_clean_charter(tmp_path: Path) -> None:
    _git_repo(tmp_path / "repo", _PROJECT_CHARTER.replace(OLD, NEW))
    assert [e.charter_pack_id for e in load_governance_config(tmp_path / "repo").activations] == ["built-in"]


def test_load_governance_config_keeps_generic_failures_generic(tmp_path: Path) -> None:
    _git_repo(tmp_path / "repo", _PROJECT_CHARTER.replace(OLD, "unrelated_field"))
    with pytest.raises(ValidationError):
        load_governance_config(tmp_path / "repo")


# --------------------------------------------------------------------------------------
# Data-driven: a planted row in each enforced scope is rejected through a real loader
# --------------------------------------------------------------------------------------


def _plant(monkeypatch: pytest.MonkeyPatch, row: RetiredField) -> None:
    monkeypatch.setattr(retired_fields, "RETIRED_PACK_FIELDS", (*RETIRED_PACK_FIELDS, row))


def test_planted_org_charter_top_level_row_is_rejected_on_load(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    planted = RetiredField(scope=SCOPE_ORG_CHARTER, field="planted_top", replacement="delete it")
    pack = _pack(tmp_path, "acme", "schema_version: 2\nplanted_top: 1\n")
    with pytest.raises(ValidationError) as control:
        load_org_charter_policy(pack)
    assert retired_field_errors(control.value) == [], "control: unplanted, it is a generic extra field"
    _plant(monkeypatch, planted)
    with pytest.raises(RetiredPackFieldError) as info:
        load_org_charter_policy(pack)
    assert (info.value.retired, info.value.path) == (planted, pack / "org-charter.yaml")


def test_planted_activation_entry_row_is_rejected_on_both_loaders(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    planted = RetiredField(scope=SCOPE_ACTIVATION_ENTRY, field="planted_entry", replacement="delete it")
    _plant(monkeypatch, planted)
    org = _pack(tmp_path, "acme", _CLEAN_ORG_CHARTER + "    planted_entry: 1\n")
    with pytest.raises(RetiredPackFieldError) as org_info:
        load_org_charter_policy(org)
    assert (org_info.value.retired, org_info.value.path) == (planted, org / "org-charter.yaml")
    charter = _git_repo(tmp_path / "repo", _PROJECT_CHARTER.replace(OLD, NEW) + "      planted_entry: 1\n")
    with pytest.raises(RetiredPackFieldError) as project_info:
        load_governance_config(tmp_path / "repo")
    assert (project_info.value.retired, project_info.value.path) == (planted, charter)


def test_activation_entry_row_does_not_bind_the_org_charter_top_level(tmp_path: Path) -> None:
    """The ``file`` honesty pin: the ``doctrine_pack_id`` row is an activation-entry row only."""
    with pytest.raises(ValidationError) as info:
        load_org_charter_policy(_pack(tmp_path, "acme", f"schema_version: 2\n{OLD}: built-in\n"))
    assert retired_field_errors(info.value) == []
