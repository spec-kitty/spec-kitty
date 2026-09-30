"""WP02 / FR-003 — drift-proof coverage for the shared /tmp prompt namespace.

Three prompt writers used to root their output directly at the flat, unbounded
``tempfile.gettempdir()``:

- ``runtime.next.prompt_builder`` (``spec-kitty-next-*``)
- ``runtime.next.decision`` (``spec-kitty-composed-{action}-*``, two
  ``mkstemp`` call sites — unbounded, a unique suffix per call)
- ``specify_cli.cli.commands.agent.workflow`` (``spec-kitty-{implement,review}-*``)

All three now write under ``runtime.next._tmp_namespace.prompt_tmp_dir`` — the
single shared, per-repo, sweepable temp-root WP01's session reaper imports.
Every assertion below routes through that same helper (never a hand-copied
path fragment), so a writer silently reverting to a flat ``/tmp`` path — or
the reaper's swept root drifting out of sync with a writer — fails this test
instead of leaking undetected.
"""

from __future__ import annotations

import inspect
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from runtime.next._tmp_namespace import SPEC_KITTY_PROMPT_NAMESPACE, prompt_tmp_dir
from runtime.next.decision import _build_prompt_or_error
from runtime.next.prompt_builder import _write_to_temp, build_decision_prompt
from specify_cli.cli.commands.agent.workflow_executor import write_prompt_to_file as _write_prompt_to_file

pytestmark = [pytest.mark.unit, pytest.mark.fast]


def _assert_under_namespace(path: Path, repo_root: Path) -> None:
    """Shared assertion: *path* falls under the shared namespace root.

    This is exactly the root WP01's session reaper sweeps for *repo_root* —
    a writer that reverts to a flat ``tempfile.gettempdir()`` path fails
    this assertion.
    """
    namespace_root = prompt_tmp_dir(repo_root)
    assert path.is_relative_to(namespace_root), (
        f"{path} is not under the shared namespace root {namespace_root} "
        f"(SPEC_KITTY_PROMPT_NAMESPACE={SPEC_KITTY_PROMPT_NAMESPACE!r}) — "
        "a prompt writer has drifted back to a flat /tmp path"
    )


# ---------------------------------------------------------------------------
# prompt_tmp_dir itself
# ---------------------------------------------------------------------------


class TestPromptTmpDir:
    def test_creates_directory(self, tmp_path: Path) -> None:
        result = prompt_tmp_dir(tmp_path)
        assert result.is_dir()

    def test_stable_for_same_repo_root(self, tmp_path: Path) -> None:
        first_dir = prompt_tmp_dir(tmp_path)
        second_dir = prompt_tmp_dir(tmp_path)
        assert first_dir == second_dir

    def test_distinct_for_distinct_repo_roots(self, tmp_path: Path) -> None:
        other = tmp_path / "other-repo"
        other.mkdir()
        assert prompt_tmp_dir(tmp_path) != prompt_tmp_dir(other)

    def test_rooted_under_namespace_constant(self, tmp_path: Path) -> None:
        result = prompt_tmp_dir(tmp_path)
        assert result.parent.name == SPEC_KITTY_PROMPT_NAMESPACE


# ---------------------------------------------------------------------------
# Writer #1 — runtime.next.prompt_builder (`spec-kitty-next-*`)
# ---------------------------------------------------------------------------


class TestPromptBuilderNamespaced:
    def test_write_to_temp_is_namespaced(self, tmp_path: Path) -> None:
        path = _write_to_temp(
            "implement", "WP01", "content", agent="claude", mission_slug="042-feat", repo_root=tmp_path
        )
        try:
            _assert_under_namespace(path, tmp_path)
            # Return-contract: consumers read the returned path directly.
            assert path.exists()
            assert path.read_text(encoding="utf-8") == "content"
        finally:
            path.unlink(missing_ok=True)

    def test_build_decision_prompt_is_namespaced(self, tmp_path: Path) -> None:
        text, path = build_decision_prompt(
            question="Ship it?",
            options=["yes", "no"],
            decision_id="dec-1",
            mission_slug="042-feat",
            agent="claude",
            repo_root=tmp_path,
        )
        try:
            _assert_under_namespace(path, tmp_path)
            assert path.exists()
            assert path.read_text(encoding="utf-8") == text
        finally:
            path.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Writer #2 — runtime.next.decision (`spec-kitty-composed-{action}-*`)
