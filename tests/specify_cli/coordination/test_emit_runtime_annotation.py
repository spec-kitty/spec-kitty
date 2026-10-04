"""Precedence tests for ``status_transition.emit_runtime_annotation`` (#5629)."""

from __future__ import annotations

from typing import Any

import pytest

from specify_cli.coordination import status_transition as st

pytestmark = pytest.mark.fast

_KW: dict[str, Any] = {"feature_dir": "fd", "wp_id": "WP01", "delta": "d", "actor": "user", "mission_slug": "m"}


@pytest.fixture
def calls(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, dict[str, Any]]]:
    recorded: list[tuple[str, dict[str, Any]]] = []

    def _tx(**kwargs: Any) -> str:
        recorded.append(("tx", kwargs))
        return "tx-result"

    def _plain(**kwargs: Any) -> str:
        recorded.append(("plain", kwargs))
        return "plain-result"

    monkeypatch.setattr(st, "emit_inner_state_changed_transactional", _tx)
    monkeypatch.setattr("specify_cli.status.emit_inner_state_changed", _plain)
    return recorded


def test_owned_goes_transactional_with_owned_forwarded(calls: list[tuple[str, dict[str, Any]]]) -> None:
    owned = object()
    result = st.emit_runtime_annotation(owned=owned, auto_commit=False, operation="op", **_KW)  # type: ignore[arg-type]
    assert result == "tx-result"
    assert [c[0] for c in calls] == ["tx"]
    assert calls[0][1]["owned"] is owned
    assert calls[0][1]["operation"] == "op"
    assert calls[0][1]["wp_id"] == "WP01"


def test_auto_commit_goes_transactional_without_owned_fact(calls: list[tuple[str, dict[str, Any]]]) -> None:
    result = st.emit_runtime_annotation(owned=None, auto_commit=True, operation="op", **_KW)
    assert result == "tx-result"
    assert [c[0] for c in calls] == ["tx"]
    assert "owned" not in calls[0][1]
    assert calls[0][1]["operation"] == "op"


def test_plain_branch_gets_no_operation_or_owned(calls: list[tuple[str, dict[str, Any]]]) -> None:
    result = st.emit_runtime_annotation(owned=None, auto_commit=False, operation="op", **_KW)
    assert result == "plain-result"
    assert [c[0] for c in calls] == ["plain"]
    assert "operation" not in calls[0][1]
    assert "owned" not in calls[0][1]
    assert calls[0][1] == {**_KW, "repo_root": None}
