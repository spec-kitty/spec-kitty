"""Tests for kernel.env_expand — the single ${VAR}/$VAR + ~ expansion authority.

Covers C-EXP-1, C-EXP-2 from contracts/env-expander.md (WP01 T005).
C-EXP-4 (org_pack_config delegation, byte-preserved fail-loud) is covered in
tests/charter_offering/test_org_pack_delegation.py. C-EXP-3 (get_packs_root_default)
is covered in tests/kernel/test_packs_root_default.py. C-EXP-5 (no upward
import) is covered in
tests/architectural/test_kernel_env_expand_no_upward_import.py.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from kernel.env_expand import (
    UnresolvedEnvTokenError,
    expand_env_template,
    expand_raw_template,
    find_empty_env_token,
    find_unresolved_token,
)
from kernel.paths import get_packs_root_default

pytestmark = pytest.mark.fast

_PACKS_ROOT_VAR = "SPEC_KITTY_PACKS_ROOT"


def _ensure_unset(monkeypatch: pytest.MonkeyPatch, name: str) -> None:
    monkeypatch.delenv(name, raising=False)


class TestDefaultInjection:
    """C-EXP-1: inject_defaults=True fills in the registered default."""

    def test_unset_packs_root_token_resolves_to_default_no_literal_token(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _ensure_unset(monkeypatch, _PACKS_ROOT_VAR)
        result = expand_env_template("${SPEC_KITTY_PACKS_ROOT}/built-in/x", inject_defaults=True)
        assert result == f"{get_packs_root_default()}/built-in/x"
        assert "${SPEC_KITTY_PACKS_ROOT}" not in result

    def test_unset_packs_root_bare_dollar_form_resolves_to_default(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _ensure_unset(monkeypatch, _PACKS_ROOT_VAR)
        result = expand_env_template("$SPEC_KITTY_PACKS_ROOT/built-in/x", inject_defaults=True)
        assert result == f"{get_packs_root_default()}/built-in/x"

    def test_set_packs_root_token_uses_env_value_not_default(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(_PACKS_ROOT_VAR, str(tmp_path))
        result = expand_env_template("${SPEC_KITTY_PACKS_ROOT}/built-in/x", inject_defaults=True)
        assert result == f"{tmp_path}/built-in/x"

    def test_unregistered_token_still_raises_even_with_inject_defaults_true(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _ensure_unset(monkeypatch, "SPEC_KITTY_DOES_NOT_EXIST")
        with pytest.raises(UnresolvedEnvTokenError) as exc_info:
            expand_env_template("${SPEC_KITTY_DOES_NOT_EXIST}/x", inject_defaults=True)
        assert "SPEC_KITTY_DOES_NOT_EXIST" in str(exc_info.value)
        assert exc_info.value.token == "${SPEC_KITTY_DOES_NOT_EXIST}"

    def test_no_token_present_is_a_no_op(self, tmp_path: Path) -> None:
        raw = str(tmp_path / "plain" / "path")
        assert expand_env_template(raw, inject_defaults=True) == raw


class TestFailLoud:
    """C-EXP-2: inject_defaults=False always raises on a surviving token."""

    def test_unset_packs_root_raises_naming_the_token(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _ensure_unset(monkeypatch, _PACKS_ROOT_VAR)
        with pytest.raises(UnresolvedEnvTokenError) as exc_info:
            expand_env_template("${SPEC_KITTY_PACKS_ROOT}/built-in/x", inject_defaults=False)
        assert "SPEC_KITTY_PACKS_ROOT" in str(exc_info.value)
        assert exc_info.value.token == "${SPEC_KITTY_PACKS_ROOT}"
        assert exc_info.value.raw == "${SPEC_KITTY_PACKS_ROOT}/built-in/x"

    def test_unresolved_error_is_a_value_error(self) -> None:
        assert issubclass(UnresolvedEnvTokenError, ValueError)

    def test_no_token_present_returns_expanded_string_unchanged(
        self, tmp_path: Path
    ) -> None:
        raw = str(tmp_path / "plain" / "path")
        assert expand_env_template(raw, inject_defaults=False) == raw

    def test_set_var_expands_without_raising(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(_PACKS_ROOT_VAR, str(tmp_path))
        result = expand_env_template("${SPEC_KITTY_PACKS_ROOT}/x", inject_defaults=False)
        assert result == f"{tmp_path}/x"


class TestEnvironOverride:
    """The optional environ= mapping sources substitution instead of os.environ."""

    def test_custom_environ_used_instead_of_os_environ(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _ensure_unset(monkeypatch, "SPEC_KITTY_CUSTOM_HOME")
        result = expand_env_template(
            "${SPEC_KITTY_CUSTOM_HOME}/pack",
            inject_defaults=False,
            environ={"SPEC_KITTY_CUSTOM_HOME": "/opt/acme"},
        )
        assert result == "/opt/acme/pack"

    def test_custom_environ_missing_token_still_raises(self) -> None:
        with pytest.raises(UnresolvedEnvTokenError):
            expand_env_template(
                "${SPEC_KITTY_CUSTOM_HOME}/pack", inject_defaults=False, environ={}
            )

    def test_custom_environ_does_not_see_real_os_environ(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A var set in the real environment must NOT leak into a custom environ call."""
        monkeypatch.setenv("SPEC_KITTY_REAL_ONLY", "/should/not/be/used")
        with pytest.raises(UnresolvedEnvTokenError):
            expand_env_template(
                "${SPEC_KITTY_REAL_ONLY}/pack", inject_defaults=False, environ={}
            )


class TestExpandRawTemplate:
    """The pure, non-raising transform underlying both policies (T004's delegation target)."""

    def test_never_raises_on_unresolved_token(self) -> None:
        result = expand_raw_template("${SPEC_KITTY_TOTALLY_UNSET_XYZ}/x")
        assert "SPEC_KITTY_TOTALLY_UNSET_XYZ" in result

    def test_tilde_expansion(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("HOME", "/home/acme")
        assert expand_raw_template("~/pack") == "/home/acme/pack"

    def test_environ_mapping_substitutes(self) -> None:
        assert (
            expand_raw_template("${FOO}/x", environ={"FOO": "bar"}) == "bar/x"
        )

    def test_environ_mapping_leaves_unknown_token_verbatim(self) -> None:
        assert expand_raw_template("${FOO}/x", environ={}) == "${FOO}/x"


class TestSharedDetectors:
    """find_unresolved_token / find_empty_env_token — org_pack_config's delegation target."""

    def test_find_unresolved_token_returns_none_when_clean(self) -> None:
        assert find_unresolved_token("/plain/path") is None

    def test_find_unresolved_token_returns_the_token(self) -> None:
        assert find_unresolved_token("${FOO}/x") == "${FOO}"
        assert find_unresolved_token("$FOO/x") == "$FOO"

    def test_find_empty_env_token_detects_blank_var(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("SPEC_KITTY_BLANK", "")
        assert find_empty_env_token("${SPEC_KITTY_BLANK}/x") == "${SPEC_KITTY_BLANK}"

    def test_find_empty_env_token_none_when_var_unset(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _ensure_unset(monkeypatch, "SPEC_KITTY_NOT_SET_AT_ALL")
        assert find_empty_env_token("${SPEC_KITTY_NOT_SET_AT_ALL}/x") is None

    def test_find_empty_env_token_honours_custom_environ(self) -> None:
        assert find_empty_env_token("${FOO}/x", environ={"FOO": ""}) == "${FOO}"
        assert find_empty_env_token("${FOO}/x", environ={"FOO": "bar"}) is None
