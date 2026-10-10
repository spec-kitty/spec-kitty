"""Invocation context module for the ``charter.*`` package.

Defines three dataclasses: ``ContextPreconditionError``, ``ProjectContext``,
and ``OperationalContext``.  ``ProjectContext`` provides a ``from_repo()``
factory that produces fully-populated instances from a repository root path.
Guard methods on both context types raise ``ContextPreconditionError``
(not ``ValueError``) when a required field is absent.

``OperationalContext`` is specced here but not wired to any production call
site — it is an in-flight stub whose symbols are explicitly allowlisted in
the dead-symbol architectural test so the ratchet does not reject them.

Layer rule
----------
This module MUST NOT import from ``specify_cli`` (C-001, hard ratchet pinned
by ``tests/architectural/test_layer_rules.py``).  ``PackContext`` is imported
only under ``TYPE_CHECKING`` at the module level and via a runtime import
inside ``from_repo()`` to avoid circular imports.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from charter.activation.pack_context import PackContext

_SPECS_DIR_NAME = "kitty-specs"


# ---------------------------------------------------------------------------
# Error type
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ContextPreconditionError(RuntimeError):
    """Raised by context guard methods when a required field is absent.

    ``hint`` is an optional actionable remediation string explaining how the
    caller can supply the missing field; when present it is appended to the
    error message.
    """

    field: str
    context_type: str
    hint: str | None = None

    def __str__(self) -> str:
        base = (
            f"Context precondition failed: '{self.field}' is required "
            f"but absent in {self.context_type}"
        )
        if self.hint:
            return f"{base}. {self.hint}"
        return base

    def __post_init__(self) -> None:
        # Ensure the RuntimeError base receives the message string so that
        # callers catching RuntimeError and calling str(exc) get a useful message.
        super().__init__(str(self))


# ---------------------------------------------------------------------------
# ProjectContext
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ProjectContext:
    """Resolved context for a spec-kitty project.

    All fields are optional so instances can be constructed partially
    in tests and in partial-discovery scenarios.
    ``from_repo()`` always returns a fully-populated instance.
    """

    repo_root: Path | None = None
    pack_context: PackContext | None = None
    specs_dir: Path | None = None
    architecture_dir: Path | None = None

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def from_repo(cls, repo_root: Path) -> ProjectContext:
        """Construct a fully-populated ProjectContext from a repository root.

        Resolves PackContext via ``PackContext.from_config()``.
        ``specs_dir`` and ``architecture_dir`` are set only when the
        corresponding directories exist on disk.
        """
        from charter.activation.pack_context import PackContext  # runtime import — avoids circular

        pack_ctx = PackContext.from_config(repo_root)

        specs_path = repo_root / _SPECS_DIR_NAME
        arch_path = repo_root / "architecture"

        return cls(
            repo_root=repo_root,
            pack_context=pack_ctx,
            specs_dir=specs_path if specs_path.is_dir() else None,
            architecture_dir=arch_path if arch_path.is_dir() else None,
        )

    # ------------------------------------------------------------------
    # Guard methods
    # ------------------------------------------------------------------

    def require_repo_root(self) -> Path:
        """Return ``repo_root`` or raise ``ContextPreconditionError``."""
        if self.repo_root is None:
            raise ContextPreconditionError(
                field="repo_root", context_type="ProjectContext"
            )
        return self.repo_root

    def require_pack_context(self) -> PackContext:
        """Return ``pack_context`` or raise ``ContextPreconditionError``."""
        if self.pack_context is None:
            raise ContextPreconditionError(
                field="pack_context", context_type="ProjectContext"
            )
        return self.pack_context


# ---------------------------------------------------------------------------
# OperationalContext
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class OperationalContext:
    """Runtime context about the active agent session.

    Holds the runtime facts about the agent invocation that is currently
    executing: the active model, profile, role, the activity being performed,
    and the technology stack in scope.

    All fields are optional so instances can be constructed partially in tests
    and in partial-discovery scenarios.  Guard methods raise
    ``ContextPreconditionError`` with actionable messages when a required field
    is absent.
    """

    active_model: str | None = None
    active_profile: str | None = None
    active_role: str | None = None
    current_activity: str | None = None
    tech_stack: frozenset[str] = field(default_factory=frozenset)

    # ------------------------------------------------------------------
    # Guard methods
    # ------------------------------------------------------------------

    def require_active_role(self) -> str:
        """Return ``active_role`` or raise ``ContextPreconditionError``.

        When ``active_role`` is absent the raised error explains how to supply
        it: by passing ``active_role=`` to :func:`build_operational_context`.
        """
        if self.active_role is None:
            raise ContextPreconditionError(
                field="active_role",
                context_type="OperationalContext",
                hint=(
                    "Resolve the active agent role and pass it as "
                    "build_operational_context(active_role=<role>)."
                ),
            )
        return self.active_role


# ---------------------------------------------------------------------------
# Module-level assembler
# ---------------------------------------------------------------------------


def build_operational_context(
    *,
    active_model: str | None = None,
    active_profile: str | None = None,
    active_role: str | None = None,
    current_activity: str | None = None,
    tech_stack: frozenset[str] | None = None,
) -> OperationalContext:
    """Assemble an :class:`OperationalContext` from explicit caller-supplied values.

    This is a **pure assembler**: it packages the values its caller passes and
    nothing else.  It does NOT read runtime, global, or environment state, and
    it does NOT import ``specify_cli`` or ``charter.offering`` runtime.  Callers are
    responsible for resolving the runtime facts (which model, profile, role,
    activity, and tech stack are active) and passing them in as data — this is
    what keeps the ``charter.*`` layer free of upward dependencies (C-006).

    Wiring this assembler to live call sites is performed by the callers
    themselves; see the activation-layer call-site work package.

    Args:
        active_model: Identifier of the active model, or ``None`` if unknown.
        active_profile: Identifier of the active agent profile, or ``None``.
        active_role: Active agent role, or ``None``.
        current_activity: The activity currently being performed, or ``None``.
        tech_stack: Frozen set of in-scope technologies; ``None`` is normalised
            to an empty frozenset.

    Returns:
        A populated :class:`OperationalContext` carrying exactly the values
        provided.
    """
    return OperationalContext(
        active_model=active_model,
        active_profile=active_profile,
        active_role=active_role,
        current_activity=current_activity,
        tech_stack=frozenset() if tech_stack is None else frozenset(tech_stack),
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

__all__ = [
    "ContextPreconditionError",
    "OperationalContext",
    "ProjectContext",
    "build_operational_context",
]
