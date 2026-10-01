"""Seal the manual global-state census allowlist.

The census gate (``test_no_manual_global_state_mutation.py``) enforces the
allowlist's shape (valid kind/class, `reason:` present, count >= 1). This
module additionally freezes a per-class cap on the allowed *count* of each
row class, so the justified remainder can only shrink from here: a class's
total may never rise above its sealed cap, and the cap itself may never sit
looser than the live total (a shrink-only ratchet).

Current sealed caps, by class::

    process-bootstrap    6
    subprocess-entry    12
    leak-sentinel        2
    deferred-01M3EW3Z    4

This module reuses ``test_no_manual_global_state_mutation``'s own
``load_allowlist``/``AllowlistRow``/``Allowlist`` -- it does not parse the YAML
shards a second time, honoring that module's docstring claim to be the only
allowlist reader.

Central baselines-registry registration (``tests/architectural/
_baselines.yaml`` / ``test_ratchet_baselines.py``) is deferred to a later
change; the caps below live only in this module until that registration
lands.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Final

import pytest

from tests.architectural.test_no_manual_global_state_mutation import (
    ALLOWLIST_DIR,
    Allowlist,
    AllowlistRow,
    load_allowlist,
)

pytestmark = pytest.mark.architectural

#: Frozen at the post-sweep counts. Shrink-only: lower a
#: cap when a site is converted; never raise it.
SEALED_CLASS_CAPS: Final[Mapping[str, int]] = {
    "process-bootstrap": 5,
    "subprocess-entry": 12,
    "leak-sentinel": 2,
    "deferred-01M3EW3Z": 4,
}


# ---------------------------------------------------------------------------
# Pure verdict functions -- each returns a list of human-readable violation
# messages (empty == pass). The self-mutation tests further below exercise
# these directly against planted, in-memory rows; the sealed-invariant tests
# just below exercise them against the real, loaded allowlist.
# ---------------------------------------------------------------------------


def unknown_class_violations(rows: Iterable[AllowlistRow], caps: Mapping[str, int]) -> list[str]:
    """Verdict: any row whose class is not one of the sealed, capped classes."""
    return [
        f"{row.shard}/{row.file}:{row.qualname} ({row.kind}) has unknown class {row.row_class!r} -- not one of {sorted(caps)}"
        for row in rows
        if row.row_class not in caps
    ]


def class_totals(rows: Iterable[AllowlistRow]) -> dict[str, int]:
    """Sum of ``count`` per ``row_class`` across ``rows``."""
    totals: dict[str, int] = {}
    for row in rows:
        totals[row.row_class] = totals.get(row.row_class, 0) + row.count
    return totals


def cap_exceeded_violations(totals: Mapping[str, int], caps: Mapping[str, int]) -> list[str]:
    """Verdict: a class's actual total exceeds its sealed cap."""
    return [
        f"class {cls} has {count} sites > sealed cap {caps[cls]} -- convert the site, never raise the cap"
        for cls, count in sorted(totals.items())
        if cls in caps and count > caps[cls]
    ]


def cap_not_tight_violations(totals: Mapping[str, int], caps: Mapping[str, int]) -> list[str]:
    """Verdict (frozen-baseline shrink-only ratchet): a cap looser than the actual count.

    A converted site must lower the cap in the same change -- a cap that sits
    above the live total is a loose ratchet that would silently permit a
    regression back up to the old cap.
    """
    return [
        f"class {cls} sealed cap is {caps[cls]} but the actual count is {totals.get(cls, 0)} -- lower the cap in this change (frozen-baseline shrink-only ratchet)"
        for cls in sorted(caps)
        if totals.get(cls, 0) != caps[cls]
    ]


def missing_reason_violations(rows: Iterable[AllowlistRow]) -> list[str]:
    """Verdict: a row with no ``reason`` (every sealed class requires one)."""
    return [f"{row.shard}/{row.file}:{row.qualname} ({row.kind}) class {row.row_class!r} has no reason" for row in rows if not row.reason]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def allowlist() -> Allowlist:
    return load_allowlist(ALLOWLIST_DIR)


@pytest.fixture(scope="module")
def rows(allowlist: Allowlist) -> list[AllowlistRow]:
    return list(allowlist.rows.values())


# ---------------------------------------------------------------------------
# Sealed invariants over the real, loaded allowlist
# ---------------------------------------------------------------------------


def test_only_known_classes(rows: list[AllowlistRow]) -> None:
    violations = unknown_class_violations(rows, SEALED_CLASS_CAPS)
    assert violations == [], "unknown allowlist class(es):\n" + "\n".join(violations)


def test_class_caps_hold(rows: list[AllowlistRow]) -> None:
    violations = cap_exceeded_violations(class_totals(rows), SEALED_CLASS_CAPS)
    assert violations == [], "\n".join(violations)


def test_caps_are_tight(rows: list[AllowlistRow]) -> None:
    violations = cap_not_tight_violations(class_totals(rows), SEALED_CLASS_CAPS)
    assert violations == [], "\n".join(violations)


def test_every_justified_row_has_reason(rows: list[AllowlistRow]) -> None:
    violations = missing_reason_violations(rows)
    assert violations == [], "\n".join(violations)


# ---------------------------------------------------------------------------
# Self-mutation tests: prove each seal assertion bites on a planted
# violation. Assertions run against the verdict functions' return values
# directly, never against pytest's own failure machinery.
# ---------------------------------------------------------------------------


def _planted_row(
    row_class: str,
    count: int = 1,
    *,
    shard: str = "S-plant",
    file: str = "tests/plant.py",
    qualname: str = "Plant.test_it",
    kind: str = "cwd",
    reason: str | None = "planted for a self-mutation test",
) -> AllowlistRow:
    return AllowlistRow(shard=shard, file=file, qualname=qualname, kind=kind, count=count, row_class=row_class, reason=reason)


def test_real_allowlist_has_zero_seal_violations(rows: list[AllowlistRow]) -> None:
    """Negative control: the unmodified real allowlist trips none of the seal checks."""
    totals = class_totals(rows)
    assert unknown_class_violations(rows, SEALED_CLASS_CAPS) == []
    assert cap_exceeded_violations(totals, SEALED_CLASS_CAPS) == []
    assert cap_not_tight_violations(totals, SEALED_CLASS_CAPS) == []
    assert missing_reason_violations(rows) == []


def test_planted_unknown_class_is_detected(rows: list[AllowlistRow]) -> None:
    planted = [*rows, _planted_row("mystery-class")]
    assert unknown_class_violations(planted, SEALED_CLASS_CAPS) != []


def test_planted_extra_subprocess_entry_site_is_detected(rows: list[AllowlistRow]) -> None:
    planted = [*rows, _planted_row("subprocess-entry")]
    assert cap_exceeded_violations(class_totals(planted), SEALED_CLASS_CAPS) != []


def test_converted_site_without_lowering_cap_is_detected(rows: list[AllowlistRow]) -> None:
    """A row removed (converted) without lowering the frozen cap fails `caps_are_tight`."""
    shrunk = [row for row in rows if row.row_class != "leak-sentinel"]
    assert cap_not_tight_violations(class_totals(shrunk), SEALED_CLASS_CAPS) != []


def test_missing_reason_is_detected(rows: list[AllowlistRow]) -> None:
    planted = [*rows, _planted_row("process-bootstrap", reason=None)]
    assert missing_reason_violations(planted) != []
