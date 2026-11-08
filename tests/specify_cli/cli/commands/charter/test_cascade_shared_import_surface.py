"""Advertised-surface lock for the shared cascade seams (#4599).

``_cascade_shared``'s module docstring names the seams a sibling module may
import. Before #4599 it advertised ``KIND_FILTERED_LABEL`` as one of them while
``__all__`` exported only the two functions, so the advertised surface and the
export list disagreed.

The label is the renderer's wording rather than a seam of its own (it is the
only consumer, and exporting a name no other ``src/`` module imports trips the
dead-symbol gate), so the docstring was narrowed. These tests pin the invariant
that remains: every seam the docstring advertises is exported.
"""

from __future__ import annotations

import re

from specify_cli.cli.commands.charter import _cascade_shared

#: Sphinx roles the module uses to advertise a name: ``:func:`x```, ``:data:`x```, …
_ADVERTISED_ROLE = re.compile(r":(?:func|data|class|attr):`([A-Za-z_][A-Za-z0-9_]*)`")


def test_every_advertised_seam_is_exported() -> None:
    """The docstring advertises only names ``__all__`` actually exports (#4599)."""
    advertised = set(_ADVERTISED_ROLE.findall(_cascade_shared.__doc__ or ""))
    assert advertised, "the module docstring must keep advertising its seams"
    unexported = sorted(advertised - set(_cascade_shared.__all__))
    assert unexported == []


def test_every_exported_name_resolves_on_the_module() -> None:
    """``__all__`` never names a missing attribute (a star import must not fail)."""
    missing = sorted(name for name in _cascade_shared.__all__ if not hasattr(_cascade_shared, name))
    assert missing == []


def test_kind_filtered_label_stays_the_renderers_wording() -> None:
    """The label is a format template the shared renderer keeps private (#4599)."""
    assert "KIND_FILTERED_LABEL" not in _cascade_shared.__all__
    assert "{kind_token}" in _cascade_shared.KIND_FILTERED_LABEL
    assert "{config_id}" in _cascade_shared.KIND_FILTERED_LABEL
