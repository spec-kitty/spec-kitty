"""T033 (FR-013, INV-003) — tension-vocabulary cascade exclusion, behaviorally.

T032 (``tests/charter/test_cascade.py``) proves the exclusion at the
data-structure level: ``in_tension_with``/``reconciles_tension``/``rejects``
are never members of ``charter.activation.cascade.REFERENCE_RELATIONS``. This module
proves the exclusion matters at the CLI/cascade level (INV-003): activating
one side of a real, built-in tension pair never auto-activates the other
side via ``--cascade all``, and activating the built-in reconciliation
directive never auto-activates the three artefacts it reconciles.

Uses the same CLI-invocation entry point as
``tests/specify_cli/cli/commands/charter/test_charter_activate_commands_cascade_*.py``
and ``tests/specify_cli/test_charter_activate_cli.py`` (``charter activate
--repo-root <project> --cascade all <kind> <id>``, reading the resulting
``activated_<kind>s`` lists back out of ``.kittify/config.yaml``), for
consistency with the existing cascade-activation test suite.

Real built-in fixtures used (authored by WP02, mission
``doctrine-tension-edges-01KY1WPC``):

* ``directive:DIRECTIVE_024`` (config-stem ``024-locality-of-change``) is
  ``in_tension_with`` ``directive:DIRECTIVE_025`` (``025-boy-scout-rule``).
* ``directive:RECONCILE_CHANGE_SCOPE_TENSIONS`` (config-stem
  ``reconcile-change-scope-tensions``) carries ``reconciles_tension`` edges to
  ``DIRECTIVE_024``, ``DIRECTIVE_025``, and
  ``tactic:change-apply-smallest-viable-diff``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml
from click.testing import Result
from typer.testing import CliRunner

from specify_cli.cli.commands.charter import charter_app

runner = CliRunner()

pytestmark = [pytest.mark.integration]


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


@pytest.fixture()
def project_root(tmp_path: Path) -> Path:
    """A project with an explicit (empty) directive/tactic activation state.

    A truly *empty* ``config.yaml`` triggers ``ActiveCharterManager``'s
    no-explicit-activation-set bootstrap: the first activation of a kind with
    no config entry seeds it from the built-in default pack (today: 19
    directives, INCLUDING ``025-boy-scout-rule``) as a side effect unrelated
    to cascade. That default-pack seed would silently satisfy (mask) the very
    assertions this module exists to make, so the fixture pre-declares empty
    ``activated_directives``/``activated_tactics`` lists to opt out of the
    bootstrap and isolate cascade behavior as the only source of activation.
    """
    kittify = tmp_path / ".kittify"
    kittify.mkdir()
    # ``mission_type_activations`` is unrelated to the directive/tactic
    # cascade-exclusion behavior this module pins, but WP04 (C-A1) made it a
    # hard construction precondition for ``PackContext.from_config`` -- a
    # genuinely absent key now raises rather than defaulting. Provision it so
    # the ``charter activate`` CLI invocation below can construct at all.
    (kittify / "config.yaml").write_text(
        "mission_type_activations:\n  - software-dev\n"
        "activated_directives: []\nactivated_tactics: []\n",
        encoding="utf-8",
    )
    return tmp_path


def _config(project_root: Path) -> dict[str, Any]:
    raw = (project_root / ".kittify" / "config.yaml").read_text(encoding="utf-8")
    return yaml.safe_load(raw) or {}


def _activate(project_root: Path, *args: str) -> Result:
    return runner.invoke(
        charter_app,
        ["activate", "--repo-root", str(project_root), *args],
        catch_exceptions=False,
    )


# ---------------------------------------------------------------------------
# INV-003 — activating one side of a tension never auto-activates the other
# ---------------------------------------------------------------------------


class TestTensionPairNotAutoActivated:
    def test_activating_locality_of_change_does_not_cascade_to_boy_scout_rule(
        self, project_root: Path
    ) -> None:
        result = _activate(
            project_root,
            "--cascade",
            "all",
            "directive",
            "024-locality-of-change",
        )
        assert result.exit_code == 0, result.output

        data = _config(project_root)
        activated_directives = data.get("activated_directives") or []

        # The target itself is activated ...
        assert "024-locality-of-change" in activated_directives
        # ... but its in_tension_with counterpart is NOT auto-activated by
        # cascade -- in_tension_with is excluded from REFERENCE_RELATIONS by
        # omission (T032), so the tension pair never triggers a cascade edge.
        assert "025-boy-scout-rule" not in activated_directives


# ---------------------------------------------------------------------------
# INV-003 — activating a reconciler never auto-activates what it reconciles
# ---------------------------------------------------------------------------


class TestReconcilerNotAutoActivatingReconciledPair:
    def test_activating_reconciler_does_not_cascade_to_reconciled_artefacts(
        self, project_root: Path
    ) -> None:
        result = _activate(
            project_root,
            "--cascade",
            "all",
            "directive",
            "reconcile-change-scope-tensions",
        )
        assert result.exit_code == 0, result.output

        data = _config(project_root)
        activated_directives = data.get("activated_directives") or []
        activated_tactics = data.get("activated_tactics") or []

        # The reconciler itself is activated ...
        assert "reconcile-change-scope-tensions" in activated_directives
        # ... but none of the three artefacts it reconciles are auto-activated
        # -- reconciles_tension is excluded from REFERENCE_RELATIONS by
        # omission (T032), so cascade never follows a reconciler's edges to
        # the pair it resolves.
        assert "024-locality-of-change" not in activated_directives
        assert "025-boy-scout-rule" not in activated_directives
        assert "change-apply-smallest-viable-diff" not in activated_tactics
