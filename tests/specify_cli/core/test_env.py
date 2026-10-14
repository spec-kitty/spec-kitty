"""Tests for the canonical env truthy parser (:mod:`specify_cli.core.env`)."""

from __future__ import annotations

import pytest

from specify_cli.core.env import (
    _TRUTHY_VALUES,
    PRE_REVIEW_GATE_SKIP_ENV_VAR,
    is_truthy,
    pre_review_gate_skip_reason,
)

pytestmark = [pytest.mark.unit, pytest.mark.fast]


@pytest.mark.parametrize(
    "value",
    ["1", "true", "TRUE", " TRUE ", "Yes", "yes", "y", "Y", "on", "ON", " on "],
)
def test_truthy_tokens_return_true(value: str) -> None:
    assert is_truthy(value) is True


@pytest.mark.parametrize(
    "value",
    [None, "", " ", "0", "false", "no", "n", "off", "2", "banana", "enabled"],
)
def test_falsy_values_return_false(value: str | None) -> None:
    assert is_truthy(value) is False


def test_truthy_values_frozenset_is_the_union_grammar() -> None:
    assert frozenset({"1", "true", "yes", "y", "on"}) == _TRUTHY_VALUES


# ---------------------------------------------------------------------------
# Pre-review regression gate (#3980): its own opt-out, no sync vocabulary.
# (The sync kill-switch and moment-handler gate were removed from open-core
# with the hosted drain/relay surface, #6164.)
# ---------------------------------------------------------------------------


def test_pre_review_gate_skip_reason_none_when_unset_or_falsy() -> None:
    assert pre_review_gate_skip_reason({}) is None
    assert pre_review_gate_skip_reason({PRE_REVIEW_GATE_SKIP_ENV_VAR: "0"}) is None


def test_pre_review_gate_skip_reason_names_its_own_var_when_set() -> None:
    assert (
        pre_review_gate_skip_reason({PRE_REVIEW_GATE_SKIP_ENV_VAR: "1"})
        == "SPEC_KITTY_SKIP_PRE_REVIEW_GATE is set"
    )


def test_pre_review_gate_does_not_read_any_sync_vocabulary() -> None:
    """#3980: disarming sync must not silently skip a review gate (and the sync
    vocabulary no longer exists in open-core)."""
    env = {"SPEC_KITTY_SYNC_DISABLE": "1", "SPEC_KITTY_SYNC_MINIMAL_IMPORT": "1"}
    assert pre_review_gate_skip_reason(env) is None
