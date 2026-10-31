"""FR — one-time repair for issue #254: re-pin a repo's pre-commit hook.

``policy/hook_installer.py`` pins the absolute interpreter path into the
generated pre-commit hook at install time. An install-method migration (e.g.
pipx -> uv) moves that interpreter, and the old path is simply gone the next
time someone commits — a shell-level ``No such file or directory`` naming a
path rather than a cause.

The hook's own run-time fallback (``spec-kitty`` resolved off ``PATH``, see
the hook installer module docstring) already recovers a working commit in
that case. This migration is the complementary REPAIR seam: it re-pins the
hook to the CURRENT interpreter so the fast, PATH-independent primary path
works again, without requiring an ``implement`` lane (the only other caller
of :func:`install`) — recovery would otherwise be circular, since running an
implement lane itself requires committing.

Idempotent: re-running against an already-current hook re-writes the same
effective hook (only the ``# Installed:`` timestamp comment differs).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RepinHooksResult:
    """Outcome of one ``migrate repin-hooks`` run."""

    hook_path: Path
    interpreter: Path


def run_repin_hooks_migration(repo_root: Path) -> RepinHooksResult:
    """Re-install the pre-commit hook, pinning the CURRENT interpreter.

    Raises:
        RuntimeError: propagated from :func:`hook_installer.install` if the
            CURRENT ``sys.executable`` does not refer to an existing file —
            i.e. the environment running this migration is itself broken.
    """
    from specify_cli.cli.commands.migrate._project_admission import admit_migration_project_root
    from specify_cli.policy.hook_installer import install

    root = admit_migration_project_root(repo_root, require_git=True)
    try:
        record = install(root)
    except OSError as exc:
        raise RuntimeError(f"Cannot re-pin hooks in {root}: {exc}") from exc
    return RepinHooksResult(hook_path=record.hook_path, interpreter=record.interpreter)
