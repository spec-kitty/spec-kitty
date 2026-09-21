"""``_auth_saas_target.py`` campsite folds (WP05, #4755, T020/T021) plus the
T023 display-still-renders assertion.

Three same-seam findings fold in here, on the lines the WP01 unification
already rewrites:

- **#4053 finding 1**: the ``except ConfigurationError`` branch (and its
  import) in ``print_saas_endpoint`` was unreachable once
  ``resolve_server_target`` stopped raising ``ConfigurationError`` (D-5
  revised, #3980) — removed rather than left dead.
- **#4053 finding 2**: ``saas_source_name``/``format_saas_provenance`` keyed
  off raw ``env_server_url``/``configured_server_url`` presence, which
  mislabels the case where both are set and agree (``OverrideMode.NONE`` —
  config decided, even though env's value happens to match) as
  ``SPEC_KITTY_SAAS_URL`` provenance. Now keyed off ``override_mode``, the
  resolver's own verdict.
- **T020**: ``format_saas_mismatch_warning`` consumes the canonical
  ``server_target._normalize_url`` instead of a second, locally-defined
  ``_normalize_endpoint`` copy, and keeps returning a string (never
  raises) so ``auth status``/``doctor`` render on a mismatch instead of
  aborting.
"""

from __future__ import annotations

import ast
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from typer.testing import CliRunner

from kernel.clock import now_utc, timedelta
from specify_cli.auth import reset_token_manager
from specify_cli.auth.server_target import OverrideMode, ResolvedServerTarget
from specify_cli.auth.session import StoredSession, Team
from specify_cli.cli.commands._auth_saas_target import (
    format_saas_mismatch_warning,
    format_saas_provenance,
    saas_source_name,
)
from specify_cli.cli.commands.auth import app

pytestmark = [pytest.mark.fast, pytest.mark.regression]

runner = CliRunner()

_MODULE_PATH = Path(__file__).resolve().parents[2] / "src" / "specify_cli" / "cli" / "commands" / "_auth_saas_target.py"


def _module_tree() -> ast.Module:
    return ast.parse(_MODULE_PATH.read_text(encoding="utf-8"), filename=str(_MODULE_PATH))


def _make_session(*, issuer_url: str | None) -> StoredSession:
    now = now_utc()
    return StoredSession(
        user_id="user-1",
        email="alice@example.com",
        name="Alice",
        teams=[Team(id="t1", name="Team One", role="owner")],
        default_team_id="t1",
        access_token="access-xyz",
        refresh_token="refresh-xyz",
        session_id="sess-1",
        issued_at=now,
        access_token_expires_at=now + timedelta(hours=1),
        refresh_token_expires_at=now + timedelta(days=30),
        scope="offline_access",
        storage_backend="file",
        last_used_at=now,
        auth_method="authorization_code",
        issuer_url=issuer_url,
    )


def _mock_storage_returning(session: StoredSession | None):
    mock_storage = Mock()
    mock_storage.read.return_value = session
    mock_storage.backend_name = "file"
    return mock_storage


def _flat(text: str) -> str:
    return " ".join(text.split())


# ---------------------------------------------------------------------------
# #4053 finding 1: the dead ``except ConfigurationError`` branch + import
# ---------------------------------------------------------------------------


class TestFold4053DeadBranchRemoved:
    def test_configuration_error_is_not_imported(self) -> None:
        """The module no longer imports the exception it no longer catches."""
        tree = _module_tree()
        imported_names = {alias.asname or alias.name for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) for alias in node.names}
        assert "ConfigurationError" not in imported_names

    def test_no_except_clause_names_configuration_error(self) -> None:
        """No ``try/except`` anywhere in the module still handles it."""
        tree = _module_tree()
        handled_exception_names: set[str] = set()
        for node in ast.walk(tree):
            if not isinstance(node, ast.Try):
                continue
            for handler in node.handlers:
                handler_type = handler.type
                if handler_type is None:
                    continue
                names = handler_type.elts if isinstance(handler_type, ast.Tuple) else [handler_type]
                for name in names:
                    if isinstance(name, ast.Name):
                        handled_exception_names.add(name.id)
        assert "ConfigurationError" not in handled_exception_names

    def test_print_saas_endpoint_still_catches_split_brain(self) -> None:
        """The one exception shape ``resolve_server_target`` can still raise
        (``ServerTargetSplitBrainError``) is still handled -- the branch
        removal did not overshoot into the live one."""
        from specify_cli.auth.server_target import ServerTargetSplitBrainError
        from specify_cli.cli.commands import _auth_saas_target

        with patch.object(
            _auth_saas_target,
            "resolve_server_target",
            side_effect=ServerTargetSplitBrainError(
                configured_server_url="https://config.test",
                env_server_url="https://env.test",
            ),
        ):
            result = _auth_saas_target.print_saas_endpoint()

        assert result is None


