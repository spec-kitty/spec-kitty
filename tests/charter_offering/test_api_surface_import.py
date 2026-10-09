"""Coverage + smoke lock for the ``charter.offering.api`` public wheel surface.

``doctrine/api.py`` is the curated surface the future ``spec-kitty-doctrine``
wheel will export. No ``tests/charter_offering`` test and no doctrine module imports it
directly, so under ``--cov=doctrine`` (the ``fast-tests-doctrine`` shard, whose
report feeds the critical-path ``diff-coverage`` aggregate) its only coverage
came *incidentally* — via a single unrelated test importing ``charter.activation.catalog``
→ ``charter.drg`` → ``from charter.offering.api import ArtifactKind``. Break that one
import and ``api.py`` silently drops to 0% on a declared critical path.

This test imports ``charter.offering.api`` explicitly and asserts every advertised
``__all__`` name resolves, so its coverage is anchored to an intentional test
rather than an incidental import chain. (#3321 landing squad — verification-gap
hardening; sibling of the ``tests/charter`` facade-import lock.)
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.fast


def test_offering_api_all_symbols_resolve() -> None:
    import charter.offering.api as api

    exported = getattr(api, "__all__", None)
    assert exported, "charter.offering.api must declare a non-empty __all__"
    unresolved = [name for name in exported if getattr(api, name, None) is None]
    assert not unresolved, f"charter.offering.api advertises unresolved/None __all__ names: {unresolved}"
