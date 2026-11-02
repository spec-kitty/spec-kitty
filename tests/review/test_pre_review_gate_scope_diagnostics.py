"""#6865 FR-006/FR-007: a refusal names the scope the gate actually chose.

The pre-review gate's timeout refusal used to say "normalized targets: (empty)"
and "a classification candidate for a reviewed metadata update" without naming
the scope shape, the command that ran or the metadata it referred to. These
cases drive the real verdict tail with a controlled clock so the two shapes are
asserted on one fixture family: a whole declared command run (non-narrowing
source) and a bounded target list (the FR-004 override tier).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from specify_cli.review import pre_review_gate
from specify_cli.review.pre_review_gate import GateOutcome, ScopeResult

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_DECLARED_COMMAND = "make test-review"
_REASON_MAX_CHARS = 800


class _FakeProcess:
    """The minimum ``Popen`` surface the runner's lifecycle touches."""

    def __init__(self) -> None:
        self.returncode = 1
        self.pid = 4242

    def communicate(self, timeout: float | None = None) -> tuple[str, str]:
        del timeout
        return "", ""

    def poll(self) -> int:
        return self.returncode


class _WholeCommandSource:
    """A scope source with NO per-file narrowing — the production shape."""

    def test_command(self) -> list[str]:
        return ["sh", "-c", _DECLARED_COMMAND]

    def file_to_scope(self, _path: str) -> tuple[str, ...]:
        return ()

    def parse_results(self, _raw: object) -> tuple[object, ...]:
        return ()

    def parse_mode(self, _raw: object) -> str:
        return "text"


def _drive_timeout(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *,
    scope_source: object | None,
    scope: ScopeResult | None = None,
    timeout: int = 300,
):
    """Run one gate evaluation that times out deterministically."""
    process = _FakeProcess()

    def _wait(candidate: subprocess.Popen[str], _timeout: float) -> tuple[str, str]:
        del candidate
        return "", "stalled"

    monkeypatch.setattr(pre_review_gate.subprocess, "Popen", lambda *args, **kwargs: process)
    monkeypatch.setattr(pre_review_gate, "_signal_owned_process_tree", lambda *args, **kwargs: None)
    monkeypatch.setattr(pre_review_gate, "_scoped_run_lock", lambda **_kwargs: _nullcontext())
    # started_at, then a reading past the deadline -> the runner reports TIMED_OUT.
    clock = iter((0.0, float(timeout) + 5.0, float(timeout) + 5.0, float(timeout) + 5.0))

    if scope is not None:
        return pre_review_gate.evaluate_with_scope(
            scope,
            repo_root=tmp_path,
            baseline=None,
            timeout=timeout,
            monotonic=lambda: next(clock),
            wait=_wait,
        )
    return pre_review_gate.evaluate_pre_review_gate(
        ["src/specify_cli/review/pre_review_gate.py"],
        repo_root=tmp_path,
        baseline=None,
        timeout=timeout,
        scope_source=scope_source,  # type: ignore[arg-type]
        monotonic=lambda: next(clock),
        wait=_wait,
    )


class _nullcontext:
    """Minimal stand-in for ``contextlib.nullcontext`` in the lock seam."""

    def __enter__(self) -> None:
        return None

    def __exit__(self, *exc: object) -> bool:
        return False


@pytest.fixture()
def repo_root(tmp_path: Path) -> Path:
    kittify = tmp_path / ".kittify"
    kittify.mkdir(parents=True, exist_ok=True)
    (kittify / "config.yaml").write_text("review:\n  test_command: 'make test-review'\n", encoding="utf-8")
    return tmp_path


def test_whole_command_timeout_names_the_scope_the_command_and_the_policy_metadata(monkeypatch: pytest.MonkeyPatch, repo_root: Path) -> None:
    verdict = _drive_timeout(monkeypatch, repo_root, scope_source=_WholeCommandSource())

    assert verdict.outcome is GateOutcome.TIMED_OUT
    reason = verdict.reason or ""
    assert "whole declared command" in reason
    assert _DECLARED_COMMAND in reason
    assert "review.test_timeout_seconds" in reason
    assert "gate_budget" in reason and "_RULES" in reason
    # Both recoveries for this shape are named, so the operator can act.
    assert "pre_review_test_scope" in reason
    assert "--skip-pre-review-gate" not in reason


def test_whole_command_timeout_reason_is_single_line_and_bounded(monkeypatch: pytest.MonkeyPatch, repo_root: Path) -> None:
    verdict = _drive_timeout(monkeypatch, repo_root, scope_source=_WholeCommandSource())

    reason = verdict.reason or ""
    assert "\n" not in reason
    assert len(reason) <= _REASON_MAX_CHARS


def test_bounded_timeout_names_its_own_shape_and_never_the_whole_command(monkeypatch: pytest.MonkeyPatch, repo_root: Path) -> None:
    verdict = _drive_timeout(
        monkeypatch,
        repo_root,
        scope_source=None,
        scope=ScopeResult.from_override(("tests/review",)),
    )

    assert verdict.outcome is GateOutcome.TIMED_OUT
    reason = verdict.reason or ""
    assert "bounded" in reason
    assert "tests/review" in reason
    assert "whole declared command" not in reason
    assert _DECLARED_COMMAND not in reason
    assert "--skip-pre-review-gate" in reason


def test_oversized_refusal_names_the_bounded_shape(monkeypatch: pytest.MonkeyPatch, repo_root: Path) -> None:
    verdict = pre_review_gate.evaluate_with_scope(
        ScopeResult.from_override(("tests/architectural",)),
        repo_root=repo_root,
        baseline=None,
        timeout=300,
    )

    assert verdict.outcome is GateOutcome.SCOPE_OVERSIZED
    reason = verdict.reason or ""
    assert "bounded" in reason
    assert "tests/architectural" in reason
    assert "whole declared command" not in reason


def test_an_already_classified_timeout_still_names_the_shape(monkeypatch: pytest.MonkeyPatch, repo_root: Path) -> None:
    """The pinned bounded vector classifies as bounded, so it is not a candidate.

    It must still name the shape and the recovery — the pre-#6865 message said
    only that the run had timed out (#6865, FR-006).
    """
    from specify_cli.review.gate_budget import BudgetClassification

    scope = ScopeResult.from_override(("tests/review/test_gate_budget.py::test_identity_matches_pinned_vector",))
    verdict = _drive_timeout(monkeypatch, repo_root, scope_source=None, scope=scope)

    assert verdict.outcome is GateOutcome.TIMED_OUT
    assert verdict.budget_assessment is not None
    assert verdict.budget_assessment.classification is BudgetClassification.BOUNDED
    assert verdict.classification_candidate is False
    reason = verdict.reason or ""
    assert "bounded target list" in reason
    assert "Recovery:" in reason
    assert "whole declared command" not in reason
