"""``ledger.retention`` limits for local event-log cleanup (#6610, FR-005).

Absent configuration reads as the defaults; an invalid value refuses
(fail closed) because the limits gate a destructive command.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from specify_cli.core.ledger_retention import (
    CONFIG_SOURCE,
    DEFAULT_KEEP_RUNS,
    DEFAULT_MAX_AGE_DAYS,
    DEFAULT_SOURCE,
    RetentionConfigError,
    RetentionLimits,
    load_retention_limits,
)

pytestmark = [pytest.mark.unit, pytest.mark.fast]


def _write_config(repo_root: Path, text: str) -> None:
    config = repo_root / ".kittify" / "config.yaml"
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text(text, encoding="utf-8")


def test_defaults_are_twenty_runs_and_thirty_days() -> None:
    assert (DEFAULT_KEEP_RUNS, DEFAULT_MAX_AGE_DAYS) == (20, 30)
    assert RetentionLimits() == RetentionLimits(keep_runs=20, max_age_days=30, source="default")


@pytest.mark.parametrize(
    "config_text",
    [
        None,
        "",
        "agents:\n  available: [claude]\n",
        "ledger:\n  projection: true\n",
        "ledger:\n  retention:\n",
        "ledger:\n",
    ],
    ids=["no-file", "empty-file", "no-ledger", "no-retention", "empty-retention", "empty-ledger"],
)
def test_absent_configuration_reads_as_defaults(tmp_path: Path, config_text: str | None) -> None:
    if config_text is not None:
        _write_config(tmp_path, config_text)
    limits = load_retention_limits(tmp_path)
    assert (limits.keep_runs, limits.max_age_days) == (20, 30)
    assert limits.source == DEFAULT_SOURCE == "default"


def test_explicit_values_are_read_from_the_project_config(tmp_path: Path) -> None:
    _write_config(tmp_path, "ledger:\n  retention:\n    keep_runs: 5\n    max_age_days: 0\n")
    limits = load_retention_limits(tmp_path)
    assert (limits.keep_runs, limits.max_age_days) == (5, 0)
    assert limits.source == CONFIG_SOURCE == ".kittify/config.yaml"


def test_a_partial_retention_block_keeps_the_other_default(tmp_path: Path) -> None:
    _write_config(tmp_path, "ledger:\n  retention:\n    max_age_days: 7\n")
    limits = load_retention_limits(tmp_path)
    assert (limits.keep_runs, limits.max_age_days, limits.source) == (20, 7, CONFIG_SOURCE)


def test_limits_serialize_to_the_contract_shape() -> None:
    assert RetentionLimits(keep_runs=3, max_age_days=4, source=CONFIG_SOURCE).to_dict() == {
        "keep_runs": 3,
        "max_age_days": 4,
        "source": ".kittify/config.yaml",
    }


@pytest.mark.parametrize(
    ("config_text", "fragment"),
    [
        ("ledger:\n  retention:\n    keep_runs: -1\n", "keep_runs"),
        ("ledger:\n  retention:\n    max_age_days: -3\n", "max_age_days"),
        ("ledger:\n  retention:\n    keep_runs: 'ten'\n", "keep_runs"),
        ("ledger:\n  retention:\n    max_age_days: 2.5\n", "max_age_days"),
        ("ledger:\n  retention:\n    keep_runs: true\n", "keep_runs"),
        ("ledger:\n  retention:\n    max_age_days: false\n", "max_age_days"),
        ("ledger:\n  retention:\n    keep_run: 3\n", "keep_run"),
        ("ledger:\n  retention: 30\n", "ledger.retention"),
        ("ledger:\n  retention: [1, 2]\n", "ledger.retention"),
        ("ledger: nope\n", "ledger"),
        ("ledger:\n  retention: {keep_runs: [\n", "config.yaml"),
    ],
    ids=[
        "negative-keep",
        "negative-age",
        "string",
        "float",
        "bool-true",
        "bool-false",
        "unknown-key",
        "retention-scalar",
        "retention-list",
        "ledger-scalar",
        "unparseable",
    ],
)
def test_invalid_configuration_refuses(tmp_path: Path, config_text: str, fragment: str) -> None:
    _write_config(tmp_path, config_text)
    with pytest.raises(RetentionConfigError) as excinfo:
        load_retention_limits(tmp_path)
    assert fragment in str(excinfo.value)
    assert isinstance(excinfo.value, ValueError)
