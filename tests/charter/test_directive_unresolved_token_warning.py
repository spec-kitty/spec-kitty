"""#4240 -- a stale/mistyped ``activated_directives`` entry that neither
resolves via URN nor names a known catalog id is silently best-effort
normalized by ``DoctrineService.directives`` (``charter.activation.resolver``)
and can co-activate an unrelated directive. This is legacy-compat behavior,
not a bug to fix outright (C-003: the resolution *result* must not change) --
but the silence is a gap. A per-token WARNING must fire on that
fully-unresolvable fallback, naming both the raw token and its normalized
form, so the drift is observable.

The WARNING must fire ONLY on the fully-unresolvable path -- i.e. only when
the token is neither URN-resolvable nor a known catalog id already present
in ``all_directives``. It must stay silent both when ``resolve_artifact_urn``
succeeds outright (stem/catalog-id resolution) and when the token matches a
known catalog id verbatim after URN resolution fails (the
``token in all_directives`` sub-branch) -- a warning on every resolution
would be noise (FR-004).

In every case the delivered ``.directives`` set must be exactly what it was
before this change (C-001/C-003) -- the warning is a signal, not a gate.
"""

from __future__ import annotations

import logging
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from charter.activation.pack_context import PackContext
from charter.activation.resolver import DoctrineService

pytestmark = pytest.mark.fast


def _directive(directive_id: str) -> MagicMock:
    item = MagicMock()
    item.id = directive_id
    return item


def _ctx_activating(repo_root: Path, tokens: frozenset[str]) -> PackContext:
    return PackContext(
        activated_kinds=frozenset({"directives"}),
        activated_mission_types=frozenset({"software-dev"}),
        pack_roots=(),
        org_pack_names=(),
        repo_root=repo_root,
        activated_directives=tokens,
    )


def test_unresolvable_token_warns_once_naming_token_and_normalized_form(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    # "999-ghost-directive" names no real directive: it is not URN-resolvable
    # (no such stem/catalog id exists) and does not match any key in
    # ``all_directives`` -- the fully-unresolvable fallback path.
    real = _directive("DIRECTIVE_025")
    inner = MagicMock()
    inner.directives.list_all.return_value = [real]
    ctx = _ctx_activating(tmp_path, frozenset({"999-ghost-directive"}))

    with caplog.at_level(logging.WARNING):
        gated = DoctrineService(inner, pack_context=ctx).directives

    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 1
    message = warnings[0].getMessage()
    assert "999-ghost-directive" in message
    assert "DIRECTIVE_999" in message

    # Outcome unchanged: the ghost token normalizes to DIRECTIVE_999, which
    # matches nothing in all_directives, so nothing is delivered.
    assert gated == {}


@pytest.mark.parametrize(
    "tokens",
    [
        frozenset({"025-boy-scout-rule"}),  # resolves via URN (filename stem)
        frozenset({"DIRECTIVE_025"}),  # matches a known catalog id verbatim
    ],
)
def test_resolvable_token_emits_no_warning(tmp_path: Path, caplog: pytest.LogCaptureFixture, tokens: frozenset[str]) -> None:
    boy_scout = _directive("DIRECTIVE_025")
    inner = MagicMock()
    inner.directives.list_all.return_value = [boy_scout]
    ctx = _ctx_activating(tmp_path, tokens)

    with caplog.at_level(logging.WARNING):
        gated = DoctrineService(inner, pack_context=ctx).directives

    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert warnings == []

    # Outcome unchanged: the resolvable token still activates DIRECTIVE_025.
    assert set(gated) == {"DIRECTIVE_025"}
    assert gated["DIRECTIVE_025"] is boy_scout
