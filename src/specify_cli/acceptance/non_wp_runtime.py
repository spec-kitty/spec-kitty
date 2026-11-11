"""Accept artifact-producing workflows through their existing frozen runtime.

The ordinary WP acceptance path is unchanged. This branch is only selected
when the recorded runtime has no WP-iteration step and no WP task files.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from runtime.next.runtime_bridge import read_runtime_acceptance_facts
from runtime.next.runtime_bridge_cores import MISSING_ARTIFACT_MESSAGE, evaluate_guards_strict
from runtime.next.runtime_bridge_io import gather_artifact_presence, presence_seam
from specify_cli.mission_metadata import resolve_mission_identity
from specify_cli.runtime.resolver import required_artifacts_for

if TYPE_CHECKING:
    from mission_runtime import OwnedCheckout

#: The one mission type whose acceptance is vouched for by its completed
#: runtime and declared artifacts instead of work packages.
_ARTIFACT_ONLY_MISSION_TYPE = "plan"


def is_artifact_only_acceptance(mission_type: str | None) -> bool:
    """Return whether ``mission_type`` may be accepted without work packages.

    Deliberately limited to the built-in ``plan`` family; every other type keeps
    the WP path with its runtime-independent gates. Generalising this to other
    artifact-producing mission types is tracked in #4983.
    """
    return mission_type == _ARTIFACT_ONLY_MISSION_TYPE


@dataclass(frozen=True)
class NonWpRuntimeFacts:
    """The part of an acceptance summary that a non-WP runtime supplies.

    ``collect_feature_summary`` composes these with the checks it shares with
    the WP path (clarification, clean tree, path conventions, fix order).
    """

    activity_issues: list[str]
    #: Artifact names (relative to the planning dir) the runtime declares blocking.
    required_artifacts: list[str]
    missing_artifacts: list[str]


def collect_non_wp_runtime_facts(
    *,
    repo_root: Path,
    feature_dir: Path,
    status_feature_dir: Path,
    wp_tasks_dir: Path,
    owned: OwnedCheckout | None,
) -> NonWpRuntimeFacts | None:
    """Return runtime facts for an artifact-only mission, or ``None`` for the WP path."""
    from . import AcceptanceError

    identity = resolve_mission_identity(feature_dir)
    if not is_artifact_only_acceptance(identity.mission_type):
        return None
    runtime_root = owned.owned_root if owned is not None else repo_root
    try:
        facts = read_runtime_acceptance_facts(runtime_root, feature_dir.name)
    except (OSError, ValueError, RuntimeError) as exc:
        raise AcceptanceError("Cannot read canonical mission runtime for acceptance; no state was changed") from exc
    if facts is None or facts.wp_driven:
        return None
    wp_homes = {feature_dir, status_feature_dir, wp_tasks_dir}
    if any(next((home / "tasks").glob("WP*.md"), None) is not None for home in wp_homes):
        return None
    if facts.mission_family != identity.mission_type:
        raise AcceptanceError("Mission type does not match its recorded runtime; acceptance refused")

    activity: list[str] = []
    if "review" not in facts.step_ids:
        activity.append("Plan runtime has no review action; acceptance refused")
    incomplete = sorted(set(facts.step_ids) - set(facts.completed_step_ids))
    if not facts.step_ids or incomplete or facts.issued_step_id or facts.blocked_reason or facts.pending_decision_ids:
        activity.append("Non-WP runtime is not complete; remaining steps: " + (", ".join(incomplete) or "pending runtime decision/result"))
    required: set[str] = set()
    missing: set[str] = set()
    missing_prefix = MISSING_ARTIFACT_MESSAGE.format(name="")
    # The presence check gets the Mission's placement seam (#7310 WP05, FR-010), so
    # classified artifacts resolve to their canonical home from the status directory.
    seam = presence_seam(repo_root, feature_dir.name, owned=owned)
    for step_id in facts.step_ids:
        required.update(required_artifacts_for(step_id, facts.mission_family, repo_root=runtime_root))
        snapshot = gather_artifact_presence(status_feature_dir, mission_family=facts.mission_family, step_id=step_id, repo_root=repo_root, seam=seam)
        for failure in evaluate_guards_strict(snapshot):
            if failure.startswith(missing_prefix):
                missing.add(failure[len(missing_prefix) :])
            else:
                activity.append(f"{step_id}: {failure}")
    if not required:
        activity.append("Non-WP runtime has no declared blocking artifacts; acceptance refused")
    return NonWpRuntimeFacts(activity_issues=activity, required_artifacts=sorted(required), missing_artifacts=sorted(missing))
