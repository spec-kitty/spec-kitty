"""CliRunner tests for ``spec-kitty auth whoami`` + the #176 SaaS line.

Contract under test:

- Exit 0 with the email as the **first non-empty output line** (machine
  consumers read it as the identity token) and exit 1 when unauthenticated.
- The ``SaaS:`` endpoint line (#176) is printed *after* the identity token,
  with the same provenance + mismatch warning shape ``auth status`` prints.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from specify_cli.auth import reset_token_manager
from specify_cli.auth.errors import SessionFilePermissionsError
from specify_cli.cli.commands.auth import app

from tests.cli.commands.test_auth_status import (
    _flat,
    _make_session,
    _mock_storage_returning,
    _saas_line,
)


pytestmark = [pytest.mark.integration]

runner = CliRunner()


@pytest.fixture(autouse=True)
def _isolate(monkeypatch):
    """Same isolation contract as test_auth_status._isolate."""
    monkeypatch.setenv("SPEC_KITTY_SAAS_URL", "https://saas.test")
    reset_token_manager()
    yield
    reset_token_manager()


def _invoke_with(session) -> object:
    mock_storage = _mock_storage_returning(session, backend="file")
    with patch(
        "specify_cli.auth.secure_storage.SecureStorage.from_environment",
        return_value=mock_storage,
    ):
        reset_token_manager()
        return runner.invoke(app, ["whoami"])


class TestAuthWhoamiCommand:
    def test_email_is_the_first_non_empty_line(self):
        result = _invoke_with(_make_session(issuer_url="https://saas.test"))

        assert result.exit_code == 0, result.stdout
        first_line = next(line for line in result.stdout.splitlines() if line.strip())
        assert first_line.strip() == "alice@example.com"

    def test_saas_endpoint_line_follows_identity(self):
        result = _invoke_with(_make_session(issuer_url="https://saas.test"))

        assert result.exit_code == 0, result.stdout
        flat = _flat(result.stdout)
        assert "https://saas.test" in flat
        assert "(from SPEC_KITTY_SAAS_URL)" in flat
        assert _saas_line(result.stdout) == "  SaaS:           https://saas.test (from SPEC_KITTY_SAAS_URL)"

    def test_mismatch_warning_follows_identity(self):
        result = _invoke_with(_make_session(issuer_url="https://old.example.com"))

        assert result.exit_code == 0, result.stdout
        flat = _flat(result.stdout)
        assert "Session is for https://old.example.com; SPEC_KITTY_SAAS_URL now points at https://saas.test" in flat

    def test_no_mismatch_warning_for_matching_issuer(self):
        result = _invoke_with(_make_session(issuer_url="https://saas.test"))

        assert result.exit_code == 0, result.stdout
        assert "Session is for" not in _flat(result.stdout)

    def test_unauthenticated_exits_1(self):
        result = _invoke_with(None)

        assert result.exit_code == 1

    def test_unsafe_permissions_refusal_names_cause_on_stderr(self):
        """#4761: a storage refusal keeps the documented 0/1 exit contract and
        an empty stdout (machine consumers), but names the real cause — the
        storage layer's chmod remedy — on stderr instead of failing silently
        like a plain logged-out state."""
        mock_storage = _mock_storage_returning(None, backend="file")
        mock_storage.read.side_effect = SessionFilePermissionsError(
            "Session file /home/u/.spec-kitty/auth/session.json has unsafe "
            "permissions (mode=0o644); expected 0600. Fix with: chmod 600 "
            "/home/u/.spec-kitty/auth/session.json"
        )
        with patch(
            "specify_cli.auth.secure_storage.SecureStorage.from_environment",
            return_value=mock_storage,
        ):
            reset_token_manager()
            result = runner.invoke(app, ["whoami"])

        assert result.exit_code == 1
        assert "alice@example.com" not in (result.output or "")
        combined = (result.output or "") + (result.stderr or "")
        assert "unsafe permissions" in combined
        assert "chmod 600" in combined

    def test_unsafe_permissions_detail_is_sanitized_on_stderr(self):
        """#4761 squad NOTE fold + pass-2 MINOR fold: the stderr detail goes
        through the terminal-hygiene rule's control-sequence half — hostile
        control sequences in the storage-authored message are stripped
        before the line is printed (a plain ``print`` bypasses
        ``CliConsole.render_str``'s sanitisation). Rich markup is NOT
        escaped: stderr is a plain print sink, nothing parses markup there,
        and ``rich.markup.escape`` would only leak a literal backslash into
        the path — so a Rich-tag-shaped path segment must pass through
        raw."""
        hostile_suffix = "\x1b[2J\x1b]0;x\x07\x1b"
        safe_text = "Session file /home/u/[red]kitty/auth/session.json has unsafe permissions"
        mock_storage = _mock_storage_returning(None, backend="file")
        mock_storage.read.side_effect = SessionFilePermissionsError(
            f"{safe_text}{hostile_suffix} (mode=0o644); expected 0600. Fix with: chmod 600 /home/u/[red]kitty/auth/session.json"
        )
        with patch(
            "specify_cli.auth.secure_storage.SecureStorage.from_environment",
            return_value=mock_storage,
        ):
            reset_token_manager()
            result = runner.invoke(app, ["whoami"])

        assert result.exit_code == 1
        stderr = result.stderr or ""
        emitted = stderr.encode("utf-8")
        assert safe_text in stderr
        assert "chmod 600" in stderr
        assert b"\x1b" not in emitted
        assert b"[2J" not in emitted
        assert b"]0;x" not in emitted
        # no Rich escape on this sink: the tag-shaped segment stays raw
        # (an escaped render would print a literal backslash before the tag).
        assert "\\[red]" not in stderr
        assert "[red]" in stderr

    def test_split_brain_shows_both_values_not_a_traceback(self, monkeypatch: pytest.MonkeyPatch, tmp_path):
        """#193: ``whoami`` shares ``_print_saas_target`` with ``status`` — a
        genuine config.toml/env disagreement must render as a friendly line
        naming both endpoints, never as an unhandled traceback."""
        (tmp_path / "config.toml").write_text('[sync]\nserver_url = "https://config.test"\n', encoding="utf-8")
        monkeypatch.setenv("SPEC_KITTY_HOME", str(tmp_path))
        result = _invoke_with(_make_session(issuer_url="https://saas.test"))

        assert result.exit_code == 0, result.stdout
        assert "Traceback" not in result.stdout
        first_line = next(line for line in result.stdout.splitlines() if line.strip())
        assert first_line.strip() == "alice@example.com"
        flat = _flat(result.stdout)
        assert _saas_line(result.stdout) == "  SaaS:           split-brain (env and config.toml disagree)"
        assert "split-brain" in flat
        assert "https://config.test" in flat
        assert "https://saas.test" in flat
