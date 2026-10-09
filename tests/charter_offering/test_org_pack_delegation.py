"""C-EXP-4: org_pack_config._expand_path_template delegates to the kernel
env-expansion seam, with the pack's own fail-loud behavior byte-preserved
(WP01 T004).

This is a REGRESSION test for the delegation itself, distinct from
tests/charter_offering/test_org_pack_subdir.py's TestEnvVarExpansion class (the
pre-existing behavioral suite that must stay green unmodified across this
WP). Here we additionally assert:

1. The delegation is real (not dead code) — org_pack_config actually calls
   into kernel.env_expand's primitives.
2. The exception TYPE raised on an unset ${VAR} is unchanged
   (OrgPackEnvVarUnsetError, not kernel's UnresolvedEnvTokenError).
3. The set-but-blank guard still fires (a case the kernel primitive itself
   does not detect — org_pack_config's own guard).
"""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from charter.offering.drg import org_pack_config
from charter.offering.drg.org_pack_config import OrgPackConfig, OrgPackEnvVarUnsetError
from kernel.env_expand import UnresolvedEnvTokenError

pytestmark = [pytest.mark.fast, pytest.mark.doctrine]

_PACK_NAME = "acme-doctrine-pack"


class TestDelegationIsWired:
    """Non-vacuity: org_pack_config really calls kernel.env_expand, not dead code."""

    def test_expand_path_template_source_calls_kernel_expand_raw_template(self) -> None:
        source = inspect.getsource(org_pack_config._expand_path_template)
        assert "expand_raw_template" in source

    def test_unresolved_env_token_source_calls_kernel_find_unresolved_token(self) -> None:
        source = inspect.getsource(org_pack_config._unresolved_env_token)
        assert "find_unresolved_token" in source

    def test_empty_expanded_env_token_source_calls_kernel_find_empty_env_token(self) -> None:
        source = inspect.getsource(org_pack_config._empty_expanded_env_token)
        assert "find_empty_env_token" in source

    def test_module_no_longer_defines_its_own_token_regex(self) -> None:
        """The single-detector requirement (T002): no second regex fork in org_pack_config."""
        assert not hasattr(org_pack_config, "_ENV_VAR_TOKEN_RE")

    def test_expand_path_template_actually_expands_a_set_var(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Spot check the delegation actually runs (not stubbed to a no-op)."""
        monkeypatch.setenv("SPEC_KITTY_DELEGATION_SPOT_CHECK", "/opt/acme")
        result = org_pack_config._expand_path_template(
            "${SPEC_KITTY_DELEGATION_SPOT_CHECK}/pack"
        )
        assert result == "/opt/acme/pack"


class TestExceptionTypeByteEnsured:
    """C-EXP-4: unset ${VAR} still raises OrgPackEnvVarUnsetError, NOT the kernel's own type."""

    def test_unset_var_raises_org_pack_error_not_kernel_error(self, tmp_path: Path) -> None:
        pack = OrgPackConfig(
            name=_PACK_NAME, local_path=Path("${SPEC_KITTY_DELEGATION_UNSET}/pack")
        )
        with pytest.raises(OrgPackEnvVarUnsetError) as exc_info:
            pack.effective_root(tmp_path)
        assert not isinstance(exc_info.value, UnresolvedEnvTokenError)
        assert issubclass(OrgPackEnvVarUnsetError, ValueError)
        assert exc_info.value.unresolved_token == "${SPEC_KITTY_DELEGATION_UNSET}"
        assert exc_info.value.pack_name == _PACK_NAME

    def test_unresolved_env_token_error_never_raised_by_org_pack(self, tmp_path: Path) -> None:
        """The kernel's own UnresolvedEnvTokenError must never surface through OrgPackConfig —
        the non-raising delegation (T004) means org_pack_config always constructs its own type."""
        pack = OrgPackConfig(
            name=_PACK_NAME, local_path=Path("${SPEC_KITTY_DELEGATION_UNSET_2}/pack")
        )
        try:
            pack.effective_root(tmp_path)
        except UnresolvedEnvTokenError:
            pytest.fail(
                "kernel.env_expand.UnresolvedEnvTokenError leaked through OrgPackConfig — "
                "the org_pack caller must stay non-raising at the kernel seam (T004)"
            )
        except OrgPackEnvVarUnsetError:
            pass  # expected


class TestSetButBlankStillFailsLoud:
    """C-EXP-4: the set-but-blank guard is org_pack_config's OWN — kernel does not detect it."""

    def test_var_set_to_empty_string_raises_org_pack_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("SPEC_KITTY_DELEGATION_BLANK", "")
        pack = OrgPackConfig(
            name=_PACK_NAME, local_path=Path("${SPEC_KITTY_DELEGATION_BLANK}/pack")
        )
        with pytest.raises(OrgPackEnvVarUnsetError) as exc_info:
            pack.effective_root(tmp_path)
        assert exc_info.value.unresolved_token == "${SPEC_KITTY_DELEGATION_BLANK}"

    def test_kernel_raw_transform_alone_does_not_catch_set_but_blank(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Proves the guard is load-bearing: the pure transform alone (no org_pack guard)
        silently produces a literal-token-free but WRONG path for a blank var."""
        from kernel.env_expand import expand_raw_template, find_unresolved_token

        monkeypatch.setenv("SPEC_KITTY_DELEGATION_BLANK_2", "")
        expanded = expand_raw_template("${SPEC_KITTY_DELEGATION_BLANK_2}/pack")
        assert expanded == "/pack"
        assert find_unresolved_token(expanded) is None
