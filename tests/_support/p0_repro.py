"""Nightly-only red-first reproductions of open P0 bugs (``p0_repro`` marker).

An open ``priority:P0`` bug carries an issue-pinned, red-first reproduction
test (ADR 2026-07-17-1). That test fails until the bug is fixed, so it must
never run where a red would block an unrelated change: it is held out of every
per-PR lane, ``make test-fast``/``make test-full`` and every other nightly lane,
and runs only in the dedicated ``p0-repro`` job of
``.github/workflows/ci-nightly.yml``, which sets
:data:`RUN_P0_REPRO_ENV_VAR` and selects ``-m p0_repro``.

Usage::

    @pytest.mark.p0_repro(issue=5613)
    def test_resume_does_not_drop_approved_content(...): ...

The issue number is mandatory. A missing or malformed one is a collection
error in every run, including per-PR runs, so a bad pin is caught before it
reaches the nightly. When such a test fails, its report carries an
``[OPEN P0 #N]`` banner naming the issue; when it passes, the terminal summary
says the marker should be removed (the fix PR removes it, which puts the test
in the per-PR lanes as an ordinary guard). A reproduction that skips, in its
call phase or already in setup (``skipif``, a fixture skip), never reached a
verdict, so the summary lists it too. Both notices are informational: a
reproduction that passes or skips does not fail the nightly job.

The pass/skip notices are derived on the *controller* from the reports it
receives (the pinned issue travels on ``report.user_properties``), so they
appear under ``pytest-xdist`` too, where ``pytest_runtest_makereport`` runs on
the workers and a stash written there never reaches the terminal summary.

This module is a pytest plugin, registered by the root ``tests/conftest.py``
through ``pytest_plugins``; the decisions are pure helpers so they can be tested
without a pytest session. See
``docs/development/reference/red-main-and-release-readiness.md``.
"""

from __future__ import annotations

import os
from collections.abc import Generator, Iterable, Mapping

import pytest

#: Opt-in env var. Only the literal ``"1"`` runs ``p0_repro`` tests.
RUN_P0_REPRO_ENV_VAR = "SPEC_KITTY_RUN_P0_REPRO"

#: The marker name.
P0_REPRO_MARKER = "p0_repro"

#: Key under which the pinned issue is recorded in ``item.user_properties``
#: (emitted as a ``<property>`` in the JUnit XML the nightly summary reads).
ISSUE_PROPERTY = "p0_issue"

ISSUE_URL = "https://github.com/spec-kitty/spec-kitty/issues/{issue}"


def p0_repro_opted_in(environ: Mapping[str, str]) -> bool:
    """Return whether ``p0_repro`` tests should run in this session.

    Strict: only the exact string ``"1"`` opts in, so anything else keeps the
    reproductions out of the run (fail-closed to *not run*).
    """
    return environ.get(RUN_P0_REPRO_ENV_VAR) == "1"


def pinned_issue(marker: pytest.Mark) -> int | None:
    """Return the issue number a ``p0_repro`` marker pins, or ``None`` if invalid.

    Valid forms: ``p0_repro(issue=N)`` or ``p0_repro(N)`` with ``N`` a positive
    ``int`` (``bool`` is rejected).
    """
    raw: object = marker.kwargs.get("issue", marker.args[0] if marker.args else None)
    if isinstance(raw, bool) or not isinstance(raw, int) or raw <= 0:
        return None
    return raw


def invalid_pins(items: Iterable[pytest.Item]) -> list[str]:
    """Node ids of ``p0_repro`` items whose marker does not pin a valid issue."""
    return [item.nodeid for item in items if (marker := item.get_closest_marker(P0_REPRO_MARKER)) is not None and pinned_issue(marker) is None]


def failure_banner(issue: int) -> str:
    """The banner attached to a failing reproduction's report."""
    return (
        f"[OPEN P0 #{issue}] This is the red-first reproduction of open P0 issue "
        f"#{issue} ({ISSUE_URL.format(issue=issue)}). It is EXPECTED to fail until "
        "that bug is fixed; it runs only in the nightly p0-repro lane. The fix PR "
        "removes the p0_repro marker so the test becomes a per-PR guard."
    )


