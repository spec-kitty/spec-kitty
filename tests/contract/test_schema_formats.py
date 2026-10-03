"""Behaviour of ``contracts/tools/schema_formats.py``, the one date-time format policy (plan D-P14).

``jsonschema`` enforces ``format: date-time`` only when ``rfc3339-validator`` is
importable, and a bare ``FormatChecker()`` also switches on other formats exactly
when optional extras are present. The policy module therefore builds an empty
checker and registers one explicit stdlib check, so a verdict never depends on
the environment. Environment independence is tested in child interpreters, not
with a ``sys.modules`` stub, because a stub installed after ``jsonschema`` is
imported cannot change an already registered checker.
"""

from __future__ import annotations

import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType

import pytest
from jsonschema import Draft202012Validator, FormatChecker

from tests.contract._loader import load_tool

pytestmark = [pytest.mark.contract, pytest.mark.fast, pytest.mark.corpus]

MODULE_PATH = Path(__file__).resolve().parents[2] / "contracts" / "tools" / "schema_formats.py"
MALFORMED = "2026-13-45T99:99:99"
SCHEMA = {"type": "string", "format": "date-time"}

# Runs in a child interpreter: optionally hide the two optional validators from the
# import system BEFORE jsonschema is imported, then validate one malformed timestamp.
CHILD_SCRIPT = """
import importlib.util
import sys

if sys.argv[1] == "block":
    class _Block:
        def find_spec(self, name, path=None, target=None):
            if name.split(".")[0] in ("rfc3339_validator", "jsonpointer"):
                raise ImportError("blocked for the test: " + name)
            return None

    sys.meta_path.insert(0, _Block())

import jsonschema

if sys.argv[2] == "policy":
    spec = importlib.util.spec_from_file_location("schema_formats_child", sys.argv[3])
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    checker = module.FORMAT_CHECKER
else:
    checker = jsonschema.FormatChecker()

validator = jsonschema.Draft202012Validator({"type": "string", "format": "date-time"}, format_checker=checker)
print("rejected" if list(validator.iter_errors(sys.argv[4])) else "accepted")
"""


@pytest.fixture(scope="module")
def formats() -> Iterator[ModuleType]:
    with pytest.MonkeyPatch.context() as mp:
        yield load_tool(mp, MODULE_PATH, "schema_formats_under_test")


def _child_verdict(*, blocked: bool, policy: bool) -> str:
    result = subprocess.run(
        [sys.executable, "-c", CHILD_SCRIPT, "block" if blocked else "open", "policy" if policy else "bare", str(MODULE_PATH), MALFORMED],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


def test_registered_formats_are_exactly_date_time(formats: ModuleType) -> None:
    assert isinstance(formats.FORMAT_CHECKER, FormatChecker)
    assert set(formats.FORMAT_CHECKER.checkers) == {"date-time"}


@pytest.mark.parametrize(
    "value",
    [
        "2026-10-02T11:00:37+00:00",
        "2026-10-02T11:00:37Z",
        "2026-10-02T11:00:37.142336Z",
        "2026-10-02t11:00:37-05:30",
        "2016-12-31T23:59:60Z",
    ],
)
def test_well_formed_timestamps_are_accepted(formats: ModuleType, value: str) -> None:
    validator = Draft202012Validator(SCHEMA, format_checker=formats.FORMAT_CHECKER)

    assert list(validator.iter_errors(value)) == []


@pytest.mark.parametrize(
    "value",
    [
        MALFORMED,
        "2026-13-02T11:00:37Z",
        "2026-02-30T11:00:37Z",
        "2026-10-02T24:00:00Z",
        "2026-10-02T11:60:00Z",
        "2026-10-02 11:00:37Z",
        "2026-10-02T11:00:37",
        "2026-10-02",
        "yesterday",
        "",
    ],
)
def test_malformed_timestamps_are_rejected(formats: ModuleType, value: str) -> None:
    validator = Draft202012Validator(SCHEMA, format_checker=formats.FORMAT_CHECKER)

    assert len(list(validator.iter_errors(value))) == 1


def test_non_strings_are_not_format_checked(formats: ModuleType) -> None:
    assert formats.FORMAT_CHECKER.conforms(12345, "date-time") is True


def test_other_formats_are_not_enabled(formats: ModuleType) -> None:
    validator = Draft202012Validator({"type": "string", "format": "uri"}, format_checker=formats.FORMAT_CHECKER)

    assert list(validator.iter_errors("not a uri at all")) == []


def test_verdict_is_the_same_with_and_without_the_optional_validators() -> None:
    open_verdict = _child_verdict(blocked=False, policy=True)
    blocked_verdict = _child_verdict(blocked=True, policy=True)

    assert (open_verdict, blocked_verdict) == ("rejected", "rejected")


def test_the_environment_test_has_teeth_a_bare_checker_accepts_when_the_validator_is_missing() -> None:
    """Mutation check (D-P14): swap the policy for a bare ``FormatChecker()`` and the verdict changes."""
    assert _child_verdict(blocked=True, policy=False) == "accepted"
