"""Unit tests for ``charter.activation.invocation_context``."""

from __future__ import annotations

from pathlib import Path

import pytest

from charter.activation.invocation_context import (
    ContextPreconditionError,
    OperationalContext,
    ProjectContext,
    build_operational_context,
)

pytestmark = pytest.mark.unit


def _provision_minimal_config(repo_root: Path) -> None:
    """Write the minimal ``mission_type_activations`` key WP04 (C-A1) requires.

    ``ProjectContext.from_repo`` always constructs a ``PackContext`` via
    ``PackContext.from_config()`` (no try/except around that call), which
    now fail-closes unconditionally when this key is absent -- even for a
    directory with no ``.kittify/`` at all. Most tests below are not about
    that precondition (they exercise ``specs_dir``/``architecture_dir``
    auto-detection or the guard methods), so a minimal config carrying ONLY
    this key unblocks them without touching any other resolution axis.
    """
    kittify = repo_root / ".kittify"
    kittify.mkdir(parents=True, exist_ok=True)
    (kittify / "config.yaml").write_text(
        "mission_type_activations:\n  - software-dev\n", encoding="utf-8"
    )


# ---------------------------------------------------------------------------
# ContextPreconditionError
# ---------------------------------------------------------------------------


class TestContextPreconditionError:
    def test_field_and_context_type_set(self) -> None:
        err = ContextPreconditionError(field="repo_root", context_type="ProjectContext")
        assert err.field == "repo_root"
        assert err.context_type == "ProjectContext"

    def test_str_message_format(self) -> None:
        err = ContextPreconditionError(field="pack_context", context_type="ProjectContext")
        msg = str(err)
        assert "pack_context" in msg
        assert "ProjectContext" in msg

    def test_is_runtime_error(self) -> None:
        err = ContextPreconditionError(field="x", context_type="Y")
        assert isinstance(err, RuntimeError)


# ---------------------------------------------------------------------------
# ProjectContext construction
# ---------------------------------------------------------------------------


class TestProjectContextDefaults:
    def test_all_none_defaults_valid(self) -> None:
        ctx = ProjectContext()
        assert ctx.repo_root is None
        assert ctx.pack_context is None
        assert ctx.org_root is None
        assert ctx.specs_dir is None
        assert ctx.architecture_dir is None

    def test_frozen_cannot_set_field(self) -> None:
        ctx = ProjectContext()
        with pytest.raises((AttributeError, TypeError)):
            ctx.repo_root = Path("/tmp")  # type: ignore[misc]


# ---------------------------------------------------------------------------
# ProjectContext.from_repo()
# ---------------------------------------------------------------------------


