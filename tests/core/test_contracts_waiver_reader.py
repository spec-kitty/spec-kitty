"""Unit tests for the meta.json contracts waiver reader (#5298).

Operator ruling (2026-09-28, 2026-10-04): a software-dev Mission keeps the
``paths.deliverables: contracts/`` convention by default, but may declare in
``meta.json`` that it defines no interfaces with ``"contracts": "none"`` plus a
required non-empty ``contracts_rationale``. ``read_contracts_waiver_from_meta``
is the ONE reader. It fails closed: anything other than a well-formed waiver
keeps the requirement in force, and a present-but-malformed declaration warns
instead of being coerced. A corrupt ``meta.json`` raises, like every
``load_meta_fail_closed`` reader.

Pure logic: a ``tmp_path`` meta.json fixture only, no git.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from specify_cli.core.paths import (
    ContractsWaiver,
    MissionMetaReadError,
    read_contracts_waiver_from_meta,
)

pytestmark = [pytest.mark.unit]

_RATIONALE = "Test-drift remediation; the Mission defines no interfaces."


def _meta_dir(tmp_path: Path, payload: dict[str, object] | None) -> Path:
    meta_dir = tmp_path / "kitty-specs" / "no-contracts-01M43DRV"
    meta_dir.mkdir(parents=True)
    if payload is not None:
        (meta_dir / "meta.json").write_text(json.dumps(payload) + "\n", encoding="utf-8")
    return meta_dir


def test_absent_meta_is_not_a_waiver(tmp_path: Path) -> None:
    assert read_contracts_waiver_from_meta(_meta_dir(tmp_path, None)) == ContractsWaiver(waived=False)


def test_absent_field_is_not_a_waiver_and_is_silent(tmp_path: Path) -> None:
    waiver = read_contracts_waiver_from_meta(_meta_dir(tmp_path, {"mission_type": "software-dev"}))

    assert waiver == ContractsWaiver(waived=False)


def test_well_formed_waiver_is_honoured_with_its_rationale(tmp_path: Path) -> None:
    waiver = read_contracts_waiver_from_meta(_meta_dir(tmp_path, {"contracts": "none", "contracts_rationale": f"  {_RATIONALE}  "}))

    assert waiver.waived is True
    assert waiver.rationale == _RATIONALE
    assert waiver.warning is None


@pytest.mark.parametrize(
    "payload",
    [
        pytest.param({"contracts": "none"}, id="rationale-missing"),
        pytest.param({"contracts": "none", "contracts_rationale": "   "}, id="rationale-blank"),
        pytest.param({"contracts": "none", "contracts_rationale": 42}, id="rationale-not-a-string"),
        pytest.param({"contracts": "None", "contracts_rationale": _RATIONALE}, id="value-wrong-case"),
        pytest.param({"contracts": "skip", "contracts_rationale": _RATIONALE}, id="value-unknown"),
        pytest.param({"contracts": False, "contracts_rationale": _RATIONALE}, id="value-not-a-string"),
        pytest.param({"contracts": None, "contracts_rationale": _RATIONALE}, id="value-null"),
    ],
)
def test_malformed_waiver_keeps_the_requirement_and_warns(tmp_path: Path, payload: dict[str, object]) -> None:
    waiver = read_contracts_waiver_from_meta(_meta_dir(tmp_path, payload))

    assert waiver.waived is False
    assert waiver.warning is not None
    assert "contracts" in waiver.warning
    assert "meta.json" in waiver.warning


def test_corrupt_meta_fails_closed(tmp_path: Path) -> None:
    meta_dir = _meta_dir(tmp_path, None)
    (meta_dir / "meta.json").write_text("{not valid json", encoding="utf-8")

    with pytest.raises(MissionMetaReadError):
        read_contracts_waiver_from_meta(meta_dir)
