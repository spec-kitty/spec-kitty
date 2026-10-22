"""Always-on freshness gate: the retired ``--feature`` alias never resurfaces.

Lifted from ``tests/specify_cli/cli/test_no_visible_feature_alias.py``, whose
directory (``tests/specify_cli/cli``) is recorded ``out_of_matrix`` in
``.github/ci-module-registry.yml`` — no per-PR lane selects it (#4374, #4479).

Terminology Canon prohibits ``feature*`` aliases for the Mission domain
object. FR-006/FR-009 (mission ``feature-alias-removal-01KW0N87``) removed
every ``--feature`` CLI flag; this gate pins that it stays removed: zero
``--feature`` options anywhere in the live Typer/Click command tree, and
(defensively) any that ever reappear must at least be hidden from rendered
help.
"""

from __future__ import annotations

import os

import pytest

# The tests live once, in the shared home this gate and its source import
# (#5015); importing them is what makes pytest collect them in this module.
from tests.architectural._lifted_cli_no_visible_feature_alias import test_every_feature_flag_is_hidden as test_every_feature_flag_is_hidden
from tests.architectural._lifted_cli_no_visible_feature_alias import test_zero_feature_flags_exist_cli_wide as test_zero_feature_flags_exist_cli_wide

pytestmark = [pytest.mark.architectural]


@pytest.fixture(autouse=True)
def _pin_no_upgrade_check(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep the upgrade-check opt-out set for every test (was a module-level ``setdefault``)."""
    monkeypatch.setenv("SPEC_KITTY_NO_UPGRADE_CHECK", os.environ.get("SPEC_KITTY_NO_UPGRADE_CHECK", "1"))
