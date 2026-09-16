"""Pin the diff-scoped shard reconciler contracts C-recon-1..4 (#4360-B).

RED on base ``36d866d4fa`` (the module does not exist / the inline reconciler
demanded all 37 registry shards); GREEN once the selection-aware
:func:`reconcile` requires only SELECTED shards fresh and treats UNSELECTED
absent shards as optional -- while a SELECTED-but-absent shard stays fatal
(the ``must_be_fresh`` false-green guard).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from scripts.ci.reconcile_shards import (
    RegistryShard,
    RegistryValidationError,
    parse_registry,
    read_selected_modules,
    reconcile,
)

pytestmark = pytest.mark.fast


def _shard(module: str, index: int = 1, count: int = 1, tier: str = "standard") -> RegistryShard:
    return RegistryShard(tier=tier, module=module, shard_index=index, shard_count=count)


# A three-module registry: M is the selected/changed one, U1 and U2 are unselected.
_M = _shard("M")
_U1 = _shard("U1")
_U2 = _shard("U2")
_REGISTRY = [_M, _U1, _U2]


def test_c_recon_1_selected_fresh_is_complete() -> None:
    """C-recon-1: a SELECTED shard fresh in current, unselected shards absent
    from an empty fallback -> complete, nothing missing."""
    result = reconcile(
        _REGISTRY,
        selected={"M"},
        current_fresh={_M.key},
        previous_available=set(),
    )
    assert result.complete is True
    assert result.missing == []
    assert _M in result.fresh


def test_c_recon_2_selected_absent_is_still_fatal() -> None:
    """C-recon-2 (must_be_fresh guard): a SELECTED shard absent from current is
    fatal EVEN when the fallback has it -- a backfill artefact never satisfies
    a selected shard."""
    result = reconcile(
        _REGISTRY,
        selected={"M"},
        current_fresh=set(),
        previous_available={_M.key},  # present in fallback, must NOT satisfy
    )
    assert result.complete is False
    assert _M in result.missing
    assert _M not in result.stale


def test_c_recon_3_selected_none_is_legacy_all_registry() -> None:
    """C-recon-3 (legacy): selected=None requires every registry shard;
    unselected-in-name shards backfill from previous, absent ones are fatal."""
    # Everything present across current+previous -> complete (legacy backfill).
    complete_result = reconcile(
        _REGISTRY,
        selected=None,
        current_fresh={_M.key},
        previous_available={_U1.key, _U2.key},
    )
    assert complete_result.complete is True
    assert complete_result.missing == []
    assert set(complete_result.stale) == {_U1, _U2}

    # A shard absent from BOTH is fatal in full mode (unchanged behaviour).
    incomplete_result = reconcile(
        _REGISTRY,
        selected=None,
        current_fresh={_M.key},
        previous_available={_U1.key},
    )
    assert incomplete_result.complete is False
    assert incomplete_result.missing == [_U2]


def test_c_recon_4_unselected_absent_is_not_fatal() -> None:
    """C-recon-4: an unselected module absent from both current and previous is
    NOT missing and does not affect completeness."""
    result = reconcile(
        _REGISTRY,
        selected={"M"},
        current_fresh={_M.key},
        previous_available=set(),
    )
    assert result.complete is True
    assert _U1 not in result.missing
    assert _U2 not in result.missing


def test_unselected_absent_backfills_from_previous_when_available() -> None:
    """An unselected shard present only in the fallback is backfilled (stale),
    not missing -- the property that keeps unchanged coverage available."""
    result = reconcile(
        _REGISTRY,
        selected={"M"},
        current_fresh={_M.key},
        previous_available={_U1.key},
    )
    assert result.complete is True
    assert _U1 in result.stale
    assert result.missing == []


def _write_registry(path: Path, modules: list[dict[str, object]]) -> None:
    path.write_text(yaml.safe_dump({"modules": modules}), encoding="utf-8")


def test_parse_registry_expands_shard_count(tmp_path: Path) -> None:
    registry = tmp_path / "ci-module-registry.yml"
    _write_registry(
        registry,
        [
            {"module": "merge", "tier": "standard", "shard_count": 1},
            {"module": "status", "tier": "standard", "shard_count": 2},
        ],
    )
    shards = parse_registry(registry)
    basenames = {shard.basename for shard in shards}
    assert basenames == {
        "coverage-standard-merge-shard1-of-1.xml",
        "coverage-standard-status-shard1-of-2.xml",
        "coverage-standard-status-shard2-of-2.xml",
    }


def test_parse_registry_rejects_injection_in_module(tmp_path: Path) -> None:
    registry = tmp_path / "ci-module-registry.yml"
    _write_registry(
        registry,
        [{"module": "evil\nmissing=", "tier": "standard", "shard_count": 1}],
    )
    with pytest.raises(RegistryValidationError):
        parse_registry(registry)


def test_parse_registry_rejects_non_positive_shard_count(tmp_path: Path) -> None:
    registry = tmp_path / "ci-module-registry.yml"
    _write_registry(
        registry,
        [{"module": "merge", "tier": "standard", "shard_count": 0}],
    )
    with pytest.raises(RegistryValidationError):
        parse_registry(registry)


def test_read_selected_modules_absent_returns_none(tmp_path: Path) -> None:
    assert read_selected_modules(tmp_path / "nope.json") is None


def test_read_selected_modules_parses_list(tmp_path: Path) -> None:
    path = tmp_path / "selected-modules.json"
    path.write_text(json.dumps(["merge", "status"]), encoding="utf-8")
    assert read_selected_modules(path) == {"merge", "status"}


def test_read_selected_modules_malformed_returns_none(tmp_path: Path) -> None:
    path = tmp_path / "selected-modules.json"
    path.write_text(json.dumps({"not": "a list"}), encoding="utf-8")
    assert read_selected_modules(path) is None
