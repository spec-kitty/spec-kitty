"""Mission directory scaffold, the tasks README and create-time governance.

Moved from ``mission_creation.py`` (#5634); reshaped by the decision-core and seam
cleanups. ``mission_creation`` re-exports every name defined here. A call to a name
tests patch on ``mission_creation``, or to a function another ``mission_creation*``
module owns, goes through a lazy in-function
``from specify_cli.core import mission_creation as _mc`` import (never at module scope).
"""

from __future__ import annotations

import contextlib
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from specify_cli.core.constants import KITTY_SPECS_DIR
from mission_runtime import (
    CommitTarget,
    MissionTopology,
)
from specify_cli.core.commit_guard import GuardCapability
from specify_cli.git import preflight_commit
from specify_cli.core.mission_creation_decisions import (
    is_coordination_routed,
)
from specify_cli.core.owned_mission import OwnedCreateMission, OwnedCreateRoot
from specify_cli.core.mission_creation_errors import _BOOTSTRAP_META_COMMIT_SKIPS
from specify_cli.core.mission_creation_protected_mint import _ProtectionProbe


TASKS_README_TEMPLATE = """\
# Tasks Directory

This directory contains work package (WP) prompt files.

## Directory Structure (v0.9.0+)

```
tasks/
\u251c\u2500\u2500 WP01-setup-infrastructure.md
\u251c\u2500\u2500 WP02-user-authentication.md
\u251c\u2500\u2500 WP03-api-endpoints.md
\u2514\u2500\u2500 README.md
```

All WP files are stored flat in `tasks/`. Status is tracked in `status.events.jsonl`, not in WP frontmatter.

## Work Package File Format

Each WP file **MUST** use YAML frontmatter:

```yaml
---
work_package_id: "WP01"
title: "Work Package Title"
dependencies: []
planning_base_branch: "{planning_branch}"
merge_target_branch: "{planning_branch}"
branch_strategy: "Planning artifacts were generated on {planning_branch}; completed changes must merge back into {planning_branch}."
subtasks:
  - "T001"
  - "T002"
phase: "Phase 1 - Setup"
assignee: ""
agent: ""
shell_pid: ""
history:
  - timestamp: "2025-01-01T00:00:00Z"
    agent: "system"
    action: "Prompt generated via /spec-kitty.tasks"
---

# Work Package Prompt: WP01 \u2013 Work Package Title

[Content follows...]
```

## Status Tracking

Status is tracked via the canonical event log (`status.events.jsonl`), not in WP frontmatter.
Use `spec-kitty agent tasks move-task` to change WP status:

```bash
spec-kitty agent tasks move-task <WPID> --to <lane>
```

Example:
```bash
spec-kitty agent tasks move-task WP01 --to doing
```

## File Naming

- Format: `WP01-kebab-case-slug.md`
- Examples: `WP01-setup-infrastructure.md`, `WP02-user-auth.md`
"""


def render_tasks_readme_content(planning_branch: str) -> str:
    """Render tasks/README.md with branch-aware example frontmatter."""
    return TASKS_README_TEMPLATE.format(planning_branch=planning_branch)


@dataclass(frozen=True, slots=True)
class _Governance:
    """Resolved mission-type context + spec template for one create call (section 4, T051)."""

    mission_type_context: Any
    spec_template: Any


