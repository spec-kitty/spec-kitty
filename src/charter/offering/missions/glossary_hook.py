"""Bridge module: wires mission primitives to the glossary pipeline via kernel registry.

This module provides the concrete integration point between the mission
framework and the glossary middleware pipeline. Mission executors use
``execute_with_glossary()`` to run any primitive function through the
glossary pipeline before the primitive body executes.

The hook is metadata-driven: it only runs the pipeline when
``glossary_check`` is enabled (the default per FR-020). When disabled,
the primitive runs without glossary checks.

Dependency contract
-------------------
This module depends only on ``kernel.glossary_runner`` — it does **not**
import from ``specify_cli``, and ``specify_cli`` plays no role here.
No eager registration happens anywhere: this hook is the registry's only
production provider and self-bootstraps it on first use in
``_ensure_runner_registered()`` — ``get_runner()``; on ``None``,
``import_module("glossary.attachment")`` (which exposes
``GlossaryAwarePrimitiveRunner``), ``register(GlossaryAwarePrimitiveRunner)``,
then a ``get_runner()`` retry.

Degradation rule: the primitive executes without glossary checks only when
the bootstrap fails — normally because ``import_module("glossary.attachment")``
raises ``ImportError`` (offering-only environments without the ``glossary``
package); ``_ensure_runner_registered`` swallows *any* exception raised while
importing or registering the provider, so a broken provider degrades the same
way.  "No runner registered" is not a steady state in a full install.

.. note::

   **Enforcement honesty (FR-020).** This hook documents ``glossary_check``
   as enabled by default, but as of mission ``dead-port-disposition-01M1TZVN``
   (2026-09) ``execute_with_glossary`` has **zero production call sites** and
   no built-in step contract under ``packs/`` sets ``glossary_check``.  The
   default is therefore enforced nowhere in the live mission loop; the tests
   in ``tests/doctrine/missions/test_glossary_hook.py`` pin the contract, not
   live behaviour.  Wiring the hook into the step executor is a separate
   feature decision (tracked on #1868), not implied by this note.

Usage from a mission executor::

    from charter.offering.missions.glossary_hook import execute_with_glossary

    result = execute_with_glossary(
        primitive_fn=run_specify_step,
        context=ctx,
        repo_root=Path("."),
    )

This module satisfies WP09 success criterion #2: pipeline attaches to
mission primitives automatically when ``glossary_check: enabled`` metadata
is present.
"""

from __future__ import annotations

import logging
from importlib import import_module
from pathlib import Path
from typing import TYPE_CHECKING, Any
from collections.abc import Callable

from kernel.glossary_types import Strictness
from kernel.glossary_runner import get_runner, register

if TYPE_CHECKING:
    from kernel.glossary_runner import GlossaryRunnerProtocol

logger = logging.getLogger(__name__)


def _read_glossary_check_metadata(step_metadata: dict[str, Any]) -> bool:
    """Read glossary_check metadata from a mission step definition.

    Args:
        step_metadata: Step metadata dictionary from mission.yaml.

    Returns:
        True if glossary checks are enabled for this step, False otherwise.
        Default is True (enabled) per FR-020.
    """
    value = step_metadata.get("glossary_check")

    if value is None:
        return True  # enabled by default (FR-020)

    if isinstance(value, bool):
        return value

    if isinstance(value, str):
        if value.lower() == "disabled":
            return False
        if value.lower() == "enabled":
            return True

    return True  # unknown value -> safe default: enabled


def _ensure_runner_registered() -> type[GlossaryRunnerProtocol] | None:
    """Return the registered runner class, self-bootstrapping the registry on first use.

    This is the kernel registry's only production provider (see the module
    docstring).  On an empty registry it imports ``glossary.attachment``,
    registers ``GlossaryAwarePrimitiveRunner``, and retries ``get_runner()``.
    Returns ``None`` only when that bootstrap fails — in practice when
    ``glossary.attachment`` is unimportable (offering-only environments) —
    so the caller degrades to running the primitive without glossary checks.
    """
    runner_cls = get_runner()
    if runner_cls is None:
        # Lazy self-bootstrap: nothing registers eagerly, so the first enabled
        # call installs the concrete runner into the kernel registry.
        try:
            module = import_module("glossary.attachment")
            glossary_aware_runner = module.GlossaryAwarePrimitiveRunner
            register(glossary_aware_runner)
            runner_cls = get_runner()
        except Exception:
            runner_cls = None
    return runner_cls


def execute_with_glossary(
    primitive_fn: Callable[..., Any],
    context: Any,
    repo_root: Path,
    runtime_strictness: Strictness | None = None,
    interaction_mode: str = "interactive",
    *args: Any,
    **kwargs: Any,
) -> Any:
    """Execute a mission primitive with glossary checks.

    This is the main entry point for wiring the glossary pipeline into
    mission execution. It:

    1. Checks whether glossary checks are enabled for this step
       (via context metadata or defaults).
    2. If enabled, ensures a runner is registered (``_ensure_runner_registered()``
       — the lazy self-bootstrap from ``glossary.attachment``) and runs the
       full glossary middleware pipeline on the context before executing the
       primitive.
    3. If ``glossary.attachment`` is unimportable (so no runner can be
       registered), executes the primitive directly (graceful degradation).
    4. Returns whatever the primitive function returns.

    Args:
        primitive_fn: The mission primitive function to execute.
            Must accept a PrimitiveExecutionContext as first argument.
        context: PrimitiveExecutionContext for this step.
        repo_root: Path to repository root.
        runtime_strictness: CLI ``--strictness`` override (highest precedence).
        interaction_mode: ``"interactive"`` or ``"non-interactive"``.
        *args: Extra positional arguments forwarded to primitive_fn.
        **kwargs: Extra keyword arguments forwarded to primitive_fn.

    Returns:
        Whatever primitive_fn returns.

    Raises:
        BlockedByConflict: If unresolved conflicts block generation
            (after clarification has had its chance to resolve them).
        DeferredToAsync: If user deferred conflict resolution.
        AbortResume: If user aborted resume.
    """
    step_metadata = getattr(context, "metadata", {}) or {}
    if not _read_glossary_check_metadata(step_metadata):
        logger.debug(
            "Glossary checks disabled for step=%s, skipping pipeline",
            getattr(context, "step_id", "unknown"),
        )
        return primitive_fn(context, *args, **kwargs)

    runner_cls = _ensure_runner_registered()
    if runner_cls is None:
        logger.debug(
            "No glossary runner registered; executing primitive directly for step=%s",
            getattr(context, "step_id", "unknown"),
        )
        return primitive_fn(context, *args, **kwargs)

    logger.info(
        "Running glossary pipeline for step=%s",
        getattr(context, "step_id", "unknown"),
    )

    runner = runner_cls(
        repo_root=repo_root,
        runtime_strictness=runtime_strictness,
        interaction_mode=interaction_mode,
    )
    return runner.execute(primitive_fn, context, *args, **kwargs)
