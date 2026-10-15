"""E2E contract test for ``agent mission create --json`` clean output.

This test verifies the FR-008 / FR-009 contract IN-PROCESS rather than
shelling out to the installed ``spec-kitty`` binary, because the
installed CLI in the agent's PATH may be the previous release without
WP06's fixes (an upgrade race that would make subprocess-based tests
flake).

The contract has observable invariants:

1. The JSON success path of ``agent mission create`` calls
   ``mark_invocation_succeeded()`` AFTER the final JSON write.
2. Repeated diagnostics within one invocation are gated by
   ``report_once(...)`` so a second call does not log.

(Invariant 3 of the original set — structured non-fatal final-sync shutdown
diagnostics — died with the sync transport's ``BackgroundSyncService``, issue
#5.)

We verify each of these in the smallest in-process way that proves the
operator-visible contract holds, without depending on the installed
binary version or the network.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Iterator

import pytest

from specify_cli.diagnostics import (
    invocation_succeeded,
    mark_invocation_succeeded,
    report_once,
    reset_for_invocation,
)


pytestmark = [pytest.mark.e2e]

ANSI_RED_RE = re.compile(r"\x1b\[(?:1;)?31m|\[red\]|\[bold red\]", re.IGNORECASE)
NOT_AUTH_RE = re.compile(r"Not authenticated, skipping sync")


@pytest.fixture(autouse=True)
def _isolate_diagnostic_state() -> Iterator[None]:
    reset_for_invocation()
    yield
    reset_for_invocation()


def test_create_mission_calls_mark_invocation_succeeded_after_json_write() -> None:
    """The JSON success path must call ``mark_invocation_succeeded()``.

    Verified by inspecting the source: there must be exactly one call
    to ``mark_invocation_succeeded()`` in the agent/mission/ command
    surface, and it must appear after the final ``_emit_json(...)`` of
    the create-payload success branch.

    The ``create`` command body (and its ``mark_invocation_succeeded()``
    call) was relocated by the #2056 mission.py decomposition into the
    ``mission_create`` seam module; scan that file.
    """
    from pathlib import Path

    from specify_cli.cli.commands.agent import mission_create as mission_module

    source_path = Path(mission_module.__file__)
    source = source_path.read_text(encoding="utf-8")

    # Exactly one call site in the mission command surface.
    matches = list(re.finditer(r"mark_invocation_succeeded\(\s*\)", source))
    assert len(matches) == 1, (
        f"Expected exactly one mark_invocation_succeeded() call site in "
        f"{source_path}; found {len(matches)}."
    )

    # It must appear after the final JSON write of the create payload —
    # i.e. after ``_emit_json(_inject_branch_contract(_build_create_payload(...``
    create_payload_emit_re = re.compile(
        r"_emit_json\(\s*_inject_branch_contract\(\s*_build_create_payload",
    )
    emit_match = create_payload_emit_re.search(source)
    assert emit_match is not None, (
        "Could not locate the create_payload _emit_json(...) call in mission_create.py; "
        "either the call moved or the JSON success path was renamed."
    )
    assert matches[0].start() > emit_match.start(), (
        "mark_invocation_succeeded() must appear AFTER the JSON write, "
        "not before."
    )


def test_not_authenticated_warning_is_deduplicated_in_process(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Direct exercise of the ``report_once`` gate.

    The former callersites lived in ``sync/background.py`` (deleted with the
    transport, issue #5); the surviving contract is the gate itself — two
    consecutive reports with the same cause key log only the first.
    """
    sync_logger = logging.getLogger("specify_cli.diagnostics.contract-pin")

    with caplog.at_level(logging.WARNING, logger="specify_cli.diagnostics.contract-pin"):
        # First auth miss — should log once.
        if report_once("sync.unauthenticated"):
            sync_logger.warning("Not authenticated, skipping sync")
        # Second auth miss in the same invocation — must be silenced.
        if report_once("sync.unauthenticated"):
            sync_logger.warning("Not authenticated, skipping sync")

    not_auth_messages = [
        rec for rec in caplog.records if NOT_AUTH_RE.search(rec.message)
    ]
    assert len(not_auth_messages) <= 1, (
        f"Expected ≤1 'Not authenticated' diagnostic; got {len(not_auth_messages)}."
    )


def test_invocation_success_flag_round_trips() -> None:
    """Sanity: the success flag flips on mark and the invariant holds."""
    assert invocation_succeeded() is False
    mark_invocation_succeeded()
    assert invocation_succeeded() is True


def test_no_red_ansi_after_success_marker(capsys: pytest.CaptureFixture[str]) -> None:
    """If success was marked, downstream code that respects the gate
    must not emit any red ANSI to stderr.

    This test asserts the discipline at the contract layer: after
    ``mark_invocation_succeeded()`` is called, no further ``[red]`` or
    raw ANSI red escapes should land on stderr from any of our
    cooperating modules. Since this is an in-process unit, we simulate
    the post-success state and assert that the well-behaved gate
    produces clean stderr.
    """
    import sys

    mark_invocation_succeeded()

    # Simulate the post-success shutdown path: no red lines should be
    # written. This stands in for "no atexit warning paints red on
    # stderr after the JSON payload."
    if not invocation_succeeded():
        # Failure path — would emit a red warning.
        print("[red]Shutdown error[/red]", file=sys.stderr)

    captured = capsys.readouterr()
    assert not ANSI_RED_RE.search(captured.err), (
        f"Found red styling on stderr after mark_invocation_succeeded():\n"
        f"{captured.err}"
    )
