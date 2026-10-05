"""``claim_policy_metadata`` -- the one shared claim ``policy_metadata`` builder (implement-degod WP08).

Exported by the status facade next to ``build_claim_policy_metadata`` and used by both
``cli.commands.implement_claim`` and ``cli.commands.agent.workflow_executor``. Kept in the
status test matrix so the diff-cover gate covers the ``status/*`` critical path.
"""

from __future__ import annotations

import pytest

from specify_cli import status
from specify_cli.status import emit

pytestmark = pytest.mark.fast

_BASELINE = "2026-10-05T00:00:00+00:00"
#: The creation-time probe ``claim_policy_metadata`` calls (patched by target, not by object).
_CAPTURE_BASELINE = "specify_cli.core.process_liveness.capture_creation_time_baseline"


def test_baseline_captured_yields_full_triple(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(_CAPTURE_BASELINE, lambda pid: _BASELINE)

    assert status.claim_policy_metadata(4242, "claude") == {
        "shell_pid": 4242,
        "shell_pid_created_at": _BASELINE,
        "agent": "claude",
    }


def test_no_baseline_omits_created_at_instead_of_fabricating(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(_CAPTURE_BASELINE, lambda pid: None)

    assert status.claim_policy_metadata(4242, "claude") == {"shell_pid": 4242, "agent": "claude"}


def test_baseline_is_captured_for_the_given_pid(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[int] = []

    def _capture(pid: int) -> str:
        seen.append(pid)
        return _BASELINE

    monkeypatch.setattr(_CAPTURE_BASELINE, _capture)

    emit.claim_policy_metadata(77, "codex")

    assert seen == [77]


def test_full_triple_matches_the_shape_authority(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(_CAPTURE_BASELINE, lambda pid: _BASELINE)

    assert status.claim_policy_metadata(9, "a") == status.build_claim_policy_metadata(9, _BASELINE, "a")


def test_facade_and_owner_are_the_same_definition() -> None:
    assert status.claim_policy_metadata is emit.claim_policy_metadata