def _resolve_create_governance(governance_root: Path, mission: str | None) -> _Governance:
    """Resolve the activated mission's spec template before any mission state exists.

    Section 4 of the pre-decomposition body (T051; FR-016 governance-root
    argument re-expressed by T053, #5009 1f42f76ea). A configuration failure
    must not leave a directory, metadata, or lifecycle events that look like
    a successful creation, so this runs before any create-side-effect helper.

    ``governance_root`` is the SINGLE root every read below uses: the
    validated owned checkout when the create is owned, the repository root
    checkout otherwise (FR-016) -- the validated write checkout owns charter
    and template configuration, and its activation may intentionally differ
    from the repository root checkout's.

    Fail-closed at the mission-create / mission-type-use boundary (WP04
    re-architecture): ``PackContext`` construction is now total (an absent
    or empty ``mission_type_activations`` key reads as ``frozenset()``
    without raising), so the actionable "provision your charter" error fires
    HERE, at the narrowest funnel every mission-create path passes through.
    """
    from charter.activation.mission_type_profiles import (
        existing_mission_types,
        resolve_mission_type_context,
    )
    from charter.activation.pack_context import CharterPackConfigError
    from specify_cli.runtime.resolver import resolve_configured_template

    if not existing_mission_types(governance_root):
        raise CharterPackConfigError(
            "This project has no activated mission types, so a mission cannot "
            "be created. A mission requires at least one activated mission "
            "type. Provision the project's charter: run `spec-kitty init` "
            "(new project) or `spec-kitty upgrade` (existing project), or add a "
            "non-empty `mission_type_activations` list to .kittify/config.yaml "
            "(or the charter.yaml it points to)."
        )

    selected_mission_type = mission or "software-dev"
    mission_type_context = resolve_mission_type_context(
        governance_root,
        mission_type=selected_mission_type,
    )
    spec_template = resolve_configured_template(
        "spec",
        governance_root,
        mission_type_context,
    )
    return _Governance(mission_type_context=mission_type_context, spec_template=spec_template)


@dataclass(frozen=True, slots=True)
class _Scaffold:
    """Paths written by the directory-creation + spec-template phase (sections 4/5, T051)."""

    feature_dir: Path
    scaffold_paths: tuple[Path, ...]
    tasks_readme: Path
    spec_file: Path
    #: The owned create root bound to ``feature_dir`` (``None`` for an unowned
    #: create): every create commit folds the mission-scoped protection hatch
    #: through this fact, never a re-derived repository root.
    owned_mission: OwnedCreateMission | None = None


