"""Production-delegating test factories (FR-008 / E-06 / IC-07, issue #2074).

``make_mission()`` is a thin wrapper over
:func:`specify_cli.core.mission_creation.create_mission_core` -- the
documented programmatic mission-creation API (spec A-002) -- so tests get a
production-shaped ``meta.json`` from the single schema authority instead of
hand-rolling a meta dict per test module. Those hand-rolled fixtures (the
329-writer tail referenced in the mission spec) are NOT migrated here
(Directive 024); this factory is purely additive for new/updated tests that
want production-shaped fixtures without re-implementing meta assembly.

The parity invariant is asserted in ``test_make_mission_parity.py``: this
factory's ``meta.json`` output is byte-identical to a direct
``create_mission_core()`` call, after normalizing the auto-minted
``{mission_id, created_at}`` fields (and the ``mid8`` embedded in the
slug-derived fields), minus explicit overrides.

**Charter provisioning (WP04 fail-closed follow-up).** ``create_mission_core()``
now hard-requires at least one activated mission type
(``charter.activation.mission_type_profiles.existing_mission_types``) and raises
``ActiveCharterConfigError`` when a project's ``.kittify/config.yaml`` has no
``mission_type_activations`` key -- exactly the state of a bare ``tmp_path``
git-init test fixture that never ran ``spec-kitty init``/``upgrade``.
:func:`provision_test_charter` mirrors what those commands do (via the real,
production ``provision_default_mission_type_activations`` provisioner) so
test fixtures see the same activated-mission-type surface a real project
would. ``make_mission()`` calls it automatically; direct
``create_mission_core()`` callers must call it themselves (see
``provision_test_charter``'s docstring).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from mission_runtime import MissionTopology
from specify_cli.core.mission_creation import MissionCreationResult, create_mission_core
from specify_cli.provisioning.default_charter import (
    provision_default_mission_type_activations,
)

__all__ = ["make_mission", "provision_test_charter"]


def provision_test_charter(project_path: Path) -> None:
    """Seed ``project_path``'s ``.kittify/config.yaml`` with activated mission types.

    Thin wrapper over the real, production
    :func:`specify_cli.provisioning.default_charter.provision_default_mission_type_activations`
    provisioner -- NOT a second, test-only seeder. Idempotent and additive
    (a no-op if the key is already present), so it is safe to call
    unconditionally at the top of a test's git-repo setup.

    Every test that calls ``create_mission_core()`` directly (bypassing
    ``make_mission()``, which already provisions internally) or resolves a
    mission-type profile against a bare ``tmp_path`` project MUST call this
    first -- otherwise ``existing_mission_types()`` returns an empty list and
    the mission-create / mission-type-resolution boundary fails closed
    exactly as it does for a real, unprovisioned project.
    """
    provision_default_mission_type_activations(project_path)


def make_mission(
    repo_root: Path,
    mission_slug: str,
    *,
    topology: MissionTopology = MissionTopology.SINGLE_BRANCH,
    **overrides: Any,
) -> MissionCreationResult:
    """Create a production-shaped test mission by delegating to ``create_mission_core()``.

    This does not fork the production schema: every field in the returned
    ``meta.json`` comes from ``create_mission_core()`` itself. Only
    test-ergonomic defaults are applied here, and only when the caller has
    not already supplied them via ``overrides``.

    Parameters
    ----------
    repo_root:
        Root of an initialized git repository (e.g. a ``tmp_path`` with
        ``git init`` run against it). ``create_mission_core()`` requires a
        resolvable current branch.
    mission_slug:
        Bare kebab-case mission slug (e.g. ``"my-test-mission"``).
    topology:
        Defaults to :attr:`MissionTopology.SINGLE_BRANCH` so no coordination
        branch is minted -- test fixtures overwhelmingly do not want that
        side effect. Pass an explicit ``topology`` override to opt back in.
    **overrides:
        Any keyword accepted by ``create_mission_core()`` (``mission``,
        ``target_branch``, ``friendly_name``, ``purpose_tldr``,
        ``purpose_context``, ``force_recreate_coordination_branch``,
        ``allow_worktree_context``). ``allow_worktree_context`` defaults to
        ``True`` here (unless overridden) since tests routinely execute from
        inside a lane worktree checkout, where the interactive/CLI guard
        would otherwise reject an in-repo-shaped ``repo_root``.

    Returns
    -------
    MissionCreationResult
        The same structured result ``create_mission_core()`` returns.
    """
    provision_test_charter(repo_root)
    overrides.setdefault("allow_worktree_context", True)
    title = mission_slug.replace("-", " ").strip() or "test mission"
    overrides.setdefault("friendly_name", title.title())
    overrides.setdefault("purpose_tldr", f"Deliver {title} cleanly for the team.")
    overrides.setdefault(
        "purpose_context",
        f"This mission delivers {title} so product and engineering can move "
        "forward with a clear outcome and shared understanding.",
    )
    return create_mission_core(repo_root, mission_slug, topology=topology, **overrides)
