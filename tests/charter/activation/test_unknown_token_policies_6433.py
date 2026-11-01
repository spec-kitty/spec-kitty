"""One pinned unknown-token policy per surface (#6433).

Issue #6433 asks for one behaviour per surface when an activation token names nothing any
searched layer knows. This module states all four in one place, so a refactor that changes
one surface's policy fails exactly one test here:

===============  ==========================================  ====================================
surface          policy                                      observable
===============  ==========================================  ====================================
runtime gate     warn and keep                               one warning, token kept best-effort
consistency      report once and keep                         one ``unknown_references`` row
check
compile          refuse                                       ``UnknownArtifactIdError``
cascade source   no source, no error                          ``_source_urn`` is ``None``
resolver
===============  ==========================================  ====================================

Every row goes through the surface it names: ``IdentityIndex.activation_id`` for the gate,
``_check_unknown_references`` for the check, ``resolve_config_activated_roots`` for compile and
``_source_urn`` for the cascade source. The first three have richer fixtures in
``tests/charter/activation/test_compile_check_identity_6433.py``; this module keeps the table
executable in one file and adds the cascade-source row.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from charter.activation.compiler import resolve_config_activated_roots
from charter.activation.consistency_check import _check_unknown_references
from charter.activation.identity_index import IdentityIndex
from charter.activation.kind_vocabulary import ArtifactKind, UnknownArtifactIdError
from specify_cli.cli.commands.charter.activate import _source_urn
from tests._factories.activation_ledger import seed_activation_ledger

pytestmark = [pytest.mark.fast]

UNKNOWN = "ghost-token"
KNOWN_STEM = "024-locality-of-change"


def _repo(tmp_path: Path) -> Path:
    (tmp_path / ".kittify").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".kittify" / "config.yaml").write_text("{}\n", encoding="utf-8")
    return tmp_path


def test_runtime_gate_warns_once_and_keeps_the_token(tmp_path: Path) -> None:
    """Warn and keep: the unknown directive token survives as a best-effort id, with one warning."""
    index = IdentityIndex.build(_repo(tmp_path))
    warnings: list[str] = []

    assert index.activation_id(ArtifactKind.DIRECTIVE, UNKNOWN, warnings) == "GHOST_TOKEN"
    assert len(warnings) == 1 and UNKNOWN in warnings[0]
    # Positive control: a known token resolves with no warning at all.
    warnings.clear()
    assert index.activation_id(ArtifactKind.DIRECTIVE, KNOWN_STEM, warnings) == "DIRECTIVE_024"
    assert warnings == []


def test_consistency_check_reports_the_unknown_token_once_and_keeps_it(tmp_path: Path) -> None:
    """Report once and keep: one ``unknown_references`` row, no second report from a parity check."""
    index = IdentityIndex.build(_repo(tmp_path))
    unknown_references: list[str] = []
    suggestions: list[str] = []

    _check_unknown_references({"directive": frozenset({UNKNOWN, KNOWN_STEM})}, {}, unknown_references, suggestions, identity=index)

    assert unknown_references == [f"directive/{UNKNOWN}"]
    assert len(suggestions) == 1
    # Positive control: the known token on the same fixture is not reported.
    assert f"directive/{KNOWN_STEM}" not in unknown_references[0]


def test_compile_refuses_the_unknown_token(tmp_path: Path) -> None:
    """Refuse: compile fails closed with the layer-naming error, never a silent drop."""
    root = _repo(tmp_path)
    seed_activation_ledger(root, mission_type_activations=["software-dev"], activated_directives=[UNKNOWN])

    with pytest.raises(UnknownArtifactIdError) as caught:
        resolve_config_activated_roots(repo_root=root)

    assert UNKNOWN in str(caught.value)
    assert "Searched layers:" in str(caught.value)
    # Positive control: the same compile on a known token resolves it, on the same fixture.
    seed_activation_ledger(root, mission_type_activations=["software-dev"], activated_directives=[KNOWN_STEM])
    assert "DIRECTIVE_024" in resolve_config_activated_roots(repo_root=root).directives
    assert "Searched layers:" in str(caught.value)


def test_cascade_source_resolution_yields_no_source_and_does_not_raise(tmp_path: Path) -> None:
    """No source, no error: the command still reports the activation it performed."""
    root = _repo(tmp_path)
    seed_activation_ledger(root, mission_type_activations=["software-dev"])

    assert _source_urn("directive", UNKNOWN, {"project": root / ".kittify" / "charter-packs"}, []) is None
    # Positive control: the same call resolves a known stem to its DRG node.
    assert _source_urn("directive", KNOWN_STEM, {"project": root / ".kittify" / "charter-packs"}, []) == "directive:DIRECTIVE_024"
