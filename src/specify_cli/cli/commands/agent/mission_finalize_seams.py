"""Shared seams and constants for the ``finalize-tasks`` leaf modules (#5627).

Holds the module constants, the owned-envelope ContextVar and the
``mission``-routed patch seams that every ``mission_finalize_*`` phase module
uses. Moved verbatim from ``mission_finalize.py``.
"""

from __future__ import annotations

import contextvars
import logging
from pathlib import Path
from specify_cli.core.commit_guard import GuardCapability
from mission_runtime import OwnedCheckout
from specify_cli.ownership.models import OwnershipManifest
from specify_cli.ownership.validation import (
    ValidationResult,
)
from specify_cli.status import BootstrapResult, WPMetadata

# Pinned to the historical module name so log records (and caplog filters)
# keep the ``mission_finalize`` logger across the #5627 decomposition.


logger = logging.getLogger("specify_cli.cli.commands.agent.mission_finalize")


TASKS_MD_FILENAME = "tasks.md"


ISSUE_MATRIX_FILENAME = "issue-matrix.md"


META_JSON_FILENAME = "meta.json"


FINALIZE_TASKS_COMMAND_NAME = "spec-kitty agent mission finalize-tasks"


INVALID_WP_OWNED_FILES_KITTY_SPECS = "INVALID_WP_OWNED_FILES_KITTY_SPECS"


PROJECT_ROOT_NOT_FOUND = "Could not locate project root"


OWNERSHIP_CONTRADICTION_CODE_CHANGE_EMPTY_OWNED_FILES = "OWNERSHIP_CONTRADICTION_CODE_CHANGE_EMPTY_OWNED_FILES"


LANE_COMPUTATION_ABORTED_EMPTY_INPUTS = "LANE_COMPUTATION_ABORTED_EMPTY_INPUTS"


# SK3466-REV-001 / #2938: the ONLY meta.json fields finalize-tasks itself writes
# (via the explicit override or legacy PR-bound normalization). A pending
# meta.json delta confined to these fields —
# whether produced by THIS invocation's own persist call or dangling from an
# earlier crashed finalize-tasks run (SK3466-RR-001) — is finalize-tasks'
# business regardless of which run produced it. A delta touching any OTHER
# field (e.g. ``vcs``/``vcs_locked_at``, written by ``implement``'s
# ``_ensure_vcs_in_meta`` -> ``set_vcs_lock`` even under ``--no-auto-commit``)
# belongs to a different command and must not silently ride finalize-tasks'
# commit. See ``_meta_json_delta_is_finalize_attributable``.
FINALIZE_ATTRIBUTABLE_META_FIELDS = frozenset({"target_branch", "merge_target_branch"})


# FR-007/R-12 (WP13 T074): the additive ``stale_repository_root_copy`` envelope
# key for the CURRENT owned invocation, or ``None`` (non-owned / not yet
# resolved). Bound by ``finalize_tasks`` after the owned fact resolves and
# merged into EVERY payload ``_emit_json`` prints -- success, validate-only, the
# generic error envelope AND the many gate-specific ``typer.Exit`` refusals that
# emit their own JSON -- so no emitter has to remember it. An explicitly
# supplied key in a payload stays authoritative.
#
# Why a scoped ContextVar and not threading ``owned`` through the emitters:
# roughly 30 gate helpers (dependency graph, requirement mapping, ownership,
# lane compute, ...) emit their own refusal JSON and have no other reason to
# know about an owned checkout; adding an ``owned`` parameter to each would
# widen ~30 signatures and let one forgotten call site silently drop the key
# again (the FR-007 defect this replaced). The binding is invocation-scoped:
# ``finalize_tasks`` sets it under a ``token`` and ``reset``s it in a
# ``finally``, so it can never outlive the owned run that bound it.
_OWNED_ENVELOPE_EXTRAS: contextvars.ContextVar[dict[str, object] | None] = contextvars.ContextVar("finalize_owned_envelope_extras", default=None)


def _emit_json(payload: dict[str, object]) -> None:
    """Emit ``payload`` as JSON via the ``mission`` module's ``_emit_json``.

    Routing every finalize JSON emission through the ``mission`` module (rather
    than importing ``_emit_json`` directly) preserves the historical
    ``mission._emit_json`` patch seam exercised by callers that invoke
    ``mission.finalize_tasks`` directly.
    """
    from specify_cli.cli.commands.agent import mission as _mission

    extras = _OWNED_ENVELOPE_EXTRAS.get()
    if extras:
        payload = {**{key: value for key, value in extras.items() if key not in payload}, **payload}
    _mission._emit_json(payload)


def _read_wp_frontmatter(wp_file: Path) -> tuple[WPMetadata, str]:
    """Route ``read_wp_frontmatter`` through ``mission`` (patch seam)."""
    from specify_cli.cli.commands.agent import mission as _mission

    frontmatter: tuple[WPMetadata, str] = _mission.read_wp_frontmatter(wp_file)
    return frontmatter


def _resolve_planning_branch_via_mission(repo_root: Path, primary_dir: Path, *, target_branch_override: str | None) -> str:
    """Route ``_resolve_planning_branch`` through ``mission`` (patch seam)."""
    from specify_cli.cli.commands.agent import mission as _mission

    branch: str = _mission._resolve_planning_branch(repo_root, primary_dir, target_branch_override=target_branch_override)
    return branch


def _bootstrap_canonical_state_via_mission(
    planning_dir: Path,
    mission_slug: str,
    *,
    dry_run: bool,
    capability: GuardCapability | None = None,
    owned: OwnedCheckout | None = None,
) -> BootstrapResult:
    """Route ``bootstrap_canonical_state`` through ``mission`` (patch seam)."""
    result = _bootstrap_through_mission(planning_dir, mission_slug, dry_run=dry_run, capability=capability, owned=owned)
    if not dry_run:
        # The bootstrap appends status rows: record the files as they are now in this run's write ledger (plan A8).
        from specify_cli.cli.commands.agent.mission_finalize_commit import note_status_files_written

        note_status_files_written(planning_dir, owned.repository_root if owned is not None else None)
    return result


def _bootstrap_through_mission(
    planning_dir: Path,
    mission_slug: str,
    *,
    dry_run: bool,
    capability: GuardCapability | None,
    owned: OwnedCheckout | None,
) -> BootstrapResult:
    from specify_cli.cli.commands.agent import mission as _mission

    if owned is not None:
        # T073 (WP13): threads the ``owned=`` fact -- the same value object
        # every per-WP seed in the loop below reuses instead of re-running the
        # ownership claim (#3866).
        return _mission.bootstrap_canonical_state(
            planning_dir,
            mission_slug,
            dry_run=dry_run,
            capability=capability or GuardCapability.STANDARD,
            repo_root=owned.repository_root,
            owned=owned,
        )
    if capability is None:
        return _mission.bootstrap_canonical_state(planning_dir, mission_slug, dry_run=dry_run)
    return _mission.bootstrap_canonical_state(planning_dir, mission_slug, dry_run=dry_run, capability=capability)


def _validate_ownership_via_mission(wp_manifests: dict[str, OwnershipManifest], wp_dependencies: dict[str, list[str]]) -> ValidationResult:
    """Route ``validate_ownership`` through ``mission`` (patch seam)."""
    from specify_cli.cli.commands.agent import mission as _mission

    return _mission.validate_ownership(wp_manifests, wp_dependencies)
