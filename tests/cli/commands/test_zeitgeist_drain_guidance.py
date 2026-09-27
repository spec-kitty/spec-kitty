"""Every relay CLI subcommand pre-flights
``hosted_posture.require_drain("relay")`` and maps a drain-off refusal to
one clean guidance line -- never a traceback, never "not checked out", and
never a credential-store/subscription read.

Covers ``status``/``watch``/``activity``/``send``/``reply``/``read``/
``inbox``/``outbox approve`` under the ``drain_off`` fixture (see
``tests/conftest.py``).
"""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from specify_cli.cli.commands.zeitgeist import app
from specify_cli.core import hosted_posture

pytestmark = pytest.mark.fast

runner = CliRunner()

_REPO = "github.com/acme/spec-kitty"


def _forbid_credential_and_subscription_reads(monkeypatch: pytest.MonkeyPatch) -> None:
    """The NFR-003 "0 credential reads" proof shared by every case below: if
    the pre-flight did not fire first, one of these would be reached."""
    from specify_cli.zeitgeist_client import credentials, subscription

    def _raise_credentials(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("credentials.load must not be called when drain is off")

    def _raise_resolve_stream(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("subscription.resolve_stream must not be called when drain is off")

    monkeypatch.setattr(credentials, "load", _raise_credentials)
    monkeypatch.setattr(subscription, "resolve_stream", _raise_resolve_stream)


def _assert_clean_guidance(output: str) -> None:
    assert "Live drain is off" in output
    assert "Traceback" not in output
    assert "not checked out" not in output.lower()
    # Exactly one logical line of guidance -- soft_wrap=True (review cycle 1,
    # non-blocking note) keeps rich from wrapping it across terminal columns.
    lines = [line for line in output.splitlines() if line.strip()]
    assert len(lines) == 1, f"expected exactly one guidance line, got {lines!r}"


@pytest.mark.parametrize(
    ("args", "expected_exit_code"),
    [
        (["status", _REPO], 0),
        (["watch", _REPO], 1),
        (["activity", _REPO], 1),
        (["send", "message", "hello", "--audience", "team"], 1),
        (["reply", "some-message-id", "hello"], 1),
        (["read"], 1),
        (["inbox"], 1),
    ],
)
def test_relay_subcommand_shows_one_guidance_line_and_reads_no_credential(
    drain_off: None, monkeypatch: pytest.MonkeyPatch, args: list[str], expected_exit_code: int
) -> None:
    _forbid_credential_and_subscription_reads(monkeypatch)

    result = runner.invoke(app, args)

    assert result.exit_code == expected_exit_code, result.stdout
    _assert_clean_guidance(result.stdout)


def test_outbox_approve_shows_one_guidance_line_and_reads_no_credential(drain_off: None, monkeypatch: pytest.MonkeyPatch) -> None:
    _forbid_credential_and_subscription_reads(monkeypatch)
    from specify_cli.zeitgeist_client import outbox_approval

    def _raise_approve(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("outbox_approval.approve must not be called when drain is off")

    monkeypatch.setattr(outbox_approval, "approve", _raise_approve)

    result = runner.invoke(app, ["outbox", "approve", "some-item-id"])

    assert result.exit_code == 1, result.stdout
    _assert_clean_guidance(result.stdout)


def test_outbox_list_show_reject_revoke_are_not_pre_flighted(drain_off: None) -> None:
    """R-3: only ``outbox approve`` (the operator-typed publication act) is
    gated -- ``list``/``show``/``reject``/``revoke`` all reach their own
    ordinary (non-drain) handling unchanged under drain-off."""
    result = runner.invoke(app, ["outbox", "list"])
    assert result.exit_code == 0
    assert "Live drain is off" not in result.stdout

    result = runner.invoke(app, ["outbox", "show", "some-item-id"])
    assert result.exit_code == 1
    assert "no item" in result.stdout
    assert "Live drain is off" not in result.stdout

    # reject/revoke reach outbox_approval's own NotFound (no such item) --
    # never the drain guidance, and never the human-gesture prompt either,
    # since the not-found check runs first.
    result = runner.invoke(app, ["outbox", "reject", "some-item-id"])
    assert result.exit_code == 1
    assert "no item" in result.stdout
    assert "Live drain is off" not in result.stdout

    result = runner.invoke(app, ["outbox", "revoke", "some-item-id"])
    assert result.exit_code == 1
    assert "no item" in result.stdout
    assert "Live drain is off" not in result.stdout


def test_drain_disabled_guidance_stays_one_line_at_80_columns(drain_off: None) -> None:
    """FR-002/#3115: ``tests/conftest.py``'s ``_plain_cli_console_seam`` pins
    the shared CLI console to a wide render surface (``_RENDER_WIDTH``) for
    every test, so ``_assert_clean_guidance`` above never actually exercises
    a narrow terminal. The guidance line here is 100+ characters -- at a
    realistic 80-column terminal, only ``soft_wrap=True`` on the
    ``console.print`` call in ``_report_drain_disabled`` keeps it as one
    logical line instead of rich wrapping it across two. Removing
    ``soft_wrap=True`` must fail this test.
    """
    from specify_cli.cli.console import console

    original_size = (console._width, console._height)
    console.size = (80, 25)
    try:
        result = runner.invoke(app, ["status", _REPO])
    finally:
        console._width, console._height = original_size

    assert result.exit_code == 0, result.stdout
    _assert_clean_guidance(result.stdout)


def test_drain_disabled_message_reuses_the_hosted_posture_guidance_constant(drain_off: None) -> None:
    """Sonar S1192: the CLI must never hand-roll a second copy of the
    guidance wording -- it comes straight from DRAIN_GUIDANCE_LINE."""
    result = runner.invoke(app, ["status", _REPO])
    assert result.exit_code == 0
    reason = "repository scope is off (test fixture)"  # the drain_off fixture's own DrainPosture.reason
    assert hosted_posture.DRAIN_GUIDANCE_LINE.format(reason=reason) in result.stdout


def test_status_json_stays_parseable_under_drain_off(drain_off: None) -> None:
    """A2: ``zeitgeist status --json`` under drain-off must still emit
    parseable JSON -- not the plain-text guidance line every other
    drain-gated relay command prints -- while keeping the exit code."""
    import json

    result = runner.invoke(app, ["status", _REPO, "--json"])

    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["drain"]["enabled"] is False
    assert payload["drain"]["reason"] == "repository scope is off (test fixture)"
