"""Behavioral tests for execute_with_glossary hook and _read_glossary_check_metadata.

Targets mutation-prone areas:
- _read_glossary_check_metadata: key name, None guard, disabled/enabled string
  comparisons, bool handling, unknown-value default
- execute_with_glossary: metadata extraction, no-runner fallback, result forwarding
- the self-bootstrap contract (mission ``dead-port-disposition-01M1TZVN``, FR-009):
  ``execute_with_glossary`` is the only production provider of the kernel
  glossary-runner registry, and degrades only when ``glossary.attachment`` is
  unimportable
- the design story (SC-004 / FR-010): the four documentation sites describe that
  contract, not a registration-by-``specify_cli``/``glossary`` fiction

Patterns: Boundary Pair (disabled/enabled strings, bool False vs None),
Non-Identity Inputs (distinct metadata keys), Bi-Directional Logic
(True vs. False return from enablement check).
"""

import re
import sys
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import Mock, patch

import charter.offering.missions.glossary_hook as glossary_hook_module
import kernel
import kernel.glossary_runner as glossary_runner_module
from charter.offering.missions.glossary_hook import _read_glossary_check_metadata, execute_with_glossary
from charter.offering.missions.primitives import PrimitiveExecutionContext
from kernel.glossary_runner import clear_registry, get_runner
import pytest

pytestmark = [pytest.mark.fast, pytest.mark.doctrine]


@pytest.fixture(autouse=True)
def _clean_registry() -> Iterator[None]:
    """Reset the process-global kernel registry before and after every test.

    The self-bootstrap pins below register the real ``GlossaryAwarePrimitiveRunner``;
    without this teardown a later test in the same worker that registers a
    different class would hit the registry's double-registration ``RuntimeError``.
    """
    clear_registry()
    yield
    clear_registry()


# ── _read_glossary_check_metadata ──────────────────────────────────────────────


class TestReadGlossaryCheckMetadata:
    """Boundary pairs on key name, None guard, and string comparison."""

    def test_absent_key_returns_true(self):
        assert _read_glossary_check_metadata({}) is True

    def test_absent_key_non_empty_dict_returns_true(self):
        assert _read_glossary_check_metadata({"other_key": "value"}) is True

    def test_glossary_check_key_is_read(self):
        # Value must come from "glossary_check", not some other key
        result = _read_glossary_check_metadata({"glossary_check": "disabled"})
        assert result is False

    def test_wrong_key_falls_through_to_default(self):
        result = _read_glossary_check_metadata({"glossary_check_flag": "disabled"})
        assert result is True

    def test_none_value_returns_true(self):
        assert _read_glossary_check_metadata({"glossary_check": None}) is True

    def test_bool_false_returns_false(self):
        assert _read_glossary_check_metadata({"glossary_check": False}) is False

    def test_bool_true_returns_true(self):
        assert _read_glossary_check_metadata({"glossary_check": True}) is True

    def test_string_disabled_returns_false(self):
        assert _read_glossary_check_metadata({"glossary_check": "disabled"}) is False

    def test_string_enabled_returns_true(self):
        assert _read_glossary_check_metadata({"glossary_check": "enabled"}) is True

    def test_string_disabled_case_insensitive(self):
        assert _read_glossary_check_metadata({"glossary_check": "DISABLED"}) is False

    def test_string_enabled_case_insensitive(self):
        assert _read_glossary_check_metadata({"glossary_check": "ENABLED"}) is True

    def test_unknown_string_returns_true(self):
        assert _read_glossary_check_metadata({"glossary_check": "maybe"}) is True

    def test_disabled_returns_false_not_true(self):
        result = _read_glossary_check_metadata({"glossary_check": "disabled"})
        assert result is not True

    def test_enabled_returns_true_not_false(self):
        result = _read_glossary_check_metadata({"glossary_check": "enabled"})
        assert result is not False


# ── execute_with_glossary ──────────────────────────────────────────────────────


def _make_ctx(metadata: dict | None = None) -> PrimitiveExecutionContext:
    return PrimitiveExecutionContext(
        step_id="step-001",
        mission_id="mission-001",
        run_id="run-001",
        inputs={},
        metadata=metadata or {},
        config={},
    )


class TestGlossaryHookEnablement:
    """Verify hook respects glossary_check metadata."""

    def test_skips_pipeline_when_disabled(self):
        primitive_fn = Mock(return_value="result")
        ctx = _make_ctx({"glossary_check": "disabled"})
        result = execute_with_glossary(primitive_fn=primitive_fn, context=ctx, repo_root=Path("/tmp"))
        assert result == "result"
        primitive_fn.assert_called_once_with(ctx)

    def test_skips_pipeline_when_bool_false(self):
        primitive_fn = Mock(return_value="result")
        ctx = _make_ctx({"glossary_check": False})
        result = execute_with_glossary(primitive_fn=primitive_fn, context=ctx, repo_root=Path("/tmp"))
        assert result == "result"
        primitive_fn.assert_called_once_with(ctx)

    def test_reads_metadata_from_context(self):
        primitive_fn = Mock(return_value="ok")
        ctx = _make_ctx({"glossary_check": "disabled"})
        result = execute_with_glossary(primitive_fn=primitive_fn, context=ctx, repo_root=Path("/tmp"))
        assert result == "ok"

    def test_no_runner_registered_falls_through_to_primitive(self):
        primitive_fn = Mock(return_value="fallback-result")
        ctx = _make_ctx({})
        # Patch get_runner to return None — simulates no runner registered
        with (
            patch("charter.offering.missions.glossary_hook.get_runner", return_value=None),
            patch("charter.offering.missions.glossary_hook.import_module", side_effect=ImportError),
        ):
            result = execute_with_glossary(
                primitive_fn=primitive_fn, context=ctx, repo_root=Path("/tmp")
            )
        assert result == "fallback-result"
        primitive_fn.assert_called_once_with(ctx)

    def test_context_with_empty_metadata_still_runs(self):
        primitive_fn = Mock(return_value="ran")
        ctx = _make_ctx({})
        with (
            patch("charter.offering.missions.glossary_hook.get_runner", return_value=None),
            patch("charter.offering.missions.glossary_hook.import_module", side_effect=ImportError),
        ):
            result = execute_with_glossary(
                primitive_fn=primitive_fn, context=ctx, repo_root=Path("/tmp")
            )
        assert result == "ran"


