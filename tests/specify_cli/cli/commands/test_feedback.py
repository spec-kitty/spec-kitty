"""ATDD / CliRunner acceptance for ``spec-kitty feedback`` (WP05 / T024).

Pins the lean command surface (bare form, --status, --prompts, hidden agent
flags) against a real loopback endpoint. Never talks to a non-loopback address.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from specify_cli.feedback.endpoint import ENV_FEEDBACK_URL
from specify_cli.feedback.wording import NO_ENDPOINT_MESSAGE, THANK_YOU
from tests.specify_cli.feedback.loopback_server import loopback_server

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_NON_INTERACTIVE_HINT_FRAGMENTS = ("terminal", "agent")


@pytest.fixture(autouse=True)
def _isolated_feedback_prefs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect preferences under tmp_path (same contract as feedback conftest)."""
    config_dir = tmp_path / "user-config" / "spec-kitty"
    monkeypatch.setattr(
        "specify_cli.feedback.preferences.resolve_config_dir",
        lambda: config_dir,
    )
    from specify_cli.feedback.preferences import preferences_path

    resolved = preferences_path()
    assert resolved.is_relative_to(tmp_path), f"preferences path escaped tmp_path: {resolved}"
    # CliRunner hits root main_callback bootstrap; skip global asset repair.
    monkeypatch.setattr("specify_cli.runtime.bootstrap.ensure_runtime", lambda: None)
    monkeypatch.setattr(
        "specify_cli.runtime.agent_skills.ensure_global_agent_skills",
        lambda: None,
    )
    monkeypatch.setattr(
        "specify_cli.runtime.agent_commands.ensure_global_agent_commands",
        lambda: None,
    )
    return config_dir


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner(env={"COLUMNS": "200", "TERM": "dumb"})


@pytest.fixture
def app():
    from specify_cli import app as cli_app

    return cli_app


def _interactive_env(url: str | None) -> dict[str, str]:
    env: dict[str, str] = {"SPEC_KITTY_FORCE_INTERACTIVE": "1"}
    if url is not None:
        env[ENV_FEEDBACK_URL] = url
    return env


def test_bare_feedback_submits_on_demand_via_loopback(
    runner: CliRunner,
    app: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "specify_cli.feedback.endpoint.resolve_distribution_profile",
        lambda: __import__("specify_cli.distribution.profile", fromlist=["stock_distribution_profile"]).stock_distribution_profile(),
    )
    with loopback_server("ok") as server:
        result = runner.invoke(
            app,  # type: ignore[arg-type]
            ["feedback"],
            input="4\nFaster planning\n\ny\n",
            env=_interactive_env(server.url),
        )
        assert result.exit_code == 0, result.output
        assert THANK_YOU in result.output
        assert server.wait_for(1, timeout=5.0), f"no request: {server.received!r}"
        body, _headers = server.received[0]
        assert body["trigger"] == "on_demand"
        assert body["harness"] == "cli"
        assert body["rating"] == 4
        assert body["comment"] == "Faster planning"
        assert "email" not in body


def test_bare_feedback_declined_sends_nothing(
    runner: CliRunner,
    app: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "specify_cli.feedback.endpoint.resolve_distribution_profile",
        lambda: __import__("specify_cli.distribution.profile", fromlist=["stock_distribution_profile"]).stock_distribution_profile(),
    )
    with loopback_server("ok") as server:
        result = runner.invoke(
            app,  # type: ignore[arg-type]
            ["feedback"],
            input="4\n\n\nn\n",
            env=_interactive_env(server.url),
        )
        assert result.exit_code == 0, result.output
        assert not server.wait_for(1, timeout=0.5)
        assert server.received == []


