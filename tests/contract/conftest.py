"""Shared fixtures for contract shape conformance tests.

Loads expected shapes from the vendored upstream_contract.json so that
all contract tests derive their assertions from a single source of truth.
"""

from __future__ import annotations

import json
from importlib.resources import files
from pathlib import Path
from typing import Any

import pytest


def _load_upstream_contract() -> dict:
    """Load the vendored upstream contract JSON."""
    contract_path = files("specify_cli.core").joinpath("upstream_contract.json")
    return json.loads(contract_path.read_text(encoding="utf-8"))


_CONTRACT = _load_upstream_contract()


@pytest.fixture()
def upstream_contract() -> dict:
    """Full upstream contract dict."""
    return _CONTRACT


@pytest.fixture()
def canonical_envelope_fields() -> set[str]:
    """Set of required envelope fields from the 3.0.0 contract."""
    return set(_CONTRACT["envelope"]["required_fields"])


@pytest.fixture()
def forbidden_envelope_fields() -> set[str]:
    """Set of fields that must never appear in an event envelope."""
    return set(_CONTRACT["envelope"]["forbidden_fields"])


@pytest.fixture()
def canonical_body_sync_fields() -> set[str]:
    """Required body sync fields from the 3.0.0 contract."""
    return set(_CONTRACT["body_sync"]["required_fields"])


@pytest.fixture()
def forbidden_body_sync_fields() -> set[str]:
    """Forbidden body sync fields from the 3.0.0 contract."""
    return set(_CONTRACT["body_sync"]["forbidden_fields"])


@pytest.fixture()
def canonical_tracker_bind_fields() -> set[str]:
    """Required tracker bind fields from the 3.0.0 contract."""
    return set(_CONTRACT["tracker_bind"]["required_fields"])


@pytest.fixture()
def orchestrator_api_contract() -> dict:
    """Orchestrator API contract section."""
    return _CONTRACT["orchestrator_api"]


def pytest_terminal_summary(terminalreporter: Any) -> None:
    """Print the timing margin lines that the Ops timed cases record, so a passing run (also under xdist) shows its minimum and margin."""
    lines = [
        value
        for reports in terminalreporter.stats.values()
        for report in reports
        for name, value in getattr(report, "user_properties", ())
        if name == "timing_margin"
    ]
    if lines:
        terminalreporter.write_sep("-", "timing margins (minimum of the cold repeats)")
        for line in lines:
            terminalreporter.write_line(line)
