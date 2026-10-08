"""``accompanies_doctrine_pack`` is retired: a ``pack.yaml`` carrying it is rejected (#3732 WP13, OD-2).

The rejection goes through the real descriptor loader
(:func:`charter.offering.packs.pack_descriptor.load_pack_descriptor`) and the
pack validator, both of which read the one table in
:mod:`charter.offering.packs.retired_fields`.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from charter.offering.pack_paths import built_in_root
from charter.offering.packs import retired_fields
from charter.offering.packs.pack_descriptor import PackDescriptor, load_pack_descriptor
from charter.offering.packs.pack_validator import validate_pack
from charter.offering.packs.retired_fields import (
    RETIRED_PACK_FIELD,
    RETIRED_PACK_FIELDS,
    SCOPE_PACK_DESCRIPTOR,
    RetiredField,
    RetiredPackFieldError,
)

pytestmark = [pytest.mark.fast]

FIELD = "accompanies_doctrine_pack"
RUNBOOK = "docs/migrations/charter-pack-cutover.md"
CLEAN = "pack_id: 01ARWG13C000000000000000FG\npack_version: 1.0.0\nparent_pack: null\nname: acme\n"


def _pack(root: Path, descriptor: str) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "pack.yaml").write_text(descriptor, encoding="utf-8")
    return root


def _retired_row() -> RetiredField:
    return next(row for row in RETIRED_PACK_FIELDS if row.field == FIELD)


# --------------------------------------------------------------------------------------
# The table
# --------------------------------------------------------------------------------------


def test_table_holds_the_pack_yaml_row() -> None:
    row = _retired_row()
    assert row.scope == SCOPE_PACK_DESCRIPTOR == "pack.yaml"
    assert "presets/<name>.yaml" in row.replacement


# --------------------------------------------------------------------------------------
# The loader
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize("value", ["null", "01ARWG13C000000000000000FH"])
def test_loader_rejects_the_field_with_code_file_field_and_replacement(tmp_path: Path, value: str) -> None:
    path = _pack(tmp_path / "p", f"{CLEAN}{FIELD}: {value}\n") / "pack.yaml"

    with pytest.raises(RetiredPackFieldError) as caught:
        load_pack_descriptor(path)

    error = caught.value
    assert error.code == RETIRED_PACK_FIELD
    assert error.file == str(path)
    assert error.field == FIELD
    assert error.replacement == _retired_row().replacement
    assert str(path) in str(error) and FIELD in str(error) and RUNBOOK in str(error)


def test_loader_reads_a_descriptor_without_the_field(tmp_path: Path) -> None:
    path = _pack(tmp_path / "p", CLEAN) / "pack.yaml"

    descriptor = load_pack_descriptor(path)

    assert descriptor == PackDescriptor(pack_id="01ARWG13C000000000000000FG", pack_version="1.0.0", name="acme")
    assert not hasattr(descriptor, FIELD)


def test_loader_reads_the_built_in_descriptor() -> None:
    descriptor = load_pack_descriptor(built_in_root() / "pack.yaml")
    assert descriptor.name == "built-in"


def test_an_unrelated_unknown_field_keeps_pydantics_generic_error(tmp_path: Path) -> None:
    """Positive control: the retired-field check is specific to the table's fields."""
    path = _pack(tmp_path / "p", f"{CLEAN}colour: blue\n") / "pack.yaml"

    with pytest.raises(ValidationError) as caught:
        load_pack_descriptor(path)

    assert not isinstance(caught.value, RetiredPackFieldError)
    assert caught.value.errors()[0]["type"] == "extra_forbidden"


def test_model_without_loader_wraps_the_typed_error() -> None:
    """The model rejects the field before pydantic's extra-field check (no ``extra_forbidden``)."""
    with pytest.raises(ValidationError) as caught:
        PackDescriptor.model_validate({"pack_id": "x", "pack_version": "1", "name": "n", FIELD: None})

    found = retired_fields.retired_field_errors(caught.value)
    assert [error.field for error in found] == [FIELD]
    assert all(error["type"] != "extra_forbidden" for error in caught.value.errors())


def test_a_planted_row_is_rejected_the_same_way(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The check is data-driven: a second ``pack.yaml`` row needs no code change."""
    planted = RetiredField(scope=SCOPE_PACK_DESCRIPTOR, field="planted_field", replacement="use the planted replacement")
    monkeypatch.setattr(retired_fields, "RETIRED_PACK_FIELDS", (*RETIRED_PACK_FIELDS, planted))
    path = _pack(tmp_path / "p", f"{CLEAN}planted_field: 1\n") / "pack.yaml"

    with pytest.raises(RetiredPackFieldError) as caught:
        load_pack_descriptor(path)

    assert caught.value.field == "planted_field"
    assert caught.value.replacement == planted.replacement


# --------------------------------------------------------------------------------------
# The validator
# --------------------------------------------------------------------------------------


def _descriptor_errors(pack_dir: Path) -> list[dict[str, object]]:
    result = validate_pack(pack_dir, check_drg_root=False)
    return [issue.to_dict() for issue in result.errors if issue.artifact_type == "pack"]


def test_validator_reports_the_retired_field(tmp_path: Path) -> None:
    pack_dir = _pack(tmp_path / "p", f"{CLEAN}{FIELD}: null\n")

    errors = _descriptor_errors(pack_dir)

    assert len(errors) == 1
    issue = errors[0]
    assert issue["category"] == RETIRED_PACK_FIELD
    assert issue["artifact_id"] == FIELD
    assert issue["file"] == str(pack_dir / "pack.yaml")
    message = str(issue["message"])
    assert message.startswith(f"{RETIRED_PACK_FIELD}: ")
    assert FIELD in message and RUNBOOK in message
    assert validate_pack(pack_dir, check_drg_root=False).ok is False


def test_validator_accepts_a_clean_descriptor(tmp_path: Path) -> None:
    pack_dir = _pack(tmp_path / "p", CLEAN)
    assert _descriptor_errors(pack_dir) == []


def test_validator_skips_a_pack_without_a_descriptor(tmp_path: Path) -> None:
    pack_dir = tmp_path / "p"
    pack_dir.mkdir()
    assert _descriptor_errors(pack_dir) == []


def test_validator_reports_other_schema_failures_generically(tmp_path: Path) -> None:
    pack_dir = _pack(tmp_path / "p", f"{CLEAN}colour: blue\n")

    errors = _descriptor_errors(pack_dir)

    assert [issue["category"] for issue in errors] == ["schema_invalid"]
    assert RETIRED_PACK_FIELD not in str(errors[0]["message"])


def test_validator_reports_an_unparseable_descriptor(tmp_path: Path) -> None:
    pack_dir = _pack(tmp_path / "p", "pack_id: [unclosed\n")

    errors = _descriptor_errors(pack_dir)

    assert [issue["category"] for issue in errors] == ["parse_error"]
