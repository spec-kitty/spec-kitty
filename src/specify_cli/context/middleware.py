"""CLI middleware that loads MissionContext or fails fast.

Provides a typer callback for ``--context <token>``, a helper to extract
context from ``typer.Context.obj``, and a ``require_context`` decorator
for commands that must have a bound context.
"""

from __future__ import annotations

import functools
from pathlib import Path
from typing import Any, Callable, TypeVar

import typer

from kernel.ancestor_walk import find_ancestor
from specify_cli.context.errors import (
    ContextCorruptedError,
    ContextNotFoundError,
)
from specify_cli.context.models import MissionContext
from specify_cli.context.store import load_context

F = TypeVar("F", bound=Callable[..., Any])

_CONTEXT_OBJ_KEY = "mission_context"


def _find_repo_root() -> Path:
    """Walk up from cwd to find repository root (contains .kittify/)."""
    root = find_ancestor(Path.cwd(), lambda parent: (parent / ".kittify").is_dir())
    if root is not None:
        return root
    msg = "Could not find repository root (no .kittify/ directory found)."
    raise typer.BadParameter(msg)


def context_callback(ctx: typer.Context, context: str | None) -> None:
    """Typer callback that loads a MissionContext from a token.

    Attach this as a typer callback parameter to inject context loading:

    .. code-block:: python

        @app.callback()
        def main(
            ctx: typer.Context,
            context: str = typer.Option(None, "--context", help="Context token"),
        ):
            context_callback(ctx, context)

    If ``context`` is provided, the MissionContext is loaded and stored
    on ``ctx.obj``. If ``context`` is None, nothing is stored (commands
    that require context should use ``require_context`` or ``get_context``
    to enforce).

    Args:
        ctx: The typer Context object.
        context: The context token string, or None.

    Raises:
        typer.BadParameter: If the token is provided but cannot be loaded.
    """
    if ctx.obj is None:
        ctx.obj = {}

    if context is None:
        return

    repo_root = _find_repo_root()

    try:
        mission_ctx = load_context(context, repo_root)
    except ContextNotFoundError as exc:
        raise typer.BadParameter(str(exc)) from exc
    except ContextCorruptedError as exc:
        raise typer.BadParameter(str(exc)) from exc

    ctx.obj[_CONTEXT_OBJ_KEY] = mission_ctx


def get_context(ctx: typer.Context) -> MissionContext:
    """Extract MissionContext from typer.Context.obj.

    Args:
        ctx: The typer Context object.

    Returns:
        The loaded MissionContext.

    Raises:
        typer.BadParameter: If no context has been loaded.
    """
    obj: dict[str, Any] = ctx.obj if isinstance(ctx.obj, dict) else {}
    mission_ctx = obj.get(_CONTEXT_OBJ_KEY)

    if not isinstance(mission_ctx, MissionContext):
        msg = (
            "No context token provided. "
            "Run `spec-kitty agent context resolve --wp <WP> --mission <slug>` first, "
            "then pass the token: --context <token>"
        )
        raise typer.BadParameter(msg)

    return mission_ctx


def require_context(func: F) -> F:
    """Decorator that ensures MissionContext is available on ctx.obj.

    Use on typer commands that must have a bound context. The decorated
    function must accept ``ctx: typer.Context`` as its first argument.

    .. code-block:: python

        @app.command()
        @require_context
        def my_command(ctx: typer.Context) -> None:
            mission_ctx = get_context(ctx)
            ...

    Raises:
        typer.BadParameter: If no context has been loaded.
    """

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        # Find the typer.Context in args or kwargs
        ctx: typer.Context | None = None
        for arg in args:
            if isinstance(arg, typer.Context):
                ctx = arg
                break
        if ctx is None:
            ctx_kwarg = kwargs.get("ctx")
            if isinstance(ctx_kwarg, typer.Context):
                ctx = ctx_kwarg

        if ctx is not None:
            # This will raise typer.BadParameter if no context is loaded
            get_context(ctx)

        return func(*args, **kwargs)

    return wrapper  # type: ignore[return-value]
