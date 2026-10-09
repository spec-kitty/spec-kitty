"""Focused unit tests for the override-adjudication predicates.

These pin :func:`charter.offering.drg.override_policy.find_overridden_builtins` and
:func:`charter.offering.drg.override_policy.adjudicate_overrides` directly at their
production home. Inputs are built from the real ``DRGGraph`` / ``DRGNode`` /
``ReplaceableBuiltinsPolicy`` constructors (no placeholder stubs, C-007), so a
regression in the pure predicates fails here without a live merge or any file I/O.

``adjudicate_overrides`` implements the sanction decision table of mission
``pack-shipped-builtin-override-sanction-01M45WB7`` (spec.md); one test per row, plus
the cross-pack, revocation and reason cells.
"""

from __future__ import annotations

import pytest

from charter.offering.drg.models import DRGGraph, DRGNode, NodeKind
from charter.offering.drg.override_policy import (
    EffectiveOverridePolicy,
    OverriddenBuiltin,
    OverrideAdjudication,
    ReplaceableBuiltin,
    ReplaceableBuiltinsPolicy,
    SanctionedOverride,
    UnsanctionedOverride,
    adjudicate_overrides,
    find_overridden_builtins,
    sanction_reason_missing,
)

pytestmark = pytest.mark.fast

_NOT_LISTED = (
    "not on .kittify/charter-packs/replaceable-builtins.yaml or pack '{pack}' "
    "replaceable-builtins.yaml"
)
_REVOKED = (
    "pack '{pack}' sanction revoked by .kittify/charter-packs/replaceable-builtins.yaml "
    "(revoked_pack_sanctions)"
)
_CONSUMER_REASON = "directive override requires a non-empty reason"
_PACK_REASON = (
    "directive override requires a non-empty reason (pack '{pack}' "
    "replaceable-builtins.yaml)"
)
_DIRECTIVE = "directive:shared"
_TACTIC = "tactic:shared"


def _node(urn: str, kind: NodeKind, provenance: str | None) -> DRGNode:
    return DRGNode(urn=urn, kind=kind, label="Node", provenance=provenance)


def _graph(*nodes: DRGNode) -> DRGGraph:
    return DRGGraph(
        schema_version="1.0",
        generated_at="2026-06-27T00:00:00Z",
        generated_by="unit-test",
        nodes=list(nodes),
        edges=[],
    )


def _policy(
    *entries: tuple[str, str],
    revoked_urns: tuple[str, ...] = (),
    revoked_packs: tuple[str, ...] = (),
) -> ReplaceableBuiltinsPolicy:
    return ReplaceableBuiltinsPolicy(
        entries=tuple(ReplaceableBuiltin(urn=u, reason=r) for u, r in entries),
        revoked_urns=frozenset(revoked_urns),
        revoked_packs=frozenset(revoked_packs),
    )


def _effective(
    consumer: ReplaceableBuiltinsPolicy | None = None,
    **packs: ReplaceableBuiltinsPolicy,
) -> EffectiveOverridePolicy:
    return EffectiveOverridePolicy(
        consumer=consumer or _policy(),
        packs=packs,
        pack_errors=(),
    )


def _override(urn: str = _TACTIC, pack: str = "acme") -> OverriddenBuiltin:
    kind = urn.split(":", 1)[0]
    return OverriddenBuiltin(urn=urn, kind=kind, pack=pack)


def _verdict(
    effective: EffectiveOverridePolicy, override: OverriddenBuiltin | None = None
) -> OverrideAdjudication:
    return adjudicate_overrides([override or _override()], effective)


def _only_why(result: OverrideAdjudication) -> str:
    assert result.sanctioned == []
    assert len(result.unsanctioned) == 1
    why: str = result.unsanctioned[0].why
    return why


# ---------------------------------------------------------------------------
# find_overridden_builtins -- provenance + built-in scope
# ---------------------------------------------------------------------------


def test_org_provenance_at_builtin_urn_is_detected_with_its_pack() -> None:
    merged = _graph(_node(_TACTIC, NodeKind.TACTIC, "org:rogue"))
    assert find_overridden_builtins(merged, frozenset({_TACTIC})) == [
        OverriddenBuiltin(urn=_TACTIC, kind="tactic", pack="rogue")
    ]


def test_pack_name_containing_a_colon_is_preserved() -> None:
    merged = _graph(_node(_TACTIC, NodeKind.TACTIC, "org:team:alpha"))
    (found,) = find_overridden_builtins(merged, frozenset({_TACTIC}))
    assert found.pack == "team:alpha"


