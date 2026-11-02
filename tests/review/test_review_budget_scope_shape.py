"""#6865 FR-004/FR-005/FR-008: the review budget matches the scope the gate chose.

A repository whose declared review command runs in full (the production
``DeclaredCommandScopeSource`` narrows nothing per file) is not running a scoped
check, so the scoped 300 s default under-bounds it. These cases pin the
shape-dependent default, the declared-value precedence, the unchanged scoped
default and the one-number-per-transition rule at the production seam
(``tasks_move_task_gates._mt_review_test_timeout``).
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from specify_cli.cli.commands.agent import tasks_move_task_gates
from specify_cli.review.test_timeout import (
    DEFAULT_TEST_TIMEOUT_SECONDS,
    InvalidReviewTestTimeout,
    WHOLE_COMMAND_TEST_TIMEOUT_SECONDS,
    resolve_review_test_timeout,
)

pytestmark = [pytest.mark.unit, pytest.mark.fast]


def _repo(tmp_path: Path, review_block: str | None = None) -> Path:
    """A repo root whose ``.kittify/config.yaml`` declares (or omits) the budget."""
    kittify = tmp_path / ".kittify"
    kittify.mkdir(parents=True, exist_ok=True)
    config = "review:\n  test_command: 'make test-fast'\n"
    if review_block:
        config = f"review:\n  test_command: 'make test-fast'\n{review_block}"
    (kittify / "config.yaml").write_text(config, encoding="utf-8")
    return tmp_path


def test_whole_command_shape_uses_the_whole_command_default(tmp_path: Path) -> None:
    repo = _repo(tmp_path)

    assert resolve_review_test_timeout(repo, whole_command=True) == WHOLE_COMMAND_TEST_TIMEOUT_SECONDS


def test_bounded_shape_keeps_the_scoped_default(tmp_path: Path) -> None:
    repo = _repo(tmp_path)

    assert resolve_review_test_timeout(repo, whole_command=False) == DEFAULT_TEST_TIMEOUT_SECONDS
    # The whole-command default is deliberately larger: a whole declared command
    # is not the bounded run the scoped default was priced for.
    assert WHOLE_COMMAND_TEST_TIMEOUT_SECONDS > DEFAULT_TEST_TIMEOUT_SECONDS


@pytest.mark.parametrize("shape", [True, False], ids=["whole-command", "bounded"])
def test_a_declared_budget_wins_over_the_shape_default(tmp_path: Path, shape: bool) -> None:
    repo = _repo(tmp_path, review_block="  test_timeout_seconds: 900\n")

    assert resolve_review_test_timeout(repo, whole_command=shape) == 900


@pytest.mark.parametrize("shape", [True, False], ids=["whole-command", "bounded"])
def test_an_explicit_api_override_wins_over_everything(tmp_path: Path, shape: bool) -> None:
    repo = _repo(tmp_path, review_block="  test_timeout_seconds: 900\n")

    assert resolve_review_test_timeout(repo, 1200, whole_command=shape) == 1200


@pytest.mark.parametrize("shape", [True, False], ids=["whole-command", "bounded"])
def test_an_invalid_declaration_is_never_masked_by_the_shape_default(tmp_path: Path, shape: bool) -> None:
    repo = _repo(tmp_path, review_block="  test_timeout_seconds: true\n")

    with pytest.raises(InvalidReviewTestTimeout, match="review.test_timeout_seconds"):
        resolve_review_test_timeout(repo, whole_command=shape)


def _state(repo: Path) -> SimpleNamespace:
    """The minimal ``_MoveTaskState`` surface ``_mt_review_test_timeout`` reads."""
    return SimpleNamespace(main_repo_root=repo, owned=None)


def test_production_seam_resolves_the_whole_command_default(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The gate's own seam, against a repo whose source narrows nothing."""
    repo = _repo(tmp_path)
    monkeypatch.setattr(
        tasks_move_task_gates,
        "_mt_resolve_scope_source",
        lambda _root: _whole_command_source(),
    )
    state = _state(repo)

    assert tasks_move_task_gates._mt_review_test_timeout(state) == WHOLE_COMMAND_TEST_TIMEOUT_SECONDS
    # Memoised: a second read cannot resolve a different number mid-transition.
    assert tasks_move_task_gates._mt_review_test_timeout(state) == WHOLE_COMMAND_TEST_TIMEOUT_SECONDS


def test_production_seam_keeps_the_scoped_default_for_a_narrowing_source(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _repo(tmp_path)
    monkeypatch.setattr(
        tasks_move_task_gates,
        "_mt_resolve_scope_source",
        lambda _root: _narrowing_source(),
    )

    assert tasks_move_task_gates._mt_review_test_timeout(_state(repo)) == DEFAULT_TEST_TIMEOUT_SECONDS


def test_production_seam_honours_the_declared_budget(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _repo(tmp_path, review_block="  test_timeout_seconds: 777\n")
    monkeypatch.setattr(
        tasks_move_task_gates,
        "_mt_resolve_scope_source",
        lambda _root: _whole_command_source(),
    )

    assert tasks_move_task_gates._mt_review_test_timeout(_state(repo)) == 777


def _whole_command_source() -> object:
    """A source with NO per-file narrowing — the production shape."""

    class _Source:
        def test_command(self) -> list[str]:
            return ["sh", "-c", "make test-fast"]

        def file_to_scope(self, _path: str) -> tuple[str, ...]:
            return ()

        def parse_results(self, _raw: object) -> tuple[object, ...]:
            return ()

        def parse_mode(self, _raw: object) -> str:
            return "text"

    return _Source()


def _narrowing_source() -> object:
    """A source that DOES narrow per file (the ``ScopeBreakdownSource`` refinement)."""

    class _Source:
        def test_command(self) -> list[str]:
            return ["python", "-m", "pytest"]

        def file_to_scope(self, path: str) -> tuple[str, ...]:
            return (path,)

        def scope_breakdown(self, path: str) -> object:
            del path
            return SimpleNamespace(test_targets=("tests/unit",), contributes_scope=True)

        def parse_results(self, _raw: object) -> tuple[object, ...]:
            return ()

        def parse_mode(self, _raw: object) -> str:
            return "junit_xml"

    return _Source()
