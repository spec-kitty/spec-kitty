"""Glossary runner protocol and registry.

This module defines the ``GlossaryRunnerProtocol`` — the abstract contract
that any concrete glossary-aware primitive runner must satisfy — and a
module-level registry (``register()`` / ``get_runner()`` / ``clear_registry()``,
the last one test-only) so that ``charter.offering`` consumers can invoke the
runner without importing the ``glossary`` package eagerly.

Registration contract — the lazy self-bootstrap
------------------------------------------------
**Nobody registers at import or startup.**  The only production provider is
the consumer itself: ``charter.offering.missions.glossary_hook`` calls
``get_runner()`` on first use and, on ``None``, self-bootstraps the registry
in ``_ensure_runner_registered()`` — ``import_module("glossary.attachment")``
(which exposes ``GlossaryAwarePrimitiveRunner`` and registers nothing when
imported), ``register(GlossaryAwarePrimitiveRunner)``, then a ``get_runner()``
retry.  ``specify_cli`` plays no role.

Degradation rule: the hook runs the primitive without glossary checks only
when its bootstrap fails — normally because ``import_module("glossary.attachment")``
raises ``ImportError`` (offering-only environments without the ``glossary``
package); the hook swallows any exception raised while importing or registering
the provider, so a broken provider degrades the same way.  "No runner
registered" is not a steady state in a full install — the first enabled call
populates the registry.

Dependency direction
--------------------
::

    charter.offering  →  kernel.glossary_runner  ←  charter.offering.missions.glossary_hook (lazy provider)  ←  glossary.attachment

Usage — consumer (``charter.offering``)::

    from kernel.glossary_runner import get_runner

    runner_cls = get_runner()
    if runner_cls is not None:
        runner = runner_cls(repo_root=repo_root, ...)
        return runner.execute(primitive_fn, context, *args, **kwargs)
    return primitive_fn(context, *args, **kwargs)

Usage — the self-bootstrap in ``glossary_hook._ensure_runner_registered()``::

    from importlib import import_module

    from kernel.glossary_runner import get_runner, register

    runner_cls = get_runner()
    if runner_cls is None:
        try:
            module = import_module("glossary.attachment")
            register(module.GlossaryAwarePrimitiveRunner)
            runner_cls = get_runner()
        except Exception:
            runner_cls = None  # degrade: run the primitive without glossary checks
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from pathlib import Path


@runtime_checkable
class GlossaryRunnerProtocol(Protocol):
    """Contract for a glossary-aware primitive runner.

    Any class registered via ``register()`` must satisfy this protocol.
    """

    def __init__(
        self,
        repo_root: Path,
        runtime_strictness: Any | None = None,
        interaction_mode: str = "interactive",
    ) -> None: ...

    def execute(
        self,
        primitive_fn: Any,
        context: Any,
        *args: Any,
        **kwargs: Any,
    ) -> Any: ...


# Module-level registry slot — holds the concrete runner class or None.
_registry: type[GlossaryRunnerProtocol] | None = None


def register(runner_cls: type[GlossaryRunnerProtocol]) -> None:
    """Register the concrete glossary runner class.

    Called on first use by the consumer's lazy self-bootstrap
    (``charter.offering.missions.glossary_hook._ensure_runner_registered``),
    never eagerly.  Calling this more than once with the same class is a no-op.  Calling it with a different class
    raises ``RuntimeError`` to catch accidental double-registration.

    Args:
        runner_cls: A class satisfying ``GlossaryRunnerProtocol``.

    Raises:
        TypeError: If ``runner_cls`` does not satisfy the protocol.
        RuntimeError: If a *different* runner class is already registered.
    """
    global _registry  # noqa: PLW0603

    if not isinstance(runner_cls, type):
        raise TypeError(f"runner_cls must be a class, got {type(runner_cls)!r}")

    if _registry is runner_cls:
        # Idempotent: same class registered twice (e.g. re-import) is fine.
        return

    if _registry is not None:
        raise RuntimeError(f"A different glossary runner is already registered: {_registry!r}. Cannot register {runner_cls!r}.")

    _registry = runner_cls


def get_runner() -> type[GlossaryRunnerProtocol] | None:
    """Return the registered glossary runner class, or None if none registered.

    Returns:
        The registered runner class, or ``None``.
    """
    return _registry


def clear_registry() -> None:
    """Reset the registry to None.

    Intended for use in tests only.  Do not call in production code.
    """
    global _registry  # noqa: PLW0603
    _registry = None


__all__ = [
    # GlossaryRunnerProtocol: demoted — no cross-module src/ from-import
    # callers (WP01 harden-dead-symbol-gate-01KW0RJR).
    "register",
    "get_runner",
    # clear_registry: demoted — test-only reset helper; no cross-module src/
    # from-import callers (WP01 harden-dead-symbol-gate-01KW0RJR).
]
