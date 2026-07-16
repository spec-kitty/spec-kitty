"""ORG_NAME / LOCAL_PATH validation for doctrine template render."""

from __future__ import annotations

import re
from dataclasses import dataclass

ORG_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9]*(-[a-z0-9]+)*$")
ORG_NAME_MIN_LEN = 2
ORG_NAME_MAX_LEN = 64
RESERVED_ORG_NAME = "doctrine-org"

RULE_ORG_FORMAT = "org_name.format"
RULE_ORG_LENGTH = "org_name.length"
RULE_ORG_RESERVED = "org_name.reserved"
RULE_ORG_PLACEHOLDER = "org_name.placeholder"
RULE_LOCAL_EMPTY = "local_path.empty"
RULE_LOCAL_PLACEHOLDER = "local_path.placeholder"


@dataclass(frozen=True, slots=True)
class ValidationResult:
    """Outcome of a single validation check."""

    ok: bool
    rule_id: str | None = None
    message: str | None = None


def _fail(rule_id: str, message: str) -> ValidationResult:
    return ValidationResult(ok=False, rule_id=rule_id, message=message)


def _ok() -> ValidationResult:
    return ValidationResult(ok=True)


def validate_org_name(value: str) -> ValidationResult:
    """Validate ORG_NAME per the doctrine-template downstream CLI contract.

    Fail-closed: never sanitises (no auto-lowercasing / hyphenating).
    """
    if "TODO" in value or value in {"ORG_NAME", "{{ORG_NAME}}"}:
        return _fail(
            RULE_ORG_PLACEHOLDER,
            f"ORG_NAME rejected as placeholder ({RULE_ORG_PLACEHOLDER}): {value!r}",
        )
    if not (ORG_NAME_MIN_LEN <= len(value) <= ORG_NAME_MAX_LEN):
        return _fail(
            RULE_ORG_LENGTH,
            f"ORG_NAME length must be {ORG_NAME_MIN_LEN}-{ORG_NAME_MAX_LEN} "
            f"({RULE_ORG_LENGTH}): {value!r} (len={len(value)})",
        )
    if value.casefold() == RESERVED_ORG_NAME:
        return _fail(
            RULE_ORG_RESERVED,
            f"ORG_NAME must not equal reserved base pack name "
            f"{RESERVED_ORG_NAME!r} ({RULE_ORG_RESERVED}): {value!r}",
        )
    if ORG_NAME_PATTERN.fullmatch(value) is None:
        return _fail(
            RULE_ORG_FORMAT,
            f"ORG_NAME must be lowercase kebab-case "
            f"({RULE_ORG_FORMAT}): {value!r}",
        )
    return _ok()


def validate_local_path(value: str) -> ValidationResult:
    """Validate LOCAL_PATH as a non-empty non-placeholder path string."""
    if value.strip() == "":
        return _fail(
            RULE_LOCAL_EMPTY,
            f"LOCAL_PATH must be a non-empty path string ({RULE_LOCAL_EMPTY}): {value!r}",
        )
    if "TODO" in value or value in {"LOCAL_PATH", "{{LOCAL_PATH}}"}:
        return _fail(
            RULE_LOCAL_PLACEHOLDER,
            f"LOCAL_PATH rejected as placeholder ({RULE_LOCAL_PLACEHOLDER}): {value!r}",
        )
    return _ok()