def test_project_provenance_at_builtin_urn_is_out_of_scope() -> None:
    # Project-tier overrides are the trusted operator tier and are deliberately NOT
    # adjudicated by the consumer-facing allowlist (C-006).
    merged = _graph(_node(_TACTIC, NodeKind.TACTIC, "project"))
    assert find_overridden_builtins(merged, frozenset({_TACTIC})) == []


def test_org_provenance_at_non_builtin_urn_is_ignored() -> None:
    merged = _graph(_node("tactic:novel", NodeKind.TACTIC, "org:rogue"))
    assert find_overridden_builtins(merged, frozenset({_TACTIC})) == []


def test_builtin_provenance_node_is_not_an_override() -> None:
    merged = _graph(_node(_TACTIC, NodeKind.TACTIC, "built-in"))
    assert find_overridden_builtins(merged, frozenset({_TACTIC})) == []


def test_detected_overrides_are_sorted_by_urn() -> None:
    merged = _graph(
        _node("tactic:zeta", NodeKind.TACTIC, "org:p"),
        _node("tactic:alpha", NodeKind.TACTIC, "org:p"),
    )
    urns = frozenset({"tactic:zeta", "tactic:alpha"})
    assert [o.urn for o in find_overridden_builtins(merged, urns)] == [
        "tactic:alpha",
        "tactic:zeta",
    ]


# ---------------------------------------------------------------------------
# adjudicate_overrides -- the decision table, one test per row
# ---------------------------------------------------------------------------


def test_row1_valid_consumer_entry_sanctions_with_source_consumer() -> None:
    result = _verdict(_effective(_policy((_TACTIC, ""))))
    assert result.unsanctioned == []
    assert result.sanctioned == [
        SanctionedOverride(
            urn=_TACTIC, kind="tactic", pack="acme", source="consumer", reason=""
        )
    ]


def test_row1_consumer_listing_wins_over_pack_and_over_revocation() -> None:
    consumer = _policy((_TACTIC, "mine"), revoked_urns=(_TACTIC,), revoked_packs=("acme",))
    result = _verdict(_effective(consumer, acme=_policy((_TACTIC, "theirs"))))
    assert [(s.source, s.reason) for s in result.sanctioned] == [("consumer", "mine")]


def test_row2_valid_pack_entry_sanctions_with_source_pack() -> None:
    result = _verdict(_effective(acme=_policy((_TACTIC, "pack says so"))))
    assert result.unsanctioned == []
    assert result.sanctioned == [
        SanctionedOverride(
            urn=_TACTIC, kind="tactic", pack="acme", source="pack", reason="pack says so"
        )
    ]


def test_row3_revocation_by_urn_makes_a_pack_sanction_unsanctioned() -> None:
    effective = _effective(
        _policy(revoked_urns=(_TACTIC,)), acme=_policy((_TACTIC, "x"))
    )
    assert _only_why(_verdict(effective)) == _REVOKED.format(pack="acme")


def test_row3_revocation_by_pack_makes_a_pack_sanction_unsanctioned() -> None:
    effective = _effective(
        _policy(revoked_packs=("acme",)), acme=_policy((_TACTIC, "x"))
    )
    assert _only_why(_verdict(effective)) == _REVOKED.format(pack="acme")


def test_row4_not_listed_anywhere_is_unsanctioned_fail_closed() -> None:
    why = _only_why(_verdict(_effective()))
    assert why == _NOT_LISTED.format(pack="acme")
    assert "replaceable-builtins" in why


def test_row4_pack_without_a_sanction_file_is_unsanctioned() -> None:
    # The pack is simply absent from ``packs`` (no file / failed to load).
    assert _only_why(_verdict(_effective(_policy((_DIRECTIVE, "r"))))) == _NOT_LISTED.format(pack="acme")


def test_row5_pack_directive_with_empty_reason_names_the_pack() -> None:
    effective = _effective(acme=_policy((_DIRECTIVE, "   ")))
    why = _only_why(_verdict(effective, _override(_DIRECTIVE)))
    assert why == _PACK_REASON.format(pack="acme")


def test_row6_consumer_directive_with_empty_reason_is_unsanctioned() -> None:
    effective = _effective(_policy((_DIRECTIVE, "")))
    why = _only_why(_verdict(effective, _override(_DIRECTIVE)))
    assert why == _CONSUMER_REASON


def test_consumer_directive_without_reason_is_sanctioned_by_pack_with_reason() -> None:
    effective = _effective(
        _policy((_DIRECTIVE, "")), acme=_policy((_DIRECTIVE, "pack reason"))
    )
    result = _verdict(effective, _override(_DIRECTIVE))
    assert [(s.source, s.pack) for s in result.sanctioned] == [("pack", "acme")]