# ---------------------------------------------------------------------------
# #4053 finding 2: the no-opinion-default provenance mislabel
# ---------------------------------------------------------------------------


class TestFold4053ProvenanceLabelCorrected:
    """When env and config agree (``OverrideMode.NONE``, config decided even
    though its value matches env), the label must not credit
    ``SPEC_KITTY_SAAS_URL`` -- the presence-first check this replaces did."""

    def _agreeing_target(self) -> ResolvedServerTarget:
        return ResolvedServerTarget(
            configured_server_url="https://selfhost.example.com",
            env_server_url="https://selfhost.example.com",
            override_mode=OverrideMode.NONE,
            resolved_server_url="https://selfhost.example.com",
        )

    def test_source_name_credits_config_when_mode_is_none(self) -> None:
        target = self._agreeing_target()
        assert saas_source_name(target) == "config.toml [sync].server_url"

    def test_provenance_credits_config_when_mode_is_none(self) -> None:
        target = self._agreeing_target()
        assert format_saas_provenance(target) == "(from config.toml [sync].server_url)"

    def test_source_name_still_credits_env_on_process_override(self) -> None:
        """The correction is scoped to the mislabel, not a blanket removal of
        env attribution: a genuine process-wide override still names it."""
        target = ResolvedServerTarget(
            configured_server_url=None,
            env_server_url="https://env.test",
            override_mode=OverrideMode.PROCESS_OVERRIDE,
            resolved_server_url="https://env.test",
        )
        assert saas_source_name(target) == "SPEC_KITTY_SAAS_URL"


# ---------------------------------------------------------------------------
# T020: the local ``_normalize_endpoint`` copy is gone
# ---------------------------------------------------------------------------


class TestNormalizerUnified:
    def test_no_local_normalize_endpoint_function(self) -> None:
        tree = _module_tree()
        function_names = {node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)}
        assert "_normalize_endpoint" not in function_names

    def test_normalize_url_is_imported_from_server_target(self) -> None:
        tree = _module_tree()
        imported = {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module is not None and node.module.split(".")[-1] == "server_target"
            for alias in node.names
        }
        assert "_normalize_url" in imported


# ---------------------------------------------------------------------------
# T023: the display path never raises -- auth status / auth doctor still
# render an issuer mismatch.
# ---------------------------------------------------------------------------


class TestDisplayStillRendersOnMismatch:
    def test_format_saas_mismatch_warning_returns_a_string_never_raises(self) -> None:
        warning = format_saas_mismatch_warning(
            "https://old-issuer.test",
            source_name="SPEC_KITTY_SAAS_URL",
            resolved_server_url="https://team.spec-kitty.ai",
        )
        assert isinstance(warning, str)
        assert "https://old-issuer.test" in warning
        assert "https://team.spec-kitty.ai" in warning

    def test_auth_status_renders_issuer_mismatch_without_exception(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SPEC_KITTY_SAAS_URL", "https://team.spec-kitty.ai")
        session = _make_session(issuer_url="https://old-host.example.com")
        mock_storage = _mock_storage_returning(session)
        with patch(
            "specify_cli.auth.secure_storage.SecureStorage.from_environment",
            return_value=mock_storage,
        ):
            reset_token_manager()
            result = runner.invoke(app, ["status"])

        assert result.exit_code == 0, result.stdout
        flat = _flat(result.stdout)
        assert "Session is for https://old-host.example.com" in flat
        assert "run spec-kitty auth login --force" in flat

    def test_auth_doctor_server_issuer_mismatch_helper_renders_without_exception(self) -> None:
        """``auth doctor --server``'s mismatch reaction
        (``_server_issuer_mismatch_error``) is the third consumer of this
        display path; it must return the rendered string, never raise, on
        exactly the same mismatch shape."""
        from specify_cli.cli.commands._auth_doctor import _server_issuer_mismatch_error

        session = _make_session(issuer_url="https://old-host.example.com")

        class _FakeTokenManager:
            def get_current_session(self) -> StoredSession | None:
                return session

        target = ResolvedServerTarget(
            configured_server_url=None,
            env_server_url="https://team.spec-kitty.ai",
            override_mode=OverrideMode.PROCESS_OVERRIDE,
            resolved_server_url="https://team.spec-kitty.ai",
        )

        result = _server_issuer_mismatch_error(_FakeTokenManager(), target)

        assert isinstance(result, str)
        assert "old-host.example.com" in result
        assert "team.spec-kitty.ai" in result
