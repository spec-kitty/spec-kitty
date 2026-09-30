"""#3143: ``pytest.ini`` must carry the single per-test timeout authority.

The default per-test timeout lives in exactly one place -- the ``timeout`` ini
key in ``pytest.ini`` -- so every surface that reads that file (the Linux module
shards, the Windows job, local ``pytest`` runs, and the ``make`` targets) gets a
uniform per-test timeout. Before #3143 the only ``--timeout`` flags lived in the
retired ``ci-quality.yml`` and later only in the Makefile serial passes, leaving
Windows and local runs with no per-test timeout at all -- a hang was killed by a
job-level ``timeout-minutes`` with no counter and no named test.

Nothing else asserted the ini default stayed put: deleting the ``timeout`` line,
or adding a ``timeout_method`` (which would defeat the deliberate signal/thread
per-platform fallback), would not fail any other test. This test parses
``pytest.ini`` with ``configparser`` -- the same approach
``test_pytest_ini_durations_addopts.py`` uses -- and pins the invariant.

This is a plain invariant, not an allowlist: there is one correct value.
"""

from __future__ import annotations

import configparser
from pathlib import Path

import pytest

pytestmark = [pytest.mark.architectural]

_REPO_ROOT = Path(__file__).resolve().parents[2]
_EXPECTED_TIMEOUT = "240"


def _pytest_ini() -> configparser.ConfigParser:
    parser = configparser.ConfigParser(interpolation=None)
    parser.read(_REPO_ROOT / "pytest.ini", encoding="utf-8")
    return parser


def test_default_per_test_timeout_is_pinned() -> None:
    parser = _pytest_ini()
    timeout = parser.get("pytest", "timeout", fallback=None)
    assert timeout is not None, (
        "pytest.ini's [pytest] section is missing the `timeout` key -- the "
        "single per-test timeout authority (#3143). Without it, hanging tests "
        "are only killed by a job-level timeout-minutes, with no named test."
    )
    assert timeout.strip() == _EXPECTED_TIMEOUT, (
        f"pytest.ini's per-test `timeout` default drifted to {timeout!r}; it must stay {_EXPECTED_TIMEOUT} (see the rationale comment in pytest.ini)."
    )


def test_timeout_method_stays_unset_for_platform_fallback() -> None:
    """`timeout_method` must be absent so pytest-timeout picks per platform:
    signal (SIGALRM) on POSIX -- the counted, test-named failure -- and the
    thread fallback on Windows, which has no SIGALRM. Pinning a method here
    would break one platform or the other (#3143)."""
    parser = _pytest_ini()
    method = parser.get("pytest", "timeout_method", fallback=None)
    assert method is None, (
        f"pytest.ini pins `timeout_method` to {method!r}; it must stay UNSET so pytest-timeout falls back to signal on POSIX and thread on Windows (#3143)."
    )


def test_timeout_value_is_read_as_a_key_not_a_substring() -> None:
    """Non-vacuousness control: the assertion reads the parsed ini key, so a
    file that merely mentions ``240`` elsewhere (e.g. in a comment) does not
    satisfy it -- proving this test pins the real option, not a substring."""
    parser = configparser.ConfigParser(interpolation=None)
    parser.read_string("[pytest]\n# a comment that mentions 240\naddopts = -q\n")
    assert parser.get("pytest", "timeout", fallback=None) is None