def test_non_directive_override_needs_no_reason() -> None:
    result = _verdict(_effective(acme=_policy((_TACTIC, ""))))
    assert [s.source for s in result.sanctioned] == ["pack"]


# ---------------------------------------------------------------------------
# Scoping, revocation edges and the cells the post-tasks squad flagged
# ---------------------------------------------------------------------------


def test_pack_b_cannot_sanction_pack_a_override() -> None:
    effective = _effective(b=_policy((_TACTIC, "b's list")))
    assert _only_why(_verdict(effective, _override(pack="a"))) == _NOT_LISTED.format(pack="a")


def test_inert_pack_entry_for_a_non_overridden_urn_changes_nothing() -> None:
    effective = _effective(acme=_policy(("tactic:other", "inert")))
    assert adjudicate_overrides([], effective) == OverrideAdjudication(sanctioned=[], unsanctioned=[])
    assert _only_why(_verdict(effective)) == _NOT_LISTED.format(pack="acme")


def test_consumer_valid_with_malformed_pack_is_sanctioned_by_consumer() -> None:
    # A broken pack file is absent from ``packs`` and recorded in ``pack_errors``;
    # report health is WP02's concern, the verdict stays "consumer sanctioned".
    effective = EffectiveOverridePolicy(
        consumer=_policy((_TACTIC, "")),
        packs={},
        pack_errors=("pack 'acme' broken",),
    )
    result = _verdict(effective)
    assert [s.source for s in result.sanctioned] == ["consumer"]


def test_invalid_consumer_entry_valid_pack_and_revocation_reports_the_revocation() -> None:
    effective = _effective(
        _policy((_DIRECTIVE, ""), revoked_urns=(_DIRECTIVE,)),
        acme=_policy((_DIRECTIVE, "pack reason")),
    )
    why = _only_why(_verdict(effective, _override(_DIRECTIVE)))
    assert why == _REVOKED.format(pack="acme")


def test_revoking_a_urn_the_pack_never_sanctioned_reports_not_listed() -> None:
    effective = _effective(_policy(revoked_urns=(_TACTIC,)), acme=_policy())
    assert _only_why(_verdict(effective)) == _NOT_LISTED.format(pack="acme")


def test_revocation_naming_another_pack_does_not_affect_this_one() -> None:
    effective = _effective(
        _policy(revoked_packs=("other",)), acme=_policy((_TACTIC, "x"))
    )
    assert [s.source for s in _verdict(effective).sanctioned] == ["pack"]


def test_pack_name_containing_a_colon_is_scoped_exactly() -> None:
    effective = _effective(**{"team:alpha": _policy((_TACTIC, "x"))})
    result = _verdict(effective, _override(pack="team:alpha"))
    assert [(s.pack, s.source) for s in result.sanctioned] == [("team:alpha", "pack")]
    assert _only_why(_verdict(effective, _override(pack="team"))) == _NOT_LISTED.format(pack="team")


def test_mixed_batch_is_partitioned_and_keeps_input_order() -> None:
    effective = _effective(acme=_policy(("tactic:ok", "")))
    overrides = [_override("tactic:ok"), _override("tactic:bad")]
    result = adjudicate_overrides(overrides, effective)
    assert [s.urn for s in result.sanctioned] == ["tactic:ok"]
    assert result.unsanctioned == [
        UnsanctionedOverride(
            urn="tactic:bad", kind="tactic", why=_NOT_LISTED.format(pack="acme")
        )
    ]


@pytest.mark.parametrize(
    ("urn", "reason", "missing"),
    [
        ("directive:x", "", True),
        ("directive:x", "   \n", True),
        ("directive:x", "because", False),
        ("tactic:x", "", False),
        ("tactic:x", "because", False),
    ],
)
def test_sanction_reason_missing_is_directive_only(urn: str, reason: str, missing: bool) -> None:
    assert sanction_reason_missing(urn, reason) is missing


def test_broken_pack_file_is_reported_as_unreadable_not_as_unlisted() -> None:
    effective = EffectiveOverridePolicy(
        consumer=_policy(),
        packs={},
        pack_errors=("pack 'acme' /x/replaceable-builtins.yaml: boom",),
        pack_error_names=frozenset({"acme"}),
    )
    why = _only_why(_verdict(effective))
    assert why == "pack 'acme' replaceable-builtins.yaml could not be read (see the sanction file errors)"
    assert "not on" not in why


def test_unlisted_urn_of_a_healthy_pack_keeps_the_not_listed_wording() -> None:
    effective = EffectiveOverridePolicy(
        consumer=_policy(), packs={}, pack_error_names=frozenset({"other"})
    )
    assert _only_why(_verdict(effective)) == _NOT_LISTED.format(pack="acme")
