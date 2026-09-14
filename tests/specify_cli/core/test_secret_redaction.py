"""Tests for ``specify_cli.core.secret_redaction`` (T018, C-SEC-1).

Fail-closed allowlist: a var not on ``_PRINTABLE_VARS`` never renders by
value, regardless of how innocuous or how secret-shaped its name looks.
"""

from __future__ import annotations

import pytest

from specify_cli.core.secret_redaction import RedactedVar, redact

pytestmark = [pytest.mark.fast]


class TestRedactAllowlisted:
    def test_allowlisted_var_renders_its_value(self) -> None:
        result = redact({"SPEC_KITTY_HOME": "/home/operator/.kittify"})
        assert result == [RedactedVar(name="SPEC_KITTY_HOME", present=True, value="/home/operator/.kittify")]

    def test_multiple_allowlisted_vars_all_render(self) -> None:
        mapping = {"SPEC_KITTY_HOME": "/x", "SPEC_KITTY_SAAS_URL": "https://saas.example.com"}
        result = redact(mapping)
        by_name = {r.name: r for r in result}
        assert by_name["SPEC_KITTY_HOME"].value == "/x"
        assert by_name["SPEC_KITTY_SAAS_URL"].value == "https://saas.example.com"


class TestRedactNonAllowlisted:
    def test_known_secret_var_never_renders_value(self) -> None:
        """C-SEC-1: SPEC_KITTY_SAAS_TOKEN is the contract's own worked example."""
        # Token-shaped but deliberately not a real provider pattern, so
        # secret-scanning push protection does not flag the fixture itself.
        secret_value = "tok_fixture_not_a_real_secret_0000000000"
        result = redact({"SPEC_KITTY_SAAS_TOKEN": secret_value})

        assert len(result) == 1
        entry = result[0]
        assert entry.name == "SPEC_KITTY_SAAS_TOKEN"
        assert entry.present is True
        assert entry.value is None
        # Fail-closed at the string level too: the secret payload never
        # appears anywhere in the redacted entry's repr.
        assert secret_value not in repr(entry)

    def test_untriaged_unknown_var_never_renders_value(self) -> None:
        """Fail-closed means absence from the allowlist redacts -- not presence on a denylist."""
        result = redact({"SPEC_KITTY_SOME_FUTURE_VAR_NOBODY_TRIAGED_YET": "whatever-value"})
        assert result[0].value is None
        assert result[0].present is True

    def test_org_token_and_auth_header_never_render(self) -> None:
        mapping = {
            "SPEC_KITTY_ORG_TOKEN": "ghp_deadbeef",
            "SPEC_KITTY_ORG_AUTH_HEADER": "Bearer deadbeef",
        }
        result = redact(mapping)
        assert all(entry.value is None for entry in result)

    def test_machine_client_secret_never_renders_value(self) -> None:
        """#3277: the CI machine credential is redacted by default — it is
        deliberately NOT on the printable allowlist."""
        mapping = {
            "SPEC_KITTY_MACHINE_CLIENT_SECRET": "machine-secret-fixture-0000000",
            # The client id is a public identifier but is not on the
            # allowlist either — fail-closed until explicitly triaged.
            "SPEC_KITTY_MACHINE_CLIENT_ID": "cid_fixture",
            "SPEC_KITTY_MACHINE_CLIENT_SECRET_FILE": "/run/secrets/fixture",
        }
        result = redact(mapping)
        assert all(entry.value is None for entry in result)
        assert all(entry.present is True for entry in result)


class TestRedactMixed:
    def test_mixed_mapping_only_allowlisted_entries_carry_values(self) -> None:
        mapping = {
            "SPEC_KITTY_HOME": "/home/op/.kittify",
            "SPEC_KITTY_SAAS_TOKEN": "top-secret-value",
        }
        result = redact(mapping)
        by_name = {r.name: r for r in result}

        assert by_name["SPEC_KITTY_HOME"].value == "/home/op/.kittify"
        assert by_name["SPEC_KITTY_SAAS_TOKEN"].value is None

    def test_empty_mapping_returns_empty_list(self) -> None:
        assert redact({}) == []