def test_status_and_prompts_toggle(
    runner: CliRunner,
    app: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "specify_cli.feedback.endpoint.resolve_distribution_profile",
        lambda: __import__("specify_cli.distribution.profile", fromlist=["stock_distribution_profile"]).stock_distribution_profile(),
    )
    url = "http://127.0.0.1:9/feedback"
    status = runner.invoke(
        app,  # type: ignore[arg-type]
        ["feedback", "--status"],
        env=_interactive_env(url),
    )
    assert status.exit_code == 0, status.output
    out = status.output
    assert "127.0.0.1" in out
    assert "never" in out.lower()
    assert "on" in out.lower()
    # Field list from ALLOWED_KEYS must appear (at least a couple of known keys).
    assert "rating" in out
    assert "comment" in out

    off = runner.invoke(
        app,  # type: ignore[arg-type]
        ["feedback", "--prompts", "off"],
        env=_interactive_env(url),
    )
    assert off.exit_code == 0, off.output

    status2 = runner.invoke(
        app,  # type: ignore[arg-type]
        ["feedback", "--status"],
        env=_interactive_env(url),
    )
    assert status2.exit_code == 0, status2.output
    assert "off" in status2.output.lower()


def test_status_redacts_url_userinfo(
    runner: CliRunner,
    app: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "specify_cli.feedback.endpoint.resolve_distribution_profile",
        lambda: __import__("specify_cli.distribution.profile", fromlist=["stock_distribution_profile"]).stock_distribution_profile(),
    )
    secret_url = "https://user:s3cret@feedback.example.test/v1"
    result = runner.invoke(
        app,  # type: ignore[arg-type]
        ["feedback", "--status"],
        env=_interactive_env(secret_url),
    )
    assert result.exit_code == 0, result.output
    assert "s3cret" not in result.output
    assert "user:" not in result.output
    assert "feedback.example.test" in result.output

    as_json = runner.invoke(
        app,  # type: ignore[arg-type]
        ["feedback", "--status", "--json"],
        env=_interactive_env(secret_url),
    )
    assert as_json.exit_code == 0, as_json.output
    payload = json.loads(as_json.output)
    blob = json.dumps(payload)
    assert "s3cret" not in blob
    assert "user:" not in blob
    assert "answer" not in blob.lower() or "answers" not in payload
    assert "email" not in payload
    assert "comment" not in payload