class TestProjectContextFromRepo:
    def test_repo_root_populated(self, tmp_path: Path) -> None:
        _provision_minimal_config(tmp_path)
        ctx = ProjectContext.from_repo(tmp_path)
        assert ctx.repo_root == tmp_path

    def test_pack_context_non_none(self, tmp_path: Path) -> None:
        """from_repo() populates pack_context for a provisioned project.

        Provisioning (WP04, C-A1) is a precondition of ``from_repo()``'s
        internal ``PackContext.from_config()`` call: a project with no
        ``mission_type_activations`` key -- with or without a ``.kittify/``
        directory -- fail-closes rather than degrading gracefully.
        """
        _provision_minimal_config(tmp_path)
        ctx = ProjectContext.from_repo(tmp_path)
        assert ctx.pack_context is not None

    def test_specs_dir_detected_when_present(self, tmp_path: Path) -> None:
        _provision_minimal_config(tmp_path)
        (tmp_path / "kitty-specs").mkdir()
        ctx = ProjectContext.from_repo(tmp_path)
        assert ctx.specs_dir == tmp_path / "kitty-specs"

    def test_specs_dir_none_when_absent(self, tmp_path: Path) -> None:
        _provision_minimal_config(tmp_path)
        ctx = ProjectContext.from_repo(tmp_path)
        assert ctx.specs_dir is None

    def test_architecture_dir_detected_when_present(self, tmp_path: Path) -> None:
        _provision_minimal_config(tmp_path)
        (tmp_path / "architecture").mkdir()
        ctx = ProjectContext.from_repo(tmp_path)
        assert ctx.architecture_dir == tmp_path / "architecture"

    def test_architecture_dir_none_when_absent(self, tmp_path: Path) -> None:
        _provision_minimal_config(tmp_path)
        ctx = ProjectContext.from_repo(tmp_path)
        assert ctx.architecture_dir is None

    def test_from_repo_without_kittify_returns_empty_mission_types(
        self, tmp_path: Path
    ) -> None:
        """from_repo() succeeds (does not raise) when .kittify/ is absent.

        The WP04 re-architecture made ``PackContext.from_config()``
        construction TOTAL: an absent ``mission_type_activations`` key reads
        as ``frozenset()`` rather than raising, so ``from_repo`` -- which
        builds a ``PackContext`` with no try/except -- produces a context whose
        ``activated_mission_types`` is empty for a directory with no
        ``.kittify/`` at all. This is the ``ProjectContext``-level counterpart
        of ``tests/charter/test_pack_context.py::
        test_from_config_no_config_yaml_returns_empty_not_raise``. The
        fail-closed for an empty activation set now fires at the
        mission-create boundary, not here.
        """
        assert not (tmp_path / ".kittify").exists()

        ctx = ProjectContext.from_repo(tmp_path)

        assert ctx.pack_context is not None
        assert ctx.pack_context.activated_mission_types == frozenset()


# ---------------------------------------------------------------------------
# Guard methods
# ---------------------------------------------------------------------------


class TestProjectContextGuards:
    def test_require_repo_root_returns_value(self) -> None:
        ctx = ProjectContext(repo_root=Path("/some/path"))
        assert ctx.require_repo_root() == Path("/some/path")

    def test_require_repo_root_raises_when_none(self) -> None:
        ctx = ProjectContext()
        with pytest.raises(ContextPreconditionError) as exc_info:
            ctx.require_repo_root()
        assert exc_info.value.field == "repo_root"
        assert exc_info.value.context_type == "ProjectContext"

    def test_require_pack_context_returns_value(self, tmp_path: Path) -> None:
        _provision_minimal_config(tmp_path)
        ctx = ProjectContext.from_repo(tmp_path)
        pc = ctx.require_pack_context()
        assert pc is ctx.pack_context
        # Assumption check: the provisioned config was actually loaded.
        assert pc.activated_mission_types == frozenset({"software-dev"})

    def test_require_pack_context_raises_when_none(self) -> None:
        ctx = ProjectContext()
        with pytest.raises(ContextPreconditionError) as exc_info:
            ctx.require_pack_context()
        assert exc_info.value.field == "pack_context"
        assert exc_info.value.context_type == "ProjectContext"


# ---------------------------------------------------------------------------
# OperationalContext
# ---------------------------------------------------------------------------


class TestOperationalContext:
    def test_all_none_defaults(self) -> None:
        ctx = OperationalContext()
        assert ctx.active_model is None
        assert ctx.active_profile is None
        assert ctx.active_role is None
        assert ctx.current_activity is None
        assert ctx.tech_stack == frozenset()

    def test_require_active_role_raises_when_none(self) -> None:
        ctx = OperationalContext()
        with pytest.raises(ContextPreconditionError) as exc_info:
            ctx.require_active_role()
        assert exc_info.value.field == "active_role"
        assert exc_info.value.context_type == "OperationalContext"

    def test_require_active_role_returns_value(self) -> None:
        ctx = OperationalContext(active_role="implementer")
        assert ctx.require_active_role() == "implementer"


class TestBuildOperationalContext:
    def test_all_fields_none(self) -> None:
        ctx = build_operational_context()
        assert ctx.active_profile is None
        assert ctx.active_role is None
        assert ctx.tech_stack == frozenset()