# Both `mkstemp` sites are unbounded (a unique suffix per call) — the top
# target per FR-003.
# ---------------------------------------------------------------------------


class TestDecisionComposedMarkersNamespaced:
    def test_fast_path_marker_is_namespaced(self, tmp_path: Path) -> None:
        """The ``_is_composed_action`` fast path (~decision.py:610)."""
        with patch(
            "charter.activation.mission_type_profiles.resolve_mission_type_context",
            return_value=SimpleNamespace(action_sequence=["specify", "plan"]),
        ):
            path_str, error, _error_code = _build_prompt_or_error(
                action="specify",
                feature_dir=tmp_path,
                mission_slug="042-feat",
                wp_id=None,
                agent="claude",
                repo_root=tmp_path,
                mission_type="software-dev",
            )
        assert error is None
        assert path_str is not None
        path = Path(path_str)
        try:
            _assert_under_namespace(path, tmp_path)
            assert path.exists()
            assert path.read_text(encoding="utf-8")  # non-empty, consumer-readable
        finally:
            path.unlink(missing_ok=True)

    def test_file_not_found_fallback_marker_is_namespaced(self, tmp_path: Path) -> None:
        """The ``FileNotFoundError`` fallback path (~decision.py:657)."""
        with patch(
            "runtime.next.prompt_builder.build_prompt",
            side_effect=FileNotFoundError("no template for 'discovery'"),
        ):
            path_str, error, _error_code = _build_prompt_or_error(
                action="discovery",
                feature_dir=tmp_path,
                mission_slug="042-feat",
                wp_id=None,
                agent="claude",
                repo_root=tmp_path,
                mission_type="software-dev",
            )
        assert error is None
        assert path_str is not None
        path = Path(path_str)
        try:
            _assert_under_namespace(path, tmp_path)
            assert path.exists()
        finally:
            path.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Writer #3 — specify_cli.cli.commands.agent.workflow
# (`spec-kitty-{implement,review}-*`)
# ---------------------------------------------------------------------------


class TestWorkflowPromptWriterNamespaced:
    def test_implement_command_type_is_namespaced(self, tmp_path: Path) -> None:
        path = _write_prompt_to_file("implement", "042-feat", "WP01", "full prompt content", repo_root=tmp_path)
        try:
            _assert_under_namespace(path, tmp_path)
            assert path.exists()
            assert path.read_text(encoding="utf-8") == "full prompt content"
        finally:
            path.unlink(missing_ok=True)

    def test_review_command_type_is_namespaced(self, tmp_path: Path) -> None:
        """``command_type="review"`` — the other half of the ``{implement|review}`` shape."""
        path = _write_prompt_to_file("review", "042-feat", "WP02", "review content", repo_root=tmp_path)
        try:
            _assert_under_namespace(path, tmp_path)
            assert path.exists()
        finally:
            path.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Single-source-of-truth gate (reviewer guidance)
# ---------------------------------------------------------------------------


class TestSharedConstantSingleSourceOfTruth:
    """No writer may hand-copy the namespace prefix/root — all import it."""

    def test_prompt_builder_imports_shared_helper(self) -> None:
        import runtime.next.prompt_builder as prompt_builder_module

        assert prompt_builder_module.prompt_tmp_dir is prompt_tmp_dir

    def test_decision_imports_shared_helper(self) -> None:
        import runtime.next.decision as decision_module

        assert decision_module.prompt_tmp_dir is prompt_tmp_dir

    def test_workflow_imports_shared_helper(self) -> None:
        import specify_cli.cli.commands.agent.workflow_executor as executor_module

        # workflow_executor.py imports prompt_tmp_dir lazily inside the function (matching
        # this module's other runtime.next imports), so it is not a module
        # attribute — assert the import statement is present in the source.
        source = inspect.getsource(executor_module.write_prompt_to_file)
        assert "from runtime.next._tmp_namespace import prompt_tmp_dir" in source
