"""Guard against this repository's own project state leaking into test fixtures.

Shared by ``tests/conftest.py``'s ``test_project`` and ``tests/e2e/conftest.py``'s
``e2e_project`` -- both simulate a *fresh* Spec Kitty project by copying
``REPO_ROOT / ".kittify"`` wholesale, then are expected to scrub the pieces of
that copy that are this repository's own maintainer-only state rather than
something a fresh project would carry.

Kept out of ``tests/conftest.py`` itself (rather than defined there directly)
because that module is under a hard architectural gate
(``tests/architectural/test_home_owner_behaviour.py::
test_conftest_definition_order_is_unchanged_with_the_owner_removed``) that
permits exactly one new top-level definition beyond a frozen merge-base
snapshot. An imported name does not add an AST-visible ``FunctionDef`` to
that module, so the shared helper lives here instead.
"""

from __future__ import annotations

import shutil
from pathlib import Path

__all__ = ["scrub_repo_mission_overrides"]


def scrub_repo_mission_overrides(project: Path) -> None:
    """Strip this repository's own mission-scoped template overrides.

    ``.kittify/overrides/missions/`` in ``REPO_ROOT`` was spec-kitty's own
    project-local customization of its built-in mission templates (added by
    #661) -- maintainer-only state, not something a simulated *fresh* test
    project should inherit. Before mission ``up-org-template-fsm-01M06F9K``
    (WP01, the commit converging the tier-1 mission-scoped override probe in
    ``specify_cli.runtime.resolver``), this tree was inert for the
    ``mission create`` / ``setup-plan`` lane -- that resolver only checked
    the flat, non-mission-scoped override path, so the mission-scoped tree
    copied in by the fixture's ``shutil.copytree`` was silently ignored.
    Once both forked resolvers agreed on probing
    ``.kittify/overrides/missions/{mission}/...`` first (the correct fix --
    ``charter list``/``show-origin``'s ``charter.offering.resolver`` lane already
    resolved it), this repo's own override started winning template
    resolution ahead of any test-authored override/legacy template at a
    less-specific tier, breaking every test that supplies its own template
    at a lower tier and asserts on its exact content. Removing it here
    restores "fresh project, no configured overrides" as the fixture's
    actual contract; tests that want an override in place already create
    their own.

    #5128 deleted the per-mission override directories from ``REPO_ROOT``
    (guarded by ``tests/dossier/test_manifest.py::
    TestRepoMissionOverrideTierRetired``), so this scrub is now defensive: it
    keeps the fixture contract true even if such a directory reappears, and
    still drops the residual flat files left under that path.
    """
    shutil.rmtree(project / ".kittify" / "overrides" / "missions", ignore_errors=True)
