"""Mission-creation errors, the result type and the bootstrap commit-skip set.

Moved verbatim from ``mission_creation.py`` (#5634). ``mission_creation`` re-exports
every name defined here. A call to a name tests patch on ``mission_creation``, or to a
function another ``mission_creation*`` module owns, goes through a lazy in-function
``from specify_cli.core import mission_creation as _mc`` import (never at module scope).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from specify_cli.core.owned_mission import OwnedCreateRoot
from specify_cli.git.commit_helpers import (
    ProtectedBranchRefused,
    SafeCommitDestinationNotFound,
    SafeCommitHeadMismatch,
)


_BOOTSTRAP_META_COMMIT_SKIPS = (
    ProtectedBranchRefused,
    SafeCommitDestinationNotFound,
    SafeCommitHeadMismatch,
)


class MissionCreationError(RuntimeError):
    """Raised when mission creation fails.

    Carries an optional structured ``error_code`` (``None`` on the base class:
    a generic, unclassified creation failure) so JSON/scripted callers can
    consume a typed failure reason instead of pattern-matching the message
    prose (#3861).
    """

    # Report the façade as home, as before #5634 (tracebacks, repr, pickling).
    __module__ = "specify_cli.core.mission_creation"

    error_code: str | None = None


class MissionAlreadyExistsError(MissionCreationError):
    """A live same-key prior mission already exists (#4033 / #3861).

    The typed already-exists-vs-failed signal on the mission-creation
    surface: raised by the idempotency guard (a live prior mission shares
    the base slug and mission type) and by the scaffold commit's genuine
    empty-changeset refusal (byte-identical scaffold already committed --
    the same duplicate-mission signature). ``error_code`` is the stable
    identifier consumed by the orchestrator-api ``specify`` verb.
    """

    # Report the façade as home, as before #5634 (tracebacks, repr, pickling).
    __module__ = "specify_cli.core.mission_creation"

    error_code = "MISSION_ALREADY_EXISTS"


@dataclass(slots=True)
class MissionCreationResult:
    """Structured result from ``create_mission_core()``."""

    feature_dir: Path
    mission_slug: str
    mission_number: int | None  # None for pre-merge missions (FR-044)
    meta: dict[str, Any]
    target_branch: str
    current_branch: str
    created_files: list[Path] = field(default_factory=list)
    uncommitted_files: list[Path] = field(default_factory=list)
    origin_binding_attempted: bool = False
    origin_binding_succeeded: bool = False
    origin_binding_error: str | None = None
    # Coordination-branch outcome (WP03 / issue #1348).  ``coordination_branch``
    # is the canonical per-mission ref ``kitty/mission-<slug>-<mid8>`` parented
    # off ``target_branch``; ``coordination_branch_created`` distinguishes a
    # freshly-minted branch from an idempotent reuse on re-run.
    coordination_branch: str | None = None
    coordination_branch_created: bool = False
    # Public result field keeps origin/main's name (``owned_checkout``) so every
    # consumer of the result shape reads one attribute; it now carries the
    # validated owned-create fact rather than a bare path (G5).
    owned_checkout: OwnedCreateRoot | None = None
    canonical_repo_root: Path | None = None


# Report the façade as home, as before #5634 (tracebacks, repr, pickling). Set
# after the class body: ``@dataclass`` resolves string annotations through
# ``sys.modules[cls.__module__]``, and the façade is not registered yet when
# this module is imported on its own.
MissionCreationResult.__module__ = "specify_cli.core.mission_creation"


class MissionBranchExistsError(MissionCreationError):
    """Raised when the deterministically-composed mission branch already exists.

    #5100 FR-007 (WP08): a protected-target ``single_branch`` mission mints
    ``kitty/mission-<slug>-<mid8>`` and refuses outright rather than reusing
    or recreating a same-named branch -- an existing branch under that exact
    name could hold unrelated content (a stale branch from a prior, deleted
    mission whose mid8 happened to collide, or an operator's own local
    branch), and silently checking it out would corrupt the mission's history.
    """

    # Report the façade as home, as before #5634 (tracebacks, repr, pickling).
    __module__ = "specify_cli.core.mission_creation"

    error_code: str = "MISSION_BRANCH_EXISTS"
