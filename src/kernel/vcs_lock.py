"""Unified VCS-lock comparator + named field-set — the single canonical authority.

Lives in ``kernel`` (the zero-dependency root) so both git plumbing
(``git/ref_advance.py``, C-003) and the application layer
(``implement_cores``) depend on one comparator instead of forking it.

Adopts the ``implement_cores._is_vcs_lock_only_meta_diff`` *sentinel* semantics
as canonical: an **absent** field is distinct from a **present-but-``None``**
field (C-005). This deliberately changes ``ref_advance``'s old ``.get()``-based
verdict on the present-but-null arm (US2 AC1 — WP02's concern, not a bug here).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

__all__ = [
    "VCS_LOCK_META_FIELDS",
    "is_vcs_lock_only_change",
]

#: The only VCS-lock field-set. No inline-literal duplicates elsewhere (NFR-002).
VCS_LOCK_META_FIELDS: frozenset[str] = frozenset({"vcs", "vcs_locked_at"})

#: Sentinel distinguishing an *absent* key from a *present-but-``None``* value.
#: Using ``.get()`` (which returns ``None`` for both) would erase that
#: distinction; the comparator MUST treat absent != present-but-null (C-005).
_MISSING: Any = object()


def is_vcs_lock_only_change(
    before: Mapping[str, Any] | None,
    after: Mapping[str, Any],
) -> bool:
    """Return ``True`` iff the only keys that differ are :data:`VCS_LOCK_META_FIELDS`.

    A key that is **absent** on one side and **present-but-``None``** on the
    other counts as a difference (C-005): they are distinct states, compared via
    a :data:`_MISSING` sentinel rather than ``.get()``.

    Args:
        before: The committed/prior mapping, or ``None`` when that side is
            absent entirely (e.g. no committed ``meta.json``).
        after: The current mapping.

    Returns:
        ``True`` when every differing key is a VCS-lock field (and at least the
        non-VCS-lock keys are identical); ``False`` when any non-VCS-lock key
        differs. Two identical mappings (no differing keys) return ``True`` —
        the empty set of differences is trivially a subset of the lock fields.
    """
    before_map: Mapping[str, Any] = before if before is not None else {}
    keys = before_map.keys() | after.keys()
    for key in keys:
        before_value = before_map.get(key, _MISSING)
        after_value = after.get(key, _MISSING)
        if before_value is _MISSING and after_value is _MISSING:
            continue
        if before_value is _MISSING or after_value is _MISSING:
            # Key present on exactly one side — a difference (absent != present,
            # even when the present value is None).
            if key not in VCS_LOCK_META_FIELDS:
                return False
            continue
        if before_value != after_value and key not in VCS_LOCK_META_FIELDS:
            return False
    return True
