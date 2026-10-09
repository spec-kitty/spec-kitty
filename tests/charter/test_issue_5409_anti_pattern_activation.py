"""Issue #5409 — anti-pattern activation, end to end (red-first regression).

Provenance
----------
`ActivationEntry` advertised ``anti_pattern`` as an accepted ``artifact_kind``
alias (via the authority-derived ``CHARTER_ACTIVATABLE_SINGULAR_TO_PLURAL``
map) but then rejected it, because the registry's ``_ALLOWED_KINDS`` mirror was
a hand-copied literal that omitted ``anti_patterns``. Triage (Stijn,
2026-09-30) ruled anti-patterns ARE charter-activatable in the 4.x model and
must work end to end.

This test is the ADR ``2026-07-17-1`` red-first reproduction the P0 requires:
it is RED on the pre-fix registry (``ActivationEntry`` raises for
``anti_pattern``) and GREEN once the activation kind vocabulary is derived from
the single ``ArtifactKind`` authority. It also pins the end-to-end reach into
``PackContext.activated_anti_patterns`` so the runtime consumer that already
exists is exercised, not just the validator.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from charter.activation.activations import ActivationEntry, normalize_artifact_kind
from charter.activation.pack_context import PackContext

pytestmark = [pytest.mark.fast, pytest.mark.regression]


@pytest.mark.parametrize("kind", ["anti_pattern", "anti_patterns"])
def test_activation_entry_accepts_anti_pattern(kind: str) -> None:
    """The activation registry accepts the anti-pattern kind (both spellings).

    RED before #5409: ``_ALLOWED_KINDS`` omitted ``anti_patterns`` while the
    alias map advertised ``anti_pattern`` — a self-contradicting rejection.
    """
    entry = ActivationEntry(
        activation_context={"action": "implement"},
        charter_pack_id="project",
        artifact_id="some-anti-pattern",
        artifact_kind=kind,
    )
    assert entry.artifact_kind == "anti_patterns"


def test_normalize_artifact_kind_round_trips_anti_pattern() -> None:
    """The singular alias normalises to the canonical plural."""
    assert normalize_artifact_kind("anti_pattern") == "anti_patterns"
    assert normalize_artifact_kind("anti_patterns") == "anti_patterns"


def test_anti_pattern_activation_reaches_pack_context(tmp_path: Path) -> None:
    """Activating anti-pattern node IDs surfaces on ``PackContext`` end to end.

    ``PackContext.activated_anti_patterns`` is the existing runtime consumer
    (``drg_activation`` gates anti-pattern nodes on it). This proves the
    activation state flows from ``.kittify/config.yaml`` to the snapshot the
    doctrine resolver reads.
    """
    kittify = tmp_path / ".kittify"
    kittify.mkdir()
    (kittify / "config.yaml").write_text(
        "activated_anti_patterns:\n  - naive-retry\n  - god-object\n",
        encoding="utf-8",
    )

    ctx = PackContext.from_config(tmp_path)

    assert ctx.activated_anti_patterns == frozenset({"naive-retry", "god-object"})
