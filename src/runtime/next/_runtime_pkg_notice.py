"""One-time deprecation notice for stale `spec-kitty-runtime` installs.

Implements FR-020 of mission ``shared-package-boundary-cutover-01KQ22DS``.

Detects, via :mod:`importlib.metadata`, whether the retired
``spec-kitty-runtime`` PyPI package is still installed in the operator's
environment. If it is, emits a single one-time notice on stderr pointing
at the migration runbook and the optional cleanup command. The notice is
gated by a marker file so subsequent invocations stay quiet.

The detection uses ``importlib.metadata.distribution`` which does NOT
import the package — that distinction is critical, because importing
``spec_kitty_runtime`` would re-create the dependency this mission
retires (FR-002 / C-001). ``importlib.metadata`` only inspects the
installed-distribution metadata; it never executes the package's code.

Failure modes are deliberately silent: if the marker file cannot be
written (read-only home, permissions, disk full), the operator still
gets the notice every invocation, which is non-fatal noise. The CLI
continues normally regardless.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from kernel.user_dirs import user_state_dir

__all__ = ["maybe_emit_runtime_pkg_notice"]


_PACKAGE_NAME = "spec-kitty-runtime"
_MARKER_FILENAME = ".spec-kitty-runtime-cutover-notice-shown"
_NOTICE_TEXT = (
    "spec-kitty: notice: the retired 'spec-kitty-runtime' PyPI package is "
    "still installed in this environment. As of mission "
    "shared-package-boundary-cutover-01KQ22DS the CLI no longer requires it; "
    "you can safely 'pip uninstall spec-kitty-runtime'. See "
    "docs/migrations/shared-package-boundary-cutover.md for the full "
    "migration runbook. (This notice is shown once per environment.)"
)


def _marker_path() -> Path:
    """Location of the one-time-notice marker file.

    ``$XDG_STATE_HOME/spec-kitty/`` when set, else ``~/.cache/spec-kitty/``,
    on every platform (:func:`kernel.user_dirs.user_state_dir`), so the marker
    survives across CLI invocations but never lands in the repo tree.
    """
    return user_state_dir() / "spec-kitty" / _MARKER_FILENAME


def _runtime_package_installed() -> bool:
    """Return True iff ``spec-kitty-runtime`` is installed.

    Uses :mod:`importlib.metadata` so the package is NEVER imported. If
    metadata lookup fails for any reason (corrupt installation, etc.),
    we err on the side of silence and return False.
    """
    try:
        from importlib import metadata
    except ImportError:  # pragma: no cover — Python 3.8+ has metadata in stdlib
        return False
    try:
        metadata.distribution(_PACKAGE_NAME)
    except metadata.PackageNotFoundError:
        return False
    except Exception:  # pragma: no cover — metadata corruption etc.
        return False
    return True


def _notice_already_shown(marker: Path) -> bool:
    """Return True iff the marker file says we already showed the notice."""
    try:
        return marker.exists()
    except OSError:  # pragma: no cover — broken filesystem path resolution
        # If we can't check, default to "already shown" so we don't spam.
        return True


def _record_notice_shown(marker: Path) -> None:
    """Best-effort marker write. Failure is non-fatal."""
    try:
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.touch(exist_ok=True)
    except OSError:  # pragma: no cover — broken filesystem
        # Silent: the operator gets the notice again next invocation.
        pass


def maybe_emit_runtime_pkg_notice() -> bool:
    """Emit the FR-020 one-time deprecation notice if applicable.

    Returns True if a notice was emitted, False otherwise. Callers
    should not depend on the return value for control flow; the notice
    is a side-effect on stderr. The return value is exposed for tests.

    Behavior:

    * If ``SPEC_KITTY_SUPPRESS_RUNTIME_NOTICE=1`` is set, never emit.
    * If ``spec-kitty-runtime`` is not installed (the post-cutover
      target state), never emit.
    * If the marker file says we already emitted in this environment,
      never emit again.
    * Otherwise, emit the notice on stderr and write the marker.
    """
    if os.environ.get("SPEC_KITTY_SUPPRESS_RUNTIME_NOTICE") == "1":
        return False
    if not _runtime_package_installed():
        return False
    marker = _marker_path()
    if _notice_already_shown(marker):
        return False
    print(_NOTICE_TEXT, file=sys.stderr, flush=True)
    _record_notice_shown(marker)
    return True
