"""Best-effort preparation of the global startup assets (#6473).

The CLI root callback prepares three owners in the home folder before every
command: the runtime assets (``bootstrap.ensure_runtime``), the agent skills
(``agent_skills.ensure_global_agent_skills``) and the agent commands
(``agent_commands.ensure_global_agent_commands``). The requested command does
not need them, so a home folder this process may not write (a read-only mount,
a sandbox that only allows writes to the workspace) must not stop it: the
failure becomes one warning and the command runs.

Only that class degrades. Every other ``StartupAssetError`` (a torn read,
source drift, a malformed inventory) and every other ``OSError`` stays fatal.
Commands that do need the assets (``init``, ``agent config add``, ``upgrade``)
call the owners directly and still fail with the named ``StartupAssetError``.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence

from specify_cli.runtime.asset_preparation import UNWRITABLE_HOME_CODE, UNWRITABLE_HOME_HINT, StartupAssetError, is_unwritable_home_error

__all__ = ["prepare_startup_assets"]

logger = logging.getLogger(__name__)


def prepare_startup_assets(owners: Sequence[tuple[str, Callable[[], None]]]) -> None:
    """Run each ``(label, owner)``; warn once about every owner the home folder refused."""
    refused: list[tuple[str, str]] = []
    for label, owner in owners:
        try:
            owner()
        except StartupAssetError as exc:
            if exc.code != UNWRITABLE_HOME_CODE:
                raise
            refused.append((label, str(exc)))  # the error already carries the hint
        except OSError as exc:
            if not is_unwritable_home_error(exc):
                raise
            refused.append((label, f"{exc}; {UNWRITABLE_HOME_HINT}"))
    if refused:
        logger.warning(
            (
                "spec-kitty could not update its %s; the command continues, but the runtime mission templates "
                "and the global agent commands and skills may be missing or out of date (%s)."
            ),
            _join_labels([label for label, _ in refused]),
            refused[0][1],
        )


def _join_labels(labels: list[str]) -> str:
    return labels[0] if len(labels) == 1 else ", ".join(labels[:-1]) + " and " + labels[-1]