def test_dormant_prints_no_endpoint_and_asks_nothing(
    runner: CliRunner,
    app: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(ENV_FEEDBACK_URL, raising=False)
    monkeypatch.setattr(
        "specify_cli.feedback.endpoint.resolve_distribution_profile",
        lambda: __import__("specify_cli.distribution.profile", fromlist=["stock_distribution_profile"]).stock_distribution_profile(),
    )
    result = runner.invoke(
        app,  # type: ignore[arg-type]
        ["feedback"],
        input="4\ny\n",
        env={"SPEC_KITTY_FORCE_INTERACTIVE": "1"},
    )
    assert result.exit_code == 0, result.output
    assert NO_ENDPOINT_MESSAGE in result.output
    # Rating prompt wording must not appear when dormant.
    assert "How would you rate" not in result.output


def test_non_interactive_prints_hint_and_exits_zero(
    runner: CliRunner,
    app: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "specify_cli.feedback.endpoint.resolve_distribution_profile",
        lambda: __import__("specify_cli.distribution.profile", fromlist=["stock_distribution_profile"]).stock_distribution_profile(),
    )
    with loopback_server("ok") as server:
        result = runner.invoke(
            app,  # type: ignore[arg-type]
            ["feedback"],
            input="4\n\n\ny\n",
            env={
                ENV_FEEDBACK_URL: server.url,
                "SPEC_KITTY_NON_INTERACTIVE": "1",
            },
        )
        assert result.exit_code == 0, result.output
        lowered = result.output.lower()
        assert any(frag in lowered for frag in _NON_INTERACTIVE_HINT_FRAGMENTS)
        assert not server.wait_for(1, timeout=0.5)
        assert server.received == []


def test_hidden_agent_flags(
    runner: CliRunner,
    app: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from specify_cli.distribution.profile import stock_distribution_profile

    monkeypatch.setattr(
        "specify_cli.feedback.endpoint.resolve_distribution_profile",
        stock_distribution_profile,
    )
    monkeypatch.setattr(
        "specify_cli.feedback.agent_protocol.is_ci_env",
        lambda: False,
    )
    with loopback_server("ok") as server:
        env = {
            ENV_FEEDBACK_URL: server.url,
            "SPEC_KITTY_NON_INTERACTIVE": "1",
        }
        check = runner.invoke(
            app,  # type: ignore[arg-type]
            [
                "feedback",
                "--agent-check",
                "--trigger",
                "mission_end",
                "--agent",
                "cursor",
                "--json",
            ],
            env=env,
        )
        assert check.exit_code == 0, check.output
        check_payload = json.loads(check.output)
        assert check_payload["schema_version"] == 1
        assert check_payload["action"] in {"prompt", "none"}
        assert "trigger" in check_payload

        submit = runner.invoke(
            app,  # type: ignore[arg-type]
            [
                "feedback",
                "--agent-submit",
                "--trigger",
                "mission_end",
                "--agent",
                "cursor",
                "--rating",
                "4",
                "--comment",
                "Faster planning",
                "--consent",
                "yes",
                "--json",
            ],
            env=env,
        )
        assert submit.exit_code == 0, submit.output
        submit_payload = json.loads(submit.output)
        assert submit_payload["status"] == "handed_off"
        assert "Faster planning" not in submit.output
        assert server.wait_for(1, timeout=5.0)

        choice = runner.invoke(
            app,  # type: ignore[arg-type]
            [
                "feedback",
                "--agent-choice",
                "never",
                "--trigger",
                "op_close",
                "--json",
            ],
            env=env,
        )
        assert choice.exit_code == 0, choice.output
        choice_payload = json.loads(choice.output)
        assert choice_payload["status"] == "prompts_off"


def test_help_hides_agent_flags(runner: CliRunner, app: object) -> None:
    result = runner.invoke(app, ["feedback", "--help"])  # type: ignore[arg-type]
    assert result.exit_code == 0, result.output
    assert "agent-" not in result.output
    assert "--status" in result.output
    assert "--prompts" in result.output


def test_status_and_prompts_are_mutually_exclusive(runner: CliRunner, app: object) -> None:
    result = runner.invoke(app, ["feedback", "--status", "--prompts", "off"])  # type: ignore[arg-type]
    assert result.exit_code == 2
    assert "mutually exclusive" in result.output.lower()


def test_agent_modes_are_mutually_exclusive(runner: CliRunner, app: object) -> None:
    result = runner.invoke(
        app,  # type: ignore[arg-type]
        ["feedback", "--agent-check", "--agent-submit", "--trigger", "on_demand", "--json"],
    )
    assert result.exit_code == 2
    assert "mutually exclusive" in result.output.lower()


def test_agent_check_requires_trigger(runner: CliRunner, app: object) -> None:
    result = runner.invoke(app, ["feedback", "--agent-check", "--json"])  # type: ignore[arg-type]
    assert result.exit_code == 2
    assert "trigger" in result.output.lower()


def test_status_with_port_and_unreadable_prefs(
    runner: CliRunner,
    app: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from specify_cli.feedback.preferences import Unreadable

    monkeypatch.setattr(
        "specify_cli.feedback.endpoint.resolve_distribution_profile",
        lambda: __import__("specify_cli.distribution.profile", fromlist=["stock_distribution_profile"]).stock_distribution_profile(),
    )
    monkeypatch.setattr(
        "specify_cli.cli.commands.feedback.load_preferences",
        lambda: Unreadable(reason="mode bits wrong"),
    )
    result = runner.invoke(
        app,  # type: ignore[arg-type]
        ["feedback", "--status"],
        env=_interactive_env("https://user:pw@feedback.example.test:8443/v1"),
    )
    assert result.exit_code == 0, result.output
    assert "pw" not in result.output
    assert "8443" in result.output
    assert "unknown" in result.output.lower()
    assert "mode bits wrong" in result.output


def test_redact_url_userinfo_helpers() -> None:
    from specify_cli.cli.commands.feedback import _redact_url_userinfo

    assert _redact_url_userinfo("https://example.test/x") == "https://example.test/x"
    redacted = _redact_url_userinfo("https://a:b@example.test:8443/path?q=1")
    assert "a:b@" not in redacted
    assert "8443" in redacted
    assert redacted.startswith("https://example.test:8443/")


def test_agent_choice_skip(runner: CliRunner, app: object, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "specify_cli.feedback.endpoint.resolve_distribution_profile",
        lambda: __import__("specify_cli.distribution.profile", fromlist=["stock_distribution_profile"]).stock_distribution_profile(),
    )
    result = runner.invoke(
        app,  # type: ignore[arg-type]
        ["feedback", "--agent-choice", "skip", "--trigger", "op_close", "--json"],
        env={"SPEC_KITTY_NON_INTERACTIVE": "1"},
    )
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["status"] == "skipped"


def test_redact_handles_urlsplit_value_error(monkeypatch: pytest.MonkeyPatch) -> None:
    from specify_cli.cli.commands import feedback as fb_mod

    def _boom(_url: str) -> None:
        raise ValueError("bad")

    monkeypatch.setattr(fb_mod, "urlsplit", _boom)
    assert fb_mod._redact_url_userinfo("https://x") == "https://x"


def test_endpoint_override_unreadable(monkeypatch: pytest.MonkeyPatch) -> None:
    from specify_cli.cli.commands.feedback import _endpoint_override
    from specify_cli.feedback.preferences import Unreadable

    monkeypatch.setattr(
        "specify_cli.cli.commands.feedback.load_preferences",
        lambda: Unreadable(reason="broken"),
    )
    assert _endpoint_override() is None


def test_parse_trigger_invalid() -> None:
    import pytest
    import typer
    from specify_cli.cli.commands.feedback import _parse_trigger

    with pytest.raises(typer.Exit) as exc:
        _parse_trigger("not-a-trigger")
    assert exc.value.exit_code == 2


def _stock_profile_patch(monkeypatch: pytest.MonkeyPatch) -> None:
    from specify_cli.distribution.profile import stock_distribution_profile

    monkeypatch.setattr(
        "specify_cli.feedback.endpoint.resolve_distribution_profile",
        stock_distribution_profile,
    )


@pytest.mark.parametrize(
    "stdin",
    [
        pytest.param("", id="eof_at_rating"),
        pytest.param("4\n", id="eof_at_comment"),
        pytest.param("4\nnote\n", id="eof_at_email"),
        pytest.param("4\nnote\n\n", id="eof_at_consent"),
        pytest.param("4\nnote\nbad-email\n", id="eof_at_email_reask"),
    ],
)
def test_bare_feedback_eof_exits_zero_sends_nothing(
    runner: CliRunner,
    app: object,
    monkeypatch: pytest.MonkeyPatch,
    stdin: str,
) -> None:
    """EOF/Ctrl-D must raise click.Abort from typer.prompt — exit 0, nothing sent.

    These drive the real CLI entry through CliRunner with short/empty stdin so
    ``typer.prompt`` genuinely raises ``click.exceptions.Abort``. Injecting
    ``EOFError`` into a stub ask would hide the production bug.
    """
    _stock_profile_patch(monkeypatch)
    with loopback_server("ok") as server:
        result = runner.invoke(
            app,  # type: ignore[arg-type]
            ["feedback"],
            input=stdin,
            env=_interactive_env(server.url),
        )
        assert result.exit_code == 0, f"expected exit 0 on survey EOF, got {result.exit_code}: {result.output!r}"
        assert "Aborted." not in result.output
        assert "Aborted." not in (result.stderr or "")
        assert "Traceback" not in result.output
        assert not server.wait_for(1, timeout=0.5)
        assert server.received == []