def passing_notice(issue: int, nodeid: str) -> str:
    """The summary line for a reproduction that now passes."""
    return (
        f"[P0 #{issue} REPRO PASSES] {nodeid} no longer reproduces the bug: if the fix "
        "has landed, remove its p0_repro marker so it runs per PR as a guard; "
        "otherwise the reproduction is broken."
    )


def skipped_notice(issue: int, nodeid: str) -> str:
    """The summary line for a reproduction that skipped without a verdict."""
    return (
        f"[P0 #{issue} REPRO SKIPPED] {nodeid} skipped in its call phase and did not run to a "
        f"verdict, so open P0 issue #{issue} is neither confirmed nor cleared: fix the skip or the reproduction."
    )


def _reaches_no_verdict_in_setup(report: pytest.TestReport) -> bool:
    """Whether the test was skipped before its call phase could run."""
    return report.when == "setup" and report.skipped


def reproduction_notice(report: pytest.TestReport) -> str | None:
    """The summary line a report earns, or ``None`` if it earns none.

    Derived purely from the report (the pinned issue rides on
    ``report.user_properties``), so it works on an xdist controller. A failure
    needs no notice: it is already bannered and fails the lane. A skip counts
    in the call phase and in setup, where ``skipif`` and fixture skips land.
    """
    if not (_reaches_no_verdict_in_setup(report) or (report.when == "call" and (report.passed or report.skipped))):
        return None
    issue = next((value for name, value in report.user_properties if name == ISSUE_PROPERTY and isinstance(value, int)), None)
    if issue is None:
        return None
    return passing_notice(issue, report.nodeid) if report.passed else skipped_notice(issue, report.nodeid)


# ---------------------------------------------------------------------------
# pytest hooks
# ---------------------------------------------------------------------------


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Reject invalid pins everywhere; deselect reproductions unless opted in."""
    bad = invalid_pins(items)
    if bad:
        raise pytest.UsageError("p0_repro marker must pin a positive issue number, e.g. @pytest.mark.p0_repro(issue=5613); invalid on: " + ", ".join(bad))
    if p0_repro_opted_in(os.environ):
        return
    held = [item for item in items if item.get_closest_marker(P0_REPRO_MARKER)]
    if held:
        held_ids = {id(item) for item in held}
        items[:] = [item for item in items if id(item) not in held_ids]
        config.hook.pytest_deselected(items=held)


@pytest.hookimpl(wrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo[None]) -> Generator[None, pytest.TestReport, pytest.TestReport]:
    """Pin the issue to a reproduction's verdict report and banner a failure.

    ``item.user_properties`` feeds the JUnit ``<property>`` (read from the
    teardown report); the call report gets its own copy because that is the
    report the controller classifies in :func:`pytest_terminal_summary`.
    """
    del call
    report = yield
    marker = item.get_closest_marker(P0_REPRO_MARKER)
    issue = pinned_issue(marker) if marker is not None else None
    if issue is not None and (report.when == "call" or _reaches_no_verdict_in_setup(report)):
        item.user_properties.append((ISSUE_PROPERTY, issue))
        report.user_properties.append((ISSUE_PROPERTY, issue))
        if report.failed:
            # A section, not a rewrite of longrepr: the JUnit failure message and
            # the nightly summary's first line must stay the real assertion.
            report.sections.append((f"OPEN P0 #{issue}", failure_banner(issue)))
    return report


def pytest_terminal_summary(terminalreporter: pytest.TerminalReporter) -> None:
    """List reproductions that no longer reproduce their bug, or never ran to a verdict.

    Reads the reports the (controller's) terminal reporter collected, so the
    result is the same with and without ``pytest-xdist``.
    """
    reports = [r for outcome in ("passed", "skipped") for r in terminalreporter.stats.get(outcome, []) if isinstance(r, pytest.TestReport)]
    notices = [notice for report in reports if (notice := reproduction_notice(report)) is not None]
    if notices:
        terminalreporter.section("p0_repro reproductions without a failing verdict")
        for line in notices:
            terminalreporter.write_line(line)
