"""Unit tests for ``tool_surface.profiles.capability_matrix``."""

from __future__ import annotations

import pytest

from specify_cli.core.config import AI_CHOICES
from specify_cli.tool_surface.profiles import capability_matrix
from specify_cli.tool_surface.profiles.capability_matrix import (
    HARNESS_CAPABILITY_MATRIX,
    HarnessCapabilityRecord,
    _build_matrix,
    is_research_gap,
)

pytestmark = [pytest.mark.unit, pytest.mark.fast]


# ---------------------------------------------------------------------------
# HarnessCapabilityRecord dataclass
# ---------------------------------------------------------------------------


def test_harness_capability_record_is_frozen() -> None:
    record = HarnessCapabilityRecord("claude", True, "Native: .claude/agents/<id>.md")
    with pytest.raises((AttributeError, TypeError)):
        record.harness_key = "other"  # type: ignore[misc]


def test_harness_capability_record_fields() -> None:
    record = HarnessCapabilityRecord("windsurf", False, "No native primitive")
    assert record.harness_key == "windsurf"
    assert record.has_native_agent_primitive is False
    assert record.reason == "No native primitive"


# ---------------------------------------------------------------------------
# HARNESS_CAPABILITY_MATRIX completeness
# ---------------------------------------------------------------------------


def test_matrix_covers_every_ai_choices_key() -> None:
    """Every key in AI_CHOICES must appear in HARNESS_CAPABILITY_MATRIX."""
    missing = sorted(AI_CHOICES.keys() - HARNESS_CAPABILITY_MATRIX.keys())
    assert missing == [], f"Missing harness keys: {missing}"


def test_matrix_has_no_extra_keys_beyond_ai_choices() -> None:
    """Matrix should not silently contain keys absent from AI_CHOICES."""
    extra = sorted(HARNESS_CAPABILITY_MATRIX.keys() - AI_CHOICES.keys())
    assert extra == [], f"Extra harness keys not in AI_CHOICES: {extra}"


def test_matrix_values_are_harness_capability_records() -> None:
    for key, record in HARNESS_CAPABILITY_MATRIX.items():
        assert isinstance(record, HarnessCapabilityRecord), (
            f"{key!r} entry is not a HarnessCapabilityRecord"
        )


def test_matrix_key_matches_record_harness_key() -> None:
    for key, record in HARNESS_CAPABILITY_MATRIX.items():
        assert record.harness_key == key, (
            f"Matrix entry {key!r} has mismatched harness_key={record.harness_key!r}"
        )


def test_matrix_reasons_are_non_empty() -> None:
    for key, record in HARNESS_CAPABILITY_MATRIX.items():
        assert record.reason.strip(), f"Empty reason for harness {key!r}"


# ---------------------------------------------------------------------------
# Supported harnesses (has_native_agent_primitive=True)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "harness_key",
    ["claude", "copilot", "codex", "auggie", "q"],
)
def test_supported_harnesses_have_native_primitive(harness_key: str) -> None:
    record = HARNESS_CAPABILITY_MATRIX[harness_key]
    assert record.has_native_agent_primitive is True, (
        f"{harness_key!r} should have has_native_agent_primitive=True"
    )


@pytest.mark.parametrize(
    "harness_key",
    ["claude", "copilot", "codex", "auggie", "q"],
)
def test_supported_harnesses_are_not_research_gaps(harness_key: str) -> None:
    assert is_research_gap(harness_key) is False, (
        f"{harness_key!r} should not be a research gap"
    )


# ---------------------------------------------------------------------------
# Not-applicable harnesses (has_native_agent_primitive=False, researched)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "harness_key",
    [
        "windsurf",
        "cursor",
        "kiro",
        "gemini",
        "qwen",
        "opencode",
        "kilocode",
        "antigravity",
        "vibe",
        "pi",
        "letta",
        "llxprt",
    ],
)
def test_not_applicable_harnesses_lack_native_primitive(harness_key: str) -> None:
    record = HARNESS_CAPABILITY_MATRIX[harness_key]
    assert record.has_native_agent_primitive is False, (
        f"{harness_key!r} should have has_native_agent_primitive=False"
    )


@pytest.mark.parametrize(
    "harness_key",
    [
        "windsurf",
        "cursor",
        "kiro",
        "gemini",
        "qwen",
        "opencode",
        "kilocode",
        "vibe",
        "pi",
        "letta",
        "llxprt",
    ],
)
def test_not_applicable_harnesses_are_not_research_gaps(harness_key: str) -> None:
    assert is_research_gap(harness_key) is False, (
        f"{harness_key!r} should not be a research gap (it has been assessed)"
    )


# ---------------------------------------------------------------------------
# is_research_gap predicate
# ---------------------------------------------------------------------------


def test_is_research_gap_returns_true_for_missing_key() -> None:
    assert is_research_gap("unknown_harness_xyz") is True


def test_is_research_gap_returns_false_for_assessed_supported() -> None:
    assert is_research_gap("claude") is False


def test_is_research_gap_returns_false_for_assessed_not_applicable() -> None:
    assert is_research_gap("windsurf") is False


# ---------------------------------------------------------------------------
# Amazon Q is user-global
# ---------------------------------------------------------------------------


def test_amazon_q_harness_record_mentions_user_global_path() -> None:
    record = HARNESS_CAPABILITY_MATRIX["q"]
    assert "~/.aws" in record.reason or "user-global" in record.reason.lower(), (
        "Amazon Q reason should reference the user-global path"
    )


# ---------------------------------------------------------------------------
# Reason strings are generic (no machine-specific paths)
# ---------------------------------------------------------------------------


def test_reasons_do_not_contain_home_directory_expansion() -> None:
    """Reasons must use ~ notation or generic text, never expanded /Users/ paths."""
    import os

    home = os.path.expanduser("~")
    for key, record in HARNESS_CAPABILITY_MATRIX.items():
        assert home not in record.reason, (
            f"{key!r} reason contains an expanded home path: {record.reason!r}"
        )


# ---------------------------------------------------------------------------
# Research-gap completeness guard (_build_matrix auto-fills unassessed keys).
# All current AI_CHOICES keys are assessed, so the auto-fill branch is only
# reachable when a *new* harness is added without a record — we simulate that
# by injecting a synthetic key into AI_CHOICES and rebuilding the matrix.
# ---------------------------------------------------------------------------


def test_build_matrix_emits_research_gap_for_unassessed_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    synthetic = "brand-new-harness-xyz"
    patched = dict(AI_CHOICES)
    patched[synthetic] = "Brand New Harness (synthetic)"
    monkeypatch.setattr(capability_matrix, "AI_CHOICES", patched)

    matrix = _build_matrix()

    assert synthetic in matrix
    record = matrix[synthetic]
    assert record.harness_key == synthetic
    assert record.has_native_agent_primitive is False
    assert "research gap" in record.reason.lower()
