"""Unit tests for ORG_NAME / LOCAL_PATH validation (WP01 T001/T002)."""

from __future__ import annotations

import pytest

from specify_cli.doctrine.template_render.validation import (
    RULE_LOCAL_EMPTY,
    RULE_LOCAL_PLACEHOLDER,
    RULE_ORG_FORMAT,
    RULE_ORG_LENGTH,
    RULE_ORG_PLACEHOLDER,
    RULE_ORG_RESERVED,
    validate_local_path,
    validate_org_name,
)

pytestmark = [pytest.mark.unit, pytest.mark.fast]


@pytest.mark.parametrize(
    ("value", "rule_id"),
    [
        ("Acme", RULE_ORG_FORMAT),
        ("acme_corp", RULE_ORG_FORMAT),
        ("-acme", RULE_ORG_FORMAT),
        ("acme-", RULE_ORG_FORMAT),
        ("acme--corp", RULE_ORG_FORMAT),
        ("1acme", RULE_ORG_FORMAT),
        ("a", RULE_ORG_LENGTH),
        ("a" * 65, RULE_ORG_LENGTH),
        ("doctrine-org", RULE_ORG_RESERVED),
        ("Doctrine-Org", RULE_ORG_RESERVED),
        ("ORG_NAME", RULE_ORG_PLACEHOLDER),
        ("{{ORG_NAME}}", RULE_ORG_PLACEHOLDER),
        ("acme-TODO", RULE_ORG_PLACEHOLDER),
    ],
)
def test_validate_org_name_rejects_invalid(value: str, rule_id: str) -> None:
    result = validate_org_name(value)
    assert result.ok is False
    assert result.rule_id == rule_id
    assert result.message is not None
    assert value in result.message
    assert rule_id in result.message


@pytest.mark.parametrize(
    "value",
    ["ac", "acme", "acme-corp", "a1", "ab-c0", "a" * 64],
)
def test_validate_org_name_accepts_valid(value: str) -> None:
    result = validate_org_name(value)
    assert result.ok is True
    assert result.rule_id is None


@pytest.mark.parametrize(
    ("value", "rule_id"),
    [
        ("", RULE_LOCAL_EMPTY),
        ("   ", RULE_LOCAL_EMPTY),
        ("LOCAL_PATH", RULE_LOCAL_PLACEHOLDER),
        ("{{LOCAL_PATH}}", RULE_LOCAL_PLACEHOLDER),
        ("pack/TODO", RULE_LOCAL_PLACEHOLDER),
    ],
)
def test_validate_local_path_rejects_invalid(value: str, rule_id: str) -> None:
    result = validate_local_path(value)
    assert result.ok is False
    assert result.rule_id == rule_id
    assert result.message is not None


@pytest.mark.parametrize("value", ["pack", ".", "path/to/pack", "~/org/pack"])
def test_validate_local_path_accepts_valid(value: str) -> None:
    result = validate_local_path(value)
    assert result.ok is True
    assert result.rule_id is None
