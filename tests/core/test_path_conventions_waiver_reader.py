"""Unit tests for the meta.json path-conventions waiver reader (#7566).

Operator ruling Q1 (Mission path-conventions-per-type-01M7VRQM): a Mission may
declare in ``meta.json`` that path conventions do not apply to it, with
``"path_conventions": "waived"`` plus a required non-empty
``path_conventions_rationale``. ``read_path_conventions_waiver_from_meta`` is the
ONE reader and shares the #5298 contracts waiver's fail-closed rules: anything
other than a well-formed waiver keeps path conventions in force, a
present-but-malformed declaration warns, and a corrupt ``meta.json`` raises.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from specify_cli.core.paths import (
    ContractsWaiver,
    MissionMetaReadError,
    read_path_conventions_waiver_from_meta,
)

pytestmark = [pytest.mark.unit]

_RATIONALE = "Content repository; there is no src/ layout."


def _meta_dir(tmp_path: Path, payload: dict[str, object] | None) -> Path:
    meta_dir = tmp_path / "kitty-specs" / "content-only-01M7VRQM"
    meta_dir.mkdir(parents=True)
    if payload is not None:
        (meta_dir / "meta.json").write_text(json.dumps(payload) + "\n", encoding="utf-8")
    return meta_dir


def test_absent_meta_is_not_a_waiver(tmp_path: Path) -> None:
    assert read_path_conventions_waiver_from_meta(_meta_dir(tmp_path, None)) == ContractsWaiver(waived=False)


def test_absent_field_is_not_a_waiver_and_is_silent(tmp_path: Path) -> None:
    waiver = read_path_conventions_waiver_from_meta(_meta_dir(tmp_path, {"mission_type": "software-dev"}))
    assert waiver == ContractsWaiver(waived=False)


def test_well_formed_waiver_is_honoured_with_its_stripped_rationale(tmp_path: Path) -> None:
    waiver = read_path_conventions_waiver_from_meta(_meta_dir(tmp_path, {"path_conventions": "waived", "path_conventions_rationale": f"  {_RATIONALE}  "}))
    assert waiver.waived is True
    assert waiver.rationale == _RATIONALE
    assert waiver.warning is None


@pytest.mark.parametrize("value", ["Waived", "none", True, None, "", 1])
def test_any_other_value_is_not_a_waiver_and_warns(tmp_path: Path, value: object) -> None:
    waiver = read_path_conventions_waiver_from_meta(_meta_dir(tmp_path, {"path_conventions": value, "path_conventions_rationale": _RATIONALE}))
    assert waiver.waived is False
    assert waiver.warning is not None
    assert repr(value) in waiver.warning
    assert "'waived'" in waiver.warning
    assert "Path conventions stay in force" in waiver.warning


@pytest.mark.parametrize("rationale", [None, "", "   ", 7, ["x"]])
def test_missing_blank_or_non_string_rationale_is_not_a_waiver(tmp_path: Path, rationale: object) -> None:
    payload: dict[str, object] = {"path_conventions": "waived"}
    if rationale is not None:
        payload["path_conventions_rationale"] = rationale
    waiver = read_path_conventions_waiver_from_meta(_meta_dir(tmp_path, payload))
    assert waiver.waived is False
    assert waiver.warning is not None
    assert "'path_conventions_rationale'" in waiver.warning


def test_corrupt_meta_raises(tmp_path: Path) -> None:
    meta_dir = _meta_dir(tmp_path, None)
    (meta_dir / "meta.json").write_text("{not json", encoding="utf-8")
    with pytest.raises(MissionMetaReadError):
        read_path_conventions_waiver_from_meta(meta_dir)


def test_contracts_waiver_does_not_waive_path_conventions(tmp_path: Path) -> None:
    waiver = read_path_conventions_waiver_from_meta(_meta_dir(tmp_path, {"contracts": "none", "contracts_rationale": "no interfaces"}))
    assert waiver == ContractsWaiver(waived=False)