def _scaffold_mission_dir(
    *,
    write_root: Path,
    resolved_root: Path,
    mission_slug_formatted: str,
    planning_branch: str,
    create_time_target: CommitTarget,
    spec_template: Any,
    owned: OwnedCreateRoot | None = None,
    topology: MissionTopology,
    commit_to_target: bool,
    protection: _ProtectionProbe | None = None,
) -> _Scaffold:
    """Create the mission directory tree and the (uncommitted) spec.md scaffold.

    Sections 4 and 5 of the pre-decomposition body (T051): human-slug + mid8
    directory naming (FR-032/FR-044), the preflight commit-authority check
    (same authority as ``safe_commit``, so a bootstrap refusal is disclosed
    before any write), and the spec.md scaffold copy. ``spec.md`` is
    intentionally NOT committed here (#846): the agent commits it from
    ``/spec-kitty.specify`` once it holds substantive content.
    """
    from specify_cli.core import mission_creation as _mc

    feature_dir = write_root / KITTY_SPECS_DIR / mission_slug_formatted
    _mc._refuse_protected_recreate(
        write_root,
        feature_dir,
        topology=topology,
        commit_to_target=commit_to_target,
        planning_branch=planning_branch,
        protection=protection,
    )
    owned_mission = owned.bind_mission(feature_dir) if owned is not None else None
    # D6 / T031: for a coordination-routed topology, ``status.events.jsonl``
    # (a COORD-partition kind) is never scaffolded on the target branch at
    # all -- the coordination surface carries it from birth (see
    # ``_materialize_and_commit_coord_create_events``). ``lanes`` /
    # ``single_branch`` keep today's root-checkout scaffolding byte-identical
    # (C-008).
    #
    # ``owned is None`` (review cycle 2, B5' ruling reversed): an OWNED
    # coordination-topology create is a supported, ratcheted path (FR-022,
    # ``TestFr022CoordinationTwin`` -- an owned sibling-checkout
    # ``create --topology lanes_with_coord`` followed by ``next`` must be a
    # non-error decision), NOT merely an operator override to refuse. An
    # ``OwnedCreateMission`` does not satisfy the ``mission_runtime.
    # OwnedCheckout`` contract ``placement_seam``/the coordination
    # write-location accessor require, so ``_seed_coord_surface_for_create``
    # already never seeds the coordination surface for an owned create
    # (``owned is not None`` short-circuits it to ``status_dir=None``) --
    # its ``MissionCreated``/``SpecifyStarted`` events land on
    # ``feature_dir`` in the owned checkout instead (``_emit_create_events``'s
    # own ``status_dir`` default). The scaffold step must therefore ALSO
    # treat an owned create as non-coordination-routed, so
    # ``status.events.jsonl`` is scaffolded AND included in the owned
    # checkout's own scaffold commit exactly as at base (``e7b085d26c``) --
    # otherwise it is written by the event emitter but never committed,
    # leaving the owned checkout with an uncommitted/untracked log. This is
    # a known, named residual (INV-COORD-HOME): an owned coordination
    # create's status log lives in the owned PRIMARY dir, never the
    # coordination surface -- follow-up tracked separately, not fixed here.
    from specify_cli.missions._create import topology_mints_coordination_branch

    coordination_routed = is_coordination_routed(mints_coordination=topology_mints_coordination_branch(topology), owned=owned is not None)
    scaffold_paths = (
        (feature_dir / "meta.json",)
        + (() if coordination_routed else (feature_dir / "status.events.jsonl",))
        + (feature_dir / "tasks" / "README.md", feature_dir / "tasks" / ".gitkeep")
    )
    # Validate before scaffold writes using the same authority as safe_commit.
    # Main permits these bootstrap refusals and discloses the uncommitted
    # scaffold; preserve that contract while rejecting other invalid targets.
    # The actual commit repeats validation, so this grants no stale authority.
    with contextlib.suppress(*_BOOTSTRAP_META_COMMIT_SKIPS):
        preflight_commit(
            repo_root=resolved_root,
            worktree_root=write_root,
            target=create_time_target,
            message=f"Add scaffold for mission {mission_slug_formatted}",
            paths=scaffold_paths,
            capability=GuardCapability.STANDARD,
            # Owned create: the mission-scoped fold reads the new mission's own
            # (not-yet-written) meta through the validated create fact, never
            # the repository root's copy (owned-checkout-lifecycle-authority).
            owned=owned_mission,
        )
    feature_dir.mkdir(parents=True, exist_ok=True)

    (feature_dir / "checklists").mkdir(exist_ok=True)
    (feature_dir / "research").mkdir(exist_ok=True)
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(exist_ok=True)

    (tasks_dir / ".gitkeep").touch()

    # Initialize empty event log so the feature has canonical status from
    # birth -- ONLY for a non-coordination-routed create (``is_coordination_
    # routed`` already folds in ``owned is None`` above). An unowned
    # coordination-routed Mission's status log is seeded straight into the
    # coordination Mission dir instead (D6); touching one here would
    # resurrect #5440 by giving the target-branch scaffold commit a (now
    # stale, empty) copy to carry. An OWNED coordination-routed create keeps
    # today's root-checkout-shaped scaffolding (INV-COORD-HOME residual).
    if not coordination_routed:
        (feature_dir / "status.events.jsonl").touch(exist_ok=True)

    tasks_readme = tasks_dir / "README.md"
    tasks_readme.write_text(
        render_tasks_readme_content(planning_branch),
        encoding="utf-8",
    )

    spec_file = feature_dir / "spec.md"
    if not spec_file.exists():
        shutil.copy2(spec_template.path, spec_file)

    return _Scaffold(
        feature_dir=feature_dir,
        scaffold_paths=scaffold_paths,
        tasks_readme=tasks_readme,
        spec_file=spec_file,
        owned_mission=owned_mission,
    )
