"""Level load-refusals: MISMATCH (refuse), MISSING (warn-then-refuse) (FR-006/FR-007, WP02 T006/T010/T011).

``check_pack_level`` is the pure MISMATCH predicate; ``validate_pack`` threads
the configured position (``expected_level``) and reports ``PACK_LEVEL_MISMATCH``
(refuse, names file/declared/configured) and ``PACK_LEVEL_MISSING`` (warn now,
refuse only behind the single module-level deprecation switch).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from charter.offering.packs import pack_validator
from charter.offering.packs.pack_descriptor import PACK_LEVEL_MISMATCH, PACK_LEVEL_MISSING, PackDescriptor
from charter.offering.packs.pack_validator import check_pack_level, validate_pack
from kernel.pack_tiers import BUILT_IN, ORG, PROJECT

pytestmark = [pytest.mark.fast]

_BASE = "pack_id: 01ARWG13C000000000000000FG\nname: acme\n"


def _pack(root: Path, descriptor: str) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "pack.yaml").write_text(descriptor, encoding="utf-8")
    return root


def _pack_issues(pack_dir: Path, **kwargs: object) -> list[pack_validator.ValidationIssue]:
    result = validate_pack(pack_dir, check_drg_root=False, **kwargs)  # type: ignore[arg-type]
    return [issue for issue in (*result.errors, *result.advisories) if issue.artifact_type == "pack"]


# ---------------------------------------------------------------------------
# check_pack_level — the pure predicate.
# ---------------------------------------------------------------------------


def _descriptor(level: str) -> PackDescriptor:
    data: dict[str, object] = {"pack_id": "01ARWG13C000000000000000FG", "name": "acme", "pack_level": level}
    if level == BUILT_IN:
        data["pack_version"] = "1.0.0"
    return PackDescriptor.model_validate(data)


def test_check_pack_level_agree_returns_none() -> None:
    assert check_pack_level(_descriptor(ORG), ORG, file=Path("pack.yaml")) is None


def test_check_pack_level_bare_path_skips_fail_closed() -> None:
    # No position context -> skip the mismatch check (never silently pass a
    # wrong level, but there is nothing to compare against here).
    assert check_pack_level(_descriptor(BUILT_IN), None, file=Path("pack.yaml")) is None


def test_check_pack_level_mismatch_names_declared_and_configured() -> None:
    issue = check_pack_level(_descriptor(BUILT_IN), ORG, file=Path("/x/pack.yaml"))
    assert issue is not None
    assert issue.severity == "error"
    assert issue.category == PACK_LEVEL_MISMATCH
    assert issue.file == "/x/pack.yaml"
    assert BUILT_IN in issue.message and ORG in issue.message


# ---------------------------------------------------------------------------
# validate_pack threads the configured position.
# ---------------------------------------------------------------------------


def test_mismatch_refuses_when_loaded_from_a_wrong_position(tmp_path: Path) -> None:
    pack_dir = _pack(tmp_path / "p", f"{_BASE}pack_level: {BUILT_IN}\npack_version: 1.0.0\n")
    result = validate_pack(pack_dir, check_drg_root=False, expected_level=ORG)
    mismatch = [i for i in result.errors if i.category == PACK_LEVEL_MISMATCH]
    assert len(mismatch) == 1
    assert result.ok is False
    assert BUILT_IN in mismatch[0].message and ORG in mismatch[0].message


def test_matching_level_loads_clean(tmp_path: Path) -> None:
    pack_dir = _pack(tmp_path / "p", f"{_BASE}pack_level: {ORG}\n")
    result = validate_pack(pack_dir, check_drg_root=False, expected_level=ORG)
    assert [i for i in _pack_issues(pack_dir, expected_level=ORG) if i.category in {PACK_LEVEL_MISMATCH, PACK_LEVEL_MISSING}] == []
    assert not any(i.category == PACK_LEVEL_MISMATCH for i in result.errors)


def test_missing_level_warns_not_refuses(tmp_path: Path) -> None:
    pack_dir = _pack(tmp_path / "p", _BASE)  # no pack_level
    result = validate_pack(pack_dir, check_drg_root=False, expected_level=ORG)
    missing = [i for i in result.advisories if i.category == PACK_LEVEL_MISSING]
    assert len(missing) == 1, result.to_dict()
    assert str(pack_dir / "pack.yaml") == missing[0].file
    # WARN, not refuse: no pack-descriptor error is recorded for the missing field.
    assert not any(i.category == PACK_LEVEL_MISSING for i in result.errors)


def test_missing_level_hard_refuse_behind_the_switch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pack_dir = _pack(tmp_path / "p", _BASE)  # no pack_level
    monkeypatch.setattr(pack_validator, "_PACK_LEVEL_MISSING_IS_ERROR", True)
    result = validate_pack(pack_dir, check_drg_root=False, expected_level=ORG)
    refused = [i for i in result.errors if i.category == PACK_LEVEL_MISSING]
    assert len(refused) == 1
    assert result.ok is False


def test_bare_path_skips_mismatch_but_still_runs_missing(tmp_path: Path) -> None:
    # No position -> never a mismatch verdict, but a missing field is still flagged.
    pack_dir = _pack(tmp_path / "p", _BASE)
    issues = _pack_issues(pack_dir)
    assert [i.category for i in issues] == [PACK_LEVEL_MISSING]
    # A declared level with no position is tolerated (no mismatch, no crash).
    pack_dir2 = _pack(tmp_path / "p2", f"{_BASE}pack_level: {PROJECT}\n")
    assert _pack_issues(pack_dir2) == []
