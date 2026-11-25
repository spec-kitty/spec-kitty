"""The single authority for committed session-presence orientation content (#5215).

Every surface that writes or checks a committed orientation block -- ``init``,
the session-presence migrations (through ``SessionPresenceManager._build_content``),
``spec-kitty upgrade`` surface repair and ``doctor tool-surfaces --fix`` (through
the session-presence tool-surface provider) -- takes its content from
:func:`expected_orientation`. Before #5215 three builders disagreed: the
provider named the checkout *directory* and the manager carried *live* health,
so upgrade and doctor wrote the directory name while the SessionStart hook
printed the recorded project.

Operator rulings (2026-11-20):

1. A committed block carries deterministic health (``healthy``, no upgrade
   line). Only the live SessionStart hook (``SessionPresenceManager.live_content``)
   shows live health.
2. The project name is ``project.slug``, else the git remote repository name,
   else ``"unknown"``. Never the directory name.
"""

from __future__ import annotations

import importlib.metadata
from pathlib import Path

from specify_cli.identity.project import load_identity, slug_from_git_remote

from .content import SessionPresenceContent
from .writers.markdown_rules import MarkdownRulesWriter, block_version, is_tool_written_block, managed_block
from .writers.registry import get_writer

__all__ = [
    "expected_orientation",
    "orientation_drift",
    "orientation_writer",
    "resolve_project_slug",
]

#: The project name used when neither ``project.slug`` nor a git remote names it.
_UNKNOWN_PROJECT_SLUG = "unknown"


def resolve_project_slug(project_root: Path) -> str:
    """Return the project name an orientation block shows.

    ``project.slug`` from ``.kittify/config.yaml``, else the repository name of
    the project's own ``origin`` remote, else ``"unknown"``. ``git`` is spawned only
    when no slug is recorded.
    """
    recorded = load_identity(project_root / ".kittify" / "config.yaml").project_slug
    if recorded:
        return str(recorded)
    # Only the project's own repository names it: git would otherwise walk up
    # to an enclosing repository (a dotfiles repo, a monorepo) and borrow its
    # name. ``.git`` is a directory in a clone and a file in a linked worktree.
    if not (project_root / ".git").exists():
        return _UNKNOWN_PROJECT_SLUG
    return slug_from_git_remote(project_root) or _UNKNOWN_PROJECT_SLUG


def expected_orientation(project_root: Path) -> SessionPresenceContent:
    """Return the committed orientation content for ``project_root``.

    Raises:
        ValueError: when the installed CLI version cannot be read.
    """
    # Looked up through the module at call time, so a patched
    # ``importlib.metadata.version`` (the migrations' tests) is honoured.
    try:
        installed = importlib.metadata.version("spec-kitty-cli")
    except importlib.metadata.PackageNotFoundError as exc:
        raise ValueError("Installed session content version is unavailable") from exc
    if not installed:
        raise ValueError("Installed session content version is unavailable")
    return SessionPresenceContent(installed, resolve_project_slug(project_root), "healthy", None)


def orientation_drift(project_root: Path, rules_path: str) -> bool:
    """Return whether the managed orientation block in ``rules_path`` needs a rewrite.

    Drift means the block exists and either carries another version stamp, or
    is a tool-written rendering whose bytes differ from :func:`expected_orientation`
    (a wrong project name, live health, legacy glyphs). A hand-edited block at
    the installed version is not drift: the writer preserves it. Committed
    content is deterministic, so a current block never drifts on a later run
    (the churn #2265 guarded against came from live health in committed bytes).
    An absent, unreadable or malformed block, or an unknown installed version,
    is not judged here.
    """
    try:
        block = managed_block((project_root / rules_path).read_text(encoding="utf-8"))
        expected = expected_orientation(project_root)
    except (OSError, UnicodeDecodeError, ValueError):
        return False
    if block is None or block == expected.render().rstrip("\n"):
        return False
    stamped = block_version(block)
    if stamped is None:
        return False
    return stamped != expected.version or is_tool_written_block(block, expected)


def orientation_writer(project_root: Path, agent_key: str, configured: set[str] | None) -> MarkdownRulesWriter | None:
    """Return the orientation writer for ``agent_key`` when it applies to this project.

    It applies when the key is configured (or no configuration was read,
    ``configured is None``), the harness has a Markdown-family orientation
    writer, and that writer can write here (its harness directory exists).
    """
    if configured is not None and agent_key not in configured:
        return None
    writer = get_writer(agent_key)
    if not isinstance(writer, MarkdownRulesWriter) or not writer.can_write(project_root):
        return None
    return writer