class TestPrimitiveForwarding:
    """Verify primitive execution returns correct results."""

    def test_returns_primitive_result(self):
        primitive_fn = Mock(return_value={"status": "done", "output": [1, 2, 3]})
        ctx = _make_ctx({"glossary_check": False})
        result = execute_with_glossary(
            primitive_fn=primitive_fn, context=ctx, repo_root=Path("/tmp")
        )
        assert result == {"status": "done", "output": [1, 2, 3]}

    def test_disabled_path_returns_primitive_result_directly(self):
        expected = object()
        primitive_fn = Mock(return_value=expected)
        ctx = _make_ctx({"glossary_check": "disabled"})
        result = execute_with_glossary(
            primitive_fn=primitive_fn, context=ctx, repo_root=Path("/tmp")
        )
        assert result is expected


# ── Self-bootstrap contract (FR-009) ──────────────────────────────────────────


class TestSelfBootstrapContract:
    """Pin the registration contract documented in ``kernel.glossary_runner``.

    Nobody registers at import or startup: the consumer lazily self-bootstraps
    the registry on first use, and runs the primitive without glossary checks
    only when ``glossary.attachment`` itself cannot be imported.
    """

    def test_execute_with_glossary_self_bootstraps_registry(self, tmp_path: Path) -> None:
        """Invariant G-2: a cleared registry is populated by the first enabled call."""
        (tmp_path / ".kittify").mkdir()
        assert get_runner() is None
        primitive_fn = Mock(return_value="bootstrapped")
        ctx = _make_ctx({})  # glossary_check absent -> enabled (FR-020 default)

        result = execute_with_glossary(primitive_fn=primitive_fn, context=ctx, repo_root=tmp_path)

        assert result == "bootstrapped"
        primitive_fn.assert_called_once()
        runner = get_runner()
        assert runner is not None
        assert type(runner) is type  # a class is registered, never an instance
        assert runner.__name__ == "GlossaryAwarePrimitiveRunner"
        assert runner.__module__ == "glossary.attachment"

    def test_execute_with_glossary_degrades_only_when_attachment_unimportable(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Degradation rule: direct execution only when the bootstrap fails (here: ``import_module`` raises ``ImportError``)."""
        (tmp_path / ".kittify").mkdir()
        assert get_runner() is None
        # A ``None`` entry in ``sys.modules`` makes ``import_module`` raise ImportError
        # (pure-doctrine environment without the glossary package).
        monkeypatch.setitem(sys.modules, "glossary.attachment", None)
        expected = object()
        primitive_fn = Mock(return_value=expected)
        ctx = _make_ctx({})

        result = execute_with_glossary(primitive_fn=primitive_fn, context=ctx, repo_root=tmp_path)

        assert result is expected
        primitive_fn.assert_called_once_with(ctx)
        assert get_runner() is None


# ── Design story (SC-004 / FR-010) ────────────────────────────────────────────


# Invariant G-1 (data-model §4): the same pattern the SC-004 grep uses.
_REGISTRATION_FICTION = re.compile(r"at import time|at startup|registers the concrete|specify_cli.*register")


def _design_story_sites() -> dict[str, str]:
    """The four sites that must describe the self-bootstrap contract."""
    kernel_dir = Path(kernel.__file__).resolve().parent
    return {
        "kernel/glossary_runner.py": Path(glossary_runner_module.__file__).read_text(encoding="utf-8"),
        "kernel/__init__.py": Path(kernel.__file__).read_text(encoding="utf-8"),
        "kernel/README.md": (kernel_dir / "README.md").read_text(encoding="utf-8"),
        "charter/offering/missions/glossary_hook.py": Path(glossary_hook_module.__file__).read_text(encoding="utf-8"),
    }


class TestDesignStory:
    """The four sites tell the truth about who registers (SC-004) and about FR-020 (SC-005)."""

    @pytest.mark.parametrize("site", sorted(_design_story_sites()))
    def test_site_carries_no_registration_fiction(self, site: str) -> None:
        text = _design_story_sites()[site]
        offending = [line for line in text.splitlines() if _REGISTRATION_FICTION.search(line)]
        assert offending == [], f"{site} still describes registration at import/startup: {offending}"

    @pytest.mark.parametrize("site", sorted(_design_story_sites()))
    def test_site_names_the_self_bootstrap(self, site: str) -> None:
        text = _design_story_sites()[site]
        assert "self-bootstrap" in text, f"{site} does not describe the self-bootstrap contract"

    def test_hook_documents_its_own_bootstrap_helper(self) -> None:
        assert "_ensure_runner_registered" in (glossary_hook_module.__doc__ or "")
        assert callable(getattr(glossary_hook_module, "_ensure_runner_registered", None))

    def test_hook_carries_the_fr020_enforcement_honesty_note(self) -> None:
        # Whitespace-normalized: the docstring is free to wrap these phrases.
        doc = " ".join((glossary_hook_module.__doc__ or "").split())
        assert "Enforcement honesty (FR-020)" in doc
        assert "zero production call sites" in doc
        assert "separate feature decision" in doc
