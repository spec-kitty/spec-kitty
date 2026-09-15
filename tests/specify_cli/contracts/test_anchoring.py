"""Regression tests for the narrowed composite-key drift contract (#3369).

``composite_key``'s **values** are content-derived, but its **lookup** is
line-number-indexed — ``tokens.get(lineno, "")`` reads whatever line
``lineno`` names in the tree it is given. These tests pin the **behavior**
``anchoring.py``'s narrowed docstring describes, so a docstring edit that
re-widens the claim contradicts this executable evidence:

* an insertion **below** the guarded site leaves a pinned-``lineno`` key
  unchanged (neither lookup moves);
* an insertion **above** the site changes a pinned-``lineno`` key — a blank or
  comment line yields the empty token line, and an insertion above the
  enclosing function resolves the pinned line to an outer scope (the #3351
  failure mode that forced the frozen-anchor workaround);
* a **re-derived** ``lineno`` against the drifted tree (the ratchet-scan case,
  where the scan follows the content) reproduces the original key.
"""

from __future__ import annotations

import pytest

from specify_cli.contracts.anchoring import composite_key

pytestmark = [pytest.mark.fast]


#: A minimal two-function source. The guarded site is line 3 (``return guarded``).
_BASE_SOURCE = """\
def outer() -> str:
    guarded = "alpha"
    return guarded


def other() -> int:
    return 1
"""

#: 1-based lineno of the guarded ``return guarded`` line in ``_BASE_SOURCE``.
_SITE = 3


def test_insertion_below_site_leaves_pinned_key_unchanged() -> None:
    base_key = composite_key(_BASE_SOURCE, _SITE)
    drifted = _BASE_SOURCE.replace(
        "    return guarded\n",
        "    return guarded\n    # trailing note\n",
    )
    assert composite_key(drifted, _SITE) == base_key


def test_blank_insertion_above_site_changes_pinned_key() -> None:
    base_key = composite_key(_BASE_SOURCE, _SITE)
    drifted = _BASE_SOURCE.replace('    guarded = "alpha"\n', '    guarded = "alpha"\n\n')
    # The pinned lineno now reads the inserted blank line: token line ''.
    assert composite_key(drifted, _SITE) == ("outer", "")
    assert composite_key(drifted, _SITE) != base_key


def test_comment_insertion_above_site_changes_pinned_key() -> None:
    drifted = _BASE_SOURCE.replace(
        '    guarded = "alpha"\n',
        '    guarded = "alpha"\n    # inserted note\n',
    )
    # A comment-only line has no code tokens: token line ''.
    assert composite_key(drifted, _SITE) == ("outer", "")


def test_insertion_above_function_resolves_pinned_line_outward() -> None:
    # Pinned line 1 used to be ``def outer``'s header (inside ``outer``).
    assert composite_key(_BASE_SOURCE, 1) == ("outer", "def outer ( ) -> str :")
    drifted = "# module note\n" + _BASE_SOURCE
    # After one line is inserted above the function, the pinned line 1 is the
    # comment — outside the shifted span — so the qualname resolves outward.
    assert composite_key(drifted, 1) == ("<module>", "")


def test_rederived_lineno_on_drifted_tree_reproduces_key() -> None:
    base_key = composite_key(_BASE_SOURCE, _SITE)
    drifted = _BASE_SOURCE.replace('    guarded = "alpha"\n', '    guarded = "alpha"\n\n')
    # The ratchet-scan case: the site moved to _SITE + 1, and a lineno
    # re-derived against this tree follows it — same key.
    assert composite_key(drifted, _SITE + 1) == base_key
