"""The offering-side SPDD probe subtracts deny (WP06: FR-016, research D-07, m3).

``is_spdd_reasons_active`` reads allow **and** deny from the source the kernel
resolver selects and applies ``allow and not deny``; the directive deny reuses
``_is_directive_038`` (both ``DIRECTIVE_038`` and the stem form match). It
applies no org required floor (the residual ADR ``2026-10-19-1`` records).

Ledger-seeded.
Positive control (F15): every deny case first shows the probe True on the same
fixture.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from charter.activation.activation_ledger import LEDGER_KEYS
from charter.offering.spdd_reasons import activation as spdd_activation
from charter.offering.spdd_reasons.activation import (
    DIRECTIVE_ID,
    PARADIGM_ID,
    TACTIC_FILL_ID,
    TACTIC_REVIEW_ID,
    is_spdd_reasons_active,
)
from tests._factories.activation_ledger import seed_activation_ledger

pytestmark = [pytest.mark.fast]

_DIRECTIVE_STEM = "038-structured-prompt-boundary"


def _project(tmp_path: Path, config: str = "") -> Path:
    (tmp_path / ".kittify").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".kittify" / "config.yaml").write_text(config, encoding="utf-8")
    return tmp_path


def _deny_every_selector(root: Path, directive_spelling: str) -> None:
    seed_activation_ledger(
        root,
        deactivated_paradigms=[PARADIGM_ID],
        deactivated_tactics=[TACTIC_FILL_ID, TACTIC_REVIEW_ID],
        deactivated_directives=[directive_spelling],
    )


def test_legacy_key_set_matches_the_activation_seam() -> None:
    """The offering's own key replica (C-002 forbids the import) stays equal to the seam's (WP03 review L2)."""
    assert frozenset(LEDGER_KEYS) == spdd_activation._LEGACY_ACTIVATION_KEYS


@pytest.mark.parametrize("directive_spelling", [DIRECTIVE_ID, _DIRECTIVE_STEM])
def test_deny_on_the_ledger_turns_the_probe_off(tmp_path: Path, directive_spelling: str) -> None:
    root = _project(tmp_path)
    seed_activation_ledger(root, mission_type_activations=["software-dev"])
    assert is_spdd_reasons_active(root) is True  # absent allow lists: "all"

    _deny_every_selector(root, directive_spelling)
    assert is_spdd_reasons_active(root) is False


def test_one_denied_selector_leaves_the_others_in_force(tmp_path: Path) -> None:
    root = _project(tmp_path)
    seed_activation_ledger(root, activated_paradigms=[PARADIGM_ID], activated_tactics=[], activated_directives=[])
    assert is_spdd_reasons_active(root) is True

    seed_activation_ledger(root, deactivated_paradigms=[PARADIGM_ID])
    assert is_spdd_reasons_active(root) is False


def test_a_denied_directive_subtracts_an_allowed_declared_id(tmp_path: Path) -> None:
    """A stem deny subtracts the declared-id allow entry (``_is_directive_038`` on both sides)."""
    root = _project(tmp_path)
    seed_activation_ledger(root, activated_paradigms=[], activated_tactics=[], activated_directives=[DIRECTIVE_ID])
    assert is_spdd_reasons_active(root) is True

    seed_activation_ledger(root, deactivated_directives=[_DIRECTIVE_STEM])
    assert is_spdd_reasons_active(root) is False


def test_unmigrated_project_reads_its_legacy_allow_keys_then_the_ledger(tmp_path: Path) -> None:
    root = _project(tmp_path, "activated_paradigms: []\nactivated_tactics: []\nactivated_directives:\n  - DIRECTIVE_001\n")

    # One mode: an unmigrated project reads its legacy allow keys, as on main (no raise).
    assert is_spdd_reasons_active(root) is False

    # Positive control: the same fixture once the keys live in the ledger.
    (root / ".kittify" / "config.yaml").write_text("", encoding="utf-8")
    seed_activation_ledger(root, activated_directives=["DIRECTIVE_001"])
    assert is_spdd_reasons_active(root) is True


def test_absent_config_yaml_keeps_the_early_false(tmp_path: Path) -> None:
    seed_activation_ledger(tmp_path, activated_paradigms=[PARADIGM_ID])
    (tmp_path / ".kittify" / "config.yaml").unlink(missing_ok=True)

    assert is_spdd_reasons_active(tmp_path) is False
