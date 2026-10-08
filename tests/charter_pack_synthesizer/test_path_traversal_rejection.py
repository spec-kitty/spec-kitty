"""Path traversal rejection — schema pattern + apply-time containment check.

Covers SEC-1 from the post-merge review: a malicious or buggy
retrospective.yaml MUST NOT be able to write outside the project's
``.kittify/glossary/`` or ``.kittify/charter-packs/{kind}/`` buckets via crafted
``term_key`` or ``artifact_id`` strings.

Schema-level: ``term_key`` and ``artifact_id`` carry a Pydantic ``pattern``
constraint that rejects any value containing ``/``, ``\\``, ``..``, or
leading dots/underscores at construction time.

Apply-time: ``_assert_within`` resolves the target path and confirms it
stays inside the artifact base, defending against any future regression
that lets a payload sneak past the schema (e.g., new payload kinds, schema
loosening, or unicode normalization tricks).
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from specify_cli.retrospective.schema import (
    AddGlossaryTermPayload,
    SynthesizeDirectivePayload,
    SynthesizeProcedurePayload,
    SynthesizeScope,
    SynthesizeTacticPayload,
    UpdateGlossaryTermPayload,
)

pytestmark = pytest.mark.fast

_EMPTY_SCOPE = SynthesizeScope()


# ---------------------------------------------------------------------------
# term_key — schema rejects traversal
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "bad_term",
    [
        "../escape",
        "../../etc/passwd",
        "..",
        "foo/bar",
        "foo\\bar",
        ".hidden",
        "",
        "name with spaces",
        "trailing/",
        "/leading-slash",
        "term$injection",
        "foo..bar",
        "..foo",
    ],
)
def test_add_glossary_term_rejects_unsafe_term_key(bad_term: str) -> None:
    with pytest.raises(ValidationError):
        AddGlossaryTermPayload(
            kind="add_glossary_term",
            term_key=bad_term,
            definition="anything",
            definition_hash="sha256:" + "a" * 64,
        )


@pytest.mark.parametrize(
    "bad_term",
    [
        "../escape",
        "..",
        "foo/bar",
        "foo\\bar",
        ".hidden",
    ],
)
def test_update_glossary_term_rejects_unsafe_term_key(bad_term: str) -> None:
    with pytest.raises(ValidationError):
        UpdateGlossaryTermPayload(
            kind="update_glossary_term",
            term_key=bad_term,
            definition="anything",
            definition_hash="sha256:" + "a" * 64,
        )


@pytest.mark.parametrize(
    "good_term",
    [
        "alpha",
        "alpha-beta",
        "alpha_beta",
        "alpha.beta",
        "term-001",
        "abc123",
        "a",
        "DIRECTIVE_001",
        "TACTIC_phase_2",
        "PROCEDURE-v2",
        "_leading-underscore",
        "Mixed.Case-Identifier",
    ],
)
def test_add_glossary_term_accepts_safe_term_key(good_term: str) -> None:
    payload = AddGlossaryTermPayload(
        kind="add_glossary_term",
        term_key=good_term,
        definition="ok",
        definition_hash="sha256:" + "a" * 64,
    )
    assert payload.term_key == good_term


@pytest.mark.parametrize(
    "good_id",
    [
        "DIRECTIVE_001",
        "TACTIC_phase_2",
        "PROCEDURE-v2",
        "PROJECT_001",
        "DIRECTIVE_NEW_EXAMPLE",
        "tactic-lowercase-style",
    ],
)
def test_synthesize_directive_accepts_documented_artifact_ids(good_id: str) -> None:
    """Documented contract IDs (uppercase, mixed case, hyphenated) all pass."""
    payload = SynthesizeDirectivePayload(
        kind="synthesize_directive",
        artifact_id=good_id,
        body="body",
        body_hash="sha256:" + "a" * 64,
        scope=_EMPTY_SCOPE,
    )
    assert payload.artifact_id == good_id


# ---------------------------------------------------------------------------
# artifact_id — schema rejects traversal on every synthesize_* kind
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "model_cls,kind_literal",
    [
        (SynthesizeDirectivePayload, "synthesize_directive"),
        (SynthesizeTacticPayload, "synthesize_tactic"),
        (SynthesizeProcedurePayload, "synthesize_procedure"),
    ],
)
@pytest.mark.parametrize(
    "bad_id",
    [
        "../escape",
        "../../etc/passwd",
        "..",
        "foo/bar",
        "foo\\bar",
        ".hidden",
        "",
    ],
)
def test_synthesize_payloads_reject_unsafe_artifact_id(model_cls: type, kind_literal: str, bad_id: str) -> None:
    with pytest.raises(ValidationError):
        model_cls(
            kind=kind_literal,
            artifact_id=bad_id,
            body="ignored",
            body_hash="sha256:" + "a" * 64,
            scope=_EMPTY_SCOPE,
        )


# ---------------------------------------------------------------------------
# Apply-time containment defense in depth
# ---------------------------------------------------------------------------


def test_assert_within_blocks_targets_outside_base(tmp_path) -> None:
    """Even if a future regression slips a traversal past schema validation,
    ``_assert_within`` MUST refuse to write outside the artifact base."""
    from specify_cli.charter_pack_synthesizer.apply import _assert_within

    base = tmp_path / "glossary"
    base.mkdir()
    outside = tmp_path / "etc" / "passwd.yaml"

    with pytest.raises(ValueError, match="refusing to write outside"):
        _assert_within(base, outside)


def test_assert_within_allows_targets_inside_base(tmp_path) -> None:
    from specify_cli.charter_pack_synthesizer.apply import _assert_within

    base = tmp_path / "glossary"
    base.mkdir()
    inside = base / "term.yaml"
    resolved = _assert_within(base, inside)
    assert resolved.is_relative_to(base.resolve())
